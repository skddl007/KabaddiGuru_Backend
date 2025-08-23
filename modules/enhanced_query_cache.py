"""
Enhanced Query caching module with advanced performance optimizations
"""
import hashlib
import json
import pickle
import gzip
from functools import lru_cache
from typing import Dict, Any, Optional, Tuple
import time
import threading
from collections import OrderedDict

class EnhancedQueryCache:
    def __init__(self, max_size: int = 500, compression: bool = True):
        self.sql_cache = OrderedDict()     # For SQL queries with LRU ordering
        self.result_cache = OrderedDict()  # For query results with LRU ordering
        self.max_size = max_size
        self.access_times = {}
        self.compression = compression
        self.hit_count = 0
        self.miss_count = 0
        self.cache_lock = threading.RLock()  # Thread-safe operations
        
        # Advanced caching features
        self.frequent_patterns = {}  # Track frequent query patterns
        self.query_analytics = {
            'avg_response_time': 0.0,
            'total_queries': 0,
            'cache_hit_rate': 0.0
        }
        
        # Performance optimizations
        self._cache_stats = {
            'last_cleanup': time.time(),
            'cleanup_interval': 300,  # 5 minutes
            'max_memory_mb': 100      # Max memory usage in MB
        }
    
    def _generate_key(self, query: str) -> str:
        """Generate cache key from query"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    def _compress_data(self, data: Any) -> bytes:
        """Compress data for storage efficiency"""
        if not self.compression:
            return pickle.dumps(data)
        return gzip.compress(pickle.dumps(data))
    
    def _decompress_data(self, compressed_data: bytes) -> Any:
        """Decompress stored data"""
        if not self.compression:
            return pickle.loads(compressed_data)
        return pickle.loads(gzip.decompress(compressed_data))
    
    def _track_query_pattern(self, question: str):
        """Track query patterns for intelligent caching"""
        # Extract pattern keywords
        keywords = [word.lower() for word in question.split() 
                   if len(word) > 2 and word.lower() not in ['the', 'and', 'for', 'are', 'can']]
        pattern = "_".join(sorted(set(keywords))[:3])  # Top 3 unique keywords
        
        self.frequent_patterns[pattern] = self.frequent_patterns.get(pattern, 0) + 1
    
    def _update_cache_analytics(self):
        """Update cache performance analytics"""
        total_requests = self.hit_count + self.miss_count
        if total_requests > 0:
            self.query_analytics['cache_hit_rate'] = self.hit_count / total_requests
            self.query_analytics['total_queries'] = total_requests
    
    def _evict_lru(self, cache_type: str = 'sql'):
        """Evict least recently used item using OrderedDict"""
        target_cache = self.sql_cache if cache_type == 'sql' else self.result_cache
        
        if target_cache:
            # OrderedDict FIFO - remove first (oldest) item
            oldest_key, _ = target_cache.popitem(last=False)
            
            # Clean up access times if not in any cache
            if oldest_key not in self.sql_cache and oldest_key not in self.result_cache:
                self.access_times.pop(oldest_key, None)
    
    def get_sql(self, question: str) -> Optional[str]:
        """Get cached SQL query for natural language question with analytics"""
        with self.cache_lock:
            # Periodic cleanup for memory management
            self._periodic_cleanup()
            
            key = self._generate_key(question)
            if key in self.sql_cache:
                # Move to end (most recently used)
                self.sql_cache.move_to_end(key)
                self.access_times[key] = time.time()
                self.hit_count += 1
                self._update_cache_analytics()
                
                # Decompress if needed
                cached_data = self.sql_cache[key]
                if isinstance(cached_data, bytes):
                    return self._decompress_data(cached_data)
                return cached_data
            
            self.miss_count += 1
            self._update_cache_analytics()
            return None
    
    def set_sql(self, question: str, sql_query: str) -> None:
        """Cache SQL query for natural language question with compression"""
        with self.cache_lock:
            if len(self.sql_cache) >= self.max_size:
                self._evict_lru('sql')
            
            key = self._generate_key(question)
            # Compress data if enabled
            data_to_store = self._compress_data(sql_query) if self.compression else sql_query
            self.sql_cache[key] = data_to_store
            self.access_times[key] = time.time()
            
            # Track query patterns
            self._track_query_pattern(question)
    
    def get_result(self, sql_query: str) -> Optional[str]:
        """Get cached result for SQL query with LRU management"""
        with self.cache_lock:
            key = self._generate_key(sql_query)
            if key in self.result_cache:
                # Move to end (most recently used)
                self.result_cache.move_to_end(key)
                self.access_times[key] = time.time()
                
                # Decompress if needed
                cached_data = self.result_cache[key]
                if isinstance(cached_data, bytes):
                    return self._decompress_data(cached_data)
                return cached_data
            return None
    
    def set_result(self, sql_query: str, result: str) -> None:
        """Cache SQL query result with compression"""
        with self.cache_lock:
            if len(self.result_cache) >= self.max_size:
                self._evict_lru('result')
            
            key = self._generate_key(sql_query)
            # Compress large results
            data_to_store = self._compress_data(result) if self.compression else result
            self.result_cache[key] = data_to_store
            self.access_times[key] = time.time()
    
    def intelligent_preload(self, common_questions: list):
        """Preload cache with common questions and patterns"""
        for question in common_questions:
            # This would need to be integrated with your SQL generation logic
            pass
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get detailed cache performance statistics"""
        with self.cache_lock:
            total_size = sum(len(str(v)) for v in self.sql_cache.values()) + \
                        sum(len(str(v)) for v in self.result_cache.values())
            
            return {
                'sql_cache_size': len(self.sql_cache),
                'result_cache_size': len(self.result_cache),
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'hit_rate': self.query_analytics['cache_hit_rate'],
                'total_memory_usage': total_size,
                'frequent_patterns': dict(sorted(self.frequent_patterns.items(), 
                                                key=lambda x: x[1], reverse=True)[:10]),
                'compression_enabled': self.compression
            }
    
    def clear_cache(self):
        """Clear all caches"""
        with self.cache_lock:
            self.sql_cache.clear()
            self.result_cache.clear()
            self.access_times.clear()
            self.hit_count = 0
            self.miss_count = 0
    
    def _periodic_cleanup(self):
        """Periodic cleanup for memory management"""
        current_time = time.time()
        if current_time - self._cache_stats['last_cleanup'] > self._cache_stats['cleanup_interval']:
            self.optimize_cache()
            self._cache_stats['last_cleanup'] = current_time
    
    def optimize_cache(self):
        """Optimize cache by removing old or infrequently accessed items"""
        with self.cache_lock:
            current_time = time.time()
            old_threshold = current_time - 1800  # 30 minutes (reduced from 1 hour)
            
            # Remove old entries
            old_keys = [key for key, access_time in self.access_times.items() 
                       if access_time < old_threshold]
            
            for key in old_keys:
                self.sql_cache.pop(key, None)
                self.result_cache.pop(key, None)
                self.access_times.pop(key, None)
            
            # Memory-based cleanup
            total_size = sum(len(str(v)) for v in self.sql_cache.values()) + \
                        sum(len(str(v)) for v in self.result_cache.values())
            
            if total_size > self._cache_stats['max_memory_mb'] * 1024 * 1024:  # Convert MB to bytes
                # Remove least recently used items
                while total_size > self._cache_stats['max_memory_mb'] * 1024 * 1024 * 0.8:  # Keep 80%
                    if self.sql_cache:
                        self.sql_cache.popitem(last=False)
                    if self.result_cache:
                        self.result_cache.popitem(last=False)
                    
                    total_size = sum(len(str(v)) for v in self.sql_cache.values()) + \
                                sum(len(str(v)) for v in self.result_cache.values())

