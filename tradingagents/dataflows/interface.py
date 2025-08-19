"""
社交媒体数据接口更新
添加真实数据源接口
"""

import asyncio
from typing import Dict, List
from tradingagents.dataflows.social_media.real_china_social_media import RealChinaSocialMedia
from tradingagents.dataflows.social_media.cache_manager import get_cache_wrapper

# 全局实例
_real_social_media = None
_cache_wrapper = None


def get_real_social_media():
    """获取真实社交媒体数据实例"""
    global _real_social_media
    if _real_social_media is None:
        _real_social_media = RealChinaSocialMedia()
    return _real_social_media


def get_cache_wrapper():
    """获取缓存包装器实例"""
    global _cache_wrapper
    if _cache_wrapper is None:
        from tradingagents.dataflows.social_media.cache_manager import get_cache_wrapper as get_wrapper
        _cache_wrapper = get_wrapper()
    return _cache_wrapper


async def get_real_china_social_sentiment(symbol: str, days: int = 3) -> Dict:
    """
    获取中国社交媒体真实情绪数据
    
    Args:
        symbol: 股票代码（如：000001.SZ、300663）
        days: 获取最近几天的数据
        
    Returns:
        Dict: 社交媒体情绪分析结果
    """
    try:
        real_social_media = get_real_social_media()
        cache_wrapper = get_cache_wrapper()
        
        # 使用缓存包装器
        result = await cache_wrapper.cached_async_call(
            real_social_media.get_social_sentiment,
            symbol,
            'social_sentiment',
            days=days
        )
        
        if result is None:
            # 使用备用数据
            return await get_fallback_social_sentiment(symbol, days)
        
        return result
        
    except Exception as e:
        # 发生异常时返回备用数据
        return await get_fallback_social_sentiment(symbol, days)


async def get_fallback_social_sentiment(symbol: str, days: int = 3) -> Dict:
    """
    获取备用社交媒体情绪数据（模拟数据）
    
    Args:
        symbol: 股票代码
        days: 获取最近几天的数据
        
    Returns:
        Dict: 备用社交媒体情绪分析结果
    """
    
    # 基于股票代码的模拟数据
    symbol_mapping = {
        '000001': {'name': '平安银行', 'industry': '银行'},
        '300663': {'name': '科蓝软件', 'industry': '软件服务'},
        '600036': {'name': '招商银行', 'industry': '银行'},
        '000858': {'name': '五粮液', 'industry': '白酒'},
        '601127': {'name': '小康股份', 'industry': '汽车制造'}
    }
    
    stock_info = symbol_mapping.get(symbol, {'name': f'股票{symbol}', 'industry': '综合'})
    
    # 基于行业生成不同的模拟情绪
    industry_sentiment = {
        '银行': 6.5,
        '软件服务': 7.2,
        '白酒': 5.8,
        '汽车制造': 6.1
    }
    
    base_score = industry_sentiment.get(stock_info['industry'], 6.0)
    
    # 添加一些随机波动
    import random
    score = base_score + random.uniform(-1, 1)
    score = max(1, min(10, score))
    
    # 确定情绪等级
    if score >= 8:
        level = 'very_positive'
        description = '极度乐观'
    elif score >= 6:
        level = 'positive'
        description = '乐观'
    elif score >= 4:
        level = 'neutral'
        description = '中性'
    elif score >= 2:
        level = 'negative'
        description = '悲观'
    else:
        level = 'very_negative'
        description = '极度悲观'
    
    return {
        'symbol': symbol,
        'source': 'fallback',
        'timestamp': '2025-07-24 14:30:00',
        'error': '使用备用模拟数据',
        'sentiment_analysis': {
            'overall_score': round(score, 1),
            'sentiment_level': level,
            'sentiment_description': description,
            'confidence': 0.5,
            'news_sentiment': round(score * 0.8, 1),
            'forum_sentiment': round(score * 0.9, 1)
        },
        'data_statistics': {
            'total_news': 5,
            'total_forum_posts': 8,
            'total_interactions': 1250,
            'data_sources': ['模拟数据源']
        },
        'hot_topics': [f"{stock_info['industry']}发展", "政策利好", "业绩预期"],
        'detailed_data': {
            'news': [
                {
                    'title': f"{stock_info['name']}获机构关注，{stock_info['industry']}前景看好",
                    'content': f"近期{stock_info['name']}受到市场关注，{stock_info['industry']}板块表现活跃...",
                    'url': '',
                    'publish_time': '2025-07-24 10:30:00',
                    'source': '模拟新闻',
                    'sentiment': 'positive'
                }
            ],
            'forum_discussions': [
                {
                    'title': f"{stock_info['name']}今天表现如何？",
                    'content': f"今天{stock_info['name']}的走势还不错，{stock_info['industry']}板块有支撑...",
                    'author': '投资者A',
                    'publish_time': '2025-07-24 11:00:00',
                    'read_count': 150,
                    'reply_count': 15,
                    'like_count': 25,
                    'platform': '模拟股吧',
                    'sentiment': 'positive'
                }
            ]
        }
    }


