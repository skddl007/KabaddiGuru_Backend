"""
Feedback System Module
Collects user feedback and learns from interactions to improve responses
"""
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import sqlite3
import os

@dataclass
class FeedbackEntry:
    timestamp: float
    user_question: str
    ai_response: str
    sql_query: str
    feedback_type: str  # 'thumbs_up', 'thumbs_down', 'correction', 'suggestion'
    feedback_text: Optional[str] = None
    response_time: float = 0.0
    tokens_used: int = 0

class FeedbackSystem:
    def __init__(self, db_path: str = "feedback.db"):
        self.db_path = db_path
        self.init_database()
        self.feedback_cache = []
        
    def init_database(self):
        """Initialize SQLite database for storing feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                user_question TEXT,
                ai_response TEXT,
                sql_query TEXT,
                feedback_type TEXT,
                feedback_text TEXT,
                response_time REAL,
                tokens_used INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS question_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT UNIQUE,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_response_time REAL DEFAULT 0.0,
                last_updated REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def collect_feedback(self, feedback_entry: FeedbackEntry):
        """Collect user feedback and store it"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO feedback (timestamp, user_question, ai_response, sql_query, 
                                feedback_type, feedback_text, response_time, tokens_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            feedback_entry.timestamp,
            feedback_entry.user_question,
            feedback_entry.ai_response,
            feedback_entry.sql_query,
            feedback_entry.feedback_type,
            feedback_entry.feedback_text,
            feedback_entry.response_time,
            feedback_entry.tokens_used
        ))
        
        conn.commit()
        conn.close()
        
        # Update question patterns
        self._update_question_patterns(feedback_entry)
        
        print(f"✅ Feedback collected: {feedback_entry.feedback_type}")
    
    def _update_question_patterns(self, feedback_entry: FeedbackEntry):
        """Update question patterns based on feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract pattern from question (simplified)
        pattern = self._extract_question_pattern(feedback_entry.user_question)
        
        # Check if pattern exists
        cursor.execute('SELECT * FROM question_patterns WHERE pattern = ?', (pattern,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing pattern
            if feedback_entry.feedback_type in ['thumbs_up', 'helpful']:
                cursor.execute('''
                    UPDATE question_patterns 
                    SET success_count = success_count + 1, 
                        avg_response_time = (avg_response_time + ?) / 2,
                        last_updated = ?
                    WHERE pattern = ?
                ''', (feedback_entry.response_time, time.time(), pattern))
            else:
                cursor.execute('''
                    UPDATE question_patterns 
                    SET failure_count = failure_count + 1,
                        last_updated = ?
                    WHERE pattern = ?
                ''', (time.time(), pattern))
        else:
            # Create new pattern
            success_count = 1 if feedback_entry.feedback_type in ['thumbs_up', 'helpful'] else 0
            failure_count = 1 if feedback_entry.feedback_type in ['thumbs_down', 'unhelpful'] else 0
            
            cursor.execute('''
                INSERT INTO question_patterns (pattern, success_count, failure_count, 
                                             avg_response_time, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (pattern, success_count, failure_count, 
                  feedback_entry.response_time, time.time()))
        
        conn.commit()
        conn.close()
    
    def _extract_question_pattern(self, question: str) -> str:
        """Extract pattern from user question for learning"""
        # Simplified pattern extraction
        question_lower = question.lower()
        
        # Common question patterns
        if any(word in question_lower for word in ['show', 'list', 'display']):
            pattern = 'list_query'
        elif any(word in question_lower for word in ['compare', 'vs', 'versus']):
            pattern = 'comparison_query'
        elif any(word in question_lower for word in ['count', 'how many', 'number']):
            pattern = 'count_query'
        elif any(word in question_lower for word in ['top', 'best', 'highest']):
            pattern = 'ranking_query'
        elif any(word in question_lower for word in ['average', 'mean', 'avg']):
            pattern = 'statistical_query'
        else:
            pattern = 'general_query'
            
        return pattern
    
    def get_feedback_analytics(self) -> Dict[str, Any]:
        """Get analytics from collected feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Overall feedback stats
        cursor.execute('SELECT feedback_type, COUNT(*) FROM feedback GROUP BY feedback_type')
        feedback_counts = dict(cursor.fetchall())
        
        # Average response times
        cursor.execute('SELECT AVG(response_time) FROM feedback WHERE response_time > 0')
        avg_response_time = cursor.fetchone()[0] or 0
        
        # Token usage stats
        cursor.execute('SELECT AVG(tokens_used), MAX(tokens_used), MIN(tokens_used) FROM feedback WHERE tokens_used > 0')
        token_stats = cursor.fetchone()
        
        # Question pattern success rates
        cursor.execute('''
            SELECT pattern, success_count, failure_count, avg_response_time 
            FROM question_patterns 
            ORDER BY (success_count * 1.0 / (success_count + failure_count + 1)) DESC
        ''')
        pattern_stats = cursor.fetchall()
        
        conn.close()
        
        return {
            'feedback_counts': feedback_counts,
            'avg_response_time': avg_response_time,
            'token_stats': {
                'avg': token_stats[0] or 0,
                'max': token_stats[1] or 0,
                'min': token_stats[2] or 0
            },
            'pattern_performance': [
                {
                    'pattern': row[0],
                    'success_rate': row[1] / (row[1] + row[2] + 1),
                    'avg_response_time': row[3]
                }
                for row in pattern_stats
            ]
        }
    
    def get_improvement_suggestions(self) -> List[str]:
        """Get suggestions for system improvement based on feedback"""
        analytics = self.get_feedback_analytics()
        suggestions = []
        
        # Check response time issues
        if analytics['avg_response_time'] > 5.0:
            suggestions.append("Consider implementing better caching to reduce response times")
            
        # Check token usage
        if analytics['token_stats']['avg'] > 2000:
            suggestions.append("Optimize prompts to reduce token usage")
            
        # Check feedback patterns
        feedback_counts = analytics['feedback_counts']
        total_feedback = sum(feedback_counts.values())
        
        if total_feedback > 0:
            negative_ratio = (feedback_counts.get('thumbs_down', 0) + 
                            feedback_counts.get('unhelpful', 0)) / total_feedback
            
            if negative_ratio > 0.3:
                suggestions.append("High negative feedback - review response quality")
        
        # Check pattern performance
        poor_patterns = [p for p in analytics['pattern_performance'] 
                        if p['success_rate'] < 0.6]
        
        if poor_patterns:
            suggestions.append(f"Improve handling of {len(poor_patterns)} question patterns")
            
        return suggestions
    
    def export_feedback_data(self) -> str:
        """Export all feedback data as JSON"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM feedback ORDER BY timestamp DESC')
        feedback_data = cursor.fetchall()
        
        cursor.execute('SELECT * FROM question_patterns ORDER BY last_updated DESC')
        pattern_data = cursor.fetchall()
        
        conn.close()
        
        export_data = {
            'feedback_entries': feedback_data,
            'question_patterns': pattern_data,
            'export_timestamp': time.time()
        }
        
        return json.dumps(export_data, indent=2)

# Global feedback system instance
feedback_system = FeedbackSystem()
