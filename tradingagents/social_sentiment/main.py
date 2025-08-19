"""
社交媒体情绪分析主接口
统一调用各个数据源，提供完整的情绪分析结果
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import logging

from .web_scraper import WebScraper
from .data_processor import DataProcessor
from .sources import (
    SinaFinanceScraper,
    EastMoneyScraper
)

logger = logging.getLogger(__name__)


class SocialSentimentAnalyzer:
    """社交媒体情绪分析器"""
    
    def __init__(self):
        self.scraper = WebScraper()
        self.processor = DataProcessor()
        
        # 初始化各个数据源
        self.sources = {
            'sina_finance': SinaFinanceScraper(self.scraper),
            'eastmoney': EastMoneyScraper(self.scraper)
        }
        
        # 数据源权重配置
        self.source_weights = {
            'sina_finance': 0.40,
            'eastmoney': 0.60
        }
        
        # 每个数据源的评论数量分配
        self.source_limits = {
            'sina_finance': 40,
            'eastmoney': 60
        }
    
    def get_stock_social_sentiment(self, stock_code: str, total_limit: int = 100) -> Dict:
        """
        获取股票社交媒体情绪分析
        
        Args:
            stock_code: 股票代码 (如: 300663)
            total_limit: 总评论数量限制
            
        Returns:
            完整的情绪分析结果
        """
        logger.info(f"开始获取股票 {stock_code} 的社交媒体情绪数据")
        
        # 收集所有评论
        all_comments = []
        source_results = {}
        
        # 从各个数据源获取评论
        for source_name, source_scraper in self.sources.items():
            try:
                logger.info(f"正在从 {source_name} 获取数据...")
                
                # 计算该数据源的评论数量限制
                source_limit = min(
                    self.source_limits.get(source_name, 20),
                    int(total_limit * self.source_weights.get(source_name, 0.2))
                )
                
                # 获取评论
                comments = source_scraper.get_stock_comments(stock_code, source_limit)
                
                if comments:
                    all_comments.extend(comments)
                    source_results[source_name] = {
                        'count': len(comments),
                        'success': True
                    }
                    logger.info(f"✅ {source_name} 获取到 {len(comments)} 条评论")
                else:
                    source_results[source_name] = {
                        'count': 0,
                        'success': False,
                        'error': '未获取到数据'
                    }
                    logger.warning(f"⚠️ {source_name} 未获取到评论")
                    
            except Exception as e:
                source_results[source_name] = {
                    'count': 0,
                    'success': False,
                    'error': str(e)
                }
                logger.error(f"❌ {source_name} 获取失败: {e}")
        
        # 检查是否获取到有效数据
        if not all_comments:
            logger.warning(f"未获取到任何有效的社交媒体数据: {stock_code}")
            return self._generate_empty_result(stock_code, source_results)
        
        logger.info(f"总共获取到 {len(all_comments)} 条原始评论")
        
        # 处理和过滤评论
        processed_comments = self.processor.process_comments(all_comments)
        
        if not processed_comments:
            logger.warning(f"所有评论都被过滤，无有效数据: {stock_code}")
            return self._generate_empty_result(stock_code, source_results)
        
        # 聚合情绪分析
        sentiment_analysis = self.processor.aggregate_sentiment(processed_comments)
        
        # 生成最终结果
        result = self._generate_final_result(
            stock_code, 
            processed_comments, 
            sentiment_analysis, 
            source_results
        )
        
        logger.info(f"✅ 完成股票 {stock_code} 的情绪分析")
        return result
    
    def _generate_empty_result(self, stock_code: str, source_results: Dict) -> Dict:
        """生成空结果"""
        return {
            'stock_code': stock_code,
            'success': False,
            'error': '未获取到有效的社交媒体数据',
            'timestamp': datetime.now().isoformat(),
            'data_sources': source_results,
            'sentiment_analysis': {
                'total_comments': 0,
                'average_sentiment': 0.0,
                'positive_ratio': 0.0,
                'negative_ratio': 0.0,
                'neutral_ratio': 0.0
            },
            'summary': f"由于数据获取限制，无法获取股票 {stock_code} 的实时社交媒体情绪数据。建议关注官方财经媒体报道和基本面分析。"
        }
    
    def _generate_final_result(self, stock_code: str, comments: List[Dict], 
                             sentiment_analysis: Dict, source_results: Dict) -> Dict:
        """生成最终分析结果"""
        
        # 计算数据质量分数
        data_quality_score = self._calculate_data_quality(comments, source_results)
        
        # 生成情绪总结
        sentiment_summary = self._generate_sentiment_summary(sentiment_analysis, stock_code)
        
        # 提取关键观点
        key_opinions = self._extract_key_opinions(comments)
        
        # 计算情绪趋势
        sentiment_trend = self._analyze_sentiment_trend(comments)
        
        return {
            'stock_code': stock_code,
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'data_quality_score': data_quality_score,
            'data_sources': source_results,
            'sentiment_analysis': sentiment_analysis,
            'sentiment_summary': sentiment_summary,
            'key_opinions': key_opinions,
            'sentiment_trend': sentiment_trend,
            'raw_comments_count': len(comments),
            'analysis_period': '实时数据',
            'confidence_level': self._calculate_confidence_level(data_quality_score, len(comments))
        }
    
    def _calculate_data_quality(self, comments: List[Dict], source_results: Dict) -> float:
        """计算数据质量分数"""
        if not comments:
            return 0.0
        
        # 基础分数：基于评论数量
        comment_score = min(len(comments) / 50, 1.0) * 0.4
        
        # 数据源多样性分数
        successful_sources = sum(1 for result in source_results.values() if result['success'])
        diversity_score = (successful_sources / len(self.sources)) * 0.3
        
        # 内容质量分数：基于平均内容长度和情绪关键词
        avg_content_length = sum(len(c['content']) for c in comments) / len(comments)
        content_score = min(avg_content_length / 100, 1.0) * 0.2
        
        # 互动质量分数：基于点赞和回复
        total_interactions = sum(c.get('likes', 0) + c.get('replies', 0) for c in comments)
        interaction_score = min(total_interactions / (len(comments) * 5), 1.0) * 0.1
        
        total_score = comment_score + diversity_score + content_score + interaction_score
        return round(total_score, 2)
    
    def _generate_sentiment_summary(self, sentiment_analysis: Dict, stock_code: str) -> str:
        """生成情绪分析总结"""
        total_comments = sentiment_analysis['total_comments']
        avg_sentiment = sentiment_analysis['average_sentiment']
        positive_ratio = sentiment_analysis['positive_ratio']
        negative_ratio = sentiment_analysis['negative_ratio']
        
        # 判断整体情绪倾向
        if avg_sentiment > 0.2:
            sentiment_label = "偏乐观"
        elif avg_sentiment < -0.2:
            sentiment_label = "偏悲观"
        else:
            sentiment_label = "中性"
        
        # 生成总结
        summary = f"""