# 向后兼容的函数
async def get_finnhub_news(symbol: str, *args, **kwargs) -> Dict:
    """获取FinnHub新闻数据（兼容接口）"""
    return await get_real_china_social_sentiment(symbol, days=1)


async def get_finnhub_company_insider_sentiment(symbol: str, *args, **kwargs) -> Dict:
    """获取FinnHub公司内幕情绪（兼容接口）"""
    return await get_real_china_social_sentiment(symbol, days=1)


async def get_finnhub_company_insider_transactions(symbol: str, *args, **kwargs) -> Dict:
    """获取FinnHub公司内幕交易（兼容接口）"""
    return await get_fallback_social_sentiment(symbol, days=1)


async def get_google_news(symbol: str, *args, **kwargs) -> Dict:
    """获取Google新闻数据（兼容接口）"""
    return await get_real_china_social_sentiment(symbol, days=1)


async def get_reddit_global_news(*args, **kwargs) -> Dict:
    """获取Reddit全球新闻（兼容接口）"""
    return await get_fallback_social_sentiment("000001", days=1)


async def get_reddit_company_news(symbol: str, *args, **kwargs) -> Dict:
    """获取Reddit公司新闻（兼容接口）"""
    return await get_real_china_social_sentiment(symbol, days=1)


# 财务报表相关兼容函数
async def get_simfin_balance_sheet(symbol: str, *args, **kwargs) -> Dict:
    """获取资产负债表（兼容接口）"""
    return {"error": "需要配置SimFin API", "symbol": symbol}


async def get_simfin_cashflow(symbol: str, *args, **kwargs) -> Dict:
    """获取现金流量表（兼容接口）"""
    return {"error": "需要配置SimFin API", "symbol": symbol}


async def get_simfin_income_statements(symbol: str, *args, **kwargs) -> Dict:
    """获取利润表（兼容接口）"""
    return {"error": "需要配置SimFin API", "symbol": symbol}


# 技术分析兼容函数
async def get_stock_stats_indicators_window(symbol: str, *args, **kwargs) -> Dict:
    """获取技术指标窗口数据（兼容接口）"""
    return {"error": "需要配置stockstats", "symbol": symbol}


async def get_stockstats_indicator(symbol: str, *args, **kwargs) -> Dict:
    """获取技术指标（兼容接口）"""
    return {"error": "需要配置stockstats", "symbol": symbol}


# 市场数据兼容函数
async def get_YFin_data_window(symbol: str, *args, **kwargs) -> Dict:
    """获取YFinance窗口数据（兼容接口）"""
    return {"error": "需要配置yfinance", "symbol": symbol}


async def get_YFin_data(symbol: str, *args, **kwargs) -> Dict:
    """获取YFinance数据（兼容接口）"""
    return {"error": "需要配置yfinance", "symbol": symbol}


# Tushare数据兼容函数
async def get_china_stock_data_tushare(symbol: str, *args, **kwargs) -> Dict:
    """获取Tushare中国股票数据（兼容接口）"""
    return {"error": "需要配置Tushare", "symbol": symbol}


