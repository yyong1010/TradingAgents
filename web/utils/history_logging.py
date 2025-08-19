#!/usr/bin/env python3
"""
Enhanced Logging for Analysis History System

This module provides specialized logging functionality for debugging
storage and retrieval issues in the analysis history system.
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps

from tradingagents.utils.logging_manager import get_logger

# Create specialized loggers for different components
storage_logger = get_logger('history.storage')
retrieval_logger = get_logger('history.retrieval')
performance_logger = get_logger('history.performance')
user_action_logger = get_logger('history.user_actions')


class HistoryOperationLogger:
    """Specialized logger for history operations with detailed context"""
    
    def __init__(self, operation_type: str, context: Dict[str, Any] = None):
        self.operation_type = operation_type
        self.context = context or {}
        self.start_time = time.time()
        self.operation_id = f"{operation_type}_{int(self.start_time * 1000)}"
        
    def log_start(self, message: str, **kwargs):
        """Log operation start with context"""
        log_data = {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type,
            'phase': 'start',
            'timestamp': datetime.now().isoformat(),
            **self.context,
            **kwargs
        }
        
        storage_logger.info(f"[START] {message}", extra=log_data)
    
    def log_progress(self, message: str, progress: float = None, **kwargs):
        """Log operation progress"""
        elapsed = time.time() - self.start_time
        log_data = {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type,
            'phase': 'progress',
            'elapsed_seconds': elapsed,
            'timestamp': datetime.now().isoformat(),
            **self.context,
            **kwargs
        }
        
        if progress is not None:
            log_data['progress_percentage'] = progress * 100
        
        storage_logger.debug(f"[PROGRESS] {message}", extra=log_data)
    
    def log_success(self, message: str, result_summary: Dict[str, Any] = None, **kwargs):
        """Log successful operation completion"""
        duration = time.time() - self.start_time
        log_data = {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type,
            'phase': 'success',
            'duration_seconds': duration,
            'timestamp': datetime.now().isoformat(),
            **self.context,
            **kwargs
        }
        
        if result_summary:
            log_data['result'] = result_summary
        
        storage_logger.info(f"[SUCCESS] {message} ({duration:.3f}s)", extra=log_data)
        
        # Log performance metrics
        performance_logger.info(f"Operation completed: {self.operation_type}", extra={
            'operation_id': self.operation_id,
            'duration_seconds': duration,
            'success': True
        })
    
    def log_error(self, message: str, error: Exception, **kwargs):
        """Log operation error with full context"""
        duration = time.time() - self.start_time
        log_data = {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type,
            'phase': 'error',
            'duration_seconds': duration,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            **self.context,
            **kwargs
        }
        
        storage_logger.error(f"[ERROR] {message} ({duration:.3f}s): {error}", extra=log_data, exc_info=True)
        
        # Log performance metrics for failed operations
        performance_logger.warning(f"Operation failed: {self.operation_type}", extra={
            'operation_id': self.operation_id,
            'duration_seconds': duration,
            'success': False,
            'error_type': type(error).__name__
        })


def log_storage_operation(operation_type: str, context: Dict[str, Any] = None):
    """Decorator for logging storage operations with detailed context"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract relevant context from arguments
            operation_context = context or {}
            
            # Try to extract common parameters
            if args and hasattr(args[0], '__class__'):
                operation_context['class'] = args[0].__class__.__name__
            
            # Extract analysis_id if present
            for arg in args:
                if isinstance(arg, str) and 'analysis_' in arg:
                    operation_context['analysis_id'] = arg
                    break
            
            logger = HistoryOperationLogger(operation_type, operation_context)
            logger.log_start(f"Starting {operation_type}")
            
            try:
                result = func(*args, **kwargs)
                
                # Log result summary
                result_summary = {}
                if isinstance(result, (list, tuple)):
                    result_summary['result_count'] = len(result)
                elif isinstance(result, dict):
                    result_summary['result_keys'] = list(result.keys())
                elif isinstance(result, bool):
                    result_summary['success'] = result
                
                logger.log_success(f"Completed {operation_type}", result_summary)
                return result
                
            except Exception as e:
                logger.log_error(f"Failed {operation_type}", e)
                raise
        
        return wrapper
    return decorator


def log_user_action(action: str, context: Dict[str, Any] = None):
    """Log user actions for debugging and analytics"""
    log_data = {
        'action': action,
        'timestamp': datetime.now().isoformat(),
        'session_id': context.get('session_id') if context else None,
        **(context or {})
    }
    
    user_action_logger.info(f"User action: {action}", extra=log_data)


def log_query_performance(query_type: str, 
                         duration: float, 
                         result_count: int,
                         filters: Dict[str, Any] = None,
                         error: Exception = None):
    """Log query performance metrics for optimization"""
    log_data = {
        'query_type': query_type,
        'duration_seconds': duration,
        'result_count': result_count,
        'timestamp': datetime.now().isoformat(),
        'success': error is None
    }
    
    if filters:
        log_data['filters'] = {k: v for k, v in filters.items() if v is not None}
        log_data['filter_count'] = len([v for v in filters.values() if v is not None])
    
    if error:
        log_data['error_type'] = type(error).__name__
        log_data['error_message'] = str(error)
    
    if error:
        performance_logger.error(f"Query failed: {query_type} ({duration:.3f}s)", extra=log_data)
    elif duration > 5.0:
        performance_logger.warning(f"Slow query: {query_type} ({duration:.3f}s)", extra=log_data)
    else:
        performance_logger.info(f"Query completed: {query_type} ({duration:.3f}s)", extra=log_data)


