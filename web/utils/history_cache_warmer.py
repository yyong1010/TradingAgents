#!/usr/bin/env python3
"""
Analysis History Cache Warming Utility

This module provides utilities for warming the cache with frequently accessed
analysis records and query results to improve performance.
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from web.utils.history_storage import get_history_storage
from web.utils.history_cache import get_cache_manager
from web.utils.history_performance import get_performance_monitor

# Setup logging
logger = logging.getLogger(__name__)


class CacheWarmer:
    """
    Cache warming utility for analysis history
    
    Provides intelligent cache warming based on usage patterns and
    performance metrics to optimize system responsiveness.
    """
    
    def __init__(self):
        """Initialize the cache warmer"""
        self.storage = get_history_storage()
        self.cache_manager = get_cache_manager()
        self.performance_monitor = get_performance_monitor()
        
        # Warming configuration
        self.config = {
            'recent_records_limit': 100,
            'popular_queries_limit': 20,
            'max_concurrent_threads': 5,
            'warm_on_startup': True,
            'periodic_warming_interval': 3600,  # 1 hour
            'warm_popular_stocks': True,
            'warm_recent_dates': True
        }
        
        # Track warming statistics
        self.warming_stats = {
            'last_warming': None,
            'records_warmed': 0,
            'queries_warmed': 0,
            'warming_duration': 0.0,
            'errors': 0
        }
        
        # Popular query patterns (can be learned from usage)
        self.popular_patterns = [
            {'filters': {}, 'page': 1, 'page_size': 20},  # Default view
            {'filters': {'status': 'completed'}, 'page': 1, 'page_size': 20},  # Completed only
            {'filters': {'market_type': 'A股'}, 'page': 1, 'page_size': 20},  # A-share only
            {'filters': {'market_type': '美股'}, 'page': 1, 'page_size': 20},  # US stocks only
        ]
    
    def warm_recent_records(self, limit: int = None) -> int:
        """
        Warm cache with recent analysis records
        
        Args:
            limit: Number of recent records to warm (None for config default)
            
        Returns:
            Number of records warmed
        """
        if not self.cache_manager.is_available() or not self.storage.is_available():
            logger.warning("Cache or storage not available for warming")
            return 0
        
        limit = limit or self.config['recent_records_limit']
        
        try:
            logger.info(f"Warming cache with {limit} recent records...")
            start_time = time.time()
            
            # Get recent records from database
            recent_records, _ = self.storage.get_user_history(
                filters={},
                page=1,
                page_size=limit,
                sort_by='created_at',
                sort_order=-1
            )
            
            # Warm cache with these records
            warmed_count = 0
            for record in recent_records:
                if self.cache_manager.cache_record(record):
                    warmed_count += 1
            
            duration = time.time() - start_time
            logger.info(f"Warmed {warmed_count} recent records in {duration:.2f}s")
            
            return warmed_count
            
        except Exception as e:
            logger.error(f"Failed to warm recent records: {e}")
            self.warming_stats['errors'] += 1
            return 0
    
    def warm_popular_queries(self) -> int:
        """
        Warm cache with popular query patterns
        
        Returns:
            Number of queries warmed
        """
        if not self.cache_manager.is_available() or not self.storage.is_available():
            return 0
        
        try:
            logger.info("Warming cache with popular query patterns...")
            start_time = time.time()
            
            warmed_count = 0
            
            with ThreadPoolExecutor(max_workers=self.config['max_concurrent_threads']) as executor:
                # Submit warming tasks
                futures = []
                for pattern in self.popular_patterns:
                    future = executor.submit(self._warm_single_query, pattern)
                    futures.append(future)
                
                # Wait for completion
                for future in as_completed(futures):
                    try:
                        if future.result():
                            warmed_count += 1
                    except Exception as e:
                        logger.warning(f"Query warming task failed: {e}")
                        self.warming_stats['errors'] += 1
            
            duration = time.time() - start_time
            logger.info(f"Warmed {warmed_count} popular queries in {duration:.2f}s")
            
            return warmed_count
            
        except Exception as e:
            logger.error(f"Failed to warm popular queries: {e}")
            self.warming_stats['errors'] += 1
            return 0
    
    def _warm_single_query(self, pattern: Dict[str, Any]) -> bool:
        """
        Warm cache with a single query pattern
        
        Args:
            pattern: Query pattern to warm
            
        Returns:
            True if warmed successfully
        """
        try:
            # Execute the query to populate cache
            self.storage.get_user_history(
                filters=pattern.get('filters', {}),
                page=pattern.get('page', 1),
                page_size=pattern.get('page_size', 20),
                sort_by=pattern.get('sort_by', 'created_at'),
                sort_order=pattern.get('sort_order', -1)
            )
            return True
            
        except Exception as e:
            logger.debug(f"Failed to warm query pattern {pattern}: {e}")
            return False
    
    def warm_popular_stocks(self, limit: int = 20) -> int:
        """
        Warm cache with records for popular stocks
        
        Args:
            limit: Number of popular stocks to warm
            
        Returns:
            Number of stock patterns warmed
        """
        if not self.cache_manager.is_available() or not self.storage.is_available():
            return 0
        
        try:
            logger.info(f"Warming cache with popular stocks (limit: {limit})...")
            start_time = time.time()
            
            # Get popular stocks from recent analysis
            popular_stocks = self._get_popular_stocks(limit)
            
            warmed_count = 0
            for stock_symbol in popular_stocks:
                try:
                    # Warm cache with recent analyses for this stock
                    self.storage.get_user_history(
                        filters={'stock_symbol': stock_symbol},
                        page=1,
                        page_size=10,
                        sort_by='created_at',
                        sort_order=-1
                    )
                    warmed_count += 1
                    
                except Exception as e:
                    logger.debug(f"Failed to warm stock {stock_symbol}: {e}")
                    continue
            
            duration = time.time() - start_time
            logger.info(f"Warmed {warmed_count} popular stocks in {duration:.2f}s")
            
            return warmed_count
            
        except Exception as e:
            logger.error(f"Failed to warm popular stocks: {e}")
            self.warming_stats['errors'] += 1
            return 0
    
    def _get_popular_stocks(self, limit: int) -> List[str]:
        """
        Get list of popular stocks based on recent analysis frequency
        
        Args:
            limit: Maximum number of stocks to return
            
        Returns:
            List of popular stock symbols
        """
        try:
            # Get recent analyses (last 7 days)
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_analyses, _ = self.storage.get_user_history(
                filters={'created_at': {'$gte': seven_days_ago}},
                page=1,
                page_size=500,  # Get more records to analyze
                sort_by='created_at',
                sort_order=-1
            )
            
            # Count frequency of each stock
            stock_counts = {}
            for record in recent_analyses:
                symbol = record.stock_symbol
                stock_counts[symbol] = stock_counts.get(symbol, 0) + 1
            
            # Sort by frequency and return top stocks
            popular_stocks = sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)
            return [stock[0] for stock in popular_stocks[:limit]]
            
        except Exception as e:
            logger.error(f"Failed to get popular stocks: {e}")
            return []
    
    def warm_statistics_cache(self) -> bool:
        """
        Warm cache with statistics data
        
        Returns:
            True if warmed successfully
        """
        if not self.cache_manager.is_available() or not self.storage.is_available():
            return False
        
        try:
            logger.info("Warming statistics cache...")
            
            # Get and cache statistics
            stats = self.storage.get_history_stats()
            
            if stats:
                logger.info("Statistics cache warmed successfully")
                return True
            
        except Exception as e:
            logger.error(f"Failed to warm statistics cache: {e}")
            self.warming_stats['errors'] += 1
        
        return False
    
    def full_cache_warming(self) -> Dict[str, Any]:
        """
        Perform comprehensive cache warming
        
        Returns:
            Dictionary containing warming results
        """
        logger.info("Starting full cache warming...")
        start_time = time.time()
        
        results = {
            'started_at': datetime.now().isoformat(),
            'records_warmed': 0,
            'queries_warmed': 0,
            'stocks_warmed': 0,
            'statistics_warmed': False,
            'total_duration': 0.0,
            'errors': 0
        }
        
        try:
            # Warm recent records
            results['records_warmed'] = self.warm_recent_records()
            
            # Warm popular queries
            results['queries_warmed'] = self.warm_popular_queries()
            
            # Warm popular stocks
            if self.config['warm_popular_stocks']:
                results['stocks_warmed'] = self.warm_popular_stocks()
            
            # Warm statistics
            results['statistics_warmed'] = self.warm_statistics_cache()
            
            # Update warming stats
            results['total_duration'] = time.time() - start_time
            results['errors'] = self.warming_stats['errors']
            
            self.warming_stats.update({
                'last_warming': datetime.now(),
                'records_warmed': results['records_warmed'],
                'queries_warmed': results['queries_warmed'],
                'warming_duration': results['total_duration']
            })
            
            logger.info(f"Full cache warming completed in {results['total_duration']:.2f}s")
            logger.info(f"Results: {results['records_warmed']} records, "
                       f"{results['queries_warmed']} queries, "
                       f"{results['stocks_warmed']} stocks")
            
        except Exception as e:
            logger.error(f"Full cache warming failed: {e}")
            results['errors'] += 1
            results['total_duration'] = time.time() - start_time
        
        return results
    
    def start_periodic_warming(self) -> None:
        """
        Start periodic cache warming in background
        """
        if not self.config.get('periodic_warming_interval'):
            logger.info("Periodic warming disabled")
            return
        
        def warming_loop():
            while True:
                try:
                    time.sleep(self.config['periodic_warming_interval'])
                    logger.info("Starting periodic cache warming...")
                    self.full_cache_warming()
                    
                except Exception as e:
                    logger.error(f"Periodic warming failed: {e}")
                    # Continue the loop even if warming fails
        
        # Start warming thread
        warming_thread = threading.Thread(target=warming_loop, daemon=True)
        warming_thread.start()
        
        logger.info(f"Periodic cache warming started (interval: {self.config['periodic_warming_interval']}s)")
    
    def get_warming_stats(self) -> Dict[str, Any]:
        """
        Get cache warming statistics
        
        Returns:
            Dictionary containing warming statistics
        """
        return {
            **self.warming_stats,
            'config': self.config,
            'cache_available': self.cache_manager.is_available(),
            'storage_available': self.storage.is_available()
        }


# Global cache warmer instance
_cache_warmer = None

def get_cache_warmer() -> CacheWarmer:
    """Get the global cache warmer instance"""
    global _cache_warmer
    if _cache_warmer is None:
        _cache_warmer = CacheWarmer()
    return _cache_warmer


def warm_cache_on_startup() -> Dict[str, Any]:
    """
    Warm cache on application startup
    
    Returns:
        Warming results
    """
    warmer = get_cache_warmer()
    if warmer.config['warm_on_startup']:
        return warmer.full_cache_warming()
    else:
        logger.info("Startup cache warming disabled")
        return {'disabled': True}