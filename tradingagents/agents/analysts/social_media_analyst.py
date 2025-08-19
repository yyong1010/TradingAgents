from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage, HumanMessage
import time
import json
import traceback

# 导入统一日志系统和分析模块日志装饰器
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_analyst_module
from tradingagents.config.debug_config import debug_config
logger = get_logger("analysts.social_media")


def get_stock_market_info(ticker: str) -> dict:
    """根据股票代码获取市场信息和特征"""
    import re
    
    # 基本信息
    info = {
        'market': 'A股',
        'industry': '需进一步确认',
        'investor_type': '散户为主',
        'policy_sensitivity': '中等',
        'performance_sensitivity': '高',
        'concept_sensitivity': '中等'
    }
    
    # 根据股票代码判断市场类型
    if re.match(r'^\d{6}$', ticker):
        # A股代码
        code_prefix = ticker[:3]
        if code_prefix in ['000', '001', '002', '003']:
            info['market'] = 'A股-深交所主板/中小板'
        elif code_prefix == '300':
            info['market'] = 'A股-创业板'
            info['concept_sensitivity'] = '高'
            info['policy_sensitivity'] = '高'
        elif code_prefix in ['600', '601', '603', '605']:
            info['market'] = 'A股-上交所主板'
        elif code_prefix in ['688']:
            info['market'] = 'A股-科创板'
            info['concept_sensitivity'] = '极高'
            info['policy_sensitivity'] = '高'
            info['investor_type'] = '机构为主'
    elif ticker.upper().endswith('.HK'):
        info['market'] = '港股'
        info['investor_type'] = '机构与散户并重'
    elif len(ticker) <= 5 and ticker.isalpha():
        info['market'] = '美股'
        info['investor_type'] = '机构为主'
    
    # 根据代码特征推断行业敏感度
    if ticker.startswith('300'):
        # 创业板通常是科技、新兴产业
        info['industry'] = '科技/新兴产业'
        info['performance_sensitivity'] = '极高'
    elif ticker.startswith('688'):
        # 科创板
        info['industry'] = '科技创新'
        info['performance_sensitivity'] = '极高'
    elif ticker.startswith('60'):
        # 上交所主板，通常是传统行业
        info['industry'] = '传统行业/大盘股'
        info['performance_sensitivity'] = '中等'
        info['concept_sensitivity'] = '低'
    
    return info


