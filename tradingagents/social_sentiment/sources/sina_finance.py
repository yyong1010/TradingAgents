"""
新浪财经数据源
获取新浪财经股票评论和讨论数据
"""

import re
import json
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class SinaFinanceScraper:
    """新浪财经爬虫"""
    
    def __init__(self, scraper):
        self.scraper = scraper
        self.base_url = "https://finance.sina.com.cn"
        
    def get_stock_comments(self, stock_code: str, limit: int = 50) -> List[Dict]:
        """
        获取股票评论
        
        Args:
            stock_code: 股票代码 (如: 300663)
            limit: 获取评论数量限制
            
        Returns:
            评论列表
        """
        comments = []
        
        try:
            # 使用正确的新浪股吧URL格式
            if stock_code.startswith('6'):
                market_code = f'sh{stock_code}'
            else:
                market_code = f'sz{stock_code}'
                
            # 正确的新浪股吧URL
            guba_url = f"https://guba.sina.com.cn/?s=bar&name={market_code}"
            
            # 获取股吧页面
            html_content = self.scraper.get_page(guba_url)
            if not html_content:
                logger.warning(f"无法获取新浪股吧页面: {stock_code}")
                return comments
                
            # 解析页面提取评论
            soup = BeautifulSoup(html_content, 'html.parser')
            comments = self._extract_guba_comments(soup, stock_code, limit)
                
        except Exception as e:
            logger.error(f"获取新浪股吧评论失败: {stock_code}, 错误: {e}")
            
        logger.info(f"新浪股吧获取到 {len(comments)} 条评论: {stock_code}")
        return comments[:limit]
    
    def _get_comments_from_api(self, api_url: str, stock_code: str, limit: int) -> List[Dict]:
        """从API获取评论"""
        comments = []
        
        try:
            # 构建API请求参数
            params = {
                'symbol': stock_code,
                'page': 1,
                'size': min(limit, 100)
            }
            
            # 设置API请求头
            api_headers = {
                'Referer': f"{self.base_url}/realstock/company/sz{stock_code}/nc.shtml",
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            # 获取评论数据
            json_data = self.scraper.get_json(api_url, params=params, custom_headers=api_headers)
            
            if json_data and 'data' in json_data:
                for item in json_data['data']:
                    comment = self._parse_comment_item(item, 'sina_finance')
                    if comment:
                        comments.append(comment)
                        
        except Exception as e:
            logger.warning(f"API获取评论失败: {api_url}, 错误: {e}")
            
        return comments
    
    def _extract_guba_comments(self, soup: BeautifulSoup, stock_code: str, limit: int) -> List[Dict]:
        """从新浪股吧页面提取评论"""
        comments = []
        
        try:
            # 查找帖子列表区域
            post_list = soup.find('div', class_=re.compile(r'list|thread|post'))
            if not post_list:
                # 尝试其他可能的选择器
                post_list = soup.find('table', class_=re.compile(r'list|thread'))
                if not post_list:
                    logger.warning(f"未找到新浪股吧帖子列表: {stock_code}")
                    return comments
            
            # 查找帖子项
            post_items = post_list.find_all(['tr', 'div', 'li'], class_=re.compile(r'item|row|post|thread'))
            
            for item in post_items[:limit]:
                # 提取帖子标题作为内容
                title_elem = item.find(['a', 'span'], class_=re.compile(r'title|subject'))
                if not title_elem:
                    title_elem = item.find('a', href=re.compile(r'/news/'))
                
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                
                # 提取作者
                author_elem = item.find(['a', 'span'], class_=re.compile(r'author|user|name'))
                author = author_elem.get_text(strip=True) if author_elem else "新浪用户"
                
                # 提取时间
                time_elem = item.find(['span', 'td'], class_=re.compile(r'time|date|update'))
                timestamp = time_elem.get_text(strip=True) if time_elem else ""
                
                # 过滤时间：只保留最近3天的内容
                if not self._is_recent_post(timestamp):
                    continue
                
                # 提取回复数
                reply_elem = item.find(['span', 'td'], class_=re.compile(r'reply|comment'))
                replies = 0
                if reply_elem:
                    reply_text = reply_elem.get_text(strip=True)
                    reply_match = re.search(r'\d+', reply_text)
                    if reply_match:
                        replies = int(reply_match.group())
                
                # 提取阅读数
                read_elem = item.find(['span', 'td'], class_=re.compile(r'read|view'))
                reads = 0
                if read_elem:
                    read_text = read_elem.get_text(strip=True)
                    read_match = re.search(r'\d+', read_text)
                    if read_match:
                        reads = int(read_match.group())
                
                comment = {
                    'content': title,
                    'author': author,
                    'timestamp': timestamp,
                    'likes': reads // 10,  # 用阅读数的1/10作为点赞数估算
                    'replies': replies,
                    'source': 'sina_guba'
                }
                
                comments.append(comment)
                
        except Exception as e:
            logger.warning(f"新浪股吧评论提取失败: {stock_code}, 错误: {e}")
            
        return comments
    
    def _is_recent_post(self, timestamp: str) -> bool:
        """判断帖子是否为最近3天内的"""
        if not timestamp:
            return True  # 如果没有时间信息，默认保留
            
        try:
            from datetime import datetime, timedelta
            import re
            
            # 提取时间信息
            now = datetime.now()
            
            # 处理各种时间格式
            if '分钟前' in timestamp or '小时前' in timestamp or '刚刚' in timestamp:
                return True
            elif '天前' in timestamp:
                days_match = re.search(r'(\d+)天前', timestamp)
                if days_match:
                    days = int(days_match.group(1))
                    return days <= 3
            elif re.match(r'\d{2}-\d{2}', timestamp):  # MM-DD格式
                try:
                    # 假设是今年的日期
                    month_day = timestamp.split(' ')[0]
                    post_date = datetime.strptime(f"{now.year}-{month_day}", "%Y-%m-%d")
                    
                    # 如果日期在未来，说明是去年的
                    if post_date > now:
                        post_date = post_date.replace(year=now.year - 1)
                    
                    return (now - post_date).days <= 3
                except:
                    return True
            elif re.match(r'\d{4}-\d{2}-\d{2}', timestamp):  # YYYY-MM-DD格式
                try:
                    post_date = datetime.strptime(timestamp.split(' ')[0], "%Y-%m-%d")
                    return (now - post_date).days <= 3
                except:
                    return True
            
            return True  # 无法解析的时间格式，默认保留
            
        except Exception as e:
            logger.debug(f"时间解析失败: {timestamp}, 错误: {e}")
            return True
    
    def _parse_comment_item(self, item: Dict, source: str) -> Optional[Dict]:
        """解析评论项"""
        try:
            content = item.get('content', '').strip()
            if not content:
                return None
                
            return {
                'content': content,
                'author': item.get('author', '匿名用户'),
                'timestamp': item.get('time', ''),
                'likes': item.get('like_count', 0),
                'replies': item.get('reply_count', 0),
                'source': source
            }
            
        except Exception as e:
            logger.warning(f"解析评论项失败: {e}")
            return None
    
    def get_stock_news_sentiment(self, stock_code: str, limit: int = 20) -> List[Dict]:
        """
        获取股票新闻相关的评论情绪
        
        Args:
            stock_code: 股票代码
            limit: 新闻数量限制
            
        Returns:
            新闻评论列表
        """
        news_comments = []
        
        try:
            # 构建新闻搜索URL
            search_url = f"{self.base_url}/search"
            params = {
                'q': stock_code,
                'range': 'title',
                'c': 'news',
                'sort': 'time'
            }
            
            # 获取新闻搜索结果
            html_content = self.scraper.get_page(search_url, params=params)
            if not html_content:
                return news_comments
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找新闻链接
            news_links = soup.find_all('a', href=re.compile(r'/news/'))[:limit]
            
            for link in news_links:
                from urllib.parse import urljoin
                news_url = urljoin(self.base_url, link.get('href'))
                
                # 获取新闻页面评论
                news_page_comments = self._get_news_page_comments(news_url, stock_code)
                news_comments.extend(news_page_comments)
                
        except Exception as e:
            logger.error(f"获取新闻评论失败: {stock_code}, 错误: {e}")
            
        return news_comments
    
    def _get_news_page_comments(self, news_url: str, stock_code: str) -> List[Dict]:
        """获取新闻页面评论"""
        comments = []
        
        try:
            html_content = self.scraper.get_page(news_url)
            if not html_content:
                return comments
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找评论区域
            comment_section = soup.find('div', class_=re.compile(r'comment'))
            if not comment_section:
                return comments
                
            # 提取评论
            comment_items = comment_section.find_all('div', class_=re.compile(r'item|comment'))
            
            for item in comment_items:
                content_elem = item.find(['p', 'div'], class_=re.compile(r'content|text'))
                if not content_elem:
                    continue
                    
                content = content_elem.get_text(strip=True)
                if content and len(content) >= 5:
                    comment = {
                        'content': content,
                        'author': '新浪用户',
                        'timestamp': '',
                        'likes': 0,
                        'replies': 0,
                        'source': 'sina_finance_news'
                    }
                    comments.append(comment)
                    
        except Exception as e:
            logger.warning(f"获取新闻页面评论失败: {news_url}, 错误: {e}")
            
        return comments