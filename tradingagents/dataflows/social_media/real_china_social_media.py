"""
中国社交媒体真实数据源统一接口
整合多个真实数据源，提供统一的社交媒体情绪分析
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import os

# 导入各个数据源
from .sina_finance_api import SinaFinanceAPI
from .eastmoney_scraper import EastMoneyScraper
from .sentiment_analyzer import SentimentAnalyzer

logger = logging.getLogger(__name__)


class RealChinaSocialMedia:
    """中国社交媒体真实数据源统一接口"""
    
    def __init__(self):
        self.sina_api = SinaFinanceAPI()
        self.eastmoney_scraper = EastMoneyScraper()
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # 配置参数
        self.request_delay = float(os.getenv('SOCIAL_MEDIA_REQUEST_DELAY', 2.0))
        self.cache_ttl = int(os.getenv('SOCIAL_MEDIA_CACHE_TTL', 3600))
        self.max_retries = int(os.getenv('SOCIAL_MEDIA_MAX_RETRIES', 3))
        
        # 数据源权重
        self.data_source_weights = {
            'sina_finance': 0.4,
            'eastmoney': 0.6
        }
        
        # LLM分析器
        try:
            from .llm_sentiment_analyzer import LLMSentimentAnalyzer
            self.llm_analyzer = LLMSentimentAnalyzer()
            self.llm_enabled = True
        except Exception as e:
            logger.warning(f"LLM情绪分析器初始化失败: {e}")
            self.llm_enabled = False
    
    async def get_social_sentiment(self, symbol: str, days: int = 3) -> Dict:
        """
        获取股票社交媒体情绪数据
        
        Args:
            symbol: 股票代码
            days: 获取最近几天的数据
            
        Returns:
            Dict: 社交媒体情绪分析结果
        """
        try:
            logger.info(f"开始获取 {symbol} 的社交媒体情绪数据...")
            
            start_time = datetime.now()
            
            # 并行获取各类数据
            news_task = self.sina_api.get_stock_news(symbol, days)
            forum_task = self.eastmoney_scraper.get_forum_discussions(symbol, days)
            
            news_data, forum_data = await asyncio.gather(news_task, forum_task)
            
            # 数据验证
            news_data = self._validate_data(news_data, 'news')
            forum_data = self._validate_data(forum_data, 'forum')
            
# 基础情绪分析
            basic_sentiment = self.sentiment_analyzer.analyze_stock_sentiment(news_data, forum_data)
            
            # 使用LLM进行深度情绪分析（如果可用）
            try:
                if self.llm_enabled:
                    enhanced_sentiment = await self._enhance_with_llm(basic_sentiment, symbol, news_data, forum_data)
                    sentiment_result = enhanced_sentiment
                    analysis_method = 'enhanced_llm_analysis'
                else:
                    sentiment_result = basic_sentiment
                    analysis_method = 'basic_sentiment'
            except Exception as e:
                logger.warning(f"LLM增强分析失败，使用基础分析: {e}")
                sentiment_result = basic_sentiment
                analysis_method = 'basic_sentiment'
            
            # 构建增强的统一返回格式
            result = self._build_enhanced_response(
                symbol, news_data, forum_data, sentiment_result, start_time, analysis_method
            )
            
            logger.info(f"成功获取 {symbol} 的社交媒体数据，共 {len(news_data)} 条新闻，{len(forum_data)} 条讨论")
            
            return result
            
        except Exception as e:
            logger.error(f"获取社交媒体情绪数据失败: {e}")
            return self._get_fallback_response(symbol, str(e))
    
    async def get_aggregated_sentiment(self, symbols: List[str], days: int = 3) -> Dict:
        """
        获取多个股票的聚合情绪数据
        
        Args:
            symbols: 股票代码列表
            days: 获取最近几天的数据
            
        Returns:
            Dict: 聚合情绪分析结果
        """
        try:
            logger.info(f"开始获取 {len(symbols)} 个股票的聚合情绪数据...")
            
            # 并行获取所有股票数据
            tasks = [self.get_social_sentiment(symbol, days) for symbol in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            valid_results = []
            for symbol, result in zip(symbols, results):
                if isinstance(result, dict) and 'error' not in result:
                    valid_results.append(result)
                else:
                    logger.warning(f"获取 {symbol} 数据失败，使用备用数据")
                    valid_results.append(self._get_fallback_response(symbol, str(result)))
            
            # 计算聚合情绪
            aggregated = self._calculate_aggregated_sentiment(valid_results)
            
            return aggregated
            
        except Exception as e:
            logger.error(f"获取聚合情绪数据失败: {e}")
            return {'error': str(e), 'symbols': symbols}
    
    def _validate_data(self, data: List[Dict], data_type: str) -> List[Dict]:
        """验证数据有效性"""
        if not isinstance(data, list):
            return []
        
        validated = []
        for item in data:
            if isinstance(item, dict) and item.get('title'):
                # 确保必要字段存在
                validated_item = {
                    'title': str(item.get('title', ''))[:200],
                    'content': str(item.get('content', ''))[:1000],
                    'url': str(item.get('url', ''))[:500],
                    'publish_time': str(item.get('publish_time', ''))[:19],
                    'source': str(item.get('source', data_type)),
                    'sentiment': str(item.get('sentiment', 'neutral'))
                }
                
                # 添加额外字段
                if data_type == 'forum':
                    validated_item.update({
                        'author': str(item.get('author', '匿名')),
                        'read_count': int(item.get('read_count', 0)),
                        'reply_count': int(item.get('reply_count', 0)),
                        'like_count': int(item.get('like_count', 0)),
                        'platform': str(item.get('platform', '东方财富股吧'))
                    })
                
                validated.append(validated_item)
        
        return validated
    
    def _build_enhanced_response(self, symbol: str, news_data: List[Dict], 
                              forum_data: List[Dict], sentiment_result: Dict,
                              start_time: datetime, analysis_method: str) -> Dict:
        """构建增强的统一返回格式"""
        end_time = datetime.now()
        
        # 获取真实股票信息
        stock_info = self._get_real_stock_info(symbol)
        
        # 计算情绪等级描述
        sentiment_mapping = {
            'very_positive': '极度乐观',
            'positive': '乐观',
            'neutral': '中性',
            'negative': '悲观',
            'very_negative': '极度悲观'
        }
        
        # 提取热点话题
        hot_topics = self._extract_hot_topics(news_data + forum_data)
        
        # 计算关键统计指标
        total_interactions = sum(
            item.get('read_count', 0) + item.get('reply_count', 0) + item.get('like_count', 0)
            for item in forum_data
        )
        
        return {
            'symbol': symbol,
            'stock_name': stock_info['name'],
            'industry': stock_info['industry'],
            'source': 'real_data',
            'timestamp': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'query_time_ms': int((end_time - start_time).total_seconds() * 1000),
            
            # 情绪分析结果
            'sentiment_analysis': {
                'overall_score': round(sentiment_result['overall_score'], 2),
                'sentiment_level': sentiment_result['sentiment_level'],
                'sentiment_description': sentiment_mapping.get(sentiment_result['sentiment_level'], '未知'),
                'confidence': round(sentiment_result['confidence'], 2),
                'news_sentiment': round(sentiment_result['news_sentiment'], 2),
                'forum_sentiment': round(sentiment_result['forum_sentiment'], 2)
            },
            
            # 数据统计
            'data_statistics': {
                'total_news': len(news_data),
                'total_forum_posts': len(forum_data),
                'total_interactions': total_interactions,
                'data_sources': ['新浪财经', '东方财富股吧']
            },
            
            # 热点话题
            'hot_topics': hot_topics,
            
            # 详细数据
            'detailed_data': {
                'news': news_data[:10],  # 限制返回数量
                'forum_discussions': forum_data[:10]
            },
            
            # 时间范围
            'time_range': {
                'start_date': (end_time - timedelta(days=3)).strftime('%Y-%m-%d'),
                'end_date': end_time.strftime('%Y-%m-%d')
            },
            
            # 数据来源透明度
            'data_transparency': {
                'news_source': '新浪财经RSS',
                'forum_source': '东方财富股吧',
                'last_updated': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'update_frequency': '实时'
            }
        }
    
    def _calculate_aggregated_sentiment(self, results: List[Dict]) -> Dict:
        """计算聚合情绪"""
        if not results:
            return {'error': '无有效数据'}
        
        # 提取情绪分数
        scores = [r['sentiment_analysis']['overall_score'] for r in results]
        confidences = [r['sentiment_analysis']['confidence'] for r in results]
        
        # 加权平均
        total_score = sum(score * conf for score, conf in zip(scores, confidences))
        total_confidence = sum(confidences)
        
        if total_confidence == 0:
            avg_score = 0.0
        else:
            avg_score = total_score / total_confidence
        
        # 情绪等级
        if avg_score >= 3:
            level = 'very_positive'
        elif avg_score >= 1:
            level = 'positive'
        elif avg_score >= -1:
            level = 'neutral'
        elif avg_score >= -3:
            level = 'negative'
        else:
            level = 'very_negative'
        
        return {
            'aggregated_score': round(avg_score, 2),
            'sentiment_level': level,
            'total_stocks': len(results),
            'average_confidence': round(sum(confidences) / len(confidences), 2),
            'individual_results': results
        }
    
    async def _enhance_with_llm(self, basic_sentiment: Dict, symbol: str, news_data: List[Dict], forum_data: List[Dict]) -> Dict:
        """
        使用LLM进行深度情绪分析增强
        
        Args:
            basic_sentiment: 基础情绪分析结果
            symbol: 股票代码
            news_data: 新闻数据
            forum_data: 论坛数据
            
        Returns:
            Dict: LLM增强后的情绪分析结果
        """
        try:
            if not self.llm_enabled or not self.llm_analyzer:
                return basic_sentiment
            
            # 获取真实股票信息
            stock_info = await self._get_real_stock_info(symbol)
            stock_name = stock_info.get('name', f'股票{symbol}')
            industry = stock_info.get('industry', '未知行业')
            
            # 准备LLM分析内容
            content_data = {
                'symbol': symbol,
                'stock_name': stock_name,
                'industry': industry,
                'news': news_data,
                'forum_discussions': forum_data,
                'statistics': {
                    'total_news': len(news_data),
                    'total_forum_posts': len(forum_data),
                    'basic_sentiment_score': basic_sentiment.get('overall_score', 0)
                }
            }
            
            # 使用LLM进行分析
            llm_result = await self.llm_analyzer.analyze_sentiment(symbol, content_data)
            
            # 合并LLM结果和基础结果
            enhanced_sentiment = basic_sentiment.copy()
            if 'sentiment_analysis' in llm_result:
                enhanced_sentiment.update(llm_result['sentiment_analysis'])
            
            return enhanced_sentiment
            
        except Exception as e:
            logger.warning(f"LLM增强分析失败: {e}")
            return basic_sentiment

    def _extract_hot_topics(self, data: List[Dict]) -> List[str]:
        """提取热点话题"""
        try:
            all_text = ' '.join([item.get('title', '') + ' ' + item.get('content', '') for item in data])
            
            # 简单的关键词提取
            keywords = ['数字化转型', '金融科技', '银行IT', '区块链', '人工智能', 
                       '云计算', '大数据', '政策利好', '业绩预增', '机构调研']
            
            hot_topics = []
            for keyword in keywords:
                if keyword in all_text:
                    hot_topics.append(keyword)
            
            return hot_topics[:5]  # 返回最多5个热点话题
            
        except Exception as e:
            logger.error(f"提取热点话题失败: {e}")
            return []
    
    def _get_real_stock_info(self, symbol: str) -> Dict:
        """获取真实股票信息 - 同步版本避免事件循环冲突"""
        try:
            # 使用同步方式获取股票信息
            stock_info_map = {
                '300663': {'name': '科蓝软件', 'industry': '软件开发', 'area': '北京'},
                '000001': {'name': '平安银行', 'industry': '银行', 'area': '深圳'},
                '600036': {'name': '招商银行', 'industry': '银行', 'area': '深圳'},
                '000858': {'name': '五粮液', 'industry': '白酒', 'area': '四川'},
                '601127': {'name': '小康股份', 'industry': '汽车制造', 'area': '重庆'},
                '002415': {'name': '海康威视', 'industry': '电子制造', 'area': '浙江'},
                '000002': {'name': '万科A', 'industry': '房地产', 'area': '深圳'},
                '600519': {'name': '贵州茅台', 'industry': '白酒', 'area': '贵州'},
                '601318': {'name': '中国平安', 'industry': '保险', 'area': '深圳'},
                '000333': {'name': '美的集团', 'industry': '家电制造', 'area': '广东'}
            }
            
            # 返回映射的股票信息
            if symbol in stock_info_map:
                return {
                    'symbol': symbol,
                    'name': stock_info_map[symbol]['name'],
                    'industry': stock_info_map[symbol]['industry'],
                    'area': stock_info_map[symbol]['area']
                }
            
            # 尝试从数据源获取
            try:
                from tradingagents.dataflows.tushare_adapter import get_tushare_adapter
                adapter = get_tushare_adapter()
                info = adapter.get_stock_info(symbol)
                if info and info.get('name'):
                    return {
                        'symbol': symbol,
                        'name': info['name'],
                        'industry': info.get('industry', '综合行业'),
                        'area': info.get('area', '未知地区')
                    }
            except Exception:
                pass
            
            # 返回默认信息
            return {
                'symbol': symbol,
                'name': f'{symbol}股票',
                'industry': '综合行业',
                'area': '未知地区'
            }
            
        except Exception as e:
            logger.warning(f"获取股票信息失败: {e}，使用默认信息")
            return {
                'symbol': symbol,
                'name': f'{symbol}股票',
                'industry': '综合行业',
                'area': '未知地区'
            }

    def _get_fallback_response(self, symbol: str, error_msg: str) -> Dict:
        """获取备用响应"""
        return {
            'symbol': symbol,
            'source': 'fallback',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': error_msg,
            'message': '使用模拟数据作为备用',
            'sentiment_analysis': {
                'overall_score': 0.0,
                'sentiment_level': 'neutral',
                'sentiment_description': '数据获取失败，使用中性评估',
                'confidence': 0.0
            },
            'data_statistics': {
                'total_news': 0,
                'total_forum_posts': 0,
                'total_interactions': 0,
                'data_sources': []
            },
            'hot_topics': [],
            'detailed_data': {
                'news': [],
                'forum_discussions': []
            }
        }


# 测试用例
async def test_real_social_media():
    """测试真实社交媒体数据"""
    social_media = RealChinaSocialMedia()
    
    # 测试单个股票
    print("测试单个股票情绪分析...")
    result = await social_media.get_social_sentiment("300663", days=1)
    
    print(f"股票代码: {result['symbol']}")
    print(f"情绪分数: {result['sentiment_analysis']['overall_score']}")
    print(f"情绪等级: {result['sentiment_analysis']['sentiment_description']}")
    print(f"新闻数量: {result['data_statistics']['total_news']}")
    print(f"论坛讨论: {result['data_statistics']['total_forum_posts']}")
    print(f"热点话题: {result['hot_topics']}")
    
    # 测试多个股票
    print("\n测试多个股票聚合分析...")
    symbols = ["000001", "300663", "600036"]
    aggregated = await social_media.get_aggregated_sentiment(symbols, days=1)
    
    print(f"聚合情绪分数: {aggregated.get('aggregated_score', 'N/A')}")
    print(f"分析股票数量: {aggregated.get('total_stocks', 0)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_real_social_media())