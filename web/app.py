#!/usr/bin/env python3
"""
TradingAgents-CN Streamlit Web界面
基于Streamlit的股票分析Web应用程序
"""

import streamlit as st
import os
import sys
from pathlib import Path
import datetime
import time
from dotenv import load_dotenv

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量 - Docker环境中不覆盖环境变量
is_docker = os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
load_dotenv(project_root / ".env", override=not is_docker)

# 导入自定义组件
from components.sidebar import render_sidebar
from components.header import render_header
from components.analysis_form import render_analysis_form
from components.results_display import render_results
from utils.api_checker import check_api_keys
from utils.analysis_runner import run_stock_analysis, validate_analysis_params, format_analysis_results
from utils.progress_tracker import SmartStreamlitProgressDisplay, create_smart_progress_callback
from utils.async_progress_tracker import AsyncProgressTracker
from components.async_progress_display import display_unified_progress
from utils.smart_session_manager import get_persistent_analysis_id, set_persistent_analysis_id

# 设置页面配置
st.set_page_config(
    page_title="TradingAgents-CN 股票分析平台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# 基本CSS样式优化
st.markdown("""
<style>
    /* 隐藏部分默认元素（保留顶部header与toolbar以便侧边栏切换） */
    .stDeployButton,
    [data-testid="stDecoration"], [data-testid="stStatusWidget"],
    #MainMenu, footer, .viewerBadge_container__1QSob {
        display: none !important;
    }
    
    /* 适度减少间距 */
    .main .block-container {
        padding-top: 1rem !important;
        max-width: none !important;
    }
    
    /* 稍微减少元素间距 */
    .element-container { margin-bottom: 0.8rem !important; }
    
    /* 表单样式 */
    .stForm { 
        border: 1px solid #e0e0e0 !important; 
        border-radius: 8px !important; 
        padding: 1.2rem !important; 
        margin: 0.8rem 0 !important; 
        background-color: #fafafa !important;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """初始化会话状态"""
    
    # Docker环境下重置数据库管理器（只执行一次）
    if 'db_manager_reset' not in st.session_state:
        if os.getenv("DOCKER_CONTAINER", "false").lower() == "true":
            try:
                from tradingagents.config.database_manager import reset_database_manager
                reset_database_manager()
                logger.info("🐳 Docker环境检测到，已重置数据库管理器")
            except ImportError:
                logger.warning("⚠️ 无法导入数据库管理器重置函数")
        st.session_state.db_manager_reset = True
    
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False
    if 'last_analysis_time' not in st.session_state:
        st.session_state.last_analysis_time = None
    if 'current_analysis_id' not in st.session_state:
        st.session_state.current_analysis_id = None
    if 'form_config' not in st.session_state:
        st.session_state.form_config = None

def main():
    """主应用程序"""

    # 初始化会话状态
    initialize_session_state()

    # 渲染页面头部
    render_header()

    # 页面导航
    st.sidebar.title("🤖 TradingAgents-CN")
    st.sidebar.markdown("---")

    # 添加功能切换标题
    st.sidebar.markdown("**🎯 功能导航**")

    page = st.sidebar.selectbox(
        "切换功能模块",
        ["📊 股票分析", "⚙️ 配置管理", "💾 缓存管理", "💰 Token统计", "📈 历史记录", "🔧 系统状态"],
        label_visibility="collapsed"
    )

    # 在功能选择和AI模型配置之间添加分隔线
    st.sidebar.markdown("---")

    # 根据选择的页面渲染不同内容
    if page == "⚙️ 配置管理":
        try:
            from modules.config_management import render_config_management
            render_config_management()
        except ImportError as e:
            st.error(f"配置管理模块加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "💾 缓存管理":
        try:
            from modules.cache_management import main as cache_main
            cache_main()
        except ImportError as e:
            st.error(f"缓存管理页面加载失败: {e}")
        return
    elif page == "💰 Token统计":
        try:
            from modules.token_statistics import render_token_statistics
            render_token_statistics()
        except ImportError as e:
            st.error(f"Token统计页面加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "📈 历史记录":
        try:
            from modules.analysis_history import render_analysis_history
            render_analysis_history()
        except ImportError as e:
            st.error(f"历史记录模块加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "🔧 系统状态":
        st.header("🔧 系统状态")
        st.info("系统状态功能开发中...")
        return

    # 默认显示股票分析页面
    # 检查API密钥
    api_status = check_api_keys()
    
    if not api_status['all_configured']:
        st.error("⚠️ API密钥配置不完整，请先配置必要的API密钥")
        
        with st.expander("📋 API密钥配置指南", expanded=True):
            st.markdown("""
            ### 🔑 必需的API密钥
            
            1. **AI模型API密钥** (至少配置一个)
               - **DeepSeek V3** (DEEPSEEK_API_KEY) - 推荐，性价比高
               - **阿里百炼** (DASHSCOPE_API_KEY) - 中文优化
               - **OpenAI** (OPENAI_API_KEY) - 功能强大
               - **Google AI** (GOOGLE_API_KEY) - 免费额度大
            
            2. **金融数据API密钥** (FINNHUB_API_KEY)  
               - 获取地址: https://finnhub.io/
            
            ### ⚙️ 配置方法
            
            1. 复制项目根目录的 `.env.example` 为 `.env`
            2. 编辑 `.env` 文件，填入您的真实API密钥
            3. 重启Web应用
            """)
        
        # 显示当前API密钥状态
        st.subheader("🔍 当前API密钥状态")
        for key, status in api_status['details'].items():
            if status['configured']:
                st.success(f"✅ {key}: {status['display']}")
            else:
                st.error(f"❌ {key}: 未配置")
        
        return
    
    # 渲染侧边栏
    config = render_sidebar()
    
    # 添加使用指南显示切换
    show_guide = st.sidebar.checkbox("📖 显示使用指南", value=True, help="显示/隐藏右侧使用指南")

    # 添加状态清理按钮
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 清理分析状态", help="清理僵尸分析状态，解决页面持续刷新问题"):
        # 清理session state
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None
        st.session_state.analysis_results = None

        # 清理所有自动刷新状态
        keys_to_remove = []
        for key in st.session_state.keys():
            if 'auto_refresh' in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del st.session_state[key]

        # 清理死亡线程
        from utils.thread_tracker import cleanup_dead_analysis_threads
        cleanup_dead_analysis_threads()

        st.sidebar.success("✅ 分析状态已清理")
        st.rerun()

    # 主内容区域 - 根据是否显示指南调整布局
    if show_guide:
        col1, col2 = st.columns([3, 1])  # 3:1比例，主要内容占更多空间
    else:
        col1 = st.container()
        col2 = None
    
    with col1:
        # 1. 分析配置区域
        st.header("⚙️ 分析配置")

        # 渲染分析表单
        try:
            form_data = render_analysis_form()

            # 验证表单数据格式
            if not isinstance(form_data, dict):
                st.error(f"⚠️ 表单数据格式异常: {type(form_data)}")
                form_data = {'submitted': False}

        except Exception as e:
            st.error(f"❌ 表单渲染失败: {e}")
            form_data = {'submitted': False}

        # 检查是否提交了表单
        if form_data.get('submitted', False) and not st.session_state.get('analysis_running', False):
            # 只有在没有分析运行时才处理新的提交
            # 验证分析参数
            is_valid, validation_errors = validate_analysis_params(
                stock_symbol=form_data['stock_symbol'],
                analysis_date=form_data['analysis_date'],
                analysts=form_data['analysts'],
                research_depth=form_data['research_depth'],
                market_type=form_data.get('market_type', '美股')
            )

            if not is_valid:
                # 显示验证错误
                for error in validation_errors:
                    st.error(error)
            else:
                # 执行分析
                st.session_state.analysis_running = True

                # 清空旧的分析结果
                st.session_state.analysis_results = None
                logger.info("🧹 [新分析] 清空旧的分析结果")

                # 生成分析ID
                import uuid
                analysis_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # 保存分析ID和表单配置到session state和cookie
                form_config = st.session_state.get('form_config', {})
                set_persistent_analysis_id(
                    analysis_id=analysis_id,
                    status="running",
                    stock_symbol=form_data['stock_symbol'],
                    market_type=form_data.get('market_type', '美股'),
                    form_config=form_config
                )

                # 创建异步进度跟踪器
                async_tracker = AsyncProgressTracker(
                    analysis_id=analysis_id,
                    analysts=form_data['analysts'],
                    research_depth=form_data['research_depth'],
                    llm_provider=config['llm_provider']
                )

                # 创建进度回调函数
                def progress_callback(message: str, step: int = None, total_steps: int = None):
                    async_tracker.update_progress(message, step)

                # 显示启动成功消息和加载动效
                st.success(f"🚀 分析已启动！分析ID: {analysis_id}")

                # 添加加载动效
                with st.spinner("🔄 正在初始化分析..."):
                    time.sleep(1.5)  # 让用户看到反馈

                st.info(f"📊 正在分析: {form_data.get('market_type', '美股')} {form_data['stock_symbol']}")
                st.info("⏱️ 页面将在6秒后自动刷新...")

                # 设置分析状态
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = analysis_id
                st.session_state.last_stock_symbol = form_data['stock_symbol']
                st.session_state.last_market_type = form_data.get('market_type', '美股')

                # 在后台线程中运行分析
                import threading

                def run_analysis_in_background():
                    try:
                        results = run_stock_analysis(
                            stock_symbol=form_data['stock_symbol'],
                            analysis_date=form_data['analysis_date'],
                            analysts=form_data['analysts'],
                            research_depth=form_data['research_depth'],
                            llm_provider=config['llm_provider'],
                            market_type=form_data.get('market_type', '美股'),
                            llm_model=config['llm_model'],
                            progress_callback=progress_callback,
                            session_id=analysis_id
                        )

                        # 标记分析完成并保存结果
                        async_tracker.mark_completed("✅ 分析成功完成！", results=results)
                        logger.info(f"✅ [分析完成] 股票分析成功完成: {analysis_id}")

                    except Exception as e:
                        # 标记分析失败
                        async_tracker.mark_failed(str(e))
                        logger.error(f"❌ [分析失败] {analysis_id}: {e}")

                    finally:
                        # 分析结束后注销线程
                        from utils.thread_tracker import unregister_analysis_thread
                        unregister_analysis_thread(analysis_id)
                        logger.info(f"🧵 [线程清理] 分析线程已注销: {analysis_id}")

                # 启动后台分析线程
                analysis_thread = threading.Thread(target=run_analysis_in_background)
                analysis_thread.daemon = True
                analysis_thread.start()

                # 注册线程到跟踪器
                from utils.thread_tracker import register_analysis_thread
                register_analysis_thread(analysis_id, analysis_thread)

                logger.info(f"🧵 [后台分析] 分析线程已启动: {analysis_id}")

                # 等待2秒让用户看到启动信息，然后刷新页面
                time.sleep(2)
                st.rerun()

        # 2. 股票分析区域（只有在有分析ID时才显示）
        current_analysis_id = st.session_state.get('current_analysis_id')
        if current_analysis_id:
            st.markdown("---")
            st.header("📊 股票分析")

            # 使用线程检测来获取真实状态
            from utils.thread_tracker import check_analysis_status
            actual_status = check_analysis_status(current_analysis_id)
            is_running = (actual_status == 'running')

            # 同步session state状态
            if st.session_state.get('analysis_running', False) != is_running:
                st.session_state.analysis_running = is_running
                logger.info(f"🔄 [状态同步] 更新分析状态: {is_running} (基于线程检测: {actual_status})")

            # 获取进度数据用于显示
            from utils.async_progress_tracker import get_progress_by_id
            progress_data = get_progress_by_id(current_analysis_id)

            # 显示分析信息
            if is_running:
                st.info(f"🔄 正在分析: {current_analysis_id}")
            else:
                if actual_status == 'completed':
                    st.success(f"✅ 分析完成: {current_analysis_id}")
                elif actual_status == 'failed':
                    st.error(f"❌ 分析失败: {current_analysis_id}")
                else:
                    st.warning(f"⚠️ 分析状态未知: {current_analysis_id}")

            # 显示进度
            progress_col1, progress_col2 = st.columns([4, 1])
            with progress_col1:
                st.markdown("### 📊 分析进度")

            is_completed = display_unified_progress(current_analysis_id, show_refresh_controls=is_running)

            # 如果分析正在进行，显示提示信息
            if is_running:
                st.info("⏱️ 分析正在进行中，可以使用下方的自动刷新功能查看进度更新...")

            # 如果分析刚完成，尝试恢复结果
            if is_completed and not st.session_state.get('analysis_results') and progress_data:
                if 'raw_results' in progress_data:
                    try:
                        from utils.analysis_runner import format_analysis_results
                        raw_results = progress_data['raw_results']
                        formatted_results = format_analysis_results(raw_results)
                        if formatted_results:
                            st.session_state.analysis_results = formatted_results
                            st.session_state.analysis_running = False
                            logger.info(f"📊 [结果同步] 恢复分析结果: {current_analysis_id}")

                            # 检查是否已经刷新过，避免重复刷新
                            refresh_key = f"results_refreshed_{current_analysis_id}"
                            if not st.session_state.get(refresh_key, False):
                                st.session_state[refresh_key] = True
                                st.success("📊 分析结果已恢复，正在刷新页面...")
                                time.sleep(1)
                                st.rerun()
                    except Exception as e:
                        logger.error(f"❌ [结果恢复] 恢复分析结果失败: {e}")

        # 3. 分析结果显示区域
        if st.session_state.analysis_results:
            st.markdown("---")
            st.header("📊 分析结果")
            render_results(st.session_state.analysis_results)

    # 如果显示使用指南
    if show_guide and col2 is not None:
        with col2:
            st.markdown("### 📖 使用指南")
            
            with st.expander("🚀 快速开始", expanded=True):
                st.markdown("""
                **基本步骤：**
                1. 选择市场类型（美股/A股/港股）
                2. 输入股票代码
                3. 选择分析师团队
                4. 设置研究深度
                5. 点击开始分析
                
                **股票代码示例：**
                - 美股：AAPL, TSLA, MSFT
                - A股：000001, 600519
                - 港股：0700.HK, 9988.HK
                """)
            
            with st.expander("⚙️ 配置说明"):
                st.markdown("""
                **AI模型选择：**
                - DeepSeek V3：性价比高，推荐
                - 阿里百炼：中文优化
                - OpenAI：功能强大
                - Google AI：免费额度大
                """)
            
            st.warning("⚠️ 投资有风险，分析结果仅供参考")
        
        # 显示系统状态
        if st.session_state.last_analysis_time:
            st.info(f"🕒 上次分析时间: {st.session_state.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()