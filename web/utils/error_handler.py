#!/usr/bin/env python3
"""
Comprehensive Error Handler for Analysis History Tracking

This module provides centralized error handling, user-friendly error messages,
retry mechanisms, and progress indicators for the analysis history system.
"""

import logging
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Tuple, List
from enum import Enum
from functools import wraps
import streamlit as st

from tradingagents.utils.logging_manager import get_logger

logger = get_logger('web.error_handler')


class ErrorType(Enum):
    """Error type classifications for better error handling"""
    STORAGE_CONNECTION = "storage_connection"
    STORAGE_OPERATION = "storage_operation"
    DATA_VALIDATION = "data_validation"
    NETWORK_ERROR = "network_error"
    PERMISSION_ERROR = "permission_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UserFriendlyError:
    """Container for user-friendly error information"""
    
    def __init__(self, 
                 error_type: ErrorType,
                 severity: ErrorSeverity,
                 user_message: str,
                 technical_message: str,
                 suggestions: List[str],
                 retry_possible: bool = False,
                 contact_support: bool = False):
        self.error_type = error_type
        self.severity = severity
        self.user_message = user_message
        self.technical_message = technical_message
        self.suggestions = suggestions
        self.retry_possible = retry_possible
        self.contact_support = contact_support
        self.timestamp = datetime.now()


class ProgressTracker:
    """Enhanced progress tracking with error handling"""
    
    def __init__(self, total_steps: int = 100):
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = time.time()
        self.step_times = []
        self.errors = []
        
    def update(self, step: int, message: str, error: Optional[Exception] = None):
        """Update progress with optional error tracking"""
        self.current_step = step
        current_time = time.time()
        self.step_times.append(current_time)
        
        if error:
            self.errors.append({
                'step': step,
                'message': message,
                'error': str(error),
                'timestamp': current_time
            })
            logger.error(f"Progress error at step {step}: {message} - {error}")
        else:
            logger.debug(f"Progress update: Step {step}/{self.total_steps} - {message}")
    
    def get_estimated_remaining_time(self) -> float:
        """Estimate remaining time based on current progress"""
        if len(self.step_times) < 2:
            return 0.0
        
        elapsed_time = time.time() - self.start_time
        progress_ratio = self.current_step / self.total_steps
        
        if progress_ratio > 0:
            estimated_total_time = elapsed_time / progress_ratio
            return max(0, estimated_total_time - elapsed_time)
        
        return 0.0
    
    def has_errors(self) -> bool:
        """Check if any errors occurred during progress"""
        return len(self.errors) > 0


