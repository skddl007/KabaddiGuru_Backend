"""
LLM Model Optimization Module
Optimizes model configuration and prompt engineering for better performance
"""
import os
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Load environment variables from config.env
load_dotenv('config.env')

@dataclass
class ModelConfig:
    model_name: str
    temperature: float
    max_tokens: Optional[int]
    top_p: Optional[float]
    
class ModelOptimizer:
    def __init__(self):
        self.performance_history = []
        # Get model name from environment variable
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
        
        self.optimal_configs = {
            'sql_generation': ModelConfig(
                model_name=model_name,
                temperature=0.1,  # Low temperature for consistent SQL
                max_tokens=1000,
                top_p=0.8
            ),
            'answer_formatting': ModelConfig(
                model_name=model_name, 
                temperature=0.3,  # Slightly higher for natural responses
                max_tokens=800,
                top_p=0.9
            ),
            'question_rephrasing': ModelConfig(
                model_name=model_name,
                temperature=0.2,
                max_tokens=200,
                top_p=0.7
            )
        }
    
    def get_optimized_llm(self, task_type: str = 'sql_generation', api_key: str = None) -> ChatGoogleGenerativeAI:
        """Get optimized LLM configuration for specific task"""
        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY")  # Get API key from environment variable
            if not api_key:
                raise ValueError("Google API key not set. Please set GOOGLE_API_KEY in config.env file.")
            
        config = self.optimal_configs.get(task_type, self.optimal_configs['sql_generation'])
        
        # Create optimized model instance
        model_params = {
            'model': config.model_name,
            'temperature': config.temperature,
            'google_api_key': api_key
        }
        
        # Add optional parameters if specified
        if config.max_tokens:
            model_params['max_output_tokens'] = config.max_tokens
        if config.top_p:
            model_params['top_p'] = config.top_p
            
        return ChatGoogleGenerativeAI(**model_params)
    
    def optimize_prompt_structure(self, base_prompt: str, task_type: str) -> str:
        """Optimize prompt structure for better token efficiency"""
        
        if task_type == 'sql_generation':
            # For SQL generation, emphasize structure and constraints
            optimized_prompt = f"""
TASK: Generate PostgreSQL query only. No explanations.

CONSTRAINTS:
- Use only provided table schema
- Apply case-insensitive matching with COLLATE NOCASE
- Return all results unless user specifies a limit
- Return only the SQL query

SCHEMA:
{base_prompt}

OUTPUT: SQL query only"""
            
        elif task_type == 'answer_formatting':
            # For answer formatting, emphasize clarity and structure
            optimized_prompt = f"""
TASK: Format SQL results into clear, readable response.

RULES:
- Use table format for multiple results
- Use natural language for single values
- Do not add information not in the data
- Be concise but complete

{base_prompt}

OUTPUT: Formatted response"""
            
        else:
            # Default optimization
            optimized_prompt = base_prompt
            
        return optimized_prompt
    
    def adaptive_token_management(self, prompt: str, max_tokens: int = 2000) -> str:
        """Adaptively manage token usage based on prompt length"""
        
        # Rough token estimation (4 chars = 1 token average)
        estimated_tokens = len(prompt) // 4
        
        if estimated_tokens <= max_tokens:
            return prompt
            
        # If too long, progressively reduce content
        lines = prompt.split('\n')
        
        # Priority preservation order
        essential_markers = ['TASK:', 'RULES:', 'SCHEMA:', 'OUTPUT:', 'Question:']
        priority_lines = []
        optional_lines = []
        
        for line in lines:
            if any(marker in line for marker in essential_markers):
                priority_lines.append(line)
            elif line.strip() and not line.startswith(('---', '||', '#')):
                optional_lines.append(line)
                
        # Start with essential content
        reduced_prompt = '\n'.join(priority_lines)
        
        # Add optional content until token limit
        for line in optional_lines:
            test_prompt = reduced_prompt + '\n' + line
            if len(test_prompt) // 4 < max_tokens:
                reduced_prompt = test_prompt
            else:
                break
                
        return reduced_prompt
    
    def performance_based_optimization(self, task_type: str, response_time: float, 
                                     tokens_used: int, success: bool):
        """Optimize model config based on performance feedback"""
        
        performance_data = {
            'task_type': task_type,
            'response_time': response_time,
            'tokens_used': tokens_used,
            'success': success,
            'timestamp': time.time()
        }
        self.performance_history.append(performance_data)
        
        # If performance is poor, adjust configuration
        if response_time > 5.0 or not success:
            current_config = self.optimal_configs[task_type]
            
            # Reduce max_tokens to speed up generation
            if current_config.max_tokens and current_config.max_tokens > 200:
                current_config.max_tokens = int(current_config.max_tokens * 0.8)
                
            # Adjust temperature for better consistency
            if not success and current_config.temperature > 0.1:
                current_config.temperature = max(0.0, current_config.temperature - 0.1)
                
        # If performance is excellent, we can potentially increase quality
        elif response_time < 2.0 and success and tokens_used < 1000:
            current_config = self.optimal_configs[task_type]
            
            # Slightly increase max_tokens for richer responses
            if current_config.max_tokens and current_config.max_tokens < 1500:
                current_config.max_tokens = int(current_config.max_tokens * 1.1)
    
    def get_performance_insights(self) -> Dict[str, Any]:
        """Get insights from performance history"""
        if not self.performance_history:
            return {"message": "No performance data available"}
            
        # Analyze performance by task type
        task_performance = {}
        
        for task_type in self.optimal_configs.keys():
            task_data = [p for p in self.performance_history if p['task_type'] == task_type]
            
            if task_data:
                avg_response_time = sum(p['response_time'] for p in task_data) / len(task_data)
                avg_tokens = sum(p['tokens_used'] for p in task_data) / len(task_data)
                success_rate = sum(1 for p in task_data if p['success']) / len(task_data)
                
                task_performance[task_type] = {
                    'avg_response_time': avg_response_time,
                    'avg_tokens_used': avg_tokens,
                    'success_rate': success_rate,
                    'total_requests': len(task_data)
                }
        
        return {
            'task_performance': task_performance,
            'total_history_entries': len(self.performance_history),
            'overall_success_rate': sum(1 for p in self.performance_history if p['success']) / len(self.performance_history)
        }
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get optimization recommendations based on performance"""
        recommendations = []
        insights = self.get_performance_insights()
        
        if 'task_performance' in insights:
            for task_type, performance in insights['task_performance'].items():
                
                # Response time recommendations
                if performance['avg_response_time'] > 4.0:
                    recommendations.append(
                        f"Consider reducing max_tokens for {task_type} to improve speed"
                    )
                
                # Token usage recommendations
                if performance['avg_tokens_used'] > 1500:
                    recommendations.append(
                        f"Optimize prompts for {task_type} to reduce token usage"
                    )
                
                # Success rate recommendations
                if performance['success_rate'] < 0.9:
                    recommendations.append(
                        f"Review prompt engineering for {task_type} to improve success rate"
                    )
        
        # General recommendations
        if insights.get('overall_success_rate', 1.0) < 0.85:
            recommendations.append("Consider implementing more robust error handling")
            
        return recommendations if recommendations else ["System is performing optimally"]

# Global model optimizer instance
model_optimizer = ModelOptimizer()
