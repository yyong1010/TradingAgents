"""
Analysis History Configuration Utilities

This module provides configuration management and utilities for the analysis history system.
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import timedelta

logger = logging.getLogger(__name__)


class HistoryConfig:
    """Configuration manager for analysis history system"""
    
    # Default configuration values
    DEFAULT_CONFIG = {
        # Storage settings
        'collection_name': 'analysis_history',
        'enable_history': True,
        'auto_save_enabled': True,
        
        # Pagination settings
        'default_page_size': 20,
        'max_page_size': 100,
        
        # Retention settings
        'default_retention_days': 90,
        'max_retention_days': 365,
        'auto_cleanup_enabled': False,
        'cleanup_interval_hours': 24,
        
        # Performance settings
        'enable_caching': True,
        'cache_ttl_seconds': 300,  # 5 minutes
        'max_concurrent_operations': 10,
        
        # Search settings
        'enable_text_search': True,
        'search_result_limit': 100,
        
        # Export settings
        'enable_export': True,
        'max_export_records': 1000,
        'export_formats': ['markdown', 'pdf', 'docx'],
        
        # Security settings
        'enable_access_logging': True,
        'max_delete_batch_size': 50,
        
        # UI settings
        'default_sort_field': 'created_at',
        'default_sort_order': 'desc',
        'show_demo_data': False,
        'enable_bulk_operations': True
    }
    
    def __init__(self):
        """Initialize configuration"""
        self._config = self.DEFAULT_CONFIG.copy()
        self._load_from_environment()
    
    def _load_from_environment(self) -> None:
        """Load configuration from environment variables"""
        try:
            # Storage settings
            self._config['enable_history'] = self._get_bool_env('HISTORY_ENABLED', True)
            self._config['auto_save_enabled'] = self._get_bool_env('HISTORY_AUTO_SAVE', True)
            self._config['collection_name'] = os.getenv('HISTORY_COLLECTION_NAME', 'analysis_history')
            
            # Pagination settings
            self._config['default_page_size'] = self._get_int_env('HISTORY_PAGE_SIZE', 20, 1, 100)
            self._config['max_page_size'] = self._get_int_env('HISTORY_MAX_PAGE_SIZE', 100, 10, 500)
            
            # Retention settings
            self._config['default_retention_days'] = self._get_int_env('HISTORY_RETENTION_DAYS', 90, 1, 365)
            self._config['auto_cleanup_enabled'] = self._get_bool_env('HISTORY_AUTO_CLEANUP', False)
            self._config['cleanup_interval_hours'] = self._get_int_env('HISTORY_CLEANUP_INTERVAL', 24, 1, 168)
            
            # Performance settings
            self._config['enable_caching'] = self._get_bool_env('HISTORY_ENABLE_CACHE', True)
            self._config['cache_ttl_seconds'] = self._get_int_env('HISTORY_CACHE_TTL', 300, 60, 3600)
            
            # Search settings
            self._config['enable_text_search'] = self._get_bool_env('HISTORY_TEXT_SEARCH', True)
            self._config['search_result_limit'] = self._get_int_env('HISTORY_SEARCH_LIMIT', 100, 10, 1000)
            
            # Export settings
            self._config['enable_export'] = self._get_bool_env('HISTORY_ENABLE_EXPORT', True)
            self._config['max_export_records'] = self._get_int_env('HISTORY_MAX_EXPORT', 1000, 100, 10000)
            
            # Security settings
            self._config['enable_access_logging'] = self._get_bool_env('HISTORY_ACCESS_LOG', True)
            self._config['max_delete_batch_size'] = self._get_int_env('HISTORY_MAX_DELETE_BATCH', 50, 1, 100)
            
            # UI settings
            self._config['show_demo_data'] = self._get_bool_env('HISTORY_SHOW_DEMO', False)
            self._config['enable_bulk_operations'] = self._get_bool_env('HISTORY_BULK_OPS', True)
            
            logger.info("Successfully loaded history configuration from environment")
            
        except Exception as e:
            logger.warning(f"Error loading configuration from environment: {e}")
            logger.info("Using default configuration values")
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean value from environment variable"""
        value = os.getenv(key, '').lower()
        if value in ('true', '1', 'yes', 'on'):
            return True
        elif value in ('false', '0', 'no', 'off'):
            return False
        else:
            return default
    
    def _get_int_env(self, key: str, default: int, min_val: int = None, max_val: int = None) -> int:
        """Get integer value from environment variable with validation"""
        try:
            value = int(os.getenv(key, str(default)))
            if min_val is not None and value < min_val:
                logger.warning(f"Environment variable {key}={value} is below minimum {min_val}, using minimum")
                return min_val
            if max_val is not None and value > max_val:
                logger.warning(f"Environment variable {key}={value} is above maximum {max_val}, using maximum")
                return max_val
            return value
        except (ValueError, TypeError):
            logger.warning(f"Invalid integer value for {key}, using default {default}")
            return default
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self._config[key] = value
    
    def is_enabled(self) -> bool:
        """Check if history tracking is enabled"""
        return self._config.get('enable_history', True)
    
    def is_auto_save_enabled(self) -> bool:
        """Check if auto-save is enabled"""
        return self._config.get('auto_save_enabled', True)
    
    def get_page_size(self) -> int:
        """Get default page size"""
        return self._config.get('default_page_size', 20)
    
    def get_max_page_size(self) -> int:
        """Get maximum page size"""
        return self._config.get('max_page_size', 100)
    
    def get_retention_days(self) -> int:
        """Get retention period in days"""
        return self._config.get('default_retention_days', 90)
    
    def is_caching_enabled(self) -> bool:
        """Check if caching is enabled"""
        return self._config.get('enable_caching', True)
    
    def get_cache_ttl(self) -> int:
        """Get cache TTL in seconds"""
        return self._config.get('cache_ttl_seconds', 300)
    
    def is_export_enabled(self) -> bool:
        """Check if export is enabled"""
        return self._config.get('enable_export', True)
    
    def get_max_export_records(self) -> int:
        """Get maximum number of records for export"""
        return self._config.get('max_export_records', 1000)
    
    def get_supported_export_formats(self) -> list:
        """Get supported export formats"""
        return self._config.get('export_formats', ['markdown', 'pdf', 'docx'])
    
    def is_text_search_enabled(self) -> bool:
        """Check if text search is enabled"""
        return self._config.get('enable_text_search', True)
    
    def get_search_limit(self) -> int:
        """Get search result limit"""
        return self._config.get('search_result_limit', 100)
    
    def is_bulk_operations_enabled(self) -> bool:
        """Check if bulk operations are enabled"""
        return self._config.get('enable_bulk_operations', True)
    
    def get_max_delete_batch_size(self) -> int:
        """Get maximum batch size for delete operations"""
        return self._config.get('max_delete_batch_size', 50)
    
    def should_show_demo_data(self) -> bool:
        """Check if demo data should be shown"""
        return self._config.get('show_demo_data', False)
    
    def get_default_sort(self) -> tuple:
        """Get default sort field and order"""
        field = self._config.get('default_sort_field', 'created_at')
        order = self._config.get('default_sort_order', 'desc')
        return field, order
    
    def validate_page_size(self, page_size: int) -> int:
        """Validate and clamp page size"""
        max_size = self.get_max_page_size()
        return min(max(1, page_size), max_size)
    
    def validate_retention_days(self, days: int) -> int:
        """Validate and clamp retention days"""
        max_days = self._config.get('max_retention_days', 365)
        return min(max(1, days), max_days)
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration values"""
        return self._config.copy()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of key configuration values"""
        return {
            'history_enabled': self.is_enabled(),
            'auto_save_enabled': self.is_auto_save_enabled(),
            'page_size': self.get_page_size(),
            'retention_days': self.get_retention_days(),
            'caching_enabled': self.is_caching_enabled(),
            'export_enabled': self.is_export_enabled(),
            'text_search_enabled': self.is_text_search_enabled(),
            'bulk_operations_enabled': self.is_bulk_operations_enabled(),
            'collection_name': self.get('collection_name'),
            'supported_formats': self.get_supported_export_formats()
        }