class ErrorHandler:
    """Comprehensive error handler with retry mechanisms and user feedback"""
    
    # Error message templates
    ERROR_MESSAGES = {
        ErrorType.STORAGE_CONNECTION: {
            'user': "📊 历史记录存储服务暂时不可用",
            'suggestions': [
                "请检查网络连接",
                "稍后重试操作",
                "如果问题持续，请联系技术支持"
            ]
        },
        ErrorType.STORAGE_OPERATION: {
            'user': "💾 存储操作失败",
            'suggestions': [
                "请重试操作",
                "检查是否有足够的存储空间",
                "如果问题持续，请联系管理员"
            ]
        },
        ErrorType.DATA_VALIDATION: {
            'user': "📋 数据验证失败",
            'suggestions': [
                "请检查输入数据的格式",
                "确保所有必填字段都已填写",
                "参考帮助文档了解正确格式"
            ]
        },
        ErrorType.NETWORK_ERROR: {
            'user': "🌐 网络连接出现问题",
            'suggestions': [
                "请检查网络连接",
                "稍后重试操作",
                "如果使用VPN，请尝试断开后重试"
            ]
        },
        ErrorType.PERMISSION_ERROR: {
            'user': "🔒 权限不足",
            'suggestions': [
                "请联系管理员获取必要权限",
                "确认您有执行此操作的权限",
                "尝试重新登录"
            ]
        },
        ErrorType.RESOURCE_EXHAUSTED: {
            'user': "⚡ 系统资源不足",
            'suggestions': [
                "请稍后重试",
                "减少并发操作数量",
                "联系管理员检查系统资源"
            ]
        },
        ErrorType.TIMEOUT_ERROR: {
            'user': "⏰ 操作超时",
            'suggestions': [
                "请重试操作",
                "检查网络连接稳定性",
                "如果数据量较大，请耐心等待"
            ]
        },
        ErrorType.UNKNOWN_ERROR: {
            'user': "❓ 发生未知错误",
            'suggestions': [
                "请重试操作",
                "如果问题持续，请联系技术支持",
                "提供错误发生时的详细信息"
            ]
        }
    }
    
    @staticmethod
    def classify_error(exception: Exception) -> ErrorType:
        """Classify exception into error types"""
        error_str = str(exception).lower()
        exception_type = type(exception).__name__.lower()
        
        # MongoDB/Database errors
        if any(keyword in error_str for keyword in ['mongodb', 'pymongo', 'connection', 'database']):
            if 'timeout' in error_str:
                return ErrorType.TIMEOUT_ERROR
            elif 'connection' in error_str:
                return ErrorType.STORAGE_CONNECTION
            else:
                return ErrorType.STORAGE_OPERATION
        
        # Network errors
        if any(keyword in error_str for keyword in ['network', 'connection', 'timeout', 'unreachable']):
            return ErrorType.NETWORK_ERROR
        
        # Permission errors
        if any(keyword in error_str for keyword in ['permission', 'access', 'forbidden', 'unauthorized']):
            return ErrorType.PERMISSION_ERROR
        
        # Resource errors
        if any(keyword in error_str for keyword in ['memory', 'disk', 'space', 'resource']):
            return ErrorType.RESOURCE_EXHAUSTED
        
        # Validation errors
        if any(keyword in error_str for keyword in ['validation', 'invalid', 'format', 'schema']):
            return ErrorType.DATA_VALIDATION
        
        # Timeout errors
        if 'timeout' in error_str or 'timeout' in exception_type:
            return ErrorType.TIMEOUT_ERROR
        
        return ErrorType.UNKNOWN_ERROR
    
    @staticmethod
    def determine_severity(error_type: ErrorType, exception: Exception) -> ErrorSeverity:
        """Determine error severity based on type and context"""
        critical_keywords = ['critical', 'fatal', 'corruption', 'security']
        high_keywords = ['connection', 'database', 'storage']
        
        error_str = str(exception).lower()
        
        if any(keyword in error_str for keyword in critical_keywords):
            return ErrorSeverity.CRITICAL
        elif error_type in [ErrorType.STORAGE_CONNECTION, ErrorType.PERMISSION_ERROR]:
            return ErrorSeverity.HIGH
        elif error_type in [ErrorType.STORAGE_OPERATION, ErrorType.NETWORK_ERROR]:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    @classmethod
    def create_user_friendly_error(cls, exception: Exception, context: str = "") -> UserFriendlyError:
        """Create a user-friendly error from an exception"""
        error_type = cls.classify_error(exception)
        severity = cls.determine_severity(error_type, exception)
        
        error_template = cls.ERROR_MESSAGES.get(error_type, cls.ERROR_MESSAGES[ErrorType.UNKNOWN_ERROR])
        
        # Enhanced user message with context
        user_message = error_template['user']
        if context:
            user_message = f"{user_message} ({context})"
        
        # Technical message for logging
        technical_message = f"{type(exception).__name__}: {str(exception)}"
        
        # Determine if retry is possible
        retry_possible = error_type in [
            ErrorType.STORAGE_CONNECTION,
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.RESOURCE_EXHAUSTED
        ]
        
        # Determine if support contact is needed
        contact_support = severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
        
        return UserFriendlyError(
            error_type=error_type,
            severity=severity,
            user_message=user_message,
            technical_message=technical_message,
            suggestions=error_template['suggestions'],
            retry_possible=retry_possible,
            contact_support=contact_support
        )
    
    @staticmethod
    def log_error(error: UserFriendlyError, context: Dict[str, Any] = None):
        """Log error with appropriate level and context"""
        log_context = {
            'error_type': error.error_type.value,
            'severity': error.severity.value,
            'user_message': error.user_message,
            'technical_message': error.technical_message,
            'timestamp': error.timestamp.isoformat()
        }
        
        if context:
            log_context.update(context)
        
        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical error: {error.technical_message}", extra=log_context)
        elif error.severity == ErrorSeverity.HIGH:
            logger.error(f"High severity error: {error.technical_message}", extra=log_context)
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Medium severity error: {error.technical_message}", extra=log_context)
        else:
            logger.info(f"Low severity error: {error.technical_message}", extra=log_context)