# Legacy support - keep the old class name working
QueryCache = EnhancedQueryCache

# Enhanced cache instance with better defaults
query_cache = EnhancedQueryCache(max_size=300, compression=True)

@lru_cache(maxsize=20)
def get_table_schema_summary(full_schema: str) -> str:
    """
    Generate a condensed version of table schema to reduce token usage
    Enhanced with better summarization
    """
    lines = full_schema.split('\n')
    summary_lines = []
    
    essential_keywords = ['Table:', 'CREATE TABLE', 'Column:', 'PRIMARY KEY', 'FOREIGN KEY']
    
    for line in lines:
        line = line.strip()
        
        # Keep essential structural information
        if any(keyword in line for keyword in essential_keywords):
            summary_lines.append(line)
        # Keep column definitions but make them concise
        elif 'Column:' in line or line.startswith('Column'):
            # Simplify column info - keep only name and type
            simplified = ' '.join(line.split()[:3])  
            summary_lines.append(simplified)
        # Keep short important lines
        elif line and not line.startswith(('/*', '--', '#')) and len(line) < 80:
            summary_lines.append(line)
    
    # Limit to most important lines
    return '\n'.join(summary_lines[:40])

def optimize_prompt_tokens(prompt: str, table_info: str, max_tokens: int = 3000) -> str:
    """
    Enhanced prompt optimization with token limits
    """
    # Use condensed table schema
    condensed_schema = get_table_schema_summary(table_info)
    
    # Replace full table info with condensed version
    optimized_prompt = prompt.replace(table_info, condensed_schema)
    
    # Further optimization if still too long
    lines = optimized_prompt.split('\n')
    if len(optimized_prompt) > max_tokens * 3:  # Rough estimate
        # Keep only most important sections
        important_sections = []
        current_section = []
        
        for line in lines:
            if line.startswith(('##', '|||', '---')):  # Section markers
                if current_section:
                    important_sections.append('\n'.join(current_section))
                current_section = [line]
            else:
                current_section.append(line)
        
        if current_section:
            important_sections.append('\n'.join(current_section))
        
        # Keep most critical sections
        optimized_prompt = '\n\n'.join(important_sections[:8])
    
    return optimized_prompt
