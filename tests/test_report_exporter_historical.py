#!/usr/bin/env python3
"""
Test ReportExporter with Historical Data Support

This test verifies that the ReportExporter can handle both current analysis results
and historical data formats correctly.
"""

import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from web.utils.report_exporter import ReportExporter
from web.models.history_models import AnalysisHistoryRecord


class TestReportExporterHistorical(unittest.TestCase):
    """Test ReportExporter with historical data support"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.exporter = ReportExporter()
        
        # Mock current analysis results format
        self.current_results = {
            'stock_symbol': 'AAPL',
            'decision': {
                'action': '买入',
                'confidence': 0.85,
                'risk_score': 0.25,
                'target_price': 150.0,
                'reasoning': '基于技术分析和基本面分析，建议买入'
            },
            'state': {
                'market_report': '技术分析显示上涨趋势',
                'fundamentals_report': '基本面良好',
                'news_report': '正面新闻较多',
                'sentiment_report': '市场情绪积极'
            },
            'success': True,
            'analysis_date': datetime(2025, 1, 4, 14, 30, 22),
            'analysts': ['market', 'fundamentals', 'news'],
            'research_depth': 3,
            'llm_provider': 'dashscope',
            'llm_model': 'qwen-plus'
        }
        
        # Mock historical data format (from AnalysisHistoryRecord)
        self.historical_results = {
            'analysis_id': 'analysis_20250104_143022_a1b2c3d4',
            'stock_symbol': 'AAPL',
            'stock_name': 'Apple Inc.',
            'market_type': '美股',
            'analysis_date': datetime(2025, 1, 4, 14, 30, 22),
            'created_at': datetime(2025, 1, 4, 14, 35, 45),
            'status': 'completed',
            'analysis_type': 'comprehensive',
            'analysts_used': ['market', 'fundamentals', 'news'],
            'research_depth': 3,
            'llm_provider': 'dashscope',
            'llm_model': 'qwen-plus',
            'execution_time': 245.67,
            'token_usage': {
                'input_tokens': 8500,
                'output_tokens': 3200,
                'total_cost': 0.0234
            },
            'formatted_results': {
                'stock_symbol': 'AAPL',
                'decision': {
                    'action': '买入',
                    'confidence': 0.85,
                    'risk_score': 0.25,
                    'target_price': 150.0,
                    'reasoning': '基于技术分析和基本面分析，建议买入'
                },
                'state': {
                    'market_report': '技术分析显示上涨趋势',
                    'fundamentals_report': '基本面良好',
                    'news_report': '正面新闻较多',
                    'sentiment_report': '市场情绪积极'
                },
                'success': True
            },
            'raw_results': {
                'stock_symbol': 'AAPL',
                'decision': {'action': 'BUY'},
                'state': {},
                'success': True
            }
        }
    
    def test_is_historical_data_format_detection(self):
        """Test detection of historical vs current data formats"""
        
        # Test current format detection
        self.assertFalse(self.exporter._is_historical_data_format(self.current_results))
        
        # Test historical format detection
        self.assertTrue(self.exporter._is_historical_data_format(self.historical_results))
        
        # Test edge cases
        self.assertFalse(self.exporter._is_historical_data_format({}))
        self.assertFalse(self.exporter._is_historical_data_format({'stock_symbol': 'AAPL'}))
    
    def test_extract_historical_data(self):
        """Test extraction of data from historical format"""
        
        stock_symbol, decision, state, metadata = self.exporter._extract_historical_data(self.historical_results)
        
        # Verify extracted data
        self.assertEqual(stock_symbol, 'AAPL')
        self.assertEqual(decision['action'], '买入')
        self.assertEqual(decision['confidence'], 0.85)
        self.assertIn('market_report', state)
        
        # Verify metadata
        self.assertEqual(metadata['analysis_id'], 'analysis_20250104_143022_a1b2c3d4')
        self.assertEqual(metadata['llm_provider'], 'dashscope')
        self.assertEqual(metadata['llm_model'], 'qwen-plus')
        self.assertEqual(metadata['analysts'], ['market', 'fundamentals', 'news'])
        self.assertEqual(metadata['research_depth'], 3)
        self.assertEqual(metadata['execution_time'], 245.67)
        self.assertEqual(metadata['market_type'], '美股')
        self.assertEqual(metadata['cost_summary'], '¥0.02')
    
    def test_extract_current_data(self):
        """Test extraction of data from current format"""
        
        stock_symbol, decision, state, metadata = self.exporter._extract_current_data(self.current_results)
        
        # Verify extracted data
        self.assertEqual(stock_symbol, 'AAPL')
        self.assertEqual(decision['action'], '买入')
        self.assertEqual(decision['confidence'], 0.85)
        self.assertIn('market_report', state)
        
        # Verify metadata
        self.assertEqual(metadata['llm_provider'], 'dashscope')
        self.assertEqual(metadata['llm_model'], 'qwen-plus')
        self.assertEqual(metadata['analysts'], ['market', 'fundamentals', 'news'])
        self.assertEqual(metadata['research_depth'], 3)
    
    def test_generate_markdown_report_current_format(self):
        """Test Markdown generation with current analysis results"""
        
        markdown = self.exporter.generate_markdown_report(self.current_results)
        
        # Verify content
        self.assertIn('AAPL 股票分析报告', markdown)
        self.assertIn('正式分析', markdown)
        self.assertIn('买入', markdown)
        self.assertIn('85.0%', markdown)  # confidence
        self.assertIn('25.0%', markdown)  # risk_score
        self.assertIn('150.0', markdown)  # target_price
        self.assertIn('dashscope', markdown)
        self.assertIn('qwen-plus', markdown)
        self.assertIn('技术分析显示上涨趋势', markdown)
    
    def test_generate_markdown_report_historical_format(self):
        """Test Markdown generation with historical data"""
        
        markdown = self.exporter.generate_markdown_report(self.historical_results)
        
        # Verify content
        self.assertIn('AAPL 股票分析报告', markdown)
        self.assertIn('历史分析报告', markdown)
        self.assertIn('买入', markdown)
        self.assertIn('85.0%', markdown)  # confidence
        self.assertIn('25.0%', markdown)  # risk_score
        self.assertIn('150.0', markdown)  # target_price
        self.assertIn('dashscope', markdown)
        self.assertIn('qwen-plus', markdown)
        
        # Verify historical-specific content
        self.assertIn('原始创建时间', markdown)
        self.assertIn('分析ID', markdown)
        self.assertIn('analysis_20250104_143022_a1b2c3d4', markdown)
        self.assertIn('4分5.7秒', markdown)  # execution time
        self.assertIn('¥0.02', markdown)  # cost
        self.assertIn('美股', markdown)  # market type
        
        # Verify timestamp uses analysis_date
        self.assertIn('2025-01-04 14:30:22', markdown)
    
    def test_markdown_report_with_missing_historical_fields(self):
        """Test Markdown generation with incomplete historical data"""
        
        # Create historical data with missing fields
        incomplete_historical = self.historical_results.copy()
        del incomplete_historical['token_usage']
        del incomplete_historical['execution_time']
        incomplete_historical['formatted_results'] = {
            'stock_symbol': 'AAPL',
            'decision': {'action': '持有'},
            'state': {}
        }
        
        markdown = self.exporter.generate_markdown_report(incomplete_historical)
        
        # Should still generate valid markdown
        self.assertIn('AAPL 股票分析报告', markdown)
        self.assertIn('历史分析报告', markdown)
        self.assertIn('持有', markdown)
        
        # Should handle missing fields gracefully
        self.assertNotIn('执行时长', markdown)
        self.assertNotIn('分析成本', markdown)
    
    @patch('web.utils.report_exporter.pypandoc')
    def test_docx_generation_with_historical_data(self, mock_pypandoc):
        """Test Word document generation with historical data"""
        
        # Mock pypandoc
        mock_pypandoc.get_pandoc_version.return_value = "2.19.2"
        mock_pypandoc.convert_text.return_value = None
        
        # Mock file operations
        with patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024), \
             patch('builtins.open', create=True) as mock_open:
            
            mock_temp.return_value.__enter__.return_value.name = '/tmp/test.docx'
            mock_open.return_value.__enter__.return_value.read.return_value = b'fake docx content'
            
            # Set pandoc availability
            self.exporter.pandoc_available = True
            
            result = self.exporter.generate_docx_report(self.historical_results)
            
            # Verify result
            self.assertEqual(result, b'fake docx content')
            
            # Verify pypandoc was called with cleaned content
            mock_pypandoc.convert_text.assert_called_once()
            args, kwargs = mock_pypandoc.convert_text.call_args
            
            # Verify the markdown content includes historical information
            markdown_content = args[0]
            self.assertIn('历史分析报告', markdown_content)
            self.assertIn('原始创建时间', markdown_content)
    
    def test_cost_summary_formatting(self):
        """Test different cost summary formats"""
        
        # Test free analysis
        free_results = self.historical_results.copy()
        free_results['token_usage'] = {'total_cost': 0}
        
        _, _, _, metadata = self.exporter._extract_historical_data(free_results)
        self.assertEqual(metadata['cost_summary'], '免费分析')
        
        # Test small cost
        small_cost_results = self.historical_results.copy()
        small_cost_results['token_usage'] = {'total_cost': 0.0056}
        
        _, _, _, metadata = self.exporter._extract_historical_data(small_cost_results)
        self.assertEqual(metadata['cost_summary'], '¥0.0056')
        
        # Test larger cost
        large_cost_results = self.historical_results.copy()
        large_cost_results['token_usage'] = {'total_cost': 1.234}
        
        _, _, _, metadata = self.exporter._extract_historical_data(large_cost_results)
        self.assertEqual(metadata['cost_summary'], '¥1.23')
    
    def test_execution_time_formatting(self):
        """Test execution time formatting in different units"""
        
        # Test seconds
        short_results = self.historical_results.copy()
        short_results['execution_time'] = 45.5
        
        markdown = self.exporter.generate_markdown_report(short_results)
        self.assertIn('45.5秒', markdown)
        
        # Test minutes and seconds
        long_results = self.historical_results.copy()
        long_results['execution_time'] = 125.7  # 2 minutes 5.7 seconds
        
        markdown = self.exporter.generate_markdown_report(long_results)
        self.assertIn('2分5.7秒', markdown)


if __name__ == '__main__':
    unittest.main()