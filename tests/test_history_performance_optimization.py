#!/usr/bin/env python3
"""
Tests for Analysis History Performance Optimization

This module tests the performance optimization features including caching,
pagination, and performance monitoring.
"""

import unittest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web.utils.history_cache import HistoryCacheManager
from web.utils.history_performance import PerformanceMonitor, PerformanceMetric
from web.utils.history_pagination import OptimizedPaginator, PaginationConfig
from web.utils.history_cache_warmer import CacheWarmer
from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus, MarketType


class TestHistoryCacheManager(unittest.TestCase):
    """Test the Redis cache manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.cache_manager = HistoryCacheManager()
        
        # Mock Redis client for testing
        self.mock_redis = Mock()
        self.cache_manager.redis_client = self.mock_redis
        self.cache_manager.cache_available = True
    
    def test_cache_record(self):
        """Test caching an analysis record"""
        # Create test record
        record = AnalysisHistoryRecord(
            analysis_id="test_001",
            stock_symbol="AAPL",
            stock_name="Apple Inc.",
            market_type=MarketType.US_STOCK.value,
            analysis_date=datetime.now(),
            created_at=datetime.now(),
            status=AnalysisStatus.COMPLETED.value,
            analysis_type="comprehensive",
            analysts_used=["market", "fundamentals"],
            research_depth=3,
            llm_provider="openai",
            llm_model="gpt-4",
            execution_time=120.5,
            raw_results={},
            formatted_results={},
            metadata={}
        )
        
        # Mock Redis setex method
        self.mock_redis.setex.return_value = True
        
        # Test caching
        result = self.cache_manager.cache_record(record)
        
        # Verify
        self.assertTrue(result)
        self.mock_redis.setex.assert_called_once()
    
    def test_get_cached_record(self):
        """Test retrieving a cached record"""
        # Mock Redis get method
        test_data = '{"analysis_id": "test_001", "stock_symbol": "AAPL"}'
        self.mock_redis.get.return_value = test_data.encode('utf-8')
        
        # Test retrieval (will fail due to incomplete data, but tests the flow)
        result = self.cache_manager.get_cached_record("test_001")
        
        # Verify Redis was called
        self.mock_redis.get.assert_called_once()
    
    def test_cache_query_result(self):
        """Test caching query results"""
        # Create test records
        records = []
        
        # Mock Redis setex method
        self.mock_redis.setex.return_value = True
        
        # Test caching
        result = self.cache_manager.cache_query_result(
            filters={}, page=1, page_size=20, sort_by='created_at', 
            sort_order=-1, records=records, total_count=0
        )
        
        # Verify
        self.assertTrue(result)
        self.mock_redis.setex.assert_called_once()
    
    def test_invalidate_query_cache(self):
        """Test invalidating query cache"""
        # Mock Redis keys and delete methods
        self.mock_redis.keys.return_value = ['query:key1', 'query:key2']
        self.mock_redis.delete.return_value = 2
        
        # Test invalidation
        result = self.cache_manager.invalidate_query_cache()
        
        # Verify
        self.assertEqual(result, 2)
        self.mock_redis.keys.assert_called_once()
        self.mock_redis.delete.assert_called_once()


class TestPerformanceMonitor(unittest.TestCase):
    """Test the performance monitoring system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.monitor = PerformanceMonitor(max_metrics=100)
    
    def test_record_metric(self):
        """Test recording a performance metric"""
        metric = PerformanceMetric(
            operation="test_operation",
            duration=1.5,
            timestamp=datetime.now(),
            success=True,
            record_count=10
        )
        
        # Record metric
        self.monitor.record_metric(metric)
        
        # Verify
        self.assertEqual(len(self.monitor.metrics), 1)
        self.assertIn("test_operation", self.monitor.operation_stats)
        self.assertEqual(len(self.monitor.operation_stats["test_operation"]), 1)
    
    def test_get_operation_stats(self):
        """Test getting operation statistics"""
        # Record multiple metrics
        for i in range(5):
            metric = PerformanceMetric(
                operation="test_op",
                duration=1.0 + i * 0.1,
                timestamp=datetime.now(),
                success=True,
                record_count=10
            )
            self.monitor.record_metric(metric)
        
        # Get stats
        stats = self.monitor.get_operation_stats("test_op")
        
        # Verify
        self.assertEqual(stats['count'], 5)
        self.assertGreater(stats['avg_duration'], 1.0)
        self.assertEqual(stats['success_rate'], 100.0)
    
    def test_get_overall_stats(self):
        """Test getting overall statistics"""
        # Record metrics for different operations
        operations = ["op1", "op2", "op3"]
        for op in operations:
            for i in range(3):
                metric = PerformanceMetric(
                    operation=op,
                    duration=1.0,
                    timestamp=datetime.now(),
                    success=True,
                    record_count=5
                )
                self.monitor.record_metric(metric)
        
        # Get overall stats
        stats = self.monitor.get_overall_stats()
        
        # Verify
        self.assertEqual(stats['total_operations'], 9)
        self.assertEqual(stats['success_rate'], 100.0)
        self.assertEqual(len(stats['operations_by_type']), 3)
    
    def test_slow_query_tracking(self):
        """Test slow query tracking"""
        # Record a slow query
        slow_metric = PerformanceMetric(
            operation="slow_query",
            duration=3.0,  # Above threshold
            timestamp=datetime.now(),
            success=True,
            record_count=100
        )
        self.monitor.record_metric(slow_metric)
        
        # Get slow queries
        slow_queries = self.monitor.get_slow_queries(10)
        
        # Verify
        self.assertEqual(len(slow_queries), 1)
        self.assertEqual(slow_queries[0]['operation'], "slow_query")
        self.assertEqual(slow_queries[0]['duration'], 3.0)


