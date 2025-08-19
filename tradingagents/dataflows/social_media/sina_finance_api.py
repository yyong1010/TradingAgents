"""
新浪财经RSS接口
提供财经新闻和股票相关报道的RSS数据获取功能
"""

import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from urllib.parse import quote
import time
import random

logger = logging.getLogger(__name__)


class SinaFinanceAPI:
    """新浪财经API接口"""
    
    def __init__(self, request_delay: float = 2.0):
        self.base_url = "https://feed.sina.com.cn/api/news/rss"
        self.stock_news_url = "https://feed.sina.com.cn/api/roll/news"
        self.request_delay = request_delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/xml, application/rss+xml, text/xml',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        
    async def get_stock_news(self, symbol: str, days: int = 7) -> List[Dict]:
        """
        获取股票相关新闻
        
        Args:
            symbol: 股票代码（如：000001.SZ 或 000001）
            days: 获取最近几天的数据
            
        Returns:
            List[Dict]: 新闻列表
        """
        try:
            # 标准化股票代码
            stock_code = self._normalize_symbol(symbol)
            
            # 构建搜索关键词
            keywords = [
                stock_code,
                self._get_stock_name(symbol),
                f"股票{stock_code}"
            ]
            
            all_news = []
            
            # 并行获取不同类型的新闻
            tasks = [
                self._fetch_rss_news(keywords[0]),
                self._fetch_search_news(keywords[1]),
                self._fetch_market_news(stock_code)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"新浪财经API获取数据异常: {result}")
            
            # 去重和排序
            unique_news = self._deduplicate_news(all_news)
            sorted_news = sorted(unique_news, key=lambda x: x['publish_time'], reverse=True)
            
            # 限制返回数量
            return sorted_news[:50]
            
        except Exception as e:
            logger.error(f"获取新浪财经数据失败: {e}")
            return []
    
    async def _fetch_rss_news(self, keyword: str) -> List[Dict]:
        """获取RSS新闻"""
        try:
            async with aiohttp.ClientSession() as session:
                # 构建RSS URL
                rss_url = f"{self.base_url}?cate=stock&keyword={quote(keyword)}"
                
                await asyncio.sleep(random.uniform(1, self.request_delay))
                
                async with session.get(rss_url, headers=self.headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        return self._parse_rss(content)
                    else:
                        logger.warning(f"新浪财经RSS请求失败: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"获取新浪财经RSS失败: {e}")
            return []
    
    async def _fetch_search_news(self, keyword: str) -> List[Dict]:
        """获取搜索新闻"""
        try:
            search_url = f"https://feed.sina.com.cn/api/roll/all"
            params = {
                'pageid': '153',
                'lid': '2516',
                'k': keyword,
                'num': '20',
                'page': '1'
            }
            
            async with aiohttp.ClientSession() as session:
                await asyncio.sleep(random.uniform(1, self.request_delay))
                
                async with session.get(search_url, params=params, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_search_result(data, keyword)
                    else:
                        logger.warning(f"新浪财经搜索请求失败: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"获取新浪财经搜索数据失败: {e}")
            return []
    
    async def _fetch_market_news(self, stock_code: str) -> List[Dict]:
        """获取市场新闻"""
        try:
            market_url = f"https://feed.sina.com.cn/api/roll/finance"
            params = {
                'pageid': '153',
                'lid': '2517',
                'num': '20',
                'page': '1'
            }
            
            async with aiohttp.ClientSession() as session:
                await asyncio.sleep(random.uniform(1, self.request_delay))
                
                async with session.get(market_url, params=params, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._filter_stock_news(data, stock_code)
                    else:
                        logger.warning(f"新浪财经市场新闻请求失败: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"获取新浪财经市场新闻失败: {e}")
            return []
    
    def _parse_rss(self, rss_content: str) -> List[Dict]:
        """解析RSS内容"""
        try:
            root = ET.fromstring(rss_content)
            news_list = []
            
            # 处理命名空间
            namespaces = {
                'content': 'http://purl.org/rss/1.0/modules/content/',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }
            
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                description = item.find('description').text if item.find('description') is not None else ''
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
                
                if title and link:
                    news_list.append({
                        'title': title,
                        'content': description,
                        'url': link,
                        'publish_time': self._parse_time(pub_date),
                        'source': '新浪财经',
                        'sentiment': self._analyze_sentiment(title + ' ' + description)
                    })
            
            return news_list
            
        except Exception as e:
            logger.error(f"解析RSS内容失败: {e}")
            return []
    
    def _parse_search_result(self, data: Dict, keyword: str) -> List[Dict]:
        """解析搜索结果"""
        news_list = []
        try:
            if 'result' in data and 'data' in data['result']:
                for item in data['result']['data']:
                    title = item.get('title', '')
                    content = item.get('summary', '')
                    url = item.get('url', '')
                    time_str = item.get('ctime', '')
                    
                    if keyword in title or keyword in content:
                        news_list.append({
                            'title': title,
                            'content': content,
                            'url': url,
                            'publish_time': self._parse_time(time_str),
                            'source': '新浪财经',
                            'sentiment': self._analyze_sentiment(title + ' ' + content)
                        })
        except Exception as e:
            logger.error(f"解析搜索结果失败: {e}")
        
        return news_list
    
    def _filter_stock_news(self, data: Dict, stock_code: str) -> List[Dict]:
        """过滤股票相关新闻"""
        news_list = []
        try:
            if 'result' in data and 'data' in data['result']:
                for item in data['result']['data']:
                    title = item.get('title', '')
                    content = item.get('summary', '')
                    url = item.get('url', '')
                    time_str = item.get('ctime', '')
                    
                    # 检查是否包含股票代码或相关关键词
                    keywords = [stock_code, self._get_stock_name(stock_code), '股票']
                    if any(keyword in title or keyword in content for keyword in keywords):
                        news_list.append({
                            'title': title,
                            'content': content,
                            'url': url,
                            'publish_time': self._parse_time(time_str),
                            'source': '新浪财经',
                            'sentiment': self._analyze_sentiment(title + ' ' + content)
                        })
        except Exception as e:
            logger.error(f"过滤股票新闻失败: {e}")
        
        return news_list
    
    def _analyze_sentiment(self, text: str) -> str:
        """简单的情绪分析"""
        positive_words = ['上涨', '增长', '利好', '看好', '买入', '推荐', '强势', '突破', '创新高', '涨停']
        negative_words = ['下跌', '下降', '利空', '看空', '卖出', '风险', '跌破', '创新低', '跌停', '亏损']
        
        text = text.lower()
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def _parse_time(self, time_str: str) -> str:
        """解析时间字符串"""
        try:
            if not time_str:
                return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 处理不同格式的时间字符串
            time_str = time_str.strip()
            
            # RSS格式
            if 'GMT' in time_str or 'UTC' in time_str:
                dt = datetime.strptime(time_str, '%a, %d %b %Y %H:%M:%S %Z')
            elif len(time_str) == 10 and time_str.isdigit():
                # Unix时间戳
                dt = datetime.fromtimestamp(int(time_str))
            else:
                # 其他格式，尝试多种解析方式
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d',
                    '%Y/%m/%d %H:%M:%S',
                    '%Y年%m月%d日 %H:%M'
                ]
                for fmt in formats:
                    try:
                        dt = datetime.strptime(time_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    dt = datetime.now()
            
            return dt.strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception as e:
            logger.warning(f"解析时间失败: {time_str}, 错误: {e}")
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码"""
        symbol = str(symbol).strip()
        
        # 移除可能的后缀
        symbol = symbol.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
        
        # 补齐6位数字
        if symbol.isdigit() and len(symbol) < 6:
            symbol = symbol.zfill(6)
        
        return symbol
    
    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称（简化版，实际应该查询数据库）"""
        # 这里简化处理，实际应该查询股票名称
        stock_names = {
            '000001': '平安银行',
            '000858': '五粮液',
            '600036': '招商银行',
            '300663': '科蓝软件',
            '601127': '小康股份'
        }
        return stock_names.get(self._normalize_symbol(symbol), f'股票{symbol}')
    
    def _deduplicate_news(self, news_list: List[Dict]) -> List[Dict]:
        """去重新闻"""
        seen = set()
        unique_news = []
        
        for news in news_list:
            key = f"{news['title']}_{news['url']}"
            if key not in seen:
                seen.add(key)
                unique_news.append(news)
        
        return unique_news


# 测试用例
async def test_sina_finance():
    """测试新浪财经API"""
    api = SinaFinanceAPI()
    news = await api.get_stock_news("300663", days=3)
    
    print(f"获取到 {len(news)} 条新闻")
    for item in news[:3]:
        print(f"标题: {item['title']}")
        print(f"情绪: {item['sentiment']}")
        print(f"来源: {item['source']}")
        print(f"时间: {item['publish_time']}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(test_sina_finance())