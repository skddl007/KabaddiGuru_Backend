# Enhanced Kabaddi Analytics - Simplified API Server
# Runs only Enhanced Chat mode for frontend integration

# IMPORTANT: Load environment variables FIRST, before any imports that might need them
import os
import sys

# Environment Configuration Setup
# Priority: run-env.yaml (deployment) > config.env (local) > system env vars

# Check if we're in deployment mode (Cloud Run)
is_deployment = os.getenv('K_SERVICE') is not None or os.getenv('PORT') is not None

if is_deployment:
    # Load environment variables from run-env.yaml for Cloud Run deployment
    try:
        import yaml
        run_env_path = os.path.join(os.path.dirname(__file__), 'run-env.yaml')
        if os.path.exists(run_env_path):
            with open(run_env_path, 'r') as file:
                env_vars = yaml.safe_load(file)
                for key, value in env_vars.items():
                    os.environ[key] = str(value)
            print("✅ Loaded environment variables from run-env.yaml (deployment mode)")
        else:
            print("⚠️ run-env.yaml not found, using system environment variables")
    except Exception as e:
        print(f"⚠️ Could not load run-env.yaml: {e}")
else:
    # Load environment variables from config.env for local development
    try:
        from dotenv import load_dotenv
        config_path = os.path.join(os.path.dirname(__file__), 'config.env')
        if os.path.exists(config_path):
            load_dotenv(config_path)
            print("✅ Loaded environment variables from config.env (local mode)")
        else:
            print("⚠️ config.env not found, using system environment variables")
    except Exception as e:
        print(f"⚠️ Could not load config.env: {e}")

# Set default values for missing environment variables
if not os.getenv('DB_HOST'):
    os.environ['DB_HOST'] = 'localhost'
if not os.getenv('DB_PORT'):
    os.environ['DB_PORT'] = '5432'
if not os.getenv('DB_NAME'):
    os.environ['DB_NAME'] = 'kabaddi_data'
if not os.getenv('DB_USER'):
    os.environ['DB_USER'] = 'postgres'
if not os.getenv('DB_PASSWORD'):
    os.environ['DB_PASSWORD'] = 'password'
if not os.getenv('JWT_SECRET'):
    os.environ['JWT_SECRET'] = 'your-secret-key-change-in-production'
if not os.getenv('DEBUG'):
    os.environ['DEBUG'] = 'false'

import asyncio
import time
import json
import re
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

# FastAPI imports for API server
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Core modules
from modules.postgresql_loader import load_into_postgresql
from modules.query_cleaner import clean_sql_query, print_sql, normalize_user_query, enhance_query_with_corrections, normalize_skills_in_result
from modules.logging_config import configure_logging
from modules.prompts import SYSTEM_PROMPT_TEMPLATE, ANSWER_PROMPT_TEMPLATE

# Authentication modules
from User_sign.auth_routes import router as auth_router
from User_sign.database import user_db

# Enhanced modules - now properly imported and used
from modules.enhanced_query_cache import query_cache, optimize_prompt_tokens
from modules.conversation_memory import ConversationMemory, ConversationTurn
from modules.question_suggestions import AIQuestionSuggester
from modules.feedback_system import feedback_system, FeedbackEntry
from modules.performance_monitor import performance_monitor, PerformanceMetric
from modules.model_optimizer import model_optimizer

from modules.llm_config import get_llm

# LangChain imports
from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import tiktoken

configure_logging()

# API Models for FastAPI
class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None
    user_id: Optional[int] = None  # For authenticated users
    
    class Config:
        extra = "allow"  # Allow extra fields to prevent validation errors

class ChatResponse(BaseModel):
    response: str
    sql_query: Optional[str] = None
    success: bool
    response_time: float
    suggestions: List[str] = []
    chat_id: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    agent_initialized: bool
    uptime: float

class SummaryRequest(BaseModel):
    chat_id: str

class SummaryResponse(BaseModel):
    summary: str
    session_stats: Dict[str, Any]
    conversation_highlights: List[str]
    success: bool

class FeedbackRequest(BaseModel):
    user_question: str
    ai_response: str
    sql_query: Optional[str] = None
    feedback_type: str  # 'thumbs_up', 'thumbs_down', 'correction', 'suggestion'
    feedback_text: Optional[str] = None
    response_time: float = 0.0
    tokens_used: int = 0
    chat_id: Optional[str] = None

class FeedbackResponse(BaseModel):
    success: bool
    message: str

# Global variables for API server
api_start_time = time.time()

# Performance optimization settings
MAX_CONCURRENT_REQUESTS = 10
# REQUEST_TIMEOUT = 30  # seconds - REMOVED TO PREVENT TIMEOUT ISSUES
CACHE_PRELOAD_ENABLED = True
STREAMING_ENABLED = True

