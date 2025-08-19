from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json

# 导入统一日志系统和分析模块日志装饰器
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_analyst_module
from tradingagents.utils.llm_debug import log_llm_messages, log_llm_response
logger = get_logger("analysts.news")


def create_news_analyst(llm, toolkit):
    @log_analyst_module("news")
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 使用新的网页爬虫工具获取新闻
        tools = [
            toolkit.get_stock_news_crawler,  # 主要工具：网页爬虫获取新闻
        ]
        
        # 如果启用在线工具，添加备用工具
        if toolkit.config.get("online_tools", False):
            tools.extend([
                toolkit.get_realtime_stock_news,  # 备用：实时新闻API
                toolkit.get_global_news_openai,   # 备用：全球新闻
            ])

        system_message = (
            """您是一位专业的财经新闻分析师，专门分析中国股市的新闻事件对股票价格的潜在影响。

您的主要职责包括：
1. 使用网页爬虫工具获取股票相关的最新新闻和公告
2. 分析新闻事件的重要程度和市场影响
3. 评估新闻对股价的短期和中期影响
4. 识别可能影响投资决策的关键信息
5. 提供基于新闻分析的投资建议

🔍 数据获取策略：
- 优先使用 get_stock_news_crawler 工具获取新闻
- 该工具从新浪财经、东方财富等权威网站爬取数据
- 自动过滤2周内的新闻，确保时效性
- 提供详细的数据来源和统计信息

📊 重点关注的新闻类型：
- 公司公告和重大事项
- 财报发布和业绩预告
- 重大合作和并购消息
- 政策变化和监管动态
- 行业趋势和技术突破
- 管理层变动和战略调整
- 市场传言和投资者情绪

📈 分析要点：
- 新闻的时效性（发布时间和相关性）
- 新闻的可信度（来源权威性：新浪财经、东方财富等）
- 市场影响程度（对股价的潜在影响）
- 投资者情绪变化（正面/负面/中性）
- 与历史类似事件的对比分析

📊 价格影响分析要求：
- 评估新闻对股价的短期影响（1-3天）
- 分析可能的价格波动幅度（百分比）
- 提供基于新闻的价格调整建议
- 识别关键价格支撑位和阻力位
- 评估新闻对长期投资价值的影响

⚠️ 重要说明：
- 如果爬虫工具未获取到有效新闻，直接说明"未找到相关新闻"，不要使用模拟数据
- 优先分析最新的、高相关性的新闻事件
- 必须基于实际获取的新闻数据进行分析
- 提供新闻对股价影响的量化评估和具体建议

📝 报告格式要求：
1. 首先使用 get_stock_news_crawler 工具获取新闻数据
2. 如果获取到新闻，按重要性排序分析
3. 如果未获取到新闻，明确说明并结束分析
4. 在报告末尾附上Markdown表格总结关键发现

请撰写详细的中文分析报告。"""
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
                    "供您参考，当前日期是{current_date}。我们正在查看公司{ticker}。请用中文撰写所有分析内容。",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)
        
        # 调试日志：记录发送给LLM的内容
        logger.info("🔍 [新闻分析师] 准备调用LLM")
        log_llm_messages("新闻分析师", state["messages"])
        
        result = chain.invoke(state["messages"])
        
        # 调试日志：记录LLM返回的内容
        logger.info("🔍 [新闻分析师] LLM调用完成")
        log_llm_response("新闻分析师", result)

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
