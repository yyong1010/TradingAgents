"""
东方财富数据源
获取东方财富股吧评论和讨论数据
"""

import re
import json
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)


class EastMoneyScraper:
    """东方财富爬虫"""
    
    def __init__(self, scraper):
        self.scraper = scraper
        self.base_url = "https://guba.eastmoney.com"
        self.api_base = "https://gbapi.eastmoney.com"
        
    def get_stock_comments(self, stock_code: str, limit: int = 50) -> List[Dict]:
        """
        获取股票吧评论
        
        Args:
            stock_code: 股票代码 (如: 300663)
            limit: 获取评论数量限制
            
        Returns:
            评论列表
        """
        comments = []
        
        try:
            # 使用正确的东方财富股吧URL格式
            guba_url = f"{self.base_url}/list,{stock_code}.html"
            
            # 获取股吧页面
            html_content = self.scraper.get_page(guba_url)
            if not html_content:
                logger.warning(f"无法获取东方财富股吧页面: {stock_code}")
                return comments
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 直接从列表页面提取帖子信息
            comments = self._extract_post_list(soup, stock_code, limit)
                    
        except Exception as e:
            logger.error(f"获取东方财富评论失败: {stock_code}, 错误: {e}")
            
        logger.info(f"东方财富获取到 {len(comments)} 条评论: {stock_code}")
        return comments[:limit]
    
    def _extract_post_list(self, soup: BeautifulSoup, stock_code: str, limit: int) -> List[Dict]:
        """从列表页面直接提取帖子信息"""
        comments = []
        
        try:
            # 查找帖子列表表格
            post_table = soup.find('table', class_='default_list')
            if not post_table:
                logger.warning(f"未找到东方财富帖子列表: {stock_code}")
                return comments
                
            # 查找表格行
            post_rows = post_table.find('tbody', class_='listbody')
            if not post_rows:
                return comments
                
            rows = post_rows.find_all('tr', class_='listitem')
            
            for row in rows[:limit]:
                try:
                    # 提取各列数据
                    cells = row.find_all('td')
                    if len(cells) < 5:
                        continue
                    
                    # 阅读数
                    read_elem = cells[0].find('div', class_='read')
                    reads = int(read_elem.get_text(strip=True)) if read_elem else 0
                    
                    # 回复数
                    reply_elem = cells[1].find('div', class_='reply')
                    replies = int(reply_elem.get_text(strip=True)) if reply_elem else 0
                    
                    # 标题
                    title_elem = cells[2].find('div', class_='title').find('a')
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    
                    if not title or len(title) < 5:
                        continue
                    
                    # 作者
                    author_elem = cells[3].find('div', class_='author').find('a')
                    author = author_elem.get_text(strip=True) if author_elem else "东财用户"
                    
                    # 更新时间
                    time_elem = cells[4].find('div', class_='update')
                    timestamp = time_elem.get_text(strip=True) if time_elem else ""
                    
                    # 过滤时间：只保留最近3天的内容
                    if not self._is_recent_post(timestamp):
                        continue
                    
                    comment = {
                        'content': title,
                        'author': author,
                        'timestamp': timestamp,
                        'likes': reads // 10,  # 用阅读数的1/10作为点赞数估算
                        'replies': replies,
                        'source': 'eastmoney_guba'
                    }
                    
                    comments.append(comment)
                    
                except Exception as e:
                    logger.debug(f"解析帖子行失败: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"东方财富帖子列表提取失败: {stock_code}, 错误: {e}")
            
        return comments
    
    def _get_post_comments(self, post_url: str, stock_code: str) -> List[Dict]:
        """获取帖子评论"""
        comments = []
        
        try:
            # 获取帖子页面
            html_content = self.scraper.get_page(post_url)
            if not html_content:
                return comments
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取主帖内容
            main_post = self._extract_main_post(soup)
            if main_post:
                comments.append(main_post)
            
            # 提取回复评论
            reply_comments = self._extract_reply_comments(soup)
            comments.extend(reply_comments)
            
        except Exception as e:
            logger.warning(f"获取帖子评论失败: {post_url}, 错误: {e}")
            
        return comments
    
    def _extract_main_post(self, soup: BeautifulSoup) -> Optional[Dict]:
        """提取主帖内容"""
        try:
            # 查找主帖内容区域
            main_content = soup.find('div', class_=re.compile(r'stockcodec|content|post'))
            if not main_content:
                return None
                
            # 提取内容文本
            content_elem = main_content.find(['div', 'p'], class_=re.compile(r'content|text'))
            if not content_elem:
                return None
                
            content = content_elem.get_text(strip=True)
            if not content or len(content) < 10:
                return None
            
            # 提取作者信息
            author_elem = soup.find(['span', 'div'], class_=re.compile(r'author|user'))
            author = author_elem.get_text(strip=True) if author_elem else "股友"
            
            # 提取发布时间
            time_elem = soup.find(['span', 'div'], class_=re.compile(r'time|date'))
            timestamp = time_elem.get_text(strip=True) if time_elem else ""
            
            # 提取点赞数
            like_elem = soup.find(['span', 'div'], class_=re.compile(r'like|zan'))
            likes = 0
            if like_elem:
                like_text = like_elem.get_text(strip=True)
                like_match = re.search(r'\d+', like_text)
                if like_match:
                    likes = int(like_match.group())
            
            return {
                'content': content,
                'author': author,
                'timestamp': timestamp,
                'likes': likes,
                'replies': 0,
                'source': 'eastmoney_guba'
            }
            
        except Exception as e:
            logger.warning(f"提取主帖失败: {e}")
            return None
    
    def _extract_reply_comments(self, soup: BeautifulSoup) -> List[Dict]:
        """提取回复评论"""
        comments = []
        
        try:
            # 查找回复区域
            reply_section = soup.find('div', class_=re.compile(r'reply|comment'))
            if not reply_section:
                return comments
                
            # 提取回复项
            reply_items = reply_section.find_all(['div', 'li'], class_=re.compile(r'item|reply'))
            
            for item in reply_items:
                # 提取回复内容
                content_elem = item.find(['p', 'div', 'span'], class_=re.compile(r'content|text'))
                if not content_elem:
                    continue
                    
                content = content_elem.get_text(strip=True)
                if not content or len(content) < 5:
                    continue
                
                # 提取作者
                author_elem = item.find(['span', 'div'], class_=re.compile(r'author|user|name'))
                author = author_elem.get_text(strip=True) if author_elem else "股友"
                
                # 提取时间
                time_elem = item.find(['span', 'div'], class_=re.compile(r'time|date'))
                timestamp = time_elem.get_text(strip=True) if time_elem else ""
                
                # 提取点赞数
                like_elem = item.find(['span', 'div'], class_=re.compile(r'like|zan'))
                likes = 0
                if like_elem:
                    like_text = like_elem.get_text(strip=True)
                    like_match = re.search(r'\d+', like_text)
                    if like_match:
                        likes = int(like_match.group())
                
                comment = {
                    'content': content,
                    'author': author,
                    'timestamp': timestamp,
                    'likes': likes,
                    'replies': 0,
                    'source': 'eastmoney_guba'
                }
                
                comments.append(comment)
                
        except Exception as e:
            logger.warning(f"提取回复评论失败: {e}")
            
        return comments
    
    def get_hot_stocks_sentiment(self, limit: int = 10) -> List[Dict]:
        """
        获取热门股票情绪
        
        Args:
            limit: 股票数量限制
            
        Returns:
            热门股票情绪列表
        """
        hot_stocks = []
        
        try:
            # 获取热门股票页面
            hot_url = f"{self.base_url}/rank"
            html_content = self.scraper.get_page(hot_url)
            
            if not html_content:
                return hot_stocks
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取热门股票列表
            stock_list = soup.find('div', class_=re.compile(r'rank|hot'))
            if not stock_list:
                return hot_stocks
                
            stock_items = stock_list.find_all(['div', 'li'], class_=re.compile(r'item|stock'))
            
            for item in stock_items[:limit]:
                # 提取股票代码
                code_elem = item.find(['span', 'div'], class_=re.compile(r'code|symbol'))
                if not code_elem:
                    continue
                    
                stock_code = code_elem.get_text(strip=True)
                
                # 提取股票名称
                name_elem = item.find(['span', 'div'], class_=re.compile(r'name|title'))
                stock_name = name_elem.get_text(strip=True) if name_elem else ""
                
                # 提取热度
                heat_elem = item.find(['span', 'div'], class_=re.compile(r'heat|hot'))
                heat = heat_elem.get_text(strip=True) if heat_elem else "0"
                
                hot_stock = {
                    'code': stock_code,
                    'name': stock_name,
                    'heat': heat,
                    'source': 'eastmoney_hot'
                }
                
                hot_stocks.append(hot_stock)
                
        except Exception as e:
            logger.error(f"获取热门股票失败: {e}")
            
        return hot_stocks
    
    def get_stock_research_reports(self, stock_code: str, limit: int = 10) -> List[Dict]:
        """
        获取股票研报评论
        
        Args:
            stock_code: 股票代码
            limit: 研报数量限制
            
        Returns:
            研报评论列表
        """
        reports = []
        
        try:
            # 构建研报搜索URL
            search_url = f"{self.base_url}/search"
            params = {
                'keyword': stock_code,
                'type': 'report'
            }
            
            html_content = self.scraper.get_page(search_url, params=params)
            if not html_content:
                return reports
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取研报链接
            report_links = soup.find_all('a', href=re.compile(r'/report/'))[:limit]
            
            for link in report_links:
                report_url = urljoin(self.base_url, link.get('href'))
                
                # 获取研报评论
                report_comments = self._get_report_comments(report_url, stock_code)
                reports.extend(report_comments)
                
        except Exception as e:
            logger.error(f"获取研报评论失败: {stock_code}, 错误: {e}")
            
        return reports
    
    def _get_report_comments(self, report_url: str, stock_code: str) -> List[Dict]:
        """获取研报评论"""
        comments = []
        
        try:
            html_content = self.scraper.get_page(report_url)
            if not html_content:
                return comments
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找评论区域
            comment_section = soup.find('div', class_=re.compile(r'comment|discuss'))
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
                        'author': '投资者',
                        'timestamp': '',
                        'likes': 0,
                        'replies': 0,
                        'source': 'eastmoney_report'
                    }
                    comments.append(comment)
                    
        except Exception as e:
            logger.warning(f"获取研报评论失败: {report_url}, 错误: {e}")
            
        return comments
    
    def _is_recent_post(self, timestamp: str) -> bool:
        """判断帖子是否为最近3天内的"""
        if not timestamp:
            return True
            
        try:
            from datetime import datetime, timedelta
            import re
            
            now = datetime.now()
            
            # 处理东方财富的时间格式：07-28 02:50
            if re.match(r'\d{2}-\d{2} \d{2}:\d{2}', timestamp):
                try:
                    # 假设是今年的日期
                    post_date = datetime.strptime(f"{now.year}-{timestamp}", "%Y-%m-%d %H:%M")
                    
                    # 如果日期在未来，说明是去年的
                    if post_date > now:
                        post_date = post_date.replace(year=now.year - 1)
                    
                    return (now - post_date).days <= 3
                except:
                    return True
            elif '分钟前' in timestamp or '小时前' in timestamp or '刚刚' in timestamp:
                return True
            elif '天前' in timestamp:
                days_match = re.search(r'(\d+)天前', timestamp)
                if days_match:
                    days = int(days_match.group(1))
                    return days <= 3
            
            return True
            
        except Exception as e:
            logger.debug(f"时间解析失败: {timestamp}, 错误: {e}")
            return True