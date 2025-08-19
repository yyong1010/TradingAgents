#!/usr/bin/env python3
"""
Analysis History Caching Service

This module provides Redis-based caching for analysis history records to improve
performance and reduce database load. It implements intelligent caching strategies
with automatic cache invalidation and fallback mechanisms.
"""

import json
import logging
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import asdict

from tradingagents.config.database_manager import get_database_manager
from web.models.history_models import AnalysisHistoryRecord

# Setup logging
logger = logging.getLogger(__name__)


class HistoryCacheManager:
    """
    Redis-based caching manager for analysis history records
    
    Provides intelligent caching with automatic expiration, cache warming,
    and performance monitoring capabilities.
    """
    
    # Cache key prefixes
    CACHE_PREFIX = "history:"
    RECORD_PREFIX = f"{CACHE_PREFIX}record:"
    QUERY_PREFIX = f"{CACHE_PREFIX}query:"
    STATS_PREFIX = f"{CACHE_PREFIX}stats:"
    METADATA_PREFIX = f"{CACHE_PREFIX}meta:"
    
    # Cache expiration times (in seconds)
    RECORD_TTL = 3600  # 1 hour for individual records
    QUERY_TTL = 300    # 5 minutes for query results
    STATS_TTL = 600    # 10 minutes for statistics
    METADATA_TTL = 1800  # 30 minutes for metadata
    
    # Cache size limits
    MAX_QUERY_CACHE_SIZE = 1000
    MAX_RECORD_CACHE_SIZE = 5000
    
    def __init__(self):
        """Initialize the cache manager"""
        self.db_manager = get_database_manager()
        self.redis_client = None
        self.cache_available = False
        
        # Initialize Redis connection
        self._initialize_redis()
        
        # Performance metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_errors = 0
        
    def _initialize_redis(self) -> None:
        """Initialize Redis connection with error handling"""
        try:
            if self.db_manager.is_redis_available():
                self.redis_client = self.db_manager.get_redis_client()
                if self.redis_client:
                    # Test connection
                    self.redis_client.ping()
                    self.cache_available = True
                    logger.info("Redis cache initialized successfully")
                else:
                    logger.warning("Redis client not available")
            else:
                logger.info("Redis not available, caching disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self.cache_available = False
    
    def is_available(self) -> bool:
        """Check if caching is available"""
        return self.cache_available and self.redis_client is not None
    
    def _generate_cache_key(self, prefix: str, identifier: str) -> str:
        """Generate a cache key with proper prefix"""
        return f"{prefix}{identifier}"
    
    def _generate_query_key(self, filters: Dict[str, Any], page: int, page_size: int, 
                           sort_by: str, sort_order: int) -> str:
        """Generate a cache key for query results"""
        # Create a deterministic hash of the query parameters
        query_data = {
            'filters': filters,
            'page': page,
            'page_size': page_size,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
        
        # Convert to JSON string and hash
        query_str = json.dumps(query_data, sort_keys=True, default=str)
        query_hash = hashlib.md5(query_str.encode()).hexdigest()
        
        return self._generate_cache_key(self.QUERY_PREFIX, query_hash)
    
    def _serialize_record(self, record: AnalysisHistoryRecord) -> str:
        """Serialize a record for caching"""
        try:
            record_dict = record.to_dict()
            return json.dumps(record_dict, default=str)
        except Exception as e:
            logger.error(f"Failed to serialize record {record.analysis_id}: {e}")
            return None
    
    def _deserialize_record(self, data: str) -> Optional[AnalysisHistoryRecord]:
        """Deserialize a record from cache"""
        try:
            record_dict = json.loads(data)
            return AnalysisHistoryRecord.from_dict(record_dict)
        except Exception as e:
            logger.error(f"Failed to deserialize cached record: {e}")
            return None
    
    def _serialize_query_result(self, records: List[AnalysisHistoryRecord], 
                               total_count: int) -> str:
        """Serialize query results for caching"""
        try:
            result_data = {
                'records': [record.to_dict() for record in records],
                'total_count': total_count,
                'cached_at': datetime.now().isoformat()
            }
            return json.dumps(result_data, default=str)
        except Exception as e:
            logger.error(f"Failed to serialize query result: {e}")
            return None
    
    def _deserialize_query_result(self, data: str) -> Optional[Tuple[List[AnalysisHistoryRecord], int]]:
        """Deserialize query results from cache"""
        try:
            result_data = json.loads(data)
            records = [AnalysisHistoryRecord.from_dict(record_dict) 
                      for record_dict in result_data['records']]
            total_count = result_data['total_count']
            return records, total_count
        except Exception as e:
            logger.error(f"Failed to deserialize cached query result: {e}")
            return None
    
    def cache_record(self, record: AnalysisHistoryRecord) -> bool:
        """
        Cache an individual analysis record
        
        Args:
            record: The record to cache
            
        Returns:
            bool: True if cached successfully, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            cache_key = self._generate_cache_key(self.RECORD_PREFIX, record.analysis_id)
            serialized_data = self._serialize_record(record)
            
            if serialized_data:
                self.redis_client.setex(cache_key, self.RECORD_TTL, serialized_data)
                logger.debug(f"Cached record: {record.analysis_id}")
                return True
            
        except Exception as e:
            logger.error(f"Failed to cache record {record.analysis_id}: {e}")
            self.cache_errors += 1
        
        return False
    
    def get_cached_record(self, analysis_id: str) -> Optional[AnalysisHistoryRecord]:
        """
        Retrieve a cached analysis record
        
        Args:
            analysis_id: The analysis ID to retrieve
            
        Returns:
            AnalysisHistoryRecord if found in cache, None otherwise
        """
        if not self.is_available():
            return None
        
        try:
            cache_key = self._generate_cache_key(self.RECORD_PREFIX, analysis_id)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                record = self._deserialize_record(cached_data.decode('utf-8'))
                if record:
                    self.cache_hits += 1
                    logger.debug(f"Cache hit for record: {analysis_id}")
                    return record
            
            self.cache_misses += 1
            logger.debug(f"Cache miss for record: {analysis_id}")
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached record {analysis_id}: {e}")
            self.cache_errors += 1
        
        return None
    
    def cache_query_result(self, filters: Dict[str, Any], page: int, page_size: int,
                          sort_by: str, sort_order: int, records: List[AnalysisHistoryRecord],
                          total_count: int) -> bool:
        """
        Cache query results
        
        Args:
            filters: Query filters
            page: Page number
            page_size: Page size
            sort_by: Sort field
            sort_order: Sort order
            records: Query result records
            total_count: Total record count
            
        Returns:
            bool: True if cached successfully, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            cache_key = self._generate_query_key(filters, page, page_size, sort_by, sort_order)
            serialized_data = self._serialize_query_result(records, total_count)
            
            if serialized_data:
                self.redis_client.setex(cache_key, self.QUERY_TTL, serialized_data)
                logger.debug(f"Cached query result: {len(records)} records")
                return True
            
        except Exception as e:
            logger.error(f"Failed to cache query result: {e}")
            self.cache_errors += 1
        
        return False
    
    def get_cached_query_result(self, filters: Dict[str, Any], page: int, page_size: int,
                               sort_by: str, sort_order: int) -> Optional[Tuple[List[AnalysisHistoryRecord], int]]:
        """
        Retrieve cached query results
        
        Args:
            filters: Query filters
            page: Page number
            page_size: Page size
            sort_by: Sort field
            sort_order: Sort order
            
        Returns:
            Tuple of (records, total_count) if found in cache, None otherwise
        """
        if not self.is_available():
            return None
        
        try:
            cache_key = self._generate_query_key(filters, page, page_size, sort_by, sort_order)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                result = self._deserialize_query_result(cached_data.decode('utf-8'))
                if result:
                    self.cache_hits += 1
                    logger.debug(f"Cache hit for query: {len(result[0])} records")
                    return result
            
            self.cache_misses += 1
            logger.debug("Cache miss for query")
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached query result: {e}")
            self.cache_errors += 1
        
        return None
    
    def invalidate_record(self, analysis_id: str) -> bool:
        """
        Invalidate cached record
        
        Args:
            analysis_id: The analysis ID to invalidate
            
        Returns:
            bool: True if invalidated successfully, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            cache_key = self._generate_cache_key(self.RECORD_PREFIX, analysis_id)
            deleted = self.redis_client.delete(cache_key)
            
            if deleted:
                logger.debug(f"Invalidated cached record: {analysis_id}")
            
            return deleted > 0
            
        except Exception as e:
            logger.error(f"Failed to invalidate cached record {analysis_id}: {e}")
            self.cache_errors += 1
        
        return False
    
    def invalidate_query_cache(self) -> int:
        """
        Invalidate all cached query results
        
        Returns:
            int: Number of keys invalidated
        """
        if not self.is_available():
            return 0
        
        try:
            pattern = f"{self.QUERY_PREFIX}*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cached query results")
                return deleted
            
        except Exception as e:
            logger.error(f"Failed to invalidate query cache: {e}")
            self.cache_errors += 1
        
        return 0
    
    def cache_stats(self, stats: Dict[str, Any]) -> bool:
        """
        Cache statistics data
        
        Args:
            stats: Statistics to cache
            
        Returns:
            bool: True if cached successfully, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            cache_key = self._generate_cache_key(self.STATS_PREFIX, "global")
            stats_data = {
                **stats,
                'cached_at': datetime.now().isoformat()
            }
            serialized_data = json.dumps(stats_data, default=str)
            
            self.redis_client.setex(cache_key, self.STATS_TTL, serialized_data)
            logger.debug("Cached statistics data")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache statistics: {e}")
            self.cache_errors += 1
        
        return False
    
    def get_cached_stats(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached statistics
        
        Returns:
            Dict containing statistics if found in cache, None otherwise
        """
        if not self.is_available():
            return None
        
        try:
            cache_key = self._generate_cache_key(self.STATS_PREFIX, "global")
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                stats = json.loads(cached_data.decode('utf-8'))
                self.cache_hits += 1
                logger.debug("Cache hit for statistics")
                return stats
            
            self.cache_misses += 1
            logger.debug("Cache miss for statistics")
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached statistics: {e}")
            self.cache_errors += 1
        
        return None
    
    def warm_cache(self, recent_records: List[AnalysisHistoryRecord]) -> int:
        """
        Warm the cache with recent records
        
        Args:
            recent_records: List of recent records to cache
            
        Returns:
            int: Number of records successfully cached
        """
        if not self.is_available():
            return 0
        
        cached_count = 0
        
        for record in recent_records:
            if self.cache_record(record):
                cached_count += 1
        
        logger.info(f"Cache warmed with {cached_count} records")
        return cached_count
    
    def get_cache_metrics(self) -> Dict[str, Any]:
        """
        Get cache performance metrics
        
        Returns:
            Dict containing cache metrics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        metrics = {
            'cache_available': self.cache_available,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_errors': self.cache_errors,
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests
        }
        
        if self.is_available():
            try:
                # Get Redis memory info
                info = self.redis_client.info('memory')
                metrics.update({
                    'redis_memory_used': info.get('used_memory_human', 'N/A'),
                    'redis_memory_peak': info.get('used_memory_peak_human', 'N/A'),
                    'redis_keys': self.redis_client.dbsize()
                })
            except Exception as e:
                logger.error(f"Failed to get Redis metrics: {e}")
        
        return metrics
    
    def cleanup_expired_cache(self) -> int:
        """
        Clean up expired cache entries
        
        Returns:
            int: Number of entries cleaned up
        """
        if not self.is_available():
            return 0
        
        try:
            # Get all cache keys
            patterns = [
                f"{self.RECORD_PREFIX}*",
                f"{self.QUERY_PREFIX}*",
                f"{self.STATS_PREFIX}*",
                f"{self.METADATA_PREFIX}*"
            ]
            
            cleaned_count = 0
            
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                for key in keys:
                    ttl = self.redis_client.ttl(key)
                    if ttl == -1:  # Key exists but has no expiration
                        # Set appropriate TTL based on key type
                        if key.startswith(self.RECORD_PREFIX):
                            self.redis_client.expire(key, self.RECORD_TTL)
                        elif key.startswith(self.QUERY_PREFIX):
                            self.redis_client.expire(key, self.QUERY_TTL)
                        elif key.startswith(self.STATS_PREFIX):
                            self.redis_client.expire(key, self.STATS_TTL)
                        elif key.startswith(self.METADATA_PREFIX):
                            self.redis_client.expire(key, self.METADATA_TTL)
                        
                        cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Set TTL for {cleaned_count} cache entries")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            self.cache_errors += 1
        
        return 0
    
    def clear_all_cache(self) -> int:
        """
        Clear all history-related cache entries
        
        Returns:
            int: Number of entries cleared
        """
        if not self.is_available():
            return 0
        
        try:
            pattern = f"{self.CACHE_PREFIX}*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries")
                return deleted
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            self.cache_errors += 1
        
        return 0


# Global cache manager instance
_cache_manager = None

def get_cache_manager() -> HistoryCacheManager:
    """Get the global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = HistoryCacheManager()
    return _cache_manager