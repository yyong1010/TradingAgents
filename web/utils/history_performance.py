#!/usr/bin/env python3
"""
Analysis History Performance Monitoring

This module provides performance monitoring and optimization utilities for the
analysis history system, including query profiling, cache hit rate monitoring,
and performance metrics collection.
"""

import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""
    operation: str
    duration: float
    timestamp: datetime
    success: bool
    record_count: int = 0
    cache_hit: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """
    Performance monitoring system for history operations
    
    Tracks query performance, cache hit rates, and provides optimization
    recommendations based on usage patterns.
    """
    
    def __init__(self, max_metrics: int = 10000):
        """
        Initialize the performance monitor
        
        Args:
            max_metrics: Maximum number of metrics to keep in memory
        """
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0
        }
        self.slow_queries: List[PerformanceMetric] = []
        self.slow_query_threshold = 2.0  # seconds
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Performance thresholds
        self.thresholds = {
            'query_slow': 2.0,      # seconds
            'query_very_slow': 5.0,  # seconds
            'cache_hit_rate_low': 50.0,  # percentage
            'memory_usage_high': 80.0    # percentage
        }
    
    def record_metric(self, metric: PerformanceMetric) -> None:
        """
        Record a performance metric
        
        Args:
            metric: The performance metric to record
        """
        with self._lock:
            self.metrics.append(metric)
            
            # Update operation statistics
            self.operation_stats[metric.operation].append(metric.duration)
            
            # Track cache statistics
            if metric.cache_hit:
                self.cache_stats['hits'] += 1
            elif metric.operation.startswith('cache_'):
                self.cache_stats['misses'] += 1
            
            if metric.error:
                self.cache_stats['errors'] += 1
            
            # Track slow queries
            if metric.duration > self.slow_query_threshold:
                self.slow_queries.append(metric)
                # Keep only recent slow queries
                if len(self.slow_queries) > 100:
                    self.slow_queries = self.slow_queries[-100:]
    
    def get_operation_stats(self, operation: str, 
                           time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """
        Get statistics for a specific operation
        
        Args:
            operation: Operation name
            time_window: Time window to consider (None for all time)
            
        Returns:
            Dictionary containing operation statistics
        """
        with self._lock:
            # Filter metrics by time window if specified
            if time_window:
                cutoff_time = datetime.now() - time_window
                relevant_metrics = [
                    m for m in self.metrics 
                    if m.operation == operation and m.timestamp >= cutoff_time
                ]
            else:
                relevant_metrics = [m for m in self.metrics if m.operation == operation]
            
            if not relevant_metrics:
                return {
                    'count': 0,
                    'avg_duration': 0.0,
                    'min_duration': 0.0,
                    'max_duration': 0.0,
                    'median_duration': 0.0,
                    'success_rate': 0.0,
                    'cache_hit_rate': 0.0
                }
            
            durations = [m.duration for m in relevant_metrics]
            successes = [m for m in relevant_metrics if m.success]
            cache_hits = [m for m in relevant_metrics if m.cache_hit]
            
            return {
                'count': len(relevant_metrics),
                'avg_duration': statistics.mean(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'median_duration': statistics.median(durations),
                'p95_duration': statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else max(durations),
                'success_rate': len(successes) / len(relevant_metrics) * 100,
                'cache_hit_rate': len(cache_hits) / len(relevant_metrics) * 100 if relevant_metrics else 0,
                'total_records': sum(m.record_count for m in relevant_metrics)
            }
    
    def get_overall_stats(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """
        Get overall performance statistics
        
        Args:
            time_window: Time window to consider (None for all time)
            
        Returns:
            Dictionary containing overall statistics
        """
        with self._lock:
            # Filter metrics by time window if specified
            if time_window:
                cutoff_time = datetime.now() - time_window
                relevant_metrics = [m for m in self.metrics if m.timestamp >= cutoff_time]
            else:
                relevant_metrics = list(self.metrics)
            
            if not relevant_metrics:
                return {
                    'total_operations': 0,
                    'avg_duration': 0.0,
                    'success_rate': 0.0,
                    'cache_hit_rate': 0.0,
                    'slow_queries': 0,
                    'operations_by_type': {}
                }
            
            # Calculate overall statistics
            durations = [m.duration for m in relevant_metrics]
            successes = [m for m in relevant_metrics if m.success]
            cache_operations = [m for m in relevant_metrics if 'cache' in m.operation.lower()]
            cache_hits = [m for m in cache_operations if m.cache_hit]
            slow_queries = [m for m in relevant_metrics if m.duration > self.slow_query_threshold]
            
            # Operations by type
            operations_by_type = defaultdict(int)
            for metric in relevant_metrics:
                operations_by_type[metric.operation] += 1
            
            return {
                'total_operations': len(relevant_metrics),
                'avg_duration': statistics.mean(durations),
                'median_duration': statistics.median(durations),
                'p95_duration': statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else max(durations),
                'success_rate': len(successes) / len(relevant_metrics) * 100,
                'cache_hit_rate': len(cache_hits) / len(cache_operations) * 100 if cache_operations else 0,
                'slow_queries': len(slow_queries),
                'slow_query_rate': len(slow_queries) / len(relevant_metrics) * 100,
                'operations_by_type': dict(operations_by_type),
                'total_records_processed': sum(m.record_count for m in relevant_metrics)
            }
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the slowest queries
        
        Args:
            limit: Maximum number of slow queries to return
            
        Returns:
            List of slow query information
        """
        with self._lock:
            # Sort by duration descending
            sorted_slow = sorted(self.slow_queries, key=lambda x: x.duration, reverse=True)
            
            return [
                {
                    'operation': query.operation,
                    'duration': query.duration,
                    'timestamp': query.timestamp.isoformat(),
                    'record_count': query.record_count,
                    'error': query.error,
                    'metadata': query.metadata
                }
                for query in sorted_slow[:limit]
            ]
    
    def get_performance_recommendations(self) -> List[str]:
        """
        Get performance optimization recommendations
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Get recent statistics (last hour)
        recent_stats = self.get_overall_stats(timedelta(hours=1))
        
        # Check cache hit rate
        if recent_stats['cache_hit_rate'] < self.thresholds['cache_hit_rate_low']:
            recommendations.append(
                f"Cache hit rate is low ({recent_stats['cache_hit_rate']:.1f}%). "
                "Consider warming the cache or increasing cache TTL."
            )
        
        # Check for slow queries
        if recent_stats['slow_query_rate'] > 10:
            recommendations.append(
                f"High slow query rate ({recent_stats['slow_query_rate']:.1f}%). "
                "Consider optimizing database indexes or query patterns."
            )
        
        # Check average duration
        if recent_stats['avg_duration'] > self.thresholds['query_slow']:
            recommendations.append(
                f"Average query duration is high ({recent_stats['avg_duration']:.2f}s). "
                "Consider implementing pagination or result limiting."
            )
        
        # Check for specific operation issues
        for operation in ['get_user_history', 'get_analysis_by_id', 'get_history_stats']:
            op_stats = self.get_operation_stats(operation, timedelta(hours=1))
            if op_stats['count'] > 0 and op_stats['avg_duration'] > self.thresholds['query_slow']:
                recommendations.append(
                    f"Operation '{operation}' is slow (avg: {op_stats['avg_duration']:.2f}s). "
                    "Consider specific optimizations for this operation."
                )
        
        return recommendations
    
    def reset_stats(self) -> None:
        """Reset all performance statistics"""
        with self._lock:
            self.metrics.clear()
            self.operation_stats.clear()
            self.cache_stats = {'hits': 0, 'misses': 0, 'errors': 0}
            self.slow_queries.clear()
    
    def export_metrics(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """
        Export metrics for external analysis
        
        Args:
            time_window: Time window to export (None for all time)
            
        Returns:
            Dictionary containing exportable metrics
        """
        with self._lock:
            # Filter metrics by time window if specified
            if time_window:
                cutoff_time = datetime.now() - time_window
                relevant_metrics = [m for m in self.metrics if m.timestamp >= cutoff_time]
            else:
                relevant_metrics = list(self.metrics)
            
            return {
                'export_timestamp': datetime.now().isoformat(),
                'time_window': str(time_window) if time_window else 'all_time',
                'metrics_count': len(relevant_metrics),
                'overall_stats': self.get_overall_stats(time_window),
                'operation_stats': {
                    op: self.get_operation_stats(op, time_window)
                    for op in set(m.operation for m in relevant_metrics)
                },
                'slow_queries': self.get_slow_queries(),
                'recommendations': self.get_performance_recommendations(),
                'raw_metrics': [
                    {
                        'operation': m.operation,
                        'duration': m.duration,
                        'timestamp': m.timestamp.isoformat(),
                        'success': m.success,
                        'record_count': m.record_count,
                        'cache_hit': m.cache_hit,
                        'error': m.error,
                        'metadata': m.metadata
                    }
                    for m in relevant_metrics
                ]
            }


def performance_timer(operation: str, monitor: Optional[PerformanceMonitor] = None):
    """
    Decorator for timing operations and recording performance metrics
    
    Args:
        operation: Name of the operation being timed
        monitor: Performance monitor instance (uses global if None)
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error = None
            record_count = 0
            cache_hit = False
            
            try:
                result = func(*args, **kwargs)
                
                # Try to extract record count from result
                if isinstance(result, tuple) and len(result) == 2:
                    # Assume (records, total_count) format
                    if isinstance(result[0], list):
                        record_count = len(result[0])
                elif isinstance(result, list):
                    record_count = len(result)
                elif hasattr(result, '__len__'):
                    record_count = len(result)
                
                return result
                
            except Exception as e:
                success = False
                error = str(e)
                raise
            
            finally:
                duration = time.time() - start_time
                
                # Record the metric
                if monitor:
                    metric = PerformanceMetric(
                        operation=operation,
                        duration=duration,
                        timestamp=datetime.now(),
                        success=success,
                        record_count=record_count,
                        cache_hit=cache_hit,
                        error=error
                    )
                    monitor.record_metric(metric)
        
        return wrapper
    return decorator


# Global performance monitor instance
_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def log_performance_summary(time_window: timedelta = timedelta(hours=1)) -> None:
    """
    Log a performance summary for the specified time window
    
    Args:
        time_window: Time window to summarize
    """
    monitor = get_performance_monitor()
    stats = monitor.get_overall_stats(time_window)
    recommendations = monitor.get_performance_recommendations()
    
    logger.info(f"Performance Summary (last {time_window}):")
    logger.info(f"  Total operations: {stats['total_operations']}")
    logger.info(f"  Average duration: {stats['avg_duration']:.3f}s")
    logger.info(f"  Success rate: {stats['success_rate']:.1f}%")
    logger.info(f"  Cache hit rate: {stats['cache_hit_rate']:.1f}%")
    logger.info(f"  Slow queries: {stats['slow_queries']} ({stats['slow_query_rate']:.1f}%)")
    
    if recommendations:
        logger.info("Performance Recommendations:")
        for rec in recommendations:
            logger.info(f"  - {rec}")