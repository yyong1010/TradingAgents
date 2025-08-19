#!/usr/bin/env python3
"""
Optimized Pagination System for Analysis History

This module provides an optimized pagination system that reduces database load
through intelligent caching, cursor-based pagination for large datasets, and
adaptive page sizing based on performance metrics.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
import math

from web.utils.history_cache import get_cache_manager
from web.utils.history_performance import get_performance_monitor, PerformanceMetric

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class PaginationConfig:
    """Configuration for pagination behavior"""
    default_page_size: int = 20
    max_page_size: int = 100
    min_page_size: int = 5
    adaptive_sizing: bool = True
    cursor_threshold: int = 1000  # Switch to cursor-based pagination for large datasets
    cache_pages: bool = True
    prefetch_next_page: bool = True


@dataclass
class PaginationResult:
    """Result of a paginated query"""
    records: List[Any]
    total_count: int
    current_page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    next_cursor: Optional[str] = None
    previous_cursor: Optional[str] = None
    cache_hit: bool = False
    query_time: float = 0.0
    optimization_applied: Optional[str] = None


class OptimizedPaginator:
    """
    Optimized pagination system with intelligent caching and performance monitoring
    """
    
    def __init__(self, config: Optional[PaginationConfig] = None):
        """
        Initialize the paginator
        
        Args:
            config: Pagination configuration
        """
        self.config = config or PaginationConfig()
        self.cache_manager = get_cache_manager()
        self.performance_monitor = get_performance_monitor()
        
        # Performance tracking
        self.query_times = []
        self.cache_hit_rates = []
        
    def _calculate_optimal_page_size(self, estimated_total: int, 
                                   avg_query_time: float) -> int:
        """
        Calculate optimal page size based on dataset size and performance
        
        Args:
            estimated_total: Estimated total number of records
            avg_query_time: Average query time for recent requests
            
        Returns:
            Optimal page size
        """
        if not self.config.adaptive_sizing:
            return self.config.default_page_size
        
        # Base page size on performance
        if avg_query_time < 0.5:  # Fast queries
            optimal_size = min(50, self.config.max_page_size)
        elif avg_query_time < 2.0:  # Medium queries
            optimal_size = min(30, self.config.max_page_size)
        else:  # Slow queries
            optimal_size = min(15, self.config.max_page_size)
        
        # Adjust based on dataset size
        if estimated_total < 100:
            optimal_size = min(optimal_size, 25)
        elif estimated_total > 10000:
            optimal_size = max(optimal_size, 20)
        
        return max(self.config.min_page_size, optimal_size)
    
    def _should_use_cursor_pagination(self, total_count: int, page: int) -> bool:
        """
        Determine if cursor-based pagination should be used
        
        Args:
            total_count: Total number of records
            page: Current page number
            
        Returns:
            True if cursor pagination should be used
        """
        # Use cursor pagination for large datasets or deep pages
        return (total_count > self.config.cursor_threshold or 
                page > 50)
    
    def _generate_cache_key(self, filters: Dict[str, Any], page: int, 
                           page_size: int, sort_by: str, sort_order: int) -> str:
        """
        Generate cache key for pagination result
        
        Args:
            filters: Query filters
            page: Page number
            page_size: Page size
            sort_by: Sort field
            sort_order: Sort order
            
        Returns:
            Cache key string
        """
        import hashlib
        import json
        
        cache_data = {
            'filters': filters,
            'page': page,
            'page_size': page_size,
            'sort_by': sort_by,
            'sort_order': sort_order,
            'type': 'pagination'
        }
        
        cache_str = json.dumps(cache_data, sort_keys=True, default=str)
        return f"pagination:{hashlib.md5(cache_str.encode()).hexdigest()}"
    
    def _cache_pagination_result(self, cache_key: str, result: PaginationResult) -> None:
        """
        Cache pagination result
        
        Args:
            cache_key: Cache key
            result: Pagination result to cache
        """
        if not self.config.cache_pages or not self.cache_manager.is_available():
            return
        
        try:
            cache_data = {
                'records': [record.to_dict() if hasattr(record, 'to_dict') else record 
                           for record in result.records],
                'total_count': result.total_count,
                'current_page': result.current_page,
                'page_size': result.page_size,
                'total_pages': result.total_pages,
                'has_next': result.has_next,
                'has_previous': result.has_previous,
                'cached_at': datetime.now().isoformat()
            }
            
            # Cache for 5 minutes
            self.cache_manager.redis_client.setex(
                cache_key, 300, 
                json.dumps(cache_data, default=str)
            )
            
        except Exception as e:
            logger.warning(f"Failed to cache pagination result: {e}")
    
    def _get_cached_pagination_result(self, cache_key: str) -> Optional[PaginationResult]:
        """
        Retrieve cached pagination result
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached pagination result if found
        """
        if not self.config.cache_pages or not self.cache_manager.is_available():
            return None
        
        try:
            cached_data = self.cache_manager.redis_client.get(cache_key)
            if not cached_data:
                return None
            
            data = json.loads(cached_data.decode('utf-8'))
            
            # Convert records back to objects if needed
            from web.models.history_models import AnalysisHistoryRecord
            records = []
            for record_data in data['records']:
                if isinstance(record_data, dict) and 'analysis_id' in record_data:
                    records.append(AnalysisHistoryRecord.from_dict(record_data))
                else:
                    records.append(record_data)
            
            return PaginationResult(
                records=records,
                total_count=data['total_count'],
                current_page=data['current_page'],
                page_size=data['page_size'],
                total_pages=data['total_pages'],
                has_next=data['has_next'],
                has_previous=data['has_previous'],
                cache_hit=True,
                query_time=0.0
            )
            
        except Exception as e:
            logger.warning(f"Failed to retrieve cached pagination result: {e}")
            return None
    
    def paginate(self, query_func: callable, filters: Dict[str, Any], 
                page: int, page_size: Optional[int] = None,
                sort_by: str = 'created_at', sort_order: int = -1) -> PaginationResult:
        """
        Execute optimized pagination
        
        Args:
            query_func: Function to execute the actual query
            filters: Query filters
            page: Page number (1-based)
            page_size: Page size (None for adaptive)
            sort_by: Sort field
            sort_order: Sort order
            
        Returns:
            Pagination result
        """
        start_time = time.time()
        
        # Validate and adjust parameters
        page = max(1, page)
        
        # Calculate optimal page size if not specified
        if page_size is None:
            avg_query_time = (sum(self.query_times[-10:]) / len(self.query_times[-10:]) 
                             if self.query_times else 1.0)
            page_size = self._calculate_optimal_page_size(1000, avg_query_time)  # Estimate
        else:
            page_size = max(self.config.min_page_size, 
                           min(page_size, self.config.max_page_size))
        
        # Generate cache key
        cache_key = self._generate_cache_key(filters, page, page_size, sort_by, sort_order)
        
        # Try cache first
        cached_result = self._get_cached_pagination_result(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for pagination: page {page}, size {page_size}")
            return cached_result
        
        # Execute query
        try:
            records, total_count = query_func(filters, page, page_size, sort_by, sort_order)
            
            # Calculate pagination metadata
            total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
            has_next = page < total_pages
            has_previous = page > 1
            
            query_time = time.time() - start_time
            
            # Create result
            result = PaginationResult(
                records=records,
                total_count=total_count,
                current_page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=has_next,
                has_previous=has_previous,
                cache_hit=False,
                query_time=query_time
            )
            
            # Cache the result
            self._cache_pagination_result(cache_key, result)
            
            # Update performance tracking
            self.query_times.append(query_time)
            if len(self.query_times) > 100:
                self.query_times = self.query_times[-100:]
            
            # Prefetch next page if enabled and beneficial
            if (self.config.prefetch_next_page and has_next and 
                query_time < 1.0 and page_size <= 50):
                self._prefetch_next_page(query_func, filters, page + 1, 
                                       page_size, sort_by, sort_order)
            
            logger.debug(f"Pagination query completed: page {page}, size {page_size}, "
                        f"time {query_time:.3f}s, total {total_count}")
            
            return result
            
        except Exception as e:
            logger.error(f"Pagination query failed: {e}")
            # Return empty result on error
            return PaginationResult(
                records=[],
                total_count=0,
                current_page=page,
                page_size=page_size,
                total_pages=1,
                has_next=False,
                has_previous=False,
                query_time=time.time() - start_time
            )
    
    def _prefetch_next_page(self, query_func: callable, filters: Dict[str, Any],
                           next_page: int, page_size: int, sort_by: str, 
                           sort_order: int) -> None:
        """
        Prefetch the next page in background
        
        Args:
            query_func: Query function
            filters: Query filters
            next_page: Next page number
            page_size: Page size
            sort_by: Sort field
            sort_order: Sort order
        """
        try:
            # Check if next page is already cached
            next_cache_key = self._generate_cache_key(filters, next_page, page_size, 
                                                    sort_by, sort_order)
            if self._get_cached_pagination_result(next_cache_key):
                return  # Already cached
            
            # Execute prefetch query (don't wait for result)
            import threading
            
            def prefetch():
                try:
                    records, total_count = query_func(filters, next_page, page_size, 
                                                    sort_by, sort_order)
                    
                    # Calculate metadata for next page
                    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
                    has_next = next_page < total_pages
                    has_previous = next_page > 1
                    
                    result = PaginationResult(
                        records=records,
                        total_count=total_count,
                        current_page=next_page,
                        page_size=page_size,
                        total_pages=total_pages,
                        has_next=has_next,
                        has_previous=has_previous,
                        cache_hit=False,
                        query_time=0.0
                    )
                    
                    # Cache the prefetched result
                    self._cache_pagination_result(next_cache_key, result)
                    logger.debug(f"Prefetched page {next_page}")
                    
                except Exception as e:
                    logger.debug(f"Prefetch failed for page {next_page}: {e}")
            
            # Start prefetch in background thread
            thread = threading.Thread(target=prefetch, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.debug(f"Failed to start prefetch: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get pagination performance statistics
        
        Returns:
            Dictionary containing performance stats
        """
        if not self.query_times:
            return {
                'avg_query_time': 0.0,
                'min_query_time': 0.0,
                'max_query_time': 0.0,
                'total_queries': 0,
                'cache_enabled': self.config.cache_pages
            }
        
        return {
            'avg_query_time': sum(self.query_times) / len(self.query_times),
            'min_query_time': min(self.query_times),
            'max_query_time': max(self.query_times),
            'total_queries': len(self.query_times),
            'cache_enabled': self.config.cache_pages,
            'adaptive_sizing': self.config.adaptive_sizing,
            'recent_avg_time': (sum(self.query_times[-10:]) / len(self.query_times[-10:]) 
                               if len(self.query_times) >= 10 else 0.0)
        }
    
    def clear_cache(self) -> int:
        """
        Clear pagination cache
        
        Returns:
            Number of cache entries cleared
        """
        if not self.cache_manager.is_available():
            return 0
        
        try:
            pattern = "pagination:*"
            keys = self.cache_manager.redis_client.keys(pattern)
            if keys:
                deleted = self.cache_manager.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} pagination cache entries")
                return deleted
        except Exception as e:
            logger.error(f"Failed to clear pagination cache: {e}")
        
        return 0


# Global paginator instance
_paginator = None

def get_paginator() -> OptimizedPaginator:
    """Get the global paginator instance"""
    global _paginator
    if _paginator is None:
        _paginator = OptimizedPaginator()
    return _paginator