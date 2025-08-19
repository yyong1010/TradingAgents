"""
Analysis History Administration Web Interface

This module provides a web interface for history data management operations,
including cleanup, monitoring, and backup functionality.
"""

import streamlit as st
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from web.utils.history_data_manager import get_data_manager
from web.utils.error_handler import show_error_to_user, show_success_to_user

# Setup logging
logger = logging.getLogger(__name__)


def render_history_admin() -> None:
    """Render the history administration interface"""
    st.title("📊 分析历史管理")
    st.markdown("管理分析历史数据，包括清理、监控和备份功能")
    
    # Check if data manager is available
    data_manager = get_data_manager()
    if not data_manager.is_available():
        st.error("❌ 数据管理器不可用，请检查MongoDB连接")
        return
    
    # Create tabs for different admin functions
    tab1, tab2, tab3, tab4 = st.tabs(["📊 存储统计", "🧹 数据清理", "💾 数据备份", "🔍 监控告警"])
    
    with tab1:
        render_storage_statistics()
    
    with tab2:
        render_data_cleanup()
    
    with tab3:
        render_data_backup()
    
    with tab4:
        render_monitoring_alerts()


def render_storage_statistics() -> None:
    """Render storage statistics section"""
    st.header("存储统计信息")
    
    data_manager = get_data_manager()
    
    # Add refresh button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 刷新统计", key="refresh_stats"):
            st.rerun()
    
    # Get storage statistics
    with st.spinner("获取存储统计信息..."):
        stats = data_manager.get_storage_statistics()
    
    if not stats["success"]:
        st.error(f"获取统计信息失败: {stats.get('error', '未知错误')}")
        return
    
    storage_info = stats["storage_info"]
    
    # Display basic storage metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="总文档数",
            value=f"{storage_info['total_documents']:,}",
            help="数据库中的分析记录总数"
        )
    
    with col2:
        st.metric(
            label="存储大小",
            value=f"{storage_info['total_size_mb']:.2f} MB",
            help="数据占用的存储空间"
        )
    
    with col3:
        st.metric(
            label="索引大小",
            value=f"{storage_info['index_size_mb']:.2f} MB",
            help="数据库索引占用的空间"
        )
    
    with col4:
        avg_size_kb = storage_info['average_document_size_bytes'] / 1024
        st.metric(
            label="平均文档大小",
            value=f"{avg_size_kb:.2f} KB",
            help="每个分析记录的平均大小"
        )
    
    # Status distribution chart
    if stats["status_distribution"]:
        st.subheader("状态分布")
        status_data = stats["status_distribution"]
        
        # Create a simple bar chart
        import pandas as pd
        df = pd.DataFrame(list(status_data.items()), columns=['状态', '数量'])
        st.bar_chart(df.set_index('状态'))
    
    # Market distribution
    if stats["market_distribution"]:
        st.subheader("市场分布")
        market_data = stats["market_distribution"]
        
        col1, col2 = st.columns(2)
        with col1:
            for market, count in market_data.items():
                percentage = (count / storage_info['total_documents']) * 100
                st.write(f"**{market}**: {count:,} ({percentage:.1f}%)")
    
    # Performance statistics
    if stats["performance_stats"]:
        perf = stats["performance_stats"]
        st.subheader("性能统计")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if "avg_execution_time" in perf and perf["avg_execution_time"]:
                st.metric(
                    label="平均执行时间",
                    value=f"{perf['avg_execution_time']:.2f}秒"
                )
                st.metric(
                    label="最长执行时间",
                    value=f"{perf.get('max_execution_time', 0):.2f}秒"
                )
        
        with col2:
            if "avg_cost" in perf and perf["avg_cost"]:
                st.metric(
                    label="平均成本",
                    value=f"${perf['avg_cost']:.4f}"
                )
                st.metric(
                    label="总成本",
                    value=f"${perf.get('total_cost', 0):.2f}"
                )
    
    # Recent activity
    if stats["daily_counts_last_30_days"]:
        st.subheader("最近活动 (过去30天)")
        daily_data = stats["daily_counts_last_30_days"]
        
        # Convert to DataFrame for plotting
        import pandas as pd
        df = pd.DataFrame(list(daily_data.items()), columns=['日期', '分析数量'])
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期')
        
        st.line_chart(df.set_index('日期'))