基于 {total_comments} 条真实社交媒体评论的分析，{stock_code} 的投资者情绪呈现 {sentiment_label} 态势。

📊 情绪分布：
• 正面情绪：{positive_ratio:.1%} 
• 负面情绪：{negative_ratio:.1%}
• 中性观点：{sentiment_analysis['neutral_ratio']:.1%}

💭 情绪特征：
"""
        
        # 添加关键词分析
        top_positive = sentiment_analysis.get('top_positive_keywords', [])
        top_negative = sentiment_analysis.get('top_negative_keywords', [])
        
        if top_positive:
            pos_keywords = [kw[0] for kw in top_positive[:3]]
            summary += f"• 高频正面词汇：{', '.join(pos_keywords)}\n"
            
        if top_negative:
            neg_keywords = [kw[0] for kw in top_negative[:3]]
            summary += f"• 高频负面词汇：{', '.join(neg_keywords)}\n"
        
        return summary.strip()
    
    def _extract_key_opinions(self, comments: List[Dict], limit: int = 5) -> List[Dict]:
        """提取关键观点"""
        # 按点赞数和内容长度排序
        sorted_comments = sorted(
            comments, 
            key=lambda x: (x.get('likes', 0) * 2 + len(x['content']) / 10), 
            reverse=True
        )
        
        key_opinions = []
        for comment in sorted_comments[:limit]:
            opinion = {
                'content': comment['content'][:200] + ('...' if len(comment['content']) > 200 else ''),
                'sentiment_score': comment['sentiment_score'],
                'likes': comment.get('likes', 0),
                'source': comment.get('source', ''),
                'author': comment.get('author', '匿名')
            }
            key_opinions.append(opinion)
            
        return key_opinions
    
    def _analyze_sentiment_trend(self, comments: List[Dict]) -> Dict:
        """分析情绪趋势"""
        if not comments:
            return {'trend': 'unknown', 'description': '数据不足'}
        
        # 简单的趋势分析：比较前后两部分评论的情绪
        mid_point = len(comments) // 2
        if mid_point < 5:
            return {'trend': 'stable', 'description': '数据量较少，趋势不明显'}
        
        early_comments = comments[:mid_point]
        recent_comments = comments[mid_point:]
        
        early_sentiment = sum(c['sentiment_score'] for c in early_comments) / len(early_comments)
        recent_sentiment = sum(c['sentiment_score'] for c in recent_comments) / len(recent_comments)
        
        sentiment_change = recent_sentiment - early_sentiment
        
        if sentiment_change > 0.1:
            trend = 'improving'
            description = '投资者情绪呈现改善趋势'
        elif sentiment_change < -0.1:
            trend = 'declining'
            description = '投资者情绪呈现下降趋势'
        else:
            trend = 'stable'
            description = '投资者情绪相对稳定'
        
        return {
            'trend': trend,
            'description': description,
            'change_magnitude': round(sentiment_change, 3),
            'early_sentiment': round(early_sentiment, 3),
            'recent_sentiment': round(recent_sentiment, 3)
        }
    
    def _calculate_confidence_level(self, data_quality_score: float, comment_count: int) -> str:
        """计算置信度等级"""
        if data_quality_score >= 0.7 and comment_count >= 30:
            return '高'
        elif data_quality_score >= 0.5 and comment_count >= 15:
            return '中'
        else:
            return '低'
    
    def close(self):
        """关闭资源"""
        self.scraper.close()


# 全局实例
_analyzer = None

def get_stock_social_sentiment(stock_code: str, total_limit: int = 100) -> Dict:
    """
    获取股票社交媒体情绪分析（同步接口）
    
    Args:
        stock_code: 股票代码 (如: 300663)
        total_limit: 总评论数量限制
        
    Returns:
        完整的情绪分析结果
    """
    global _analyzer
    
    if _analyzer is None:
        _analyzer = SocialSentimentAnalyzer()
    
    try:
        return _analyzer.get_stock_social_sentiment(stock_code, total_limit)
    except Exception as e:
        logger.error(f"获取社交媒体情绪分析失败: {stock_code}, 错误: {e}")
        return {
            'stock_code': stock_code,
            'success': False,
            'error': f'分析失败: {str(e)}',
            'timestamp': datetime.now().isoformat(),
            'summary': f'由于技术原因，无法完成股票 {stock_code} 的社交媒体情绪分析。'
        }