# Initialize enhanced modules
ai_question_suggester = None  # Will be initialized with LLM
enhanced_agent = None  # Will be initialized in lifespan
print("✅ Enhanced modules imported successfully")

# Session Manager for handling multiple conversation sessions
class SessionManager:
    """Manages multiple conversation sessions"""
    def __init__(self):
        self.sessions = {}  # chat_id -> conversation_memory
        
    def get_or_create_session(self, chat_id):
        """Get existing session or create new one"""
        if chat_id not in self.sessions:
            # Use the enhanced conversation memory class
            from modules.conversation_memory import ConversationMemory
            self.sessions[chat_id] = ConversationMemory()
        return self.sessions[chat_id]
    
    def get_session_stats(self, chat_id):
        """Get stats for a specific session"""
        if chat_id in self.sessions:
            return self.sessions[chat_id].get_session_stats()
        return {'total_questions': 0, 'total_tokens': 0, 'avg_tokens_per_question': 0}

# Initialize session manager
session_manager = SessionManager()

# Simple fallback classes for when enhanced modules are not available
class SimpleConversationMemory:
    def __init__(self):
        self.history = []
        self.session_start = time.time()
        self.total_questions = 0
        self.total_tokens = 0
    
    def get_recent_context(self, num_turns: int = 3) -> str:
        return ""
    
    def get_session_stats(self) -> Dict[str, Any]:
        return {
            'session_duration': time.time() - self.session_start,
            'total_questions': self.total_questions,
            'total_tokens': self.total_tokens,
            'avg_tokens_per_question': 0,
            'conversation_turns': len(self.history)
        }

class SimpleQuestionSuggester:
    def get_suggestions(self, count: int = 6, memory=None, cache=None):
        return [
            "Show me the top raiders with most successful raids",
            "How many points did Bengaluru Bulls score this season?",
            "Show me all raids by Pawan Sehrawat",
            "Compare raid success rates between TT and BB teams",
            "List all do-or-die raids in the season",
            "Show me super tackle opportunities by team"
        ]
    
    def get_follow_up_suggestions(self, response: str, memory=None):
        return [
            "Show more detailed statistics",
            "Compare with other teams",
            "Analyze by time period"
        ]

class SimplePerformanceMonitor:
    def __init__(self):
        self.metrics = []
    
    def record_metric(self, duration: float, tokens: int, success: bool):
        self.metrics.append({
            'duration': duration,
            'tokens': tokens,
            'success': success,
            'timestamp': time.time()
        })
    
    def get_stats(self):
        if not self.metrics:
            return {"avg_time": 0, "success_rate": 1.0}
        
        successful = [m for m in self.metrics if m['success']]
        avg_time = sum(m['duration'] for m in successful) / len(successful) if successful else 0
        success_rate = len(successful) / len(self.metrics) if self.metrics else 1.0
        
        return {
            "avg_time": avg_time,
            "success_rate": success_rate
        }

# Initialize simple versions if enhanced modules are not available
# Note: These will be initialized in the lifespan function

# Initialize session manager
session_manager = SessionManager()

