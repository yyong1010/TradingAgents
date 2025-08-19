#!/usr/bin/env python3
"""
Enhanced Loading States and Progress Indicators

This module provides comprehensive loading states and progress indicators
for long-running operations in the analysis history system.
"""

import streamlit as st
import time
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum

from tradingagents.utils.logging_manager import get_logger

logger = get_logger('web.loading_states')


class LoadingState(Enum):
    """Loading state types"""
    INITIALIZING = "initializing"
    LOADING = "loading"
    PROCESSING = "processing"
    COMPLETING = "completing"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class ProgressIndicator:
    """Enhanced progress indicator with multiple display modes"""
    
    def __init__(self, 
                 title: str,
                 estimated_duration: float = None,
                 show_percentage: bool = True,
                 show_time_remaining: bool = True,
                 show_steps: bool = False):
        self.title = title
        self.estimated_duration = estimated_duration
        self.show_percentage = show_percentage
        self.show_time_remaining = show_time_remaining
        self.show_steps = show_steps
        
        self.start_time = time.time()
        self.current_progress = 0.0
        self.current_step = ""
        self.state = LoadingState.INITIALIZING
        
        # UI elements
        self.progress_bar = None
        self.status_text = None
        self.step_text = None
        self.time_text = None
        self.container = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the UI elements"""
        self.container = st.container()
        
        with self.container:
            st.markdown(f"### {self.title}")
            
            # Progress bar
            self.progress_bar = st.progress(0)
            
            # Status and step information
            col1, col2 = st.columns([2, 1])
            
            with col1:
                self.status_text = st.empty()
                if self.show_steps:
                    self.step_text = st.empty()
            
            with col2:
                if self.show_time_remaining:
                    self.time_text = st.empty()
            
            # Initial status
            self.status_text.text("⏳ 准备中...")
    
    def update(self, 
               progress: float, 
               message: str = None, 
               step: str = None,
               state: LoadingState = LoadingState.LOADING):
        """Update progress with enhanced information"""
        try:
            self.current_progress = max(0.0, min(1.0, progress))
            self.state = state
            
            if step:
                self.current_step = step
            
            # Update progress bar
            if self.progress_bar:
                self.progress_bar.progress(self.current_progress)
            
            # Update status text
            if message and self.status_text:
                status_msg = self._format_status_message(message)
                self.status_text.text(status_msg)
            
            # Update step text
            if self.show_steps and self.current_step and self.step_text:
                self.step_text.text(f"📋 当前步骤: {self.current_step}")
            
            # Update time remaining
            if self.show_time_remaining and self.time_text:
                time_msg = self._calculate_time_remaining()
                self.time_text.text(time_msg)
            
            logger.debug(f"Progress updated: {self.current_progress*100:.1f}% - {message}")
            
        except Exception as e:
            logger.error(f"Error updating progress indicator: {e}")
    
    def _format_status_message(self, message: str) -> str:
        """Format status message with progress information"""
        status_icons = {
            LoadingState.INITIALIZING: "🔄",
            LoadingState.LOADING: "⏳",
            LoadingState.PROCESSING: "⚙️",
            LoadingState.COMPLETING: "✨",
            LoadingState.SUCCESS: "✅",
            LoadingState.ERROR: "❌",
            LoadingState.TIMEOUT: "⏰"
        }
        
        icon = status_icons.get(self.state, "⏳")
        
        if self.show_percentage:
            percentage = self.current_progress * 100
            return f"{icon} {message} ({percentage:.1f}%)"
        else:
            return f"{icon} {message}"
    
    def _calculate_time_remaining(self) -> str:
        """Calculate and format time remaining"""
        elapsed = time.time() - self.start_time
        
        if self.current_progress <= 0:
            if self.estimated_duration:
                return f"⏱️ 预计: {self._format_duration(self.estimated_duration)}"
            else:
                return "⏱️ 计算中..."
        
        if self.current_progress >= 0.99:
            return "⏱️ 即将完成"
        
        # Calculate remaining time based on current progress
        if self.estimated_duration:
            # Use estimated duration as baseline
            estimated_total = self.estimated_duration
            if elapsed > 10:  # After 10 seconds, adjust based on actual progress
                progress_based_total = elapsed / self.current_progress
                estimated_total = 0.7 * progress_based_total + 0.3 * self.estimated_duration
        else:
            # Use only progress-based estimation
            estimated_total = elapsed / self.current_progress if self.current_progress > 0 else 0
        
        remaining = max(0, estimated_total - elapsed)
        return f"⏱️ 剩余: {self._format_duration(remaining)}"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    
    def complete(self, message: str = "操作完成", success: bool = True):
        """Mark operation as complete"""
        if success:
            self.update(1.0, message, state=LoadingState.SUCCESS)
            if self.status_text:
                self.status_text.success(f"✅ {message}")
        else:
            self.state = LoadingState.ERROR
            if self.status_text:
                self.status_text.error(f"❌ {message}")
        
        # Keep progress bar at 100% for success, hide for error
        if success and self.progress_bar:
            self.progress_bar.progress(1.0)
        elif not success and self.progress_bar:
            self.progress_bar.empty()
    
    def error(self, message: str):
        """Mark operation as failed"""
        self.complete(message, success=False)
    
    def cleanup(self, delay: float = 2.0):
        """Clean up UI elements after a delay"""
        if delay > 0:
            time.sleep(delay)
        
        if self.container:
            self.container.empty()


class MultiStepLoader:
    """Multi-step loading indicator with detailed progress tracking"""
    
    def __init__(self, 
                 title: str,
                 steps: List[Dict[str, Any]],
                 estimated_total_duration: float = None):
        self.title = title
        self.steps = steps
        self.estimated_total_duration = estimated_total_duration
        
        self.current_step_index = 0
        self.start_time = time.time()
        self.step_start_time = time.time()
        
        # Calculate step weights if not provided
        total_weight = sum(step.get('weight', 1.0) for step in steps)
        for step in steps:
            if 'weight' not in step:
                step['weight'] = 1.0 / len(steps)
            else:
                step['weight'] = step['weight'] / total_weight
        
        # UI elements
        self.container = None
        self.progress_indicator = None
        self.steps_container = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the multi-step UI"""
        self.container = st.container()
        
        with self.container:
            # Main progress indicator
            self.progress_indicator = ProgressIndicator(
                self.title,
                self.estimated_total_duration,
                show_steps=True
            )
            
            # Steps overview
            st.markdown("#### 执行步骤")
            self.steps_container = st.container()
            self._render_steps_overview()
    
    def _render_steps_overview(self):
        """Render overview of all steps"""
        with self.steps_container:
            for i, step in enumerate(self.steps):
                col1, col2, col3 = st.columns([1, 4, 1])
                
                with col1:
                    if i < self.current_step_index:
                        st.success("✅")
                    elif i == self.current_step_index:
                        st.info("⏳")
                    else:
                        st.empty()
                
                with col2:
                    step_name = step.get('name', f'步骤 {i+1}')
                    step_desc = step.get('description', '')
                    
                    if i == self.current_step_index:
                        st.markdown(f"**{step_name}**")
                        if step_desc:
                            st.caption(step_desc)
                    else:
                        st.text(step_name)
                        if step_desc and i < self.current_step_index:
                            st.caption(step_desc)
                
                with col3:
                    weight_pct = step.get('weight', 0) * 100
                    st.caption(f"{weight_pct:.0f}%")
    
    def start_step(self, step_index: int, message: str = None):
        """Start a specific step"""
        if step_index >= len(self.steps):
            logger.warning(f"Invalid step index: {step_index}")
            return
        
        self.current_step_index = step_index
        self.step_start_time = time.time()
        
        step = self.steps[step_index]
        step_name = step.get('name', f'步骤 {step_index + 1}')
        
        # Calculate overall progress
        completed_weight = sum(s['weight'] for s in self.steps[:step_index])
        overall_progress = completed_weight
        
        # Update main progress indicator
        step_message = message or f"执行 {step_name}"
        self.progress_indicator.update(
            overall_progress,
            step_message,
            step_name,
            LoadingState.PROCESSING
        )
        
        # Update steps overview
        self._render_steps_overview()
        
        logger.info(f"Started step {step_index + 1}/{len(self.steps)}: {step_name}")
    
    def update_step_progress(self, step_progress: float, message: str = None):
        """Update progress within the current step"""
        if self.current_step_index >= len(self.steps):
            return
        
        step = self.steps[self.current_step_index]
        step_weight = step['weight']
        
        # Calculate overall progress
        completed_weight = sum(s['weight'] for s in self.steps[:self.current_step_index])
        current_step_progress = step_weight * step_progress
        overall_progress = completed_weight + current_step_progress
        
        # Update main progress indicator
        step_name = step.get('name', f'步骤 {self.current_step_index + 1}')
        step_message = message or f"执行 {step_name}"
        
        self.progress_indicator.update(
            overall_progress,
            step_message,
            step_name,
            LoadingState.PROCESSING
        )
    
    def complete_step(self, message: str = None):
        """Complete the current step"""
        if self.current_step_index >= len(self.steps):
            return
        
        step = self.steps[self.current_step_index]
        step_name = step.get('name', f'步骤 {self.current_step_index + 1}')
        
        step_duration = time.time() - self.step_start_time
        completion_message = message or f"{step_name} 完成"
        
        logger.info(f"Completed step {self.current_step_index + 1}/{len(self.steps)}: {step_name} ({step_duration:.2f}s)")
        
        # Move to next step or complete
        if self.current_step_index < len(self.steps) - 1:
            self.current_step_index += 1
            self._render_steps_overview()
        else:
            # All steps completed
            self.complete(message or "所有步骤已完成")
    
    def complete(self, message: str = "操作完成"):
        """Complete all steps"""
        self.progress_indicator.complete(message, success=True)
        
        # Update final steps overview
        self.current_step_index = len(self.steps)
        self._render_steps_overview()
        
        total_duration = time.time() - self.start_time
        logger.info(f"Multi-step operation completed: {self.title} ({total_duration:.2f}s)")
    
    def error(self, message: str, step_error: bool = False):
        """Handle error in multi-step operation"""
        if step_error:
            error_msg = f"步骤失败: {message}"
        else:
            error_msg = message
        
        self.progress_indicator.error(error_msg)
        
        total_duration = time.time() - self.start_time
        logger.error(f"Multi-step operation failed: {self.title} ({total_duration:.2f}s) - {message}")
    
    def cleanup(self, delay: float = 3.0):
        """Clean up UI elements"""
        if self.progress_indicator:
            self.progress_indicator.cleanup(delay)
        
        if self.container:
            self.container.empty()


