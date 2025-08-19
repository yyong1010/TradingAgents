"""
Analysis History Data Management and Cleanup Utilities

This module provides comprehensive data management utilities for the analysis history system,
including automatic cleanup, storage monitoring, and backup functionality.
"""

import logging
import time
import json
import gzip
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError

from tradingagents.config.database_manager import get_database_manager
from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus
from web.utils.error_handler import with_retry, with_error_handling, log_operation_metrics

# Setup logging
logger = logging.getLogger(__name__)


class HistoryDataManager:
    """
    Analysis History Data Management Service
    
    Provides utilities for data cleanup, monitoring, and maintenance operations.
    """
    
    COLLECTION_NAME = "analysis_history"
    BACKUP_COLLECTION_NAME = "analysis_history_backup"
    
    def __init__(self):
        """Initialize the data manager"""
        self.db_manager = get_database_manager()
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database] = None
        self.collection: Optional[Collection] = None
        self.backup_collection: Optional[Collection] = None
        
        # Initialize database connection
        self._initialize_connection()
    
    @with_retry(
        max_attempts=3, 
        delay=2.0, 
        retry_on=(ConnectionFailure, ServerSelectionTimeoutError),
        show_user_feedback=False,
        operation_name="数据管理器连接初始化"
    )
    def _initialize_connection(self) -> None:
        """Initialize MongoDB connection for data management operations"""
        try:
            if not self.db_manager.is_mongodb_available():
                logger.warning("MongoDB is not available. Data management will be disabled.")
                return
            
            self.client = self.db_manager.get_mongodb_client()
            if self.client is None:
                logger.error("Failed to get MongoDB client for data management")
                return
            
            # Test connection
            self.client.admin.command('ping', maxTimeMS=5000)
            
            # Get database
            config = self.db_manager.get_config()
            db_name = config['mongodb']['database']
            self.database = self.client[db_name]
            self.collection = self.database[self.COLLECTION_NAME]
            self.backup_collection = self.database[self.BACKUP_COLLECTION_NAME]
            
            logger.info(f"Data manager connected to MongoDB database '{db_name}'")
            
        except Exception as e:
            logger.error(f"Failed to initialize data manager connection: {e}")
            self.client = None
            self.database = None
            self.collection = None
            self.backup_collection = None
            raise
    
    def is_available(self) -> bool:
        """Check if the data manager is available"""
        return self.collection is not None
    
    # Automatic Cleanup Operations
    
    @with_error_handling(context="自动清理旧记录", show_user_error=False)
    @with_retry(max_attempts=2, delay=1.0, retry_on=(ConnectionFailure, ServerSelectionTimeoutError))
    def cleanup_old_records(self, 
                           max_age_days: int = 365,
                           batch_size: int = 100,
                           dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up old analysis records automatically
        
        Args:
            max_age_days: Maximum age of records to keep (default: 365 days)
            batch_size: Number of records to process in each batch
            dry_run: If True, only count records without deleting
            
        Returns:
            Dict with cleanup statistics
        """
        if not self.is_available():
            logger.warning("Data manager not available, cannot cleanup old records")
            return {"success": False, "error": "Data manager not available"}
        
        start_time = time.time()
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        try:
            # Find old records
            query = {"created_at": {"$lt": cutoff_date}}
            
            # Count total records to be cleaned
            total_count = self.collection.count_documents(query, maxTimeMS=10000)
            
            if total_count == 0:
                logger.info(f"No records older than {max_age_days} days found")
                return {
                    "success": True,
                    "total_found": 0,
                    "deleted_count": 0,
                    "duration": time.time() - start_time,
                    "dry_run": dry_run
                }
            
            logger.info(f"Found {total_count} records older than {max_age_days} days")
            
            if dry_run:
                # Get sample records for analysis
                sample_records = list(self.collection.find(
                    query, 
                    {"analysis_id": 1, "stock_symbol": 1, "created_at": 1, "status": 1}
                ).limit(10))
                
                return {
                    "success": True,
                    "total_found": total_count,
                    "deleted_count": 0,
                    "duration": time.time() - start_time,
                    "dry_run": True,
                    "sample_records": sample_records
                }
            
            # Perform cleanup in batches
            deleted_count = 0
            processed_batches = 0
            
            while True:
                # Find a batch of old records
                batch_records = list(self.collection.find(
                    query,
                    {"_id": 1, "analysis_id": 1}
                ).limit(batch_size))
                
                if not batch_records:
                    break
                
                # Extract IDs for batch deletion
                record_ids = [record["_id"] for record in batch_records]
                analysis_ids = [record["analysis_id"] for record in batch_records]
                
                # Delete the batch
                delete_result = self.collection.delete_many({"_id": {"$in": record_ids}})
                batch_deleted = delete_result.deleted_count
                deleted_count += batch_deleted
                processed_batches += 1
                
                logger.info(f"Batch {processed_batches}: Deleted {batch_deleted} records")
                
                # Log progress for large cleanups
                if processed_batches % 10 == 0:
                    logger.info(f"Cleanup progress: {deleted_count}/{total_count} records deleted")
                
                # Break if batch was smaller than expected (last batch)
                if len(batch_records) < batch_size:
                    break
            
            duration = time.time() - start_time
            logger.info(f"Cleanup completed: Deleted {deleted_count} records in {duration:.2f}s")
            
            # Log operation metrics
            log_operation_metrics(
                "cleanup_old_records",
                duration,
                True,
                additional_metrics={
                    "max_age_days": max_age_days,
                    "total_found": total_count,
                    "deleted_count": deleted_count,
                    "processed_batches": processed_batches
                }
            )
            
            return {
                "success": True,
                "total_found": total_count,
                "deleted_count": deleted_count,
                "processed_batches": processed_batches,
                "duration": duration,
                "dry_run": False
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error during cleanup operation: {e}")
            
            log_operation_metrics(
                "cleanup_old_records",
                duration,
                False,
                error=e
            )
            
            return {
                "success": False,
                "error": str(e),
                "duration": duration
            }
    
    @with_error_handling(context="清理失败记录", show_user_error=False)
    def cleanup_failed_records(self, max_age_hours: int = 24, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up failed or incomplete analysis records
        
        Args:
            max_age_hours: Maximum age of failed records to keep (default: 24 hours)
            dry_run: If True, only count records without deleting
            
        Returns:
            Dict with cleanup statistics
        """
        if not self.is_available():
            return {"success": False, "error": "Data manager not available"}
        
        start_time = time.time()
        cutoff_date = datetime.now() - timedelta(hours=max_age_hours)
        
        try:
            # Find failed records older than cutoff
            query = {
                "status": {"$in": ["failed", "error", "incomplete"]},
                "created_at": {"$lt": cutoff_date}
            }
            
            total_count = self.collection.count_documents(query, maxTimeMS=5000)
            
            if total_count == 0:
                logger.info(f"No failed records older than {max_age_hours} hours found")
                return {
                    "success": True,
                    "total_found": 0,
                    "deleted_count": 0,
                    "duration": time.time() - start_time,
                    "dry_run": dry_run
                }
            
            logger.info(f"Found {total_count} failed records older than {max_age_hours} hours")
            
            if dry_run:
                return {
                    "success": True,
                    "total_found": total_count,
                    "deleted_count": 0,
                    "duration": time.time() - start_time,
                    "dry_run": True
                }
            
            # Delete failed records
            delete_result = self.collection.delete_many(query)
            deleted_count = delete_result.deleted_count
            
            duration = time.time() - start_time
            logger.info(f"Cleaned up {deleted_count} failed records in {duration:.2f}s")
            
            return {
                "success": True,
                "total_found": total_count,
                "deleted_count": deleted_count,
                "duration": duration,
                "dry_run": False
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up failed records: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
    
    # Storage Usage Monitoring
    
    @with_error_handling(context="获取存储统计", show_user_error=False)
    def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive storage usage statistics
        
        Returns:
            Dict with storage statistics
        """
        if not self.is_available():
            return {"success": False, "error": "Data manager not available"}
        
        start_time = time.time()
        
        try:
            # Basic collection statistics
            stats = self.database.command("collStats", self.COLLECTION_NAME)
            
            # Count records by status
            status_pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            status_counts = list(self.collection.aggregate(status_pipeline, maxTimeMS=10000))
            
            # Count records by date (last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            date_pipeline = [
                {"$match": {"created_at": {"$gte": thirty_days_ago}}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$created_at"
                            }
                        },
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            daily_counts = list(self.collection.aggregate(date_pipeline, maxTimeMS=10000))
            
            # Count records by market type
            market_pipeline = [
                {"$group": {"_id": "$market_type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            market_counts = list(self.collection.aggregate(market_pipeline, maxTimeMS=5000))
            
            # Average execution time and cost analysis
            performance_pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "avg_execution_time": {"$avg": "$execution_time"},
                        "max_execution_time": {"$max": "$execution_time"},
                        "min_execution_time": {"$min": "$execution_time"},
                        "avg_cost": {"$avg": "$token_usage.total_cost"},
                        "total_cost": {"$sum": "$token_usage.total_cost"}
                    }
                }
            ]
            performance_stats = list(self.collection.aggregate(performance_pipeline, maxTimeMS=5000))
            
            # Storage size breakdown
            storage_info = {
                "total_documents": stats.get("count", 0),
                "total_size_bytes": stats.get("size", 0),
                "total_size_mb": round(stats.get("size", 0) / 1024 / 1024, 2),
                "average_document_size_bytes": stats.get("avgObjSize", 0),
                "storage_size_bytes": stats.get("storageSize", 0),
                "storage_size_mb": round(stats.get("storageSize", 0) / 1024 / 1024, 2),
                "index_size_bytes": stats.get("totalIndexSize", 0),
                "index_size_mb": round(stats.get("totalIndexSize", 0) / 1024 / 1024, 2)
            }
            
            duration = time.time() - start_time
            
            return {
                "success": True,
                "storage_info": storage_info,
                "status_distribution": {item["_id"]: item["count"] for item in status_counts},
                "daily_counts_last_30_days": {item["_id"]: item["count"] for item in daily_counts},
                "market_distribution": {item["_id"]: item["count"] for item in market_counts},
                "performance_stats": performance_stats[0] if performance_stats else {},
                "query_duration": duration,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
    
    def check_storage_alerts(self, 
                           max_size_mb: int = 1000,
                           max_documents: int = 100000,
                           max_daily_growth: int = 1000) -> Dict[str, Any]:
        """
        Check for storage usage alerts and warnings
        
        Args:
            max_size_mb: Maximum storage size in MB before alert
            max_documents: Maximum number of documents before alert
            max_daily_growth: Maximum daily document growth before alert
            
        Returns:
            Dict with alert information
        """
        stats = self.get_storage_statistics()
        
        if not stats["success"]:
            return stats
        
        alerts = []
        warnings = []
        
        storage_info = stats["storage_info"]
        
        # Check total size
        if storage_info["total_size_mb"] > max_size_mb:
            alerts.append({
                "type": "storage_size",
                "message": f"Storage size ({storage_info['total_size_mb']:.2f} MB) exceeds limit ({max_size_mb} MB)",
                "current_value": storage_info["total_size_mb"],
                "threshold": max_size_mb
            })
        elif storage_info["total_size_mb"] > max_size_mb * 0.8:
            warnings.append({
                "type": "storage_size",
                "message": f"Storage size ({storage_info['total_size_mb']:.2f} MB) approaching limit ({max_size_mb} MB)",
                "current_value": storage_info["total_size_mb"],
                "threshold": max_size_mb
            })
        
        # Check document count
        if storage_info["total_documents"] > max_documents:
            alerts.append({
                "type": "document_count",
                "message": f"Document count ({storage_info['total_documents']}) exceeds limit ({max_documents})",
                "current_value": storage_info["total_documents"],
                "threshold": max_documents
            })
        elif storage_info["total_documents"] > max_documents * 0.8:
            warnings.append({
                "type": "document_count",
                "message": f"Document count ({storage_info['total_documents']}) approaching limit ({max_documents})",
                "current_value": storage_info["total_documents"],
                "threshold": max_documents
            })
        
        # Check daily growth (if we have recent data)
        daily_counts = stats["daily_counts_last_30_days"]
        if daily_counts:
            recent_days = sorted(daily_counts.keys())[-7:]  # Last 7 days
            if len(recent_days) >= 2:
                recent_growth = sum(daily_counts[day] for day in recent_days[-3:])  # Last 3 days
                avg_daily_growth = recent_growth / 3
                
                if avg_daily_growth > max_daily_growth:
                    alerts.append({
                        "type": "daily_growth",
                        "message": f"Daily growth ({avg_daily_growth:.0f} docs/day) exceeds limit ({max_daily_growth})",
                        "current_value": avg_daily_growth,
                        "threshold": max_daily_growth
                    })
                elif avg_daily_growth > max_daily_growth * 0.8:
                    warnings.append({
                        "type": "daily_growth",
                        "message": f"Daily growth ({avg_daily_growth:.0f} docs/day) approaching limit ({max_daily_growth})",
                        "current_value": avg_daily_growth,
                        "threshold": max_daily_growth
                    })
        
        return {
            "success": True,
            "alerts": alerts,
            "warnings": warnings,
            "alert_count": len(alerts),
            "warning_count": len(warnings),
            "storage_stats": storage_info,
            "timestamp": datetime.now().isoformat()
        }
    
    # Data Export/Import Functionality
    
    @with_error_handling(context="导出历史数据", show_user_error=False)
    def export_data(self, 
                   output_path: Union[str, Path],
                   filters: Optional[Dict[str, Any]] = None,
                   compress: bool = True,
                   batch_size: int = 1000) -> Dict[str, Any]:
        """
        Export analysis history data to JSON file
        
        Args:
            output_path: Path to output file
            filters: Optional filters to apply to export
            compress: Whether to compress the output file
            batch_size: Number of records to process in each batch
            
        Returns:
            Dict with export statistics
        """
        if not self.is_available():
            return {"success": False, "error": "Data manager not available"}
        
        start_time = time.time()
        output_path = Path(output_path)
        
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build query
            query = {}
            if filters:
                # Apply basic filters
                if "date_from" in filters:
                    query.setdefault("created_at", {})["$gte"] = filters["date_from"]
                if "date_to" in filters:
                    query.setdefault("created_at", {})["$lt"] = filters["date_to"]
                if "status" in filters:
                    query["status"] = filters["status"]
                if "market_type" in filters:
                    query["market_type"] = filters["market_type"]
            
            # Count total records
            total_count = self.collection.count_documents(query, maxTimeMS=10000)
            
            if total_count == 0:
                logger.info("No records found matching export criteria")
                return {
                    "success": True,
                    "exported_count": 0,
                    "total_found": 0,
                    "output_path": str(output_path),
                    "duration": time.time() - start_time
                }
            
            logger.info(f"Exporting {total_count} records to {output_path}")
            
            # Open output file
            if compress and not output_path.suffix == '.gz':
                output_path = output_path.with_suffix(output_path.suffix + '.gz')
                file_opener = gzip.open
            else:
                file_opener = open
            
            exported_count = 0
            
            with file_opener(output_path, 'wt', encoding='utf-8') as f:
                # Write export metadata
                export_metadata = {
                    "export_timestamp": datetime.now().isoformat(),
                    "total_records": total_count,
                    "filters_applied": filters or {},
                    "version": "1.0"
                }
                f.write(json.dumps(export_metadata) + '\n')
                
                # Export records in batches
                cursor = self.collection.find(query).batch_size(batch_size)
                
                for doc in cursor:
                    # Remove MongoDB internal fields
                    doc.pop('_id', None)
                    doc.pop('_retry_count', None)
                    doc.pop('_last_save_attempt', None)
                    
                    # Convert datetime objects to ISO strings
                    if 'created_at' in doc and isinstance(doc['created_at'], datetime):
                        doc['created_at'] = doc['created_at'].isoformat()
                    if 'updated_at' in doc and isinstance(doc['updated_at'], datetime):
                        doc['updated_at'] = doc['updated_at'].isoformat()
                    if 'analysis_date' in doc and isinstance(doc['analysis_date'], datetime):
                        doc['analysis_date'] = doc['analysis_date'].isoformat()
                    
                    # Write record as JSON line
                    f.write(json.dumps(doc, ensure_ascii=False) + '\n')
                    exported_count += 1
                    
                    # Log progress for large exports
                    if exported_count % 10000 == 0:
                        logger.info(f"Export progress: {exported_count}/{total_count} records")
            
            duration = time.time() - start_time
            file_size_mb = output_path.stat().st_size / 1024 / 1024
            
            logger.info(f"Export completed: {exported_count} records exported to {output_path} ({file_size_mb:.2f} MB) in {duration:.2f}s")
            
            return {
                "success": True,
                "exported_count": exported_count,
                "total_found": total_count,
                "output_path": str(output_path),
                "file_size_mb": file_size_mb,
                "compressed": compress,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"Error during data export: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
    
    @with_error_handling(context="导入历史数据", show_user_error=False)
    def import_data(self, 
                   input_path: Union[str, Path],
                   batch_size: int = 1000,
                   skip_existing: bool = True,
                   validate_records: bool = True) -> Dict[str, Any]:
        """
        Import analysis history data from JSON file
        
        Args:
            input_path: Path to input file
            batch_size: Number of records to process in each batch
            skip_existing: Whether to skip records that already exist
            validate_records: Whether to validate records before import
            
        Returns:
            Dict with import statistics
        """
        if not self.is_available():
            return {"success": False, "error": "Data manager not available"}
        
        start_time = time.time()
        input_path = Path(input_path)
        
        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_path}"}
        
        try:
            # Determine if file is compressed
            if input_path.suffix == '.gz':
                file_opener = gzip.open
            else:
                file_opener = open
            
            imported_count = 0
            skipped_count = 0
            error_count = 0
            batch_records = []
            
            logger.info(f"Starting import from {input_path}")
            
            with file_opener(input_path, 'rt', encoding='utf-8') as f:
                # Read and validate export metadata
                first_line = f.readline().strip()
                try:
                    metadata = json.loads(first_line)
                    if "export_timestamp" in metadata:
                        logger.info(f"Importing data exported on {metadata['export_timestamp']}")
                        total_expected = metadata.get("total_records", 0)
                    else:
                        # First line is actually a record, reset file pointer
                        f.seek(0)
                        total_expected = None
                except json.JSONDecodeError:
                    # First line is a record, reset file pointer
                    f.seek(0)
                    total_expected = None
                
                # Process records line by line
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        # Parse JSON record
                        doc = json.loads(line)
                        
                        # Convert ISO strings back to datetime objects
                        for date_field in ['created_at', 'updated_at', 'analysis_date']:
                            if date_field in doc and isinstance(doc[date_field], str):
                                try:
                                    doc[date_field] = datetime.fromisoformat(doc[date_field].replace('Z', '+00:00'))
                                except ValueError:
                                    logger.warning(f"Invalid date format in {date_field}: {doc[date_field]}")
                        
                        # Validate record if requested
                        if validate_records:
                            try:
                                record = AnalysisHistoryRecord.from_dict(doc)
                                record.validate()
                            except Exception as validation_error:
                                logger.warning(f"Record validation failed at line {line_num}: {validation_error}")
                                error_count += 1
                                continue
                        
                        # Check if record already exists
                        if skip_existing and "analysis_id" in doc:
                            existing = self.collection.find_one(
                                {"analysis_id": doc["analysis_id"]}, 
                                {"_id": 1},
                                maxTimeMS=1000
                            )
                            if existing:
                                skipped_count += 1
                                continue
                        
                        batch_records.append(doc)
                        
                        # Process batch when full
                        if len(batch_records) >= batch_size:
                            batch_result = self._import_batch(batch_records, skip_existing)
                            imported_count += batch_result["imported"]
                            error_count += batch_result["errors"]
                            batch_records = []
                            
                            # Log progress
                            if imported_count % 10000 == 0:
                                logger.info(f"Import progress: {imported_count} records imported")
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON at line {line_num}: {e}")
                        error_count += 1
                        continue
                    except Exception as e:
                        logger.warning(f"Error processing line {line_num}: {e}")
                        error_count += 1
                        continue
                
                # Process remaining records in final batch
                if batch_records:
                    batch_result = self._import_batch(batch_records, skip_existing)
                    imported_count += batch_result["imported"]
                    error_count += batch_result["errors"]
            
            duration = time.time() - start_time
            
            logger.info(f"Import completed: {imported_count} imported, {skipped_count} skipped, {error_count} errors in {duration:.2f}s")
            
            return {
                "success": True,
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "total_processed": imported_count + skipped_count + error_count,
                "duration": duration,
                "input_path": str(input_path)
            }
            
        except Exception as e:
            logger.error(f"Error during data import: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
    
    def _import_batch(self, records: List[Dict[str, Any]], skip_existing: bool) -> Dict[str, int]:
        """Import a batch of records"""
        try:
            if skip_existing:
                # Use upsert for each record to handle duplicates
                imported = 0
                errors = 0
                
                for record in records:
                    try:
                        if "analysis_id" in record:
                            result = self.collection.replace_one(
                                {"analysis_id": record["analysis_id"]},
                                record,
                                upsert=True
                            )
                            if result.upserted_id or result.modified_count > 0:
                                imported += 1
                        else:
                            self.collection.insert_one(record)
                            imported += 1
                    except Exception as e:
                        logger.warning(f"Error importing record {record.get('analysis_id', 'unknown')}: {e}")
                        errors += 1
                
                return {"imported": imported, "errors": errors}
            else:
                # Bulk insert all records
                result = self.collection.insert_many(records, ordered=False)
                return {"imported": len(result.inserted_ids), "errors": 0}
                
        except Exception as e:
            logger.error(f"Error importing batch: {e}")
            return {"imported": 0, "errors": len(records)}


# Convenience functions for external use

def get_data_manager() -> HistoryDataManager:
    """Get a singleton instance of the data manager"""
    if not hasattr(get_data_manager, '_instance'):
        get_data_manager._instance = HistoryDataManager()
    return get_data_manager._instance


def cleanup_old_analysis_records(max_age_days: int = 365, dry_run: bool = False) -> Dict[str, Any]:
    """
    Convenience function to cleanup old analysis records
    
    Args:
        max_age_days: Maximum age of records to keep
        dry_run: If True, only count records without deleting
        
    Returns:
        Dict with cleanup results
    """
    manager = get_data_manager()
    return manager.cleanup_old_records(max_age_days=max_age_days, dry_run=dry_run)


def get_storage_usage_report() -> Dict[str, Any]:
    """
    Convenience function to get storage usage report
    
    Returns:
        Dict with storage statistics and alerts
    """
    manager = get_data_manager()
    stats = manager.get_storage_statistics()
    alerts = manager.check_storage_alerts()
    
    return {
        "statistics": stats,
        "alerts": alerts,
        "timestamp": datetime.now().isoformat()
    }


def export_analysis_history(output_path: Union[str, Path], 
                          filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function to export analysis history
    
    Args:
        output_path: Path to output file
        filters: Optional filters to apply
        
    Returns:
        Dict with export results
    """
    manager = get_data_manager()
    return manager.export_data(output_path=output_path, filters=filters)


def import_analysis_history(input_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Convenience function to import analysis history
    
    Args:
        input_path: Path to input file
        
    Returns:
        Dict with import results
    """
    manager = get_data_manager()
    return manager.import_data(input_path=input_path)