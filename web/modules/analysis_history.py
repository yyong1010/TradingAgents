#!/usr/bin/env python3
"""
Analysis History Web Module

This module provides the web interface for viewing, searching, and managing
analysis history records. It integrates with the existing Streamlit application
and provides a comprehensive history management experience with enhanced
search and filtering capabilities.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import math
import re
import time

# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import logging
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web.history')

# Import history storage and models
from web.utils.history_storage import get_history_storage
from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus, MarketType

# Import performance utilities
from web.utils.history_cache_warmer import get_cache_warmer

# Import error handling utilities
from web.utils.error_handler import (
    with_error_handling, handle_storage_operation, show_error_to_user,
    show_loading_with_progress, ErrorHandler, UserFriendlyError, ErrorType, ErrorSeverity,
    create_operation_timeout_handler, log_operation_metrics
)

# Import UI utilities
from web.utils.ui_utils import apply_hide_deploy_button_css


def render_analysis_history():
    """
    Enhanced main render function for the analysis history page with real-time updates
    
    This function serves as the entry point for the history module and handles
    the overall page layout, navigation integration, and component orchestration.
    """
    # Initialize session state for modal
    if 'show_analysis_modal' not in st.session_state:
        st.session_state['show_analysis_modal'] = False
    if 'selected_analysis_id' not in st.session_state:
        st.session_state['selected_analysis_id'] = None
    
    # Initialize session state for delete confirmation
    if 'show_delete_confirmation' not in st.session_state:
        st.session_state['show_delete_confirmation'] = False
    if 'delete_target_id' not in st.session_state:
        st.session_state['delete_target_id'] = None
    if 'delete_target_info' not in st.session_state:
        st.session_state['delete_target_info'] = {}
    
    # Initialize session state for bulk delete
    if 'show_bulk_delete' not in st.session_state:
        st.session_state['show_bulk_delete'] = False
    if 'selected_for_delete' not in st.session_state:
        st.session_state['selected_for_delete'] = set()
    
    # Apply CSS to hide deploy button
    apply_hide_deploy_button_css()
    
    # Page header with enhanced information
    st.title("📈 分析历史记录")
    st.markdown("查看和管理您的股票分析历史记录 - 支持实时筛选和高级搜索")
    
    # Initialize history storage with enhanced error handling
    try:
        with show_loading_with_progress("初始化历史记录存储", estimated_duration=3.0) as loading:
            loading.update_progress(0.3, "连接数据库")
            history_storage = get_history_storage()
            
            loading.update_progress(0.7, "验证存储可用性")
            # Check if storage is available
            if not history_storage.is_available():
                loading.mark_error("存储服务不可用")
                _render_storage_unavailable()
                return
            
            loading.update_progress(1.0, "存储初始化完成")
            loading.set_completion_message("✅ 历史记录存储已就绪")
            
    except Exception as e:
        logger.error(f"Failed to initialize history storage: {e}")
        user_error = ErrorHandler.create_user_friendly_error(e, "初始化历史记录存储")
        show_error_to_user(user_error)
        
        # Show fallback options
        st.info("💡 您可以尝试以下操作：")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 重新加载页面"):
                st.rerun()
        with col2:
            if st.button("🏠 返回主页"):
                st.switch_page("web/app.py")
        with col3:
            if st.button("📞 联系支持"):
                st.info("请联系技术支持团队获取帮助")
        return
    
    # Add debug toggle in sidebar (for development)
    with st.sidebar:
        debug_mode = st.checkbox("🔧 调试模式", value=False, help="显示查询性能和调试信息")
        st.session_state['debug_mode'] = debug_mode
        
        if debug_mode:
            st.markdown("### 🔍 调试信息")
            if 'last_query_info' in st.session_state:
                query_info = st.session_state['last_query_info']
                st.json({
                    "查询条件": query_info.get('query', {}),
                    "结果数量": query_info.get('results', 0),
                    "总记录数": query_info.get('total', 0),
                    "排序方式": query_info.get('sort', 'N/A')
                })
    
    # Get history statistics for overview with error handling
    stats = handle_storage_operation(
        "加载统计信息",
        history_storage.get_history_stats,
        show_progress=True
    )
    
    if stats is None:
        # Fallback to empty stats if loading failed
        stats = {
            'total_analyses': 0,
            'completed_analyses': 0,
            'failed_analyses': 0,
            'recent_analyses': 0,
            'total_cost': 0.0,
            'avg_execution_time': 0.0,
            'storage_available': False
        }
    
    # Render overview metrics
    _render_overview_metrics(stats)
    
    # Render enhanced filter controls with real-time updates
    filters = _render_filter_controls()
    
    # Performance monitoring
    query_start_time = datetime.now()
    query_duration = 0.0  # Initialize to avoid UnboundLocalError
    
    # Get filtered history data with enhanced error handling and progress tracking
    try:
        with show_loading_with_progress("搜索分析记录", estimated_duration=5.0) as loading:
            loading.update_progress(0.1, "验证搜索条件")
            
            # Validate filters before processing
            if not isinstance(filters, dict):
                raise ValueError("搜索条件格式错误")
            
            loading.update_progress(0.3, "构建数据库查询")
            
            # Execute database query
            loading.update_progress(0.5, "执行数据库查询")
            history_records, total_count = _get_filtered_history(history_storage, filters)
            
            loading.update_progress(0.9, "处理查询结果")
            
            # Calculate query duration
            query_end_time = datetime.now()
            query_duration = (query_end_time - query_start_time).total_seconds()
            
            # Log search metrics
            log_operation_metrics(
                "history_search",
                query_duration,
                True,
                additional_metrics={
                    'total_results': total_count,
                    'filters_applied': _count_active_filters(filters),
                    'page_size': filters.get('page_size', 20)
                }
            )
            
            loading.update_progress(1.0, f"找到 {total_count} 条记录")
            loading.set_completion_message(f"✅ 搜索完成，找到 {total_count} 条记录")
            
    except TimeoutError as e:
        logger.error(f"Search timeout: {e}")
        st.error("🕐 搜索超时，请尝试缩小搜索范围或稍后重试")
        
        # Provide timeout-specific suggestions
        with st.expander("💡 搜索优化建议"):
            st.markdown("""
            - 缩小日期范围（如最近30天）
            - 使用更具体的股票代码或名称
            - 减少同时应用的筛选条件
            - 尝试分页浏览而不是一次加载大量数据
            """)
        
        history_records, total_count = [], 0
        
    except Exception as e:
        logger.error(f"Error getting filtered history: {e}")
        user_error = ErrorHandler.create_user_friendly_error(e, "搜索分析记录")
        show_error_to_user(user_error)
        
        # Provide fallback options
        st.info("💡 您可以尝试：")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 重新搜索", key="retry_search"):
                st.rerun()
        with col2:
            if st.button("🧹 清除筛选条件", key="clear_filters"):
                # Clear all filters
                for key in st.session_state.keys():
                    if key.startswith('history_'):
                        del st.session_state[key]
                st.rerun()
        with col3:
            if st.button("📊 查看统计信息", key="view_stats"):
                # Show basic stats even if search failed
                try:
                    stats = history_storage.get_history_stats()
                    st.json(stats)
                except:
                    st.error("无法获取统计信息")
        
        history_records, total_count = [], 0
        
        # Calculate query duration for failed case
        query_end_time = datetime.now()
        query_duration = (query_end_time - query_start_time).total_seconds()
    
    # Show query performance in debug mode
    if debug_mode:
        st.info(f"⚡ 查询耗时: {query_duration:.3f}秒 | 找到 {total_count} 条记录")
    
    # Check if we have any data
    if total_count == 0:
        if _has_any_filters_applied(filters):
            _render_no_results_found()
            _render_filter_suggestions(filters)
        else:
            _render_empty_state()
        return
    
    # Show results summary
    _render_results_summary(total_count, filters, query_duration)
    
    # Get current page from session state
    current_page = st.session_state.get('history_current_page', 1)
    
    # Render pagination controls (top)
    current_page = _render_pagination_controls(total_count, filters['page_size'], position='top')
    
    # Update filters with current page
    filters['page'] = current_page
    
    # Get data for current page with updated filters (only if page changed)
    if current_page != 1 or len(history_records) != filters['page_size']:
        with st.spinner("📄 加载页面数据..."):
            history_records, _ = _get_filtered_history(history_storage, filters)
    
    # Render history table with enhanced features
    _render_history_table(history_records)
    
    # Render pagination controls (bottom) - only if there are multiple pages
    if total_count > filters['page_size']:
        st.markdown("---")
        _render_pagination_controls(total_count, filters['page_size'], position='bottom')
    
    # Add footer with helpful information
    _render_page_footer(total_count, filters)
    
    # Render analysis detail section at the bottom if a record is selected
    # This is now a fixed bottom section that doesn't interfere with the table
    _render_bottom_detail_section()


def _render_results_summary(total_count: int, filters: Dict[str, Any], query_duration: float):
    """Render a summary of the current search results"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="🔍 搜索结果",
            value=f"{total_count:,} 条记录",
            help="当前筛选条件下的记录总数"
        )
    
    with col2:
        active_filters = _count_active_filters(filters)
        st.metric(
            label="🎯 活跃筛选",
            value=f"{active_filters} 个条件",
            help="当前应用的筛选条件数量"
        )
    
    with col3:
        st.metric(
            label="⚡ 查询性能",
            value=f"{query_duration:.2f}s",
            help="查询执行时间"
        )


