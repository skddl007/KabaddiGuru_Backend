"""
AI-Powered Question Suggestion Module
Uses AI to generate contextual follow-up questions based on conversation history and cache memory
"""
import random
from typing import List, Dict, Any, Optional

# AI-powered question generation prompt - Simplified and dataset-focused
AI_SUGGESTION_PROMPT = """
You are a Kabaddi analytics assistant. Based on the conversation history, generate 4 simple follow-up questions that can be answered using the S_RBR database table.

CONVERSATION CONTEXT:
{conversation_history}

LAST USER QUESTION: {last_question}
LAST AI RESPONSE: {last_response}

AVAILABLE DATA COLUMNS in S_RBR table:
- Season, Match_Number, Team_A_Name, Team_B_Name
- Attacking_Player_Name, Defending_Team_Code, Attacking_Team_Code
- Game_Half_Period (1 or 2), Points_Scored_By_Attacker, Points_Scored_By_Defenders
- Attack_Result_Status, Defense_Result_Status
- Do_Or_Die_Mandatory_Raid, Bonus_Point_Available, Super_Tackle_Opportunity
- Attack_Techniques_Used, Defense_Techniques_Used
- Match_Winner_Team, Final_Team_A_Score, Final_Team_B_Score

GUIDELINES:
1. Generate SIMPLE questions that can be answered with basic SQL queries
2. Focus on data that actually exists in the S_RBR table
3. Use common Kabaddi terms: raids, points, teams, players, successful/failed
4. Avoid complex analytical questions that require advanced calculations
5. Make questions specific but not overly complex

SIMPLE QUESTION TYPES TO USE:
- Count questions: "How many successful raids did [player] have?"
- List questions: "Show me all raids by [player/team]"
- Compare questions: "Compare points scored by [team A] vs [team B]"
- Filter questions: "Show raids in [period 1/2] or [do-or-die situations]"
- Top questions: "Show top players by [points/raids]"

OUTPUT FORMAT:
Generate exactly 4 simple questions, one per line, without numbering.

EXAMPLE OUTPUT:
Show me all successful raids by Pawan Sehrawat
How many points did Bengaluru Bulls score in period 1
Compare raid success rates between TT and BB teams
List all do-or-die raids in the season

YOUR GENERATED QUESTIONS:
"""

