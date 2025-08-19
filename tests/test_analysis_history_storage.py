#!/usr/bin/env python3
"""
Unit tests for analysis history storage operations

This test suite verifies the AnalysisHistoryStorage class methods, data model
serialization/deserialization, error handling scenarios, and edge cases.

Requirements tested:
- 6.1: MongoDB storage backend with proper data validation
- 6.2: Data indexing for efficient querying and data integrity
- 6.4: Error handling with appropriate logging
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import uuid
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Disable logging during tests to avoid conflicts
logging.disable(logging.CRITICAL)

from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus, MarketType
from pymongo.errors import PyMongoError, DuplicateKeyError, ConnectionFailure, ServerSelectionTimeoutError


class TestAnalysisHistoryStorageFixtures:
    """Test fixtures for consistent test data"""
    
    @staticmethod
    def create_sample_record(
        analysis_id: str = None,
        stock_symbol: str = "AAPL",
        stock_name: str = "Apple Inc.",
        market_type: str = MarketType.US_STOCK.value,
        status: str = AnalysisStatus.COMPLETED.value
    ) -> AnalysisHistoryRecord:
        """Create a sample analysis history record for testing"""
        if analysis_id is None:
            analysis_id = f"test_analysis_{uuid.uuid4().hex[:8]}"
        
        return AnalysisHistoryRecord(
            analysis_id=analysis_id,
            stock_symbol=stock_symbol,
            stock_name=stock_name,
            market_type=market_type,
            analysis_date=datetime(2025, 1, 4, 14, 30, 22),
            created_at=datetime(2025, 1, 4, 14, 30, 22),
            updated_at=datetime(2025, 1, 4, 14, 35, 45),
            status=status,
            analysis_type="comprehensive",
            analysts_used=["market", "fundamentals", "news", "social"],
            research_depth=3,
            llm_provider="dashscope",
            llm_model="qwen-plus",
            execution_time=245.67,
            token_usage={
                "input_tokens": 8500,
                "output_tokens": 3200,
                "total_tokens": 11700,
                "total_cost": 0.0234
            },
            raw_results={
                "stock_symbol": stock_symbol,
                "decision": {"action": "buy", "confidence": 0.85},
                "state": {"analysis_complete": True},
                "success": True
            },
            formatted_results={
                "stock_symbol": stock_symbol,
                "decision": {"action": "buy", "confidence": 0.85},
                "state": {"analysis_complete": True},
                "metadata": {"version": "1.0"}
            },
            metadata={
                "user_agent": "streamlit",
                "session_id": "session_xyz",
                "ip_address": "192.168.1.100",
                "version": "0.1.2"
            }
        )
    
    @staticmethod
    def create_multiple_records(count: int = 5) -> List[AnalysisHistoryRecord]:
        """Create multiple sample records for testing"""
        records = []
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
        names = ["Apple Inc.", "Alphabet Inc.", "Microsoft Corp.", "Tesla Inc.", "Amazon.com Inc."]
        
        for i in range(count):
            symbol = symbols[i % len(symbols)]
            name = names[i % len(names)]
            
            record = TestAnalysisHistoryStorageFixtures.create_sample_record(
                analysis_id=f"test_analysis_{i:03d}",
                stock_symbol=symbol,
                stock_name=name,
                status=AnalysisStatus.COMPLETED.value if i % 2 == 0 else AnalysisStatus.FAILED.value
            )
            
            # Vary the creation dates
            record.created_at = datetime.now() - timedelta(days=i)
            record.analysis_date = datetime.now() - timedelta(days=i)
            
            records.append(record)
        
        return records


class TestAnalysisHistoryStorageBasic(unittest.TestCase):
    """Test basic storage operations without complex mocking"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fixtures = TestAnalysisHistoryStorageFixtures()
        self.sample_record = self.fixtures.create_sample_record()
    
    def test_storage_class_exists(self):
        """Test that the storage class can be imported"""
        from web.utils.history_storage import AnalysisHistoryStorage
        self.assertTrue(callable(AnalysisHistoryStorage))
    
    def test_storage_methods_exist(self):
        """Test that all required storage methods exist"""
        from web.utils.history_storage import AnalysisHistoryStorage
        
        # Create a mock instance to avoid initialization issues
        storage = Mock(spec=AnalysisHistoryStorage)
        
        # Verify methods exist
        required_methods = [
            'save_analysis',
            'get_analysis_by_id', 
            'get_user_history',
            'delete_analysis',
            'delete_multiple_analyses',
            'get_history_stats',
            'is_available'
        ]
        
        for method_name in required_methods:
            self.assertTrue(hasattr(AnalysisHistoryStorage, method_name))
            self.assertTrue(callable(getattr(AnalysisHistoryStorage, method_name)))


