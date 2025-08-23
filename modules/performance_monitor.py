"""
Performance Monitoring Module
Tracks system performance, response times, and provides analytics
"""
import time
import json
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import statistics

@dataclass
class PerformanceMetric:
    timestamp: float
    operation: str
    duration: float
    tokens_used: int
    cache_hit: bool
    error: Optional[str] = None
    metadata: Optional[Dict] = None

class PerformanceMonitor:
    def __init__(self, max_metrics: int = 1000):
        self.metrics = deque(maxlen=max_metrics)
        self.operation_stats = defaultdict(list)
        self.lock = threading.RLock()
        self.start_time = time.time()
        
    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric"""
        with self.lock:
            self.metrics.append(metric)
            self.operation_stats[metric.operation].append(metric.duration)
    
    def track_operation(self, operation_name: str):
        """Decorator to track operation performance"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                error = None
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error = str(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    metric = PerformanceMetric(
                        timestamp=time.time(),
                        operation=operation_name,
                        duration=duration,
                        tokens_used=0,  # To be updated if available
                        cache_hit=False,  # To be updated if available
                        error=error
                    )
                    self.record_metric(metric)
            
            return wrapper
        return decorator
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        with self.lock:
            if not self.metrics:
                return {"status": "No metrics available"}
            
            # Overall statistics
            total_operations = len(self.metrics)
            successful_operations = sum(1 for m in self.metrics if m.error is None)
            error_rate = (total_operations - successful_operations) / total_operations
            
            # Response time statistics
            response_times = [m.duration for m in self.metrics if m.error is None]
            
            if response_times:
                avg_response_time = statistics.mean(response_times)
                median_response_time = statistics.median(response_times)
                p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else max(response_times)
            else:
                avg_response_time = median_response_time = p95_response_time = 0
            
            # Token usage statistics
            token_usage = [m.tokens_used for m in self.metrics if m.tokens_used > 0]
            avg_tokens = statistics.mean(token_usage) if token_usage else 0
            total_tokens = sum(token_usage)
            
            # Cache performance
            cache_hits = sum(1 for m in self.metrics if m.cache_hit)
            cache_hit_rate = cache_hits / total_operations if total_operations > 0 else 0
            
            # Operation breakdown
            operation_breakdown = {}
            for operation, durations in self.operation_stats.items():
                if durations:
                    operation_breakdown[operation] = {
                        'count': len(durations),
                        'avg_duration': statistics.mean(durations),
                        'min_duration': min(durations),
                        'max_duration': max(durations)
                    }
            
            return {
                'summary': {
                    'total_operations': total_operations,
                    'successful_operations': successful_operations,
                    'error_rate': error_rate,
                    'uptime_hours': (time.time() - self.start_time) / 3600
                },
                'response_times': {
                    'average_seconds': avg_response_time,
                    'median_seconds': median_response_time,
                    'p95_seconds': p95_response_time
                },
                'token_usage': {
                    'average_per_query': avg_tokens,
                    'total_consumed': total_tokens
                },
                'cache_performance': {
                    'hit_rate': cache_hit_rate,
                    'hits': cache_hits,
                    'misses': total_operations - cache_hits
                },
                'operation_breakdown': operation_breakdown
            }
    
    def get_slow_operations(self, threshold_seconds: float = 3.0) -> List[Dict]:
        """Get operations that took longer than threshold"""
        with self.lock:
            slow_ops = []
            for metric in self.metrics:
                if metric.duration > threshold_seconds:
                    slow_ops.append({
                        'timestamp': metric.timestamp,
                        'operation': metric.operation,
                        'duration': metric.duration,
                        'error': metric.error,
                        'metadata': metric.metadata
                    })
            
            return sorted(slow_ops, key=lambda x: x['duration'], reverse=True)
    
    def get_error_analysis(self) -> Dict[str, Any]:
        """Analyze errors and failure patterns"""
        with self.lock:
            errors = [m for m in self.metrics if m.error]
            
            if not errors:
                return {"error_count": 0, "error_types": {}}
            
            # Group errors by type
            error_types = defaultdict(list)
            for error_metric in errors:
                error_type = error_metric.error.split(':')[0] if error_metric.error else 'Unknown'
                error_types[error_type].append(error_metric)
            
            error_summary = {}
            for error_type, error_list in error_types.items():
                error_summary[error_type] = {
                    'count': len(error_list),
                    'recent_example': error_list[-1].error,
                    'operations_affected': list(set(e.operation for e in error_list))
                }
            
            return {
                'error_count': len(errors),
                'error_rate': len(errors) / len(self.metrics),
                'error_types': error_summary
            }
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get real-time performance statistics"""
        with self.lock:
            recent_metrics = [m for m in self.metrics if time.time() - m.timestamp < 300]  # Last 5 minutes
            
            if not recent_metrics:
                return {"status": "No recent activity"}
            
            recent_response_times = [m.duration for m in recent_metrics if m.error is None]
            recent_errors = [m for m in recent_metrics if m.error]
            
            return {
                'recent_activity': {
                    'operations_last_5min': len(recent_metrics),
                    'avg_response_time': statistics.mean(recent_response_times) if recent_response_times else 0,
                    'error_count': len(recent_errors),
                    'active_operations': list(set(m.operation for m in recent_metrics))
                },
                'current_status': 'healthy' if len(recent_errors) / len(recent_metrics) < 0.1 else 'degraded'
            }
    
    def export_metrics(self, format_type: str = 'json') -> str:
        """Export metrics data"""
        with self.lock:
            if format_type == 'json':
                metrics_data = [asdict(m) for m in self.metrics]
                return json.dumps(metrics_data, indent=2)
            else:
                # CSV format
                lines = ['timestamp,operation,duration,tokens_used,cache_hit,error']
                for m in self.metrics:
                    lines.append(f"{m.timestamp},{m.operation},{m.duration},{m.tokens_used},{m.cache_hit},{m.error or ''}")
                return '\n'.join(lines)
    
    def clear_metrics(self):
        """Clear all stored metrics"""
        with self.lock:
            self.metrics.clear()
            self.operation_stats.clear()
    
    def set_alert_thresholds(self, thresholds: Dict[str, float]):
        """Set performance alert thresholds"""
        self.alert_thresholds = thresholds
    
    def check_alerts(self) -> List[str]:
        """Check for performance alerts"""
        alerts = []
        summary = self.get_performance_summary()
        
        # Check response time alerts
        avg_response = summary['response_times']['average_seconds']
        if hasattr(self, 'alert_thresholds'):
            if avg_response > self.alert_thresholds.get('max_response_time', 5.0):
                alerts.append(f"High average response time: {avg_response:.2f}s")
            
            # Check error rate alerts
            error_rate = summary['summary']['error_rate']
            if error_rate > self.alert_thresholds.get('max_error_rate', 0.1):
                alerts.append(f"High error rate: {error_rate:.2%}")
            
            # Check cache hit rate alerts
            cache_hit_rate = summary['cache_performance']['hit_rate']
            if cache_hit_rate < self.alert_thresholds.get('min_cache_hit_rate', 0.5):
                alerts.append(f"Low cache hit rate: {cache_hit_rate:.2%}")
        
        return alerts

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Set default alert thresholds
performance_monitor.set_alert_thresholds({
    'max_response_time': 5.0,
    'max_error_rate': 0.15,
    'min_cache_hit_rate': 0.4
})
