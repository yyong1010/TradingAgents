"""
新闻爬虫模块
用于从指定网站爬取股票相关新闻
"""

from .news_crawler import NewsCrawler
from .news_sources import SinaNewsSource, EastmoneyNewsSource

__all__ = ['NewsCrawler', 'SinaNewsSource', 'EastmoneyNewsSource']