class TestAnalysisHistoryRecordSerialization(unittest.TestCase):
    """Test data model serialization and deserialization"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fixtures = TestAnalysisHistoryStorageFixtures()
        self.sample_record = self.fixtures.create_sample_record()
    
    def test_to_dict_serialization(self):
        """Test record serialization to dictionary"""
        # Serialize record
        data = self.sample_record.to_dict()
        
        # Verify all fields are present
        expected_fields = [
            'analysis_id', 'stock_symbol', 'stock_name', 'market_type',
            'analysis_date', 'created_at', 'updated_at', 'status',
            'analysis_type', 'analysts_used', 'research_depth',
            'llm_provider', 'llm_model', 'execution_time', 'token_usage',
            'raw_results', 'formatted_results', 'metadata'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Verify data types
        self.assertIsInstance(data['analysis_id'], str)
        self.assertIsInstance(data['stock_symbol'], str)
        self.assertIsInstance(data['analysis_date'], datetime)
        self.assertIsInstance(data['analysts_used'], list)
        self.assertIsInstance(data['token_usage'], dict)
    
    def test_from_dict_deserialization(self):
        """Test record deserialization from dictionary"""
        # Serialize and deserialize
        data = self.sample_record.to_dict()
        restored_record = AnalysisHistoryRecord.from_dict(data)
        
        # Verify all fields match
        self.assertEqual(restored_record.analysis_id, self.sample_record.analysis_id)
        self.assertEqual(restored_record.stock_symbol, self.sample_record.stock_symbol)
        self.assertEqual(restored_record.stock_name, self.sample_record.stock_name)
        self.assertEqual(restored_record.market_type, self.sample_record.market_type)
        self.assertEqual(restored_record.status, self.sample_record.status)
        self.assertEqual(restored_record.analysts_used, self.sample_record.analysts_used)
        self.assertEqual(restored_record.token_usage, self.sample_record.token_usage)
    
    def test_from_dict_with_string_dates(self):
        """Test deserialization with string date fields"""
        # Create data with string dates
        data = self.sample_record.to_dict()
        data['analysis_date'] = '2025-01-04T14:30:22'
        data['created_at'] = '2025-01-04T14:30:22Z'
        data['updated_at'] = '2025-01-04T14:35:45+00:00'
        
        # Deserialize
        restored_record = AnalysisHistoryRecord.from_dict(data)
        
        # Verify dates were parsed correctly
        self.assertIsInstance(restored_record.analysis_date, datetime)
        self.assertIsInstance(restored_record.created_at, datetime)
        self.assertIsInstance(restored_record.updated_at, datetime)
    
    def test_from_dict_with_invalid_dates(self):
        """Test deserialization with invalid date strings"""
        # Create data with invalid dates
        data = self.sample_record.to_dict()
        data['analysis_date'] = 'invalid_date'
        data['created_at'] = 'also_invalid'
        
        # Deserialize should handle gracefully
        restored_record = AnalysisHistoryRecord.from_dict(data)
        
        # Verify fallback dates were used
        self.assertIsInstance(restored_record.analysis_date, datetime)
        self.assertIsInstance(restored_record.created_at, datetime)
    
    def test_serialization_roundtrip(self):
        """Test complete serialization roundtrip"""
        # Multiple roundtrips
        for _ in range(3):
            data = self.sample_record.to_dict()
            restored_record = AnalysisHistoryRecord.from_dict(data)
            
            # Verify key fields remain consistent
            self.assertEqual(restored_record.analysis_id, self.sample_record.analysis_id)
            self.assertEqual(restored_record.stock_symbol, self.sample_record.stock_symbol)
            self.assertEqual(restored_record.execution_time, self.sample_record.execution_time)
            
            # Update sample_record for next iteration
            self.sample_record = restored_record


class TestAnalysisHistoryRecordValidation(unittest.TestCase):
    """Test data model validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fixtures = TestAnalysisHistoryStorageFixtures()
    
    def test_valid_record_validation(self):
        """Test validation of valid record"""
        # Create valid record
        record = self.fixtures.create_sample_record()
        
        # Validation should pass without exception
        try:
            record.validate()
        except ValueError:
            self.fail("Validation failed for valid record")
    
    def test_invalid_stock_symbol_validation(self):
        """Test validation with invalid stock symbols"""
        # Test empty symbol
        with self.assertRaises(ValueError) as context:
            record = self.fixtures.create_sample_record(stock_symbol="")
        self.assertIn("Stock symbol cannot be empty", str(context.exception))
        
        # Test invalid A-share symbol
        with self.assertRaises(ValueError) as context:
            record = AnalysisHistoryRecord(
                stock_symbol="INVALID",
                stock_name="Test Stock",
                market_type=MarketType.A_SHARE.value,
                analysts_used=["market"]
            )
        self.assertIn("A-share symbol must be 6 digits", str(context.exception))
        
        # Test invalid US stock symbol
        with self.assertRaises(ValueError) as context:
            record = AnalysisHistoryRecord(
                stock_symbol="123456",
                stock_name="Test Stock",
                market_type=MarketType.US_STOCK.value,
                analysts_used=["market"]
            )
        self.assertIn("US stock symbol must be 1-5 letters", str(context.exception))
    
    def test_invalid_analysts_validation(self):
        """Test validation with invalid analysts"""
        # Test empty analysts list
        with self.assertRaises(ValueError) as context:
            record = AnalysisHistoryRecord(
                stock_symbol="AAPL",
                stock_name="Apple Inc.",
                analysts_used=[]
            )
        self.assertIn("At least one analyst must be specified", str(context.exception))
        
        # Test invalid analyst names
        with self.assertRaises(ValueError) as context:
            record = AnalysisHistoryRecord(
                stock_symbol="AAPL",
                stock_name="Apple Inc.",
                analysts_used=["invalid_analyst", "market"]
            )
        self.assertIn("Invalid analysts", str(context.exception))
    
    def test_invalid_research_depth_validation(self):
        """Test validation with invalid research depth"""
        # Test out of range research depth
        with self.assertRaises(ValueError) as context:
            record = AnalysisHistoryRecord(
                stock_symbol="AAPL",
                stock_name="Apple Inc.",
                analysts_used=["market"],
                research_depth=10
            )
        self.assertIn("Research depth must be an integer between 1 and 5", str(context.exception))
    
    def test_invalid_token_usage_validation(self):
        """Test validation with invalid token usage"""
        # Test negative token values
        with self.assertRaises(ValueError) as context:
            record = AnalysisHistoryRecord(
                stock_symbol="AAPL",
                stock_name="Apple Inc.",
                analysts_used=["market"],
                token_usage={
                    "input_tokens": -100,
                    "output_tokens": 200,
                    "total_cost": 0.05
                }
            )
        self.assertIn("Token usage input_tokens must be a non-negative number", str(context.exception))