def render_data_cleanup() -> None:
    """Render data cleanup section"""
    st.header("数据清理")
    
    data_manager = get_data_manager()
    
    # Cleanup old records section
    st.subheader("清理旧记录")
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_age_days = st.number_input(
            "保留天数",
            min_value=1,
            max_value=3650,
            value=365,
            help="删除超过指定天数的记录"
        )
        
        batch_size = st.number_input(
            "批处理大小",
            min_value=10,
            max_value=1000,
            value=100,
            help="每批处理的记录数量"
        )
    
    with col2:
        dry_run = st.checkbox(
            "预览模式",
            value=True,
            help="只显示将要删除的记录，不实际删除"
        )
    
    if st.button("🧹 清理旧记录", key="cleanup_old"):
        with st.spinner("正在清理旧记录..."):
            result = data_manager.cleanup_old_records(
                max_age_days=max_age_days,
                batch_size=batch_size,
                dry_run=dry_run
            )
        
        if result["success"]:
            if dry_run:
                st.info(f"📊 预览: 将删除 {result['total_found']} 条记录")
                if "sample_records" in result and result["sample_records"]:
                    st.write("示例记录:")
                    for record in result["sample_records"][:5]:
                        st.write(f"- {record['analysis_id']}: {record['stock_symbol']} ({record['created_at']})")
            else:
                if result["deleted_count"] > 0:
                    show_success_to_user(f"成功删除 {result['deleted_count']} 条记录")
                else:
                    st.info("没有找到需要清理的记录")
        else:
            show_error_to_user(f"清理失败: {result.get('error', '未知错误')}")
    
    st.divider()
    
    # Cleanup failed records section
    st.subheader("清理失败记录")
    
    col1, col2 = st.columns(2)
    
    with col1:
        failed_age_hours = st.number_input(
            "失败记录保留小时数",
            min_value=1,
            max_value=168,  # 1 week
            value=24,
            help="删除超过指定小时数的失败记录"
        )
    
    with col2:
        failed_dry_run = st.checkbox(
            "预览模式",
            value=True,
            key="failed_dry_run",
            help="只显示将要删除的失败记录，不实际删除"
        )
    
    if st.button("🧹 清理失败记录", key="cleanup_failed"):
        with st.spinner("正在清理失败记录..."):
            result = data_manager.cleanup_failed_records(
                max_age_hours=failed_age_hours,
                dry_run=failed_dry_run
            )
        
        if result["success"]:
            if failed_dry_run:
                st.info(f"📊 预览: 将删除 {result['total_found']} 条失败记录")
            else:
                if result["deleted_count"] > 0:
                    show_success_to_user(f"成功删除 {result['deleted_count']} 条失败记录")
                else:
                    st.info("没有找到需要清理的失败记录")
        else:
            show_error_to_user(f"清理失败: {result.get('error', '未知错误')}")


