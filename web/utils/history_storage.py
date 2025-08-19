"""
Analysis History Storage Service

This module provides the storage infrastructure for analysis history records,
including MongoDB collection management, indexing, and CRUD operations.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError, DuplicateKeyError, ConnectionFailure, ServerSelectionTimeoutError

from tradingagents.config.database_manager import get_database_manager
from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus
from web.utils.error_handler import (
    with_retry, with_error_handling, handle_storage_operation,
    ErrorHandler, show_error_to_user, show_loading_with_progress,
    log_operation_metrics
)

# Setup logging
logger = logging.getLogger(__name__)

# Import enhanced logging utilities
from web.utils.history_logging import (
    log_storage_operation, log_query_performance, log_database_health_check,
    log_cache_operation, create_debug_session, HistoryOperationLogger
)

# Import caching utilities
from web.utils.history_cache import get_cache_manager

# Import performance monitoring
from web.utils.history_performance import get_performance_monitor, PerformanceMetric, performance_timer

# Import optimized pagination
from web.utils.history_pagination import get_paginator


class AnalysisHistoryStorage:
    """
    Analysis History Storage Service
    
    Manages the storage and retrieval of analysis history records in MongoDB.
    Provides methods for saving, querying, updating, and deleting analysis records.
    """
    
    COLLECTION_NAME = "analysis_history"
    
    def __init__(self):
        """Initialize the storage service"""
        self.db_manager = get_database_manager()
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database] = None
        self.collection: Optional[Collection] = None
        
        # Initialize caching
        self.cache_manager = get_cache_manager()
        
        # Initialize performance monitoring
        self.performance_monitor = get_performance_monitor()
        
        # Initialize optimized pagination
        self.paginator = get_paginator()
        
        # Initialize database connection
        self._initialize_connection()
        
        # Create indexes if connection is available
        if self.collection is not None:
            self._create_indexes()
    
    @with_retry(
        max_attempts=3, 
        delay=2.0, 
        retry_on=(ConnectionFailure, ServerSelectionTimeoutError),
        show_user_feedback=False,
        operation_name="MongoDB连接初始化"
    )
    def _initialize_connection(self) -> None:
        """Initialize MongoDB connection and collection with enhanced retry logic and logging"""
        start_time = time.time()
        
        try:
            logger.info("开始初始化MongoDB连接...")
            
            if not self.db_manager.is_mongodb_available():
                logger.warning("MongoDB is not available. History storage will be disabled.")
                return
            
            self.client = self.db_manager.get_mongodb_client()
            if self.client is None:
                logger.error("Failed to get MongoDB client")
                return
            
            # Test connection with timeout and enhanced error handling
            logger.debug("Testing MongoDB connection...")
            try:
                self.client.admin.command('ping', maxTimeMS=5000)
                logger.debug("MongoDB ping successful")
            except Exception as ping_error:
                logger.error(f"MongoDB ping failed: {ping_error}")
                raise ConnectionFailure(f"MongoDB ping failed: {ping_error}")
            
            # Get database name from config with validation
            config = self.db_manager.get_config()
            if 'mongodb' not in config or 'database' not in config['mongodb']:
                raise ValueError("MongoDB database configuration is missing")
            
            db_name = config['mongodb']['database']
            if not db_name or not isinstance(db_name, str):
                raise ValueError("Invalid MongoDB database name in configuration")
            
            self.database = self.client[db_name]
            self.collection = self.database[self.COLLECTION_NAME]
            
            # Verify collection access
            try:
                self.collection.estimated_document_count()
                logger.debug(f"Collection '{self.COLLECTION_NAME}' access verified")
            except Exception as collection_error:
                logger.warning(f"Collection access verification failed: {collection_error}")
                # Continue anyway as collection might not exist yet
            
            duration = time.time() - start_time
            logger.info(f"Successfully connected to MongoDB database '{db_name}', collection '{self.COLLECTION_NAME}' ({duration:.2f}s)")
            
            # Log connection metrics
            log_operation_metrics(
                "mongodb_connection_init",
                duration,
                True,
                additional_metrics={
                    'database': db_name,
                    'collection': self.COLLECTION_NAME
                }
            )
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            duration = time.time() - start_time
            logger.error(f"MongoDB connection failed after {duration:.2f}s: {e}")
            
            # Log failure metrics
            log_operation_metrics(
                "mongodb_connection_init",
                duration,
                False,
                error=e
            )
            
            self.client = None
            self.database = None
            self.collection = None
            raise  # Re-raise for retry mechanism
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed to initialize MongoDB connection after {duration:.2f}s: {e}")
            
            # Log failure metrics
            log_operation_metrics(
                "mongodb_connection_init",
                duration,
                False,
                error=e,
                additional_metrics={'error_type': 'configuration_error'}
            )
            
            self.client = None
            self.database = None
            self.collection = None
    
    def _create_indexes(self) -> None:
        """Create optimized indexes for efficient querying and performance"""
        if self.collection is None:
            return
        
        try:
            # Create indexes for efficient querying with performance optimizations
            indexes_to_create = [
                # Unique index for analysis_id (primary key)
                {
                    'keys': [('analysis_id', ASCENDING)],
                    'options': {'unique': True, 'name': 'idx_analysis_id_unique'}
                },
                # Optimized compound index for stock symbol and date queries
                {
                    'keys': [('stock_symbol', ASCENDING), ('created_at', DESCENDING)],
                    'options': {'name': 'idx_stock_symbol_date', 'background': True}
                },
                # Primary date index for chronological queries
                {
                    'keys': [('created_at', DESCENDING)],
                    'options': {'name': 'idx_created_at_desc', 'background': True}
                },
                # Status filtering with date for efficient pagination
                {
                    'keys': [('status', ASCENDING), ('created_at', DESCENDING)],
                    'options': {'name': 'idx_status_date', 'background': True}
                },
                # Market type filtering with date
                {
                    'keys': [('market_type', ASCENDING), ('created_at', DESCENDING)],
                    'options': {'name': 'idx_market_type_date', 'background': True}
                },
                # Comprehensive compound index for complex queries
                {
                    'keys': [
                        ('market_type', ASCENDING),
                        ('status', ASCENDING),
                        ('created_at', DESCENDING)
                    ],
                    'options': {'name': 'idx_market_status_date', 'background': True}
                },
                # Analysis type filtering
                {
                    'keys': [('analysis_type', ASCENDING), ('created_at', DESCENDING)],
                    'options': {'name': 'idx_analysis_type_date', 'background': True}
                },
                # LLM provider analysis
                {
                    'keys': [('llm_provider', ASCENDING), ('created_at', DESCENDING)],
                    'options': {'name': 'idx_llm_provider_date', 'background': True}
                },
                # Performance metrics index
                {
                    'keys': [('execution_time', DESCENDING), ('created_at', DESCENDING)],
                    'options': {'name': 'idx_execution_time_date', 'background': True}
                },
                # Cost analysis index
                {
                    'keys': [('token_usage.total_cost', DESCENDING), ('created_at', DESCENDING)],
                    'options': {'name': 'idx_cost_date', 'background': True}
                },
                # Text index for full-text search
                {
                    'keys': [('stock_name', 'text'), ('stock_symbol', 'text')],
                    'options': {
                        'name': 'idx_text_search',
                        'background': True,
                        'weights': {'stock_name': 10, 'stock_symbol': 5}
                    }
                },
                # Sparse index for analysts used (only when field exists)
                {
                    'keys': [('analysts_used', ASCENDING)],
                    'options': {'name': 'idx_analysts_used', 'sparse': True, 'background': True}
                },
                # TTL index for automatic cleanup (if needed)
                # Uncomment if automatic cleanup is desired
                # {
                #     'keys': [('created_at', ASCENDING)],
                #     'options': {
                #         'name': 'idx_ttl_cleanup',
                #         'expireAfterSeconds': 365 * 24 * 60 * 60,  # 1 year
                #         'background': True
                #     }
                # }
            ]
            
            # Create each index
            for index_spec in indexes_to_create:
                try:
                    self.collection.create_index(
                        index_spec['keys'],
                        **index_spec['options']
                    )
                    logger.debug(f"Created index: {index_spec['options']['name']}")
                except Exception as e:
                    # Index might already exist, which is fine
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to create index {index_spec['options']['name']}: {e}")
            
            logger.info("Successfully created/verified all database indexes")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
    
    def is_available(self) -> bool:
        """Check if the storage service is available"""
        return self.collection is not None
    
    @performance_timer("save_analysis")
    @log_storage_operation("save_analysis")
    @with_error_handling(context="保存分析记录", show_user_error=False)
    @with_retry(
        max_attempts=3, 
        delay=1.0, 
        retry_on=(ConnectionFailure, ServerSelectionTimeoutError),
        show_user_feedback=False,
        operation_name="保存分析记录"
    )
    def save_analysis(self, record: AnalysisHistoryRecord) -> bool:
        """
        Save an analysis record to the database with comprehensive error handling
        
        Args:
            record: AnalysisHistoryRecord to save
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if not self.is_available():
            logger.warning("Storage service not available, cannot save analysis")
            return False
        
        try:
            # Validate the record
            record.validate()
            
            # Convert to dictionary for storage
            doc = record.to_dict()
            
            # Add retry metadata
            doc['_retry_count'] = getattr(record, '_retry_count', 0)
            doc['_last_save_attempt'] = datetime.now()
            
            # Insert the document with write concern for reliability
            result = self.collection.insert_one(doc)
            
            if result.inserted_id:
                logger.info(f"Successfully saved analysis record: {record.analysis_id}")
                
                # Cache the record for faster retrieval
                self.cache_manager.cache_record(record)
                
                # Invalidate query cache since new data was added
                self.cache_manager.invalidate_query_cache()
                
                return True
            else:
                logger.error(f"Failed to save analysis record: {record.analysis_id}")
                return False
                
        except DuplicateKeyError:
            logger.warning(f"Analysis record already exists: {record.analysis_id}")
            # Try to update existing record instead
            try:
                update_result = self.collection.replace_one(
                    {'analysis_id': record.analysis_id},
                    record.to_dict()
                )
                if update_result.modified_count > 0:
                    logger.info(f"Updated existing analysis record: {record.analysis_id}")
                    
                    # Update cache with new data
                    self.cache_manager.cache_record(record)
                    
                    # Invalidate query cache since data was updated
                    self.cache_manager.invalidate_query_cache()
                    
                    return True
                else:
                    logger.warning(f"No changes made to existing record: {record.analysis_id}")
                    return True  # Record exists and is identical
            except Exception as update_error:
                logger.error(f"Failed to update existing record {record.analysis_id}: {update_error}")
                return False
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Connection error saving analysis record {record.analysis_id}: {e}")
            raise  # Re-raise for retry mechanism
        except Exception as e:
            logger.error(f"Error saving analysis record {record.analysis_id}: {e}")
            return False
    
    @performance_timer("get_analysis_by_id")
    @with_error_handling(context="获取分析记录", show_user_error=False)
    @with_retry(max_attempts=2, delay=0.5, retry_on=(ConnectionFailure, ServerSelectionTimeoutError))
    def get_analysis_by_id(self, analysis_id: str) -> Optional[AnalysisHistoryRecord]:
        """
        Retrieve an analysis record by its ID with caching and error handling
        
        Args:
            analysis_id: The analysis ID to search for
            
        Returns:
            AnalysisHistoryRecord if found, None otherwise
        """
        if not analysis_id or not isinstance(analysis_id, str):
            logger.warning(f"Invalid analysis_id provided: {analysis_id}")
            return None
        
        # Try cache first
        cached_record = self.cache_manager.get_cached_record(analysis_id)
        if cached_record:
            logger.debug(f"Retrieved record from cache: {analysis_id}")
            return cached_record
        
        if not self.is_available():
            logger.warning("Storage service not available, cannot retrieve analysis")
            return None
        
        try:
            doc = self.collection.find_one(
                {'analysis_id': analysis_id},
                max_time_ms=5000  # 5 second timeout
            )
            
            if doc:
                # Remove MongoDB's _id field and other internal fields
                doc.pop('_id', None)
                doc.pop('_retry_count', None)
                doc.pop('_last_save_attempt', None)
                
                try:
                    record = AnalysisHistoryRecord.from_dict(doc)
                    
                    # Cache the record for future requests
                    self.cache_manager.cache_record(record)
                    
                    return record
                except Exception as parse_error:
                    logger.error(f"Error parsing analysis record {analysis_id}: {parse_error}")
                    return None
            else:
                logger.debug(f"Analysis record not found: {analysis_id}")
                return None
                
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Connection error retrieving analysis record {analysis_id}: {e}")
            raise  # Re-raise for retry mechanism
        except Exception as e:
            logger.error(f"Error retrieving analysis record {analysis_id}: {e}")
            return None
    
    @performance_timer("get_user_history")
    @log_storage_operation("get_user_history")
    @with_error_handling(context="获取历史记录列表", show_user_error=False)
    @with_retry(
        max_attempts=2, 
        delay=0.5, 
        retry_on=(ConnectionFailure, ServerSelectionTimeoutError),
        show_user_feedback=False,
        operation_name="获取历史记录"
    )
    def get_user_history(self, 
                        filters: Optional[Dict[str, Any]] = None,
                        page: int = 1,
                        page_size: int = 20,
                        sort_by: str = 'created_at',
                        sort_order: int = -1) -> Tuple[List[AnalysisHistoryRecord], int]:
        """
        Retrieve user's analysis history with filtering and pagination
        
        Args:
            filters: Optional filters to apply
            page: Page number (1-based)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_order: Sort order (1 for ascending, -1 for descending)
            
        Returns:
            Tuple of (records, total_count)
        """
        if not self.is_available():
            logger.warning("Storage service not available, cannot retrieve history")
            return [], 0
        
        # Validate input parameters
        try:
            page = max(1, int(page))
            page_size = max(1, min(100, int(page_size)))  # Limit page size to prevent memory issues
            sort_order = 1 if sort_order > 0 else -1
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid pagination parameters: {e}")
            return [], 0
        
        try:
            query_start_time = time.time()
            
            # Build query from filters with validation
            query = self._build_query(filters or {})
            
            # Try cache first for query results
            cached_result = self.cache_manager.get_cached_query_result(
                filters or {}, page, page_size, sort_by, sort_order
            )
            if cached_result:
                records, total_count = cached_result
                logger.debug(f"Retrieved {len(records)} records from cache (page {page}, total {total_count})")
                return records, total_count
            
            # Log query details for debugging
            logger.debug(f"Executing history query: {query}")
            logger.debug(f"Query parameters: page={page}, page_size={page_size}, sort_by={sort_by}, sort_order={sort_order}")
            
            # Add query timeout and performance hints
            query_options = {
                'max_time_ms': 10000,  # 10 second timeout
                'hint': [('created_at', -1)]  # Use index hint for better performance
            }
            
            # Get total count with timeout and performance logging
            count_start_time = time.time()
            total_count = self.collection.count_documents(query, maxTimeMS=5000)
            count_duration = time.time() - count_start_time
            
            logger.debug(f"Count query completed in {count_duration:.3f}s, found {total_count} total records")
            
            # Calculate skip value
            skip = (page - 1) * page_size
            
            # Execute query with pagination and sorting
            find_start_time = time.time()
            cursor = self.collection.find(query, **query_options).sort(sort_by, sort_order).skip(skip).limit(page_size)
            find_duration = time.time() - find_start_time
            
            logger.debug(f"Find query setup completed in {find_duration:.3f}s")
            
            # Convert documents to records with error handling
            records = []
            parse_errors = 0
            
            for doc in cursor:
                try:
                    # Remove MongoDB internal fields
                    doc.pop('_id', None)
                    doc.pop('_retry_count', None)
                    doc.pop('_last_save_attempt', None)
                    
                    record = AnalysisHistoryRecord.from_dict(doc)
                    records.append(record)
                except Exception as e:
                    parse_errors += 1
                    logger.warning(f"Failed to parse record {doc.get('analysis_id', 'unknown')}: {e}")
                    
                    # If too many parse errors, something is seriously wrong
                    if parse_errors > 5:
                        logger.error("Too many parse errors, stopping record processing")
                        break
                    continue
            
            if parse_errors > 0:
                logger.warning(f"Encountered {parse_errors} parse errors while retrieving history")
            
            # Log performance metrics
            total_duration = time.time() - query_start_time
            log_query_performance(
                "get_user_history",
                total_duration,
                len(records),
                filters,
                None
            )
            
            # Cache the query result for future requests
            self.cache_manager.cache_query_result(
                filters or {}, page, page_size, sort_by, sort_order, records, total_count
            )
            
            logger.debug(f"Retrieved {len(records)} records (page {page}, total {total_count}) in {total_duration:.3f}s")
            return records, total_count
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            # Log performance metrics for failed queries
            if 'query_start_time' in locals():
                total_duration = time.time() - query_start_time
                log_query_performance(
                    "get_user_history",
                    total_duration,
                    0,
                    filters,
                    e
                )
            
            logger.error(f"Connection error retrieving user history: {e}")
            raise  # Re-raise for retry mechanism
        except Exception as e:
            # Log performance metrics for failed queries
            if 'query_start_time' in locals():
                total_duration = time.time() - query_start_time
                log_query_performance(
                    "get_user_history",
                    total_duration,
                    0,
                    filters,
                    e
                )
            
            logger.error(f"Error retrieving user history: {e}")
            return [], 0
    
    def _build_query(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build MongoDB query from filters with proper type handling
        
        Args:
            filters: Filter parameters
            
        Returns:
            MongoDB query dictionary
        """
        query = {}
        
        # Handle direct MongoDB query filters (from get_user_history calls)
        for key, value in filters.items():
            if key in ['stock_symbol', 'stock_name', 'market_type', 'status', 'analysis_type', 'created_at', 'analysts_used', '$text', '$or']:
                # Validate regex patterns
                if isinstance(value, dict) and '$regex' in value:
                    if isinstance(value['$regex'], str):
                        query[key] = value
                    else:
                        # Skip invalid regex patterns
                        logger.warning(f"Invalid regex pattern for {key}: {value['$regex']}")
                        continue
                else:
                    query[key] = value
                continue
        
        # Legacy filter handling for backward compatibility
        # Stock symbol filter
        if 'stock_symbol' in filters and filters['stock_symbol'] and isinstance(filters['stock_symbol'], str):
            if 'stock_symbol' not in query:  # Don't override if already set above
                query['stock_symbol'] = {'$regex': filters['stock_symbol'], '$options': 'i'}
        
        # Stock name filter
        if 'stock_name' in filters and filters['stock_name'] and isinstance(filters['stock_name'], str):
            if 'stock_name' not in query:  # Don't override if already set above
                query['stock_name'] = {'$regex': filters['stock_name'], '$options': 'i'}
        
        # Market type filter
        if 'market_type' in filters and filters['market_type'] and isinstance(filters['market_type'], str):
            if 'market_type' not in query:  # Don't override if already set above
                query['market_type'] = filters['market_type']
        
        # Status filter
        if 'status' in filters and filters['status'] and isinstance(filters['status'], str):
            if 'status' not in query:  # Don't override if already set above
                query['status'] = filters['status']
        
        # Date range filter (legacy format)
        if ('date_from' in filters or 'date_to' in filters) and 'created_at' not in query:
            date_query = {}
            if 'date_from' in filters and filters['date_from']:
                date_query['$gte'] = filters['date_from']
            if 'date_to' in filters and filters['date_to']:
                # Add one day to include the entire end date
                end_date = filters['date_to']
                if isinstance(end_date, datetime):
                    end_date = end_date + timedelta(days=1)
                date_query['$lt'] = end_date
            
            if date_query:
                query['created_at'] = date_query
        
        # Analysis type filter
        if 'analysis_type' in filters and filters['analysis_type'] and isinstance(filters['analysis_type'], str):
            if 'analysis_type' not in query:  # Don't override if already set above
                query['analysis_type'] = filters['analysis_type']
        
        # Analysts filter
        if 'analysts' in filters and filters['analysts'] and isinstance(filters['analysts'], list):
            if 'analysts_used' not in query:  # Don't override if already set above
                query['analysts_used'] = {'$in': filters['analysts']}
        
        # Text search
        if 'search_text' in filters and filters['search_text'] and isinstance(filters['search_text'], str):
            if '$text' not in query:  # Don't override if already set above
                query['$text'] = {'$search': filters['search_text']}
        
        return query
    
    @with_error_handling(context="删除分析记录", show_user_error=False)
    @with_retry(max_attempts=2, delay=1.0, retry_on=(ConnectionFailure, ServerSelectionTimeoutError))
    def delete_analysis(self, analysis_id: str) -> bool:
        """
        Delete an analysis record with comprehensive error handling
        
        Args:
            analysis_id: The analysis ID to delete
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not self.is_available():
            logger.warning("Storage service not available, cannot delete analysis")
            return False
        
        if not analysis_id or not isinstance(analysis_id, str):
            logger.warning(f"Invalid analysis_id provided for deletion: {analysis_id}")
            return False
        
        try:
            # First check if record exists
            existing_record = self.collection.find_one(
                {'analysis_id': analysis_id}, 
                {'_id': 1},  # Only fetch _id field
                max_time_ms=3000
            )
            
            if not existing_record:
                logger.warning(f"Analysis record not found for deletion: {analysis_id}")
                return False
            
            # Perform deletion with write concern
            result = self.collection.delete_one(
                {'analysis_id': analysis_id},
                max_time_ms=5000
            )
            
            if result.deleted_count > 0:
                logger.info(f"Successfully deleted analysis record: {analysis_id}")
                
                # Invalidate cache entries
                self.cache_manager.invalidate_record(analysis_id)
                self.cache_manager.invalidate_query_cache()
                
                return True
            else:
                logger.warning(f"Analysis record not found for deletion: {analysis_id}")
                return False
                
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Connection error deleting analysis record {analysis_id}: {e}")
            raise  # Re-raise for retry mechanism
        except Exception as e:
            logger.error(f"Error deleting analysis record {analysis_id}: {e}")
            return False
    
    def delete_multiple_analyses(self, analysis_ids: List[str]) -> int:
        """
        Delete multiple analysis records
        
        Args:
            analysis_ids: List of analysis IDs to delete
            
        Returns:
            int: Number of records deleted
        """
        if not self.is_available():
            logger.warning("Storage service not available, cannot delete analyses")
            return 0
        
        try:
            result = self.collection.delete_many({'analysis_id': {'$in': analysis_ids}})
            deleted_count = result.deleted_count
            
            logger.info(f"Successfully deleted {deleted_count} analysis records")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting multiple analysis records: {e}")
            return 0
    
    def update_analysis_status(self, analysis_id: str, status: str) -> bool:
        """
        Update the status of an analysis record
        
        Args:
            analysis_id: The analysis ID to update
            status: New status value
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        if not self.is_available():
            logger.warning("Storage service not available, cannot update analysis")
            return False
        
        try:
            # Validate status
            valid_statuses = [s.value for s in AnalysisStatus]
            if status not in valid_statuses:
                logger.error(f"Invalid status: {status}")
                return False
            
            result = self.collection.update_one(
                {'analysis_id': analysis_id},
                {
                    '$set': {
                        'status': status,
                        'updated_at': datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Successfully updated analysis status: {analysis_id} -> {status}")
                return True
            else:
                logger.warning(f"Analysis record not found for update: {analysis_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating analysis status {analysis_id}: {e}")
            return False
    
    def get_history_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the analysis history with caching
        
        Returns:
            Dictionary containing various statistics
        """
        # Try cache first
        cached_stats = self.cache_manager.get_cached_stats()
        if cached_stats:
            logger.debug("Retrieved statistics from cache")
            return cached_stats
        
        if not self.is_available():
            return {
                'total_analyses': 0,
                'completed_analyses': 0,
                'failed_analyses': 0,
                'recent_analyses': 0,
                'total_cost': 0.0,
                'avg_execution_time': 0.0,
                'storage_available': False
            }
        
        try:
            stats_start_time = time.time()
            
            # Basic counts
            total_analyses = self.collection.count_documents({})
            completed_analyses = self.collection.count_documents({'status': AnalysisStatus.COMPLETED.value})
            failed_analyses = self.collection.count_documents({'status': AnalysisStatus.FAILED.value})
            
            # Recent analyses (last 7 days)
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_analyses = self.collection.count_documents({
                'created_at': {'$gte': seven_days_ago}
            })
            
            # Aggregation for cost and execution time
            pipeline = [
                {
                    '$group': {
                        '_id': None,
                        'total_cost': {'$sum': '$token_usage.total_cost'},
                        'avg_execution_time': {'$avg': '$execution_time'},
                        'total_execution_time': {'$sum': '$execution_time'}
                    }
                }
            ]
            
            agg_result = list(self.collection.aggregate(pipeline))
            
            if agg_result:
                stats = agg_result[0]
                total_cost = stats.get('total_cost', 0.0) or 0.0
                avg_execution_time = stats.get('avg_execution_time', 0.0) or 0.0
                total_execution_time = stats.get('total_execution_time', 0.0) or 0.0
            else:
                total_cost = 0.0
                avg_execution_time = 0.0
                total_execution_time = 0.0
            
            # Market type distribution
            market_pipeline = [
                {'$group': {'_id': '$market_type', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}}
            ]
            market_stats = list(self.collection.aggregate(market_pipeline))
            
            # Status distribution
            status_pipeline = [
                {'$group': {'_id': '$status', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}}
            ]
            status_stats = list(self.collection.aggregate(status_pipeline))
            
            # LLM provider distribution
            llm_pipeline = [
                {'$group': {'_id': '$llm_provider', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}}
            ]
            llm_stats = list(self.collection.aggregate(llm_pipeline))
            
            # Daily analysis trend (last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            daily_pipeline = [
                {
                    '$match': {
                        'created_at': {'$gte': thirty_days_ago}
                    }
                },
                {
                    '$group': {
                        '_id': {
                            '$dateToString': {
                                'format': '%Y-%m-%d',
                                'date': '$created_at'
                            }
                        },
                        'count': {'$sum': 1}
                    }
                },
                {'$sort': {'_id': 1}}
            ]
            daily_stats = list(self.collection.aggregate(daily_pipeline))
            
            stats_duration = time.time() - stats_start_time
            logger.debug(f"Statistics calculation completed in {stats_duration:.3f}s")
            
            stats_result = {
                'total_analyses': total_analyses,
                'completed_analyses': completed_analyses,
                'failed_analyses': failed_analyses,
                'recent_analyses': recent_analyses,
                'success_rate': (completed_analyses / total_analyses * 100) if total_analyses > 0 else 0,
                'total_cost': total_cost,
                'avg_execution_time': avg_execution_time,
                'total_execution_time': total_execution_time,
                'market_distribution': {item['_id']: item['count'] for item in market_stats},
                'status_distribution': {item['_id']: item['count'] for item in status_stats},
                'llm_distribution': {item['_id']: item['count'] for item in llm_stats},
                'daily_trend': {item['_id']: item['count'] for item in daily_stats},
                'storage_available': True,
                'calculation_time': stats_duration
            }
            
            # Cache the statistics for future requests
            self.cache_manager.cache_stats(stats_result)
            
            return stats_result
            
        except Exception as e:
            logger.error(f"Error getting history stats: {e}")
            return {
                'total_analyses': 0,
                'completed_analyses': 0,
                'failed_analyses': 0,
                'recent_analyses': 0,
                'total_cost': 0.0,
                'avg_execution_time': 0.0,
                'storage_available': True,
                'error': str(e)
            }
    
    def cleanup_old_records(self, days_to_keep: int = 90) -> int:
        """
        Clean up old analysis records
        
        Args:
            days_to_keep: Number of days to keep records for
            
        Returns:
            int: Number of records deleted
        """
        if not self.is_available():
            logger.warning("Storage service not available, cannot cleanup records")
            return 0
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            result = self.collection.delete_many({
                'created_at': {'$lt': cutoff_date}
            })
            
            deleted_count = result.deleted_count
            logger.info(f"Cleaned up {deleted_count} old analysis records (older than {days_to_keep} days)")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
            return 0
    
    def get_cache_metrics(self) -> Dict[str, Any]:
        """
        Get cache performance metrics
        
        Returns:
            Dictionary containing cache metrics
        """
        return self.cache_manager.get_cache_metrics()
    
    def warm_cache_with_recent_records(self, limit: int = 100) -> int:
        """
        Warm the cache with recent analysis records
        
        Args:
            limit: Number of recent records to cache
            
        Returns:
            int: Number of records cached
        """
        if not self.is_available():
            return 0
        
        try:
            # Get recent records
            cursor = self.collection.find(
                {},
                sort=[('created_at', -1)],
                limit=limit
            )
            
            recent_records = []
            for doc in cursor:
                try:
                    # Remove MongoDB internal fields
                    doc.pop('_id', None)
                    doc.pop('_retry_count', None)
                    doc.pop('_last_save_attempt', None)
                    
                    record = AnalysisHistoryRecord.from_dict(doc)
                    recent_records.append(record)
                except Exception as e:
                    logger.warning(f"Failed to parse record for cache warming: {e}")
                    continue
            
            # Warm the cache
            cached_count = self.cache_manager.warm_cache(recent_records)
            logger.info(f"Cache warmed with {cached_count} recent records")
            
            return cached_count
            
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
            return 0
    
    def clear_cache(self) -> int:
        """
        Clear all cache entries
        
        Returns:
            int: Number of entries cleared
        """
        return self.cache_manager.clear_all_cache()
    
    def cleanup_cache(self) -> int:
        """
        Clean up expired cache entries
        
        Returns:
            int: Number of entries cleaned up
        """
        return self.cache_manager.cleanup_expired_cache()
    
    def get_user_history_optimized(self, 
                                  filters: Optional[Dict[str, Any]] = None,
                                  page: int = 1,
                                  page_size: Optional[int] = None,
                                  sort_by: str = 'created_at',
                                  sort_order: int = -1) -> Dict[str, Any]:
        """
        Get user history with optimized pagination and caching
        
        Args:
            filters: Optional filters to apply
            page: Page number (1-based)
            page_size: Number of records per page (None for adaptive)
            sort_by: Field to sort by
            sort_order: Sort order (1 for ascending, -1 for descending)
            
        Returns:
            Dictionary containing paginated results and metadata
        """
        # Use the optimized paginator
        result = self.paginator.paginate(
            query_func=self.get_user_history,
            filters=filters or {},
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return {
            'records': result.records,
            'pagination': {
                'current_page': result.current_page,
                'page_size': result.page_size,
                'total_count': result.total_count,
                'total_pages': result.total_pages,
                'has_next': result.has_next,
                'has_previous': result.has_previous
            },
            'performance': {
                'cache_hit': result.cache_hit,
                'query_time': result.query_time,
                'optimization_applied': result.optimization_applied
            }
        }
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get comprehensive performance report
        
        Returns:
            Dictionary containing performance metrics and recommendations
        """
        # Get cache metrics
        cache_metrics = self.cache_manager.get_cache_metrics()
        
        # Get performance monitor stats
        perf_stats = self.performance_monitor.get_overall_stats()
        
        # Get pagination stats
        pagination_stats = self.paginator.get_performance_stats()
        
        # Get slow queries
        slow_queries = self.performance_monitor.get_slow_queries(5)
        
        # Get recommendations
        recommendations = self.performance_monitor.get_performance_recommendations()
        
        return {
            'cache_metrics': cache_metrics,
            'performance_stats': perf_stats,
            'pagination_stats': pagination_stats,
            'slow_queries': slow_queries,
            'recommendations': recommendations,
            'storage_available': self.is_available(),
            'report_timestamp': datetime.now().isoformat()
        }


# Global storage instance
_storage_instance: Optional[AnalysisHistoryStorage] = None


def get_history_storage() -> AnalysisHistoryStorage:
    """
    Get the global history storage instance
    
    Returns:
        AnalysisHistoryStorage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = AnalysisHistoryStorage()
    return _storage_instance