class EnhancedKabaddiAgent:
    """Enhanced Kabaddi Analytics Agent with all improvements integrated"""
    
    def __init__(self):
        self.engine = None
        self.db = None
        self.llm = None
        self.table_details = None
        self.execute_query = None
        self.rephrase_answer = None
        self.session_start = time.time()
        
        # Performance optimization attributes
        self.request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.common_queries_cache = {}
        self.table_schema_summary = None
        self.optimized_prompts = {}
    
    def _is_greeting(self, user_input: str) -> bool:
        """Check if the user input is a greeting"""
        # Convert to lowercase and remove extra whitespace
        cleaned_input = user_input.lower().strip()
        
        # Define greeting patterns
        greeting_patterns = [
            r'^hi\b', r'^hello\b', r'^hey\b', r'^good morning\b', r'^good afternoon\b', 
            r'^good evening\b', r'^goodbye\b', r'^bye\b', r'^see you\b', r'^take care\b',
            r'^thanks\b', r'^thank you\b', r'^how are you\b', r'^what\'s up\b', r'^sup\b'
        ]
        
        # Check if input matches any greeting pattern
        for pattern in greeting_patterns:
            if re.search(pattern, cleaned_input):
                return True
        
        return False
    
    def _get_greeting_response(self, user_input: str) -> str:
        """Generate appropriate greeting response for Kabaddi analyst"""
        cleaned_input = user_input.lower().strip()
        
        # Farewell responses
        if any(word in cleaned_input for word in ['bye', 'goodbye', 'see you', 'take care']):
            return "Goodbye! I'm your KabaddiGuru analyst. Feel free to come back anytime to analyze player performance, match statistics, team strategies, and more Kabaddi insights! 🏏"
        
        # Thank you responses
        if any(word in cleaned_input for word in ['thanks', 'thank you']):
            return "You're welcome! I'm here to help you with all your Kabaddi analytics needs. Feel free to ask me about player performance, match statistics, team strategies, or any other Kabaddi-related questions! 🏏"
        
        # How are you responses
        if any(word in cleaned_input for word in ['how are you', 'what\'s up', 'sup']):
            return "I'm doing great! I'm your dedicated KabaddiGuru analyst, ready to help you explore player performance, match statistics, team strategies, and uncover insights from your Kabaddi data. What would you like to analyze today? 🏏"
        
        # General greeting responses
        return "Hello! I'm your KabaddiGuru analyst. I can help you analyze player performance, match statistics, team strategies, and much more from your Kabaddi data. What would you like to know about your Kabaddi analytics? 🏏"
    
    def initialize(self):
        """Initialize the enhanced agent"""
        print("🚀 Initializing Enhanced Kabaddi Analytics Agent...")
        
        # Load data into PostgreSQL
        self.engine = load_into_postgresql()
        self.db = SQLDatabase(self.engine)
        self.llm = get_llm()
        self.table_details = self.db.get_table_info()
        
        # Pre-optimize table schema for faster processing
        self.table_schema_summary = optimize_prompt_tokens("", self.table_details)
        
        # Set up query execution and answer generation
        self.execute_query = QuerySQLDataBaseTool(db=self.db)
        answer_prompt = PromptTemplate.from_template(ANSWER_PROMPT_TEMPLATE)
        self.rephrase_answer = answer_prompt | self.llm | StrOutputParser()
        
        # Initialize AI-powered question suggester with LLM
        global ai_question_suggester
        if AIQuestionSuggester and ai_question_suggester is None:
            ai_question_suggester = AIQuestionSuggester(llm=self.llm)
            print("🤖 AI-powered question suggester initialized")
        elif not isinstance(ai_question_suggester, SimpleQuestionSuggester):
            ai_question_suggester = SimpleQuestionSuggester()
            print("📝 Simple question suggester initialized")
        
        # Preload common queries for faster response
        if CACHE_PRELOAD_ENABLED:
            self._preload_common_queries()
        
        print("✅ Enhanced agent initialized successfully!")
    
    def _preload_common_queries(self):
        """Preload cache with common queries for faster response"""
        common_questions = [
            "Show me the top raiders with most successful raids",
            "How many points did Bengaluru Bulls score in this season?",
            "Show me all raids by Pawan Sehrawat",
            "Compare raid success rates between TT and BB teams",
            "List all do-or-die raids in the season",
            "Show me super tackle opportunities by team",
            "How many successful raids did each team have?",
            "Show me raids in period 1 vs period 2",
            "Which players scored the most raid points?",
            "Show me all bonus point raids"
        ]
        
        print("🔄 Preloading common queries...")
        for question in common_questions:
            try:
                # Pre-generate optimized prompts for common questions
                optimized_prompt = optimize_prompt_tokens(
                    SYSTEM_PROMPT_TEMPLATE.format(
                        input=question,
                        table_info=self.table_details
                    ),
                    self.table_details
                )
                self.optimized_prompts[question] = optimized_prompt
            except Exception as e:
                print(f"Warning: Could not preload query '{question}': {e}")
        
        print(f"✅ Preloaded {len(self.optimized_prompts)} common queries")
        
    def generate_sql_with_caching(self, question: str, session_memory=None) -> Dict[str, str]:
        """Generate SQL with enhanced caching and optimization"""
        # Normalize the question to handle player name variations
        normalized_question = normalize_user_query(question)
        
        # Check cache first (try both original and normalized versions)
        cached_result = query_cache.get_sql(question) or query_cache.get_sql(normalized_question)
        if cached_result:
            return {"raw_query": cached_result, "query": clean_sql_query(cached_result)}
        
        # Check if we have a pre-optimized prompt for this question
        if question in self.optimized_prompts:
            optimized_prompt = self.optimized_prompts[question]
        else:
            # Get conversation context if available
            conversation_context = ""
            if session_memory and hasattr(session_memory, 'get_recent_context'):
                conversation_context = session_memory.get_recent_context(3)
            
            # Check if this is a follow-up question and rephrase if needed
            processed_question = normalized_question  # Use normalized question
            if session_memory and hasattr(session_memory, 'is_follow_up_question') and session_memory.is_follow_up_question(question):
                try:
                    # Use built-in rephrasing method for better performance
                    if hasattr(session_memory, 'rephrase_follow_up'):
                        processed_question = session_memory.rephrase_follow_up(normalized_question)
                except Exception as e:
                    processed_question = normalized_question
            
            # Use context-aware prompt if we have conversation context
            if conversation_context:
                try:
                    from modules.prompts import CONTEXT_AWARE_SYSTEM_PROMPT_TEMPLATE
                    optimized_prompt = optimize_prompt_tokens(
                        CONTEXT_AWARE_SYSTEM_PROMPT_TEMPLATE.format(
                            input=processed_question,
                            table_info=self.table_details,
                            conversation_context=conversation_context
                        ),
                        self.table_details
                    )
                except:
                    # Fallback to regular prompt
                    optimized_prompt = optimize_prompt_tokens(
                        SYSTEM_PROMPT_TEMPLATE.format(
                            input=processed_question,
                            table_info=self.table_details
                        ),
                        self.table_details
                    )
            else:
                # Generate optimized prompt with reduced token usage
                optimized_prompt = optimize_prompt_tokens(
                    SYSTEM_PROMPT_TEMPLATE.format(
                        input=processed_question,
                        table_info=self.table_details
                    ),
                    self.table_details
                )
        
        # LLM call without timeout to prevent hanging issues
        response = None
        try:
            response = self.llm.invoke(optimized_prompt)
        except Exception as e:
            # Return a simple error query
            return {
                "raw_query": "SELECT 'Error: Could not generate SQL query. Please try again.' as error",
                "query": "SELECT 'Error: Could not generate SQL query. Please try again.' as error"
            }
        
        # Check if response was successful
        if response is None:
            return {
                "raw_query": "SELECT 'Error: Could not generate SQL query. Please try again.' as error",
                "query": "SELECT 'Error: Could not generate SQL query. Please try again.' as error"
            }
        
        # Cache the result using both original and normalized questions
        query_cache.set_sql(question, response.content)
        if normalized_question != question:
            query_cache.set_sql(normalized_question, response.content)
        
        return {"raw_query": response.content, "query": clean_sql_query(response.content)}
    
    def execute_with_caching(self, sql_query: str) -> str:
        """Execute query with result caching"""
        cached_query_result = query_cache.get_result(sql_query)
        if cached_query_result:
            return cached_query_result
        else:
            try:
                # Database query without timeout
                query_result = self.execute_query.invoke(sql_query)
                query_cache.set_result(sql_query, query_result)
                return query_result
            except Exception as e:
                # Provide more specific error messages based on the type of error
                error_msg = str(e).lower()
                if "column" in error_msg and "does not exist" in error_msg:
                    return f"Error: Column not found in database schema - {str(e)}"
                elif "syntax error" in error_msg:
                    return f"Error: SQL syntax error - {str(e)}"
                elif "connection" in error_msg:
                    return f"Error: Database connection failed - {str(e)}"
                else:
                    return f"Error: Database query failed - {str(e)}"
    
    def process_question(self, user_input: str, chat_id: str = None) -> Dict[str, Any]:
        """Process user question with full pipeline and session context"""
        start_time = time.time()
        
        try:
            # Check if this is a greeting first
            if self._is_greeting(user_input):
                greeting_response = self._get_greeting_response(user_input)
                
                # Record this conversation turn in session memory
                session_memory = None
                if chat_id:
                    session_memory = session_manager.get_or_create_session(chat_id)
                    try:
                        turn = ConversationTurn(
                            timestamp=time.time(),
                            user_question=user_input,
                            sql_query="GREETING_RESPONSE",
                            sql_result="N/A",
                            ai_response=greeting_response,
                            tokens_used=0,
                            response_time=time.time() - start_time
                        )
                        session_memory.add_turn(turn)
                    except Exception as e:
                        pass
                
                return {
                    'success': True,
                    'response': greeting_response,
                    'sql_query': None,
                    'total_time': time.time() - start_time,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'chat_id': chat_id,
                    'suggestions': [
                        "Show me the top raiders with most successful raids",
                        "How many points did Bengaluru Bulls score this season?",
                        "Show me all raids by Pawan Sehrawat"
                    ]
                }
            
            # Get session-specific conversation memory
            session_memory = None
            if chat_id:
                session_memory = session_manager.get_or_create_session(chat_id)
                
                # Check if this is a follow-up question and rephrase if needed
                if session_memory and session_memory.is_follow_up_question(user_input):
                    user_input = session_memory.rephrase_follow_up(user_input)
            
            # Initialize token variables
            input_tokens = 0
            output_tokens = 0
            
            # Check cache first for SQL query
            cached_sql = query_cache.get_sql(user_input)
            if cached_sql:
                sql_result = {"query": cached_sql, "raw_query": cached_sql, "cached": True}
            else:
                # Calculate tokens for optimized prompt
                optimized_prompt_str = optimize_prompt_tokens(
                    SYSTEM_PROMPT_TEMPLATE.format(
                        input=user_input, 
                        table_info=self.table_details
                    ),
                    self.table_details
                )
                enc = tiktoken.get_encoding("cl100k_base")
                input_tokens = len(enc.encode(optimized_prompt_str))
                
                # Generate SQL query with session context
                sql_result = self.generate_sql_with_caching(user_input, session_memory)
                
                # Cache the SQL query
                query_cache.set_sql(user_input, sql_result["query"])
                
                print_sql({
                    "raw_query": sql_result["raw_query"], 
                    "query": sql_result["query"], 
                    "question": user_input
                })
            
            # Check cache for query result
            cached_result = query_cache.get_result(sql_result["query"])
            if cached_result:
                query_result = cached_result
            else:
                # Execute query
                query_result = self.execute_with_caching(sql_result["query"])
                
                # Normalize skills in textual results if techniques are involved
                try:
                    query_result = normalize_skills_in_result(sql_result["query"], str(query_result))
                except Exception:
                    pass

                # Cache the query result
                query_cache.set_result(sql_result["query"], query_result)
            
            # Format answer without timeout protection to prevent hanging
            suggestions = []
            
            if query_result.startswith("Error:"):
                # Provide a helpful, guided message instead of a generic unavailable notice
                response_lines = [
                    "I couldn't complete that request due to a query or schema issue.",
                    f"Details: {query_result}",
                    "",
                    "Try adjusting your question. Here are some alternatives:",
                    "• Show all successful raids by [Player Name]",
                    "• What are the top raiders by total points?",
                    "• Which teams have won the most matches?",
                    "• Show me raids from [specific match number]",
                    "• What are the most common attack techniques used?"
                ]
                response = "\n".join(response_lines)
                # Also surface suggestions to the client UI
                suggestions = [
                    "Show all successful raids by [Player Name]",
                    "What are the top raiders by total points?",
                    "Which teams have won the most matches?"
                ]
            elif not query_result.strip():
                # Empty result - this could mean no data found for the specific query
                # but data exists in the database, so we should provide a more helpful response
                response = "No data found matching your specific criteria. The database contains data, but your query returned no results. Please try rephrasing your question or using different search terms."
                
                # Add suggestions for similar player names
                enhancement = enhance_query_with_corrections(user_input, query_result)
                suggestions = enhancement.get("suggestions", [])
                if suggestions:
                    response += "\n\n" + "\n".join(suggestions)
            else:
                try:
                    response = self.rephrase_answer.invoke({
                        "question": user_input,
                        "query": sql_result["query"],
                        "result": query_result
                    })
                except Exception as e:
                    # Fallback to simple formatting
                    response = f"Here are the results for your query:\n\n{query_result}"
            
            # Calculate metrics
            end_time = time.time()
            total_time = end_time - start_time
            enc = tiktoken.get_encoding("cl100k_base")
            output_tokens = len(enc.encode(str(response)))
            total_tokens = input_tokens + output_tokens
            
            # Record this conversation turn in session memory
            if session_memory:
                try:
                    # Enhanced conversation memory with ConversationTurn
                    turn = ConversationTurn(
                        timestamp=time.time(),
                        user_question=user_input,
                        sql_query=sql_result["query"],
                        sql_result=query_result[:500] + "..." if len(query_result) > 500 else query_result,
                        ai_response=response,
                        tokens_used=total_tokens,
                        response_time=total_time
                    )
                    session_memory.add_turn(turn)
                except Exception as e:
                    pass
            
            # Record performance metrics
            if performance_monitor:
                try:
                    metric = PerformanceMetric(
                        timestamp=time.time(),
                        operation="chat_query",
                        duration=total_time,
                        tokens_used=total_tokens,
                        cache_hit=False,
                        error=None
                    )
                    performance_monitor.record_metric(metric)
                except Exception as e:
                    pass
            
            result = {
                'success': True,
                'response': response,
                'sql_query': sql_result["query"],
                'total_time': total_time,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'chat_id': chat_id,
                'suggestions': suggestions
            }
            return result
            
        except Exception as e:
            end_time = time.time()
            total_time = end_time - start_time
            
            # Record error in performance monitor
            if performance_monitor:
                try:
                    metric = PerformanceMetric(
                        timestamp=time.time(),
                        operation="chat_query",
                        duration=total_time,
                        tokens_used=0,
                        cache_hit=False,
                        error=str(e)
                    )
                    performance_monitor.record_metric(metric)
                except Exception as metric_error:
                    pass
            
            return {
                'success': False,
                'error': str(e),
                'total_time': total_time,
                'chat_id': chat_id,
                'suggestions': []
            }

