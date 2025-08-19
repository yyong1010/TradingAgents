"""
中国社交媒体真实数据源模块
提供新浪财经、东方财富等平台的真实数据获取功能
"""

from .sina_finance_api import SinaFinanceAPI
from .eastmoney_scraper import EastMoneyScraper
from .sentiment_analyzer import SentimentAnalyzer
from .real_china_social_media import RealChinaSocialMedia

__all__ = [
    'SinaFinanceAPI',
    'EastMoneyScraper', 
    'TencentFinanceAPI',
    'SentimentAnalyzer',
    'RealChinaSocialMedia'
]