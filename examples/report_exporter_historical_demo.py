#!/usr/bin/env python3
"""
ReportExporter Historical Data Support Demo

This script demonstrates how the enhanced ReportExporter can handle both
current analysis results and historical data formats.
"""

import sys
import os
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from web.utils.report_exporter import ReportExporter
from web.models.history_models import AnalysisHistoryRecord


def create_sample_current_data():
    """Create sample current analysis results"""
    return {
        'stock_symbol': 'AAPL',
        'decision': {
            'action': '买入',
            'confidence': 0.85,
            'risk_score': 0.25,
            'target_price': 150.0,
            'reasoning': '基于技术分析和基本面分析，建议买入'
        },
        'state': {
            'market_report': '技术分析显示上涨趋势，RSI指标显示超买状态',
            'fundamentals_report': '基本面良好，P/E比率合理，营收增长稳定',
            'news_report': '正面新闻较多，新产品发布获得市场好评',
            'sentiment_report': '市场情绪积极，社交媒体讨论热度高'
        },
        'success': True,
        'analysis_date': datetime(2025, 1, 4, 14, 30, 22),
        'analysts': ['market', 'fundamentals', 'news', 'social'],
        'research_depth': 3,
        'llm_provider': 'dashscope',
        'llm_model': 'qwen-plus'
    }


def create_sample_historical_data():
    """Create sample historical analysis record"""
    record = AnalysisHistoryRecord(
        analysis_id='analysis_20250104_143022_a1b2c3d4',
        stock_symbol='AAPL',
        stock_name='Apple Inc.',
        market_type='美股',
        analysis_date=datetime(2025, 1, 4, 14, 30, 22),
        created_at=datetime(2025, 1, 4, 14, 35, 45),
        status='completed',
        analysis_type='comprehensive',
        analysts_used=['market', 'fundamentals', 'news', 'social'],
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
                'market_report': '技术分析显示上涨趋势，RSI指标显示超买状态',
                'fundamentals_report': '基本面良好，P/E比率合理，营收增长稳定',
                'news_report': '正面新闻较多，新产品发布获得市场好评',
                'sentiment_report': '市场情绪积极，社交媒体讨论热度高'
            },
            'success': True
        }
    )
    return record.to_dict()


def main():
    """Main demonstration function"""
    print("🚀 ReportExporter Historical Data Support Demo")
    print("=" * 50)
    
    # Initialize the exporter
    exporter = ReportExporter()
    
    # Create sample data
    current_data = create_sample_current_data()
    historical_data = create_sample_historical_data()
    
    print("\n📊 Testing Current Analysis Results Format")
    print("-" * 40)
    
    # Test format detection
    is_historical_current = exporter._is_historical_data_format(current_data)
    print(f"Is historical format: {is_historical_current}")
    
    # Generate markdown for current data
    current_markdown = exporter.generate_markdown_report(current_data)
    print(f"Generated markdown length: {len(current_markdown)} characters")
    print(f"Contains '正式分析': {'正式分析' in current_markdown}")
    print(f"Contains '原始创建时间': {'原始创建时间' in current_markdown}")
    
    print("\n📚 Testing Historical Analysis Results Format")
    print("-" * 40)
    
    # Test format detection
    is_historical_historical = exporter._is_historical_data_format(historical_data)
    print(f"Is historical format: {is_historical_historical}")
    
    # Generate markdown for historical data
    historical_markdown = exporter.generate_markdown_report(historical_data)
    print(f"Generated markdown length: {len(historical_markdown)} characters")
    print(f"Contains '历史分析报告': {'历史分析报告' in historical_markdown}")
    print(f"Contains '原始创建时间': {'原始创建时间' in historical_markdown}")
    print(f"Contains '分析ID': {'分析ID' in historical_markdown}")
    print(f"Contains '执行时长': {'执行时长' in historical_markdown}")
    print(f"Contains '分析成本': {'分析成本' in historical_markdown}")
    
    print("\n🔍 Data Extraction Comparison")
    print("-" * 40)
    
    # Extract data from both formats
    current_stock, current_decision, current_state, current_metadata = exporter._extract_current_data(current_data)
    historical_stock, historical_decision, historical_state, historical_metadata = exporter._extract_historical_data(historical_data)
    
    print(f"Current format - Stock: {current_stock}, LLM: {current_metadata.get('llm_provider')}")
    print(f"Historical format - Stock: {historical_stock}, LLM: {historical_metadata.get('llm_provider')}")
    print(f"Historical metadata includes: analysis_id={historical_metadata.get('analysis_id') is not None}, "
          f"execution_time={historical_metadata.get('execution_time')}, "
          f"cost_summary={historical_metadata.get('cost_summary')}")
    
    print("\n💾 Export Testing")
    print("-" * 40)
    
    # Test markdown export for both formats
    current_export = exporter.export_report(current_data, 'markdown')
    historical_export = exporter.export_report(historical_data, 'markdown')
    
    print(f"Current data export successful: {current_export is not None}")
    print(f"Historical data export successful: {historical_export is not None}")
    
    if current_export and historical_export:
        print(f"Current export size: {len(current_export)} bytes")
        print(f"Historical export size: {len(historical_export)} bytes")
    
    print("\n✅ Demo completed successfully!")
    print("\nKey Features Demonstrated:")
    print("- ✅ Automatic detection of data format (current vs historical)")
    print("- ✅ Proper extraction of metadata from both formats")
    print("- ✅ Historical metadata inclusion (analysis ID, execution time, cost)")
    print("- ✅ Backward compatibility with current analysis results")
    print("- ✅ Consistent export functionality for both formats")
    
    # Save sample outputs for inspection
    if current_export and historical_export:
        with open('/tmp/current_analysis_sample.md', 'wb') as f:
            f.write(current_export)
        with open('/tmp/historical_analysis_sample.md', 'wb') as f:
            f.write(historical_export)
        print(f"\n📁 Sample files saved:")
        print(f"- Current format: /tmp/current_analysis_sample.md")
        print(f"- Historical format: /tmp/historical_analysis_sample.md")


if __name__ == '__main__':
    main()