def _render_filter_suggestions(filters: Dict[str, Any]):
    """Render suggestions when no results are found"""
    st.markdown("### 💡 搜索建议")
    
    suggestions = []
    
    if filters.get('stock_symbol'):
        suggestions.append("• 尝试输入更少的股票代码字符")
        suggestions.append("• 检查股票代码格式是否正确")
    
    if filters.get('stock_name'):
        suggestions.append("• 尝试使用股票名称的简称")
        suggestions.append("• 检查是否有拼写错误")
    
    if filters.get('market_type'):
        suggestions.append(f"• 尝试切换到其他市场类型")
    
    if filters.get('status'):
        suggestions.append("• 尝试选择 '全部' 状态查看所有记录")
    
    if filters.get('analysis_type'):
        suggestions.append("• 尝试选择 '全部' 分析类型")
    
    # Always show general suggestions
    suggestions.extend([
        "• 扩大日期范围以包含更多历史记录",
        "• 使用 '清除所有筛选' 按钮重置搜索条件",
        "• 尝试使用 '综合搜索' 同时搜索代码和名称"
    ])
    
    for suggestion in suggestions[:5]:  # Show max 5 suggestions
        st.markdown(suggestion)


def _render_page_footer(total_count: int, filters: Dict[str, Any]):
    """Render page footer with helpful information"""
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📚 使用提示")
        st.markdown("""
        - 使用 **综合搜索** 同时搜索代码和名称
        - **日期预设** 可快速选择常用时间范围
        - **排序功能** 支持多字段排序
        """)
    
    with col2:
        st.markdown("### ⚡ 性能优化")
        st.markdown("""
        - 筛选条件越具体，查询速度越快
        - 使用精确的股票代码比模糊搜索更快
        - 较小的日期范围可提高查询性能
        """)
    
    with col3:
        st.markdown("### 🔧 功能说明")
        st.markdown("""
        - **实时筛选**: 修改条件后自动更新结果
        - **智能分页**: 自动优化大数据集显示
        - **多维排序**: 支持按多个字段排序
        """)
    
    # Show current filter summary
    if _has_any_filters_applied(filters):
        st.markdown("### 🎯 当前筛选条件")
        filter_summary = []
        
        if filters.get('stock_symbol'):
            filter_summary.append(f"股票代码: {filters['stock_symbol']}")
        if filters.get('stock_name'):
            filter_summary.append(f"股票名称: {filters['stock_name']}")
        if filters.get('combined_search'):
            filter_summary.append(f"综合搜索: {filters['combined_search']}")
        if filters.get('market_type'):
            filter_summary.append(f"市场类型: {filters['market_type']}")
        if filters.get('status'):
            filter_summary.append(f"分析状态: {filters['status']}")
        if filters.get('analysis_type'):
            filter_summary.append(f"分析类型: {filters['analysis_type']}")
        if filters.get('analyst'):
            filter_summary.append(f"分析师: {filters['analyst']}")
        
        st.markdown(" | ".join(filter_summary))


def _render_storage_unavailable():
    """Render enhanced message when storage is not available with troubleshooting options"""
    st.error("📊 历史记录存储服务不可用")
    
    # Enhanced error information with tabs
    tab1, tab2, tab3 = st.tabs(["🔍 问题诊断", "🛠️ 解决方案", "📞 获取帮助"])
    
    with tab1:
        st.markdown("### 可能的原因")
        st.markdown("""
        - 🔌 **数据库连接失败**: MongoDB 服务可能未启动或网络不通
        - ⚙️ **配置错误**: 数据库连接参数可能不正确
        - 🌐 **网络问题**: 防火墙或网络策略阻止了连接
        - 💾 **存储空间不足**: 数据库磁盘空间可能已满
        - 🔐 **权限问题**: 数据库用户权限不足
        """)
        
        # Add diagnostic information
        st.markdown("### 系统状态")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("存储状态", "❌ 不可用", help="历史记录存储服务状态")
        with col2:
            st.metric("连接尝试", "失败", help="最近一次连接尝试结果")
    
    with tab2:
        st.markdown("### 立即尝试的解决方案")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 重新连接存储", type="primary"):
                with st.spinner("正在重新连接..."):
                    time.sleep(2)  # Simulate reconnection attempt
                    st.rerun()
            
            if st.button("📊 查看系统状态"):
                st.info("系统状态检查功能开发中...")
        
        with col2:
            if st.button("🏠 返回主页"):
                st.switch_page("web/app.py")
            
            if st.button("📋 使用离线模式"):
                st.warning("离线模式下无法查看历史记录，但可以进行新的分析")
        
        st.markdown("### 管理员解决方案")
        st.markdown("""
        1. **检查 MongoDB 服务**
           ```bash
           # 检查 MongoDB 状态
           systemctl status mongod
           # 或使用 Docker
           docker ps | grep mongo
           ```
        
        2. **验证连接配置**
           - 检查 `.env` 文件中的 MongoDB 配置
           - 确认数据库地址、端口、用户名和密码
        
        3. **查看详细日志**
           ```bash
           # 查看应用日志
           tail -f logs/tradingagents.log
           ```
        """)
    
    with tab3:
        st.markdown("### 联系技术支持")
        st.info("""
        如果问题持续存在，请联系技术支持团队：
        
        **提供以下信息有助于快速解决问题：**
        - 错误发生的具体时间
        - 您的操作步骤
        - 系统环境信息（操作系统、浏览器等）
        - 错误截图或日志信息
        """)
        
        if st.button("📤 生成诊断报告"):
            diagnostic_info = {
                "timestamp": datetime.now().isoformat(),
                "error_type": "storage_unavailable",
                "user_agent": st.context.headers.get("User-Agent", "Unknown"),
                "session_id": st.session_state.get("session_id", "Unknown")
            }
            
            st.code(f"""
诊断报告
========
时间: {diagnostic_info['timestamp']}
错误类型: 存储服务不可用
用户代理: {diagnostic_info['user_agent']}
会话ID: {diagnostic_info['session_id']}

请将此信息提供给技术支持团队
            """)
            
            logger.info("User generated diagnostic report for storage unavailable", extra=diagnostic_info)
    
    # Add a refresh timer
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 30秒后自动重试", help="页面将在30秒后自动刷新"):
            with st.spinner("等待自动重试..."):
                for i in range(30, 0, -1):
                    st.text(f"⏳ {i} 秒后自动重试...")
                    time.sleep(1)
                st.rerun()


