#!/usr/bin/env python3
"""
Analysis History Scheduled Cleanup Service

This script provides automated cleanup and maintenance operations for analysis history data.
It can be run as a cron job or scheduled task to perform regular maintenance.
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.logging_manager import get_logger
from web.utils.history_data_manager import get_data_manager

# Setup logging
logger = get_logger('history_scheduler')


class HistoryScheduler:
    """Automated history maintenance scheduler"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize the scheduler
        
        Args:
            config_path: Path to configuration file (optional)
        """
        self.data_manager = get_data_manager()
        self.config = self._load_config(config_path)
        self.results = []
    
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load scheduler configuration"""
        default_config = {
            "cleanup": {
                "enabled": True,
                "max_age_days": 365,
                "batch_size": 100,
                "cleanup_failed_records": True,
                "failed_record_age_hours": 24
            },
            "monitoring": {
                "enabled": True,
                "max_size_mb": 1000,
                "max_documents": 100000,
                "max_daily_growth": 1000,
                "alert_on_warnings": False
            },
            "backup": {
                "enabled": False,
                "backup_path": "data/backups/history",
                "backup_frequency_days": 7,
                "compress_backups": True,
                "keep_backups": 4
            },
            "notifications": {
                "enabled": False,
                "log_level": "INFO",
                "email_alerts": False,
                "webhook_url": None
            }
        }
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                
                # Merge user config with defaults
                def merge_config(default, user):
                    for key, value in user.items():
                        if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                            merge_config(default[key], value)
                        else:
                            default[key] = value
                
                merge_config(default_config, user_config)
                logger.info(f"Loaded configuration from {config_path}")
                
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
                logger.info("Using default configuration")
        
        return default_config
    
    def run_cleanup(self) -> Dict[str, Any]:
        """Run cleanup operations"""
        if not self.config["cleanup"]["enabled"]:
            logger.info("Cleanup is disabled in configuration")
            return {"success": True, "skipped": True, "reason": "disabled"}
        
        logger.info("🧹 Starting scheduled cleanup operations...")
        
        results = {
            "success": True,
            "operations": [],
            "total_deleted": 0,
            "errors": []
        }
        
        try:
            # Cleanup old records
            cleanup_result = self.data_manager.cleanup_old_records(
                max_age_days=self.config["cleanup"]["max_age_days"],
                batch_size=self.config["cleanup"]["batch_size"],
                dry_run=False
            )
            
            if cleanup_result["success"]:
                deleted_count = cleanup_result.get("deleted_count", 0)
                results["operations"].append({
                    "type": "old_records_cleanup",
                    "success": True,
                    "deleted_count": deleted_count,
                    "duration": cleanup_result.get("duration", 0)
                })
                results["total_deleted"] += deleted_count
                
                if deleted_count > 0:
                    logger.info(f"✅ Cleaned up {deleted_count} old records")
                else:
                    logger.info("✅ No old records found for cleanup")
            else:
                error_msg = cleanup_result.get("error", "Unknown error")
                results["errors"].append(f"Old records cleanup failed: {error_msg}")
                logger.error(f"❌ Old records cleanup failed: {error_msg}")
            
            # Cleanup failed records if enabled
            if self.config["cleanup"]["cleanup_failed_records"]:
                failed_cleanup_result = self.data_manager.cleanup_failed_records(
                    max_age_hours=self.config["cleanup"]["failed_record_age_hours"],
                    dry_run=False
                )
                
                if failed_cleanup_result["success"]:
                    failed_deleted = failed_cleanup_result.get("deleted_count", 0)
                    results["operations"].append({
                        "type": "failed_records_cleanup",
                        "success": True,
                        "deleted_count": failed_deleted,
                        "duration": failed_cleanup_result.get("duration", 0)
                    })
                    results["total_deleted"] += failed_deleted
                    
                    if failed_deleted > 0:
                        logger.info(f"✅ Cleaned up {failed_deleted} failed records")
                    else:
                        logger.info("✅ No failed records found for cleanup")
                else:
                    error_msg = failed_cleanup_result.get("error", "Unknown error")
                    results["errors"].append(f"Failed records cleanup failed: {error_msg}")
                    logger.error(f"❌ Failed records cleanup failed: {error_msg}")
        
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Cleanup operation failed: {str(e)}")
            logger.error(f"❌ Cleanup operation failed: {e}")
        
        return results
    
    def run_monitoring(self) -> Dict[str, Any]:
        """Run monitoring and alerting"""
        if not self.config["monitoring"]["enabled"]:
            logger.info("Monitoring is disabled in configuration")
            return {"success": True, "skipped": True, "reason": "disabled"}
        
        logger.info("🔍 Starting scheduled monitoring...")
        
        try:
            # Get storage statistics
            stats = self.data_manager.get_storage_statistics()
            if not stats["success"]:
                return {
                    "success": False,
                    "error": f"Failed to get storage statistics: {stats.get('error', 'Unknown error')}"
                }
            
            # Check for alerts
            alerts = self.data_manager.check_storage_alerts(
                max_size_mb=self.config["monitoring"]["max_size_mb"],
                max_documents=self.config["monitoring"]["max_documents"],
                max_daily_growth=self.config["monitoring"]["max_daily_growth"]
            )
            
            if not alerts["success"]:
                return {
                    "success": False,
                    "error": f"Failed to check storage alerts: {alerts.get('error', 'Unknown error')}"
                }
            
            # Log current status
            storage_info = stats["storage_info"]
            logger.info(f"📊 Current storage: {storage_info['total_documents']:,} documents, {storage_info['total_size_mb']:.2f} MB")
            
            # Handle alerts
            alert_triggered = False
            if alerts["alert_count"] > 0:
                alert_triggered = True
                logger.error(f"🚨 Found {alerts['alert_count']} storage alerts:")
                for alert in alerts["alerts"]:
                    logger.error(f"  - {alert['message']}")
            
            # Handle warnings
            warning_triggered = False
            if alerts["warning_count"] > 0:
                warning_triggered = True
                if self.config["monitoring"]["alert_on_warnings"]:
                    alert_triggered = True
                
                logger.warning(f"⚠️ Found {alerts['warning_count']} storage warnings:")
                for warning in alerts["warnings"]:
                    logger.warning(f"  - {warning['message']}")
            
            if not alert_triggered and not warning_triggered:
                logger.info("✅ All monitoring checks passed")
            
            return {
                "success": True,
                "storage_stats": storage_info,
                "alert_count": alerts["alert_count"],
                "warning_count": alerts["warning_count"],
                "alerts": alerts["alerts"],
                "warnings": alerts["warnings"],
                "alert_triggered": alert_triggered
            }
            
        except Exception as e:
            logger.error(f"❌ Monitoring operation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def run_backup(self) -> Dict[str, Any]:
        """Run backup operations"""
        if not self.config["backup"]["enabled"]:
            logger.info("Backup is disabled in configuration")
            return {"success": True, "skipped": True, "reason": "disabled"}
        
        logger.info("💾 Starting scheduled backup...")
        
        try:
            backup_dir = Path(self.config["backup"]["backup_path"])
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if backup is needed based on frequency
            frequency_days = self.config["backup"]["backup_frequency_days"]
            last_backup_file = None
            
            # Find the most recent backup
            for backup_file in backup_dir.glob("history_backup_*.json*"):
                if last_backup_file is None or backup_file.stat().st_mtime > last_backup_file.stat().st_mtime:
                    last_backup_file = backup_file
            
            if last_backup_file:
                last_backup_time = datetime.fromtimestamp(last_backup_file.stat().st_mtime)
                if datetime.now() - last_backup_time < timedelta(days=frequency_days):
                    logger.info(f"✅ Backup not needed (last backup: {last_backup_time.strftime('%Y-%m-%d %H:%M:%S')})")
                    return {
                        "success": True,
                        "skipped": True,
                        "reason": "not_needed",
                        "last_backup": last_backup_time.isoformat()
                    }
            
            # Create backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"history_backup_{timestamp}.json"
            if self.config["backup"]["compress_backups"]:
                backup_filename += ".gz"
            
            backup_path = backup_dir / backup_filename
            
            # Perform backup
            backup_result = self.data_manager.export_data(
                output_path=backup_path,
                filters=None,  # Backup all data
                compress=self.config["backup"]["compress_backups"]
            )
            
            if backup_result["success"]:
                logger.info(f"✅ Backup completed: {backup_result['exported_count']:,} records exported to {backup_path}")
                
                # Clean up old backups
                self._cleanup_old_backups(backup_dir)
                
                return {
                    "success": True,
                    "backup_path": str(backup_path),
                    "exported_count": backup_result["exported_count"],
                    "file_size_mb": backup_result["file_size_mb"],
                    "duration": backup_result["duration"]
                }
            else:
                error_msg = backup_result.get("error", "Unknown error")
                logger.error(f"❌ Backup failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"❌ Backup operation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _cleanup_old_backups(self, backup_dir: Path) -> None:
        """Clean up old backup files"""
        try:
            keep_backups = self.config["backup"]["keep_backups"]
            backup_files = sorted(
                backup_dir.glob("history_backup_*.json*"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            if len(backup_files) > keep_backups:
                files_to_delete = backup_files[keep_backups:]
                for backup_file in files_to_delete:
                    backup_file.unlink()
                    logger.info(f"🗑️ Deleted old backup: {backup_file.name}")
                
                logger.info(f"✅ Cleaned up {len(files_to_delete)} old backup files")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")
    
    def run_all(self) -> Dict[str, Any]:
        """Run all scheduled operations"""
        logger.info("🚀 Starting scheduled history maintenance operations...")
        
        start_time = datetime.now()
        
        # Check if data manager is available
        if not self.data_manager.is_available():
            logger.error("❌ Data manager is not available. Skipping all operations.")
            return {
                "success": False,
                "error": "Data manager not available",
                "timestamp": start_time.isoformat()
            }
        
        results = {
            "success": True,
            "timestamp": start_time.isoformat(),
            "operations": {}
        }
        
        # Run cleanup
        cleanup_result = self.run_cleanup()
        results["operations"]["cleanup"] = cleanup_result
        if not cleanup_result["success"] and not cleanup_result.get("skipped"):
            results["success"] = False
        
        # Run monitoring
        monitoring_result = self.run_monitoring()
        results["operations"]["monitoring"] = monitoring_result
        if not monitoring_result["success"] and not monitoring_result.get("skipped"):
            results["success"] = False
        
        # Run backup
        backup_result = self.run_backup()
        results["operations"]["backup"] = backup_result
        if not backup_result["success"] and not backup_result.get("skipped"):
            results["success"] = False
        
        # Calculate total duration
        end_time = datetime.now()
        results["duration"] = (end_time - start_time).total_seconds()
        
        # Log summary
        if results["success"]:
            logger.info(f"✅ All scheduled operations completed successfully in {results['duration']:.2f} seconds")
        else:
            logger.error(f"❌ Some scheduled operations failed (duration: {results['duration']:.2f} seconds)")
        
        return results


def main():
    """Main entry point for scheduled operations"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analysis History Scheduled Maintenance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all scheduled operations with default config
  python history_scheduler.py
  
  # Run only cleanup operations
  python history_scheduler.py --cleanup-only
  
  # Run with custom configuration file
  python history_scheduler.py --config /path/to/config.json
  
  # Run in dry-run mode (monitoring only)
  python history_scheduler.py --dry-run
  
Configuration file format (JSON):
{
  "cleanup": {
    "enabled": true,
    "max_age_days": 365,
    "batch_size": 100,
    "cleanup_failed_records": true,
    "failed_record_age_hours": 24
  },
  "monitoring": {
    "enabled": true,
    "max_size_mb": 1000,
    "max_documents": 100000,
    "max_daily_growth": 1000,
    "alert_on_warnings": false
  },
  "backup": {
    "enabled": false,
    "backup_path": "data/backups/history",
    "backup_frequency_days": 7,
    "compress_backups": true,
    "keep_backups": 4
  }
}
        """
    )
    
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--cleanup-only', action='store_true',
                       help='Run only cleanup operations')
    parser.add_argument('--monitoring-only', action='store_true',
                       help='Run only monitoring operations')
    parser.add_argument('--backup-only', action='store_true',
                       help='Run only backup operations')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run in dry-run mode (monitoring only, no changes)')
    parser.add_argument('--output-json', help='Output results to JSON file')
    
    args = parser.parse_args()
    
    try:
        # Initialize scheduler
        scheduler = HistoryScheduler(config_path=args.config)
        
        # Run operations based on arguments
        if args.dry_run:
            logger.info("🔍 Running in dry-run mode (monitoring only)")
            results = scheduler.run_monitoring()
        elif args.cleanup_only:
            results = scheduler.run_cleanup()
        elif args.monitoring_only:
            results = scheduler.run_monitoring()
        elif args.backup_only:
            results = scheduler.run_backup()
        else:
            results = scheduler.run_all()
        
        # Output results to JSON file if requested
        if args.output_json:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"📄 Results written to {output_path}")
        
        # Exit with appropriate code
        if results.get("success", False):
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⏹️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()