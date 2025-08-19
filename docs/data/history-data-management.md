# Analysis History Data Management

This document describes the data management and cleanup utilities for the analysis history tracking system.

## Overview

The analysis history data management system provides comprehensive utilities for:

- **Automatic cleanup** of old and failed analysis records
- **Storage monitoring** and alerting for usage thresholds
- **Data backup and restore** functionality for disaster recovery
- **Admin utilities** for maintenance operations

## Components

### 1. History Data Manager (`web/utils/history_data_manager.py`)

The core data management service that provides:

#### Cleanup Operations
- `cleanup_old_records()` - Remove records older than specified days
- `cleanup_failed_records()` - Remove failed/error records older than specified hours

#### Storage Monitoring
- `get_storage_statistics()` - Comprehensive storage usage statistics
- `check_storage_alerts()` - Check for storage usage alerts and warnings

#### Backup Operations
- `export_data()` - Export analysis history to JSON files (with optional compression)
- `import_data()` - Import analysis history from JSON files

### 2. Admin CLI Tool (`scripts/maintenance/history_admin.py`)

Command-line interface for administrative operations:

```bash
# Show storage statistics
python scripts/maintenance/history_admin.py stats

# Check for storage alerts
python scripts/maintenance/history_admin.py stats --check-alerts

# Cleanup records older than 1 year (dry run)
python scripts/maintenance/history_admin.py cleanup --max-age-days 365 --dry-run

# Cleanup failed records older than 24 hours
python scripts/maintenance/history_admin.py cleanup --failed-only --failed-age-hours 24

# Export all data to compressed JSON
python scripts/maintenance/history_admin.py export data_backup.json.gz --compress

# Import data from backup
python scripts/maintenance/history_admin.py import data_backup.json.gz

# Monitor storage and exit with error if alerts found
python scripts/maintenance/history_admin.py monitor --exit-on-alert
```

### 3. Scheduled Maintenance (`scripts/maintenance/history_scheduler.py`)

Automated maintenance service for regular operations:

```bash
# Run all scheduled operations
python scripts/maintenance/history_scheduler.py

# Run only cleanup operations
python scripts/maintenance/history_scheduler.py --cleanup-only

# Run with custom configuration
python scripts/maintenance/history_scheduler.py --config /path/to/config.json

# Run in dry-run mode (monitoring only)
python scripts/maintenance/history_scheduler.py --dry-run
```

### 4. Web Admin Interface (`web/modules/history_admin.py`)

Web-based administration interface accessible through the main application:

- **Storage Statistics**: View comprehensive storage usage information
- **Data Cleanup**: Interactive cleanup operations with preview mode
- **Data Backup**: Export and import functionality with filtering options
- **Monitoring Alerts**: Real-time storage monitoring and alert configuration

## Configuration

### Maintenance Configuration (`config/history_maintenance.json`)

```json
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
    "enabled": true,
    "backup_path": "data/backups/history",
    "backup_frequency_days": 7,
    "compress_backups": true,
    "keep_backups": 4
  }
}
```

## Usage Examples

### Programmatic Usage

```python
from web.utils.history_data_manager import get_data_manager

# Get data manager instance
manager = get_data_manager()

# Cleanup old records (dry run)
result = manager.cleanup_old_records(max_age_days=365, dry_run=True)
print(f"Would delete {result['total_found']} records")

# Get storage statistics
stats = manager.get_storage_statistics()
print(f"Total documents: {stats['storage_info']['total_documents']:,}")
print(f"Storage size: {stats['storage_info']['total_size_mb']:.2f} MB")

# Check for alerts
alerts = manager.check_storage_alerts(max_size_mb=1000)
if alerts['alert_count'] > 0:
    print(f"Found {alerts['alert_count']} storage alerts!")

# Export data with filters
result = manager.export_data(
    output_path="backup.json.gz",
    filters={"status": "completed", "date_from": datetime(2025, 1, 1)},
    compress=True
)
print(f"Exported {result['exported_count']} records")
```

### Convenience Functions

```python
from web.utils.history_data_manager import (
    cleanup_old_analysis_records,
    get_storage_usage_report,
    export_analysis_history,
    import_analysis_history
)

# Quick cleanup
result = cleanup_old_analysis_records(max_age_days=180, dry_run=False)

# Get comprehensive usage report
report = get_storage_usage_report()

# Quick export/import
export_analysis_history("backup.json", filters={"market_type": "美股"})
import_analysis_history("backup.json")
```

## Automated Maintenance

### Setting up Cron Jobs

For automated maintenance, set up cron jobs:

```bash
# Edit crontab
crontab -e

# Add these entries:

# Daily cleanup of failed records at 2 AM
0 2 * * * cd /path/to/project && python scripts/maintenance/history_scheduler.py --cleanup-only

# Weekly backup on Sundays at 3 AM
0 3 * * 0 cd /path/to/project && python scripts/maintenance/history_scheduler.py --backup-only

# Hourly monitoring checks
0 * * * * cd /path/to/project && python scripts/maintenance/history_scheduler.py --monitoring-only

# Monthly cleanup of old records (first day of month at 4 AM)
0 4 1 * * cd /path/to/project && python scripts/maintenance/history_admin.py cleanup --max-age-days 365
```

### Docker Environment

For Docker deployments, add a maintenance service to `docker-compose.yml`:

```yaml
services:
  history-maintenance:
    build: .
    command: python scripts/maintenance/history_scheduler.py
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - MONGODB_HOST=mongodb
      - MONGODB_ENABLED=true
    depends_on:
      - mongodb
    restart: "no"  # Run once, don't restart
```