class AIQuestionSuggester:
    def __init__(self, llm=None):
        self.llm = llm
        self.question_cache = []  # Store popular questions from cache
        
        # Improved fallback questions - simpler and dataset-appropriate
        self.fallback_questions = [
            "Show me the top raiders with most successful raids",
            "How many points did Bengaluru Bulls score in this season?",
            "Show me all raids by Pawan Sehrawat",
            "Compare raid success rates between TT and BB teams",
            "List all do-or-die raids in the season",
            "Show me super tackle opportunities by team",
            "How many successful raids did each team have?",
            "Show me raids in period 1 vs period 2",
            "Which players scored the most raid points?",
            "Show me all bonus point raids",
            "Compare final scores between teams",
            "Show me raids with successful defense"
        ]
    
    def update_cache_questions(self, query_cache):
        """Update popular questions from cache memory"""
        if hasattr(query_cache, 'sql_cache'):
            # Extract popular questions from cache
            cached_questions = []
            for question_hash, sql in list(query_cache.sql_cache.items())[:10]:
                # Try to reverse engineer the question from SQL (simplified)
                cached_questions.append("Popular cached query")
            self.question_cache = cached_questions[:5]
    
    def get_conversation_context(self, conversation_memory) -> str:
        """Extract relevant conversation context"""
        if not hasattr(conversation_memory, 'history') or not conversation_memory.history:
            return "No previous conversation."
        
        # Get last 3 conversation turns
        recent_turns = list(conversation_memory.history)[-3:]
        context_parts = []
        
        for turn in recent_turns:
            if hasattr(turn, 'user_question'):
                context_parts.append(f"User: {turn.user_question}")
                if hasattr(turn, 'ai_response'):
                    # Truncate long responses
                    response = turn.ai_response[:150] + "..." if len(turn.ai_response) > 150 else turn.ai_response
                    context_parts.append(f"AI: {response}")
        
        return "\n".join(context_parts) if context_parts else "No previous conversation."
    
    def get_suggestions(self, num_suggestions: int = 4, conversation_memory=None, query_cache=None, team: Optional[str] = None) -> List[str]:
        """Get AI-generated question suggestions based on conversation context.

        If a team is provided, bias suggestions toward that team and its players/matches.
        """

        # If no LLM available, use fallback (team-aware if provided)
        if not self.llm:
            return self._get_team_fallback_suggestions(team, num_suggestions) if team else self._get_fallback_suggestions(num_suggestions)

        try:
            # Update cache questions
            if query_cache:
                self.update_cache_questions(query_cache)

            # Get conversation context
            conversation_context = self.get_conversation_context(conversation_memory) if conversation_memory else "No previous conversation."

            # Get last question and response
            last_question = "No previous question."
            last_response = "No previous response."

            if conversation_memory and hasattr(conversation_memory, 'history') and conversation_memory.history:
                last_turn = conversation_memory.history[-1]
                if hasattr(last_turn, 'user_question'):
                    last_question = last_turn.user_question
                if hasattr(last_turn, 'ai_response'):
                    last_response = last_turn.ai_response[:200] + "..." if len(last_turn.ai_response) > 200 else last_turn.ai_response

            # Prepare popular questions context
            popular_questions = "\n".join(self.question_cache) if self.question_cache else "No cached questions yet."

            # Generate AI suggestions, optionally team-focused
            prompt = AI_SUGGESTION_PROMPT.format(
                conversation_history=conversation_context,
                last_question=last_question,
                last_response=last_response,
                popular_questions=popular_questions
            )

            if team:
                prompt += (
                    f"\n\nSTRICT REQUIREMENTS:\n"
                    f"- Generate questions ONLY about team '{team}'.\n"
                    f"- Do NOT mention, reference, or compare with any other team or their players.\n"
                    f"- Do NOT propose cross-team comparisons.\n"
                    f"- Every question must explicitly relate to '{team}', its players, or its matches.\n"
                )

            # Get AI response
            ai_response = self.llm.invoke(prompt)
            suggestions = ai_response.content.strip().split('\n')

            # Clean up suggestions
            cleaned_suggestions = []
            for suggestion in suggestions:
                suggestion = suggestion.strip()
                # Remove numbering, bullets, etc.
                suggestion = suggestion.lstrip('1234567890.-• ')
                if suggestion and len(suggestion) > 10:  # Valid question
                    cleaned_suggestions.append(suggestion)

            # Ensure we have enough suggestions
            while len(cleaned_suggestions) < num_suggestions:
                if team:
                    cleaned_suggestions.extend(self._get_team_fallback_suggestions(team, 1))
                else:
                    cleaned_suggestions.extend(self._get_fallback_suggestions(1))

            return cleaned_suggestions[:num_suggestions]

        except Exception as e:
            print(f"⚠️ AI suggestion failed: {e}")
            return self._get_team_fallback_suggestions(team, num_suggestions) if team else self._get_fallback_suggestions(num_suggestions)
    
    def _get_fallback_suggestions(self, num_suggestions: int = 4) -> List[str]:
        """Get fallback suggestions when AI is not available"""
        return random.sample(self.fallback_questions, min(num_suggestions, len(self.fallback_questions)))
    
    def get_follow_up_suggestions(self, last_response: str, conversation_memory=None) -> List[str]:
        """Generate AI-powered follow-up suggestions based on the last AI response"""
        
        if not self.llm:
            return self._get_simple_follow_ups(last_response)
        
        try:
            follow_up_prompt = f"""
Based on this AI response about Kabaddi analytics, generate 3 simple follow-up questions that can be answered using the S_RBR database:

AI RESPONSE: {last_response[:300]}...

AVAILABLE DATA: Season, Match_Number, Team_A_Name, Team_B_Name, Attacking_Player_Name, 
Defending_Team_Code, Attacking_Team_Code, Game_Half_Period, Points_Scored_By_Attacker, 
Points_Scored_By_Defenders, Attack_Result_Status, Defense_Result_Status, 
Do_Or_Die_Mandatory_Raid, Bonus_Point_Available, Super_Tackle_Opportunity

Generate 3 simple follow-up questions that:
1. Ask for related data from the same topic
2. Request comparisons or breakdowns
3. Explore different aspects (teams, players, periods, situations)

Keep questions simple and focused on available data.

Output format: One question per line, no numbering.
"""
            
            ai_response = self.llm.invoke(follow_up_prompt)
            suggestions = ai_response.content.strip().split('\n')
            
            # Clean up suggestions
            cleaned_suggestions = []
            for suggestion in suggestions:
                suggestion = suggestion.strip().lstrip('1234567890.-• ')
                if suggestion and len(suggestion) > 10:
                    cleaned_suggestions.append(suggestion)
            
            return cleaned_suggestions[:3]
            
        except Exception:
            return self._get_simple_follow_ups(last_response)
    
    def _get_simple_follow_ups(self, last_response: str) -> List[str]:
        """Simple follow-up suggestions when AI is not available"""
        response_lower = last_response.lower()
        
        follow_ups = []
        
        # Player-focused follow-ups
        if any(word in response_lower for word in ['player', 'raider', 'name', 'pawan', 'sehrawat']):
            follow_ups.append("Show me all raids by this player")
            follow_ups.append("Compare this player's performance with others")
            
        # Team-focused follow-ups
        if any(word in response_lower for word in ['team', 'tt', 'bb', 'pu', 'hs', 'bengaluru', 'telugu']):
            follow_ups.append("Show me all raids by this team")
            follow_ups.append("Compare this team's performance with others")
            
        # Performance-focused follow-ups
        if any(word in response_lower for word in ['successful', 'failed', 'points', 'score']):
            follow_ups.append("Break this down by period")
            follow_ups.append("Show me the detailed statistics")
            
        # Situation-focused follow-ups
        if any(word in response_lower for word in ['do-or-die', 'bonus', 'super tackle']):
            follow_ups.append("Show me all similar situations")
            follow_ups.append("Compare with regular raids")
            
        # Add generic follow-ups if not enough specific ones
        generic_follow_ups = [
            "Show me the opposing team's performance",
            "Compare performance in different periods",
            "Show me related statistics"
        ]
        
        follow_ups.extend(generic_follow_ups)
        return follow_ups[:3]

    def get_dataset_aware_suggestions(self) -> List[str]:
        """Generate suggestions specifically tailored to the S_RBR dataset structure"""
        return [
            "Show me the top raiders with most successful raids",
            "How many points did each team score this season?",
            "Show me all do-or-die raids in the season",
            "Compare raid success rates between teams",
            "Show me super tackle opportunities by team",
            "List all bonus point raids",
            "Show me raids in period 1 vs period 2",
            "Which players scored the most raid points?",
            "Show me all raids with successful defense",
            "Compare final match scores between teams",
            "Show me raids by specific attack techniques",
            "List all matches won by each team"
        ]

    def _get_team_fallback_suggestions(self, team: Optional[str], num_suggestions: int = 4) -> List[str]:
        """Generate simple, team-focused fallback suggestions when AI is unavailable or fails."""
        if not team:
            return self._get_fallback_suggestions(num_suggestions)

        base_templates = [
            f"Show me all raids by {team}",
            f"How many points did {team} score this season?",
            f"Who are the top raiders for {team}?",
            f"Show {team}'s successful raids vs failed raids",
            f"List all do-or-die raids by {team}",
            f"Show super tackle opportunities by {team}",
            f"Breakdown {team}'s points by period",
            f"Show bonus point raids by {team}"
        ]
        # Cycle through templates to satisfy num_suggestions
        result: List[str] = []
        idx = 0
        while len(result) < num_suggestions and base_templates:
            result.append(base_templates[idx % len(base_templates)])
            idx += 1
        return result[:num_suggestions]

# Global question suggester instance - will be initialized with LLM in main.py
question_suggester = None
