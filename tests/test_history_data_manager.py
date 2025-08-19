"""
Unit tests for Analysis History Data Manager

Tests the data management and cleanup utilities for analysis history.
"""

import pytest
import tempfile
import json
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the modules to test
from web.utils.history_data_manager import HistoryDataManager, get_data_manager
from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus


class TestHistoryDataManager:
    """Test cases for HistoryDataManager"""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager"""
        mock_manager = Mock()
        mock_manager.is_mongodb_available.return_value = True
        
        # Create a proper mock client that supports subscripting
        mock_client = Mock()
        mock_database = Mock()
        mock_client.__getitem__ = Mock(return_value=mock_database)
        mock_client.admin.command = Mock(return_value=True)
        
        mock_manager.get_mongodb_client.return_value = mock_client
        mock_manager.get_config.return_value = {
            'mongodb': {'database': 'test_db'}
        }
        return mock_manager
    
    @pytest.fixture
    def mock_collection(self):
        """Mock MongoDB collection"""
        mock_collection = Mock()
        mock_collection.count_documents.return_value = 0
        mock_collection.find.return_value = []
        mock_collection.aggregate.return_value = []
        mock_collection.delete_many.return_value = Mock(deleted_count=0)
        mock_collection.insert_many.return_value = Mock(inserted_ids=[])
        return mock_collection
    
    @pytest.fixture
    def data_manager(self, mock_db_manager, mock_collection):
        """Create a data manager instance with mocked dependencies"""
        with patch('web.utils.history_data_manager.get_database_manager', return_value=mock_db_manager):
            manager = HistoryDataManager()
            manager.collection = mock_collection
            manager.backup_collection = mock_collection
            return manager
    
    @pytest.fixture
    def sample_record(self):
        """Create a sample analysis history record"""
        return AnalysisHistoryRecord(
            analysis_id="test_analysis_123",
            stock_symbol="AAPL",
            stock_name="Apple Inc.",
            market_type="美股",
            analysis_date=datetime.now().date(),
            created_at=datetime.now(),
            analysis_type="comprehensive",
            status=AnalysisStatus.COMPLETED,
            analysts_used=["market", "fundamentals"],
            research_depth=3,
            llm_provider="openai",
            llm_model="gpt-4",
            execution_time=120.5,
            raw_results={"test": "data"},
            formatted_results={"formatted": "data"},
            metadata={"version": "1.0"}
        )
    
    def test_initialization(self, mock_db_manager):
        """Test data manager initialization"""
        with patch('web.utils.history_data_manager.get_database_manager', return_value=mock_db_manager):
            manager = HistoryDataManager()
            assert manager.db_manager == mock_db_manager
            assert manager.COLLECTION_NAME == "analysis_history"
            assert manager.BACKUP_COLLECTION_NAME == "analysis_history_backup"
    
    def test_is_available(self, data_manager):
        """Test availability check"""
        assert data_manager.is_available() == True
        
        data_manager.collection = None
        assert data_manager.is_available() == False
    
    def test_cleanup_old_records_dry_run(self, data_manager, mock_collection):
        """Test cleanup old records in dry run mode"""
        # Mock finding old records
        mock_collection.count_documents.return_value = 5
        mock_collection.find.return_value = [
            {"analysis_id": "old_1", "stock_symbol": "AAPL", "created_at": datetime.now(), "status": "completed"},
            {"analysis_id": "old_2", "stock_symbol": "GOOGL", "created_at": datetime.now(), "status": "completed"}
        ]
        
        result = data_manager.cleanup_old_records(max_age_days=365, dry_run=True)
        
        assert result["success"] == True
        assert result["total_found"] == 5
        assert result["deleted_count"] == 0
        assert result["dry_run"] == True
        assert "sample_records" in result
    
    def test_cleanup_old_records_actual(self, data_manager, mock_collection):
        """Test actual cleanup of old records"""
        # Mock finding and deleting old records
        mock_collection.count_documents.return_value = 3
        mock_collection.find.return_value = [
            {"_id": "id1", "analysis_id": "old_1"},
            {"_id": "id2", "analysis_id": "old_2"},
            {"_id": "id3", "analysis_id": "old_3"}
        ]
        mock_collection.delete_many.return_value = Mock(deleted_count=3)
        
        result = data_manager.cleanup_old_records(max_age_days=365, dry_run=False)
        
        assert result["success"] == True
        assert result["total_found"] == 3
        assert result["deleted_count"] == 3
        assert result["dry_run"] == False
    
    def test_cleanup_failed_records(self, data_manager, mock_collection):
        """Test cleanup of failed records"""
        mock_collection.count_documents.return_value = 2
        mock_collection.delete_many.return_value = Mock(deleted_count=2)
        
        result = data_manager.cleanup_failed_records(max_age_hours=24, dry_run=False)
        
        assert result["success"] == True
        assert result["total_found"] == 2
        assert result["deleted_count"] == 2
    
    def test_get_storage_statistics(self, data_manager, mock_collection):
        """Test getting storage statistics"""
        # Mock database command response
        mock_database = Mock()
        mock_database.command.return_value = {
            "count": 1000,
            "size": 1024000,
            "avgObjSize": 1024,
            "storageSize": 2048000,
            "totalIndexSize": 512000
        }
        data_manager.database = mock_database
        
        # Mock aggregation results
        mock_collection.aggregate.side_effect = [
            [{"_id": "completed", "count": 800}, {"_id": "failed", "count": 200}],  # status
            [{"_id": "2025-01-01", "count": 50}, {"_id": "2025-01-02", "count": 75}],  # daily
            [{"_id": "美股", "count": 600}, {"_id": "A股", "count": 400}],  # market
            [{"_id": None, "avg_execution_time": 120.5, "avg_cost": 0.05}]  # performance
        ]
        
        result = data_manager.get_storage_statistics()
        
        assert result["success"] == True
        assert result["storage_info"]["total_documents"] == 1000
        assert result["storage_info"]["total_size_mb"] == 1.0  # 1024000 bytes = ~1 MB
        assert "completed" in result["status_distribution"]
        assert "美股" in result["market_distribution"]
    
    def test_check_storage_alerts(self, data_manager):
        """Test storage alert checking"""
        # Mock get_storage_statistics
        with patch.object(data_manager, 'get_storage_statistics') as mock_stats:
            mock_stats.return_value = {
                "success": True,
                "storage_info": {
                    "total_documents": 90000,  # Below threshold
                    "total_size_mb": 900.0     # Below threshold
                },
                "daily_counts_last_30_days": {
                    "2025-01-01": 100,
                    "2025-01-02": 150,
                    "2025-01-03": 200
                }
            }
            
            result = data_manager.check_storage_alerts(
                max_size_mb=1000,
                max_documents=100000,
                max_daily_growth=1000
            )
            
            assert result["success"] == True
            assert result["alert_count"] == 0
            assert result["warning_count"] == 0
    
    def test_export_data(self, data_manager, mock_collection):
        """Test data export functionality"""
        # Mock collection data
        mock_collection.count_documents.return_value = 2
        mock_collection.find.return_value = [
            {
                "analysis_id": "test_1",
                "stock_symbol": "AAPL",
                "created_at": datetime.now(),
                "status": "completed"
            },
            {
                "analysis_id": "test_2",
                "stock_symbol": "GOOGL",
                "created_at": datetime.now(),
                "status": "completed"
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            temp_path = temp_file.name
        
        try:
            result = data_manager.export_data(
                output_path=temp_path,
                filters=None,
                compress=False
            )
            
            assert result["success"] == True
            assert result["exported_count"] == 2
            assert result["total_found"] == 2
            
            # Verify file contents
            with open(temp_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                assert len(lines) == 3  # metadata + 2 records
                
                # Check metadata
                metadata = json.loads(lines[0])
                assert "export_timestamp" in metadata
                assert metadata["total_records"] == 2
                
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_export_data_compressed(self, data_manager, mock_collection):
        """Test compressed data export"""
        mock_collection.count_documents.return_value = 1
        mock_collection.find.return_value = [
            {
                "analysis_id": "test_1",
                "stock_symbol": "AAPL",
                "created_at": datetime.now(),
                "status": "completed"
            }
        ]
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json.gz') as temp_file:
            temp_path = temp_file.name
        
        try:
            result = data_manager.export_data(
                output_path=temp_path,
                filters=None,
                compress=True
            )
            
            assert result["success"] == True
            assert result["exported_count"] == 1
            assert result["compressed"] == True
            
            # Verify compressed file can be read
            with gzip.open(temp_path, 'rt', encoding='utf-8') as f:
                lines = f.readlines()
                assert len(lines) == 2  # metadata + 1 record
                
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_data(self, data_manager, mock_collection, sample_record):
        """Test data import functionality"""
        # Create test data file
        test_data = [
            {
                "export_timestamp": datetime.now().isoformat(),
                "total_records": 1,
                "version": "1.0"
            },
            sample_record.to_dict()
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            for item in test_data:
                json.dump(item, temp_file, default=str)
                temp_file.write('\n')
            temp_path = temp_file.name
        
        try:
            # Mock successful insertion
            mock_collection.find_one.return_value = None  # No existing record
            mock_collection.insert_many.return_value = Mock(inserted_ids=["id1"])
            
            result = data_manager.import_data(
                input_path=temp_path,
                skip_existing=True,
                validate_records=True
            )
            
            assert result["success"] == True
            assert result["imported_count"] == 1
            assert result["skipped_count"] == 0
            assert result["error_count"] == 0
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_data_skip_existing(self, data_manager, mock_collection, sample_record):
        """Test import with skip existing records"""
        test_data = [sample_record.to_dict()]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            for item in test_data:
                json.dump(item, temp_file, default=str)
                temp_file.write('\n')
            temp_path = temp_file.name
        
        try:
            # Mock existing record found
            mock_collection.find_one.return_value = {"_id": "existing"}
            
            result = data_manager.import_data(
                input_path=temp_path,
                skip_existing=True
            )
            
            assert result["success"] == True
            assert result["imported_count"] == 0
            assert result["skipped_count"] == 1
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_data_validation_error(self, data_manager, mock_collection):
        """Test import with validation errors"""
        # Create invalid test data
        invalid_data = [
            {
                "analysis_id": "invalid",
                # Missing required fields
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            for item in invalid_data:
                json.dump(item, temp_file, default=str)
                temp_file.write('\n')
            temp_path = temp_file.name
        
        try:
            result = data_manager.import_data(
                input_path=temp_path,
                validate_records=True
            )
            
            assert result["success"] == True
            assert result["imported_count"] == 0
            assert result["error_count"] == 1
            
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch('web.utils.history_data_manager.get_data_manager')
    def test_cleanup_old_analysis_records(self, mock_get_manager):
        """Test cleanup convenience function"""
        mock_manager = Mock()
        mock_manager.cleanup_old_records.return_value = {"success": True, "deleted_count": 5}
        mock_get_manager.return_value = mock_manager
        
        from web.utils.history_data_manager import cleanup_old_analysis_records
        
        result = cleanup_old_analysis_records(max_age_days=180, dry_run=True)
        
        assert result["success"] == True
        assert result["deleted_count"] == 5
        mock_manager.cleanup_old_records.assert_called_once_with(max_age_days=180, dry_run=True)
    
    @patch('web.utils.history_data_manager.get_data_manager')
    def test_get_storage_usage_report(self, mock_get_manager):
        """Test storage usage report convenience function"""
        mock_manager = Mock()
        mock_manager.get_storage_statistics.return_value = {"success": True, "storage_info": {}}
        mock_manager.check_storage_alerts.return_value = {"success": True, "alerts": []}
        mock_get_manager.return_value = mock_manager
        
        from web.utils.history_data_manager import get_storage_usage_report
        
        result = get_storage_usage_report()
        
        assert "statistics" in result
        assert "alerts" in result
        assert "timestamp" in result
    
    @patch('web.utils.history_data_manager.get_data_manager')
    def test_export_analysis_history(self, mock_get_manager):
        """Test export convenience function"""
        mock_manager = Mock()
        mock_manager.export_data.return_value = {"success": True, "exported_count": 10}
        mock_get_manager.return_value = mock_manager
        
        from web.utils.history_data_manager import export_analysis_history
        
        result = export_analysis_history("test_export.json", filters={"status": "completed"})
        
        assert result["success"] == True
        assert result["exported_count"] == 10
        mock_manager.export_data.assert_called_once_with(
            output_path="test_export.json",
            filters={"status": "completed"}
        )
    
    @patch('web.utils.history_data_manager.get_data_manager')
    def test_import_analysis_history(self, mock_get_manager):
        """Test import convenience function"""
        mock_manager = Mock()
        mock_manager.import_data.return_value = {"success": True, "imported_count": 8}
        mock_get_manager.return_value = mock_manager
        
        from web.utils.history_data_manager import import_analysis_history
        
        result = import_analysis_history("test_import.json")
        
        assert result["success"] == True
        assert result["imported_count"] == 8
        mock_manager.import_data.assert_called_once_with(input_path="test_import.json")


class TestErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.fixture
    def unavailable_manager(self):
        """Create a data manager that's not available"""
        with patch('web.utils.history_data_manager.get_database_manager') as mock_db_manager:
            mock_db_manager.return_value.is_mongodb_available.return_value = False
            manager = HistoryDataManager()
            return manager
    
    def test_cleanup_when_unavailable(self, unavailable_manager):
        """Test cleanup when data manager is unavailable"""
        result = unavailable_manager.cleanup_old_records()
        
        assert result["success"] == False
        assert "not available" in result["error"]
    
    def test_export_when_unavailable(self, unavailable_manager):
        """Test export when data manager is unavailable"""
        result = unavailable_manager.export_data("test.json")
        
        assert result["success"] == False
        assert "not available" in result["error"]
    
    def test_import_nonexistent_file(self, unavailable_manager):
        """Test import with nonexistent file"""
        # Create a manager that is available but with nonexistent file
        with patch('web.utils.history_data_manager.get_database_manager') as mock_db_manager:
            mock_db_manager.return_value.is_mongodb_available.return_value = True
            
            # Create a proper mock client
            mock_client = Mock()
            mock_database = Mock()
            mock_collection = Mock()
            mock_client.__getitem__ = Mock(return_value=mock_database)
            mock_client.admin.command = Mock(return_value=True)
            mock_database.__getitem__ = Mock(return_value=mock_collection)
            
            mock_db_manager.return_value.get_mongodb_client.return_value = mock_client
            mock_db_manager.return_value.get_config.return_value = {
                'mongodb': {'database': 'test_db'}
            }
            
            manager = HistoryDataManager()
            result = manager.import_data("nonexistent_file.json")
            
            assert result["success"] == False
            assert "not found" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])