# Global agent instance for API
enhanced_agent = None

# API Endpoints
def setup_api_routes(app: FastAPI):
    """Setup all API routes"""
    
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint"""
        return HealthResponse(
            status="healthy",
            agent_initialized=enhanced_agent is not None,
            uptime=time.time() - api_start_time
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(request: Request, authorization: Optional[str] = Header(None)):
        """Main chat endpoint for processing user questions"""
        try:
            # Get raw body first
            body = await request.body()
            
            # Try to parse as JSON
            try:
                data = json.loads(body)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail="Invalid JSON")
            
            # Create ChatRequest object
            chat_request = ChatRequest(**data)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid request format: {str(e)}")
        
        # Use chat_request instead of request for the rest of the function
        request = chat_request
        
        # Check user authentication and chat limits
        user_id = None
        if authorization:
            try:
                token = authorization.replace("Bearer ", "")
                user_id = user_db.verify_jwt_token(token)
                if user_id:
                    # Check if user can chat (free trial limit)
                    chat_limit_result = user_db.can_user_chat(user_id)
                    if not chat_limit_result["can_chat"]:
                        raise HTTPException(
                            status_code=403, 
                            detail=chat_limit_result.get("error", "Free trial limit reached. Please upgrade to premium for unlimited chats.")
                        )
            except Exception as e:
                # Continue without authentication for demo purposes
                pass
        
        if not enhanced_agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")
        
        try:
            # Generate chat_id if not provided
            chat_id = request.chat_id
            if not chat_id:
                chat_id = f"session_{int(time.time() * 1000)}"
                
            # Process the question using the enhanced agent with session context
            result = enhanced_agent.process_question(request.message, chat_id)
            
            if result['success']:
                # Get AI suggestions for follow-up questions and player name corrections
                suggestions = result.get('suggestions', [])  # Get suggestions from player name matcher
                try:
                    if hasattr(enhanced_agent, 'ai_question_suggester') and enhanced_agent.ai_question_suggester:
                        ai_suggestions = enhanced_agent.ai_question_suggester.get_follow_up_suggestions(
                            result['response'], 
                            enhanced_agent.conversation_memory if hasattr(enhanced_agent, 'conversation_memory') else None
                        )
                        suggestions.extend(ai_suggestions)
                    else:
                        ai_suggestions = ai_question_suggester.get_follow_up_suggestions(result['response'])
                        suggestions.extend(ai_suggestions)
                except Exception as e:
                    suggestions.extend([
                        "Show more detailed statistics",
                        "Compare with other teams",
                        "Analyze by time period"
                    ])
                
                # Record metrics
                total_tokens = result.get('input_tokens', 0) + result.get('output_tokens', 0)
                if hasattr(performance_monitor, 'record_metric'):
                    try:
                        # Create a PerformanceMetric object for the enhanced monitor
                        if hasattr(PerformanceMetric, '__init__'):
                            metric = PerformanceMetric(
                                timestamp=time.time(),
                                operation="chat_query",
                                duration=result['total_time'],
                                tokens_used=total_tokens,
                                cache_hit=False,
                                error=None
                            )
                            performance_monitor.record_metric(metric)
                        else:
                            # Use simple monitor method signature
                            try:
                                metric = PerformanceMetric(
                                    timestamp=time.time(),
                                    operation="chat_query",
                                    duration=result['total_time'],
                                    tokens_used=total_tokens,
                                    cache_hit=False,
                                    error=None
                                )
                                performance_monitor.record_metric(metric)
                            except Exception as metric_error:
                                # Fallback to simple monitor
                                if hasattr(performance_monitor, 'record_metric'):
                                    try:
                                        performance_monitor.record_metric(result['total_time'], total_tokens, True)
                                    except Exception as e:
                                        pass
                    except Exception as e:
                        # Use simple monitor fallback
                        if hasattr(performance_monitor, 'metrics'):
                            performance_monitor.metrics.append({
                                'duration': result['total_time'],
                                'tokens': total_tokens,
                                'success': True,
                                'timestamp': time.time()
                            })
                
                # Get session-specific memory for suggestions
                session_memory = session_manager.get_or_create_session(chat_id)
                
                # Persist chat turn and increment chat count for authenticated users
                if user_id:
                    try:
                        # Save chat to DB
                        user_db.save_chat_turn(
                            user_id=user_id,
                            chat_id=chat_id,
                            question=request.message,
                            response=result['response'],
                            sql_query=result.get('sql_query') or "",
                            tokens_used=(result.get('input_tokens', 0) + result.get('output_tokens', 0))
                        )
                    except Exception as e:
                        pass
                    try:
                        user_db.increment_chat_count(user_id)
                    except Exception as e:
                        pass
                
                response_data = {
                    'response': result['response'],
                    'sql_query': result.get('sql_query'),
                    'success': True,
                    'response_time': result['total_time'],
                    'suggestions': suggestions[:3],  # Limit to 3 suggestions
                    'chat_id': chat_id
                }
                return ChatResponse(**response_data)
            else:
                error_response = {
                    'response': f"I encountered an error: {result.get('error', 'Unknown error')}",
                    'success': False,
                    'response_time': result.get('total_time', 0),
                    'suggestions': [],
                    'chat_id': chat_id
                }
                return ChatResponse(**error_response)
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/chat/raw")
    async def chat_endpoint_raw(request: Request, authorization: Optional[str] = Header(None)):
        """Alternative chat endpoint that handles raw JSON body"""
        try:
            # Get raw body
            body = await request.body()
            
            # Parse JSON
            try:
                data = json.loads(body)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail="Invalid JSON")
            
            # Create ChatRequest object
            chat_request = ChatRequest(**data)
            
            # Call the main chat endpoint
            return await chat_endpoint(chat_request, authorization)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/chat/stream")
    async def chat_stream_endpoint(request: ChatRequest):
        """Streaming chat endpoint for real-time responses"""
        if not enhanced_agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")
        
        async def generate_stream():
            try:
                # Generate chat_id if not provided
                chat_id = request.chat_id
                if not chat_id:
                    chat_id = f"session_{int(time.time() * 1000)}"
                
                # Send initial status
                yield f"data: {json.dumps({'status': 'processing', 'chat_id': chat_id})}\n\n"
                
                # Process the question
                result = enhanced_agent.process_question(request.message, chat_id)
                
                if result['success']:
                    # Send SQL query first
                    yield f"data: {json.dumps({'sql_query': result.get('sql_query'), 'chat_id': chat_id})}\n\n"
                    
                    # Send response in chunks for streaming
                    response = result['response']
                    chunk_size = 100
                    for i in range(0, len(response), chunk_size):
                        chunk = response[i:i + chunk_size]
                        yield f"data: {json.dumps({'chunk': chunk, 'chat_id': chat_id})}\n\n"
                        await asyncio.sleep(0.01)  # Small delay for smooth streaming
                    
                    # Send final status
                    yield f"data: {json.dumps({'status': 'complete', 'response_time': result['total_time'], 'chat_id': chat_id})}\n\n"
                else:
                    yield f"data: {json.dumps({'error': result.get('error', 'Unknown error'), 'chat_id': chat_id})}\n\n"
                    
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    @app.get("/suggestions")
    async def get_suggestions(request: Request):
        """Get AI-generated question suggestions.

        Optional query parameter:
        - team: str -> if provided, generate team-focused suggestions
        """
        if not enhanced_agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")
        
        try:
            # Parse optional team from query string
            team = None
            try:
                team = request.query_params.get("team")
            except Exception:
                team = None
            
            # Get suggestions from the AI suggester
            suggestions = []
            if hasattr(enhanced_agent, 'ai_question_suggester') and enhanced_agent.ai_question_suggester:
                try:
                    suggestions = enhanced_agent.ai_question_suggester.get_suggestions(
                        6,
                        enhanced_agent.conversation_memory if hasattr(enhanced_agent, 'conversation_memory') else None,
                        query_cache,
                        team=team
                    )
                except TypeError:
                    # Backward compatibility for suggesters without team param
                    suggestions = enhanced_agent.ai_question_suggester.get_suggestions(
                        6,
                        enhanced_agent.conversation_memory if hasattr(enhanced_agent, 'conversation_memory') else None,
                        query_cache
                    )
            else:
                # Use global ai_question_suggester
                try:
                    suggestions = ai_question_suggester.get_suggestions(6, None, query_cache, team=team)
                except TypeError:
                    suggestions = ai_question_suggester.get_suggestions(6, None, query_cache)
            
            return {"suggestions": suggestions}
            
        except Exception as e:
            print(f"Error getting suggestions: {e}")
            # Return fallback suggestions
            return {
                "suggestions": [
                    "Show me the top raiders with most successful raids",
                    "How many points did Bengaluru Bulls score this season?",
                    "Show me all raids by Pawan Sehrawat",
                    "Compare raid success rates between TT and BB teams",
                    "List all do-or-die raids in the season",
                    "Show me super tackle opportunities by team"
                ]
            }

    @app.get("/stats")
    async def get_performance_stats():
        """Get current performance statistics"""
        if not enhanced_agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")
        
        try:
            # Get performance stats
            perf_stats = performance_monitor.get_stats()
            session_stats = {"total_questions": 0, "total_tokens": 0, "avg_tokens_per_question": 0}
            
            # Get cache statistics
            cache_stats = query_cache.get_cache_statistics()
            
            return {
                "performance": perf_stats,
                "session": session_stats,
                "cache": cache_stats,
                "uptime": time.time() - api_start_time,
                "optimization_settings": {
                    "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
                    "cache_preload_enabled": CACHE_PRELOAD_ENABLED,
                    "streaming_enabled": STREAMING_ENABLED
                }
            }
            
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {
                "performance": {"avg_time": 0, "success_rate": 1.0},
                "session": {"total_questions": 0},
                "cache": {"hit_rate": 0, "total_queries": 0},
                "uptime": time.time() - api_start_time,
                "optimization_settings": {
                    "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
                    "cache_preload_enabled": CACHE_PRELOAD_ENABLED,
                    "streaming_enabled": STREAMING_ENABLED
                }
            }

    @app.post("/summary", response_model=SummaryResponse)
    async def get_summary(request: SummaryRequest):
        """Generate a summary of the conversation for a specific chat session"""
        if not enhanced_agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")
        
        try:
            # Get or create session memory
            session_memory = session_manager.get_or_create_session(request.chat_id)
            if not session_memory:
                raise HTTPException(status_code=404, detail=f"Session with chat_id '{request.chat_id}' not found.")
            
            # Get conversation history
            conversation_history = session_memory.get_recent_context(10) # Get last 10 turns
            
            # Get session statistics
            session_stats = session_memory.get_session_stats()
            
            # Check if there's any conversation history
            if not conversation_history.strip():
                return SummaryResponse(
                    summary="No conversation history found for this session. Start a conversation to generate a summary.",
                    session_stats=session_stats,
                    conversation_highlights=[],
                    success=True
                )
            
            # Generate summary using LLM with better error handling
            try:
                summary_prompt = PromptTemplate.from_template("""
                    You are a helpful assistant that summarizes conversations.
                    Please summarize the following conversation history and session statistics.
                    Conversation History:
                    {conversation_history}
                    Session Statistics:
                    {session_stats}
                    Provide a concise summary of the key points discussed and the overall context.
                """)
                
                summary_llm = get_llm()
                summary_response = summary_llm.invoke(summary_prompt.format(
                    conversation_history=conversation_history,
                    session_stats=json.dumps(session_stats, indent=2)
                ))
                
                # Extract summary text
                summary_text = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
                
                # Generate conversation highlights
                highlights_prompt = PromptTemplate.from_template("""
                    Based on the conversation history below, provide 3-5 key highlights or insights:
                    {conversation_history}
                    
                    Return only the highlights, one per line, without numbering or bullet points.
                """)
                
                highlights_response = summary_llm.invoke(highlights_prompt.format(
                    conversation_history=conversation_history
                ))
                
                highlights_text = highlights_response.content if hasattr(highlights_response, 'content') else str(highlights_response)
                conversation_highlights = [line.strip() for line in highlights_text.split('\n') if line.strip()]
                
                return SummaryResponse(
                    summary=summary_text,
                    session_stats=session_stats,
                    conversation_highlights=conversation_highlights,
                    success=True
                )
                
            except Exception as e:
                print(f"Error generating summary: {e}")
                return SummaryResponse(
                    summary=f"Error generating summary: {str(e)}",
                    session_stats=session_stats,
                    conversation_highlights=[],
                    success=False
                )
                
        except Exception as e:
            print(f"Error in summary endpoint: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/feedback", response_model=FeedbackResponse)
    async def submit_feedback(request: FeedbackRequest):
        """Submit user feedback for a response"""
        try:
            # Create feedback entry
            feedback_entry = FeedbackEntry(
                timestamp=time.time(),
                user_question=request.user_question,
                ai_response=request.ai_response,
                sql_query=request.sql_query or "",
                feedback_type=request.feedback_type,
                feedback_text=request.feedback_text,
                response_time=request.response_time,
                tokens_used=request.tokens_used
            )
            
            # Collect feedback using the feedback system
            feedback_system.collect_feedback(feedback_entry)
            
            # If feedback is negative, try to improve the system
            if request.feedback_type in ['thumbs_down', 'correction']:
                # Could trigger model optimization or prompt improvement here
                pass
            
            return FeedbackResponse(
                success=True,
                message="Feedback submitted successfully"
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Create FastAPI app at module level for uvicorn
def create_app():
    """Create and configure FastAPI application"""
    # Startup and shutdown events
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        global enhanced_agent, session_manager
        enhanced_agent = EnhancedKabaddiAgent()
        enhanced_agent.initialize()
        session_manager = SessionManager()  # Ensure session manager is initialized
        
        yield

    # Create FastAPI app
    app = FastAPI(
        title="KabaddiGuru Analytics API",
        description="Enhanced Chat API for KabaddiGuru data analysis",
        version="1.0.0",
        lifespan=lifespan
    )

    # Add CORS middleware
    debug_mode = str(os.getenv("DEBUG", "False")).lower() == "true"
    configured_origin = os.getenv("FRONTEND_ORIGIN")
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://192.168.1.107:3000",
        "http://192.168.1.107:3001"
    ]
    if configured_origin:
        allowed_origins.append(configured_origin)

    if debug_mode:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_origin_regex=".*",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Include authentication routes
    app.include_router(auth_router)

    # Include analytics routes
    try:
        from Analytics_Tool.analytics_routes import router as analytics_router
        app.include_router(analytics_router)
    except ImportError as e:
        pass

    return app

# Create the app instance for uvicorn
app = create_app()

# Set up API routes
setup_api_routes(app)

# FastAPI Server Setup
# (App is now created at module level above)

def run_server():
    """Run the Enhanced Chat API server"""
    global app
    
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info"
    )

def main():
    """Main function - run Enhanced Chat API server"""
    # Start the Enhanced Chat API server
    run_server()

if __name__ == "__main__":
    main()