Run maintenance manually:
```bash
docker-compose run --rm history-maintenance
```

## Monitoring and Alerts

### Storage Thresholds

The system monitors several metrics:

- **Storage Size**: Total data size in MB
- **Document Count**: Number of analysis records
- **Daily Growth**: Average daily increase in records
- **Index Size**: Database index overhead

### Alert Levels

- **Warnings**: Triggered at 80% of threshold (configurable)
- **Alerts**: Triggered at 100% of threshold
- **Actions**: Automatic cleanup can be triggered on alerts

### Monitoring Integration

For production monitoring, integrate with your monitoring system:

```bash
# Check status and exit with error code if alerts found
python scripts/maintenance/history_admin.py monitor --exit-on-alert

# Output results to JSON for monitoring systems
python scripts/maintenance/history_scheduler.py --monitoring-only --output-json /tmp/history_status.json
```

## Backup and Recovery

### Backup Strategy

1. **Regular Backups**: Weekly full backups with compression
2. **Incremental Exports**: Daily exports of recent data
3. **Retention Policy**: Keep 4 most recent backups
4. **Compression**: Use gzip compression to save space

### Backup Format

Exported data is stored in JSON Lines format:

```json
{"export_timestamp": "2025-01-06T10:30:00", "total_records": 1000, "version": "1.0"}
{"analysis_id": "analysis_123", "stock_symbol": "AAPL", "created_at": "2025-01-01T12:00:00", ...}
{"analysis_id": "analysis_124", "stock_symbol": "GOOGL", "created_at": "2025-01-01T13:00:00", ...}
```

### Recovery Process

1. **Identify Backup**: Choose appropriate backup file
2. **Validate Data**: Check backup integrity
3. **Import Data**: Use import functionality with validation
4. **Verify Results**: Check imported record counts

```bash
# Restore from backup
python scripts/maintenance/history_admin.py import backup_20250106.json.gz

# Verify restoration
python scripts/maintenance/history_admin.py stats
```

## Performance Considerations

### Cleanup Performance

- **Batch Processing**: Process records in configurable batches (default: 100)
- **Index Usage**: Leverage database indexes for efficient queries
- **Progress Logging**: Monitor progress for large cleanup operations

### Export/Import Performance

- **Streaming**: Process large datasets without loading all into memory
- **Compression**: Reduce file sizes and I/O overhead
- **Validation**: Optional record validation for faster imports

### Storage Optimization

- **Index Management**: Maintain optimal database indexes
- **Data Archival**: Move old data to separate collections
- **Compression**: Use MongoDB compression features

## Troubleshooting

### Common Issues

1. **MongoDB Connection Errors**
   - Check MongoDB service status
   - Verify connection configuration
   - Check network connectivity

2. **Large Cleanup Operations**
   - Use smaller batch sizes
   - Monitor system resources
   - Run during low-usage periods

3. **Export/Import Failures**
   - Check disk space availability
   - Verify file permissions
   - Validate JSON format for imports

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.getLogger('web.utils.history_data_manager').setLevel(logging.DEBUG)
```

### Health Checks

Regular health checks:

```bash
# Check data manager availability
python -c "from web.utils.history_data_manager import get_data_manager; print('Available:', get_data_manager().is_available())"

# Check storage statistics
python scripts/maintenance/history_admin.py stats

# Test export/import cycle
python scripts/maintenance/history_admin.py export test_export.json --date-from 2025-01-01 --date-to 2025-01-02
python scripts/maintenance/history_admin.py import test_export.json --skip-validation
```

## Security Considerations

### Data Protection

- **Access Control**: Limit access to admin utilities
- **Backup Security**: Secure backup files with appropriate permissions
- **Data Validation**: Validate all imported data

### Audit Trail

- **Operation Logging**: Log all maintenance operations
- **Change Tracking**: Track data modifications
- **Access Logging**: Log administrative access

## Integration with Main Application

### Web Interface Integration

Add admin tab to main navigation in `web/app.py`:

```python
from web.modules.history_admin import render_history_admin, should_show_admin_tab

# In main navigation
if should_show_admin_tab():
    with st.sidebar:
        if st.button("📊 历史管理"):
            st.session_state.current_page = "history_admin"

# In page routing
if st.session_state.get("current_page") == "history_admin":
    render_history_admin()
```

### API Integration

Expose admin functions through API endpoints:

```python
from web.utils.history_data_manager import get_data_manager

@app.route('/api/admin/storage-stats')
def get_storage_stats():
    manager = get_data_manager()
    return manager.get_storage_statistics()

@app.route('/api/admin/cleanup', methods=['POST'])
def cleanup_records():
    manager = get_data_manager()
    return manager.cleanup_old_records(**request.json)
```

## Best Practices

### Maintenance Schedule

1. **Daily**: Cleanup failed records, monitor alerts
2. **Weekly**: Full backup, performance review
3. **Monthly**: Cleanup old records, index optimization
4. **Quarterly**: Storage planning, capacity review

### Configuration Management

- Use version control for configuration files
- Test configuration changes in staging environment
- Document all configuration parameters
- Regular configuration reviews

### Monitoring and Alerting

- Set up proactive monitoring
- Configure appropriate alert thresholds
- Regular review of alert patterns
- Automated response to critical alerts

This comprehensive data management system ensures the analysis history remains performant, reliable, and maintainable as the system scales.