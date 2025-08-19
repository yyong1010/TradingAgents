#!/usr/bin/env python3
"""
Analysis History Administration Utilities

This script provides command-line utilities for managing analysis history data,
including cleanup, monitoring, backup, and maintenance operations.
"""

import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.logging_manager import get_logger
from web.utils.history_data_manager import get_data_manager, HistoryDataManager

# Setup logging
logger = get_logger('history_admin')


class HistoryAdminCLI:
    """Command-line interface for history administration"""
    
    def __init__(self):
        self.data_manager = get_data_manager()
    
    def cleanup_command(self, args) -> None:
        """Execute cleanup command"""
        logger.info("🧹 Starting analysis history cleanup...")
        
        if args.failed_only:
            # Clean up only failed records
            result = self.data_manager.cleanup_failed_records(
                max_age_hours=args.failed_age_hours,
                dry_run=args.dry_run
            )
            
            if result["success"]:
                if args.dry_run:
                    logger.info(f"📊 Dry run: Would delete {result['total_found']} failed records")
                else:
                    logger.info(f"✅ Deleted {result['deleted_count']} failed records")
            else:
                logger.error(f"❌ Cleanup failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
        else:
            # Clean up old records
            result = self.data_manager.cleanup_old_records(
                max_age_days=args.max_age_days,
                batch_size=args.batch_size,
                dry_run=args.dry_run
            )
            
            if result["success"]:
                if args.dry_run:
                    logger.info(f"📊 Dry run: Would delete {result['total_found']} records older than {args.max_age_days} days")
                    if "sample_records" in result:
                        logger.info("📋 Sample records that would be deleted:")
                        for record in result["sample_records"][:5]:
                            logger.info(f"  - {record['analysis_id']}: {record['stock_symbol']} ({record['created_at']})")
                else:
                    logger.info(f"✅ Deleted {result['deleted_count']} records in {result['processed_batches']} batches")
                    logger.info(f"⏱️ Operation completed in {result['duration']:.2f} seconds")
            else:
                logger.error(f"❌ Cleanup failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
    
    def stats_command(self, args) -> None:
        """Execute statistics command"""
        logger.info("📊 Gathering analysis history statistics...")
        
        stats = self.data_manager.get_storage_statistics()
        
        if not stats["success"]:
            logger.error(f"❌ Failed to get statistics: {stats.get('error', 'Unknown error')}")
            sys.exit(1)
        
        storage_info = stats["storage_info"]
        
        # Display basic storage information
        logger.info("\n📁 Storage Information:")
        logger.info(f"  Total Documents: {storage_info['total_documents']:,}")
        logger.info(f"  Total Size: {storage_info['total_size_mb']:.2f} MB")
        logger.info(f"  Storage Size: {storage_info['storage_size_mb']:.2f} MB")
        logger.info(f"  Index Size: {storage_info['index_size_mb']:.2f} MB")
        logger.info(f"  Average Document Size: {storage_info['average_document_size_bytes']:,} bytes")
        
        # Display status distribution
        if stats["status_distribution"]:
            logger.info("\n📈 Status Distribution:")
            for status, count in stats["status_distribution"].items():
                percentage = (count / storage_info['total_documents']) * 100
                logger.info(f"  {status}: {count:,} ({percentage:.1f}%)")
        
        # Display market distribution
        if stats["market_distribution"]:
            logger.info("\n🌍 Market Distribution:")
            for market, count in stats["market_distribution"].items():
                percentage = (count / storage_info['total_documents']) * 100
                logger.info(f"  {market}: {count:,} ({percentage:.1f}%)")
        
        # Display performance statistics
        if stats["performance_stats"]:
            perf = stats["performance_stats"]
            logger.info("\n⚡ Performance Statistics:")
            if "avg_execution_time" in perf and perf["avg_execution_time"]:
                logger.info(f"  Average Execution Time: {perf['avg_execution_time']:.2f} seconds")
                logger.info(f"  Max Execution Time: {perf.get('max_execution_time', 0):.2f} seconds")
                logger.info(f"  Min Execution Time: {perf.get('min_execution_time', 0):.2f} seconds")
            if "avg_cost" in perf and perf["avg_cost"]:
                logger.info(f"  Average Cost per Analysis: ${perf['avg_cost']:.4f}")
                logger.info(f"  Total Cost: ${perf.get('total_cost', 0):.2f}")
        
        # Display recent activity (last 7 days)
        if stats["daily_counts_last_30_days"]:
            recent_days = sorted(stats["daily_counts_last_30_days"].keys())[-7:]
            if recent_days:
                logger.info("\n📅 Recent Activity (Last 7 Days):")
                for day in recent_days:
                    count = stats["daily_counts_last_30_days"][day]
                    logger.info(f"  {day}: {count:,} analyses")
        
        # Check for alerts if requested
        if args.check_alerts:
            logger.info("\n🚨 Checking Storage Alerts...")
            alerts = self.data_manager.check_storage_alerts(
                max_size_mb=args.max_size_mb,
                max_documents=args.max_documents,
                max_daily_growth=args.max_daily_growth
            )
            
            if alerts["success"]:
                if alerts["alert_count"] > 0:
                    logger.warning(f"⚠️ Found {alerts['alert_count']} alerts:")
                    for alert in alerts["alerts"]:
                        logger.warning(f"  - {alert['type']}: {alert['message']}")
                
                if alerts["warning_count"] > 0:
                    logger.info(f"💡 Found {alerts['warning_count']} warnings:")
                    for warning in alerts["warnings"]:
                        logger.info(f"  - {warning['type']}: {warning['message']}")
                
                if alerts["alert_count"] == 0 and alerts["warning_count"] == 0:
                    logger.info("✅ No storage alerts or warnings")
            else:
                logger.error(f"❌ Failed to check alerts: {alerts.get('error', 'Unknown error')}")
    
    def export_command(self, args) -> None:
        """Execute export command"""
        logger.info(f"📤 Exporting analysis history to {args.output_path}...")
        
        # Build filters
        filters = {}
        if args.date_from:
            filters["date_from"] = datetime.fromisoformat(args.date_from)
        if args.date_to:
            filters["date_to"] = datetime.fromisoformat(args.date_to)
        if args.status:
            filters["status"] = args.status
        if args.market_type:
            filters["market_type"] = args.market_type
        
        result = self.data_manager.export_data(
            output_path=args.output_path,
            filters=filters,
            compress=args.compress,
            batch_size=args.batch_size
        )
        
        if result["success"]:
            logger.info(f"✅ Export completed successfully:")
            logger.info(f"  Records exported: {result['exported_count']:,}")
            logger.info(f"  Output file: {result['output_path']}")
            logger.info(f"  File size: {result['file_size_mb']:.2f} MB")
            logger.info(f"  Duration: {result['duration']:.2f} seconds")
            if result.get("compressed"):
                logger.info(f"  Compression: Enabled")
        else:
            logger.error(f"❌ Export failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    
    def import_command(self, args) -> None:
        """Execute import command"""
        logger.info(f"📥 Importing analysis history from {args.input_path}...")
        
        result = self.data_manager.import_data(
            input_path=args.input_path,
            batch_size=args.batch_size,
            skip_existing=not args.overwrite_existing,
            validate_records=not args.skip_validation
        )
        
        if result["success"]:
            logger.info(f"✅ Import completed successfully:")
            logger.info(f"  Records imported: {result['imported_count']:,}")
            logger.info(f"  Records skipped: {result['skipped_count']:,}")
            logger.info(f"  Errors encountered: {result['error_count']:,}")
            logger.info(f"  Total processed: {result['total_processed']:,}")
            logger.info(f"  Duration: {result['duration']:.2f} seconds")
            
            if result['error_count'] > 0:
                logger.warning(f"⚠️ {result['error_count']} records had errors during import")
        else:
            logger.error(f"❌ Import failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    
    def monitor_command(self, args) -> None:
        """Execute monitoring command"""
        logger.info("🔍 Starting analysis history monitoring...")
        
        # Get current statistics
        stats = self.data_manager.get_storage_statistics()
        if not stats["success"]:
            logger.error(f"❌ Failed to get statistics: {stats.get('error', 'Unknown error')}")
            sys.exit(1)
        
        # Check alerts
        alerts = self.data_manager.check_storage_alerts(
            max_size_mb=args.max_size_mb,
            max_documents=args.max_documents,
            max_daily_growth=args.max_daily_growth
        )
        
        if not alerts["success"]:
            logger.error(f"❌ Failed to check alerts: {alerts.get('error', 'Unknown error')}")
            sys.exit(1)
        
        # Generate monitoring report
        storage_info = stats["storage_info"]
        
        logger.info("\n📊 Current Status:")
        logger.info(f"  Documents: {storage_info['total_documents']:,}")
        logger.info(f"  Storage Size: {storage_info['total_size_mb']:.2f} MB")
        logger.info(f"  Index Size: {storage_info['index_size_mb']:.2f} MB")
        
        # Report alerts and warnings
        if alerts["alert_count"] > 0:
            logger.error(f"\n🚨 ALERTS ({alerts['alert_count']}):")
            for alert in alerts["alerts"]:
                logger.error(f"  - {alert['message']}")
            
            # Exit with error code if there are alerts
            if args.exit_on_alert:
                sys.exit(1)
        
        if alerts["warning_count"] > 0:
            logger.warning(f"\n⚠️ WARNINGS ({alerts['warning_count']}):")
            for warning in alerts["warnings"]:
                logger.warning(f"  - {warning['message']}")
        
        if alerts["alert_count"] == 0 and alerts["warning_count"] == 0:
            logger.info("\n✅ All monitoring checks passed")
        
        # Suggest cleanup if needed
        if storage_info['total_documents'] > 50000:
            logger.info(f"\n💡 Suggestion: Consider running cleanup for old records")
            logger.info(f"   Command: python {__file__} cleanup --max-age-days 180 --dry-run")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Analysis History Administration Utilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show storage statistics
  python history_admin.py stats
  
  # Check for storage alerts
  python history_admin.py stats --check-alerts
  
  # Cleanup records older than 1 year (dry run)
  python history_admin.py cleanup --max-age-days 365 --dry-run
  
  # Cleanup failed records older than 24 hours
  python history_admin.py cleanup --failed-only --failed-age-hours 24
  
  # Export all data to compressed JSON
  python history_admin.py export data_backup.json.gz --compress
  
  # Export data from specific date range
  python history_admin.py export recent_data.json --date-from 2025-01-01 --date-to 2025-01-31
  
  # Import data from backup
  python history_admin.py import data_backup.json.gz
  
  # Monitor storage and exit with error if alerts found
  python history_admin.py monitor --exit-on-alert
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old or failed analysis records')
    cleanup_parser.add_argument('--max-age-days', type=int, default=365,
                               help='Maximum age of records to keep in days (default: 365)')
    cleanup_parser.add_argument('--batch-size', type=int, default=100,
                               help='Number of records to process in each batch (default: 100)')
    cleanup_parser.add_argument('--dry-run', action='store_true',
                               help='Show what would be deleted without actually deleting')
    cleanup_parser.add_argument('--failed-only', action='store_true',
                               help='Only clean up failed/error records')
    cleanup_parser.add_argument('--failed-age-hours', type=int, default=24,
                               help='Maximum age of failed records to keep in hours (default: 24)')
    
    # Statistics command
    stats_parser = subparsers.add_parser('stats', help='Show storage statistics and usage information')
    stats_parser.add_argument('--check-alerts', action='store_true',
                             help='Also check for storage alerts and warnings')
    stats_parser.add_argument('--max-size-mb', type=int, default=1000,
                             help='Maximum storage size in MB for alerts (default: 1000)')
    stats_parser.add_argument('--max-documents', type=int, default=100000,
                             help='Maximum number of documents for alerts (default: 100000)')
    stats_parser.add_argument('--max-daily-growth', type=int, default=1000,
                             help='Maximum daily document growth for alerts (default: 1000)')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export analysis history data')
    export_parser.add_argument('output_path', help='Output file path')
    export_parser.add_argument('--compress', action='store_true',
                              help='Compress the output file with gzip')
    export_parser.add_argument('--batch-size', type=int, default=1000,
                              help='Number of records to process in each batch (default: 1000)')
    export_parser.add_argument('--date-from', help='Export records from this date (ISO format: 2025-01-01)')
    export_parser.add_argument('--date-to', help='Export records until this date (ISO format: 2025-01-31)')
    export_parser.add_argument('--status', help='Export only records with this status')
    export_parser.add_argument('--market-type', help='Export only records for this market type')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import analysis history data')
    import_parser.add_argument('input_path', help='Input file path')
    import_parser.add_argument('--batch-size', type=int, default=1000,
                              help='Number of records to process in each batch (default: 1000)')
    import_parser.add_argument('--overwrite-existing', action='store_true',
                              help='Overwrite existing records (default: skip existing)')
    import_parser.add_argument('--skip-validation', action='store_true',
                              help='Skip record validation during import')
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor storage usage and check for alerts')
    monitor_parser.add_argument('--max-size-mb', type=int, default=1000,
                               help='Maximum storage size in MB for alerts (default: 1000)')
    monitor_parser.add_argument('--max-documents', type=int, default=100000,
                               help='Maximum number of documents for alerts (default: 100000)')
    monitor_parser.add_argument('--max-daily-growth', type=int, default=1000,
                               help='Maximum daily document growth for alerts (default: 1000)')
    monitor_parser.add_argument('--exit-on-alert', action='store_true',
                               help='Exit with error code if alerts are found')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize CLI handler
    cli = HistoryAdminCLI()
    
    # Check if data manager is available
    if not cli.data_manager.is_available():
        logger.error("❌ Data manager is not available. Please check MongoDB connection.")
        sys.exit(1)
    
    # Execute command
    try:
        if args.command == 'cleanup':
            cli.cleanup_command(args)
        elif args.command == 'stats':
            cli.stats_command(args)
        elif args.command == 'export':
            cli.export_command(args)
        elif args.command == 'import':
            cli.import_command(args)
        elif args.command == 'monitor':
            cli.monitor_command(args)
        else:
            logger.error(f"❌ Unknown command: {args.command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⏹️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()