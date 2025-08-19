"""
数据处理和过滤模块
过滤垃圾信息，保留真实客户意见
"""

import re
import jieba
from typing import List, Dict, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataProcessor:
    """数据处理和过滤器"""
    
    def __init__(self):
        # 垃圾信息关键词
        self.spam_keywords = {
            '广告', '推广', '加群', '微信', 'QQ', '联系', '代理', '投资顾问',
            '荐股', '内幕', '必涨', '必跌', '包赚', '稳赚', '暴涨', '暴跌',
            '老师', '群主', '带单', '跟单', '收费', '付费', '会员', 'VIP',
            '炒股软件', '选股器', '股票软件', '交流群', '股友群'
        }
        
        # 无意义内容关键词
        self.meaningless_keywords = {
            '顶', '沙发', '板凳', '路过', '围观', '吃瓜', '哈哈', '呵呵',
            '不错', '支持', '赞', '👍', '💪', '🚀', '📈', '📉',
            '早上好', '晚上好', '签到', '打卡'
        }
        
        # 情绪关键词
        self.positive_keywords = {
            '看好', '乐观', '上涨', '涨', '买入', '加仓', '持有', '利好',
            '突破', '强势', '牛市', '机会', '潜力', '价值', '低估',
            '反弹', '回升', '企稳', '支撑', '底部', '抄底'
        }
        
        self.negative_keywords = {
            '看空', '悲观', '下跌', '跌', '卖出', '减仓', '清仓', '利空',
            '破位', '弱势', '熊市', '风险', '高估', '泡沫', '套牢',
            '下跌', '暴跌', '跳水', '压力', '顶部', '逃顶'
        }
        
        # 初始化jieba分词
        jieba.initialize()
    
    def is_spam(self, text: str) -> bool:
        """
        判断是否为垃圾信息
        
        Args:
            text: 待检查的文本
            
        Returns:
            True表示是垃圾信息
        """
        if not text or len(text.strip()) < 5:
            return True
            
        text_lower = text.lower()
        
        # 检查垃圾关键词
        for keyword in self.spam_keywords:
            if keyword in text_lower:
                return True
                
        # 检查是否包含过多特殊字符
        special_char_ratio = len(re.findall(r'[^\w\s\u4e00-\u9fff]', text)) / len(text)
        if special_char_ratio > 0.3:
            return True
            
        # 检查是否为重复字符
        if len(set(text)) / len(text) < 0.3:
            return True
            
        return False
    
    def is_meaningless(self, text: str) -> bool:
        """
        判断是否为无意义内容
        
        Args:
            text: 待检查的文本
            
        Returns:
            True表示无意义
        """
        if not text or len(text.strip()) < 3:
            return True
            
        text_clean = text.strip()
        
        # 检查是否只包含无意义关键词
        words = jieba.lcut(text_clean)
        meaningful_words = [w for w in words if w not in self.meaningless_keywords and len(w) > 1]
        
        if len(meaningful_words) == 0:
            return True
            
        # 检查是否过短且无实质内容
        if len(text_clean) < 10 and not any(kw in text_clean for kw in self.positive_keywords | self.negative_keywords):
            return True
            
        return False
    
    def extract_sentiment_keywords(self, text: str) -> Dict[str, List[str]]:
        """
        提取情绪关键词
        
        Args:
            text: 文本内容
            
        Returns:
            包含正面和负面关键词的字典
        """
        words = jieba.lcut(text)
        
        positive_found = [w for w in words if w in self.positive_keywords]
        negative_found = [w for w in words if w in self.negative_keywords]
        
        return {
            'positive': positive_found,
            'negative': negative_found
        }
    
    def calculate_sentiment_score(self, text: str) -> float:
        """
        计算情绪分数
        
        Args:
            text: 文本内容
            
        Returns:
            情绪分数 (-1到1之间，正数表示正面情绪)
        """
        sentiment_keywords = self.extract_sentiment_keywords(text)
        
        positive_count = len(sentiment_keywords['positive'])
        negative_count = len(sentiment_keywords['negative'])
        
        total_count = positive_count + negative_count
        if total_count == 0:
            return 0.0
            
        # 计算情绪分数
        score = (positive_count - negative_count) / total_count
        return score
    
    def clean_text(self, text: str) -> str:
        """
        清理文本内容
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return ""
            
        # 移除多余空白字符
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除特殊字符（保留中文、英文、数字、基本标点）
        text = re.sub(r'[^\w\s\u4e00-\u9fff，。！？；：""''（）【】]', '', text)
        
        return text.strip()
    
    def process_comments(self, comments: List[Dict]) -> List[Dict]:
        """
        处理评论列表，过滤垃圾信息
        
        Args:
            comments: 原始评论列表
            
        Returns:
            过滤后的评论列表
        """
        processed_comments = []
        
        for comment in comments:
            if not isinstance(comment, dict) or 'content' not in comment:
                continue
                
            content = comment.get('content', '')
            if not content:
                continue
                
            # 清理文本
            cleaned_content = self.clean_text(content)
            
            # 过滤垃圾信息
            if self.is_spam(cleaned_content):
                logger.debug(f"过滤垃圾信息: {cleaned_content[:50]}...")
                continue
                
            # 过滤无意义内容
            if self.is_meaningless(cleaned_content):
                logger.debug(f"过滤无意义内容: {cleaned_content[:50]}...")
                continue
                
            # 计算情绪分数
            sentiment_score = self.calculate_sentiment_score(cleaned_content)
            sentiment_keywords = self.extract_sentiment_keywords(cleaned_content)
            
            # 构建处理后的评论
            processed_comment = {
                'content': cleaned_content,
                'original_content': content,
                'sentiment_score': sentiment_score,
                'sentiment_keywords': sentiment_keywords,
                'timestamp': comment.get('timestamp'),
                'author': comment.get('author'),
                'source': comment.get('source'),
                'likes': comment.get('likes', 0),
                'replies': comment.get('replies', 0)
            }
            
            processed_comments.append(processed_comment)
            
        logger.info(f"评论处理完成: 原始{len(comments)}条 -> 有效{len(processed_comments)}条")
        return processed_comments
    
    def aggregate_sentiment(self, comments: List[Dict]) -> Dict:
        """
        聚合情绪分析结果
        
        Args:
            comments: 处理后的评论列表
            
        Returns:
            聚合的情绪分析结果
        """
        if not comments:
            return {
                'total_comments': 0,
                'average_sentiment': 0.0,
                'positive_ratio': 0.0,
                'negative_ratio': 0.0,
                'neutral_ratio': 0.0,
                'top_positive_keywords': [],
                'top_negative_keywords': []
            }
            
        # 计算基本统计
        total_comments = len(comments)
        sentiment_scores = [c['sentiment_score'] for c in comments]
        average_sentiment = sum(sentiment_scores) / total_comments
        
        # 分类统计
        positive_count = sum(1 for score in sentiment_scores if score > 0.1)
        negative_count = sum(1 for score in sentiment_scores if score < -0.1)
        neutral_count = total_comments - positive_count - negative_count
        
        positive_ratio = positive_count / total_comments
        negative_ratio = negative_count / total_comments
        neutral_ratio = neutral_count / total_comments
        
        # 统计关键词
        all_positive_keywords = []
        all_negative_keywords = []
        
        for comment in comments:
            all_positive_keywords.extend(comment['sentiment_keywords']['positive'])
            all_negative_keywords.extend(comment['sentiment_keywords']['negative'])
            
        # 获取高频关键词
        from collections import Counter
        positive_counter = Counter(all_positive_keywords)
        negative_counter = Counter(all_negative_keywords)
        
        top_positive_keywords = positive_counter.most_common(10)
        top_negative_keywords = negative_counter.most_common(10)
        
        return {
            'total_comments': total_comments,
            'average_sentiment': round(average_sentiment, 3),
            'positive_ratio': round(positive_ratio, 3),
            'negative_ratio': round(negative_ratio, 3),
            'neutral_ratio': round(neutral_ratio, 3),
            'top_positive_keywords': top_positive_keywords,
            'top_negative_keywords': top_negative_keywords,
            'sentiment_distribution': {
                'positive': positive_count,
                'negative': negative_count,
                'neutral': neutral_count
            }
        }