def render_data_backup() -> None:
    """Render data backup section"""
    st.header("数据备份")
    
    data_manager = get_data_manager()
    
    # Export section
    st.subheader("导出数据")
    
    col1, col2 = st.columns(2)
    
    with col1:
        export_path = st.text_input(
            "导出文件路径",
            value=f"data/backups/history_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            help="导出文件的保存路径"
        )
        
        compress_export = st.checkbox(
            "压缩文件",
            value=True,
            help="使用gzip压缩导出文件"
        )
    
    with col2:
        # Date range filters
        st.write("**过滤条件 (可选)**")
        
        date_from = st.date_input(
            "开始日期",
            value=None,
            help="只导出此日期之后的记录"
        )
        
        date_to = st.date_input(
            "结束日期",
            value=None,
            help="只导出此日期之前的记录"
        )
        
        status_filter = st.selectbox(
            "状态过滤",
            options=["", "completed", "failed", "error", "incomplete"],
            help="只导出指定状态的记录"
        )
    
    if st.button("📤 导出数据", key="export_data"):
        # Build filters
        filters = {}
        if date_from:
            filters["date_from"] = datetime.combine(date_from, datetime.min.time())
        if date_to:
            filters["date_to"] = datetime.combine(date_to, datetime.max.time())
        if status_filter:
            filters["status"] = status_filter
        
        with st.spinner("正在导出数据..."):
            result = data_manager.export_data(
                output_path=export_path,
                filters=filters,
                compress=compress_export
            )
        
        if result["success"]:
            show_success_to_user(f"成功导出 {result['exported_count']:,} 条记录")
            st.info(f"文件路径: {result['output_path']}")
            st.info(f"文件大小: {result['file_size_mb']:.2f} MB")
        else:
            show_error_to_user(f"导出失败: {result.get('error', '未知错误')}")
    
    st.divider()
    
    # Import section
    st.subheader("导入数据")
    
    col1, col2 = st.columns(2)
    
    with col1:
        import_path = st.text_input(
            "导入文件路径",
            help="要导入的JSON文件路径"
        )
        
        skip_existing = st.checkbox(
            "跳过已存在记录",
            value=True,
            help="跳过已存在的记录，避免重复"
        )
    
    with col2:
        validate_records = st.checkbox(
            "验证记录",
            value=True,
            help="导入前验证记录格式"
        )
        
        batch_size = st.number_input(
            "批处理大小",
            min_value=100,
            max_value=5000,
            value=1000,
            help="每批处理的记录数量"
        )
    
    if st.button("📥 导入数据", key="import_data"):
        if not import_path:
            st.error("请输入导入文件路径")
            return
        
        if not Path(import_path).exists():
            st.error(f"文件不存在: {import_path}")
            return
        
        with st.spinner("正在导入数据..."):
            result = data_manager.import_data(
                input_path=import_path,
                batch_size=batch_size,
                skip_existing=skip_existing,
                validate_records=validate_records
            )
        
        if result["success"]:
            show_success_to_user(f"导入完成")
            st.info(f"导入记录: {result['imported_count']:,}")
            st.info(f"跳过记录: {result['skipped_count']:,}")
            if result['error_count'] > 0:
                st.warning(f"错误记录: {result['error_count']:,}")
        else:
            show_error_to_user(f"导入失败: {result.get('error', '未知错误')}")


