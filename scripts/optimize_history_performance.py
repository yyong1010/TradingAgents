#!/usr/bin/env python3
"""
Analysis History Performance Optimization Script

This script analyzes the current performance of the analysis history system
and applies optimizations including cache warming, index optimization,
and performance monitoring setup.
"""

import sys
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import optimization utilities
from web.utils.history_storage import get_history_storage
from web.utils.history_cache import get_cache_manager
from web.utils.history_performance import get_performance_monitor, log_performance_summary
from web.utils.history_cache_warmer import get_cache_warmer
from web.utils.history_pagination import get_paginator


class HistoryPerformanceOptimizer:
    """
    Comprehensive performance optimizer for analysis history system
    """
    
    def __init__(self):
        """Initialize the optimizer"""
        self.storage = get_history_storage()
        self.cache_manager = get_cache_manager()
        self.performance_monitor = get_performance_monitor()
        self.cache_warmer = get_cache_warmer()
        self.paginator = get_paginator()
        
        self.optimization_results = {
            'started_at': datetime.now().isoformat(),
            'steps_completed': [],
            'errors': [],
            'recommendations': [],
            'performance_before': {},
            'performance_after': {},
            'total_duration': 0.0
        }
    
    def analyze_current_performance(self) -> dict:
        """
        Analyze current system performance
        
        Returns:
            Dictionary containing performance analysis
        """
        logger.info("Analyzing current performance...")
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'storage_available': self.storage.is_available(),
            'cache_available': self.cache_manager.is_available(),
            'cache_metrics': {},
            'performance_stats': {},
            'database_stats': {},
            'recommendations': []
        }
        
        try:
            # Get cache metrics
            if self.cache_manager.is_available():
                analysis['cache_metrics'] = self.cache_manager.get_cache_metrics()
            
            # Get performance stats
            analysis['performance_stats'] = self.performance_monitor.get_overall_stats(
                timedelta(hours=24)
            )
            
            # Get database statistics
            if self.storage.is_available():
                analysis['database_stats'] = self.storage.get_history_stats()
            
            # Get recommendations
            analysis['recommendations'] = self.performance_monitor.get_performance_recommendations()
            
            logger.info("Performance analysis completed")
            
        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
            analysis['error'] = str(e)
        
        return analysis
    
    def optimize_database_indexes(self) -> bool:
        """
        Optimize database indexes for better query performance
        
        Returns:
            True if optimization succeeded
        """
        logger.info("Optimizing database indexes...")
        
        try:
            if not self.storage.is_available():
                logger.warning("Storage not available, skipping index optimization")
                return False
            
            # Recreate indexes (they are created in _create_indexes method)
            self.storage._create_indexes()
            
            # Analyze index usage (if MongoDB supports it)
            if hasattr(self.storage.collection, 'index_stats'):
                try:
                    index_stats = list(self.storage.collection.index_stats())
                    logger.info(f"Index statistics: {len(index_stats)} indexes analyzed")
                    
                    # Log index usage
                    for stat in index_stats:
                        index_name = stat.get('name', 'unknown')
                        usage_count = stat.get('accesses', {}).get('ops', 0)
                        logger.debug(f"Index '{index_name}': {usage_count} operations")
                        
                except Exception as e:
                    logger.debug(f"Could not get index statistics: {e}")
            
            self.optimization_results['steps_completed'].append('database_indexes')
            logger.info("Database index optimization completed")
            return True
            
        except Exception as e:
            logger.error(f"Database index optimization failed: {e}")
            self.optimization_results['errors'].append(f"Index optimization: {e}")
            return False
    
    def warm_cache_system(self) -> bool:
        """
        Warm the cache system with frequently accessed data
        
        Returns:
            True if cache warming succeeded
        """
        logger.info("Warming cache system...")
        
        try:
            if not self.cache_manager.is_available():
                logger.warning("Cache not available, skipping cache warming")
                return False
            
            # Perform full cache warming
            warming_results = self.cache_warmer.full_cache_warming()
            
            logger.info(f"Cache warming completed: {warming_results}")
            
            self.optimization_results['steps_completed'].append('cache_warming')
            self.optimization_results['cache_warming_results'] = warming_results
            
            return True
            
        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            self.optimization_results['errors'].append(f"Cache warming: {e}")
            return False
    
    def optimize_pagination_settings(self) -> bool:
        """
        Optimize pagination settings based on current performance
        
        Returns:
            True if optimization succeeded
        """
        logger.info("Optimizing pagination settings...")
        
        try:
            # Get current pagination performance
            pagination_stats = self.paginator.get_performance_stats()
            
            # Adjust settings based on performance
            if pagination_stats['avg_query_time'] > 2.0:
                # Slow queries - reduce default page size
                self.paginator.config.default_page_size = min(15, self.paginator.config.default_page_size)
                logger.info("Reduced default page size due to slow queries")
            elif pagination_stats['avg_query_time'] < 0.5:
                # Fast queries - can increase page size
                self.paginator.config.default_page_size = min(30, self.paginator.config.max_page_size)
                logger.info("Increased default page size due to fast queries")
            
            # Enable adaptive sizing if not already enabled
            if not self.paginator.config.adaptive_sizing:
                self.paginator.config.adaptive_sizing = True
                logger.info("Enabled adaptive page sizing")
            
            # Enable prefetching for better user experience
            if not self.paginator.config.prefetch_next_page:
                self.paginator.config.prefetch_next_page = True
                logger.info("Enabled next page prefetching")
            
            self.optimization_results['steps_completed'].append('pagination_optimization')
            logger.info("Pagination optimization completed")
            return True
            
        except Exception as e:
            logger.error(f"Pagination optimization failed: {e}")
            self.optimization_results['errors'].append(f"Pagination optimization: {e}")
            return False
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> bool:
        """
        Clean up old analysis records to improve performance
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            True if cleanup succeeded
        """
        logger.info(f"Cleaning up data older than {days_to_keep} days...")
        
        try:
            if not self.storage.is_available():
                logger.warning("Storage not available, skipping data cleanup")
                return False
            
            # Clean up old records
            deleted_count = self.storage.cleanup_old_records(days_to_keep)
            
            logger.info(f"Cleaned up {deleted_count} old records")
            
            self.optimization_results['steps_completed'].append('data_cleanup')
            self.optimization_results['records_cleaned'] = deleted_count
            
            return True
            
        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            self.optimization_results['errors'].append(f"Data cleanup: {e}")
            return False
    
    def setup_performance_monitoring(self) -> bool:
        """
        Set up ongoing performance monitoring
        
        Returns:
            True if setup succeeded
        """
        logger.info("Setting up performance monitoring...")
        
        try:
            # Start periodic cache warming
            self.cache_warmer.start_periodic_warming()
            
            # Log current performance summary
            log_performance_summary(timedelta(hours=1))
            
            self.optimization_results['steps_completed'].append('performance_monitoring')
            logger.info("Performance monitoring setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Performance monitoring setup failed: {e}")
            self.optimization_results['errors'].append(f"Performance monitoring: {e}")
            return False
    
    def run_performance_tests(self) -> dict:
        """
        Run performance tests to measure optimization impact
        
        Returns:
            Dictionary containing test results
        """
        logger.info("Running performance tests...")
        
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'tests': []
        }
        
        try:
            # Test 1: Basic query performance
            start_time = time.time()
            records, total_count = self.storage.get_user_history(page=1, page_size=20)
            query_time = time.time() - start_time
            
            test_results['tests'].append({
                'name': 'basic_query',
                'duration': query_time,
                'records_returned': len(records),
                'total_count': total_count,
                'success': True
            })
            
            # Test 2: Filtered query performance
            start_time = time.time()
            records, total_count = self.storage.get_user_history(
                filters={'status': 'completed'},
                page=1,
                page_size=20
            )
            query_time = time.time() - start_time
            
            test_results['tests'].append({
                'name': 'filtered_query',
                'duration': query_time,
                'records_returned': len(records),
                'total_count': total_count,
                'success': True
            })
            
            # Test 3: Statistics query performance
            start_time = time.time()
            stats = self.storage.get_history_stats()
            stats_time = time.time() - start_time
            
            test_results['tests'].append({
                'name': 'statistics_query',
                'duration': stats_time,
                'success': bool(stats),
                'total_analyses': stats.get('total_analyses', 0) if stats else 0
            })
            
            # Test 4: Cache performance
            if self.cache_manager.is_available() and records:
                test_record = records[0]
                
                # Test cache write
                start_time = time.time()
                cache_write_success = self.cache_manager.cache_record(test_record)
                cache_write_time = time.time() - start_time
                
                # Test cache read
                start_time = time.time()
                cached_record = self.cache_manager.get_cached_record(test_record.analysis_id)
                cache_read_time = time.time() - start_time
                
                test_results['tests'].append({
                    'name': 'cache_performance',
                    'write_duration': cache_write_time,
                    'read_duration': cache_read_time,
                    'write_success': cache_write_success,
                    'read_success': cached_record is not None
                })
            
            logger.info(f"Performance tests completed: {len(test_results['tests'])} tests")
            
        except Exception as e:
            logger.error(f"Performance tests failed: {e}")
            test_results['error'] = str(e)
        
        return test_results
    
    def run_full_optimization(self, cleanup_old_data: bool = False, 
                             days_to_keep: int = 90) -> dict:
        """
        Run complete performance optimization
        
        Args:
            cleanup_old_data: Whether to clean up old data
            days_to_keep: Days of data to keep if cleaning up
            
        Returns:
            Dictionary containing optimization results
        """
        logger.info("Starting full performance optimization...")
        start_time = time.time()
        
        # Analyze performance before optimization
        self.optimization_results['performance_before'] = self.analyze_current_performance()
        
        # Run optimization steps
        optimization_steps = [
            ('Database Index Optimization', self.optimize_database_indexes),
            ('Cache System Warming', self.warm_cache_system),
            ('Pagination Optimization', self.optimize_pagination_settings),
            ('Performance Monitoring Setup', self.setup_performance_monitoring)
        ]
        
        if cleanup_old_data:
            optimization_steps.append(
                ('Data Cleanup', lambda: self.cleanup_old_data(days_to_keep))
            )
        
        # Execute optimization steps
        for step_name, step_func in optimization_steps:
            logger.info(f"Executing: {step_name}")
            try:
                success = step_func()
                if success:
                    logger.info(f"✅ {step_name} completed successfully")
                else:
                    logger.warning(f"⚠️ {step_name} completed with warnings")
            except Exception as e:
                logger.error(f"❌ {step_name} failed: {e}")
                self.optimization_results['errors'].append(f"{step_name}: {e}")
        
        # Run performance tests after optimization
        self.optimization_results['performance_tests'] = self.run_performance_tests()
        
        # Analyze performance after optimization
        self.optimization_results['performance_after'] = self.analyze_current_performance()
        
        # Calculate total duration
        self.optimization_results['total_duration'] = time.time() - start_time
        self.optimization_results['completed_at'] = datetime.now().isoformat()
        
        # Generate summary
        self._generate_optimization_summary()
        
        logger.info(f"Full optimization completed in {self.optimization_results['total_duration']:.2f}s")
        
        return self.optimization_results
    
    def _generate_optimization_summary(self):
        """Generate optimization summary"""
        summary = []
        
        # Steps completed
        steps_completed = len(self.optimization_results['steps_completed'])
        total_steps = steps_completed + len(self.optimization_results['errors'])
        summary.append(f"Completed {steps_completed}/{total_steps} optimization steps")
        
        # Performance improvements
        before_stats = self.optimization_results['performance_before'].get('performance_stats', {})
        after_stats = self.optimization_results['performance_after'].get('performance_stats', {})
        
        if before_stats and after_stats:
            before_avg = before_stats.get('avg_duration', 0)
            after_avg = after_stats.get('avg_duration', 0)
            
            if before_avg > 0 and after_avg > 0:
                improvement = ((before_avg - after_avg) / before_avg) * 100
                summary.append(f"Average query time improvement: {improvement:.1f}%")
        
        # Cache improvements
        before_cache = self.optimization_results['performance_before'].get('cache_metrics', {})
        after_cache = self.optimization_results['performance_after'].get('cache_metrics', {})
        
        if before_cache and after_cache:
            before_hit_rate = before_cache.get('hit_rate', 0)
            after_hit_rate = after_cache.get('hit_rate', 0)
            
            if after_hit_rate > before_hit_rate:
                summary.append(f"Cache hit rate improved from {before_hit_rate:.1f}% to {after_hit_rate:.1f}%")
        
        # Errors
        if self.optimization_results['errors']:
            summary.append(f"Encountered {len(self.optimization_results['errors'])} errors")
        
        self.optimization_results['summary'] = summary
        
        # Log summary
        logger.info("Optimization Summary:")
        for item in summary:
            logger.info(f"  - {item}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Optimize analysis history performance')
    parser.add_argument('--cleanup-data', action='store_true', 
                       help='Clean up old data (default: False)')
    parser.add_argument('--days-to-keep', type=int, default=90,
                       help='Days of data to keep when cleaning up (default: 90)')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Only analyze performance, do not optimize')
    
    args = parser.parse_args()
    
    optimizer = HistoryPerformanceOptimizer()
    
    if args.analyze_only:
        # Only analyze current performance
        logger.info("Analyzing current performance (no optimization)...")
        analysis = optimizer.analyze_current_performance()
        
        print("\n" + "="*60)
        print("PERFORMANCE ANALYSIS RESULTS")
        print("="*60)
        
        print(f"Storage Available: {analysis['storage_available']}")
        print(f"Cache Available: {analysis['cache_available']}")
        
        if analysis.get('performance_stats'):
            stats = analysis['performance_stats']
            print(f"\nPerformance Statistics:")
            print(f"  Total Operations: {stats.get('total_operations', 0)}")
            print(f"  Average Duration: {stats.get('avg_duration', 0):.3f}s")
            print(f"  Success Rate: {stats.get('success_rate', 0):.1f}%")
            print(f"  Cache Hit Rate: {stats.get('cache_hit_rate', 0):.1f}%")
        
        if analysis.get('recommendations'):
            print(f"\nRecommendations:")
            for rec in analysis['recommendations']:
                print(f"  - {rec}")
        
    else:
        # Run full optimization
        results = optimizer.run_full_optimization(
            cleanup_old_data=args.cleanup_data,
            days_to_keep=args.days_to_keep
        )
        
        print("\n" + "="*60)
        print("OPTIMIZATION RESULTS")
        print("="*60)
        
        print(f"Duration: {results['total_duration']:.2f}s")
        print(f"Steps Completed: {len(results['steps_completed'])}")
        print(f"Errors: {len(results['errors'])}")
        
        if results.get('summary'):
            print(f"\nSummary:")
            for item in results['summary']:
                print(f"  - {item}")
        
        if results['errors']:
            print(f"\nErrors:")
            for error in results['errors']:
                print(f"  - {error}")


if __name__ == '__main__':
    main()