def with_retry(max_attempts: int = 3, 
               delay: float = 1.0, 
               backoff_factor: float = 2.0,
               retry_on: Tuple[Exception, ...] = (Exception,),
               show_user_feedback: bool = False,
               operation_name: str = None):
    """
    Enhanced decorator for adding retry logic to functions with user feedback
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff_factor: Multiplier for delay after each attempt
        retry_on: Tuple of exception types to retry on
        show_user_feedback: Whether to show retry attempts to user
        operation_name: Name of operation for user display
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            operation_display_name = operation_name or func.__name__
            
            for attempt in range(max_attempts):
                try:
                    # Show retry attempt to user if requested
                    if show_user_feedback and attempt > 0:
                        with st.spinner(f"🔄 重试 {operation_display_name} (第 {attempt + 1} 次尝试)"):
                            time.sleep(0.5)  # Brief pause to show the message
                    
                    result = func(*args, **kwargs)
                    
                    # Show success message if this was a retry
                    if show_user_feedback and attempt > 0:
                        st.success(f"✅ {operation_display_name} 重试成功")
                        time.sleep(1)
                    
                    return result
                    
                except retry_on as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # Last attempt failed, don't retry
                        break
                    
                    # Enhanced logging with context
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed for {operation_display_name}: {e}")
                    logger.warning(f"Retrying in {current_delay} seconds...")
                    
                    # Show user feedback for retry
                    if show_user_feedback:
                        user_error = ErrorHandler.create_user_friendly_error(e, operation_display_name)
                        
                        if user_error.retry_possible:
                            st.warning(f"⚠️ {operation_display_name} 暂时失败，{current_delay:.0f} 秒后自动重试...")
                            
                            # Show countdown if delay is significant
                            if current_delay >= 3:
                                countdown_placeholder = st.empty()
                                for remaining in range(int(current_delay), 0, -1):
                                    countdown_placeholder.text(f"⏳ {remaining} 秒后重试...")
                                    time.sleep(1)
                                countdown_placeholder.empty()
                            else:
                                time.sleep(current_delay)
                        else:
                            # Non-retryable error according to classification
                            logger.error(f"Non-retryable error detected for {operation_display_name}: {e}")
                            raise
                    else:
                        time.sleep(current_delay)
                    
                    current_delay *= backoff_factor
                    
                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error in {operation_display_name}: {e}")
                    
                    if show_user_feedback:
                        user_error = ErrorHandler.create_user_friendly_error(e, operation_display_name)
                        show_error_to_user(user_error)
                    
                    raise
            
            # All attempts failed
            logger.error(f"All {max_attempts} attempts failed for {operation_display_name}")
            
            if show_user_feedback:
                user_error = ErrorHandler.create_user_friendly_error(last_exception, operation_display_name)
                st.error(f"❌ {operation_display_name} 在 {max_attempts} 次尝试后仍然失败")
                show_error_to_user(user_error)
            
            raise last_exception
        
        return wrapper
    return decorator


def with_error_handling(context: str = "", show_user_error: bool = True):
    """
    Decorator for comprehensive error handling with user feedback
    
    Args:
        context: Context description for error messages
        show_user_error: Whether to show error to user via Streamlit
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Create user-friendly error
                user_error = ErrorHandler.create_user_friendly_error(e, context)
                
                # Log the error
                ErrorHandler.log_error(user_error, {
                    'function': func.__name__,
                    'args': str(args)[:200],  # Truncate long args
                    'kwargs': str(kwargs)[:200]
                })
                
                # Show user error if requested
                if show_user_error:
                    show_error_to_user(user_error)
                
                # Re-raise the exception for caller to handle
                raise
        
        return wrapper
    return decorator