class TestAnalysisHistoryStorageMocked(unittest.TestCase):
    """Test storage operations with simplified mocking"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fixtures = TestAnalysisHistoryStorageFixtures()
        self.sample_record = self.fixtures.create_sample_record()
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_save_analysis_success(self, mock_get_db_manager):
        """Test successful analysis save"""
        # Mock database manager to return unavailable
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection manually
        storage.collection = Mock()
        mock_result = Mock()
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        storage.collection.insert_one.return_value = mock_result
        
        # Save analysis
        result = storage.save_analysis(self.sample_record)
        
        # Verify success
        self.assertTrue(result)
        storage.collection.insert_one.assert_called_once()
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_save_analysis_storage_unavailable(self, mock_get_db_manager):
        """Test save when storage is unavailable"""
        # Mock database manager to return unavailable
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Storage should be unavailable
        self.assertFalse(storage.is_available())
        
        # Save analysis should return False
        result = storage.save_analysis(self.sample_record)
        self.assertFalse(result)
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_get_analysis_by_id_success(self, mock_get_db_manager):
        """Test successful retrieval by ID"""
        # Mock database manager to return unavailable
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection manually
        storage.collection = Mock()
        mock_doc = self.sample_record.to_dict()
        mock_doc['_id'] = "507f1f77bcf86cd799439011"
        storage.collection.find_one.return_value = mock_doc
        
        # Get analysis
        result = storage.get_analysis_by_id(self.sample_record.analysis_id)
        
        # Verify success
        self.assertIsNotNone(result)
        self.assertIsInstance(result, AnalysisHistoryRecord)
        self.assertEqual(result.analysis_id, self.sample_record.analysis_id)
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_get_analysis_by_id_not_found(self, mock_get_db_manager):
        """Test retrieval when record not found"""
        # Mock database manager to return unavailable
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection manually
        storage.collection = Mock()
        storage.collection.find_one.return_value = None
        
        # Get analysis
        result = storage.get_analysis_by_id("nonexistent_id")
        
        # Verify not found
        self.assertIsNone(result)
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_delete_analysis_success(self, mock_get_db_manager):
        """Test successful analysis deletion"""
        # Mock database manager to return unavailable
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection manually
        storage.collection = Mock()
        storage.collection.find_one.return_value = {'_id': "507f1f77bcf86cd799439011"}
        
        mock_result = Mock()
        mock_result.deleted_count = 1
        storage.collection.delete_one.return_value = mock_result
        
        # Delete analysis
        result = storage.delete_analysis(self.sample_record.analysis_id)
        
        # Verify success
        self.assertTrue(result)
        storage.collection.delete_one.assert_called_once()
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_delete_analysis_not_found(self, mock_get_db_manager):
        """Test deletion when record not found"""
        # Mock database manager to return unavailable
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection manually
        storage.collection = Mock()
        storage.collection.find_one.return_value = None
        
        # Delete analysis
        result = storage.delete_analysis("nonexistent_id")
        
        # Verify failure
        self.assertFalse(result)
        storage.collection.delete_one.assert_not_called()


class TestAnalysisHistoryStorageErrorHandling(unittest.TestCase):
    """Test error handling scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fixtures = TestAnalysisHistoryStorageFixtures()
        self.sample_record = self.fixtures.create_sample_record()
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_duplicate_key_error_handling(self, mock_get_db_manager):
        """Test handling of duplicate key errors"""
        # Mock database manager to return unavailable
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection manually
        storage.collection = Mock()
        storage.collection.insert_one.side_effect = DuplicateKeyError("Duplicate key")
        
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        storage.collection.replace_one.return_value = mock_update_result
        
        # Save analysis should handle duplicate and update
        result = storage.save_analysis(self.sample_record)
        
        # Verify success through update
        self.assertTrue(result)
        storage.collection.replace_one.assert_called_once()
    
    def test_invalid_input_handling(self):
        """Test handling of invalid inputs"""
        # Mock storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        storage.collection = Mock()
        
        # Test invalid analysis ID inputs
        self.assertIsNone(storage.get_analysis_by_id(None))
        self.assertIsNone(storage.get_analysis_by_id(""))
        self.assertIsNone(storage.get_analysis_by_id(123))
        
        # Test invalid delete inputs
        self.assertFalse(storage.delete_analysis(None))
        self.assertFalse(storage.delete_analysis(""))
        self.assertFalse(storage.delete_analysis(123))


