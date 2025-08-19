"""
新闻数据源实现
支持从新浪财经和东方财富爬取股票新闻
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import logging
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

class NewsItem:
    """新闻条目数据结构"""
    def __init__(self, title: str, content: str, url: str, publish_time: datetime, source: str):
        self.title = title
        self.content = content
        self.url = url
        self.publish_time = publish_time
        self.source = source
        self.hash_key = self._generate_hash()
    
    def _generate_hash(self) -> str:
        """生成新闻的唯一标识用于去重"""
        import hashlib
        content_for_hash = f"{self.title}_{self.publish_time.strftime('%Y%m%d')}"
        return hashlib.md5(content_for_hash.encode('utf-8')).hexdigest()
    
    def is_within_days(self, days: int = 14) -> bool:
        """检查新闻是否在指定天数内"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return self.publish_time >= cutoff_date
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'title': self.title,
            'content': self.content,
            'url': self.url,
            'publish_time': self.publish_time.isoformat(),
            'source': self.source,
            'hash_key': self.hash_key
        }

class BaseNewsSource:
    """新闻源基类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.timeout = 10
        self.max_retries = 3
    
    def _make_request(self, url: str, **kwargs) -> Optional[requests.Response]:
        """发起HTTP请求，带重试机制"""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {url} - {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        # 常见的日期格式
        date_patterns = [
            r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})',  # 2024-01-15 10:30
            r'(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{2}):(\d{2})',  # 2024年1月15日 10:30
            r'(\d{2})-(\d{2})\s+(\d{2}):(\d{2})',  # 01-15 10:30 (当年)
            r'(\d{1,2})月(\d{1,2})日\s+(\d{2}):(\d{2})',  # 1月15日 10:30 (当年)
            r'(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})',  # 2024/01/15 10:30
        ]
        
        current_year = datetime.now().year
        
        for pattern in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 5:
                        if len(groups[0]) == 4:  # 包含年份
                            year, month, day, hour, minute = map(int, groups)
                        else:  # 不包含年份，使用当前年份
                            month, day, hour, minute = map(int, groups)
                            year = current_year
                    elif len(groups) == 4:  # MM-DD HH:MM 格式
                        month, day, hour, minute = map(int, groups)
                        year = current_year
                    else:
                        continue
                    
                    return datetime(year, month, day, hour, minute)
                except ValueError:
                    continue
        
        # 如果无法解析，返回当前时间
        logger.warning(f"无法解析日期: {date_str}")
        return datetime.now()
    
    def get_news(self, stock_code: str) -> List[NewsItem]:
        """获取新闻，子类需要实现"""
        raise NotImplementedError

class SinaNewsSource(BaseNewsSource):
    """新浪财经新闻源"""
    
    def __init__(self):
        super().__init__()
        self.source_name = "新浪财经"
    
    def get_news(self, stock_code: str) -> List[NewsItem]:
        """获取新浪财经的股票新闻"""
        news_items = []
        
        # 获取公司新闻
        corp_news = self._get_corp_news(stock_code)
        news_items.extend(corp_news)
        
        # 获取研报新闻
        report_news = self._get_report_news(stock_code)
        news_items.extend(report_news)
        
        return news_items
    
    def _get_corp_news(self, stock_code: str) -> List[NewsItem]:
        """获取公司新闻"""
        news_items = []
        
        # 构建URL - 新浪财经公司新闻页面
        if stock_code.startswith('3'):
            symbol = f"sz{stock_code}"
        elif stock_code.startswith('0'):
            symbol = f"sz{stock_code}"
        elif stock_code.startswith('6'):
            symbol = f"sh{stock_code}"
        else:
            symbol = f"sz{stock_code}"
        
        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{symbol}.phtml"
        
        logger.info(f"🔍 [新浪财经] 获取公司新闻: {url}")
        
        response = self._make_request(url)
        if not response:
            return news_items
        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找新闻列表 - 更新的选择器
            news_div = soup.find('div', {'class': 'datelist'})
            if not news_div:
                logger.warning("未找到新闻列表div")
                return news_items
            
            news_ul = news_div.find('ul')
            if not news_ul:
                logger.warning("未找到新闻列表ul")
                return news_items
            
            # 解析新闻列表的文本内容
            news_text = news_ul.get_text()
            
            # 使用正则表达式解析新闻条目
            import re
            # 匹配格式：日期 时间 标题链接
            pattern = r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+([^<]+?)(?=\s+\d{4}-\d{2}-\d{2}|\s*$)'
            
            # 查找所有链接
            links = news_ul.find_all('a', href=True)
            
            for link in links:
                try:
                    title = link.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    
                    news_url = link.get('href', '')
                    if not news_url.startswith('http'):
                        news_url = urljoin(url, news_url)
                    
                    # 从链接的前面文本中提取时间
                    link_parent = link.parent
                    if link_parent:
                        parent_text = link_parent.get_text()
                        # 查找时间模式
                        time_match = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', parent_text)
                        if time_match:
                            date_str = f"{time_match.group(1)} {time_match.group(2)}"
                            publish_time = self._parse_date(date_str)
                        else:
                            publish_time = datetime.now()
                    else:
                        publish_time = datetime.now()
                    
                    # 获取新闻内容
                    content = self._get_news_content(news_url)
                    if not content:
                        content = title  # 如果无法获取内容，使用标题作为内容
                    
                    if title:
                        news_item = NewsItem(
                            title=title,
                            content=content,
                            url=news_url,
                            publish_time=publish_time,
                            source=f"{self.source_name}-公司新闻"
                        )
                        
                        # 只保留2周内的新闻
                        if news_item.is_within_days(14):
                            news_items.append(news_item)
                            logger.info(f"✅ 获取新闻: {title[:50]}...")
                        else:
                            logger.debug(f"⏰ 跳过过期新闻: {title[:50]}...")
                
                except Exception as e:
                    logger.error(f"解析新闻链接失败: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"解析新浪财经公司新闻失败: {e}")
        
        return news_items
    
    def _get_report_news(self, stock_code: str) -> List[NewsItem]:
        """获取研报新闻"""
        news_items = []
        
        url = f"https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/search/index.phtml?symbol={stock_code}&t1=all"
        
        logger.info(f"🔍 [新浪财经] 获取研报新闻: {url}")
        
        response = self._make_request(url)
        if not response:
            return news_items
        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找研报列表
            report_list = soup.find('div', {'class': 'datelist'})
            if not report_list:
                logger.warning("未找到研报列表")
                return news_items
            
            items = report_list.find_all('li')
            
            for item in items:
                try:
                    # 提取标题和链接
                    title_link = item.find('a')
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    news_url = urljoin(url, title_link.get('href', ''))
                    
                    # 提取时间
                    time_span = item.find('span', {'class': 'time'})
                    if time_span:
                        time_str = time_span.get_text(strip=True)
                        publish_time = self._parse_date(time_str)
                    else:
                        publish_time = datetime.now()
                    
                    # 获取内容
                    content = self._get_news_content(news_url)
                    
                    if title and content:
                        news_item = NewsItem(
                            title=title,
                            content=content,
                            url=news_url,
                            publish_time=publish_time,
                            source=f"{self.source_name}-研报"
                        )
                        
                        if news_item.is_within_days(14):
                            news_items.append(news_item)
                            logger.info(f"✅ 获取研报: {title[:50]}...")
                
                except Exception as e:
                    logger.error(f"解析研报项失败: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"解析新浪财经研报失败: {e}")
        
        return news_items
    
    def _get_news_content(self, url: str) -> str:
        """获取新闻详细内容"""
        if not url:
            return ""
        
        response = self._make_request(url)
        if not response:
            return ""
        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尝试多种内容选择器
            content_selectors = [
                'div.article-content',
                'div.content',
                'div.news-content',
                'div#artibody',
                'div.artibody',
                'div.blkContainerSblk'
            ]
            
            content = ""
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    # 移除脚本和样式
                    for script in content_div(["script", "style"]):
                        script.decompose()
                    
                    content = content_div.get_text(strip=True)
                    break
            
            # 如果没有找到特定的内容区域，尝试获取页面主要文本
            if not content:
                # 移除不需要的元素
                for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                    element.decompose()
                
                content = soup.get_text(strip=True)
                # 限制内容长度
                if len(content) > 2000:
                    content = content[:2000] + "..."
            
            return content[:1500] if content else ""  # 限制内容长度
        
        except Exception as e:
            logger.error(f"获取新闻内容失败: {url} - {e}")
            return ""

class EastmoneyNewsSource(BaseNewsSource):
    """东方财富新闻源"""
    
    def __init__(self):
        super().__init__()
        self.source_name = "东方财富"
    
    def get_news(self, stock_code: str) -> List[NewsItem]:
        """获取东方财富的股票新闻"""
        news_items = []
        
        # 东方财富股吧新闻
        guba_news = self._get_guba_news(stock_code)
        news_items.extend(guba_news)
        
        return news_items
    
    def _get_guba_news(self, stock_code: str) -> List[NewsItem]:
        """获取东方财富股吧新闻"""
        news_items = []
        
        url = f"https://guba.eastmoney.com/list,{stock_code},1,f.html"
        
        logger.info(f"🔍 [东方财富] 获取股吧新闻: {url}")
        
        response = self._make_request(url)
        if not response:
            return news_items
        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找新闻列表表格 - 更新的选择器
            news_table = soup.find('table', {'class': 'default_list'})
            if not news_table:
                logger.warning("未找到股吧新闻列表表格")
                return news_items
            
            # 查找表格主体
            tbody = news_table.find('tbody', {'class': 'listbody'})
            if not tbody:
                logger.warning("未找到股吧新闻列表主体")
                return news_items
            
            # 查找所有新闻行
            rows = tbody.find_all('tr', {'class': 'listitem'})
            
            for row in rows[:20]:  # 限制获取数量
                try:
                    cells = row.find_all('td')
                    if len(cells) < 5:
                        continue
                    
                    # 提取标题和链接（第3列）
                    title_cell = cells[2]
                    title_div = title_cell.find('div', {'class': 'title'})
                    if not title_div:
                        continue
                    
                    title_link = title_div.find('a')
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    if not title or len(title) < 5:  # 过滤太短的标题
                        continue
                    
                    post_url = urljoin(url, title_link.get('href', ''))
                    
                    # 提取时间（第5列）
                    time_cell = cells[4]
                    time_div = time_cell.find('div', {'class': 'update'})
                    if time_div:
                        time_str = time_div.get_text(strip=True)
                        # 东方财富的时间格式：07-25 06:39
                        publish_time = self._parse_date(f"2025-{time_str}")
                    else:
                        publish_time = datetime.now()
                    
                    # 获取帖子内容
                    content = self._get_post_content(post_url)
                    if not content:
                        content = title  # 如果无法获取内容，使用标题作为内容
                    
                    if title and len(content) > 10:  # 确保有实质内容
                        news_item = NewsItem(
                            title=title,
                            content=content,
                            url=post_url,
                            publish_time=publish_time,
                            source=f"{self.source_name}-股吧"
                        )
                        
                        if news_item.is_within_days(14):
                            news_items.append(news_item)
                            logger.info(f"✅ 获取股吧帖子: {title[:50]}...")
                        else:
                            logger.debug(f"⏰ 跳过过期帖子: {title[:50]}...")
                
                except Exception as e:
                    logger.error(f"解析股吧帖子失败: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"解析东方财富股吧失败: {e}")
        
        return news_items
    
    def _get_post_content(self, url: str) -> str:
        """获取帖子详细内容"""
        if not url:
            return ""
        
        response = self._make_request(url)
        if not response:
            return ""
        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尝试多种内容选择器
            content_selectors = [
                'div.stockcodec',
                'div.articleZoom',
                'div.content',
                'div.post-content',
                'div#zwconttb'
            ]
            
            content = ""
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    # 移除脚本和样式
                    for script in content_div(["script", "style"]):
                        script.decompose()
                    
                    content = content_div.get_text(strip=True)
                    break
            
            return content[:1000] if content else ""  # 限制内容长度
        
        except Exception as e:
            logger.error(f"获取帖子内容失败: {url} - {e}")
            return ""