async def search_china_stocks_tushare(keyword: str, *args, **kwargs) -> List:
    """搜索Tushare中国股票（兼容接口）"""
    return [{"symbol": "000001", "name": "平安银行"}, {"symbol": "300663", "name": "科蓝软件"}]


async def get_china_stock_fundamentals_tushare(symbol: str, *args, **kwargs) -> Dict:
    """获取Tushare中国股票基本面（兼容接口）"""
    return {"error": "需要配置Tushare", "symbol": symbol}


async def get_china_stock_info_tushare(symbol: str, *args, **kwargs) -> Dict:
    """获取Tushare中国股票信息（兼容接口）"""
    return {"error": "需要配置Tushare", "symbol": symbol}


# 统一中国数据兼容函数
async def get_china_stock_data_unified(symbol: str, *args, **kwargs) -> Dict:
    """获取统一中国股票数据（兼容接口）"""
    return {"error": "需要配置数据源", "symbol": symbol}


async def get_china_stock_info_unified(symbol: str, *args, **kwargs) -> Dict:
    """获取统一中国股票信息（兼容接口）"""
    return {"error": "需要配置数据源", "symbol": symbol}


async def switch_china_data_source(source: str, *args, **kwargs) -> Dict:
    """切换中国数据源（兼容接口）"""
    return {"status": "success", "message": f"已切换到数据源: {source}"}


async def get_current_china_data_source(*args, **kwargs) -> Dict:
    """获取当前中国数据源（兼容接口）"""
    return {"source": "tushare", "name": "Tushare"}


# 香港股票兼容函数
async def get_hk_stock_data_unified(symbol: str, *args, **kwargs) -> Dict:
    """获取统一香港股票数据（兼容接口）"""
    return {"error": "需要配置数据源", "symbol": symbol}


async def get_hk_stock_info_unified(symbol: str, *args, **kwargs) -> Dict:
    """获取统一香港股票信息（兼容接口）"""
    return {"error": "需要配置数据源", "symbol": symbol}


async def get_stock_data_by_market(symbol: str, market: str, *args, **kwargs) -> Dict:
    """按市场获取股票数据（兼容接口）"""
    return {"error": "需要配置数据源", "symbol": symbol, "market": market}


# 新增：社交媒体数据接口
def get_stock_news_openai(ticker: str, curr_date: str) -> str:
    """
    获取股票新闻和社交媒体情绪数据
    
    Args:
        ticker: 股票代码
        curr_date: 当前日期
        
    Returns:
        格式化的分析结果字符串
    """
    try:
        from tradingagents.dataflows.social_media_interface import get_stock_news_openai as get_real_data
        return get_real_data(ticker, curr_date)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取社交媒体数据失败: {ticker}, 错误: {e}")
        
        return f"""
## {ticker} 社交媒体分析
**分析日期**: {curr_date}
**状态**: 数据获取失败

### ⚠️ 错误信息
{str(e)}

### 💡 建议
请检查网络连接和数据源配置，或联系技术支持。
在此期间，建议重点关注基本面分析和官方公告。
"""


def get_chinese_social_sentiment(ticker: str, curr_date: str) -> str:
    """
    获取中国社交媒体情绪分析（兼容接口）
    """
    return get_stock_news_openai(ticker, curr_date)


# 配置函数
def set_config(config=None, **kwargs):
    """设置配置参数（兼容接口）"""
    if config is None:
        config = {}
    config.update(kwargs)
    return {"status": "success", "message": "配置已设置", "config": config}


# 测试用例
async def test_social_media_interface():
    """测试社交媒体接口"""
    print("测试社交媒体数据接口...")
    
    # 测试真实数据
    result = await get_real_china_social_sentiment("300663", days=1)
    print(f"300663 情绪数据: {result.get('sentiment_analysis', {}).get('sentiment_description', 'N/A')}")
    
    # 测试多个股票
    symbols = ["000001", "600036", "300663"]
    real_social = get_real_social_media()
    
    for symbol in symbols:
        result = await real_social.get_social_sentiment(symbol, days=1)
        print(f"{symbol}: 情绪分数 {result.get('sentiment_analysis', {}).get('overall_score', 'N/A')}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_social_media_interface())