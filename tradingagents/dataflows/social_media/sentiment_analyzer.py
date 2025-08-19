"""
情绪分析引擎
基于中文文本的情绪分析和量化评分
"""

import re
import jieba
from typing import List, Dict, Tuple
import logging
from collections import Counter
import math

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """中文情绪分析引擎"""
    
    def __init__(self):
        # 情绪词典
        self.positive_words = {
            # 上涨相关
            '上涨': 3, '增长': 3, '涨停': 4, '大涨': 4, '暴涨': 4, '飙升': 4, '拉升': 3,
            '突破': 3, '创新高': 4, '强势': 3, '反弹': 2, '拉升': 3, '拉升': 3,
            
            # 利好相关
            '利好': 3, '利好': 3, '利好': 3, '利好': 3, '利好': 3, '利好': 3,
            '看好': 3, '推荐': 3, '买入': 3, '加仓': 3, '持有': 2, '看好': 3,
            
            # 盈利相关
            '盈利': 3, '赚钱': 3, '收益': 2, '利润': 2, '营收': 2, '业绩': 2,
            '分红': 2, '派息': 2, '送股': 2,
            
            # 机会相关
            '机会': 2, '机遇': 2, '潜力': 2, '前景': 2, '发展': 2, '成长': 2,
            '价值': 2, '低估': 3, '便宜': 2, '性价比': 2
        }
        
        self.negative_words = {
            # 下跌相关
            '下跌': -3, '跌停': -4, '大跌': -4, '暴跌': -4, '崩盘': -4, '跳水': -3,
            '跌破': -3, '创新低': -4, '弱势': -3, '回调': -2, '调整': -2,
            
            # 利空相关
            '利空': -3, '看空': -3, '卖出': -3, '减仓': -3, '清仓': -4, '止损': -2,
            
            # 亏损相关
            '亏损': -3, '亏钱': -3, '亏损': -3, '亏损': -3, '亏损': -3, '亏损': -3,
            '亏损': -3, '亏损': -3, '亏损': -3, '亏损': -3, '亏损': -3,
            
            # 风险相关
            '风险': -2, '危险': -2, '警告': -2, '警惕': -2, '谨慎': -1, '担忧': -2,
            '恐慌': -3, '恐惧': -3, '焦虑': -2
        }
        
        self.intensifiers = {
            '非常': 1.5, '极其': 2.0, '特别': 1.3, '相当': 1.2, '很': 1.2,
            '太': 1.3, '超级': 1.8, '特别': 1.3, '十分': 1.4, '极其': 2.0
        }
        
        self.negations = {'不', '没', '无', '非', '莫', '勿', '别', '未', '否', '休'}
        
        # 初始化jieba
        try:
            jieba.initialize()
        except Exception as e:
            logger.warning(f"jieba初始化失败: {e}")
    
    def analyze_sentiment(self, text: str) -> Dict:
        """
        分析文本情绪
        
        Args:
            text: 输入文本
            
        Returns:
            Dict: 情绪分析结果
        """
        if not text or not text.strip():
            return {
                'sentiment': 'neutral',
                'score': 0.0,
                'confidence': 0.0,
                'positive_score': 0.0,
                'negative_score': 0.0,
                'keywords': []
            }
        
        try:
            # 文本预处理
            processed_text = self._preprocess_text(text)
            
            # 分词
            words = list(jieba.cut(processed_text))
            
            # 计算情绪分数
            sentiment_result = self._calculate_sentiment(words)
            
            # 提取关键词
            keywords = self._extract_keywords(words, sentiment_result['sentiment'])
            
            # 计算置信度
            confidence = self._calculate_confidence(sentiment_result, len(words))
            
            return {
                'sentiment': sentiment_result['sentiment'],
                'score': sentiment_result['score'],
                'confidence': confidence,
                'positive_score': sentiment_result['positive_score'],
                'negative_score': sentiment_result['negative_score'],
                'keywords': keywords,
                'text_length': len(text)
            }
            
        except Exception as e:
            logger.error(f"情绪分析失败: {e}")
            return self._get_default_result()
    
    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """
        批量分析文本情绪
        
        Args:
            texts: 文本列表
            
        Returns:
            List[Dict]: 批量分析结果
        """
        return [self.analyze_sentiment(text) for text in texts]
    
    def _preprocess_text(self, text: str) -> str:
        """文本预处理"""
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除特殊字符和表情
        text = re.sub(r'[^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a]', '', text)
        
        # 转换为小写
        text = text.lower()
        
        return text.strip()
    
    def _calculate_sentiment(self, words: List[str]) -> Dict:
        """计算情绪分数"""
        positive_score = 0.0
        negative_score = 0.0
        
        # 遍历分词结果
        for i, word in enumerate(words):
            word_score = 0
            
            # 检查是否在积极词典中
            if word in self.positive_words:
                base_score = self.positive_words[word]
                
                # 检查前一个词是否是加强词
                if i > 0 and words[i-1] in self.intensifiers:
                    base_score *= self.intensifiers[words[i-1]]
                
                # 检查前一个词是否是否定词
                if i > 0 and words[i-1] in self.negations:
                    base_score *= -1
                
                word_score = base_score
            
            # 检查是否在消极词典中
            elif word in self.negative_words:
                base_score = self.negative_words[word]
                
                # 检查前一个词是否是加强词
                if i > 0 and words[i-1] in self.intensifiers:
                    base_score *= self.intensifiers[words[i-1]]
                
                # 检查前一个词是否是否定词
                if i > 0 and words[i-1] in self.negations:
                    base_score *= -1
                
                word_score = base_score
            
            # 累加分数
            if word_score > 0:
                positive_score += word_score
            elif word_score < 0:
                negative_score += abs(word_score)
        
        # 计算最终情绪
        total_score = positive_score - negative_score
        
        if total_score > 0.5:
            sentiment = 'positive'
        elif total_score < -0.5:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        return {
            'sentiment': sentiment,
            'score': total_score,
            'positive_score': positive_score,
            'negative_score': negative_score
        }
    
    def _extract_keywords(self, words: List[str], sentiment: str) -> List[str]:
        """提取关键词"""
        # 根据情绪类型提取相关关键词
        if sentiment == 'positive':
            keywords = [word for word in words if word in self.positive_words]
        elif sentiment == 'negative':
            keywords = [word for word in words if word in self.negative_words]
        else:
            # 中性情绪提取高频词
            word_freq = Counter(words)
            keywords = [word for word, freq in word_freq.most_common(5)]
        
        return keywords[:5]  # 限制关键词数量
    
    def _calculate_confidence(self, sentiment_result: Dict, text_length: int) -> float:
        """计算置信度"""
        if text_length == 0:
            return 0.0
        
        total_score = abs(sentiment_result['positive_score']) + abs(sentiment_result['negative_score'])
        
        # 基于文本长度和情绪强度计算置信度
        length_factor = min(text_length / 100, 1.0)
        intensity_factor = min(total_score / 10, 1.0)
        
        confidence = (length_factor * 0.3 + intensity_factor * 0.7)
        return min(confidence, 1.0)
    
    def _get_default_result(self) -> Dict:
        """获取默认结果"""
        return {
            'sentiment': 'neutral',
            'score': 0.0,
            'confidence': 0.0,
            'positive_score': 0.0,
            'negative_score': 0.0,
            'keywords': []
        }
    
    def calculate_sentiment_score(self, texts: List[str]) -> float:
        """
        计算整体情绪分数
        
        Args:
            texts: 文本列表
            
        Returns:
            float: 整体情绪分数 (-10 到 10)
        """
        if not texts:
            return 0.0
        
        total_score = 0.0
        valid_count = 0
        
        for text in texts:
            if text and text.strip():
                result = self.analyze_sentiment(text)
                # 加权平均，置信度高的权重更大
                weight = result['confidence']
                total_score += result['score'] * weight
                valid_count += weight
        
        if valid_count == 0:
            return 0.0
        
        # 归一化到-10到10的范围
        avg_score = total_score / valid_count
        return max(-10, min(10, avg_score))
    
    def analyze_stock_sentiment(self, news_list: List[Dict], forum_list: List[Dict]) -> Dict:
        """
        分析股票整体情绪
        
        Args:
            news_list: 新闻列表
            forum_list: 论坛讨论列表
            
        Returns:
            Dict: 股票整体情绪分析
        """
        # 分析新闻情绪
        news_texts = [item.get('title', '') + ' ' + item.get('content', '') for item in news_list]
        news_sentiment = self.calculate_sentiment_score(news_texts)
        
        # 分析论坛情绪
        forum_texts = [item.get('title', '') + ' ' + item.get('content', '') for item in forum_list]
        forum_sentiment = self.calculate_sentiment_score(forum_texts)
        
        # 加权计算整体情绪
        # 新闻权重60%，论坛权重40%
        overall_sentiment = news_sentiment * 0.6 + forum_sentiment * 0.4
        
        # 计算情绪等级
        if overall_sentiment >= 3:
            sentiment_level = 'very_positive'
        elif overall_sentiment >= 1:
            sentiment_level = 'positive'
        elif overall_sentiment >= -1:
            sentiment_level = 'neutral'
        elif overall_sentiment >= -3:
            sentiment_level = 'negative'
        else:
            sentiment_level = 'very_negative'
        
        return {
            'overall_score': overall_sentiment,
            'sentiment_level': sentiment_level,
            'news_sentiment': news_sentiment,
            'forum_sentiment': forum_sentiment,
            'news_count': len(news_list),
            'forum_count': len(forum_list),
            'confidence': min(1.0, (len(news_list) + len(forum_list)) / 20)
        }


# 测试用例
if __name__ == "__main__":
    analyzer = SentimentAnalyzer()
    
    # 测试单个文本
    test_texts = [
        "科蓝软件今天大涨5%，业绩超预期，建议买入",
        "这只股票风险很大，可能要继续下跌",
        "市场表现一般，暂时观望"
    ]
    
    for text in test_texts:
        result = analyzer.analyze_sentiment(text)
        print(f"文本: {text}")
        print(f"情绪: {result['sentiment']}, 分数: {result['score']}, 置信度: {result['confidence']}")
        print(f"关键词: {result['keywords']}")
        print("-" * 50)
    
    # 测试批量分析
    texts = [
        "股票上涨，前景看好",
        "市场下跌，需要谨慎",
        "表现平稳"
    ]
    batch_results = analyzer.analyze_batch(texts)
    print("批量分析结果:", batch_results)
    
    # 测试整体情绪计算
    overall_score = analyzer.calculate_sentiment_score(texts)
    print(f"整体情绪分数: {overall_score}")