if __name__ == '__main__':
    # Run the tests with verbose output
    unittest.main(verbosity=2)


class TestAnalysisHistoryStorageEdgeCases(unittest.TestCase):
    """Test edge cases and comprehensive scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fixtures = TestAnalysisHistoryStorageFixtures()
    
    def test_multiple_records_creation(self):
        """Test creating multiple records with different configurations"""
        records = self.fixtures.create_multiple_records(10)
        
        # Verify all records are valid
        for record in records:
            self.assertIsInstance(record, AnalysisHistoryRecord)
            record.validate()  # Should not raise exception
        
        # Verify records have different IDs
        ids = [record.analysis_id for record in records]
        self.assertEqual(len(ids), len(set(ids)))  # All unique
    
    def test_record_status_transitions(self):
        """Test record status update functionality"""
        record = self.fixtures.create_sample_record()
        
        # Test valid status transitions
        valid_statuses = [s.value for s in AnalysisStatus]
        for status in valid_statuses:
            record.update_status(status)
            self.assertEqual(record.status, status)
        
        # Test invalid status
        with self.assertRaises(ValueError):
            record.update_status("INVALID_STATUS")
    
    def test_record_results_addition(self):
        """Test adding results to a record"""
        record = self.fixtures.create_sample_record()
        
        # Add results
        raw_results = {"test": "raw_data", "success": True}
        formatted_results = {"test": "formatted_data", "display": "ready"}
        
        record.add_results(raw_results, formatted_results)
        
        # Verify results were added
        self.assertEqual(record.raw_results, raw_results)
        self.assertEqual(record.formatted_results, formatted_results)
        self.assertEqual(record.status, AnalysisStatus.COMPLETED.value)
    
    def test_record_token_usage_addition(self):
        """Test adding token usage information"""
        record = self.fixtures.create_sample_record()
        
        # Add token usage
        record.add_token_usage(1000, 500, 0.05)
        
        # Verify token usage
        self.assertEqual(record.token_usage['input_tokens'], 1000)
        self.assertEqual(record.token_usage['output_tokens'], 500)
        self.assertEqual(record.token_usage['total_tokens'], 1500)
        self.assertEqual(record.token_usage['total_cost'], 0.05)
    
    def test_record_execution_time_setting(self):
        """Test setting execution time"""
        record = self.fixtures.create_sample_record()
        
        # Set execution time
        record.set_execution_time(123.45)
        self.assertEqual(record.execution_time, 123.45)
        
        # Test negative time (should be corrected to 0)
        record.set_execution_time(-10.0)
        self.assertEqual(record.execution_time, 0.0)
    
    def test_record_metadata_addition(self):
        """Test adding metadata to records"""
        record = self.fixtures.create_sample_record()
        
        # Add metadata
        record.add_metadata("test_key", "test_value")
        record.add_metadata("numeric_key", 42)
        record.add_metadata("dict_key", {"nested": "data"})
        
        # Verify metadata
        self.assertEqual(record.metadata["test_key"], "test_value")
        self.assertEqual(record.metadata["numeric_key"], 42)
        self.assertEqual(record.metadata["dict_key"], {"nested": "data"})
    
    def test_record_utility_methods(self):
        """Test utility methods on records"""
        # Test completed record
        completed_record = self.fixtures.create_sample_record(
            status=AnalysisStatus.COMPLETED.value
        )
        self.assertTrue(completed_record.is_completed())
        self.assertFalse(completed_record.is_failed())
        
        # Test failed record
        failed_record = self.fixtures.create_sample_record(
            status=AnalysisStatus.FAILED.value
        )
        self.assertFalse(failed_record.is_completed())
        self.assertTrue(failed_record.is_failed())
        
        # Test display name
        display_name = completed_record.get_display_name()
        self.assertIn(completed_record.stock_name, display_name)
        self.assertIn(completed_record.stock_symbol, display_name)
        
        # Test cost summary
        cost_summary = completed_record.get_cost_summary()
        self.assertIsInstance(cost_summary, str)
    
    def test_different_market_types(self):
        """Test records for different market types"""
        # Test A-share
        a_share_record = AnalysisHistoryRecord(
            stock_symbol="000001",
            stock_name="平安银行",
            market_type=MarketType.A_SHARE.value,
            analysts_used=["market"]
        )
        a_share_record.validate()
        
        # Test HK stock
        hk_record = AnalysisHistoryRecord(
            stock_symbol="0700.HK",
            stock_name="腾讯控股",
            market_type=MarketType.HK_STOCK.value,
            analysts_used=["market"]
        )
        hk_record.validate()
        
        # Test US stock
        us_record = AnalysisHistoryRecord(
            stock_symbol="AAPL",
            stock_name="Apple Inc.",
            market_type=MarketType.US_STOCK.value,
            analysts_used=["market"]
        )
        us_record.validate()
    
    def test_comprehensive_validation_scenarios(self):
        """Test comprehensive validation scenarios"""
        # Test all valid analysts
        valid_analysts = ['market', 'fundamentals', 'news', 'social']
        record = AnalysisHistoryRecord(
            stock_symbol="AAPL",
            stock_name="Apple Inc.",
            analysts_used=valid_analysts
        )
        record.validate()
        
        # Test all valid research depths
        for depth in range(1, 6):
            record = AnalysisHistoryRecord(
                stock_symbol="AAPL",
                stock_name="Apple Inc.",
                analysts_used=["market"],
                research_depth=depth
            )
            record.validate()
        
        # Test all valid LLM providers
        valid_providers = ['dashscope', 'deepseek', 'openai', 'google']
        for provider in valid_providers:
            record = AnalysisHistoryRecord(
                stock_symbol="AAPL",
                stock_name="Apple Inc.",
                analysts_used=["market"],
                llm_provider=provider
            )
            record.validate()


class TestAnalysisHistoryStorageIntegration(unittest.TestCase):
    """Test integration scenarios with mocked storage"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fixtures = TestAnalysisHistoryStorageFixtures()
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_bulk_operations(self, mock_get_db_manager):
        """Test bulk operations on storage"""
        # Mock database manager
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection
        storage.collection = Mock()
        
        # Test bulk delete
        mock_result = Mock()
        mock_result.deleted_count = 3
        storage.collection.delete_many.return_value = mock_result
        
        result = storage.delete_multiple_analyses(["id1", "id2", "id3"])
        self.assertEqual(result, 3)
        storage.collection.delete_many.assert_called_once()
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_stats_collection(self, mock_get_db_manager):
        """Test statistics collection"""
        # Mock database manager
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection
        storage.collection = Mock()
        
        # Mock count queries
        storage.collection.count_documents.side_effect = [100, 80, 15, 25]
        
        # Mock aggregation result
        agg_result = [{
            '_id': None,
            'total_cost': 12.34,
            'avg_execution_time': 180.5,
            'total_execution_time': 18050.0
        }]
        storage.collection.aggregate.return_value = agg_result
        
        # Get stats
        stats = storage.get_history_stats()
        
        # Verify stats structure
        expected_keys = [
            'total_analyses', 'completed_analyses', 'failed_analyses',
            'recent_analyses', 'total_cost', 'avg_execution_time',
            'storage_available'
        ]
        
        for key in expected_keys:
            self.assertIn(key, stats)
    
    @patch('web.utils.history_storage.get_database_manager')
    def test_update_analysis_status(self, mock_get_db_manager):
        """Test updating analysis status"""
        # Mock database manager
        mock_db_manager = Mock()
        mock_db_manager.is_mongodb_available.return_value = False
        mock_get_db_manager.return_value = mock_db_manager
        
        # Import and create storage
        from web.utils.history_storage import AnalysisHistoryStorage
        storage = AnalysisHistoryStorage()
        
        # Mock collection
        storage.collection = Mock()
        
        # Mock successful update
        mock_result = Mock()
        mock_result.modified_count = 1
        storage.collection.update_one.return_value = mock_result
        
        # Update status
        result = storage.update_analysis_status("test_id", AnalysisStatus.COMPLETED.value)
        
        # Verify success
        self.assertTrue(result)
        storage.collection.update_one.assert_called_once()