def render_monitoring_alerts() -> None:
    """Render monitoring and alerts section"""
    st.header("监控告警")
    
    data_manager = get_data_manager()
    
    # Alert thresholds
    st.subheader("告警阈值设置")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        max_size_mb = st.number_input(
            "最大存储大小 (MB)",
            min_value=100,
            max_value=10000,
            value=1000,
            help="存储大小超过此值时触发告警"
        )
    
    with col2:
        max_documents = st.number_input(
            "最大文档数量",
            min_value=1000,
            max_value=1000000,
            value=100000,
            help="文档数量超过此值时触发告警"
        )
    
    with col3:
        max_daily_growth = st.number_input(
            "最大日增长量",
            min_value=100,
            max_value=10000,
            value=1000,
            help="日增长量超过此值时触发告警"
        )
    
    if st.button("🔍 检查告警", key="check_alerts"):
        with st.spinner("检查存储告警..."):
            alerts = data_manager.check_storage_alerts(
                max_size_mb=max_size_mb,
                max_documents=max_documents,
                max_daily_growth=max_daily_growth
            )
        
        if not alerts["success"]:
            st.error(f"检查告警失败: {alerts.get('error', '未知错误')}")
            return
        
        # Display alerts
        if alerts["alert_count"] > 0:
            st.error(f"🚨 发现 {alerts['alert_count']} 个告警:")
            for alert in alerts["alerts"]:
                st.error(f"- {alert['message']}")
        
        # Display warnings
        if alerts["warning_count"] > 0:
            st.warning(f"⚠️ 发现 {alerts['warning_count']} 个警告:")
            for warning in alerts["warnings"]:
                st.warning(f"- {warning['message']}")
        
        # Display success message if no issues
        if alerts["alert_count"] == 0 and alerts["warning_count"] == 0:
            st.success("✅ 所有监控检查通过，没有发现问题")
        
        # Display current storage info
        storage_stats = alerts["storage_stats"]
        st.subheader("当前存储状态")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            current_size = storage_stats["total_size_mb"]
            size_percentage = (current_size / max_size_mb) * 100
            st.metric(
                label="存储使用率",
                value=f"{size_percentage:.1f}%",
                delta=f"{current_size:.2f} MB / {max_size_mb} MB"
            )
        
        with col2:
            current_docs = storage_stats["total_documents"]
            docs_percentage = (current_docs / max_documents) * 100
            st.metric(
                label="文档数量使用率",
                value=f"{docs_percentage:.1f}%",
                delta=f"{current_docs:,} / {max_documents:,}"
            )
        
        with col3:
            # Calculate recent growth if possible
            stats = data_manager.get_storage_statistics()
            if stats["success"] and stats["daily_counts_last_30_days"]:
                daily_counts = stats["daily_counts_last_30_days"]
                recent_days = sorted(daily_counts.keys())[-3:]  # Last 3 days
                if len(recent_days) >= 2:
                    recent_growth = sum(daily_counts[day] for day in recent_days) / len(recent_days)
                    growth_percentage = (recent_growth / max_daily_growth) * 100
                    st.metric(
                        label="日增长率",
                        value=f"{growth_percentage:.1f}%",
                        delta=f"{recent_growth:.0f} / {max_daily_growth}"
                    )
    
    st.divider()
    
    # Automated maintenance settings
    st.subheader("自动维护设置")
    
    st.info("""
    💡 **自动维护建议**
    
    可以设置定时任务来自动执行维护操作:
    
    1. **每日清理**: 清理失败的分析记录
    2. **每周备份**: 导出重要数据进行备份
    3. **每月清理**: 清理超过1年的旧记录
    4. **监控告警**: 定期检查存储使用情况
    
    使用以下命令设置定时任务:
    ```bash
    # 每日凌晨2点执行清理
    0 2 * * * python scripts/maintenance/history_scheduler.py --cleanup-only
    
    # 每周日凌晨3点执行备份
    0 3 * * 0 python scripts/maintenance/history_scheduler.py --backup-only
    
    # 每小时检查监控告警
    0 * * * * python scripts/maintenance/history_scheduler.py --monitoring-only
    ```
    """)
    
    # Configuration file editor
    config_path = Path("config/history_maintenance.json")
    if config_path.exists():
        st.subheader("维护配置")
        
        if st.button("📝 编辑配置文件", key="edit_config"):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_content = f.read()
                
                edited_config = st.text_area(
                    "配置文件内容 (JSON格式)",
                    value=config_content,
                    height=300,
                    help="编辑自动维护配置"
                )
                
                if st.button("💾 保存配置", key="save_config"):
                    try:
                        # Validate JSON
                        json.loads(edited_config)
                        
                        # Save configuration
                        with open(config_path, 'w', encoding='utf-8') as f:
                            f.write(edited_config)
                        
                        show_success_to_user("配置文件保存成功")
                        st.rerun()
                        
                    except json.JSONDecodeError as e:
                        show_error_to_user(f"JSON格式错误: {e}")
                    except Exception as e:
                        show_error_to_user(f"保存失败: {e}")
                        
            except Exception as e:
                show_error_to_user(f"读取配置文件失败: {e}")


# Helper function to integrate with main navigation
def should_show_admin_tab() -> bool:
    """Check if admin tab should be shown (can be extended with permission checks)"""
    # For now, always show admin tab
    # In production, you might want to check user permissions here
    return True