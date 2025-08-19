"""
新闻爬虫主控制器
负责协调各个新闻源，去重和数据整理
"""

from typing import List, Dict, Set
from datetime import datetime, timedelta
import logging
from .news_sources import NewsItem, SinaNewsSource, EastmoneyNewsSource

logger = logging.getLogger(__name__)

class NewsCrawler:
    """新闻爬虫主控制器"""
    
    def __init__(self):
        self.sources = [
            SinaNewsSource(),
            EastmoneyNewsSource()
        ]
        self.seen_hashes: Set[str] = set()
    
    def get_stock_news(self, stock_code: str, max_days: int = 14) -> Dict:
        """
        获取股票相关新闻
        
        Args:
            stock_code: 股票代码
            max_days: 最大天数，超过此天数的新闻将被过滤
            
        Returns:
            包含新闻数据和统计信息的字典
        """
        logger.info(f"🔍 [新闻爬虫] 开始获取股票 {stock_code} 的新闻")
        
        all_news = []
        source_stats = {}
        
        # 从各个数据源获取新闻
        for source in self.sources:
            try:
                logger.info(f"📰 [新闻爬虫] 从 {source.source_name} 获取新闻")
                news_items = source.get_news(stock_code)
                
                # 过滤和去重
                filtered_news = self._filter_and_deduplicate(news_items, max_days)
                
                all_news.extend(filtered_news)
                source_stats[source.source_name] = len(filtered_news)
                
                logger.info(f"✅ [新闻爬虫] {source.source_name} 获取到 {len(filtered_news)} 条有效新闻")
                
            except Exception as e:
                logger.error(f"❌ [新闻爬虫] {source.source_name} 获取失败: {e}")
                source_stats[source.source_name] = 0
        
        # 按时间排序（最新的在前）
        all_news.sort(key=lambda x: x.publish_time, reverse=True)
        
        # 限制新闻数量
        max_news = 20
        if len(all_news) > max_news:
            all_news = all_news[:max_news]
            logger.info(f"📊 [新闻爬虫] 限制新闻数量为 {max_news} 条")
        
        # 生成统计信息
        total_news = len(all_news)
        cutoff_date = datetime.now() - timedelta(days=max_days)
        
        result = {
            'success': total_news > 0,
            'total_news': total_news,
            'cutoff_date': cutoff_date.strftime('%Y-%m-%d'),
            'source_stats': source_stats,
            'news_items': [news.to_dict() for news in all_news],
            'summary': self._generate_summary(all_news, source_stats)
        }
        
        if total_news == 0:
            logger.warning(f"⚠️ [新闻爬虫] 未获取到股票 {stock_code} 的有效新闻")
            result['message'] = f"未找到股票 {stock_code} 在过去 {max_days} 天内的相关新闻"
        else:
            logger.info(f"🎉 [新闻爬虫] 成功获取股票 {stock_code} 的 {total_news} 条新闻")
        
        return result
    
    def _filter_and_deduplicate(self, news_items: List[NewsItem], max_days: int) -> List[NewsItem]:
        """过滤和去重新闻"""
        filtered_news = []
        
        for news in news_items:
            # 检查时间范围
            if not news.is_within_days(max_days):
                continue
            
            # 检查是否重复
            if news.hash_key in self.seen_hashes:
                logger.debug(f"🔄 [去重] 跳过重复新闻: {news.title[:30]}...")
                continue
            
            # 检查内容质量
            if len(news.content) < 50:
                logger.debug(f"📝 [过滤] 跳过内容过短的新闻: {news.title[:30]}...")
                continue
            
            # 过滤垃圾标题
            spam_keywords = ['广告', '推广', '免费', '加群', '股神', '必涨', '内幕']
            if any(keyword in news.title for keyword in spam_keywords):
                logger.debug(f"🚫 [过滤] 跳过垃圾新闻: {news.title[:30]}...")
                continue
            
            self.seen_hashes.add(news.hash_key)
            filtered_news.append(news)
        
        return filtered_news
    
    def _generate_summary(self, news_items: List[NewsItem], source_stats: Dict) -> str:
        """生成新闻摘要"""
        if not news_items:
            return "未获取到有效新闻数据"
        
        # 统计信息
        total_count = len(news_items)
        sources = list(source_stats.keys())
        
        # 时间范围
        if news_items:
            latest_time = max(news.publish_time for news in news_items)
            earliest_time = min(news.publish_time for news in news_items)
            time_range = f"{earliest_time.strftime('%m-%d')} 至 {latest_time.strftime('%m-%d')}"
        else:
            time_range = "无"
        
        # 生成摘要
        summary_parts = [
            f"📊 新闻统计: 共获取 {total_count} 条新闻",
            f"📅 时间范围: {time_range}",
            f"📰 数据源: {', '.join(sources)}"
        ]
        
        # 各源统计
        source_details = []
        for source, count in source_stats.items():
            if count > 0:
                source_details.append(f"{source}({count}条)")
        
        if source_details:
            summary_parts.append(f"📈 来源分布: {', '.join(source_details)}")
        
        # 最新新闻标题
        if news_items:
            latest_news = news_items[0]
            summary_parts.append(f"🔥 最新新闻: {latest_news.title[:50]}...")
        
        return " | ".join(summary_parts)
    
    def get_formatted_news_text(self, stock_code: str, max_days: int = 14) -> str:
        """
        获取格式化的新闻文本，用于LLM分析
        
        Args:
            stock_code: 股票代码
            max_days: 最大天数
            
        Returns:
            格式化的新闻文本
        """
        news_data = self.get_stock_news(stock_code, max_days)
        
        if not news_data['success']:
            return f"⚠️ 新闻获取失败: {news_data.get('message', '未知错误')}"
        
        # 构建格式化文本
        text_parts = [
            f"📰 股票 {stock_code} 新闻分析数据",
            f"📊 数据统计: {news_data['summary']}",
            "=" * 60,
            ""
        ]
        
        # 添加新闻内容
        for i, news_dict in enumerate(news_data['news_items'], 1):
            publish_time = datetime.fromisoformat(news_dict['publish_time'])
            time_str = publish_time.strftime('%m-%d %H:%M')
            
            news_section = [
                f"📄 新闻 {i}: {news_dict['title']}",
                f"🕒 时间: {time_str} | 📍 来源: {news_dict['source']}",
                f"🔗 链接: {news_dict['url']}",
                f"📝 内容: {news_dict['content'][:800]}{'...' if len(news_dict['content']) > 800 else ''}",
                "-" * 40,
                ""
            ]
            
            text_parts.extend(news_section)
        
        return "\n".join(text_parts)