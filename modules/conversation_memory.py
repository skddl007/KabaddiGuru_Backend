"""
Conversation Memory Module
Handles chat history, context preservation, and question rephrasing
"""
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import deque

@dataclass
class ConversationTurn:
    """Represents a single conversation turn"""
    timestamp: float
    user_question: str
    sql_query: str
    sql_result: str
    ai_response: str
    tokens_used: int
    response_time: float
    user_feedback: Optional[str] = None

class ConversationMemory:
    def __init__(self, max_history: int = 10):
        self.history: deque = deque(maxlen=max_history)
        self.session_start = time.time()
        self.total_questions = 0
        self.total_tokens = 0
        
    def add_turn(self, turn: ConversationTurn):
        """Add a conversation turn to memory"""
        self.history.append(turn)
        self.total_questions += 1
        self.total_tokens += turn.tokens_used
        
    def get_recent_context(self, num_turns: int = 3) -> str:
        """Get recent conversation context for follow-up questions"""
        if not self.history:
            return ""
            
        recent_turns = list(self.history)[-num_turns:]
        context_parts = []
        
        for turn in recent_turns:
            context_parts.append(f"User: {turn.user_question}")
            context_parts.append(f"AI: {turn.ai_response[:200]}...")
            
        return "\n".join(context_parts)
    
    def get_last_entities(self) -> Dict[str, List[str]]:
        """Extract entities (players, teams, etc.) from recent questions"""
        entities = {
            'players': [],
            'teams': [],
            'positions': [],
            'actions': []
        }
        
        if not self.history:
            return entities
            
        # Team abbreviations
        team_codes = ['BW', 'BB', 'DD', 'GG', 'HS', 'JP', 'PP', 'PU', 'TN', 'TT', 'UM', 'UP']
        
        # Common kabaddi terms
        positions = ['raider', 'defender', 'left', 'right', 'corner', 'cover', 'middle']
        actions = ['raid', 'tackle', 'bonus', 'super tackle', 'all out', 'successful', 'unsuccessful']
        
        recent_text = " ".join([turn.user_question.lower() for turn in list(self.history)[-3:]])
        
        # Extract teams
        for team in team_codes:
            if team.lower() in recent_text:
                entities['teams'].append(team)
                
        # Extract positions
        for pos in positions:
            if pos in recent_text:
                entities['positions'].append(pos)
                
        # Extract actions
        for action in actions:
            if action in recent_text:
                entities['actions'].append(action)
                
        return entities
    
    def is_follow_up_question(self, question: str) -> bool:
        """Determine if this is a follow-up question"""
        if not self.history:
            return False
            
        follow_up_indicators = [
            'what about', 'how about', 'and', 'also', 'what if', 'can you',
            'show me', 'tell me', 'what are', 'which', 'who', 'when',
            'they', 'them', 'that team', 'those players', 'this', 'these'
        ]
        
        question_lower = question.lower()
        return any(indicator in question_lower for indicator in follow_up_indicators)
    
    def rephrase_follow_up(self, question: str) -> str:
        """Rephrase follow-up questions into standalone questions"""
        if not self.is_follow_up_question(question):
            return question
            
        context = self.get_recent_context(2)
        entities = self.get_last_entities()
        
        # Simple rephrasing logic
        rephrased = question
        
        # Replace pronouns with entities from context
        if entities['teams']:
            latest_team = entities['teams'][-1]
            rephrased = rephrased.replace('they', f'team {latest_team}')
            rephrased = rephrased.replace('them', f'team {latest_team}')
            rephrased = rephrased.replace('that team', f'team {latest_team}')
            
        if entities['players']:
            latest_player = entities['players'][-1]
            rephrased = rephrased.replace('he', latest_player)
            rephrased = rephrased.replace('him', latest_player)
            rephrased = rephrased.replace('that player', latest_player)
            
        return rephrased
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        return {
            'session_duration': time.time() - self.session_start,
            'total_questions': self.total_questions,
            'total_tokens': self.total_tokens,
            'avg_tokens_per_question': self.total_tokens / max(1, self.total_questions),
            'conversation_turns': len(self.history)
        }
    
    def export_history(self) -> str:
        """Export conversation history as JSON"""
        history_data = [asdict(turn) for turn in self.history]
        return json.dumps(history_data, indent=2)
    
    def add_feedback(self, feedback: str):
        """Add feedback to the last conversation turn"""
        if self.history:
            self.history[-1].user_feedback = feedback

# Global conversation memory instance
conversation_memory = ConversationMemory()