def log_database_health_check(database_name: str, 
                             collection_name: str,
                             health_status: Dict[str, Any]):
    """Log database health check results"""
    log_data = {
        'database': database_name,
        'collection': collection_name,
        'timestamp': datetime.now().isoformat(),
        **health_status
    }
    
    if health_status.get('healthy', False):
        storage_logger.info(f"Database health check passed: {database_name}.{collection_name}", extra=log_data)
    else:
        storage_logger.error(f"Database health check failed: {database_name}.{collection_name}", extra=log_data)


def log_cache_operation(operation: str, 
                       cache_key: str, 
                       hit: bool = None, 
                       size: int = None,
                       ttl: int = None):
    """Log cache operations for debugging cache issues"""
    log_data = {
        'cache_operation': operation,
        'cache_key': cache_key,
        'timestamp': datetime.now().isoformat()
    }
    
    if hit is not None:
        log_data['cache_hit'] = hit
    if size is not None:
        log_data['data_size_bytes'] = size
    if ttl is not None:
        log_data['ttl_seconds'] = ttl
    
    retrieval_logger.debug(f"Cache {operation}: {cache_key}", extra=log_data)


def log_data_consistency_check(check_type: str, 
                              inconsistencies: List[Dict[str, Any]],
                              total_checked: int):
    """Log data consistency check results"""
    log_data = {
        'check_type': check_type,
        'total_checked': total_checked,
        'inconsistencies_found': len(inconsistencies),
        'timestamp': datetime.now().isoformat()
    }
    
    if inconsistencies:
        log_data['inconsistencies'] = inconsistencies[:10]  # Log first 10 inconsistencies
        storage_logger.warning(f"Data consistency issues found: {check_type}", extra=log_data)
    else:
        storage_logger.info(f"Data consistency check passed: {check_type}", extra=log_data)


def create_debug_session(session_name: str, context: Dict[str, Any] = None):
    """Create a debug session for tracking related operations"""
    session_id = f"{session_name}_{int(time.time() * 1000)}"
    
    class DebugSession:
        def __init__(self):
            self.session_id = session_id
            self.start_time = time.time()
            self.operations = []
            self.context = context or {}
        
        def log_operation(self, operation: str, details: Dict[str, Any] = None):
            """Log an operation within this debug session"""
            operation_data = {
                'session_id': self.session_id,
                'operation': operation,
                'timestamp': datetime.now().isoformat(),
                'elapsed_seconds': time.time() - self.start_time,
                **self.context,
                **(details or {})
            }
            
            self.operations.append(operation_data)
            storage_logger.debug(f"[{session_name}] {operation}", extra=operation_data)
        
        def log_error(self, operation: str, error: Exception, details: Dict[str, Any] = None):
            """Log an error within this debug session"""
            error_data = {
                'session_id': self.session_id,
                'operation': operation,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'timestamp': datetime.now().isoformat(),
                'elapsed_seconds': time.time() - self.start_time,
                **self.context,
                **(details or {})
            }
            
            self.operations.append(error_data)
            storage_logger.error(f"[{session_name}] {operation} failed: {error}", extra=error_data, exc_info=True)
        
        def get_summary(self) -> Dict[str, Any]:
            """Get a summary of all operations in this session"""
            duration = time.time() - self.start_time
            return {
                'session_id': self.session_id,
                'session_name': session_name,
                'duration_seconds': duration,
                'total_operations': len(self.operations),
                'operations': self.operations,
                'context': self.context
            }
        
        def close(self):
            """Close the debug session and log summary"""
            summary = self.get_summary()
            storage_logger.info(f"Debug session completed: {session_name}", extra=summary)
    
    return DebugSession()


def setup_history_logging_filters():
    """Setup logging filters for better log organization"""
    
    class HistoryLogFilter(logging.Filter):
        """Filter to add history-specific context to log records"""
        
        def filter(self, record):
            # Add default history context if not present
            if not hasattr(record, 'component'):
                record.component = 'history'
            
            # Add performance classification
            if hasattr(record, 'duration_seconds'):
                if record.duration_seconds > 10:
                    record.performance_class = 'slow'
                elif record.duration_seconds > 5:
                    record.performance_class = 'moderate'
                else:
                    record.performance_class = 'fast'
            
            return True
    
    # Apply filter to all history loggers
    history_filter = HistoryLogFilter()
    for logger_instance in [storage_logger, retrieval_logger, performance_logger, user_action_logger]:
        logger_instance.addFilter(history_filter)


def get_logging_stats() -> Dict[str, Any]:
    """Get logging statistics for monitoring"""
    return {
        'timestamp': datetime.now().isoformat(),
        'loggers': {
            'storage': {
                'name': storage_logger.name,
                'level': storage_logger.level,
                'handlers': len(storage_logger.handlers)
            },
            'retrieval': {
                'name': retrieval_logger.name,
                'level': retrieval_logger.level,
                'handlers': len(retrieval_logger.handlers)
            },
            'performance': {
                'name': performance_logger.name,
                'level': performance_logger.level,
                'handlers': len(performance_logger.handlers)
            },
            'user_actions': {
                'name': user_action_logger.name,
                'level': user_action_logger.level,
                'handlers': len(user_action_logger.handlers)
            }
        }
    }


# Initialize logging filters on module import
setup_history_logging_filters()