def _render_overview_metrics(stats: Dict[str, Any]):
    """Render enhanced overview metrics at the top of the page"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_analyses = stats.get('total_analyses', 0)
        st.metric(
            label="📊 总分析数",
            value=total_analyses,
            help="历史记录中的分析总数"
        )
    
    with col2:
        completed_analyses = stats.get('completed_analyses', 0)
        success_rate = stats.get('success_rate', 0)
        st.metric(
            label="✅ 成功分析",
            value=completed_analyses,
            delta=f"{success_rate:.1f}% 成功率" if success_rate > 0 else None,
            help="成功完成的分析数量和成功率"
        )
    
    with col3:
        # Calculate recent analyses (last 7 days)
        recent_count = _calculate_recent_analyses_count(stats)
        st.metric(
            label="📅 最近7天",
            value=recent_count,
            help="最近7天内的分析数量"
        )
    
    with col4:
        avg_time = stats.get('avg_execution_time', 0)
        if avg_time > 0:
            if avg_time < 60:
                avg_time_str = f"{avg_time:.1f}s"
            else:
                minutes = int(avg_time // 60)
                seconds = avg_time % 60
                avg_time_str = f"{minutes}m{seconds:.0f}s"
        else:
            avg_time_str = "N/A"
        
        total_cost = stats.get('total_cost', 0)
        cost_delta = f"总成本 ¥{total_cost:.2f}" if total_cost > 0 else "免费使用"
        
        st.metric(
            label="⏱️ 平均用时",
            value=avg_time_str,
            delta=cost_delta,
            help="分析的平均执行时间和总成本"
        )
    
    # Add market distribution if available
    market_dist = stats.get('market_distribution', {})
    if market_dist:
        st.markdown("**📈 市场分布:**")
        market_cols = st.columns(len(market_dist))
        for i, (market, count) in enumerate(market_dist.items()):
            with market_cols[i]:
                percentage = (count / stats.get('total_analyses', 1)) * 100
                st.metric(
                    label=market,
                    value=count,
                    delta=f"{percentage:.1f}%",
                    help=f"{market}市场的分析数量和占比"
                )
    
    st.markdown("---")


def _calculate_recent_analyses_count(stats: Dict[str, Any]) -> int:
    """
    Calculate the number of analyses in the last 7 days
    This is a placeholder that would need to be implemented in the storage layer
    """
    # For now, return a placeholder value
    # In a real implementation, this would query the database for recent records
    return stats.get('recent_analyses', 0)


def _render_filter_controls() -> Dict[str, Any]:
    """
    Render enhanced filter controls with real-time updates and return current filter values
    
    Returns:
        Dictionary containing current filter values
    """
    st.subheader("🔍 筛选条件")
    
    # Initialize session state for filters if not exists
    filter_keys = [
        'history_stock_symbol', 'history_stock_name', 'history_market_type',
        'history_status', 'history_analysis_type', 'history_date_range',
        'history_page_size', 'history_sort_by', 'history_sort_order'
    ]
    
    for key in filter_keys:
        if key not in st.session_state:
            if key == 'history_date_range':
                st.session_state[key] = (datetime.now().date() - timedelta(days=30), datetime.now().date())
            elif key == 'history_page_size':
                st.session_state[key] = 20
            elif key == 'history_sort_by':
                st.session_state[key] = "创建时间"
            elif key == 'history_sort_order':
                st.session_state[key] = "降序"
            elif key in ['history_market_type', 'history_status', 'history_analysis_type']:
                st.session_state[key] = "全部"
            else:
                st.session_state[key] = ""
    
    # Create enhanced filter layout with better organization
    with st.container():
        # Row 1: Search fields
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Stock symbol search with enhanced functionality
            stock_symbol = st.text_input(
                "🔍 股票代码搜索",
                value=st.session_state.get('history_stock_symbol', ''),
                placeholder="输入股票代码 (如: AAPL, 000001, 0700.HK)",
                help="支持模糊搜索，输入部分代码即可匹配",
                key="stock_symbol_input"
            )
            
            # Update session state if changed
            if stock_symbol != st.session_state.get('history_stock_symbol', ''):
                st.session_state['history_stock_symbol'] = stock_symbol
                # Reset page when filter changes
                st.session_state['history_current_page'] = 1
        
        with col2:
            # Stock name search with enhanced functionality
            stock_name = st.text_input(
                "🏢 股票名称搜索",
                value=st.session_state.get('history_stock_name', ''),
                placeholder="输入股票名称 (如: 苹果, 腾讯)",
                help="支持模糊搜索，输入部分名称即可匹配",
                key="stock_name_input"
            )
            
            # Update session state if changed
            if stock_name != st.session_state.get('history_stock_name', ''):
                st.session_state['history_stock_name'] = stock_name
                # Reset page when filter changes
                st.session_state['history_current_page'] = 1
        
        with col3:
            # Combined search field for both symbol and name
            combined_search = st.text_input(
                "🔎 综合搜索",
                value="",
                placeholder="同时搜索代码和名称",
                help="在股票代码和名称中同时搜索关键词",
                key="combined_search_input"
            )
        
        # Row 2: Category filters
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Market type filter with enhanced options
            market_types = ["全部"] + [market.value for market in MarketType]
            market_type = st.selectbox(
                "🌍 市场类型",
                options=market_types,
                index=market_types.index(st.session_state.get('history_market_type', '全部')),
                help="按交易市场筛选分析记录",
                key="market_type_select"
            )
            
            # Update session state if changed
            if market_type != st.session_state.get('history_market_type', '全部'):
                st.session_state['history_market_type'] = market_type
                st.session_state['history_current_page'] = 1
        
        with col2:
            # Status filter with enhanced display
            status_options = ["全部"] + [status.value for status in AnalysisStatus]
            status_display_map = {
                "全部": "全部",
                AnalysisStatus.PENDING.value: "⏳ 等待中",
                AnalysisStatus.IN_PROGRESS.value: "🔄 进行中", 
                AnalysisStatus.COMPLETED.value: "✅ 已完成",
                AnalysisStatus.FAILED.value: "❌ 失败",
                AnalysisStatus.CANCELLED.value: "🚫 已取消"
            }
            
            status_display_options = [status_display_map.get(s, s) for s in status_options]
            current_status = st.session_state.get('history_status', '全部')
            current_status_index = status_options.index(current_status) if current_status in status_options else 0
            
            status_display_selected = st.selectbox(
                "📊 分析状态",
                options=status_display_options,
                index=current_status_index,
                help="按分析执行状态筛选",
                key="status_select"
            )
            
            # Convert back to actual status value
            status_filter = status_options[status_display_options.index(status_display_selected)]
            
            # Update session state if changed
            if status_filter != st.session_state.get('history_status', '全部'):
                st.session_state['history_status'] = status_filter
                st.session_state['history_current_page'] = 1
        
        with col3:
            # Analysis type filter (new requirement)
            analysis_types = ["全部", "comprehensive", "quick", "fundamental", "technical", "news", "social"]
            analysis_type_display_map = {
                "全部": "全部",
                "comprehensive": "🔍 综合分析",
                "quick": "⚡ 快速分析",
                "fundamental": "📊 基本面分析",
                "technical": "📈 技术分析",
                "news": "📰 新闻分析",
                "social": "💬 社交情绪分析"
            }
            
            analysis_type_display_options = [analysis_type_display_map.get(t, t) for t in analysis_types]
            current_analysis_type = st.session_state.get('history_analysis_type', '全部')
            current_analysis_type_index = analysis_types.index(current_analysis_type) if current_analysis_type in analysis_types else 0
            
            analysis_type_display_selected = st.selectbox(
                "🎯 分析类型",
                options=analysis_type_display_options,
                index=current_analysis_type_index,
                help="按分析类型筛选记录",
                key="analysis_type_select"
            )
            
            # Convert back to actual analysis type value
            analysis_type_filter = analysis_types[analysis_type_display_options.index(analysis_type_display_selected)]
            
            # Update session state if changed
            if analysis_type_filter != st.session_state.get('history_analysis_type', '全部'):
                st.session_state['history_analysis_type'] = analysis_type_filter
                st.session_state['history_current_page'] = 1
        
        with col4:
            # Analyst filter (new feature)
            analyst_options = ["全部", "market", "fundamentals", "news", "social"]
            analyst_display_map = {
                "全部": "全部",
                "market": "📈 市场分析师",
                "fundamentals": "📊 基本面分析师",
                "news": "📰 新闻分析师",
                "social": "💬 社交分析师"
            }
            
            analyst_display_options = [analyst_display_map.get(a, a) for a in analyst_options]
            
            analyst_filter = st.selectbox(
                "👥 分析师类型",
                options=analyst_display_options,
                index=0,
                help="按参与的分析师类型筛选",
                key="analyst_select"
            )
            
            # Convert back to actual analyst value
            analyst_value = analyst_options[analyst_display_options.index(analyst_filter)]
        
        # Row 3: Date range and advanced options
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Enhanced date range filter with presets
            st.write("📅 日期范围")
            
            # Date range presets
            date_presets = {
                "最近7天": (datetime.now().date() - timedelta(days=7), datetime.now().date()),
                "最近30天": (datetime.now().date() - timedelta(days=30), datetime.now().date()),
                "最近90天": (datetime.now().date() - timedelta(days=90), datetime.now().date()),
                "今年": (datetime(datetime.now().year, 1, 1).date(), datetime.now().date()),
                "自定义": st.session_state.get('history_date_range', (datetime.now().date() - timedelta(days=30), datetime.now().date()))
            }
            
            preset_selected = st.selectbox(
                "快速选择",
                options=list(date_presets.keys()),
                index=1,  # Default to "最近30天"
                help="选择预设日期范围或自定义",
                key="date_preset_select",
                label_visibility="collapsed"
            )
            
            if preset_selected != "自定义":
                date_range = date_presets[preset_selected]
                st.session_state['history_date_range'] = date_range
            else:
                date_range = st.date_input(
                    "自定义日期范围",
                    value=st.session_state.get('history_date_range', (datetime.now().date() - timedelta(days=30), datetime.now().date())),
                    help="选择自定义分析日期范围",
                    key="custom_date_range",
                    label_visibility="collapsed"
                )
                st.session_state['history_date_range'] = date_range
        
        with col2:
            # Page size with better options
            st.write("📄 显示设置")
            page_size_options = [10, 20, 50, 100]
            current_page_size = st.session_state.get('history_page_size', 20)
            page_size_index = page_size_options.index(current_page_size) if current_page_size in page_size_options else 1
            
            page_size = st.selectbox(
                "每页显示",
                options=page_size_options,
                index=page_size_index,
                help="每页显示的记录数量",
                key="page_size_select",
                label_visibility="collapsed"
            )
            
            # Update session state if changed
            if page_size != st.session_state.get('history_page_size', 20):
                st.session_state['history_page_size'] = page_size
                st.session_state['history_current_page'] = 1
        
        with col3:
            # Enhanced sorting controls
            st.write("🔄 排序设置")
            sort_options = {
                "创建时间": "created_at",
                "分析日期": "analysis_date",
                "股票代码": "stock_symbol", 
                "股票名称": "stock_name",
                "执行时间": "execution_time",
                "分析状态": "status",
                "市场类型": "market_type",
                "分析成本": "token_usage.total_cost"
            }
            
            current_sort_by = st.session_state.get('history_sort_by', '创建时间')
            sort_by_index = list(sort_options.keys()).index(current_sort_by) if current_sort_by in sort_options.keys() else 0
            
            sort_by_display = st.selectbox(
                "排序字段",
                options=list(sort_options.keys()),
                index=sort_by_index,
                help="选择排序字段",
                key="sort_by_select",
                label_visibility="collapsed"
            )
            
            # Update session state if changed
            if sort_by_display != st.session_state.get('history_sort_by', '创建时间'):
                st.session_state['history_sort_by'] = sort_by_display
        
        with col4:
            # Sort order
            st.write("⬆️⬇️ 排序方向")
            sort_order_options = ["降序", "升序"]
            current_sort_order = st.session_state.get('history_sort_order', '降序')
            sort_order_index = sort_order_options.index(current_sort_order) if current_sort_order in sort_order_options else 0
            
            sort_order_display = st.selectbox(
                "排序方向",
                options=sort_order_options,
                index=sort_order_index,
                help="选择排序方向",
                key="sort_order_select",
                label_visibility="collapsed"
            )
            
            # Update session state if changed
            if sort_order_display != st.session_state.get('history_sort_order', '降序'):
                st.session_state['history_sort_order'] = sort_order_display
    
    # Action buttons row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🧹 清除所有筛选", help="清除所有筛选条件并重置为默认值", type="secondary"):
            # Clear all filter session state
            for key in filter_keys:
                if key in st.session_state:
                    del st.session_state[key]
            # Reset page
            if 'history_current_page' in st.session_state:
                del st.session_state['history_current_page']
            st.rerun()
    
    with col2:
        # Show active filters count
        active_filters = _count_active_filters({
            'stock_symbol': stock_symbol,
            'stock_name': stock_name,
            'combined_search': combined_search,
            'market_type': market_type,
            'status': status_filter,
            'analysis_type': analysis_type_filter,
            'analyst': analyst_value
        })
        
        if active_filters > 0:
            st.info(f"🔍 已应用 {active_filters} 个筛选条件")
        else:
            st.success("📋 显示所有记录")
    
    with col3:
        # Quick filter buttons for common scenarios
        if st.button("⚡ 仅显示成功", help="快速筛选仅显示成功完成的分析"):
            st.session_state['history_status'] = AnalysisStatus.COMPLETED.value
            st.session_state['history_current_page'] = 1
            st.rerun()
    
    with col4:
        # Bulk delete button
        if st.button("🗑️ 批量删除", help="选择多条记录进行批量删除", type="secondary"):
            st.session_state['show_bulk_delete'] = True
            st.session_state['selected_for_delete'] = set()
            st.rerun()
    
    st.markdown("---")
    
    # Process date range with better error handling
    start_date = None
    end_date = None
    
    try:
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date = datetime.combine(date_range[0], datetime.min.time())
            end_date = datetime.combine(date_range[1], datetime.max.time())
        elif hasattr(date_range, '__iter__'):
            date_list = list(date_range)
            if len(date_list) == 2:
                start_date = datetime.combine(date_list[0], datetime.min.time())
                end_date = datetime.combine(date_list[1], datetime.max.time())
            elif len(date_list) == 1:
                # Single date selected, use as both start and end
                start_date = datetime.combine(date_list[0], datetime.min.time())
                end_date = datetime.combine(date_list[0], datetime.max.time())
    except Exception as e:
        logger.warning(f"Error processing date range: {e}")
        # Fallback to default date range
        start_date = datetime.combine(datetime.now().date() - timedelta(days=30), datetime.min.time())
        end_date = datetime.combine(datetime.now().date(), datetime.max.time())
    
    # Convert sort options
    sort_by = sort_options[sort_by_display]
    sort_order = -1 if sort_order_display == "降序" else 1
    
    # Build comprehensive filter dictionary
    filters = {
        'stock_symbol': stock_symbol.strip() if stock_symbol else None,
        'stock_name': stock_name.strip() if stock_name else None,
        'combined_search': combined_search.strip() if combined_search else None,
        'market_type': market_type if market_type != "全部" else None,
        'status': status_filter if status_filter != "全部" else None,
        'analysis_type': analysis_type_filter if analysis_type_filter != "全部" else None,
        'analyst': analyst_value if analyst_value != "全部" else None,
        'start_date': start_date,
        'end_date': end_date,
        'page': 1,  # Will be updated by pagination controls
        'page_size': page_size,
        'sort_by': sort_by,
        'sort_order': sort_order
    }
    
    # Store current filters in session state for bulk delete functionality
    st.session_state['current_filters'] = filters
    
    return filters


def _count_active_filters(filters: Dict[str, Any]) -> int:
    """Count the number of active filters"""
    count = 0
    for key, value in filters.items():
        if key in ['market_type', 'status', 'analysis_type', 'analyst']:
            if value and value != "全部":
                count += 1
        elif key in ['stock_symbol', 'stock_name', 'combined_search']:
            if value and value.strip():
                count += 1
    return count


@with_error_handling(context="获取筛选历史记录", show_user_error=False)
def _get_filtered_history(storage, filters: Dict[str, Any]) -> Tuple[List[AnalysisHistoryRecord], int]:
    """
    Get filtered history records from storage with enhanced query optimization and error handling
    
    Args:
        storage: History storage instance
        filters: Filter parameters
        
    Returns:
        Tuple of (records, total_count)
    """
    try:
        # Validate storage availability
        if not storage or not storage.is_available():
            logger.warning("Storage not available for filtered history query")
            return [], 0
        
        # Build MongoDB filter query with optimized structure
        query_filters = {}
        
        # Combined search functionality (new requirement)
        if filters.get('combined_search'):
            search_term = filters['combined_search'].strip()
            if search_term:
                # Escape special regex characters to prevent injection
                escaped_term = re.escape(search_term)
                # Search in both stock symbol and name simultaneously
                query_filters['$or'] = [
                    {'stock_symbol': {'$regex': escaped_term, '$options': 'i'}},
                    {'stock_name': {'$regex': escaped_term, '$options': 'i'}}
                ]
        else:
            # Individual field searches
            if filters.get('stock_symbol'):
                symbol_term = filters['stock_symbol'].strip()
                if symbol_term:
                    query_filters['stock_symbol'] = {'$regex': re.escape(symbol_term), '$options': 'i'}
            
            if filters.get('stock_name'):
                name_term = filters['stock_name'].strip()
                if name_term:
                    query_filters['stock_name'] = {'$regex': re.escape(name_term), '$options': 'i'}
        
        # Market type filter
        if filters.get('market_type'):
            query_filters['market_type'] = filters['market_type']
        
        # Status filter
        if filters.get('status'):
            query_filters['status'] = filters['status']
        
        # Analysis type filter
        if filters.get('analysis_type'):
            query_filters['analysis_type'] = filters['analysis_type']
        
        # Analyst filter
        if filters.get('analyst'):
            query_filters['analysts_used'] = {'$in': [filters['analyst']]}
        
        # Date range filter
        if filters.get('start_date') or filters.get('end_date'):
            date_query = {}
            if filters.get('start_date'):
                date_query['$gte'] = filters['start_date']
            if filters.get('end_date'):
                date_query['$lte'] = filters['end_date']
            
            if date_query:
                query_filters['created_at'] = date_query
        
        # Store query info for debugging
        if st.session_state.get('debug_mode', False):
            st.session_state['last_query_info'] = {
                'query': query_filters,
                'sort': f"{filters.get('sort_by', 'created_at')} ({filters.get('sort_order', -1)})"
            }
        
        # Execute query with error handling
        try:
            records, total_count = storage.get_user_history(
                filters=query_filters,
                page=filters.get('page', 1),
                page_size=filters.get('page_size', 20),
                sort_by=filters.get('sort_by', 'created_at'),
                sort_order=filters.get('sort_order', -1)
            )
            
            # Update debug info
            if st.session_state.get('debug_mode', False):
                st.session_state['last_query_info'].update({
                    'results': len(records),
                    'total': total_count
                })
            
            logger.debug(f"Retrieved {len(records)} records out of {total_count} total")
            return records, total_count
            
        except Exception as query_error:
            logger.error(f"Query execution failed: {query_error}")
            # Try a simpler fallback query
            try:
                logger.info("Attempting fallback query with basic filters only")
                fallback_filters = {}
                
                # Only include the most basic filters for fallback
                if filters.get('market_type'):
                    fallback_filters['market_type'] = filters['market_type']
                if filters.get('status'):
                    fallback_filters['status'] = filters['status']
                
                records, total_count = storage.get_user_history(
                    filters=fallback_filters,
                    page=1,  # Reset to first page
                    page_size=filters.get('page_size', 20),
                    sort_by='created_at',
                    sort_order=-1
                )
                
                logger.info(f"Fallback query succeeded: {len(records)} records")
                
                # Show warning to user about fallback
                st.warning("⚠️ 部分筛选条件可能未生效，显示基础查询结果")
                
                return records, total_count
                
            except Exception as fallback_error:
                logger.error(f"Fallback query also failed: {fallback_error}")
                raise query_error  # Re-raise original error
    
    except Exception as e:
        logger.error(f"Error in _get_filtered_history: {e}")
        return [], 0


def _build_search_conditions(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build MongoDB search conditions from filters"""
    search_conditions = []
    
    # Combined search (searches both symbol and name)
    if filters.get('combined_search'):
        search_term = filters['combined_search'].strip()
        if search_term:
            search_conditions.append({
                '$or': [
                    {'stock_symbol': {'$regex': re.escape(search_term), '$options': 'i'}},
                    {'stock_name': {'$regex': re.escape(search_term), '$options': 'i'}}
                ]
            })
    else:
        # Individual search filters (only if combined search is not used)
        pass
        
        # Stock symbol filter - optimized with different strategies based on input length
        if filters.get('stock_symbol'):
            symbol = filters['stock_symbol'].strip()
            if len(symbol) >= 4:  # Likely complete or near-complete symbol
                search_conditions.append({'stock_symbol': {'$regex': f'^{re.escape(symbol)}', '$options': 'i'}})
            elif len(symbol) >= 2:  # Partial symbol search
                search_conditions.append({'stock_symbol': {'$regex': re.escape(symbol), '$options': 'i'}})
            else:  # Single character - use starts with for better performance
                search_conditions.append({'stock_symbol': {'$regex': f'^{re.escape(symbol)}', '$options': 'i'}})
        
        # Stock name filter - enhanced with text search fallback
        if filters.get('stock_name'):
            name = filters['stock_name'].strip()
            # Use text search for better performance on longer names
            if len(name) >= 2:
                search_conditions.append({'stock_name': {'$regex': re.escape(name), '$options': 'i'}})
        
        # Combine search conditions with OR if multiple exist
        if len(search_conditions) > 1:
            query_filters['$and'] = [{'$or': search_conditions}]
        elif len(search_conditions) == 1:
            query_filters.update(search_conditions[0])
    
    # Market type filter - exact match for optimal index usage
    if filters.get('market_type'):
        query_filters['market_type'] = filters['market_type']
    
    # Status filter - exact match for optimal index usage
    if filters.get('status'):
        query_filters['status'] = filters['status']
    
    # Analysis type filter (new requirement)
    if filters.get('analysis_type'):
        query_filters['analysis_type'] = filters['analysis_type']
    
    # Analyst filter (new requirement) - check if analyst is in the analysts_used array
    if filters.get('analyst'):
        query_filters['analysts_used'] = {'$in': [filters['analyst']]}
    
    # Date range filter - optimized for index usage with proper boundary handling
    date_filter = {}
    if filters.get('start_date'):
        date_filter['$gte'] = filters['start_date']
    if filters.get('end_date'):
        date_filter['$lte'] = filters['end_date']
    
    if date_filter:
        query_filters['created_at'] = date_filter
    
    try:
        # Get sort parameters with enhanced validation
        sort_by = filters.get('sort_by', 'created_at')
        sort_order = filters.get('sort_order', -1)
        
        # Expanded list of valid sort fields including new options
        valid_sort_fields = [
            'created_at', 'analysis_date', 'stock_symbol', 'stock_name', 
            'execution_time', 'status', 'market_type', 'analysis_type',
            'token_usage.total_cost', 'llm_provider', 'research_depth'
        ]
        
        if sort_by not in valid_sort_fields:
            logger.warning(f"Invalid sort field: {sort_by}, using default")
            sort_by = 'created_at'
        
        # Log query for debugging (in development mode)
        logger.debug(f"Executing history query: {query_filters}")
        logger.debug(f"Sort: {sort_by} ({sort_order}), Page: {filters.get('page', 1)}, Size: {filters.get('page_size', 20)}")
        
        # Execute query with optimized parameters
        records, total_count = storage.get_user_history(
            filters=query_filters,
            page=filters.get('page', 1),
            page_size=filters.get('page_size', 20),
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Log performance metrics
        logger.debug(f"Query completed: {len(records)} records from {total_count} total, "
                    f"page {filters.get('page', 1)}, sort by {sort_by}")
        
        # Add query performance info to session state for debugging
        if 'debug_mode' in st.session_state and st.session_state.debug_mode:
            st.session_state['last_query_info'] = {
                'query': query_filters,
                'results': len(records),
                'total': total_count,
                'sort': f"{sort_by} ({sort_order})"
            }
        
        return records, total_count
        
    except Exception as e:
        logger.error(f"Error getting filtered history: {e}")
        st.error(f"获取历史记录时出错: {e}")
        
        # Show detailed error in debug mode
        if 'debug_mode' in st.session_state and st.session_state.debug_mode:
            st.error(f"详细错误信息: {str(e)}")
            st.json(query_filters)
        
        return [], 0


def _has_any_filters_applied(filters: Dict[str, Any]) -> bool:
    """Check if any filters are currently applied (excluding default date range)"""
    return any([
        filters.get('stock_symbol'),
        filters.get('stock_name'),
        filters.get('combined_search'),
        filters.get('market_type'),
        filters.get('status'),
        filters.get('analysis_type'),
        filters.get('analyst'),
        # Date range is considered applied only if it's not the default 30-day range
        _is_custom_date_range_applied(filters)
    ])


def _is_custom_date_range_applied(filters: Dict[str, Any]) -> bool:
    """Check if a custom date range (not default 30 days) is applied"""
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    
    if not start_date or not end_date:
        return False
    
    # Check if it's the default 30-day range
    default_start = datetime.combine(datetime.now().date() - timedelta(days=30), datetime.min.time())
    default_end = datetime.combine(datetime.now().date(), datetime.max.time())
    
    # Allow some tolerance for time differences (1 hour)
    tolerance = timedelta(hours=1)
    
    start_diff = abs((start_date - default_start).total_seconds())
    end_diff = abs((end_date - default_end).total_seconds())
    
    return start_diff > tolerance.total_seconds() or end_diff > tolerance.total_seconds()


def _render_no_results_found():
    """Render message when no results match the current filters"""
    st.info("🔍 没有找到符合筛选条件的分析记录")
    st.markdown("""
    **建议：**
    - 尝试调整筛选条件
    - 扩大日期范围
    - 清除部分筛选条件
    """)


def _render_empty_state():
    """Render empty state when user has no history"""
    st.info("📊 您还没有任何分析历史记录")
    
    # Create a helpful empty state with guidance
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        ### 🚀 开始您的第一次分析
        
        要创建分析历史记录，请：
        
        1. **返回股票分析页面**
           - 点击侧边栏的 "📊 股票分析"
        
        2. **配置分析参数**
           - 输入股票代码
           - 选择分析师类型
           - 设置研究深度
        
        3. **执行分析**
           - 点击 "开始分析" 按钮
           - 等待分析完成
        
        4. **查看历史记录**
           - 分析完成后会自动保存到历史记录
           - 返回此页面即可查看
        
        ---
        
        ### 💡 提示
        - 所有成功完成的分析都会自动保存
        - 您可以随时回来查看和下载历史报告
        - 支持按股票代码、日期等条件筛选
        """)
        
        # Add a button to navigate back to analysis
        if st.button("🔙 前往股票分析页面", type="primary"):
            # This will be handled by the main app navigation
            st.info("请使用侧边栏导航到 '📊 股票分析' 页面")


def _render_pagination_controls(total_count: int, page_size: int, position: str = 'top') -> int:
    """
    Render enhanced pagination controls with better performance
    
    Args:
        total_count: Total number of records
        page_size: Number of records per page
        position: 'top' or 'bottom' for styling
        
    Returns:
        Current page number
    """
    if total_count <= page_size:
        return 1
    
    total_pages = math.ceil(total_count / page_size)
    
    # Get current page from session state with unified key
    page_key = "history_current_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    
    current_page = st.session_state[page_key]
    
    # Ensure current page is within valid range
    current_page = max(1, min(current_page, total_pages))
    st.session_state[page_key] = current_page
    
    # Create enhanced pagination layout
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 2, 1, 1])
    
    with col1:
        if st.button("⏮️ 首页", key=f"first_{position}", disabled=(current_page == 1)):
            st.session_state[page_key] = 1
            st.rerun()
    
    with col2:
        if st.button("◀️ 上页", key=f"prev_{position}", disabled=(current_page == 1)):
            st.session_state[page_key] = max(1, current_page - 1)
            st.rerun()
    
    with col3:
        # Quick jump to specific page ranges
        if total_pages > 10:
            jump_options = []
            # Add page ranges for quick navigation
            for i in range(1, total_pages + 1, max(1, total_pages // 10)):
                if i == 1:
                    jump_options.append(f"第1页")
                elif i + 9 >= total_pages:
                    jump_options.append(f"第{total_pages}页")
                else:
                    jump_options.append(f"第{i}-{min(i+9, total_pages)}页")
            
            # Find current selection
            current_range_idx = 0
            for idx, option in enumerate(jump_options):
                if "第1页" in option and current_page == 1:
                    current_range_idx = idx
                    break
                elif f"第{total_pages}页" in option and current_page == total_pages:
                    current_range_idx = idx
                    break
                elif "-" in option:
                    start_page = int(option.split("第")[1].split("-")[0])
                    end_page = int(option.split("-")[1].split("页")[0])
                    if start_page <= current_page <= end_page:
                        current_range_idx = idx
                        break
            
            selected_range = st.selectbox(
                "快速跳转",
                options=jump_options,
                index=current_range_idx,
                key=f"jump_{position}",
                label_visibility="collapsed"
            )
            
            # Handle range selection
            if selected_range != jump_options[current_range_idx]:
                if "第1页" in selected_range:
                    st.session_state[page_key] = 1
                elif f"第{total_pages}页" in selected_range:
                    st.session_state[page_key] = total_pages
                elif "-" in selected_range:
                    start_page = int(selected_range.split("第")[1].split("-")[0])
                    st.session_state[page_key] = start_page
                st.rerun()
    
    with col4:
        # Direct page input with validation
        if total_pages <= 100:  # Use selectbox for smaller page counts
            page_options = list(range(1, total_pages + 1))
            selected_page = st.selectbox(
                f"页码 (共 {total_pages} 页)",
                options=page_options,
                index=current_page - 1,
                key=f"page_select_{position}",
                label_visibility="collapsed"
            )
            
            if selected_page != current_page:
                st.session_state[page_key] = selected_page
                st.rerun()
        else:  # Use number input for large page counts
            selected_page = st.number_input(
                f"页码 (1-{total_pages})",
                min_value=1,
                max_value=total_pages,
                value=current_page,
                key=f"page_input_{position}",
                label_visibility="collapsed"
            )
            
            if selected_page != current_page:
                st.session_state[page_key] = int(selected_page)
                st.rerun()
    
    with col5:
        if st.button("▶️ 下页", key=f"next_{position}", disabled=(current_page == total_pages)):
            st.session_state[page_key] = min(total_pages, current_page + 1)
            st.rerun()
    
    with col6:
        if st.button("⏭️ 末页", key=f"last_{position}", disabled=(current_page == total_pages)):
            st.session_state[page_key] = total_pages
            st.rerun()
    
    # Show enhanced record count info
    start_record = (current_page - 1) * page_size + 1
    end_record = min(current_page * page_size, total_count)
    
    # Add performance info
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.caption(f"📊 显示第 {start_record}-{end_record} 条记录，共 {total_count} 条")
    with col_info2:
        st.caption(f"📄 第 {current_page} 页，共 {total_pages} 页")
    
    return current_page


def _render_history_table(records: List[AnalysisHistoryRecord]):
    """
    Render the main history table with enhanced sorting and display
    
    Args:
        records: List of analysis history records to display
    """
    if not records:
        st.info("当前页面没有记录")
        return
    
    # Add header row
    st.subheader(f"📋 分析记录 ({len(records)} 条)")
    
    header_col1, header_col2, header_col3, header_col4, header_col5, header_col6, header_col7, header_col8 = st.columns([1, 2, 1, 2, 1, 1, 1, 2])
    
    with header_col1:
        st.write("**股票代码**")
    with header_col2:
        st.write("**股票名称**")
    with header_col3:
        st.write("**市场**")
    with header_col4:
        st.write("**分析时间**")
    with header_col5:
        st.write("**状态**")
    with header_col6:
        st.write("**用时**")
    with header_col7:
        st.write("**成本**")
    with header_col8:
        st.write("**操作**")
    
    # Display table with action buttons integrated
    for i, record in enumerate(records):
        with st.container():
            # Create a bordered container for each record
            st.markdown("---")
            
            # Main record info in columns
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1, 2, 1, 2, 1, 1, 1, 2])
            
            with col1:
                st.write(f"**{record.stock_symbol}**")
            
            with col2:
                st.write(record.stock_name[:15] + "..." if len(record.stock_name) > 15 else record.stock_name)
            
            with col3:
                st.write(record.market_type)
            
            with col4:
                st.write(record.created_at.strftime("%m-%d %H:%M"))
            
            with col5:
                st.write(_get_status_display(record.status))
            
            with col6:
                if record.execution_time > 0:
                    if record.execution_time < 60:
                        st.write(f"{record.execution_time:.1f}s")
                    else:
                        minutes = int(record.execution_time // 60)
                        seconds = record.execution_time % 60
                        st.write(f"{minutes}m{seconds:.0f}s")
                else:
                    st.write("N/A")
            
            with col7:
                st.write(record.get_cost_summary())
            
            with col8:
                # Action buttons in the same row
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                
                with btn_col1:
                    if st.button(
                        "👁️",
                        key=f"view_{record.analysis_id}_{i}",
                        help=f"查看详情",
                        use_container_width=True
                    ):
                        _show_analysis_detail(record)
                
                with btn_col2:
                    # 使用新的下载菜单组件
                    _render_download_menu(record, f"{record.analysis_id}_{i}")
                
                with btn_col3:
                    if st.button(
                        "🗑️",
                        key=f"delete_{record.analysis_id}_{i}",
                        help=f"删除记录",
                        use_container_width=True
                    ):
                        _handle_delete_request(record)


def _get_status_display(status: str) -> str:
    """Get display-friendly status with emoji"""
    status_map = {
        AnalysisStatus.PENDING.value: "⏳ 等待中",
        AnalysisStatus.IN_PROGRESS.value: "🔄 进行中",
        AnalysisStatus.COMPLETED.value: "✅ 已完成",
        AnalysisStatus.FAILED.value: "❌ 失败",
        AnalysisStatus.CANCELLED.value: "🚫 已取消"
    }
    return status_map.get(status, f"❓ {status}")


def _show_analysis_detail(record: AnalysisHistoryRecord):
    """Set the selected record for detail view at the bottom of the page"""
    # Store the selected analysis record in session state for bottom detail display
    st.session_state['selected_detail_record'] = record
    
    # Show success message
    st.success(f"✅ 已选择查看 {record.stock_symbol} ({record.stock_name}) 的详情，请滚动到页面底部查看")
    
    # Rerun to show the detail section
    st.rerun()



def _generate_simple_report(record: AnalysisHistoryRecord, export_data: dict) -> str:
    """Generate a simple text report from analysis data"""
    
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append(f"股票分析报告 - {record.stock_symbol} ({record.stock_name})")
    report_lines.append("=" * 60)
    report_lines.append("")
    
    # Basic information
    report_lines.append("📊 基本信息")
    report_lines.append("-" * 30)
    report_lines.append(f"股票代码: {record.stock_symbol}")
    report_lines.append(f"股票名称: {record.stock_name}")
    report_lines.append(f"市场类型: {record.market_type}")
    report_lines.append(f"分析日期: {record.analysis_date.strftime('%Y-%m-%d')}")
    report_lines.append(f"创建时间: {record.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"分析用时: {record.execution_time:.1f}秒")
    report_lines.append(f"分析师: {', '.join(record.analysts_used)}")
    report_lines.append(f"研究深度: {record.research_depth}")
    report_lines.append(f"LLM模型: {record.llm_provider}/{record.llm_model}")
    
    # Token使用信息
    if record.token_usage:
        token_usage = record.token_usage
        if 'total_cost' in token_usage:
            cost = token_usage['total_cost']
            if cost == 0:
                cost_str = "免费分析"
            elif cost < 0.01:
                cost_str = f"¥{cost:.4f}"
            else:
                cost_str = f"¥{cost:.2f}"
            report_lines.append(f"分析成本: {cost_str}")
        
        if 'total_tokens' in token_usage:
            report_lines.append(f"Token使用: {token_usage['total_tokens']}")
    
    report_lines.append("")
    
    # Analysis results
    if 'decision' in export_data and export_data['decision']:
        decision = export_data['decision']
        report_lines.append("💡 投资建议")
        report_lines.append("-" * 30)
        
        if isinstance(decision, dict):
            if 'action' in decision:
                report_lines.append(f"投资建议: {decision['action']}")
            if 'target_price' in decision:
                report_lines.append(f"目标价格: {decision['target_price']}")
            if 'confidence' in decision:
                report_lines.append(f"置信度: {decision['confidence']}")
            if 'risk_score' in decision:
                report_lines.append(f"风险评分: {decision['risk_score']}")
            if 'reasoning' in decision:
                report_lines.append(f"分析理由: {decision['reasoning']}")
        else:
            report_lines.append(f"投资建议: {decision}")
        
        report_lines.append("")
    
    # Market analysis
    if 'state' in export_data and export_data['state']:
        state = export_data['state']
        
        if 'market_report' in state and state['market_report']:
            report_lines.append("📈 市场分析")
            report_lines.append("-" * 30)
            report_lines.append(str(state['market_report']))
            report_lines.append("")
        
        if 'fundamentals_report' in state and state['fundamentals_report']:
            report_lines.append("📊 基本面分析")
            report_lines.append("-" * 30)
            report_lines.append(str(state['fundamentals_report']))
            report_lines.append("")
        
        if 'news_report' in state and state['news_report']:
            report_lines.append("📰 新闻分析")
            report_lines.append("-" * 30)
            report_lines.append(str(state['news_report']))
            report_lines.append("")
        
        if 'sentiment_report' in state and state['sentiment_report']:
            report_lines.append("💬 社交媒体情绪分析")
            report_lines.append("-" * 30)
            report_lines.append(str(state['sentiment_report']))
            report_lines.append("")
        
        if 'investment_plan' in state and state['investment_plan']:
            report_lines.append("📋 投资建议")
            report_lines.append("-" * 30)
            report_lines.append(str(state['investment_plan']))
            report_lines.append("")
    
    # Risk assessment
    if 'risk_assessment' in export_data and export_data['risk_assessment']:
        report_lines.append("⚠️ 风险评估")
        report_lines.append("-" * 30)
        report_lines.append(str(export_data['risk_assessment']))
        report_lines.append("")
    
    # Footer
    report_lines.append("=" * 60)
    report_lines.append("报告生成时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    report_lines.append("免责声明: 本报告仅供参考，不构成投资建议。投资有风险，决策需谨慎。")
    report_lines.append("=" * 60)
    
    return "\n".join(report_lines)


def _handle_format_download(record: AnalysisHistoryRecord, format_type: str):
    """
    处理指定格式的下载请求
    
    Args:
        record: 分析历史记录
        format_type: 下载格式 ('markdown', 'docx', 'pdf')
    """
    if not record.is_completed():
        st.error("❌ 只有完成的分析才能下载")
        return
    
    try:
        # 构建适合报告导出器的数据格式
        results_for_export = {
            # 基本信息（使用原始分析时的信息）
            'stock_symbol': record.stock_symbol,
            'analysis_date': record.analysis_date,
            'market_type': record.market_type,
            
            # 分析结果（使用保存的格式化结果）
            'decision': record.formatted_results.get('decision', {}) if record.formatted_results else record.raw_results.get('decision', {}),
            'state': record.formatted_results.get('state', {}) if record.formatted_results else record.raw_results.get('state', {}),
            
            # 配置信息（使用原始分析时的配置）
            'llm_provider': record.llm_provider,
            'llm_model': record.llm_model,
            'analysts': record.analysts_used,
            'research_depth': record.research_depth,
            'execution_time': record.execution_time,
            
            # 历史记录特有信息
            'analysis_id': record.analysis_id,
            'created_at': record.created_at,
            'formatted_results': record.formatted_results,
            'raw_results': record.raw_results,
            'token_usage': record.token_usage,
            
            # 标记为历史数据
            'is_demo': False,
            'is_historical': True
        }
        
        # 使用报告导出器生成指定格式
        from web.utils.report_exporter import report_exporter
        
        content = report_exporter.export_report(results_for_export, format_type)
        
        if content:
            # 生成文件名
            analysis_datetime_str = record.created_at.strftime("%Y%m%d_%H%M%S")
            
            # 根据格式设置文件扩展名和MIME类型
            if format_type == 'markdown':
                file_extension = 'md'
                mime_type = 'text/markdown'
            elif format_type == 'docx':
                file_extension = 'docx'
                mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif format_type == 'pdf':
                file_extension = 'pdf'
                mime_type = 'application/pdf'
            else:
                st.error(f"❌ 不支持的格式: {format_type}")
                return
            
            filename = f"{record.stock_symbol}_analysis_{analysis_datetime_str}.{file_extension}"
            
            # 显示下载按钮
            st.download_button(
                label=f"📥 下载 {format_type.upper()} 报告",
                data=content,
                file_name=filename,
                mime=mime_type,
                key=f"download_{format_type}_{record.analysis_id}",
                help=f"下载 {record.stock_symbol} 的 {format_type.upper()} 格式分析报告"
            )
            
            st.success(f"✅ {format_type.upper()} 报告已准备好下载")
        else:
            st.error(f"❌ {format_type.upper()} 报告生成失败")
            
    except Exception as e:
        st.error(f"❌ 生成 {format_type.upper()} 报告时出错: {str(e)}")
        logger.error(f"Error generating {format_type} report for {record.analysis_id}: {e}")


@st.dialog("📥 下载分析报告")
def _show_download_dialog(record: AnalysisHistoryRecord):
    """
    显示下载对话框
    - PDF格式：打开对话框时预先生成，一键下载
    - Word/Markdown格式：点击后生成，两步下载
    
    Args:
        record: 分析历史记录
    """
    # 报告信息
    st.info(f"**{record.stock_symbol}** ({record.stock_name}) - {record.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    st.markdown("### 选择下载格式")
    st.markdown("PDF格式可直接下载，其他格式点击后生成")
    
    # 构建通用的导出数据格式
    results_for_export = {
        'stock_symbol': record.stock_symbol,
        'analysis_date': record.analysis_date,
        'market_type': record.market_type,
        'decision': record.formatted_results.get('decision', {}) if record.formatted_results else record.raw_results.get('decision', {}),
        'state': record.formatted_results.get('state', {}) if record.formatted_results else record.raw_results.get('state', {}),
        'llm_provider': record.llm_provider,
        'llm_model': record.llm_model,
        'analysts': record.analysts_used,
        'research_depth': record.research_depth,
        'execution_time': record.execution_time,
        'analysis_id': record.analysis_id,
        'created_at': record.created_at,
        'formatted_results': record.formatted_results,
        'raw_results': record.raw_results,
        'token_usage': record.token_usage,
        'is_demo': False,
        'is_historical': True
    }
    
    # 导入报告导出器
    from web.utils.report_exporter import report_exporter
    
    # 生成文件名基础部分
    analysis_datetime_str = record.created_at.strftime("%Y%m%d_%H%M%S")
    
    # 预先生成PDF内容（对话框打开时就生成）
    pdf_cache_key = f'pdf_content_{record.analysis_id}'
    if pdf_cache_key not in st.session_state:
        try:
            with st.spinner("正在准备PDF报告..."):
                pdf_content = report_exporter.export_report(results_for_export, 'pdf')
                st.session_state[pdf_cache_key] = pdf_content
        except Exception as e:
            st.session_state[pdf_cache_key] = None
            logger.error(f"PDF pre-generation error for {record.analysis_id}: {e}")
    
    # 检查其他格式的生成状态
    generate_docx = st.session_state.get(f'generate_docx_{record.analysis_id}', False)
    generate_md = st.session_state.get(f'generate_md_{record.analysis_id}', False)
    
    # 三个格式的按钮
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # PDF - 预先生成，直接下载
        pdf_content = st.session_state.get(pdf_cache_key)
        if pdf_content:
            filename = f"{record.stock_symbol}_analysis_{analysis_datetime_str}.pdf"
            st.download_button(
                label="📊 下载PDF格式",
                data=pdf_content,
                file_name=filename,
                mime="application/pdf",
                key=f"pdf_download_{record.analysis_id}",
                help="便携式文档格式，适合打印和分享（已预生成）",
                use_container_width=True,
                type="primary"
            )
        else:
            st.error("❌ PDF生成失败")
            if st.button("🔄 重新生成PDF", use_container_width=True):
                # 清除缓存，重新生成
                st.session_state.pop(pdf_cache_key, None)
                st.rerun()
    
    with col2:
        # Word - 按需生成
        if not generate_docx:
            if st.button(
                "📝 下载Word格式",
                use_container_width=True,
                help="Microsoft Word文档格式"
            ):
                st.session_state[f'generate_docx_{record.analysis_id}'] = True
                st.rerun()
        else:
            # 生成Word并提供下载
            try:
                with st.spinner("正在生成Word报告..."):
                    docx_content = report_exporter.export_report(results_for_export, 'docx')
                
                if docx_content:
                    filename = f"{record.stock_symbol}_analysis_{analysis_datetime_str}.docx"
                    st.download_button(
                        label="💾 下载Word",
                        data=docx_content,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"docx_download_{record.analysis_id}",
                        use_container_width=True
                    )
                    st.success("✅ Word生成成功！")
                else:
                    st.error("❌ Word生成失败")
                    
                # 重置状态
                st.session_state[f'generate_docx_{record.analysis_id}'] = False
                
            except Exception as e:
                st.error(f"❌ Word生成错误: {str(e)}")
                st.session_state[f'generate_docx_{record.analysis_id}'] = False
                logger.error(f"Word generation error for {record.analysis_id}: {e}")
    
    with col3:
        # Markdown - 按需生成
        if not generate_md:
            if st.button(
                "📄 下载Markdown格式",
                use_container_width=True,
                help="轻量级文本格式，支持所有编辑器"
            ):
                st.session_state[f'generate_md_{record.analysis_id}'] = True
                st.rerun()
        else:
            # 生成Markdown并提供下载
            try:
                with st.spinner("正在生成Markdown报告..."):
                    md_content = report_exporter.export_report(results_for_export, 'markdown')
                
                if md_content:
                    filename = f"{record.stock_symbol}_analysis_{analysis_datetime_str}.md"
                    st.download_button(
                        label="💾 下载Markdown",
                        data=md_content,
                        file_name=filename,
                        mime="text/markdown",
                        key=f"md_download_{record.analysis_id}",
                        use_container_width=True
                    )
                    st.success("✅ Markdown生成成功！")
                else:
                    st.error("❌ Markdown生成失败")
                    
                # 重置状态
                st.session_state[f'generate_md_{record.analysis_id}'] = False
                
            except Exception as e:
                st.error(f"❌ Markdown生成错误: {str(e)}")
                st.session_state[f'generate_md_{record.analysis_id}'] = False
                logger.error(f"Markdown generation error for {record.analysis_id}: {e}")
    
    st.markdown("---")
    
    # 取消按钮
    if st.button(
        "❌ 关闭",
        use_container_width=True
    ):
        # 清理session state
        st.session_state.pop(f'generate_docx_{record.analysis_id}', None)
        st.session_state.pop(f'generate_md_{record.analysis_id}', None)
        # 保留PDF缓存，下次打开对话框时可以直接使用
        st.rerun()


def _render_download_menu(record: AnalysisHistoryRecord, key_suffix: str):
    """
    渲染下载按钮，点击后显示下载对话框
    
    Args:
        record: 分析历史记录
        key_suffix: 按钮key的后缀，确保唯一性
    """
    if not record.is_completed():
        st.button(
            "📥 下载",
            key=f"download_disabled_{key_suffix}",
            help="分析未完成，无法下载",
            disabled=True,
            use_container_width=True
        )
        return
    
    # 显示下载按钮，点击后打开对话框
    if st.button(
        "📥 下载",
        key=f"download_menu_{key_suffix}",
        help="点击选择下载格式 (PDF/Word/Markdown)",
        use_container_width=True
    ):
        _show_download_dialog(record)


# 以下函数已弃用，保留用于向后兼容
def _handle_quick_txt_download(record: AnalysisHistoryRecord):
    """
    [已弃用] 处理表格中的快速TXT下载请求
    现在使用 _handle_format_download 和 _render_download_menu 替代
    """
    logger.warning("_handle_quick_txt_download is deprecated, use _handle_format_download instead")
    _handle_format_download(record, 'markdown')


def _handle_download_request(record: AnalysisHistoryRecord):
    """
    [已弃用] 处理历史记录的完整报告下载请求
    现在下载功能已移至表格中，此函数不再使用
    """
    logger.warning("_handle_download_request is deprecated, download functionality moved to table")
    st.info("💡 请在上方表格中点击下载按钮选择格式下载")


def _render_bottom_detail_section():
    """Render analysis detail section at the fixed bottom of the page"""
    
    # Check if a record is selected for detail view
    selected_record = st.session_state.get('selected_detail_record')
    
    if selected_record:
        # Create a clear separation from the main content
        st.markdown("---")
        st.markdown("---")  # Double line for stronger separation
        
        # Fixed bottom detail container with distinct styling
        with st.container():
            # Header with prominent styling and close button
            col1, col2 = st.columns([5, 1])
            
            with col1:
                st.markdown(f"## 🔍 详情查看: {selected_record.stock_symbol} ({selected_record.stock_name})")
                st.caption(f"分析ID: {selected_record.analysis_id} | 状态: {_get_status_display(selected_record.status)}")
            
            with col2:
                if st.button("❌ 关闭", key="close_bottom_detail", type="secondary"):
                    st.session_state['selected_detail_record'] = None
                    st.rerun()
            
            # Create tabs for organized information display
            tab1, tab2, tab3, tab4 = st.tabs(["📋 基本信息", "💡 投资建议", "📈 分析报告", "🔧 操作"])
            
            with tab1:
                # Basic information in a clean layout
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("股票代码", selected_record.stock_symbol)
                    st.metric("分析日期", selected_record.analysis_date.strftime("%Y-%m-%d"))
                
                with col2:
                    st.metric("股票名称", selected_record.stock_name)
                    st.metric("创建时间", selected_record.created_at.strftime("%Y-%m-%d %H:%M"))
                
                with col3:
                    st.metric("市场类型", selected_record.market_type)
                    exec_time = f"{selected_record.execution_time:.1f}s" if selected_record.execution_time > 0 else "N/A"
                    st.metric("执行时间", exec_time)
                
                with col4:
                    st.metric("分析状态", _get_status_display(selected_record.status))
                    st.metric("分析成本", selected_record.get_cost_summary())
                
                # Analysis configuration
                st.markdown("#### 🔧 分析配置")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**分析师**: {', '.join(selected_record.analysts_used)}")
                with col2:
                    st.write(f"**研究深度**: {selected_record.research_depth}")
                with col3:
                    st.write(f"**LLM模型**: {selected_record.llm_provider}/{selected_record.llm_model}")
            
            with tab2:
                # Investment decision
                export_data = selected_record.formatted_results or selected_record.raw_results
                
                if export_data and 'decision' in export_data and export_data['decision']:
                    decision = export_data['decision']
                    
                    if isinstance(decision, dict):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if 'action' in decision:
                                action_color = {
                                    '买入': 'green',
                                    '卖出': 'red', 
                                    '持有': 'blue'
                                }.get(decision['action'], 'gray')
                                st.markdown(f"### :{action_color}[{decision['action']}]")
                        
                        with col2:
                            if 'confidence' in decision:
                                confidence_val = decision['confidence']
                                if isinstance(confidence_val, (int, float)):
                                    st.metric("置信度", f"{confidence_val:.2f}")
                                else:
                                    st.metric("置信度", str(confidence_val))
                        
                        with col3:
                            if 'risk_score' in decision:
                                risk_val = decision['risk_score']
                                if isinstance(risk_val, (int, float)):
                                    st.metric("风险评分", f"{risk_val:.2f}")
                                else:
                                    st.metric("风险评分", str(risk_val))
                        
                        if 'reasoning' in decision:
                            st.markdown("#### 📝 分析理由")
                            reasoning = str(decision['reasoning'])
                            st.text_area("", reasoning, height=200, disabled=True, key="reasoning_display")
                    else:
                        st.markdown(f"### 投资建议: {decision}")
                else:
                    st.info("💡 暂无投资建议信息")
            
            with tab3:
                # Analysis reports in expandable sections
                export_data = selected_record.formatted_results or selected_record.raw_results
                
                if export_data and 'state' in export_data and export_data['state']:
                    state = export_data['state']
                    
                    # Market analysis
                    if 'market_report' in state and state['market_report']:
                        with st.expander("📈 市场分析报告", expanded=False):
                            st.markdown(str(state['market_report']))
                    
                    # Fundamental analysis
                    if 'fundamentals_report' in state and state['fundamentals_report']:
                        with st.expander("📊 基本面分析报告", expanded=False):
                            st.markdown(str(state['fundamentals_report']))
                    
                    # News analysis
                    if 'news_report' in state and state['news_report']:
                        with st.expander("📰 新闻分析报告", expanded=False):
                            st.markdown(str(state['news_report']))
                    
                    # Social sentiment analysis
                    if 'sentiment_report' in state and state['sentiment_report']:
                        with st.expander("💬 社交媒体情绪分析", expanded=False):
                            st.markdown(str(state['sentiment_report']))
                    
                    # Risk assessment
                    if 'risk_assessment' in export_data and export_data['risk_assessment']:
                        with st.expander("⚠️ 风险评估", expanded=False):
                            st.markdown(str(export_data['risk_assessment']))
                    
                    if not any([
                        state.get('market_report'),
                        state.get('fundamentals_report'), 
                        state.get('news_report'),
                        state.get('sentiment_report'),
                        export_data.get('risk_assessment')
                    ]):
                        st.info("📈 暂无详细分析报告")
                else:
                    st.info("📈 暂无详细分析报告")
            
            with tab4:
                # Action buttons (移除下载功能，下载已在表格中提供)
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🗑️ 删除此记录", key="bottom_detail_delete_btn", type="secondary"):
                        _handle_delete_request(selected_record)
                
                with col2:
                    if st.button("🔄 刷新数据", key="bottom_detail_refresh_btn"):
                        # Refresh the record data
                        st.rerun()
                
                # Additional information
                st.markdown("---")
                st.markdown("#### ℹ️ 操作说明")
                st.markdown("""
                - **下载报告**: 请在上方表格中点击"📥 下载"按钮选择格式下载
                - **删除记录**: 永久删除此分析记录（不可恢复）
                - **刷新数据**: 重新加载最新的分析状态
                """)
        
        # Add some bottom padding
        st.markdown("<br><br>", unsafe_allow_html=True)
