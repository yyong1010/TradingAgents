"""
数据源配置模块
"""

from .sina_finance import SinaFinanceScraper
from .eastmoney import EastMoneyScraper

__all__ = [
    'SinaFinanceScraper',
    'EastMoneyScraper'
]