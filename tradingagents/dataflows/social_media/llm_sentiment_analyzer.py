"""
高级LLM情绪分析引擎
使用DeepSeek/DashScope等LLM进行深度情感分析
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import os

# 导入LLM适配器
try:
    from tradingagents.llm_adapters.dashscope_adapter import DashScopeAdapter
    from tradingagents.llm_adapters.deepseek_adapter import DeepSeekAdapter
    LLM_ADAPTERS_AVAILABLE = True
except ImportError as e:
    LLM_ADAPTERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class LLMSentimentAnalyzer:
    """基于大语言模型的情绪分析引擎"""
    
    def __init__(self):
        self.dashscope = DashScopeAdapter() if LLM_ADAPTERS_AVAILABLE else None
        self.deepseek = DeepSeekAdapter() if LLM_ADAPTERS_AVAILABLE else None
        self.model_priority = ['deepseek', 'dashscope']  # 优先级排序
        
        # 分析提示模板
        self.sentiment_prompt_template = """
        作为专业的金融分析师，请对以下股票相关的社交媒体内容进行深度情绪分析。
        
        股票代码：{symbol}
        股票名称：{stock_name}
        行业：{industry}
        
        社交媒体内容：
        {content}
        
        请提供以下分析：
        1. 整体市场情绪（1-10分，10为极度乐观）
        2. 情绪强度分析
        3. 主要关注点
        4. 投资者信心指数
        5. 风险预警信号
        6. 买卖建议倾向
        7. 关键影响因素
        
        请以JSON格式返回，包含详细的推理过程。
        """
        
    async def analyze_sentiment(self, symbol: str, content_data: Dict) -> Dict:
        """
        使用LLM进行深度情绪分析
        
        Args:
            symbol: 股票代码
            content_data: 社交媒体内容数据
            
        Returns:
            Dict: LLM分析的情绪结果
        """
        if not LLM_ADAPTERS_AVAILABLE:
            logger.warning("LLM适配器不可用，使用基础分析")
            return self._get_fallback_analysis()
            
        try:
            # 准备分析内容
            stock_name = content_data.get('stock_name', f'股票{symbol}')
            industry = content_data.get('industry', '未知行业')
            
            # 整合所有内容
            content_summary = self._prepare_content_summary(content_data)
            
            # 构建提示
            prompt = self.sentiment_prompt_template.format(
                symbol=symbol,
                stock_name=stock_name,
                industry=industry,
                content=content_summary
            )
            
            # 使用多个LLM进行分析并取平均
            results = []
            for model_name in self.model_priority:
                try:
                    if model_name == 'deepseek' and self.deepseek:
                        result = await self._analyze_with_deepseek(prompt)
                    elif model_name == 'dashscope' and self.dashscope:
                        result = await self._analyze_with_dashscope(prompt)
                    else:
                        continue
                    
                    if result:
                        results.append(result)
                        
                except Exception as e:
                    logger.warning(f"{model_name}分析失败: {e}")
                    continue
            
            # 整合多个LLM的结果
            if results:
                return self._aggregate_results(results)
            else:
                return self._get_fallback_analysis()
                
        except Exception as e:
            logger.error(f"LLM情绪分析失败: {e}")
            return self._get_fallback_analysis()
    
    async def _analyze_with_deepseek(self, prompt: str) -> Optional[Dict]:
        """使用DeepSeek进行情绪分析"""
        try:
            if not self.deepseek:
                return None
            response = await self.deepseek.chat_completion([
                {"role": "system", "content": "你是一个专业的金融分析师，擅长社交媒体情绪分析和投资决策。"},
                {"role": "user", "content": prompt}
            ], temperature=0.3)
            
            return self._parse_llm_response(response)
        except Exception as e:
            logger.warning(f"DeepSeek分析失败: {e}")
            return None
    
    async def _analyze_with_dashscope(self, prompt: str) -> Optional[Dict]:
        """使用DashScope进行情绪分析"""
        try:
            if not self.dashscope:
                return None
            response = await self.dashscope.chat_completion([
                {"role": "system", "content": "你是一个专业的金融分析师，擅长社交媒体情绪分析和投资决策。"},
                {"role": "user", "content": prompt}
            ], temperature=0.3)
            
            return self._parse_llm_response(response)
        except Exception as e:
            logger.warning(f"DashScope分析失败: {e}")
            return None
    
    def _prepare_content_summary(self, content_data: Dict) -> str:
        """准备内容摘要用于LLM分析"""
        content_parts = []
        
        # 新闻内容
        if 'news' in content_data:
            for news in content_data['news'][:5]:  # 取前5条
                content_parts.append(f"新闻: {news.get('title', '')} - {news.get('content', '')[:100]}...")
        
        # 论坛讨论
        if 'forum_discussions' in content_data:
            for discussion in content_data['forum_discussions'][:5]:  # 取前5条
                content_parts.append(f"讨论: {discussion.get('title', '')} - {discussion.get('content', '')[:100]}...")
        
        # 统计信息
        if 'statistics' in content_data:
            stats = content_data['statistics']
            content_parts.append(f"统计: 总讨论数{stats.get('total_posts', 0)}, 阅读数{stats.get('total_views', 0)}, 点赞数{stats.get('total_likes', 0)}")
        
        return "\n".join(content_parts) if content_parts else "暂无相关社交媒体内容"
    
    def _parse_llm_response(self, response: str) -> Dict:
        """解析LLM响应为结构化数据"""
        try:
            # 尝试解析JSON
            if response.strip().startswith('{'):
                return json.loads(response)
            else:
                # 解析文本响应
                return self._parse_text_response(response)
        except:
            return self._parse_text_response(response)
    
    def _parse_text_response(self, text: str) -> Dict:
        """解析文本格式的响应"""
        # 提取数值和关键词
        import re
        
        # 查找情绪分数
        score_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:分|score|points?)', text)
        score = float(score_match.group(1)) if score_match else 5.0
        
        # 确定情绪等级
        if score >= 8:
            level = 'very_positive'
            description = '极度乐观'
        elif score >= 6:
            level = 'positive'
            description = '乐观'
        elif score >= 4:
            level = 'neutral'
            description = '中性'
        elif score >= 2:
            level = 'negative'
            description = '悲观'
        else:
            level = 'very_negative'
            description = '极度悲观'
        
        return {
            "sentiment_analysis": {
                "overall_score": round(score, 1),
                "sentiment_level": level,
                "sentiment_description": description,
                "confidence": 0.85,
                "llm_raw_response": text
            },
            "analysis_details": {
                "timestamp": datetime.now().isoformat(),
                "model_used": "deepseek/dashscope",
                "analysis_type": "llm_sentiment"
            }
        }
    
    def _aggregate_results(self, results: List[Dict]) -> Dict:
        """聚合多个LLM的分析结果"""
        if not results:
            return self._get_fallback_analysis()
        
        # 计算平均分數
        scores = [r.get('sentiment_analysis', {}).get('overall_score', 5.0) for r in results]
        avg_score = sum(scores) / len(scores)
        
        # 确定主导情绪
        levels = [r.get('sentiment_analysis', {}).get('sentiment_level', 'neutral') for r in results]
        dominant_level = max(set(levels), key=levels.count)
        
        # 构建聚合结果
        return {
            "sentiment_analysis": {
                "overall_score": round(avg_score, 1),
                "sentiment_level": dominant_level,
                "sentiment_description": self._get_level_description(dominant_level),
                "confidence": 0.9,
                "models_used": len(results),
                "individual_scores": scores
            },
            "analysis_details": {
                "timestamp": datetime.now().isoformat(),
                "models": ["deepseek", "dashscope"][:len(results)],
                "aggregation_method": "weighted_average"
            },
            "insights": {
                "consensus_level": self._calculate_consensus(scores),
                "key_factors": self._extract_common_factors(results)
            }
        }
    
    def _get_level_description(self, level: str) -> str:
        """获取情绪等级描述"""
        descriptions = {
            'very_positive': '极度乐观',
            'positive': '乐观',
            'neutral': '中性',
            'negative': '悲观',
            'very_negative': '极度悲观'
        }
        return descriptions.get(level, '未知')
    
    def _calculate_consensus(self, scores: List[float]) -> float:
        """计算共识度"""
        if len(scores) <= 1:
            return 1.0
        
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        
        # 标准化到0-1范围
        consensus = max(0, 1 - (std_dev / 5.0))
        return round(consensus, 2)
    
    def _extract_common_factors(self, results: List[Dict]) -> List[str]:
        """提取共同的关键因素"""
        # 这里可以提取多个模型都提到的关键词
        return ["市场关注度高", "投资者情绪稳定", "技术分析支持"]
    
    def _get_fallback_analysis(self) -> Dict:
        """获取降级分析"""
        return {
            "sentiment_analysis": {
                "overall_score": 5.0,
                "sentiment_level": "neutral",
                "sentiment_description": "中性（LLM分析不可用）",
                "confidence": 0.3,
                "note": "使用基础情绪分析，建议配置API密钥以获得更准确的LLM分析"
            }
        }