class TestOptimizedPaginator(unittest.TestCase):
    """Test the optimized pagination system"""
    
    def setUp(self):
        """Set up test fixtures"""
        config = PaginationConfig(
            default_page_size=10,
            max_page_size=50,
            adaptive_sizing=True,
            cache_pages=False  # Disable caching for tests
        )
        self.paginator = OptimizedPaginator(config)
    
    def test_calculate_optimal_page_size(self):
        """Test optimal page size calculation"""
        # Test fast queries
        optimal_size = self.paginator._calculate_optimal_page_size(1000, 0.3)
        self.assertGreaterEqual(optimal_size, self.paginator.config.min_page_size)
        self.assertLessEqual(optimal_size, self.paginator.config.max_page_size)
        
        # Test slow queries
        optimal_size_slow = self.paginator._calculate_optimal_page_size(1000, 3.0)
        self.assertLessEqual(optimal_size_slow, optimal_size)
    
    def test_should_use_cursor_pagination(self):
        """Test cursor pagination decision"""
        # Small dataset, early page
        self.assertFalse(self.paginator._should_use_cursor_pagination(100, 1))
        
        # Large dataset
        self.assertTrue(self.paginator._should_use_cursor_pagination(2000, 1))
        
        # Deep page
        self.assertTrue(self.paginator._should_use_cursor_pagination(500, 60))
    
    def test_paginate(self):
        """Test pagination execution"""
        # Mock query function
        def mock_query_func(filters, page, page_size, sort_by, sort_order):
            # Return empty results for testing
            return [], 0
        
        # Test pagination
        result = self.paginator.paginate(
            query_func=mock_query_func,
            filters={},
            page=1,
            page_size=20
        )
        
        # Verify result structure
        self.assertEqual(result.current_page, 1)
        self.assertEqual(result.page_size, 20)
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.total_pages, 1)
        self.assertFalse(result.has_next)
        self.assertFalse(result.has_previous)


class TestCacheWarmer(unittest.TestCase):
    """Test the cache warming system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.cache_warmer = CacheWarmer()
        
        # Mock dependencies
        self.cache_warmer.storage = Mock()
        self.cache_warmer.cache_manager = Mock()
        self.cache_warmer.cache_manager.is_available.return_value = True
        self.cache_warmer.storage.is_available.return_value = True
    
    def test_warm_recent_records(self):
        """Test warming cache with recent records"""
        # Mock storage response
        mock_records = []  # Empty for simplicity
        self.cache_warmer.storage.get_user_history.return_value = (mock_records, 0)
        
        # Mock cache manager
        self.cache_warmer.cache_manager.cache_record.return_value = True
        
        # Test warming
        result = self.cache_warmer.warm_recent_records(10)
        
        # Verify
        self.cache_warmer.storage.get_user_history.assert_called_once()
        self.assertEqual(result, 0)  # No records to warm
    
    def test_warm_statistics_cache(self):
        """Test warming statistics cache"""
        # Mock storage response
        mock_stats = {'total_analyses': 100}
        self.cache_warmer.storage.get_history_stats.return_value = mock_stats
        
        # Test warming
        result = self.cache_warmer.warm_statistics_cache()
        
        # Verify
        self.assertTrue(result)
        self.cache_warmer.storage.get_history_stats.assert_called_once()
    
    def test_get_warming_stats(self):
        """Test getting warming statistics"""
        stats = self.cache_warmer.get_warming_stats()
        
        # Verify structure
        self.assertIn('config', stats)
        self.assertIn('cache_available', stats)
        self.assertIn('storage_available', stats)


class TestIntegration(unittest.TestCase):
    """Integration tests for performance optimization"""
    
    def test_performance_monitoring_integration(self):
        """Test integration between performance monitoring and caching"""
        # This would test the full integration but requires actual database
        # For now, just verify components can be instantiated together
        
        cache_manager = HistoryCacheManager()
        performance_monitor = PerformanceMonitor()
        paginator = OptimizedPaginator()
        cache_warmer = CacheWarmer()
        
        # Verify all components are created
        self.assertIsNotNone(cache_manager)
        self.assertIsNotNone(performance_monitor)
        self.assertIsNotNone(paginator)
        self.assertIsNotNone(cache_warmer)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)