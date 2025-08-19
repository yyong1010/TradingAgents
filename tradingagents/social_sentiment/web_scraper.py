"""
网页爬虫核心模块
模拟真实浏览器访问，获取社交媒体数据
"""

import requests
import time
import random
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)


class WebScraper:
    """网页爬虫核心类"""
    
    def __init__(self):
        self.session = requests.Session()
        
        # 模拟真实浏览器的Headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        self.session.headers.update(self.headers)
        
        # 请求配置
        self.timeout = 10
        self.max_retries = 3
        self.retry_delay = 2
        self.request_delay = (1, 3)  # 随机延迟范围
        
    def get_page(self, url: str, params: Optional[Dict] = None, 
                 custom_headers: Optional[Dict] = None) -> Optional[str]:
        """
        获取网页内容
        
        Args:
            url: 目标URL
            params: URL参数
            custom_headers: 自定义请求头
            
        Returns:
            网页HTML内容，失败返回None
        """
        headers = self.headers.copy()
        if custom_headers:
            headers.update(custom_headers)
            
        for attempt in range(self.max_retries):
            try:
                # 随机延迟，避免被识别为爬虫
                delay = random.uniform(*self.request_delay)
                time.sleep(delay)
                
                logger.debug(f"请求URL: {url}, 尝试次数: {attempt + 1}")
                
                response = self.session.get(
                    url, 
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                
                response.raise_for_status()
                
                # 检查响应内容
                if response.text and len(response.text) > 100:
                    logger.debug(f"成功获取页面: {url}, 内容长度: {len(response.text)}")
                    return response.text
                else:
                    logger.warning(f"页面内容异常: {url}, 内容长度: {len(response.text) if response.text else 0}")
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {url}, 错误: {e}")
                
                if attempt < self.max_retries - 1:
                    # 指数退避
                    sleep_time = self.retry_delay * (2 ** attempt)
                    time.sleep(sleep_time)
                    
        logger.error(f"所有重试失败: {url}")
        return None
    
    def get_json(self, url: str, params: Optional[Dict] = None,
                 custom_headers: Optional[Dict] = None) -> Optional[Dict]:
        """
        获取JSON数据
        
        Args:
            url: 目标URL
            params: URL参数
            custom_headers: 自定义请求头
            
        Returns:
            JSON数据，失败返回None
        """
        headers = self.headers.copy()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        })
        
        if custom_headers:
            headers.update(custom_headers)
            
        for attempt in range(self.max_retries):
            try:
                # 随机延迟
                delay = random.uniform(*self.request_delay)
                time.sleep(delay)
                
                logger.debug(f"请求JSON: {url}, 尝试次数: {attempt + 1}")
                
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                json_data = response.json()
                logger.debug(f"成功获取JSON: {url}")
                return json_data
                
            except (requests.exceptions.RequestException, ValueError) as e:
                logger.warning(f"JSON请求失败 (尝试 {attempt + 1}/{self.max_retries}): {url}, 错误: {e}")
                
                if attempt < self.max_retries - 1:
                    sleep_time = self.retry_delay * (2 ** attempt)
                    time.sleep(sleep_time)
                    
        logger.error(f"JSON请求所有重试失败: {url}")
        return None
    
    def update_headers(self, new_headers: Dict):
        """更新请求头"""
        self.headers.update(new_headers)
        self.session.headers.update(new_headers)
    
    def set_proxy(self, proxy: str):
        """设置代理"""
        self.session.proxies.update({
            'http': proxy,
            'https': proxy
        })
    
    def close(self):
        """关闭会话"""
        self.session.close()