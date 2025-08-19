"""
新闻爬虫工具
用于新闻分析师获取股票相关新闻
"""

from langchain.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field
import logging
from tradingagents.news_crawler import NewsCrawler

logger = logging.getLogger(__name__)

class NewsCrawlerInput(BaseModel):
    """新闻爬虫工具输入"""
    stock_code: str = Field(description="股票代码，如300663")
    max_days: Optional[int] = Field(default=14, description="获取多少天内的新闻，默认14天")

class NewsCrawlerTool(BaseTool):
    """新闻爬虫工具"""
    
    name = "get_stock_news_crawler"
    description = """
    通过网页爬虫获取股票相关新闻。
    
    功能特点：
    - 从新浪财经和东方财富爬取新闻
    - 自动去重和时间过滤
    - 只获取指定天数内的新闻
    - 提供详细的数据统计
    
    使用场景：
    - 获取最新的股票新闻和公告
    - 分析市场热点和舆情
    - 评估新闻对股价的潜在影响
    
    输入参数：
    - stock_code: 股票代码（必需）
    - max_days: 获取天数，默认14天
    """
    
    args_schema: Type[BaseModel] = NewsCrawlerInput
    
    def __init__(self):
        super().__init__()
        self.crawler = NewsCrawler()
    
    def _run(self, stock_code: str, max_days: int = 14) -> str:
        """执行新闻爬取"""
        try:
            logger.info(f"🔍 [新闻爬虫工具] 开始获取股票 {stock_code} 的新闻")
            
            # 获取格式化的新闻文本
            news_text = self.crawler.get_formatted_news_text(stock_code, max_days)
            
            logger.info(f"✅ [新闻爬虫工具] 成功获取股票 {stock_code} 的新闻数据")
            
            return news_text
            
        except Exception as e:
            error_msg = f"❌ [新闻爬虫工具] 获取新闻失败: {e}"
            logger.error(error_msg)
            return error_msg
    
    async def _arun(self, stock_code: str, max_days: int = 14) -> str:
        """异步执行（暂时使用同步实现）"""
        return self._run(stock_code, max_days)