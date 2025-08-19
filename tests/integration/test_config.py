#!/usr/bin/env python3
"""
Integration Test Configuration

This module provides configuration and utilities for integration tests,
including test data generation, mock services, and test environment setup.
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Test configuration constants
TEST_CONFIG = {
    # Database settings
    'test_db_name': 'tradingagents_test',
    'test_collection_name': 'analysis_history_test',
    
    # Test data settings
    'large_dataset_size': 100,
    'performance_test_size': 50,
    'concurrent_users': 5,
    
    # Timeout settings
    'query_timeout': 10.0,
    'export_timeout': 30.0,
    'analysis_timeout': 60.0,
    
    # Performance thresholds
    'max_query_time': 5.0,
    'max_save_time_per_record': 1.0,
    'max_export_time': 15.0,
    
    # Test data patterns
    'test_symbols': {
        'us_stocks': ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'META', 'NVDA'],
        'a_shares': ['000001', '000002', '600036', '600519', '000858', '002415'],
        'hk_stocks': ['0700.HK', '0941.HK', '1299.HK', '2318.HK', '0005.HK']
    },
    
    'test_names': {
        'us_stocks': ['Apple Inc.', 'Alphabet Inc.', 'Microsoft Corp.', 'Tesla Inc.', 'Amazon.com Inc.', 'Meta Platforms', 'NVIDIA Corp.'],
        'a_shares': ['平安银行', '万科A', '招商银行', '贵州茅台', '五粮液', '三一重工'],
        'hk_stocks': ['腾讯控股', '中国移动', '友邦保险', '中国平安', '汇丰控股']
    }
}


class TestDataGenerator:
    """Generate test data for integration tests"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.record_counter = 0
    
    def generate_comprehensive_dataset(self, size: int = 20) -> List[Dict[str, Any]]:
        """Generate a comprehensive dataset covering various scenarios"""
        from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus, MarketType
        
        records = []
        
        # Generate records for each market type
        markets = [
            (MarketType.US_STOCK.value, TEST_CONFIG['test_symbols']['us_stocks'], TEST_CONFIG['test_names']['us_stocks']),
            (MarketType.A_SHARE.value, TEST_CONFIG['test_symbols']['a_shares'], TEST_CONFIG['test_names']['a_shares']),
            (MarketType.HK_STOCK.value, TEST_CONFIG['test_symbols']['hk_stocks'], TEST_CONFIG['test_names']['hk_stocks'])
        ]
        
        statuses = [AnalysisStatus.COMPLETED.value, AnalysisStatus.FAILED.value, AnalysisStatus.IN_PROGRESS.value]
        analysts_combinations = [
            ['market'],
            ['market', 'fundamentals'],
            ['market', 'fundamentals', 'news'],
            ['market', 'fundamentals', 'news', 'social']
        ]
        
        for i in range(size):
            market_type, symbols, names = markets[i % len(markets)]
            symbol = symbols[i % len(symbols)]
            name = names[i % len(names)]
            status = statuses[i % len(statuses)]
            analysts = analysts_combinations[i % len(analysts_combinations)]
            
            record = AnalysisHistoryRecord(
                analysis_id=f"{self.session_id}_{self.record_counter:04d}",
                stock_symbol=symbol,
                stock_name=name,
                market_type=market_type,
                analysis_date=datetime.now() - timedelta(days=i % 90),
                status=status,
                analysis_type="comprehensive",
                analysts_used=analysts,
                research_depth=(i % 5) + 1,
                llm_provider="dashscope" if i % 2 == 0 else "deepseek",
                llm_model="qwen-plus" if i % 2 == 0 else "deepseek-chat",
                execution_time=60.0 + (i * 10) % 300,
                token_usage={
                    "input_tokens": 1500 + (i * 100) % 5000,
                    "output_tokens": 800 + (i * 50) % 2000,
                    "total_cost": 0.03 + (i * 0.01) % 0.20
                },
                raw_results=self._generate_mock_analysis_results(symbol, status),
                formatted_results=self._generate_mock_formatted_results(symbol, status),
                metadata={
                    "session_id": f"{self.session_id}_{i}",
                    "test_record": True,
                    "test_batch": self.session_id,
                    "record_index": i
                }
            )
            
            records.append(record)
            self.record_counter += 1
        
        return records
    
    def _generate_mock_analysis_results(self, symbol: str, status: str) -> Dict[str, Any]:
        """Generate mock analysis results"""
        if status == AnalysisStatus.COMPLETED.value:
            return {
                "stock_symbol": symbol,
                "decision": {
                    "action": "BUY" if hash(symbol) % 3 == 0 else "HOLD" if hash(symbol) % 3 == 1 else "SELL",
                    "confidence": 0.6 + (hash(symbol) % 40) / 100,
                    "target_price": 100.0 + (hash(symbol) % 200),
                    "reasoning": f"Analysis indicates {symbol} shows strong potential"
                },
                "state": {
                    "market_report": f"Technical analysis for {symbol} shows positive trends",
                    "fundamentals_report": f"Fundamental analysis of {symbol} reveals solid metrics",
                    "news_report": f"Recent news for {symbol} is generally positive",
                    "risk_assessment": f"Risk assessment for {symbol} indicates moderate risk"
                },
                "success": True
            }
        else:
            return {
                "stock_symbol": symbol,
                "decision": {},
                "state": {},
                "success": False,
                "error": "Analysis failed due to data unavailability"
            }
    
    def _generate_mock_formatted_results(self, symbol: str, status: str) -> Dict[str, Any]:
        """Generate mock formatted results"""
        if status == AnalysisStatus.COMPLETED.value:
            return {
                "stock_symbol": symbol,
                "decision": {
                    "action": "买入" if hash(symbol) % 3 == 0 else "持有" if hash(symbol) % 3 == 1 else "卖出",
                    "confidence": 0.6 + (hash(symbol) % 40) / 100,
                    "target_price": 100.0 + (hash(symbol) % 200),
                    "reasoning": f"分析显示{symbol}具有强劲潜力"
                },
                "state": {
                    "market_report": f"{symbol}的技术分析显示积极趋势",
                    "fundamentals_report": f"{symbol}的基本面分析显示稳健指标",
                    "news_report": f"{symbol}的最新消息总体积极",
                    "risk_assessment": f"{symbol}的风险评估显示中等风险"
                },
                "metadata": {
                    "analysis_complete": True,
                    "formatted_at": datetime.now().isoformat()
                }
            }
        else:
            return {
                "stock_symbol": symbol,
                "error": "分析失败，数据不可用",
                "metadata": {
                    "analysis_complete": False,
                    "error_type": "data_unavailable"
                }
            }


