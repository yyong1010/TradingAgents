"""
东方财富网网页爬取
获取股吧讨论、投资者情绪等真实数据
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import re
import time
import random
from datetime import datetime
from typing import List, Dict, Optional
import logging
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class EastMoneyScraper:
    """东方财富网数据爬取器"""
    
    def __init__(self, request_delay: float = 3.0, max_retries: int = 3):
        self.base_url = "https://guba.eastmoney.com"
        self.list_url = "https://guba.eastmoney.com/list"
        self.post_url = "https://guba.eastmoney.com/news"
        self.request_delay = request_delay
        self.max_retries = max_retries
        
        self.headers = [
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
        ]
        
    async def get_forum_discussions(self, symbol: str, days: int = 3, max_posts: int = 20) -> List[Dict]:
        """
        获取股吧讨论数据
        
        Args:
            symbol: 股票代码
            days: 获取最近几天的数据
            max_posts: 最大帖子数量
            
        Returns:
            List[Dict]: 讨论数据列表
        """
        try:
            stock_code = self._normalize_symbol(symbol)
            
            # 获取股吧帖子列表
            posts = await self._get_post_list(stock_code, max_posts)
            
            # 获取帖子详情
            detailed_posts = []
            for post in posts[:max_posts]:
                detailed = await self._get_post_detail(post)
                if detailed:
                    detailed_posts.append(detailed)
                
                await asyncio.sleep(random.uniform(1, self.request_delay))
            
            # 过滤最近几天的数据
            filtered_posts = self._filter_by_date(detailed_posts, days)
            
            return filtered_posts
            
        except Exception as e:
            logger.error(f"获取东方财富股吧数据失败: {e}")
            return []
    
    async def _get_post_list(self, stock_code: str, max_posts: int) -> List[Dict]:
        """获取帖子列表"""
        posts = []
        
        try:
            # 构建股吧列表URL
            list_url = f"{self.list_url},{stock_code},f_1.html"
            
            # 尝试获取多个页面
            for page in range(1, min(4, max_posts // 10 + 1)):
                page_url = f"{self.list_url},{stock_code},f_{page}.html"
                
                page_posts = await self._fetch_page_posts(page_url)
                posts.extend(page_posts)
                
                if len(posts) >= max_posts:
                    break
                    
                await asyncio.sleep(random.uniform(1, self.request_delay))
            
            return posts[:max_posts]
            
        except Exception as e:
            logger.error(f"获取帖子列表失败: {e}")
            return []
    
    async def _fetch_page_posts(self, url: str) -> List[Dict]:
        """获取单页帖子"""
        try:
            headers = random.choice(self.headers)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._parse_post_list(html)
                    else:
                        logger.warning(f"东方财富请求失败: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"获取页面数据失败: {e}")
            return []
    
    def _parse_post_list(self, html: str) -> List[Dict]:
        """解析帖子列表"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            posts = []
            
            # 查找帖子列表
            article_list = soup.find('div', {'class': 'articleh normal_post'})
            if not article_list:
                article_list = soup.find_all('div', {'class': ['articleh', 'normal_post']})
            
            if isinstance(article_list, list):
                post_elements = article_list
            else:
                post_elements = soup.find_all('div', {'class': ['articleh', 'normal_post']})
            
            for post in post_elements[:20]:  # 限制数量
                try:
                    # 提取帖子信息
                    title_elem = post.find('span', {'class': 'l3'})
                    if not title_elem:
                        title_elem = post.find('a', {'class': 'l3'})
                    
                    if title_elem and title_elem.find('a'):
                        title_link = title_elem.find('a')
                        title = title_link.get_text(strip=True)
                        post_url = title_link.get('href', '')
                        
                        # 提取阅读数和回复数
                        read_count = 0
                        reply_count = 0
                        
                        read_elem = post.find('span', {'class': 'l1'})
                        if read_elem:
                            read_text = read_elem.get_text(strip=True)
                            read_count = self._extract_number(read_text)
                        
                        reply_elem = post.find('span', {'class': 'l2'})
                        if reply_elem:
                            reply_text = reply_elem.get_text(strip=True)
                            reply_count = self._extract_number(reply_text)
                        
                        # 提取作者和时间
                        author_elem = post.find('span', {'class': 'l4'})
                        author = author_elem.get_text(strip=True) if author_elem else '匿名用户'
                        
                        time_elem = post.find('span', {'class': 'l5'})
                        publish_time = time_elem.get_text(strip=True) if time_elem else ''
                        
                        # 构建完整URL
                        if post_url and not post_url.startswith('http'):
                            post_url = urljoin(self.base_url, post_url)
                        
                        posts.append({
                            'title': title,
                            'url': post_url,
                            'author': author,
                            'read_count': read_count,
                            'reply_count': reply_count,
                            'publish_time': self._parse_time(publish_time),
                            'platform': '东方财富股吧'
                        })
                        
                except Exception as e:
                    logger.warning(f"解析单个帖子失败: {e}")
                    continue
            
            return posts
            
        except Exception as e:
            logger.error(f"解析帖子列表失败: {e}")
            return []
    
    async def _get_post_detail(self, post: Dict) -> Optional[Dict]:
        """获取帖子详情"""
        try:
            if not post.get('url'):
                return None
            
            headers = random.choice(self.headers)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(post['url'], headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._parse_post_detail(html, post)
                    else:
                        logger.warning(f"获取帖子详情失败: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"获取帖子详情失败: {e}")
            return None
    
    def _parse_post_detail(self, html: str, post_info: Dict) -> Optional[Dict]:
        """解析帖子详情"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 提取帖子内容
            content_div = soup.find('div', {'class': 'stockcodec'})
            if not content_div:
                content_div = soup.find('div', {'id': 'zwcontentmain'})
            
            content = ''
            if content_div:
                content = content_div.get_text(strip=True)
            
            # 提取点赞数
            like_count = 0
            like_elem = soup.find('span', {'class': 'like-num'})
            if like_elem:
                like_text = like_elem.get_text(strip=True)
                like_count = self._extract_number(like_text)
            
            # 提取发布者信息
            author_info = soup.find('div', {'class': 'zwfbtime'})
            if author_info:
                author_text = author_info.get_text(strip=True)
                # 提取时间
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', author_text)
                if time_match:
                    post_info['publish_time'] = time_match.group(1)
            
            # 情绪分析
            sentiment = self._analyze_sentiment(post_info['title'] + ' ' + content)
            
            return {
                'title': post_info['title'],
                'content': content,
                'author': post_info['author'],
                'publish_time': post_info['publish_time'],
                'read_count': post_info['read_count'],
                'reply_count': post_info['reply_count'],
                'like_count': like_count,
                'platform': '东方财富股吧',
                'sentiment': sentiment,
                'url': post_info['url']
            }
            
        except Exception as e:
            logger.error(f"解析帖子详情失败: {e}")
            return None
    
    def _analyze_sentiment(self, text: str) -> str:
        """简单的情绪分析"""
        positive_words = ['上涨', '增长', '利好', '看好', '买入', '推荐', '强势', '突破', '涨停', '盈利', '赚钱', '机会']
        negative_words = ['下跌', '下降', '利空', '看空', '卖出', '风险', '跌破', '跌停', '亏损', '亏钱', '风险', '危险']
        
        text = text.lower()
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def _extract_number(self, text: str) -> int:
        """提取数字"""
        try:
            numbers = re.findall(r'\d+', text)
            return int(numbers[0]) if numbers else 0
        except:
            return 0
    
    def _parse_time(self, time_str: str) -> str:
        """解析时间"""
        try:
            if not time_str:
                return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 处理不同格式的时间
            time_str = time_str.strip()
            
            # 处理相对时间
            if '分钟前' in time_str:
                minutes = int(re.findall(r'(\d+)', time_str)[0])
                dt = datetime.now() - timedelta(minutes=minutes)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            elif '小时前' in time_str:
                hours = int(re.findall(r'(\d+)', time_str)[0])
                dt = datetime.now() - timedelta(hours=hours)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            elif '天前' in time_str:
                days = int(re.findall(r'(\d+)', time_str)[0])
                dt = datetime.now() - timedelta(days=days)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # 处理标准时间格式
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d',
                    '%Y/%m/%d %H:%M:%S',
                    '%m-%d %H:%M'
                ]
                for fmt in formats:
                    try:
                        dt = datetime.strptime(time_str, fmt)
                        if dt.year == 1900:  # 没有年份的情况
                            dt = dt.replace(year=datetime.now().year)
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        continue
                
                return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
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
    
    def _filter_by_date(self, posts: List[Dict], days: int) -> List[Dict]:
        """按日期过滤"""
        if not posts:
            return []
        
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_posts = []
        
        for post in posts:
            try:
                post_time = datetime.strptime(post['publish_time'], '%Y-%m-%d %H:%M:%S')
                if post_time >= cutoff_date:
                    filtered_posts.append(post)
            except:
                # 如果时间解析失败，保留帖子
                filtered_posts.append(post)
        
        return filtered_posts


# 测试用例
async def test_eastmoney_scraper():
    """测试东方财富爬取"""
    scraper = EastMoneyScraper()
    discussions = await scraper.get_forum_discussions("300663", days=1, max_posts=10)
    
    print(f"获取到 {len(discussions)} 条讨论")
    for discussion in discussions[:3]:
        print(f"标题: {discussion['title']}")
        print(f"内容: {discussion['content'][:100]}...")
        print(f"作者: {discussion['author']}")
        print(f"阅读: {discussion['read_count']}, 回复: {discussion['reply_count']}, 点赞: {discussion.get('like_count', 0)}")
        print(f"情绪: {discussion['sentiment']}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(test_eastmoney_scraper())