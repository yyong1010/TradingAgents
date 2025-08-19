#!/usr/bin/env python3
"""
Integration test for ReportExporter with actual historical data

This test verifies that the ReportExporter works correctly with real
historical data from the analysis history system.
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


class TestReportExporterIntegration(unittest.TestCase):
    """Integration test for ReportExporter with historical data"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.exporter = ReportExporter()
        
        # Create a realistic historical record
        self.history_record = AnalysisHistoryRecord(
            analysis_id='analysis_20250104_143022_a1b2c3d4',
            stock_symbol='AAPL',
            stock_name='Apple Inc.',
            market_type='美股',
            analysis_date=datetime(2025, 1, 4, 14, 30, 22),
            created_at=datetime(2025, 1, 4, 14, 35, 45),
            status='completed',
            analysis_type='comprehensive',
            analysts_used=['market', 'fundamentals', 'news'],
            research_depth=3,
            llm_provider='dashscope',
            llm_model='qwen-plus',
            execution_time=245.67,
            token_usage={
                'input_tokens': 8500,
                'output_tokens': 3200,
                'total_cost': 0.0234
            },
            raw_results={
                'stock_symbol': 'AAPL',
                'decision': {'action': 'BUY'},
                'state': {},
                'success': True
            },
            formatted_results={
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
            }
        )
    
    def test_export_historical_record_as_markdown(self):
        """Test exporting a historical record as Markdown"""
        
        # Convert record to dictionary format
        historical_data = self.history_record.to_dict()
        
        # Generate markdown report
        markdown = self.exporter.generate_markdown_report(historical_data)
        
        # Verify the report contains expected content
        self.assertIn('AAPL 股票分析报告', markdown)
        self.assertIn('历史分析报告', markdown)
        self.assertIn('买入', markdown)
        self.assertIn('原始创建时间', markdown)
        self.assertIn('分析ID', markdown)
        self.assertIn('analysis_20250104_143022_a1b2c3d4', markdown)
        self.assertIn('4分5.7秒', markdown)
        self.assertIn('¥0.02', markdown)
        self.assertIn('美股', markdown)
        
        # Verify analysis content
        self.assertIn('技术分析显示上涨趋势', markdown)
        self.assertIn('基本面良好', markdown)
        self.assertIn('正面新闻较多', markdown)
        self.assertIn('市场情绪积极', markdown)
    
    def test_export_report_method_with_historical_data(self):
        """Test the main export_report method with historical data"""
        
        # Convert record to dictionary format
        historical_data = self.history_record.to_dict()
        
        # Test markdown export
        result = self.exporter.export_report(historical_data, 'markdown')
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        
        # Decode and verify content
        markdown_content = result.decode('utf-8')
        self.assertIn('AAPL 股票分析报告', markdown_content)
        self.assertIn('历史分析报告', markdown_content)
    
    @patch('web.utils.report_exporter.pypandoc')
    def test_docx_generation_with_historical_data(self, mock_pypandoc):
        """Test Word document generation with historical data (direct method call)"""
        
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
            
            # Convert record to dictionary format
            historical_data = self.history_record.to_dict()
            
            # Test direct docx generation (bypassing UI components)
            result = self.exporter.generate_docx_report(historical_data)
            
            self.assertIsNotNone(result)
            self.assertEqual(result, b'fake docx content')
            
            # Verify pypandoc was called with historical content
            mock_pypandoc.convert_text.assert_called_once()
            args, kwargs = mock_pypandoc.convert_text.call_args
            
            # Verify the markdown content includes historical information
            markdown_content = args[0]
            self.assertIn('历史分析报告', markdown_content)
            self.assertIn('原始创建时间', markdown_content)
    
    def test_filename_generation_with_historical_data(self):
        """Test that filenames include historical analysis date"""
        
        # This test simulates the filename generation logic in render_export_buttons
        historical_data = self.history_record.to_dict()
        
        # Test the detection and extraction logic
        is_historical = self.exporter._is_historical_data_format(historical_data)
        self.assertTrue(is_historical)
        
        if is_historical:
            stock_symbol, _, _, metadata = self.exporter._extract_historical_data(historical_data)
            analysis_date = metadata.get('analysis_date')
            
            self.assertEqual(stock_symbol, 'AAPL')
            self.assertIsInstance(analysis_date, datetime)
            
            # Verify the timestamp would be from the analysis date
            timestamp = analysis_date.strftime('%Y%m%d_%H%M%S')
            self.assertEqual(timestamp, '20250104_143022')
    
    def test_backward_compatibility_with_current_format(self):
        """Test that the exporter still works with current analysis format"""
        
        # Create current format data
        current_data = {
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
                'fundamentals_report': '基本面良好'
            },
            'success': True,
            'analysis_date': datetime(2025, 1, 4, 14, 30, 22),
            'analysts': ['market', 'fundamentals'],
            'research_depth': 3,
            'llm_provider': 'dashscope',
            'llm_model': 'qwen-plus'
        }
        
        # Should be detected as current format
        is_historical = self.exporter._is_historical_data_format(current_data)
        self.assertFalse(is_historical)
        
        # Should still generate valid markdown
        markdown = self.exporter.generate_markdown_report(current_data)
        
        self.assertIn('AAPL 股票分析报告', markdown)
        self.assertIn('正式分析', markdown)  # Not historical
        self.assertIn('买入', markdown)
        self.assertNotIn('原始创建时间', markdown)  # No historical metadata
        self.assertNotIn('分析ID', markdown)


if __name__ == '__main__':
    unittest.main()