class MockAnalysisRunner:
    """Mock analysis runner for testing without actual LLM calls"""
    
    def __init__(self):
        self.call_count = 0
        self.should_fail = False
        self.failure_rate = 0.1  # 10% failure rate
    
    def mock_run_stock_analysis(self, **kwargs):
        """Mock implementation of run_stock_analysis"""
        self.call_count += 1
        
        # Simulate occasional failures
        if self.should_fail or (hash(kwargs.get('stock_symbol', '')) % 10 < self.failure_rate * 10):
            return {
                'success': False,
                'error': 'Mock analysis failure',
                'stock_symbol': kwargs.get('stock_symbol'),
                'analysis_date': kwargs.get('analysis_date'),
                'session_id': f"mock_session_{self.call_count}"
            }
        
        # Simulate successful analysis
        return {
            'success': True,
            'stock_symbol': kwargs.get('stock_symbol'),
            'analysis_date': kwargs.get('analysis_date'),
            'analysts': kwargs.get('analysts', []),
            'research_depth': kwargs.get('research_depth', 3),
            'llm_provider': kwargs.get('llm_provider', 'dashscope'),
            'llm_model': kwargs.get('llm_model', 'qwen-plus'),
            'state': {
                'market_report': f"Mock technical analysis for {kwargs.get('stock_symbol')}",
                'fundamentals_report': f"Mock fundamental analysis for {kwargs.get('stock_symbol')}",
                'news_report': f"Mock news analysis for {kwargs.get('stock_symbol')}"
            },
            'decision': {
                'action': 'BUY',
                'confidence': 0.75,
                'target_price': 150.0,
                'reasoning': 'Mock analysis reasoning'
            },
            'session_id': f"mock_session_{self.call_count}"
        }


class TestEnvironmentManager:
    """Manage test environment setup and cleanup"""
    
    def __init__(self):
        self.temp_dirs = []
        self.test_records = []
        self.original_env = {}
    
    def setup_test_environment(self):
        """Set up test environment"""
        # Create temporary directories
        temp_dir = tempfile.mkdtemp(prefix='tradingagents_test_')
        self.temp_dirs.append(temp_dir)
        
        # Set test environment variables
        test_env_vars = {
            'TRADINGAGENTS_TEST_MODE': 'true',
            'TRADINGAGENTS_TEST_DATA_DIR': temp_dir,
            'MONGODB_TEST_DB': TEST_CONFIG['test_db_name']
        }
        
        for key, value in test_env_vars.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        return temp_dir
    
    def cleanup_test_environment(self):
        """Clean up test environment"""
        # Restore original environment variables
        for key, original_value in self.original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value
        
        # Clean up temporary directories
        import shutil
        for temp_dir in self.temp_dirs:
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Warning: Failed to clean up temp dir {temp_dir}: {e}")
        
        self.temp_dirs.clear()
    
    def __enter__(self):
        return self.setup_test_environment()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_test_environment()


def get_test_config() -> Dict[str, Any]:
    """Get test configuration"""
    return TEST_CONFIG.copy()


def create_test_data_generator(session_id: str) -> TestDataGenerator:
    """Create a test data generator"""
    return TestDataGenerator(session_id)


def create_mock_analysis_runner() -> MockAnalysisRunner:
    """Create a mock analysis runner"""
    return MockAnalysisRunner()


def create_test_environment_manager() -> TestEnvironmentManager:
    """Create a test environment manager"""
    return TestEnvironmentManager()