# Global configuration instance
_config_instance: Optional[HistoryConfig] = None


def get_history_config() -> HistoryConfig:
    """
    Get the global history configuration instance
    
    Returns:
        HistoryConfig instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = HistoryConfig()
    return _config_instance


def validate_database_connection() -> Dict[str, Any]:
    """
    Validate database connection and return status
    
    Returns:
        Dictionary with connection status and details
    """
    try:
        from tradingagents.config.database_manager import get_database_manager
        
        db_manager = get_database_manager()
        
        # Get connection status
        mongodb_available = db_manager.is_mongodb_available()
        redis_available = db_manager.is_redis_available()
        
        # Get configuration details
        config = db_manager.get_config()
        
        status = {
            'mongodb': {
                'available': mongodb_available,
                'host': config['mongodb']['host'],
                'port': config['mongodb']['port'],
                'database': config['mongodb']['database'],
                'enabled': config['mongodb']['enabled']
            },
            'redis': {
                'available': redis_available,
                'host': config['redis']['host'],
                'port': config['redis']['port'],
                'enabled': config['redis']['enabled']
            },
            'overall_status': 'healthy' if mongodb_available else 'degraded',
            'history_storage_available': mongodb_available,
            'cache_available': redis_available
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Error validating database connection: {e}")
        return {
            'mongodb': {'available': False, 'error': str(e)},
            'redis': {'available': False, 'error': str(e)},
            'overall_status': 'error',
            'history_storage_available': False,
            'cache_available': False,
            'error': str(e)
        }


def get_storage_health_check() -> Dict[str, Any]:
    """
    Perform a comprehensive health check of the storage system
    
    Returns:
        Dictionary with health check results
    """
    try:
        from web.utils.history_storage import get_history_storage
        
        storage = get_history_storage()
        config = get_history_config()
        
        # Basic availability check
        storage_available = storage.is_available()
        
        # Get statistics if available
        stats = {}
        if storage_available:
            try:
                stats = storage.get_history_stats()
            except Exception as e:
                logger.warning(f"Could not get storage stats: {e}")
                stats = {'error': str(e)}
        
        # Database connection validation
        db_status = validate_database_connection()
        
        health_check = {
            'timestamp': logger.info,
            'storage_available': storage_available,
            'configuration': config.get_config_summary(),
            'database_status': db_status,
            'statistics': stats,
            'overall_health': 'healthy' if storage_available else 'degraded'
        }
        
        return health_check
        
    except Exception as e:
        logger.error(f"Error performing storage health check: {e}")
        return {
            'timestamp': logger.info,
            'storage_available': False,
            'overall_health': 'error',
            'error': str(e)
        }