def create_search_loader(estimated_duration: float = 5.0) -> MultiStepLoader:
    """Create a specialized loader for search operations"""
    search_steps = [
        {
            'name': '验证搜索条件',
            'description': '检查输入参数的有效性',
            'weight': 0.1
        },
        {
            'name': '构建数据库查询',
            'description': '根据筛选条件生成查询语句',
            'weight': 0.2
        },
        {
            'name': '执行查询',
            'description': '在数据库中搜索匹配的记录',
            'weight': 0.5
        },
        {
            'name': '处理结果',
            'description': '格式化和验证查询结果',
            'weight': 0.15
        },
        {
            'name': '渲染界面',
            'description': '在界面中显示搜索结果',
            'weight': 0.05
        }
    ]
    
    return MultiStepLoader("搜索分析记录", search_steps, estimated_duration)


def create_storage_loader(operation_name: str, estimated_duration: float = 3.0) -> MultiStepLoader:
    """Create a specialized loader for storage operations"""
    storage_steps = [
        {
            'name': '连接数据库',
            'description': '建立与MongoDB的连接',
            'weight': 0.2
        },
        {
            'name': f'执行{operation_name}',
            'description': f'在数据库中{operation_name}',
            'weight': 0.6
        },
        {
            'name': '验证结果',
            'description': '确认操作成功完成',
            'weight': 0.2
        }
    ]
    
    return MultiStepLoader(f"{operation_name}操作", storage_steps, estimated_duration)


def show_loading_skeleton(num_rows: int = 5):
    """Show a skeleton loading animation for table data"""
    with st.container():
        st.markdown("### 📊 加载中...")
        
        # Create skeleton rows
        for i in range(num_rows):
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
            
            with col1:
                st.markdown("▓▓▓▓▓▓▓▓")
            with col2:
                st.markdown("▓▓▓▓▓▓▓▓▓▓")
            with col3:
                st.markdown("▓▓▓▓▓▓")
            with col4:
                st.markdown("▓▓▓")
            with col5:
                st.markdown("▓▓")
            
            if i < num_rows - 1:
                st.markdown("---")


def show_error_with_retry(error_message: str, 
                         retry_callback: Callable = None,
                         show_details: bool = True) -> bool:
    """Show error message with retry option and return whether user wants to retry"""
    st.error(f"❌ {error_message}")
    
    if show_details:
        with st.expander("📋 错误详情"):
            st.text(f"发生时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            st.text(f"错误信息: {error_message}")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("🔄 重试", type="primary"):
            if retry_callback:
                retry_callback()
            return True
    
    with col2:
        if st.button("🏠 返回主页"):
            st.switch_page("web/app.py")
    
    return False