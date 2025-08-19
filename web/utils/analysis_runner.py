"""
股票分析执行工具
"""

import sys
import os
import uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger, get_logger_manager
logger = get_logger('web')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 确保环境变量正确加载 - Docker环境中不覆盖环境变量
is_docker = os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
load_dotenv(project_root / ".env", override=not is_docker)

# 导入统一日志系统
from tradingagents.utils.logging_init import setup_web_logging
logger = setup_web_logging()

# Import error handling utilities
from web.utils.error_handler import (
    with_error_handling, with_retry, ErrorHandler, show_error_to_user,
    show_loading_with_progress, ProgressTracker, validate_and_sanitize_input,
    validate_stock_symbol, validate_date_string, validate_positive_integer, validate_non_empty_string
)

# 添加配置管理器
try:
    from tradingagents.config.config_manager import token_tracker
    TOKEN_TRACKING_ENABLED = True
    logger.info("✅ Token跟踪功能已启用")
except ImportError:
    TOKEN_TRACKING_ENABLED = False
    logger.warning("⚠️ Token跟踪功能未启用")

def _clean_results_for_storage(results):
    """
    清理分析结果中不可序列化的对象，以便存储到MongoDB
    
    Args:
        results: 原始分析结果
        
    Returns:
        清理后的结果字典
    """
    import copy
    from langchain_core.messages import BaseMessage
    
    def clean_object(obj):
        """递归清理对象中的不可序列化内容"""
        if isinstance(obj, BaseMessage):
            # 将LangChain消息对象转换为可序列化的字典
            return {
                'type': obj.__class__.__name__,
                'content': str(obj.content),
                'id': getattr(obj, 'id', None),
                'additional_kwargs': getattr(obj, 'additional_kwargs', {}),
                'response_metadata': getattr(obj, 'response_metadata', {})
            }
        elif isinstance(obj, dict):
            return {key: clean_object(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [clean_object(item) for item in obj]
        elif hasattr(obj, '__dict__') and not isinstance(obj, (str, int, float, bool, type(None))):
            # 对于其他复杂对象，尝试转换为字符串
            try:
                return str(obj)
            except:
                return f"<{obj.__class__.__name__} object>"
        else:
            return obj
    
    try:
        # 深拷贝原始结果以避免修改原对象
        cleaned_results = copy.deepcopy(results)
        
        # 清理结果
        cleaned_results = clean_object(cleaned_results)
        
        logger.debug(f"Successfully cleaned results for storage")
        return cleaned_results
        
    except Exception as e:
        logger.error(f"Error cleaning results for storage: {e}")
        # 如果清理失败，返回一个基本的结果结构
        return {
            'stock_symbol': results.get('stock_symbol', 'unknown'),
            'analysis_date': results.get('analysis_date', 'unknown'),
            'analysts': results.get('analysts', []),
            'success': results.get('success', False),
            'error': f"Results cleaning failed: {str(e)}"
        }

def translate_analyst_labels(text):
    """将分析师的英文标签转换为中文"""
    if not text:
        return text

    # 分析师标签翻译映射
    translations = {
        'Bull Analyst:': '看涨分析师:',
        'Bear Analyst:': '看跌分析师:',
        'Risky Analyst:': '激进风险分析师:',
        'Safe Analyst:': '保守风险分析师:',
        'Neutral Analyst:': '中性风险分析师:',
        'Research Manager:': '研究经理:',
        'Portfolio Manager:': '投资组合经理:',
        'Risk Judge:': '风险管理委员会:',
        'Trader:': '交易员:'
    }

    # 替换所有英文标签
    for english, chinese in translations.items():
        text = text.replace(english, chinese)

    return text


def add_analysis_completion_hook(session_id, hook_function):
    """
    Add a completion hook for analysis
    
    Args:
        session_id: Analysis session ID
        hook_function: Function to call when analysis completes
    """
    # This is a placeholder for future extensibility
    # Currently, history persistence is handled directly in run_stock_analysis
    logger.debug(f"Analysis completion hook registered for session: {session_id}")


def get_analysis_history_metadata(results):
    """
    Extract metadata for history storage from analysis results
    
    Args:
        results: Analysis results dictionary
        
    Returns:
        Dictionary containing metadata for history storage
    """
    metadata = {
        'session_id': results.get('session_id'),
        'analysis_type': 'comprehensive',
        'success': results.get('success', False),
        'has_demo_data': results.get('is_demo', False),
        'demo_reason': results.get('demo_reason'),
        'created_at': datetime.now().isoformat()
    }
    
    # Add LLM configuration
    if 'llm_provider' in results:
        metadata['llm_config'] = {
            'provider': results['llm_provider'],
            'model': results['llm_model']
        }
    
    # Add analysis configuration
    if 'analysts' in results:
        metadata['analysis_config'] = {
            'analysts': results['analysts'],
            'research_depth': results['research_depth']
        }
    
    return metadata

def extract_risk_assessment(state):
    """从分析状态中提取风险评估数据"""
    try:
        risk_debate_state = state.get('risk_debate_state', {})

        if not risk_debate_state:
            return None

        # 提取各个风险分析师的观点并进行中文化
        risky_analysis = translate_analyst_labels(risk_debate_state.get('risky_history', ''))
        safe_analysis = translate_analyst_labels(risk_debate_state.get('safe_history', ''))
        neutral_analysis = translate_analyst_labels(risk_debate_state.get('neutral_history', ''))
        judge_decision = translate_analyst_labels(risk_debate_state.get('judge_decision', ''))

        # 格式化风险评估报告
        risk_assessment = f"""
## ⚠️ 风险评估报告

### 🔴 激进风险分析师观点
{risky_analysis if risky_analysis else '暂无激进风险分析'}

### 🟡 中性风险分析师观点
{neutral_analysis if neutral_analysis else '暂无中性风险分析'}

### 🟢 保守风险分析师观点
{safe_analysis if safe_analysis else '暂无保守风险分析'}

### 🏛️ 风险管理委员会最终决议
{judge_decision if judge_decision else '暂无风险管理决议'}

---
*风险评估基于多角度分析，请结合个人风险承受能力做出投资决策*
        """.strip()

        return risk_assessment

    except Exception as e:
        logger.info(f"提取风险评估数据时出错: {e}")
        return None

@with_error_handling(context="股票分析执行", show_user_error=False)
def run_stock_analysis(stock_symbol, analysis_date, analysts, research_depth, llm_provider, llm_model, market_type="美股", progress_callback=None, session_id=None):
    """执行股票分析，包含完整的错误处理和进度跟踪

    Args:
        stock_symbol: 股票代码
        analysis_date: 分析日期
        analysts: 分析师列表
        research_depth: 研究深度
        llm_provider: LLM提供商 (dashscope/deepseek/google)
        llm_model: 大模型名称
        progress_callback: 进度回调函数，用于更新UI状态
    """
    
    # Initialize progress tracker
    progress_tracker = ProgressTracker(total_steps=10)
    
    def update_progress(message, step=None, total_steps=None):
        """更新进度，包含错误跟踪"""
        if step is not None:
            progress_tracker.update(step, message)
        
        if progress_callback:
            progress_callback(message, step, total_steps)
        logger.info(f"[进度] {message}")
    
    # Validate input parameters
    validation_rules = {
        'stock_symbol': validate_stock_symbol,
        'analysis_date': validate_date_string,
        'research_depth': validate_positive_integer,
        'llm_provider': validate_non_empty_string,
        'llm_model': validate_non_empty_string,
        'market_type': validate_non_empty_string
    }
    
    input_data = {
        'stock_symbol': stock_symbol,
        'analysis_date': analysis_date,
        'research_depth': research_depth,
        'llm_provider': llm_provider,
        'llm_model': llm_model,
        'market_type': market_type
    }
    
    is_valid, sanitized_data, validation_errors = validate_and_sanitize_input(input_data, validation_rules)
    
    if not is_valid:
        error_msg = f"输入参数验证失败: {'; '.join(validation_errors)}"
        logger.error(error_msg)
        user_error = ErrorHandler.create_user_friendly_error(
            ValueError(error_msg), "参数验证"
        )
        show_error_to_user(user_error)
        return {
            'success': False,
            'error': error_msg,
            'suggestion': "请检查输入参数的格式和有效性",
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date
        }
    
    # Use sanitized data
    stock_symbol = sanitized_data['stock_symbol']
    analysis_date = sanitized_data['analysis_date']
    research_depth = sanitized_data['research_depth']
    llm_provider = sanitized_data['llm_provider']
    llm_model = sanitized_data['llm_model']
    market_type = sanitized_data['market_type']
    
    # Validate analysts list
    if not analysts or not isinstance(analysts, list) or len(analysts) == 0:
        error_msg = "分析师列表不能为空"
        logger.error(error_msg)
        user_error = ErrorHandler.create_user_friendly_error(
            ValueError(error_msg), "分析师配置"
        )
        show_error_to_user(user_error)
        return {
            'success': False,
            'error': error_msg,
            'suggestion': "请至少选择一个分析师",
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date
        }

    # 使用传入的session_id，如果没有则生成新的
    if session_id:
        logger.info(f"Using provided session_id: {session_id}")
    else:
        # 生成会话ID用于Token跟踪和日志关联
        session_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Generated new session_id: {session_id}")
    
    # Initialize history storage and create analysis record
    history_record = None
    try:
        from web.utils.history_storage import get_history_storage
        from web.models.history_models import AnalysisHistoryRecord, AnalysisStatus
        from datetime import datetime as dt
        
        history_storage = get_history_storage()
        
        # Create analysis history record
        history_record = AnalysisHistoryRecord(
            analysis_id=session_id,
            stock_symbol=stock_symbol,
            stock_name=f"股票{stock_symbol}",  # Temporary name, will be updated after data preparation
            market_type=market_type,
            analysis_date=dt.strptime(analysis_date, '%Y-%m-%d') if isinstance(analysis_date, str) else analysis_date,
            status=AnalysisStatus.IN_PROGRESS.value,
            analysis_type="comprehensive",
            analysts_used=analysts,
            research_depth=research_depth,
            llm_provider=llm_provider,
            llm_model=llm_model,
            metadata={
                'session_id': session_id,
                'user_agent': 'streamlit_web',
                'version': '0.1.2'
            }
        )
        
        logger.info(f"Created analysis history record: {session_id}")
        
    except Exception as e:
        logger.warning(f"Failed to initialize history storage: {e}")
        # Continue without history storage - graceful fallback

    # 1. 数据预获取和验证阶段
    update_progress("🔍 验证股票代码并预获取数据...", 1, 10)

    @with_retry(max_attempts=3, delay=2.0, retry_on=(ConnectionError, TimeoutError))
    def prepare_stock_data_with_retry():
        from tradingagents.utils.stock_validator import prepare_stock_data
        return prepare_stock_data(
            stock_code=stock_symbol,
            market_type=market_type,
            period_days=30,  # 可以根据research_depth调整
            analysis_date=analysis_date
        )

    try:
        # 预获取股票数据（默认30天历史数据）
        preparation_result = prepare_stock_data_with_retry()

        if not preparation_result.is_valid:
            error_msg = f"❌ 股票数据验证失败: {preparation_result.error_message}"
            update_progress(error_msg, 1)
            logger.error(f"[{session_id}] {error_msg}")

            # Create user-friendly error
            user_error = ErrorHandler.create_user_friendly_error(
                ValueError(preparation_result.error_message), "股票数据验证"
            )
            
            # Save failed validation to history
            if history_record and history_storage.is_available():
                try:
                    history_record.update_status(AnalysisStatus.FAILED.value)
                    history_record.add_metadata('error', preparation_result.error_message)
                    history_record.add_metadata('error_type', 'data_validation_failed')
                    history_record.add_metadata('suggestion', preparation_result.suggestion)
                    history_record.add_metadata('success', False)
                    
                    if history_storage.save_analysis(history_record):
                        logger.info(f"Saved failed validation to history: {session_id}")
                        
                except Exception as history_error:
                    logger.error(f"Error saving failed validation to history: {history_error}")

            return {
                'success': False,
                'error': preparation_result.error_message,
                'suggestion': preparation_result.suggestion,
                'stock_symbol': stock_symbol,
                'analysis_date': analysis_date,
                'session_id': session_id,
                'user_error': user_error
            }

        # 数据预获取成功
        success_msg = f"✅ 数据准备完成: {preparation_result.stock_name} ({preparation_result.market_type})"
        update_progress(success_msg, 2)
        logger.info(f"[{session_id}] {success_msg}")
        logger.info(f"[{session_id}] 缓存状态: {preparation_result.cache_status}")
        
        # Update history record with stock name
        if history_record:
            history_record.stock_name = preparation_result.stock_name
            history_record.market_type = preparation_result.market_type

    except Exception as e:
        error_msg = f"❌ 数据预获取过程中发生错误: {str(e)}"
        update_progress(error_msg, 1)
        logger.error(f"[{session_id}] {error_msg}")

        # Create user-friendly error
        user_error = ErrorHandler.create_user_friendly_error(e, "数据预获取")

        # Save data preparation failure to history
        if history_record and history_storage.is_available():
            try:
                history_record.update_status(AnalysisStatus.FAILED.value)
                history_record.add_metadata('error', str(e))
                history_record.add_metadata('error_type', 'data_preparation_failed')
                history_record.add_metadata('success', False)
                
                if history_storage.save_analysis(history_record):
                    logger.info(f"Saved data preparation failure to history: {session_id}")
                    
            except Exception as history_error:
                logger.error(f"Error saving data preparation failure to history: {history_error}")

        return {
            'success': False,
            'error': error_msg,
            'suggestion': "请检查网络连接或稍后重试",
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date,
            'session_id': session_id,
            'user_error': user_error
        }

    # 记录分析开始的详细日志
    logger_manager = get_logger_manager()
    import time
    analysis_start_time = time.time()

    logger_manager.log_analysis_start(
        logger, stock_symbol, "comprehensive_analysis", session_id
    )

    logger.info(f"🚀 [分析开始] 股票分析启动",
               extra={
                   'stock_symbol': stock_symbol,
                   'analysis_date': analysis_date,
                   'analysts': analysts,
                   'research_depth': research_depth,
                   'llm_provider': llm_provider,
                   'llm_model': llm_model,
                   'market_type': market_type,
                   'session_id': session_id,
                   'event_type': 'web_analysis_start'
               })

    update_progress("🚀 开始股票分析...")

    # 估算Token使用（用于成本预估）
    if TOKEN_TRACKING_ENABLED:
        estimated_input = 2000 * len(analysts)  # 估算每个分析师2000个输入token
        estimated_output = 1000 * len(analysts)  # 估算每个分析师1000个输出token
        estimated_cost = token_tracker.estimate_cost(llm_provider, llm_model, estimated_input, estimated_output)

        update_progress(f"💰 预估分析成本: ¥{estimated_cost:.4f}")

    # 验证环境变量
    update_progress("检查环境变量配置...")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")

    logger.info(f"环境变量检查:")
    logger.info(f"  DEEPSEEK_API_KEY: {'已设置' if deepseek_key else '未设置'}")
    logger.info(f"  DASHSCOPE_API_KEY: {'已设置' if dashscope_key else '未设置'}")
    logger.info(f"  OPENAI_API_KEY: {'已设置' if openai_key else '未设置'}")
    logger.info(f"  FINNHUB_API_KEY: {'已设置' if finnhub_key else '未设置'}")

    # 检查至少有一个AI模型API密钥
    if not any([deepseek_key, dashscope_key, openai_key]):
        raise ValueError("请至少配置一个AI模型API密钥：DEEPSEEK_API_KEY、DASHSCOPE_API_KEY 或 OPENAI_API_KEY")
    if not finnhub_key:
        raise ValueError("FINNHUB_API_KEY 环境变量未设置")

    update_progress("环境变量验证通过")

    try:
        # 导入必要的模块
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        # 创建配置
        update_progress("配置分析参数...")
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = llm_provider
        config["deep_think_llm"] = llm_model
        config["quick_think_llm"] = llm_model
        # 根据研究深度调整配置
        if research_depth == 1:  # 1级 - 快速分析
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1
            # 保持内存功能启用，因为内存操作开销很小但能显著提升分析质量
            config["memory_enabled"] = True

            # 统一使用在线工具，避免离线工具的各种问题
            config["online_tools"] = True  # 所有市场都使用统一工具
            logger.info(f"🔧 [快速分析] {market_type}使用统一工具，确保数据源正确和稳定性")
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-turbo"  # 使用最快模型
                config["deep_think_llm"] = "qwen-plus"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"  # DeepSeek只有一个模型
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 2:  # 2级 - 基础分析
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen-plus"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 3:  # 3级 - 标准分析 (默认)
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 2
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 4:  # 4级 - 深度分析
            config["max_debate_rounds"] = 2
            config["max_risk_discuss_rounds"] = 2
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        else:  # 5级 - 全面分析
            config["max_debate_rounds"] = 3
            config["max_risk_discuss_rounds"] = 3
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-max"
                config["deep_think_llm"] = "qwen-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"

        # 根据LLM提供商设置不同的配置
        if llm_provider == "dashscope":
            config["backend_url"] = "https://dashscope.aliyuncs.com/api/v1"
        elif llm_provider == "deepseek":
            config["backend_url"] = "https://api.deepseek.com"
        elif llm_provider == "google":
            # Google AI不需要backend_url，使用默认的OpenAI格式
            config["backend_url"] = "https://api.openai.com/v1"

        # 修复路径问题
        config["data_dir"] = str(project_root / "data")
        config["results_dir"] = str(project_root / "results")
        config["data_cache_dir"] = str(project_root / "tradingagents" / "dataflows" / "data_cache")

        # 确保目录存在
        update_progress("📁 创建必要的目录...")
        os.makedirs(config["data_dir"], exist_ok=True)
        os.makedirs(config["results_dir"], exist_ok=True)
        os.makedirs(config["data_cache_dir"], exist_ok=True)

        logger.info(f"使用配置: {config}")
        logger.info(f"分析师列表: {analysts}")
        logger.info(f"股票代码: {stock_symbol}")
        logger.info(f"分析日期: {analysis_date}")

        # 根据市场类型调整股票代码格式
        logger.debug(f"🔍 [RUNNER DEBUG] ===== 股票代码格式化 =====")
        logger.debug(f"🔍 [RUNNER DEBUG] 原始股票代码: '{stock_symbol}'")
        logger.debug(f"🔍 [RUNNER DEBUG] 市场类型: '{market_type}'")

        if market_type == "A股":
            # A股代码不需要特殊处理，保持原样
            formatted_symbol = stock_symbol
            logger.debug(f"🔍 [RUNNER DEBUG] A股代码保持原样: '{formatted_symbol}'")
            update_progress(f"🇨🇳 准备分析A股: {formatted_symbol}")
        elif market_type == "港股":
            # 港股代码转为大写，确保.HK后缀
            formatted_symbol = stock_symbol.upper()
            if not formatted_symbol.endswith('.HK'):
                # 如果是纯数字，添加.HK后缀
                if formatted_symbol.isdigit():
                    formatted_symbol = f"{formatted_symbol.zfill(4)}.HK"
            update_progress(f"🇭🇰 准备分析港股: {formatted_symbol}")
        else:
            # 美股代码转为大写
            formatted_symbol = stock_symbol.upper()
            logger.debug(f"🔍 [RUNNER DEBUG] 美股代码转大写: '{stock_symbol}' -> '{formatted_symbol}'")
            update_progress(f"🇺🇸 准备分析美股: {formatted_symbol}")

        logger.debug(f"🔍 [RUNNER DEBUG] 最终传递给分析引擎的股票代码: '{formatted_symbol}'")

        # 初始化交易图
        update_progress("🔧 初始化分析引擎...")
        graph = TradingAgentsGraph(analysts, config=config, debug=False)

        # 执行分析
        update_progress(f"📊 开始分析 {formatted_symbol} 股票，这可能需要几分钟时间...")
        logger.debug(f"🔍 [RUNNER DEBUG] ===== 调用graph.propagate =====")
        logger.debug(f"🔍 [RUNNER DEBUG] 传递给graph.propagate的参数:")
        logger.debug(f"🔍 [RUNNER DEBUG]   symbol: '{formatted_symbol}'")
        logger.debug(f"🔍 [RUNNER DEBUG]   date: '{analysis_date}'")

        state, decision = graph.propagate(formatted_symbol, analysis_date)

        # 调试信息
        logger.debug(f"🔍 [DEBUG] 分析完成，decision类型: {type(decision)}")
        logger.debug(f"🔍 [DEBUG] decision内容: {decision}")

        # 格式化结果
        update_progress("📋 分析完成，正在整理结果...")

        # 提取风险评估数据
        risk_assessment = extract_risk_assessment(state)

        # 将风险评估添加到状态中
        if risk_assessment:
            state['risk_assessment'] = risk_assessment

        # 记录Token使用（实际使用量，这里使用估算值）
        if TOKEN_TRACKING_ENABLED:
            # 在实际应用中，这些值应该从LLM响应中获取
            # 这里使用基于分析师数量和研究深度的估算
            actual_input_tokens = len(analysts) * (1500 if research_depth == "快速" else 2500 if research_depth == "标准" else 4000)
            actual_output_tokens = len(analysts) * (800 if research_depth == "快速" else 1200 if research_depth == "标准" else 2000)

            usage_record = token_tracker.track_usage(
                provider=llm_provider,
                model_name=llm_model,
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                session_id=session_id,
                analysis_type=f"{market_type}_analysis"
            )

            if usage_record:
                update_progress(f"💰 记录使用成本: ¥{usage_record.cost:.4f}")

        results = {
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date,
            'analysts': analysts,
            'research_depth': research_depth,
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'state': state,
            'decision': decision,
            'success': True,
            'error': None,
            'session_id': session_id if TOKEN_TRACKING_ENABLED else None
        }

        # 记录分析完成的详细日志
        analysis_duration = time.time() - analysis_start_time

        # 计算总成本（如果有Token跟踪）
        total_cost = 0.0
        if TOKEN_TRACKING_ENABLED:
            try:
                total_cost = token_tracker.get_session_cost(session_id)
            except:
                pass

        # Save analysis results to history
        if history_record and history_storage.is_available():
            try:
                # Clean results for MongoDB serialization
                cleaned_results = _clean_results_for_storage(results)
                
                # Generate formatted results for consistent reporting
                formatted_results = format_analysis_results(results)
                
                # Update history record with results and completion data
                history_record.set_execution_time(analysis_duration)
                history_record.add_results(
                    raw_results=cleaned_results,
                    formatted_results=formatted_results
                )
                
                # Add token usage if available
                if TOKEN_TRACKING_ENABLED and total_cost > 0:
                    # Estimate token usage based on cost and provider
                    estimated_input = actual_input_tokens if 'actual_input_tokens' in locals() else len(analysts) * 2000
                    estimated_output = actual_output_tokens if 'actual_output_tokens' in locals() else len(analysts) * 1000
                    history_record.add_token_usage(estimated_input, estimated_output, total_cost)
                
                # Add session metadata
                history_record.add_metadata('analysis_duration', analysis_duration)
                history_record.add_metadata('success', True)
                
                # Update status to completed
                history_record.update_status(AnalysisStatus.COMPLETED.value)
                
                # Save to database
                if history_storage.save_analysis(history_record):
                    logger.info(f"Successfully saved analysis to history: {session_id}")
                    update_progress("💾 分析结果已保存到历史记录")
                else:
                    logger.warning(f"Failed to save analysis to history: {session_id}")
                    
            except Exception as e:
                logger.error(f"Error saving analysis to history: {e}")
                # Continue without failing the analysis

        logger_manager.log_analysis_complete(
            logger, stock_symbol, "comprehensive_analysis", session_id,
            analysis_duration, total_cost
        )

        logger.info(f"✅ [分析完成] 股票分析成功完成",
                   extra={
                       'stock_symbol': stock_symbol,
                       'session_id': session_id,
                       'duration': analysis_duration,
                       'total_cost': total_cost,
                       'analysts_used': analysts,
                       'success': True,
                       'event_type': 'web_analysis_complete'
                   })

        update_progress("✅ 分析成功完成！")
        return results

    except Exception as e:
        # 记录分析失败的详细日志
        analysis_duration = time.time() - analysis_start_time

        # Save failed analysis to history
        if history_record and history_storage.is_available():
            try:
                history_record.update_status(AnalysisStatus.FAILED.value)
                history_record.set_execution_time(analysis_duration)
                history_record.add_metadata('error', str(e))
                history_record.add_metadata('error_type', type(e).__name__)
                history_record.add_metadata('success', False)
                
                if history_storage.save_analysis(history_record):
                    logger.info(f"Saved failed analysis to history: {session_id}")
                    
            except Exception as history_error:
                logger.error(f"Error saving failed analysis to history: {history_error}")

        logger_manager.log_module_error(
            logger, "comprehensive_analysis", stock_symbol, session_id,
            analysis_duration, str(e)
        )

        logger.error(f"❌ [分析失败] 股票分析执行失败",
                    extra={
                        'stock_symbol': stock_symbol,
                        'session_id': session_id,
                        'duration': analysis_duration,
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'analysts_used': analysts,
                        'success': False,
                        'event_type': 'web_analysis_error'
                    }, exc_info=True)

        # 如果真实分析失败，返回模拟数据用于演示
        return generate_demo_results(stock_symbol, analysis_date, analysts, research_depth, llm_provider, llm_model, str(e), market_type)

def format_analysis_results(results):
    """格式化分析结果用于显示"""
    
    if not results['success']:
        return {
            'error': results['error'],
            'success': False
        }
    
    # Try to update history record with formatted results
    session_id = results.get('session_id')
    if session_id:
        try:
            from web.utils.history_storage import get_history_storage
            history_storage = get_history_storage()
            
            if history_storage.is_available():
                # Get the existing record
                history_record = history_storage.get_analysis_by_id(session_id)
                if history_record:
                    # We'll update the formatted results after processing
                    pass
        except Exception as e:
            logger.warning(f"Could not retrieve history record for formatting: {e}")
    
    state = results['state']
    decision = results['decision']

    # 提取关键信息
    # decision 可能是字符串（如 "BUY", "SELL", "HOLD"）或字典
    if isinstance(decision, str):
        # 将英文投资建议转换为中文
        action_translation = {
            'BUY': '买入',
            'SELL': '卖出',
            'HOLD': '持有',
            'buy': '买入',
            'sell': '卖出',
            'hold': '持有'
        }
        action = action_translation.get(decision.strip(), decision.strip())

        formatted_decision = {
            'action': action,
            'confidence': 0.7,  # 默认置信度
            'risk_score': 0.3,  # 默认风险分数
            'target_price': None,  # 字符串格式没有目标价格
            'reasoning': f'基于AI分析，建议{decision.strip().upper()}'
        }
    elif isinstance(decision, dict):
        # 处理目标价格 - 确保正确提取数值
        target_price = decision.get('target_price')
        if target_price is not None and target_price != 'N/A':
            try:
                # 尝试转换为浮点数
                if isinstance(target_price, str):
                    # 移除货币符号和空格
                    clean_price = target_price.replace('$', '').replace('¥', '').replace('￥', '').strip()
                    target_price = float(clean_price) if clean_price and clean_price != 'None' else None
                elif isinstance(target_price, (int, float)):
                    target_price = float(target_price)
                else:
                    target_price = None
            except (ValueError, TypeError):
                target_price = None
        else:
            target_price = None

        # 将英文投资建议转换为中文
        action_translation = {
            'BUY': '买入',
            'SELL': '卖出',
            'HOLD': '持有',
            'buy': '买入',
            'sell': '卖出',
            'hold': '持有'
        }
        action = decision.get('action', '持有')
        chinese_action = action_translation.get(action, action)

        formatted_decision = {
            'action': chinese_action,
            'confidence': decision.get('confidence', 0.5),
            'risk_score': decision.get('risk_score', 0.3),
            'target_price': target_price,
            'reasoning': decision.get('reasoning', '暂无分析推理')
        }
    else:
        # 处理其他类型
        formatted_decision = {
            'action': '持有',
            'confidence': 0.5,
            'risk_score': 0.3,
            'target_price': None,
            'reasoning': f'分析结果: {str(decision)}'
        }
    
    # 格式化状态信息
    formatted_state = {}
    
    # 处理各个分析模块的结果
    analysis_keys = [
        'market_report',
        'fundamentals_report', 
        'sentiment_report',
        'news_report',
        'risk_assessment',
        'investment_plan'
    ]
    
    for key in analysis_keys:
        if key in state:
            # 对文本内容进行中文化处理
            content = state[key]
            if isinstance(content, str):
                content = translate_analyst_labels(content)
            formatted_state[key] = content
    
    formatted_results = {
        'stock_symbol': results['stock_symbol'],
        'decision': formatted_decision,
        'state': formatted_state,
        'success': True,
        # 将配置信息放在顶层，供前端直接访问
        'analysis_date': results['analysis_date'],
        'analysts': results['analysts'],
        'research_depth': results['research_depth'],
        'llm_provider': results.get('llm_provider', 'dashscope'),
        'llm_model': results['llm_model'],
        'session_id': results.get('session_id'),
        'metadata': {
            'analysis_date': results['analysis_date'],
            'analysts': results['analysts'],
            'research_depth': results['research_depth'],
            'llm_provider': results.get('llm_provider', 'dashscope'),
            'llm_model': results['llm_model'],
            'session_id': results.get('session_id'),
            'formatted_at': datetime.now().isoformat()
        }
    }
    
    # Note: History record update is now handled in the main analysis flow
    # to ensure formatted results are saved consistently with raw results
    
    return formatted_results

def validate_analysis_params(stock_symbol, analysis_date, analysts, research_depth, market_type="美股"):
    """验证分析参数"""

    errors = []

    # 验证股票代码
    if not stock_symbol or len(stock_symbol.strip()) == 0:
        errors.append("股票代码不能为空")
    elif len(stock_symbol.strip()) > 10:
        errors.append("股票代码长度不能超过10个字符")
    else:
        # 根据市场类型验证代码格式
        symbol = stock_symbol.strip()
        if market_type == "A股":
            # A股：6位数字
            import re
            if not re.match(r'^\d{6}$', symbol):
                errors.append("A股代码格式错误，应为6位数字（如：000001）")
        elif market_type == "港股":
            # 港股：4-5位数字.HK 或 纯4-5位数字
            import re
            symbol_upper = symbol.upper()
            # 检查是否为 XXXX.HK 或 XXXXX.HK 格式
            hk_format = re.match(r'^\d{4,5}\.HK$', symbol_upper)
            # 检查是否为纯4-5位数字格式
            digit_format = re.match(r'^\d{4,5}$', symbol)

            if not (hk_format or digit_format):
                errors.append("港股代码格式错误，应为4位数字.HK（如：0700.HK）或4位数字（如：0700）")
        elif market_type == "美股":
            # 美股：1-5位字母
            import re
            if not re.match(r'^[A-Z]{1,5}$', symbol.upper()):
                errors.append("美股代码格式错误，应为1-5位字母（如：AAPL）")
    
    # 验证分析师列表
    if not analysts or len(analysts) == 0:
        errors.append("必须至少选择一个分析师")
    
    valid_analysts = ['market', 'social', 'news', 'fundamentals']
    invalid_analysts = [a for a in analysts if a not in valid_analysts]
    if invalid_analysts:
        errors.append(f"无效的分析师类型: {', '.join(invalid_analysts)}")
    
    # 验证研究深度
    if not isinstance(research_depth, int) or research_depth < 1 or research_depth > 5:
        errors.append("研究深度必须是1-5之间的整数")
    
    # 验证分析日期
    try:
        from datetime import datetime
        datetime.strptime(analysis_date, '%Y-%m-%d')
    except ValueError:
        errors.append("分析日期格式无效，应为YYYY-MM-DD格式")
    
    return len(errors) == 0, errors

def get_supported_stocks():
    """获取支持的股票列表"""
    
    # 常见的美股股票代码
    popular_stocks = [
        {'symbol': 'AAPL', 'name': '苹果公司', 'sector': '科技'},
        {'symbol': 'MSFT', 'name': '微软', 'sector': '科技'},
        {'symbol': 'GOOGL', 'name': '谷歌', 'sector': '科技'},
        {'symbol': 'AMZN', 'name': '亚马逊', 'sector': '消费'},
        {'symbol': 'TSLA', 'name': '特斯拉', 'sector': '汽车'},
        {'symbol': 'NVDA', 'name': '英伟达', 'sector': '科技'},
        {'symbol': 'META', 'name': 'Meta', 'sector': '科技'},
        {'symbol': 'NFLX', 'name': '奈飞', 'sector': '媒体'},
        {'symbol': 'AMD', 'name': 'AMD', 'sector': '科技'},
        {'symbol': 'INTC', 'name': '英特尔', 'sector': '科技'},
        {'symbol': 'SPY', 'name': 'S&P 500 ETF', 'sector': 'ETF'},
        {'symbol': 'QQQ', 'name': '纳斯达克100 ETF', 'sector': 'ETF'},
    ]
    
    return popular_stocks

def generate_demo_results(stock_symbol, analysis_date, analysts, research_depth, llm_provider, llm_model, error_msg, market_type="美股"):
    """生成演示分析结果"""

    import random

    # 根据市场类型设置货币符号和价格范围
    if market_type == "港股":
        currency_symbol = "HK$"
        price_range = (50, 500)  # 港股价格范围
        market_name = "港股"
    elif market_type == "A股":
        currency_symbol = "¥"
        price_range = (5, 100)   # A股价格范围
        market_name = "A股"
    else:  # 美股
        currency_symbol = "$"
        price_range = (50, 300)  # 美股价格范围
        market_name = "美股"

    # 生成模拟决策
    actions = ['买入', '持有', '卖出']
    action = random.choice(actions)

    demo_decision = {
        'action': action,
        'confidence': round(random.uniform(0.6, 0.9), 2),
        'risk_score': round(random.uniform(0.2, 0.7), 2),
        'target_price': round(random.uniform(*price_range), 2),
        'reasoning': f"""
基于对{market_name}{stock_symbol}的综合分析，我们的AI分析团队得出以下结论：

**投资建议**: {action}
**目标价格**: {currency_symbol}{round(random.uniform(*price_range), 2)}

**主要分析要点**:
1. **技术面分析**: 当前价格趋势显示{'上涨' if action == '买入' else '下跌' if action == '卖出' else '横盘'}信号
2. **基本面评估**: 公司财务状况{'良好' if action == '买入' else '一般' if action == '持有' else '需关注'}
3. **市场情绪**: 投资者情绪{'乐观' if action == '买入' else '中性' if action == '持有' else '谨慎'}
4. **风险评估**: 当前风险水平为{'中等' if action == '持有' else '较低' if action == '买入' else '较高'}

**注意**: 这是演示数据，实际分析需要配置正确的API密钥。
        """
    }

    # 生成模拟状态数据
    demo_state = {}

    if 'market' in analysts:
        current_price = round(random.uniform(*price_range), 2)
        high_price = round(current_price * random.uniform(1.2, 1.8), 2)
        low_price = round(current_price * random.uniform(0.5, 0.8), 2)

        demo_state['market_report'] = f"""
## 📈 {market_name}{stock_symbol} 技术面分析报告

### 价格趋势分析
- **当前价格**: {currency_symbol}{current_price}
- **日内变化**: {random.choice(['+', '-'])}{round(random.uniform(0.5, 5), 2)}%
- **52周高点**: {currency_symbol}{high_price}
- **52周低点**: {currency_symbol}{low_price}

### 技术指标
- **RSI (14日)**: {round(random.uniform(30, 70), 1)}
- **MACD**: {'看涨' if action == 'BUY' else '看跌' if action == 'SELL' else '中性'}
- **移动平均线**: 价格{'高于' if action == 'BUY' else '低于' if action == 'SELL' else '接近'}20日均线

### 支撑阻力位
- **支撑位**: ${round(random.uniform(80, 120), 2)}
- **阻力位**: ${round(random.uniform(250, 350), 2)}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if 'fundamentals' in analysts:
        demo_state['fundamentals_report'] = f"""
## 💰 {stock_symbol} 基本面分析报告

### 财务指标
- **市盈率 (P/E)**: {round(random.uniform(15, 35), 1)}
- **市净率 (P/B)**: {round(random.uniform(1, 5), 1)}
- **净资产收益率 (ROE)**: {round(random.uniform(10, 25), 1)}%
- **毛利率**: {round(random.uniform(20, 60), 1)}%

### 盈利能力
- **营收增长**: {random.choice(['+', '-'])}{round(random.uniform(5, 20), 1)}%
- **净利润增长**: {random.choice(['+', '-'])}{round(random.uniform(10, 30), 1)}%
- **每股收益**: ${round(random.uniform(2, 15), 2)}

### 财务健康度
- **负债率**: {round(random.uniform(20, 60), 1)}%
- **流动比率**: {round(random.uniform(1, 3), 1)}
- **现金流**: {'正向' if action != 'SELL' else '需关注'}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if 'social' in analysts:
        demo_state['sentiment_report'] = f"""
## 💭 {stock_symbol} 市场情绪分析报告

### 社交媒体情绪
- **整体情绪**: {'积极' if action == 'BUY' else '消极' if action == 'SELL' else '中性'}
- **情绪强度**: {round(random.uniform(0.5, 0.9), 2)}
- **讨论热度**: {'高' if random.random() > 0.5 else '中等'}

### 投资者情绪指标
- **恐慌贪婪指数**: {round(random.uniform(20, 80), 0)}
- **看涨看跌比**: {round(random.uniform(0.8, 1.5), 2)}
- **期权Put/Call比**: {round(random.uniform(0.5, 1.2), 2)}

### 机构投资者动向
- **机构持仓变化**: {random.choice(['增持', '减持', '维持'])}
- **分析师评级**: {'买入' if action == 'BUY' else '卖出' if action == 'SELL' else '持有'}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if 'news' in analysts:
        demo_state['news_report'] = f"""
## 📰 {stock_symbol} 新闻事件分析报告

### 近期重要新闻
1. **财报发布**: 公司发布{'超预期' if action == 'BUY' else '低于预期' if action == 'SELL' else '符合预期'}的季度财报
2. **行业动态**: 所在行业面临{'利好' if action == 'BUY' else '挑战' if action == 'SELL' else '稳定'}政策环境
3. **公司公告**: 管理层{'乐观' if action == 'BUY' else '谨慎' if action == 'SELL' else '稳健'}展望未来

### 新闻情绪分析
- **正面新闻占比**: {round(random.uniform(40, 80), 0)}%
- **负面新闻占比**: {round(random.uniform(10, 40), 0)}%
- **中性新闻占比**: {round(random.uniform(20, 50), 0)}%

### 市场影响评估
- **短期影响**: {'正面' if action == 'BUY' else '负面' if action == 'SELL' else '中性'}
- **长期影响**: {'积极' if action != 'SELL' else '需观察'}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    # 添加风险评估和投资建议
    demo_state['risk_assessment'] = f"""
## ⚠️ {stock_symbol} 风险评估报告

### 主要风险因素
1. **市场风险**: {'低' if action == 'BUY' else '高' if action == 'SELL' else '中等'}
2. **行业风险**: {'可控' if action != 'SELL' else '需关注'}
3. **公司特定风险**: {'较低' if action == 'BUY' else '中等'}

### 风险等级评估
- **总体风险等级**: {'低风险' if action == 'BUY' else '高风险' if action == 'SELL' else '中等风险'}
- **建议仓位**: {random.choice(['轻仓', '标准仓位', '重仓']) if action != 'SELL' else '建议减仓'}

*注意: 这是演示数据，实际分析需要配置API密钥*
    """

    demo_state['investment_plan'] = f"""
## 📋 {stock_symbol} 投资建议

### 具体操作建议
- **操作方向**: {action}
- **建议价位**: ${round(random.uniform(90, 310), 2)}
- **止损位**: ${round(random.uniform(80, 200), 2)}
- **目标价位**: ${round(random.uniform(150, 400), 2)}

### 投资策略
- **投资期限**: {'短期' if research_depth <= 2 else '中长期'}
- **仓位管理**: {'分批建仓' if action == 'BUY' else '分批减仓' if action == 'SELL' else '维持现状'}

*注意: 这是演示数据，实际分析需要配置API密钥*
    """

    return {
        'stock_symbol': stock_symbol,
        'analysis_date': analysis_date,
        'analysts': analysts,
        'research_depth': research_depth,
        'llm_provider': llm_provider,
        'llm_model': llm_model,
        'state': demo_state,
        'decision': demo_decision,
        'success': True,
        'error': None,
        'is_demo': True,
        'demo_reason': f"API调用失败，显示演示数据。错误信息: {error_msg}"
    }
