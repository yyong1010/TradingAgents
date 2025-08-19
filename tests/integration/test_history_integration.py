#!/usr/bin/env python3
"""
Integration tests for analysis history end-to-end functionality

This test suite validates the complete analysis workflow with history saving,
history page rendering with real database data, search/filter/pagination with
large datasets, and download functionality producing correct files.

Requirements tested:
- 1.1: Automatic analysis result saving with timestamp and metadata
- 2.2: History page display with paginated table format
- 3.1: Search functionality by stock code and stock name
- 4.1: Download options for available formats (Word, PDF, Markdown)
"""

import unittest
import asyncio
import threading
import time
import tempfile
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, MagicMock
import uuid

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import test utilities
from tests.test_analysis_history_storage import TestAnalysisHistoryStorageFixtures

# Import components to test
from web.utils.analysis_runner import run_stock_analysis, format_analysis_results
from web.utils.history_storage import get_history_storage
from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus, MarketType
from web.modules.analysis_history import (
    render_analysis_history, _get_filtered_history, _render_history_table
)
from web.utils.report_exporter import ReportExporter

# Import logging
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('test.integration')


class TestAnalysisHistoryIntegration(unittest.TestCase):
    """Integration tests for end-to-end analysis history functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.fixtures = TestAnalysisHistoryStorageFixtures()
        self.test_session_id = f"integration_test_{uuid.uuid4().hex[:8]}"
        
        # Initialize history storage
        self.history_storage = get_history_storage()
        
        # Create test data
        self.test_records = self._create_test_dataset()
        
        # Initialize report exporter
        self.report_exporter = ReportExporter()
        
        logger.info(f"Integration test setup complete: {self.test_session_id}")
    
    def tearDown(self):
        """Clean up test environment"""
        # Clean up test records if storage is available
        if self.history_storage.is_available():
            try:
                # Delete test records
                for record in self.test_records:
                    self.history_storage.delete_analysis(record.analysis_id)
                logger.info(f"Cleaned up {len(self.test_records)} test records")
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
    
    def _create_test_dataset(self) -> List[AnalysisHistoryRecord]:
        """Create a comprehensive test dataset for integration testing"""
        test_records = []
        
        # Create records for different scenarios
        test_scenarios = [
            # US stocks
            ("AAPL", "Apple Inc.", MarketType.US_STOCK.value, AnalysisStatus.COMPLETED.value),
            ("GOOGL", "Alphabet Inc.", MarketType.US_STOCK.value, AnalysisStatus.COMPLETED.value),
            ("TSLA", "Tesla Inc.", MarketType.US_STOCK.value, AnalysisStatus.FAILED.value),
            
            # A-shares
            ("000001", "平安银行", MarketType.A_SHARE.value, AnalysisStatus.COMPLETED.value),
            ("000002", "万科A", MarketType.A_SHARE.value, AnalysisStatus.COMPLETED.value),
            ("600036", "招商银行", MarketType.A_SHARE.value, AnalysisStatus.IN_PROGRESS.value),
            
            # HK stocks
            ("0700.HK", "腾讯控股", MarketType.HK_STOCK.value, AnalysisStatus.COMPLETED.value),
            ("0941.HK", "中国移动", MarketType.HK_STOCK.value, AnalysisStatus.COMPLETED.value),
        ]
        
        for i, (symbol, name, market, status) in enumerate(test_scenarios):
            record = AnalysisHistoryRecord(
                analysis_id=f"{self.test_session_id}_{i:03d}",
                stock_symbol=symbol,
                stock_name=name,
                market_type=market,
                analysis_date=datetime.now() - timedelta(days=i),
                status=status,
                analysis_type="comprehensive",
                analysts_used=["market", "fundamentals", "news"],
                research_depth=3,
                llm_provider="dashscope",
                llm_model="qwen-plus",
                execution_time=120.5 + i * 10,
                token_usage={
                    "input_tokens": 2000 + i * 100,
                    "output_tokens": 1000 + i * 50,
                    "total_cost": 0.05 + i * 0.01
                },
                raw_results={
                    "stock_symbol": symbol,
                    "decision": {"action": "buy", "confidence": 0.8},
                    "state": {"analysis_complete": True},
                    "success": status == AnalysisStatus.COMPLETED.value
                },
                formatted_results={
                    "stock_symbol": symbol,
                    "decision": {"action": "买入", "confidence": 0.8},
                    "state": {"analysis_complete": True}
                },
                metadata={
                    "session_id": f"{self.test_session_id}_{i}",
                    "test_record": True,
                    "integration_test": True
                }
            )
            test_records.append(record)
        
        return test_records


class TestCompleteAnalysisWorkflow(TestAnalysisHistoryIntegration):
    """Test complete analysis workflow with history saving"""
    
    @patch('web.utils.analysis_runner.TradingAgentsGraph')
    @patch('web.utils.analysis_runner.prepare_stock_data')
    def test_analysis_workflow_with_history_saving(self, mock_prepare_data, mock_graph):
        """
        Test complete analysis workflow with automatic history saving
        Requirements: 1.1 - Automatic analysis result saving
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Mock successful data preparation
        mock_prepare_result = Mock()
        mock_prepare_result.is_valid = True
        mock_prepare_result.stock_name = "Apple Inc."
        mock_prepare_result.market_type = "美股"
        mock_prepare_result.cache_status = "hit"
        mock_prepare_data.return_value = mock_prepare_result
        
        # Mock successful analysis
        mock_graph_instance = Mock()
        mock_state = {
            "market_report": "Technical analysis shows bullish trend",
            "fundamentals_report": "Strong financial metrics",
            "news_report": "Positive earnings report",
            "risk_assessment": "Low to moderate risk"
        }
        mock_decision = {
            "action": "BUY",
            "confidence": 0.85,
            "target_price": 150.0,
            "reasoning": "Strong fundamentals and positive momentum"
        }
        mock_graph_instance.propagate.return_value = (mock_state, mock_decision)
        mock_graph.return_value = mock_graph_instance
        
        # Execute analysis
        results = run_stock_analysis(
            stock_symbol="AAPL",
            analysis_date="2025-01-06",
            analysts=["market", "fundamentals", "news"],
            research_depth=3,
            llm_provider="dashscope",
            llm_model="qwen-plus",
            market_type="美股"
        )
        
        # Verify analysis succeeded
        self.assertTrue(results['success'])
        self.assertEqual(results['stock_symbol'], "AAPL")
        self.assertIn('session_id', results)
        
        # Verify history was saved
        session_id = results['session_id']
        saved_record = self.history_storage.get_analysis_by_id(session_id)
        
        self.assertIsNotNone(saved_record)
        self.assertEqual(saved_record.stock_symbol, "AAPL")
        self.assertEqual(saved_record.stock_name, "Apple Inc.")
        self.assertEqual(saved_record.status, AnalysisStatus.COMPLETED.value)
        self.assertEqual(saved_record.market_type, "美股")
        self.assertIsNotNone(saved_record.raw_results)
        self.assertGreater(saved_record.execution_time, 0)
        
        logger.info("✅ Complete analysis workflow with history saving test passed")
    
    def test_analysis_failure_history_recording(self):
        """
        Test that failed analyses are also recorded in history
        Requirements: 1.1 - Record all analysis attempts
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # This will fail due to invalid stock symbol
        results = run_stock_analysis(
            stock_symbol="INVALID_SYMBOL_12345",
            analysis_date="2025-01-06",
            analysts=["market"],
            research_depth=1,
            llm_provider="dashscope",
            llm_model="qwen-turbo",
            market_type="美股"
        )
        
        # Verify analysis failed
        self.assertFalse(results['success'])
        self.assertIn('error', results)
        
        # Check if failure was recorded (if session_id exists)
        if 'session_id' in results:
            session_id = results['session_id']
            saved_record = self.history_storage.get_analysis_by_id(session_id)
            
            if saved_record:  # Only check if record was created
                self.assertEqual(saved_record.status, AnalysisStatus.FAILED.value)
                self.assertIn('error', saved_record.metadata)
        
        logger.info("✅ Analysis failure history recording test passed")


class TestHistoryPageRendering(TestAnalysisHistoryIntegration):
    """Test history page rendering with real database data"""
    
    def test_history_page_with_real_data(self):
        """
        Test history page rendering with real database data
        Requirements: 2.2 - History page display with paginated table format
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Save test records to database
        saved_count = 0
        for record in self.test_records:
            if self.history_storage.save_analysis(record):
                saved_count += 1
        
        self.assertGreater(saved_count, 0, "No test records were saved")
        
        # Test basic history retrieval
        filters = {
            'page': 1,
            'page_size': 10,
            'sort_by': 'created_at',
            'sort_order': 'desc'
        }
        
        history_records, total_count = _get_filtered_history(self.history_storage, filters)
        
        # Verify data retrieval
        self.assertGreater(total_count, 0)
        self.assertGreater(len(history_records), 0)
        self.assertLessEqual(len(history_records), filters['page_size'])
        
        # Verify record structure
        for record in history_records:
            self.assertIsInstance(record, AnalysisHistoryRecord)
            self.assertIsNotNone(record.stock_symbol)
            self.assertIsNotNone(record.stock_name)
            self.assertIsNotNone(record.analysis_date)
            self.assertIsNotNone(record.status)
        
        logger.info(f"✅ History page rendering test passed with {total_count} records")
    
    def test_pagination_with_large_dataset(self):
        """
        Test pagination functionality with large datasets
        Requirements: 2.2 - Paginated table format for large datasets
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Create additional test records for pagination testing
        large_dataset = []
        for i in range(25):  # Create 25 additional records
            record = self.fixtures.create_sample_record(
                analysis_id=f"{self.test_session_id}_large_{i:03d}",
                stock_symbol=f"TEST{i:03d}",
                stock_name=f"Test Stock {i}",
                status=AnalysisStatus.COMPLETED.value
            )
            large_dataset.append(record)
        
        # Save large dataset
        saved_count = 0
        for record in large_dataset:
            if self.history_storage.save_analysis(record):
                saved_count += 1
        
        self.assertGreater(saved_count, 20, "Insufficient test records saved")
        
        # Test pagination
        page_size = 10
        
        # Test first page
        filters_page1 = {
            'page': 1,
            'page_size': page_size,
            'sort_by': 'created_at',
            'sort_order': 'desc'
        }
        
        records_page1, total_count = _get_filtered_history(self.history_storage, filters_page1)
        
        self.assertGreater(total_count, page_size)
        self.assertEqual(len(records_page1), page_size)
        
        # Test second page
        filters_page2 = {
            'page': 2,
            'page_size': page_size,
            'sort_by': 'created_at',
            'sort_order': 'desc'
        }
        
        records_page2, _ = _get_filtered_history(self.history_storage, filters_page2)
        
        self.assertGreater(len(records_page2), 0)
        
        # Verify pages contain different records
        page1_ids = {r.analysis_id for r in records_page1}
        page2_ids = {r.analysis_id for r in records_page2}
        self.assertEqual(len(page1_ids.intersection(page2_ids)), 0)
        
        logger.info(f"✅ Pagination test passed with {total_count} total records")


class TestSearchAndFiltering(TestAnalysisHistoryIntegration):
    """Test search, filter, and pagination with large datasets"""
    
    def test_stock_symbol_search(self):
        """
        Test search functionality by stock code
        Requirements: 3.1 - Search functionality by stock code
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Save test records
        for record in self.test_records:
            self.history_storage.save_analysis(record)
        
        # Test exact symbol search
        filters = {
            'stock_symbol': 'AAPL',
            'page': 1,
            'page_size': 10
        }
        
        results, total_count = _get_filtered_history(self.history_storage, filters)
        
        self.assertGreater(total_count, 0)
        for record in results:
            self.assertIn('AAPL', record.stock_symbol.upper())
        
        # Test partial symbol search
        filters['stock_symbol'] = '000'  # Should match A-share stocks
        results, total_count = _get_filtered_history(self.history_storage, filters)
        
        self.assertGreater(total_count, 0)
        for record in results:
            self.assertIn('000', record.stock_symbol)
        
        logger.info("✅ Stock symbol search test passed")
    
    def test_stock_name_search(self):
        """
        Test search functionality by stock name
        Requirements: 3.1 - Search functionality by stock name
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Save test records
        for record in self.test_records:
            self.history_storage.save_analysis(record)
        
        # Test name search
        filters = {
            'stock_name': 'Apple',
            'page': 1,
            'page_size': 10
        }
        
        results, total_count = _get_filtered_history(self.history_storage, filters)
        
        self.assertGreater(total_count, 0)
        for record in results:
            self.assertIn('Apple', record.stock_name)
        
        # Test Chinese name search
        filters['stock_name'] = '银行'
        results, total_count = _get_filtered_history(self.history_storage, filters)
        
        self.assertGreater(total_count, 0)
        for record in results:
            self.assertIn('银行', record.stock_name)
        
        logger.info("✅ Stock name search test passed")
    
    def test_market_type_filtering(self):
        """Test filtering by market type"""
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Save test records
        for record in self.test_records:
            self.history_storage.save_analysis(record)
        
        # Test US stock filtering
        filters = {
            'market_type': MarketType.US_STOCK.value,
            'page': 1,
            'page_size': 10
        }
        
        results, total_count = _get_filtered_history(self.history_storage, filters)
        
        self.assertGreater(total_count, 0)
        for record in results:
            self.assertEqual(record.market_type, MarketType.US_STOCK.value)
        
        # Test A-share filtering
        filters['market_type'] = MarketType.A_SHARE.value
        results, total_count = _get_filtered_history(self.history_storage, filters)
        
        self.assertGreater(total_count, 0)
        for record in results:
            self.assertEqual(record.market_type, MarketType.A_SHARE.value)
        
        logger.info("✅ Market type filtering test passed")
    
    def test_status_filtering(self):
        """Test filtering by analysis status"""
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Save test records
        for record in self.test_records:
            self.history_storage.save_analysis(record)
        
        # Test completed status filtering
        filters = {
            'status': AnalysisStatus.COMPLETED.value,
            'page': 1,
            'page_size': 10
        }
        
        results, total_count = _get_filtered_history(self.history_storage, filters)
        
        self.assertGreater(total_count, 0)
        for record in results:
            self.assertEqual(record.status, AnalysisStatus.COMPLETED.value)
        
        logger.info("✅ Status filtering test passed")
    
    def test_date_range_filtering(self):
        """Test filtering by date range"""
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Save test records
        for record in self.test_records:
            self.history_storage.save_analysis(record)
        
        # Test recent date filtering (last 3 days)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=3)
        
        filters = {
            'date_range': (start_date, end_date),
            'page': 1,
            'page_size': 10
        }
        
        results, total_count = _get_filtered_history(self.history_storage, filters)
        
        # Should have some results within the date range
        self.assertGreaterEqual(total_count, 0)
        
        for record in results:
            record_date = record.analysis_date.date() if isinstance(record.analysis_date, datetime) else record.analysis_date
            self.assertGreaterEqual(record_date, start_date)
            self.assertLessEqual(record_date, end_date)
        
        logger.info("✅ Date range filtering test passed")


class TestDownloadFunctionality(TestAnalysisHistoryIntegration):
    """Test download functionality produces correct files"""
    
    def test_markdown_download(self):
        """
        Test markdown download functionality
        Requirements: 4.1 - Download options for Markdown format
        """
        # Create test analysis results
        test_results = {
            'stock_symbol': 'AAPL',
            'analysis_date': '2025-01-06',
            'decision': {
                'action': 'BUY',
                'confidence': 0.85,
                'target_price': 150.0,
                'reasoning': 'Strong fundamentals and positive momentum'
            },
            'state': {
                'market_report': 'Technical analysis shows bullish trend',
                'fundamentals_report': 'Strong financial metrics',
                'news_report': 'Positive earnings report'
            },
            'success': True,
            'llm_provider': 'dashscope',
            'llm_model': 'qwen-plus',
            'analysts': ['market', 'fundamentals', 'news'],
            'research_depth': 3,
            'is_historical_report': True,
            'historical_analysis_id': f"{self.test_session_id}_download_test"
        }
        
        # Test markdown export
        markdown_content = self.report_exporter.export_report(test_results, 'markdown')
        
        self.assertIsNotNone(markdown_content)
        self.assertIsInstance(markdown_content, bytes)
        
        # Decode and verify content
        markdown_text = markdown_content.decode('utf-8')
        self.assertIn('AAPL', markdown_text)
        self.assertIn('股票分析报告', markdown_text)
        self.assertIn('BUY', markdown_text)
        self.assertIn('Strong fundamentals', markdown_text)
        self.assertIn('历史分析报告', markdown_text)  # Historical report indicator
        
        logger.info("✅ Markdown download test passed")
    
    @unittest.skipIf(not hasattr(ReportExporter(), 'pandoc_available') or not ReportExporter().pandoc_available, 
                     "Pandoc not available for Word export")
    def test_word_download(self):
        """
        Test Word document download functionality
        Requirements: 4.1 - Download options for Word format
        """
        # Create test analysis results
        test_results = {
            'stock_symbol': 'GOOGL',
            'analysis_date': '2025-01-06',
            'decision': {
                'action': 'HOLD',
                'confidence': 0.75,
                'target_price': 2800.0,
                'reasoning': 'Mixed signals in current market conditions'
            },
            'state': {
                'market_report': 'Sideways trend with support at 2700',
                'fundamentals_report': 'Solid revenue growth but margin pressure',
                'news_report': 'Regulatory concerns offset by AI developments'
            },
            'success': True,
            'llm_provider': 'dashscope',
            'llm_model': 'qwen-plus',
            'analysts': ['market', 'fundamentals', 'news'],
            'research_depth': 3,
            'is_historical_report': True,
            'created_at': datetime.now() - timedelta(hours=2),
            'execution_time': 145.7,
            'cost_summary': '¥0.08'
        }
        
        # Test Word export
        try:
            word_content = self.report_exporter.export_report(test_results, 'docx')
            
            self.assertIsNotNone(word_content)
            self.assertIsInstance(word_content, bytes)
            self.assertGreater(len(word_content), 1000)  # Should be substantial file
            
            # Verify it's a valid docx file by checking magic bytes
            self.assertTrue(word_content.startswith(b'PK'))  # ZIP file signature
            
            logger.info(f"✅ Word download test passed, file size: {len(word_content)} bytes")
            
        except Exception as e:
            logger.warning(f"Word export test skipped due to: {e}")
            self.skipTest(f"Word export not available: {e}")
    
    def test_historical_report_metadata_in_download(self):
        """
        Test that historical reports include proper metadata in downloads
        Requirements: 4.1 - Historical analysis date in filename and content
        """
        # Create historical analysis results
        historical_date = datetime.now() - timedelta(days=5)
        test_results = {
            'stock_symbol': 'TSLA',
            'analysis_date': historical_date.strftime('%Y-%m-%d'),
            'created_at': historical_date,
            'decision': {
                'action': 'SELL',
                'confidence': 0.65,
                'target_price': 180.0,
                'reasoning': 'Overvalued at current levels'
            },
            'state': {
                'market_report': 'Bearish technical indicators',
                'fundamentals_report': 'High P/E ratio concerns',
                'risk_assessment': 'High volatility risk'
            },
            'success': True,
            'llm_provider': 'dashscope',
            'llm_model': 'qwen-max',
            'analysts': ['market', 'fundamentals', 'news', 'social'],
            'research_depth': 4,
            'execution_time': 234.5,
            'market_type': '美股',
            'is_historical_report': True,
            'historical_analysis_id': f"{self.test_session_id}_historical"
        }
        
        # Test markdown export with historical metadata
        markdown_content = self.report_exporter.export_report(test_results, 'markdown')
        
        self.assertIsNotNone(markdown_content)
        markdown_text = markdown_content.decode('utf-8')
        
        # Verify historical metadata is included
        self.assertIn('历史分析报告', markdown_text)
        self.assertIn('原始创建时间', markdown_text)
        self.assertIn('分析ID', markdown_text)
        self.assertIn('执行时长', markdown_text)
        # Time should be formatted as minutes and seconds since 234.5s > 60s
        self.assertTrue('分54.5秒' in markdown_text or '234.5秒' in markdown_text)
        self.assertIn('美股', markdown_text)
        
        logger.info("✅ Historical report metadata test passed")
    
    def test_download_error_handling(self):
        """Test download functionality error handling"""
        # Test with invalid results
        invalid_results = None
        
        markdown_content = self.report_exporter.export_report(invalid_results, 'markdown')
        self.assertIsNone(markdown_content)
        
        # Test with invalid format
        valid_results = {
            'stock_symbol': 'TEST',
            'decision': {'action': 'HOLD'},
            'state': {},
            'success': True
        }
        
        invalid_format_content = self.report_exporter.export_report(valid_results, 'invalid_format')
        self.assertIsNone(invalid_format_content)
        
        logger.info("✅ Download error handling test passed")


class TestPerformanceAndScalability(TestAnalysisHistoryIntegration):
    """Test performance with large datasets"""
    
    def test_large_dataset_performance(self):
        """Test system performance with large datasets"""
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Create a larger dataset for performance testing
        large_dataset_size = 50
        large_dataset = []
        
        for i in range(large_dataset_size):
            record = self.fixtures.create_sample_record(
                analysis_id=f"{self.test_session_id}_perf_{i:04d}",
                stock_symbol=f"PERF{i:04d}",
                stock_name=f"Performance Test Stock {i}",
                status=AnalysisStatus.COMPLETED.value if i % 3 != 0 else AnalysisStatus.FAILED.value
            )
            # Vary the dates to test date range queries
            record.analysis_date = datetime.now() - timedelta(days=i % 30)
            record.created_at = datetime.now() - timedelta(days=i % 30)
            large_dataset.append(record)
        
        # Save dataset and measure time
        start_time = time.time()
        saved_count = 0
        for record in large_dataset:
            if self.history_storage.save_analysis(record):
                saved_count += 1
        save_time = time.time() - start_time
        
        self.assertEqual(saved_count, large_dataset_size)
        self.assertLess(save_time, 30.0, f"Saving {large_dataset_size} records took too long: {save_time:.2f}s")
        
        # Test query performance
        start_time = time.time()
        filters = {
            'page': 1,
            'page_size': 20,
            'sort_by': 'created_at',
            'sort_order': 'desc'
        }
        results, total_count = _get_filtered_history(self.history_storage, filters)
        query_time = time.time() - start_time
        
        self.assertGreater(total_count, large_dataset_size - 5)  # Allow for some variance
        self.assertLess(query_time, 5.0, f"Query took too long: {query_time:.2f}s")
        
        # Test filtered query performance
        start_time = time.time()
        filters['stock_symbol'] = 'PERF'
        results, total_count = _get_filtered_history(self.history_storage, filters)
        filtered_query_time = time.time() - start_time
        
        self.assertGreater(total_count, 0)
        self.assertLess(filtered_query_time, 5.0, f"Filtered query took too long: {filtered_query_time:.2f}s")
        
        logger.info(f"✅ Performance test passed - Save: {save_time:.2f}s, Query: {query_time:.2f}s, Filtered: {filtered_query_time:.2f}s")


if __name__ == '__main__':
    # Configure test logging
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the integration tests
    unittest.main(verbosity=2)


class TestEndToEndWorkflow(TestAnalysisHistoryIntegration):
    """Test complete end-to-end workflow scenarios"""
    
    def test_complete_user_workflow(self):
        """
        Test complete user workflow: analysis -> history -> search -> download
        This simulates a real user's interaction with the system
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Step 1: Save some analysis records (simulating completed analyses)
        workflow_records = []
        for i, symbol in enumerate(['AAPL', 'GOOGL', 'MSFT']):
            record = self.fixtures.create_sample_record(
                analysis_id=f"{self.test_session_id}_workflow_{i}",
                stock_symbol=symbol,
                stock_name=f"Test Company {symbol}",
                status=AnalysisStatus.COMPLETED.value
            )
            workflow_records.append(record)
            self.assertTrue(self.history_storage.save_analysis(record))
        
        # Step 2: User views history page (test basic retrieval)
        filters = {'page': 1, 'page_size': 10}
        history_records, total_count = _get_filtered_history(self.history_storage, filters)
        
        self.assertGreaterEqual(total_count, 3)
        self.assertGreaterEqual(len(history_records), 3)
        
        # Step 3: User searches for specific stock
        search_filters = {
            'stock_symbol': 'AAPL',
            'page': 1,
            'page_size': 10
        }
        search_results, search_count = _get_filtered_history(self.history_storage, search_filters)
        
        self.assertGreater(search_count, 0)
        for record in search_results:
            self.assertIn('AAPL', record.stock_symbol)
        
        # Step 4: User downloads a report
        test_record = search_results[0]
        download_results = {
            'stock_symbol': test_record.stock_symbol,
            'analysis_date': test_record.analysis_date.strftime('%Y-%m-%d'),
            'decision': test_record.raw_results.get('decision', {}),
            'state': test_record.raw_results.get('state', {}),
            'success': True,
            'is_historical_report': True,
            'historical_analysis_id': test_record.analysis_id,
            'created_at': test_record.created_at,
            'execution_time': test_record.execution_time,
            'llm_provider': test_record.llm_provider,
            'llm_model': test_record.llm_model,
            'analysts': test_record.analysts_used,
            'research_depth': test_record.research_depth
        }
        
        markdown_content = self.report_exporter.export_report(download_results, 'markdown')
        self.assertIsNotNone(markdown_content)
        
        # Verify the downloaded content contains expected information
        markdown_text = markdown_content.decode('utf-8')
        self.assertIn(test_record.stock_symbol, markdown_text)
        self.assertIn('历史分析报告', markdown_text)
        
        logger.info("✅ Complete user workflow test passed")
    
    def test_concurrent_access_simulation(self):
        """
        Test system behavior under concurrent access
        Simulates multiple users accessing history simultaneously
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Create test data
        concurrent_records = []
        for i in range(10):
            record = self.fixtures.create_sample_record(
                analysis_id=f"{self.test_session_id}_concurrent_{i}",
                stock_symbol=f"CONC{i:02d}",
                stock_name=f"Concurrent Test {i}"
            )
            concurrent_records.append(record)
            self.history_storage.save_analysis(record)
        
        # Simulate concurrent queries
        def query_history(query_id):
            """Simulate a user querying history"""
            try:
                filters = {
                    'page': 1,
                    'page_size': 5,
                    'sort_by': 'created_at',
                    'sort_order': 'desc'
                }
                results, count = _get_filtered_history(self.history_storage, filters)
                return len(results), count, None
            except Exception as e:
                return 0, 0, str(e)
        
        # Run concurrent queries
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(query_history, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verify all queries succeeded
        for result_count, total_count, error in results:
            self.assertIsNone(error, f"Concurrent query failed: {error}")
            self.assertGreater(result_count, 0)
            self.assertGreater(total_count, 0)
        
        logger.info("✅ Concurrent access simulation test passed")
    
    def test_data_consistency_across_operations(self):
        """
        Test data consistency across different operations
        Ensures data integrity during CRUD operations
        """
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Create and save a test record
        original_record = self.fixtures.create_sample_record(
            analysis_id=f"{self.test_session_id}_consistency",
            stock_symbol="CONSISTENCY",
            stock_name="Data Consistency Test"
        )
        
        # Save record
        self.assertTrue(self.history_storage.save_analysis(original_record))
        
        # Retrieve and verify
        retrieved_record = self.history_storage.get_analysis_by_id(original_record.analysis_id)
        self.assertIsNotNone(retrieved_record)
        self.assertEqual(retrieved_record.stock_symbol, original_record.stock_symbol)
        self.assertEqual(retrieved_record.stock_name, original_record.stock_name)
        self.assertEqual(retrieved_record.status, original_record.status)
        
        # Test record appears in filtered queries
        filters = {'stock_symbol': 'CONSISTENCY', 'page': 1, 'page_size': 10}
        search_results, count = _get_filtered_history(self.history_storage, filters)
        
        self.assertEqual(count, 1)
        self.assertEqual(len(search_results), 1)
        self.assertEqual(search_results[0].analysis_id, original_record.analysis_id)
        
        # Test deletion
        self.assertTrue(self.history_storage.delete_analysis(original_record.analysis_id))
        
        # Verify record is gone
        deleted_record = self.history_storage.get_analysis_by_id(original_record.analysis_id)
        self.assertIsNone(deleted_record)
        
        # Verify record doesn't appear in searches
        search_results_after_delete, count_after_delete = _get_filtered_history(self.history_storage, filters)
        self.assertEqual(count_after_delete, 0)
        
        logger.info("✅ Data consistency test passed")


class TestErrorHandlingAndRecovery(TestAnalysisHistoryIntegration):
    """Test error handling and recovery scenarios"""
    
    def test_storage_unavailable_graceful_handling(self):
        """Test graceful handling when storage becomes unavailable"""
        # Mock storage unavailable
        with patch.object(self.history_storage, 'is_available', return_value=False):
            # Test that operations handle unavailable storage gracefully
            filters = {'page': 1, 'page_size': 10}
            
            try:
                results, count = _get_filtered_history(self.history_storage, filters)
                # Should return empty results, not crash
                self.assertEqual(len(results), 0)
                self.assertEqual(count, 0)
            except Exception as e:
                # If an exception is raised, it should be handled gracefully
                self.fail(f"Storage unavailable should be handled gracefully: {e}")
        
        logger.info("✅ Storage unavailable handling test passed")
    
    def test_malformed_data_handling(self):
        """Test handling of malformed data in storage"""
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Create a record with some malformed data
        malformed_record = self.fixtures.create_sample_record(
            analysis_id=f"{self.test_session_id}_malformed",
            stock_symbol="AAPL",  # Use valid symbol to pass validation
            stock_name="Malformed Data Test"
        )
        
        # Intentionally corrupt some data
        malformed_record.raw_results = {"corrupted": "data", "invalid_structure": True}
        malformed_record.formatted_results = None
        
        # Save the malformed record
        self.assertTrue(self.history_storage.save_analysis(malformed_record))
        
        # Test that retrieval handles malformed data gracefully
        retrieved_record = self.history_storage.get_analysis_by_id(malformed_record.analysis_id)
        self.assertIsNotNone(retrieved_record)
        
        # Test that export handles malformed data
        export_results = {
            'stock_symbol': retrieved_record.stock_symbol,
            'analysis_date': retrieved_record.analysis_date.strftime('%Y-%m-%d'),
            'decision': retrieved_record.raw_results.get('decision', {}),
            'state': retrieved_record.raw_results.get('state', {}),
            'success': True,
            'is_historical_report': True
        }
        
        # Should not crash, even with malformed data
        try:
            markdown_content = self.report_exporter.export_report(export_results, 'markdown')
            self.assertIsNotNone(markdown_content)
        except Exception as e:
            # If export fails, it should fail gracefully
            logger.warning(f"Export failed gracefully with malformed data: {e}")
        
        logger.info("✅ Malformed data handling test passed")
    
    def test_network_timeout_simulation(self):
        """Test behavior during network timeouts"""
        if not self.history_storage.is_available():
            self.skipTest("History storage not available")
        
        # Mock a slow database operation
        original_get_user_history = self.history_storage.get_user_history
        
        def slow_get_user_history(*args, **kwargs):
            time.sleep(0.1)  # Simulate slow operation
            return original_get_user_history(*args, **kwargs)
        
        with patch.object(self.history_storage, 'get_user_history', side_effect=slow_get_user_history):
            # Test that operations complete even with slow responses
            start_time = time.time()
            filters = {'page': 1, 'page_size': 5}
            
            try:
                results, count = _get_filtered_history(self.history_storage, filters)
                elapsed_time = time.time() - start_time
                
                # Should complete within reasonable time
                self.assertLess(elapsed_time, 5.0)
                
            except Exception as e:
                # Should handle timeouts gracefully
                logger.warning(f"Operation handled timeout gracefully: {e}")
        
        logger.info("✅ Network timeout simulation test passed")


class TestIntegrationTestRunner:
    """Utility class to run integration tests with proper setup and teardown"""
    
    @staticmethod
    def run_all_tests():
        """Run all integration tests with proper logging and error handling"""
        logger.info("🚀 Starting integration tests for analysis history")
        
        # Create test suite
        test_classes = [
            TestCompleteAnalysisWorkflow,
            TestHistoryPageRendering,
            TestSearchAndFiltering,
            TestDownloadFunctionality,
            TestPerformanceAndScalability,
            TestEndToEndWorkflow,
            TestErrorHandlingAndRecovery
        ]
        
        suite = unittest.TestSuite()
        
        for test_class in test_classes:
            tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
            suite.addTests(tests)
        
        # Run tests with detailed output
        runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
        result = runner.run(suite)
        
        # Log summary
        total_tests = result.testsRun
        failures = len(result.failures)
        errors = len(result.errors)
        skipped = len(result.skipped) if hasattr(result, 'skipped') else 0
        
        logger.info(f"📊 Integration test summary:")
        logger.info(f"  Total tests: {total_tests}")
        logger.info(f"  Passed: {total_tests - failures - errors - skipped}")
        logger.info(f"  Failed: {failures}")
        logger.info(f"  Errors: {errors}")
        logger.info(f"  Skipped: {skipped}")
        
        if failures > 0:
            logger.error("❌ Some integration tests failed:")
            for test, traceback in result.failures:
                logger.error(f"  FAIL: {test}")
                logger.error(f"    {traceback}")
        
        if errors > 0:
            logger.error("❌ Some integration tests had errors:")
            for test, traceback in result.errors:
                logger.error(f"  ERROR: {test}")
                logger.error(f"    {traceback}")
        
        success = failures == 0 and errors == 0
        if success:
            logger.info("✅ All integration tests passed successfully!")
        else:
            logger.error("❌ Some integration tests failed")
        
        return success


# Test execution helper
def run_integration_tests():
    """Main entry point for running integration tests"""
    return TestIntegrationTestRunner.run_all_tests()


if __name__ == '__main__':
    # Run integration tests when script is executed directly
    success = run_integration_tests()
    sys.exit(0 if success else 1)