def show_error_to_user(error: UserFriendlyError):
    """Display enhanced user-friendly error in Streamlit interface with better UX"""
    
    # Choose appropriate Streamlit alert based on severity with enhanced styling
    if error.severity == ErrorSeverity.CRITICAL:
        st.error(f"🚨 {error.user_message}")
        # Add critical error styling
        st.markdown("""
        <div style="background-color: #ffebee; border-left: 4px solid #f44336; padding: 10px; margin: 10px 0;">
            <strong>⚠️ 严重错误</strong><br>
            系统遇到了严重问题，请立即联系技术支持团队。
        </div>
        """, unsafe_allow_html=True)
    elif error.severity == ErrorSeverity.HIGH:
        st.error(f"❌ {error.user_message}")
    elif error.severity == ErrorSeverity.MEDIUM:
        st.warning(f"⚠️ {error.user_message}")
    else:
        st.info(f"ℹ️ {error.user_message}")
    
    # Show suggestions in an enhanced expander
    if error.suggestions:
        with st.expander("💡 解决建议", expanded=error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]):
            st.markdown("**请尝试以下解决方案：**")
            for i, suggestion in enumerate(error.suggestions, 1):
                st.markdown(f"{i}. {suggestion}")
    
    # Show retry option with enhanced UI
    if error.retry_possible:
        st.info("🔄 此错误可能是临时的，系统将自动重试或您可以手动重新操作")
        
        # Add retry button for user-initiated retry
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🔄 立即重试", key=f"retry_{error.timestamp.timestamp()}"):
                st.rerun()
        with col2:
            if st.button("📋 复制错误信息", key=f"copy_{error.timestamp.timestamp()}"):
                st.code(error.technical_message)
                st.success("错误信息已显示，您可以复制给技术支持")
    
    # Show support contact with enhanced information
    if error.contact_support:
        st.error("📞 如果问题持续存在，请联系技术支持团队")
        
        # Add support contact information
        with st.expander("📞 技术支持信息", expanded=True):
            st.markdown("""
            **联系技术支持时，请提供以下信息：**
            - 错误发生的时间和操作
            - 您的用户ID或会话信息
            - 下方的技术详情
            """)
    
    # Show technical details in debug mode with better formatting
    if st.session_state.get('debug_mode', False):
        with st.expander("🔧 技术详情 (调试模式)", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.text(f"错误类型: {error.error_type.value}")
                st.text(f"严重程度: {error.severity.value}")
                st.text(f"发生时间: {error.timestamp}")
            with col2:
                st.text(f"可重试: {'是' if error.retry_possible else '否'}")
                st.text(f"需要支持: {'是' if error.contact_support else '否'}")
            
            st.markdown("**详细错误信息：**")
            st.code(error.technical_message)
    
    # Add error reporting functionality
    if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
        with st.expander("📊 错误报告", expanded=False):
            if st.button("📤 发送错误报告", key=f"report_{error.timestamp.timestamp()}"):
                # Log error report
                logger.info(f"User reported error: {error.technical_message}", extra={
                    'error_type': error.error_type.value,
                    'severity': error.severity.value,
                    'user_reported': True,
                    'timestamp': error.timestamp.isoformat()
                })
                st.success("✅ 错误报告已发送给技术团队")


def show_loading_with_progress(message: str, 
                             estimated_duration: float = None,
                             progress_callback: Callable = None,
                             show_spinner: bool = True,
                             show_progress_bar: bool = True) -> Callable:
    """
    Enhanced context manager for showing loading state with progress and better user feedback
    
    Args:
        message: Loading message to display
        estimated_duration: Estimated duration in seconds
        progress_callback: Optional callback for progress updates
        show_spinner: Whether to show spinner animation
        show_progress_bar: Whether to show progress bar
    """
    class LoadingContext:
        def __init__(self):
            self.progress_bar = None
            self.status_text = None
            self.spinner_placeholder = None
            self.start_time = None
            self.last_progress = 0.0
            self.error_occurred = False
            self.completion_message = None
            
        def __enter__(self):
            self.start_time = time.time()
            
            # Create UI elements
            if show_progress_bar:
                self.progress_bar = st.progress(0)
            
            if show_spinner:
                self.spinner_placeholder = st.empty()
                with self.spinner_placeholder:
                    with st.spinner(f"⏳ {message}"):
                        pass
            
            self.status_text = st.empty()
            self.status_text.text(f"⏳ {message}")
            
            logger.debug(f"Loading context started: {message}")
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                # Clear spinner first
                if self.spinner_placeholder:
                    self.spinner_placeholder.empty()
                
                # Handle completion or error
                if exc_type is None and not self.error_occurred:
                    # Success case
                    if self.progress_bar:
                        self.progress_bar.progress(1.0)
                    
                    completion_msg = self.completion_message or f"✅ {message} - 完成"
                    if self.status_text:
                        self.status_text.success(completion_msg)
                    
                    logger.info(f"Loading completed successfully: {message}")
                    
                else:
                    # Error case
                    if self.progress_bar:
                        self.progress_bar.empty()
                    
                    error_msg = f"❌ {message} - 失败"
                    if exc_val:
                        # Create user-friendly error from exception
                        user_error = ErrorHandler.create_user_friendly_error(exc_val, message)
                        error_msg = f"❌ {user_error.user_message}"
                    
                    if self.status_text:
                        self.status_text.error(error_msg)
                    
                    logger.error(f"Loading failed: {message} - {exc_val if exc_val else 'Unknown error'}")
                
                # Brief display time for user to see result
                time.sleep(1.5)
                
                # Clean up UI elements
                if self.progress_bar:
                    self.progress_bar.empty()
                if self.status_text:
                    self.status_text.empty()
                    
            except Exception as cleanup_error:
                logger.error(f"Error during loading context cleanup: {cleanup_error}")
        
        def update_progress(self, progress: float, status: str = None, show_time_estimate: bool = True):
            """Enhanced progress update with better time estimation and error handling"""
            try:
                # Validate progress value
                progress = min(1.0, max(0.0, progress))
                self.last_progress = progress
                
                # Update progress bar
                if self.progress_bar:
                    self.progress_bar.progress(progress)
                
                # Update status text with enhanced information
                if status and self.status_text:
                    elapsed = time.time() - self.start_time
                    status_msg = f"⏳ {status}"
                    
                    if show_time_estimate and estimated_duration and progress > 0.1:
                        # More accurate time estimation
                        if progress >= 0.95:
                            status_msg += " (即将完成)"
                        else:
                            # Use both elapsed time and estimated duration for better accuracy
                            time_based_estimate = elapsed / progress if progress > 0 else estimated_duration
                            duration_based_estimate = estimated_duration
                            
                            # Weighted average of both estimates
                            if elapsed > 10:  # After 10 seconds, trust elapsed time more
                                estimated_total = 0.7 * time_based_estimate + 0.3 * duration_based_estimate
                            else:
                                estimated_total = 0.3 * time_based_estimate + 0.7 * duration_based_estimate
                            
                            remaining = max(0, estimated_total - elapsed)
                            
                            if remaining > 60:
                                remaining_str = f"约 {remaining/60:.1f} 分钟"
                            elif remaining > 0:
                                remaining_str = f"约 {remaining:.0f} 秒"
                            else:
                                remaining_str = "即将完成"
                            
                            status_msg += f" (剩余 {remaining_str})"
                    
                    # Add progress percentage
                    status_msg += f" - {progress*100:.1f}%"
                    
                    self.status_text.text(status_msg)
                
                # Call external progress callback if provided
                if progress_callback:
                    try:
                        progress_callback(progress, status)
                    except Exception as callback_error:
                        logger.warning(f"Progress callback error: {callback_error}")
                
                logger.debug(f"Progress updated: {progress*100:.1f}% - {status}")
                
            except Exception as e:
                logger.error(f"Error updating progress: {e}")
                self.error_occurred = True
        
        def set_completion_message(self, message: str):
            """Set custom completion message"""
            self.completion_message = message
        
        def mark_error(self, error_message: str):
            """Mark the operation as failed with custom error message"""
            self.error_occurred = True
            if self.status_text:
                self.status_text.error(f"❌ {error_message}")
    
    return LoadingContext()


def handle_storage_operation(operation_name: str, 
                           operation_func: Callable,
                           *args, 
                           show_progress: bool = True,
                           retry_attempts: int = 3,
                           show_user_feedback: bool = True,
                           **kwargs) -> Any:
    """
    Enhanced storage operation handler with comprehensive error handling and user feedback
    
    Args:
        operation_name: Name of the operation for user display
        operation_func: Function to execute
        show_progress: Whether to show progress indicator
        retry_attempts: Number of retry attempts
        show_user_feedback: Whether to show user feedback during retries
        *args, **kwargs: Arguments to pass to operation_func
    
    Returns:
        Result of operation_func or None if failed
    """
    
    @with_retry(
        max_attempts=retry_attempts, 
        delay=1.0, 
        backoff_factor=1.5,
        show_user_feedback=show_user_feedback,
        operation_name=operation_name
    )
    @with_error_handling(context=operation_name, show_user_error=False)
    def execute_operation():
        return operation_func(*args, **kwargs)
    
    if show_progress:
        with show_loading_with_progress(f"执行{operation_name}", estimated_duration=5.0) as loading:
            try:
                loading.update_progress(0.1, f"开始{operation_name}")
                result = execute_operation()
                loading.update_progress(1.0, f"{operation_name}完成")
                loading.set_completion_message(f"✅ {operation_name}成功完成")
                return result
            except Exception as e:
                # Create and show user-friendly error
                user_error = ErrorHandler.create_user_friendly_error(e, operation_name)
                loading.mark_error(user_error.user_message)
                
                # Show detailed error information
                if show_user_feedback:
                    show_error_to_user(user_error)
                
                return None
    else:
        try:
            return execute_operation()
        except Exception as e:
            # Create and show user-friendly error
            user_error = ErrorHandler.create_user_friendly_error(e, operation_name)
            if show_user_feedback:
                show_error_to_user(user_error)
            return None


def validate_and_sanitize_input(data: Dict[str, Any], 
                              validation_rules: Dict[str, Callable]) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    Enhanced input validation with better error messages and logging
    
    Args:
        data: Input data to validate
        validation_rules: Dictionary of field_name -> validation_function
    
    Returns:
        Tuple of (is_valid, sanitized_data, error_messages)
    """
    is_valid = True
    sanitized_data = {}
    error_messages = []
    
    logger.debug(f"Validating input data with {len(validation_rules)} rules")
    
    for field_name, validation_func in validation_rules.items():
        try:
            if field_name in data:
                original_value = data[field_name]
                sanitized_value = validation_func(original_value)
                sanitized_data[field_name] = sanitized_value
                
                # Log validation success
                if original_value != sanitized_value:
                    logger.debug(f"Field {field_name} sanitized: '{original_value}' -> '{sanitized_value}'")
                else:
                    logger.debug(f"Field {field_name} validated successfully")
                    
            else:
                # Field is missing
                error_messages.append(f"缺少必填字段: {field_name}")
                is_valid = False
                logger.warning(f"Missing required field: {field_name}")
                
        except ValueError as e:
            error_messages.append(f"字段 {field_name} 验证失败: {str(e)}")
            is_valid = False
            logger.warning(f"Validation failed for field {field_name}: {e}")
            
        except Exception as e:
            error_messages.append(f"字段 {field_name} 处理错误: {str(e)}")
            is_valid = False
            logger.error(f"Unexpected error validating field {field_name}: {e}")
    
    logger.info(f"Input validation completed: {'✅ Valid' if is_valid else '❌ Invalid'} "
                f"({len(sanitized_data)} fields processed, {len(error_messages)} errors)")
    
    return is_valid, sanitized_data, error_messages


# Enhanced validation functions for common data types
def validate_stock_symbol(value: str) -> str:
    """Validate and sanitize stock symbol with enhanced checks"""
    if not value or not isinstance(value, str):
        raise ValueError("股票代码不能为空")
    
    cleaned = value.strip().upper()
    if len(cleaned) < 1 or len(cleaned) > 20:
        raise ValueError("股票代码长度必须在1-20个字符之间")
    
    # Additional format validation
    import re
    if not re.match(r'^[A-Z0-9.]+$', cleaned):
        raise ValueError("股票代码只能包含字母、数字和点号")
    
    return cleaned


def validate_date_string(value: str) -> str:
    """Validate date string format with enhanced error messages"""
    if not value or not isinstance(value, str):
        raise ValueError("日期不能为空")
    
    try:
        parsed_date = datetime.strptime(value, '%Y-%m-%d')
        
        # Check if date is not too far in the future
        if parsed_date > datetime.now():
            raise ValueError("日期不能是未来时间")
            
        return value
    except ValueError as e:
        if "time data" in str(e):
            raise ValueError("日期格式必须为 YYYY-MM-DD (例如: 2024-01-15)")
        else:
            raise


def validate_positive_integer(value: Any) -> int:
    """Validate positive integer with enhanced error messages"""
    try:
        int_value = int(value)
        if int_value <= 0:
            raise ValueError("必须是正整数 (大于0)")
        if int_value > 1000000:
            raise ValueError("数值过大，请输入合理范围内的正整数")
        return int_value
    except (ValueError, TypeError) as e:
        if "invalid literal" in str(e):
            raise ValueError(f"'{value}' 不是有效的整数")
        else:
            raise ValueError("必须是有效的正整数")


def validate_non_empty_string(value: Any) -> str:
    """Validate non-empty string with enhanced checks"""
    if not value or not isinstance(value, str):
        raise ValueError("不能为空字符串")
    
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("不能为空字符串或只包含空格")
    
    if len(cleaned) > 1000:
        raise ValueError("字符串长度不能超过1000个字符")
    
    return cleaned


def create_operation_timeout_handler(timeout_seconds: int = 30):
    """
    Create a thread-safe timeout handler for long-running operations
    
    Args:
        timeout_seconds: Maximum time to wait before timing out
    
    Returns:
        Context manager for timeout handling
    """
    import threading
    import time
    
    class ThreadSafeTimeoutHandler:
        def __init__(self, timeout):
            self.timeout = timeout
            self.timer = None
            self.timed_out = False
            
        def __enter__(self):
            def timeout_callback():
                self.timed_out = True
            
            # Use threading.Timer instead of signal for thread safety
            self.timer = threading.Timer(self.timeout, timeout_callback)
            self.timer.start()
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.timer:
                self.timer.cancel()
            
            # Check if we timed out
            if self.timed_out:
                raise TimeoutError(f"操作超时 ({self.timeout} 秒)")
        
        def check_timeout(self):
            """Check if timeout occurred - can be called periodically during long operations"""
            if self.timed_out:
                raise TimeoutError(f"操作超时 ({self.timeout} 秒)")
    
    return ThreadSafeTimeoutHandler(timeout_seconds)


def log_operation_metrics(operation_name: str, 
                         duration: float, 
                         success: bool, 
                         error: Optional[Exception] = None,
                         additional_metrics: Dict[str, Any] = None):
    """
    Log operation metrics for monitoring and debugging
    
    Args:
        operation_name: Name of the operation
        duration: Duration in seconds
        success: Whether the operation succeeded
        error: Exception if operation failed
        additional_metrics: Additional metrics to log
    """
    metrics = {
        'operation': operation_name,
        'duration_seconds': duration,
        'success': success,
        'timestamp': datetime.now().isoformat()
    }
    
    if additional_metrics:
        metrics.update(additional_metrics)
    
    if error:
        metrics['error_type'] = type(error).__name__
        metrics['error_message'] = str(error)
    
    if success:
        logger.info(f"Operation completed: {operation_name} ({duration:.2f}s)", extra=metrics)
    else:
        logger.error(f"Operation failed: {operation_name} ({duration:.2f}s)", extra=metrics)