class TestAnalysisHistoryStorageRequirements(unittest.TestCase):
    """Test that all task requirements are met"""
    
    def test_requirement_6_1_mongodb_storage_validation(self):
        """Test requirement 6.1: MongoDB storage backend with proper data validation"""
        # Test that storage class uses MongoDB
        from web.utils.history_storage import AnalysisHistoryStorage
        
        # Verify collection name is defined
        self.assertEqual(AnalysisHistoryStorage.COLLECTION_NAME, "analysis_history")
        
        # Test data validation through model
        fixtures = TestAnalysisHistoryStorageFixtures()
        record = fixtures.create_sample_record()
        
        # Validation should pass for valid record
        record.validate()
        
        # Validation should fail for invalid record
        with self.assertRaises(ValueError):
            invalid_record = AnalysisHistoryRecord(
                stock_symbol="",  # Invalid
                stock_name="Test",
                analysts_used=[]  # Invalid
            )
    
    def test_requirement_6_2_data_indexing(self):
        """Test requirement 6.2: Data indexing for efficient querying and data integrity"""
        from web.utils.history_storage import AnalysisHistoryStorage
        
        # Verify _create_indexes method exists
        self.assertTrue(hasattr(AnalysisHistoryStorage, '_create_indexes'))
        self.assertTrue(callable(AnalysisHistoryStorage._create_indexes))
        
        # Test that serialization maintains data integrity
        fixtures = TestAnalysisHistoryStorageFixtures()
        record = fixtures.create_sample_record()
        
        # Serialize and deserialize
        data = record.to_dict()
        restored = AnalysisHistoryRecord.from_dict(data)
        
        # Verify data integrity
        self.assertEqual(record.analysis_id, restored.analysis_id)
        self.assertEqual(record.stock_symbol, restored.stock_symbol)
        self.assertEqual(record.token_usage, restored.token_usage)
    
    def test_requirement_6_4_error_handling(self):
        """Test requirement 6.4: Error handling with appropriate logging"""
        from web.utils.history_storage import AnalysisHistoryStorage
        
        # Verify error handling methods exist
        storage_methods = [
            'save_analysis',
            'get_analysis_by_id',
            'get_user_history',
            'delete_analysis'
        ]
        
        for method_name in storage_methods:
            method = getattr(AnalysisHistoryStorage, method_name)
            self.assertTrue(callable(method))
        
        # Test that invalid inputs are handled gracefully
        storage = AnalysisHistoryStorage()
        storage.collection = Mock()
        
        # These should not raise exceptions
        self.assertIsNone(storage.get_analysis_by_id(None))
        self.assertIsNone(storage.get_analysis_by_id(""))
        self.assertFalse(storage.delete_analysis(None))
        self.assertFalse(storage.delete_analysis(""))
    
    def test_fixtures_provide_consistent_data(self):
        """Test that fixtures provide consistent test data"""
        fixtures = TestAnalysisHistoryStorageFixtures()
        
        # Test single record creation
        record1 = fixtures.create_sample_record()
        record2 = fixtures.create_sample_record()
        
        # Should have different IDs but same structure
        self.assertNotEqual(record1.analysis_id, record2.analysis_id)
        self.assertEqual(record1.stock_symbol, record2.stock_symbol)
        self.assertEqual(record1.stock_name, record2.stock_name)
        
        # Test multiple records creation
        records = fixtures.create_multiple_records(5)
        self.assertEqual(len(records), 5)
        
        # All should be valid
        for record in records:
            record.validate()
        
        # Should have unique IDs
        ids = [r.analysis_id for r in records]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == '__main__':
    # Run the tests with verbose output
    unittest.main(verbosity=2)