def create_social_media_analyst(llm, toolkit):
    @log_analyst_module("social_media")
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        company_name = state["company_of_interest"]

        # 始终优先使用真实的中国社交媒体数据源
        tools = [toolkit.get_stock_news_openai]

        system_message = (
            """您是一位专业的中国市场社交媒体和投资情绪分析师，负责分析中国投资者对特定股票的讨论和情绪变化。

您的主要职责包括：
1. 分析中国主要财经平台的投资者情绪（如雪球、东方财富股吧等）
2. 监控财经媒体和新闻对股票的报道倾向
3. 识别影响股价的热点事件和市场传言
4. 评估散户与机构投资者的观点差异
5. 分析政策变化对投资者情绪的影响
6. 评估情绪变化对股价的潜在影响

重点关注平台：
- 财经新闻：财联社、新浪财经、东方财富、腾讯财经
- 投资社区：雪球、东方财富股吧、同花顺
- 社交媒体：微博财经大V、知乎投资话题
- 专业分析：各大券商研报、财经自媒体

分析要点：
- 投资者情绪的变化趋势和原因
- 关键意见领袖(KOL)的观点和影响力
- 热点事件对股价预期的影响
- 政策解读和市场预期变化
- 散户情绪与机构观点的差异

📊 情绪价格影响分析要求：
- 量化投资者情绪强度（乐观/悲观程度）
- 评估情绪变化对短期股价的影响（1-5天）
- 分析散户情绪与股价走势的相关性
- 识别情绪驱动的价格支撑位和阻力位
- 提供基于情绪分析的价格预期调整
- 评估市场情绪对估值的影响程度
- 不允许回复'无法评估情绪影响'或'需要更多数据'

💰 必须包含：
- 情绪指数评分（1-10分）
- 预期价格波动幅度
- 基于情绪的交易时机建议

请撰写详细的中文分析报告，并在报告末尾附上Markdown表格总结关键发现。
注意：由于中国社交媒体API限制，如果数据获取受限，请明确说明并提供替代分析建议。"""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "您是一位有用的AI助手，与其他助手协作。"
                    " 使用提供的工具来推进回答问题。"
                    " 如果您无法完全回答，没关系；具有不同工具的其他助手"
                    " 将从您停下的地方继续帮助。执行您能做的以取得进展。"
                    " 如果您或任何其他助手有最终交易提案：**买入/持有/卖出**或可交付成果，"
                    " 请在您的回应前加上最终交易提案：**买入/持有/卖出**，以便团队知道停止。"
                    " 您可以访问以下工具：{tool_names}。\n{system_message}"
                    "供您参考，当前日期是{current_date}。我们要分析的当前公司是{ticker}。请用中文撰写所有分析内容。",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        # 安全地获取工具名称，处理函数和工具对象
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        # 处理社交媒体情绪分析报告
        if len(result.tool_calls) == 0:
            # 没有工具调用，直接使用LLM的回复
            report = result.content if result.content else "暂无社交媒体分析数据。"
            logger.info(f"💭 [社交媒体分析师] 直接回复，长度: {len(report)}")
        else:
            # 有工具调用，执行工具并生成完整分析报告
            logger.info(f"💭 [社交媒体分析师] 工具调用: {[call.get('name', 'unknown') for call in result.tool_calls]}")

            try:
                # 执行工具调用
                tool_messages = []
                for tool_call in result.tool_calls:
                    tool_name = tool_call.get('name')
                    tool_args = tool_call.get('args', {})
                    tool_id = tool_call.get('id')

                    logger.debug(f"💭 [DEBUG] 执行工具: {tool_name}, 参数: {tool_args}")

                    # 找到对应的工具并执行
                    tool_result = None
                    for tool in tools:
                        # 安全地获取工具名称进行比较
                        current_tool_name = None
                        if hasattr(tool, 'name'):
                            current_tool_name = tool.name
                        elif hasattr(tool, '__name__'):
                            current_tool_name = tool.__name__

                        if current_tool_name == tool_name:
                            try:
                                tool_result = tool.invoke(tool_args)
                                logger.debug(f"💭 [DEBUG] 工具执行成功，结果长度: {len(str(tool_result))}")
                                break
                            except Exception as tool_error:
                                logger.error(f"❌ [DEBUG] 工具执行失败: {tool_error}")
                                tool_result = f"工具执行失败: {str(tool_error)}"

                    if tool_result is None:
                        tool_result = f"未找到工具: {tool_name}"

                    # 创建工具消息
                    tool_message = ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_id
                    )
                    tool_messages.append(tool_message)
                    
                    # 详细日志：记录工具执行结果
                    if debug_config.is_tool_debug_enabled():
                        logger.info(f"🔍 [工具调试] {tool_name} 执行结果:")
                        result_preview = str(tool_result)[:500] + "..." if len(str(tool_result)) > 500 else str(tool_result)
                        logger.info(f"  结果预览: {result_preview}")

                # 验证工具结果是否包含真实数据
                has_real_data = _validate_tool_results(tool_messages)
                
                if not has_real_data:
                    logger.warning(f"💭 [社交媒体分析师] 未获取到真实数据，使用降级处理: {ticker}")
                    # 直接返回降级处理结果，不调用LLM
                    market_info = get_stock_market_info(ticker)
                    report = self._generate_fallback_report(ticker, market_info)
                    
                    return {
                        "messages": [result] + tool_messages,
                        "sentiment_report": report,
                    }
                
                # 基于工具结果生成完整分析报告
                analysis_prompt = f"""现在请基于上述工具获取的社交媒体和投资者情绪数据，生成针对股票{ticker}的个性化情绪分析报告。

🎯 分析重点：
1. **个股特异性分析**：重点分析{ticker}特有的情绪驱动因素，而非泛泛的市场情绪
2. **具体事件关联**：识别影响该股票情绪的具体新闻、公告、业绩等事件
3. **投资者行为模式**：分析该股票投资者的典型情绪反应和交易行为
4. **情绪价格影响**：量化情绪变化对{ticker}股价的历史影响程度

📊 报告结构要求：
### 一、{ticker}投资者情绪现状
- 当前情绪指数及其合理性评估
- 与同行业/大盘情绪的对比分析
- 情绪极值预警（过度乐观/悲观）

### 二、关键情绪驱动因素
- 近期影响情绪的具体事件分析
- 政策、业绩、行业变化的情绪影响
- 市场传言和预期的情绪作用

### 三、投资者结构情绪分析
- 散户vs机构的情绪差异
- 不同平台投资者的观点分歧
- 情绪传导机制和影响力分析

### 四、情绪交易策略建议
- 基于情绪周期的买卖时机
- 情绪反转信号识别
- 风险控制和仓位管理

⚠️ 避免：
- 通用的市场情绪描述
- 缺乏数据支撑的主观判断
- 与{ticker}无关的泛化分析

请确保分析内容与{ticker}高度相关，提供可操作的投资洞察。"""

                # 构建完整的消息序列
                messages = state["messages"] + [result] + tool_messages + [HumanMessage(content=analysis_prompt)]

                # 详细日志：记录发送给LLM的内容
                if debug_config.is_llm_debug_enabled():
                    logger.info("🔍 [LLM交互调试] 发送给LLM的消息序列:")
                    for i, msg in enumerate(messages):
                        if hasattr(msg, 'content'):
                            content_preview = str(msg.content)[:200] + "..." if len(str(msg.content)) > 200 else str(msg.content)
                            logger.info(f"  消息{i+1} ({type(msg).__name__}): {content_preview}")
                        elif hasattr(msg, 'tool_calls'):
                            logger.info(f"  消息{i+1} ({type(msg).__name__}): 工具调用 - {len(msg.tool_calls)}个工具")

                # 生成最终分析报告
                final_result = llm.invoke(messages)
                report = final_result.content

                # 详细日志：记录LLM返回的内容
                if debug_config.is_llm_debug_enabled():
                    logger.info(f"🔍 [LLM交互调试] LLM返回内容长度: {len(report)}")
                    logger.info(f"🔍 [LLM交互调试] LLM返回内容预览: {report[:300]}...")

                logger.info(f"💭 [社交媒体分析师] 生成完整分析报告，长度: {len(report)}")

                # 返回包含工具调用和最终分析的完整消息序列
                return {
                    "messages": [result] + tool_messages + [final_result],
                    "sentiment_report": report,
                }

            except Exception as e:
                logger.error(f"❌ [社交媒体分析师] 工具执行或分析生成失败: {e}")
                import traceback
                traceback.print_exc()

                # 降级处理：基于股票特征提供针对性分析框架
                # 根据股票代码判断市场类型和特征
                market_info = get_stock_market_info(ticker)
                
                report = f"""
## {ticker}投资者情绪分析报告

⚠️ **数据获取说明**: 实时社交媒体数据获取受限，基于{ticker}特征提供针对性分析框架。

### 📊 {ticker}情绪特征分析

**股票基本信息：**
- 市场类型：{market_info.get('market', 'A股')}
- 行业属性：{market_info.get('industry', '需进一步确认')}
- 投资者结构：{market_info.get('investor_type', '散户为主')}

**情绪敏感度评估：**
- 政策敏感度：{market_info.get('policy_sensitivity', '中等')}
- 业绩敏感度：{market_info.get('performance_sensitivity', '高')}
- 概念炒作敏感度：{market_info.get('concept_sensitivity', '中等')}

### 🎯 {ticker}专属情绪监控要点

**重点关注事件：**
1. 季度/年度业绩发布前后的情绪变化
2. 行业政策变化对该股的情绪影响
3. 同行业公司动态的连带情绪效应
4. 大股东减持/增持的情绪冲击

**情绪交易特征：**
- 散户情绪波动较大，易受短期消息影响
- 机构投资者相对理性，关注长期价值
- 技术面突破/破位时情绪放大效应明显

### 💡 基于{ticker}特征的情绪投资策略

**买入时机：**
- 负面情绪过度释放，股价超跌时
- 正面催化剂出现，情绪开始转暖时
- 行业政策利好，板块情绪提升时

**卖出时机：**
- 情绪过度乐观，估值明显偏高时
- 负面事件发酵，情绪开始恶化时
- 大盘情绪转弱，个股难以独善其身时

**风险控制：**
- 设置基于情绪极值的止损点
- 关注情绪反转的早期信号
- 避免在情绪极端时重仓操作

### 📈 后续监控建议

建议投资者持续关注以下渠道获取{ticker}的实时情绪信息：
1. 雪球平台的专业讨论和研报分享
2. 东方财富股吧的散户情绪变化
3. 财经媒体对该股的报道倾向
4. 机构研报中的投资者情绪评估

*注：本分析框架基于{ticker}的市场特征设计，建议结合实时数据进行动态调整。*
"""

                return {
                    "messages": [result],
                    "sentiment_report": report,
                }

        # 确保报告不为空
        if not report or report.strip() == "":
            # 获取股票特征信息
            market_info = get_stock_market_info(ticker)
            
            report = f"""
## {ticker}投资者情绪分析报告

### 📊 基于{ticker}特征的情绪分析

**股票特征：**
- 市场：{market_info.get('market', 'A股')}
- 预估行业：{market_info.get('industry', '需确认')}
- 主要投资者：{market_info.get('investor_type', '散户为主')}

**情绪敏感度评估：**
- 政策敏感度：{market_info.get('policy_sensitivity', '中等')}
- 业绩敏感度：{market_info.get('performance_sensitivity', '高')}
- 概念敏感度：{market_info.get('concept_sensitivity', '中等')}

### 🎯 {ticker}情绪监控重点

**关键情绪触发因素：**
1. 季度业绩发布及预期差异
2. 行业政策变化和监管动态
3. 同行业公司表现的连带效应
4. 市场热点概念的轮动影响

**投资者行为特征：**
- 散户情绪易受短期消息面影响
- 技术面突破时情绪放大效应明显
- 负面事件的情绪冲击通常被放大

### 💡 基于情绪的投资策略

**情绪买点识别：**
- 负面情绪过度释放，基本面未恶化
- 行业政策转暖，板块情绪开始修复
- 业绩超预期，正面情绪开始发酵

**情绪卖点识别：**
- 正面情绪过度乐观，估值明显偏高
- 负面事件持续发酵，情绪恶化加速
- 大盘情绪转弱，个股难以独立走强

### 📈 实用监控建议

建议重点关注以下信息源：
1. **雪球平台**：{ticker}的专业讨论和研报
2. **东方财富股吧**：散户情绪变化和热点话题
3. **财经媒体**：权威报道和分析师观点
4. **同花顺**：资金流向和投资者结构变化

*注：本分析基于{ticker}的市场特征，建议结合实时数据动态调整投资策略。*
"""

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    @staticmethod
    def _validate_tool_results(tool_messages) -> bool:
        """验证工具结果是否包含真实数据"""
        if not tool_messages:
            return False
            
        for tool_message in tool_messages:
            content = tool_message.content
            
            # 检查是否包含真实数据的标识
            real_data_indicators = [
                '总评论数',
                '数据质量',
                '真实评论',
                '成功获取数据的平台',
                '情绪分析概览'
            ]
            
            # 检查是否包含错误或回退信息
            error_indicators = [
                '数据获取失败',
                '数据获取受限',
                '系统错误',
                '无法获取实时社交媒体数据',
                '建议的替代分析方法'
            ]
            
            # 如果包含真实数据标识且不包含错误标识，认为是真实数据
            has_real_indicators = any(indicator in content for indicator in real_data_indicators)
            has_error_indicators = any(indicator in content for indicator in error_indicators)
            
            if has_real_indicators and not has_error_indicators:
                logger.info(f"💭 [数据验证] 检测到真实社交媒体数据")
                return True
                
        logger.warning(f"💭 [数据验证] 未检测到真实数据，将使用降级处理")
        return False
    
    def _generate_fallback_report(ticker: str, market_info: dict) -> str:
        """生成降级处理报告（不调用LLM）"""
        return f"""
## {ticker}投资者情绪分析报告

### ⚠️ 数据获取说明
由于网络限制或数据源暂时不可用，无法获取实时社交媒体数据。以下提供基于{ticker}特征的分析框架。

### 📊 基于{ticker}特征的情绪分析框架

**股票特征：**
- 市场：{market_info.get('market', 'A股')}
- 预估行业：{market_info.get('industry', '需确认')}
- 主要投资者：{market_info.get('investor_type', '散户为主')}

**情绪敏感度评估：**
- 政策敏感度：{market_info.get('policy_sensitivity', '中等')}
- 业绩敏感度：{market_info.get('performance_sensitivity', '高')}
- 概念敏感度：{market_info.get('concept_sensitivity', '中等')}

### 🎯 {ticker}情绪监控重点

**关键情绪触发因素：**
1. 季度业绩发布及预期差异
2. 行业政策变化和监管动态  
3. 同行业公司表现的连带效应
4. 市场热点概念的轮动影响

**投资者行为特征：**
- 散户情绪易受短期消息面影响
- 技术面突破时情绪放大效应明显
- 负面事件的情绪冲击通常被放大

### 💡 基于情绪的投资策略

**情绪买点识别：**
- 负面情绪过度释放，基本面未恶化
- 行业政策转暖，板块情绪开始修复
- 业绩超预期，正面情绪开始发酵

**情绪卖点识别：**
- 正面情绪过度乐观，估值明显偏高
- 负面事件持续发酵，情绪恶化加速
- 大盘情绪转弱，个股难以独立走强

### 📈 实用监控建议

建议重点关注以下信息源：
1. **雪球平台**：{ticker}的专业讨论和研报
2. **东方财富股吧**：散户情绪变化和热点话题
3. **财经媒体**：权威报道和分析师观点
4. **同花顺**：资金流向和投资者结构变化

*注：本分析基于{ticker}的市场特征，建议获取实时数据后进行动态调整。*
"""

    return social_media_analyst_node
