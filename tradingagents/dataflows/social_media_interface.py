"""
新的社交媒体数据接口
集成真实的网页爬虫数据源
"""

from typing import Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_stock_news_openai(ticker: str, curr_date: str) -> str:
    """
    获取股票新闻和社交媒体情绪（替换原有接口）
    
    Args:
        ticker: 股票代码
        curr_date: 当前日期
        
    Returns:
        格式化的分析结果
    """
    try:
        # 导入新的社交媒体分析模块
        from tradingagents.social_sentiment import get_stock_social_sentiment
        
        logger.info(f"开始获取股票 {ticker} 的真实社交媒体数据")
        
        # 获取真实的社交媒体情绪数据
        result = get_stock_social_sentiment(ticker, total_limit=80)
        
        if not result['success']:
            logger.warning(f"社交媒体数据获取失败: {ticker}, 原因: {result.get('error', '未知错误')}")
            return _generate_fallback_response(ticker, curr_date, result.get('error', '数据获取失败'))
        
        # 格式化为分析报告
        formatted_report = _format_social_media_report(result, ticker, curr_date)
        
        logger.info(f"✅ 成功获取并格式化股票 {ticker} 的社交媒体数据，数据质量: {result.get('data_quality_score', 0)}")
        return formatted_report
        
    except Exception as e:
        logger.error(f"获取社交媒体数据时发生错误: {ticker}, 错误: {e}")
        return _generate_fallback_response(ticker, curr_date, f"系统错误: {str(e)}")


def _format_social_media_report(result: Dict, ticker: str, curr_date: str) -> str:
    """格式化社交媒体分析报告"""
    
    sentiment_analysis = result.get('sentiment_analysis', {})
    data_quality_score = result.get('data_quality_score', 0)
    confidence_level = result.get('confidence_level', '低')
    
    # 构建数据源信息
    data_sources = result.get('data_sources', {})
    source_info_lines = []
    total_comments = 0
    
    for source_name, source_data in data_sources.items():
        if source_data.get('success'):
            count = source_data.get('count', 0)
            total_comments += count
            # 转换数据源名称为中文
            source_display_names = {
                'sina_finance': '新浪财经',
                'eastmoney': '东方财富',
                'xueqiu': '雪球',
                'baidu_gushitong': '百度股市通',
                'simple_discussion': '综合讨论'
            }
            display_name = source_display_names.get(source_name, source_name)
            source_info_lines.append(f"- {display_name}: {count}条评论")
    
    if not source_info_lines:
        source_info_lines.append("- 暂无有效数据源")
    
    # 构建详细报告
    report = f"""
## {ticker} 社交媒体情绪分析报告
**分析日期**: {curr_date}
**数据质量**: {data_quality_score:.2f}/1.0 (置信度: {confidence_level})

### 📡 数据源统计
{chr(10).join(source_info_lines)}
**总计**: {total_comments}条原始评论

### 📊 情绪分析概览
- **总评论数**: {sentiment_analysis.get('total_comments', 0)} 条真实评论
- **平均情绪分数**: {sentiment_analysis.get('average_sentiment', 0):.3f} (-1到1之间)
- **正面情绪比例**: {sentiment_analysis.get('positive_ratio', 0):.1%}
- **负面情绪比例**: {sentiment_analysis.get('negative_ratio', 0):.1%}
- **中性观点比例**: {sentiment_analysis.get('neutral_ratio', 0):.1%}

### 💭 投资者情绪总结
{result.get('sentiment_summary', '暂无详细分析')}

### 🔥 关键观点摘录
"""
    
    # 添加关键观点
    key_opinions = result.get('key_opinions', [])
    if key_opinions:
        for i, opinion in enumerate(key_opinions[:3], 1):
            report += f"""
**观点 {i}** (👍 {opinion.get('likes', 0)}) - {opinion.get('source', '')}
> {opinion['content']}
"""
    else:
        report += "\n暂无突出观点"
    
    # 添加情绪趋势
    sentiment_trend = result.get('sentiment_trend', {})
    if sentiment_trend:
        report += f"""

### 📈 情绪趋势分析
- **趋势方向**: {sentiment_trend.get('description', '趋势不明显')}
- **变化幅度**: {sentiment_trend.get('change_magnitude', 0):.3f}
"""
    
    # 添加高频关键词
    top_positive = sentiment_analysis.get('top_positive_keywords', [])
    top_negative = sentiment_analysis.get('top_negative_keywords', [])
    
    if top_positive or top_negative:
        report += "\n### 🏷️ 高频关键词"
        
        if top_positive:
            pos_words = [f"{word}({count})" for word, count in top_positive[:5]]
            report += f"\n**正面词汇**: {', '.join(pos_words)}"
            
        if top_negative:
            neg_words = [f"{word}({count})" for word, count in top_negative[:5]]
            report += f"\n**负面词汇**: {', '.join(neg_words)}"
    
    report += f"""

### ⚠️ 分析说明
- 本分析基于真实的社交媒体平台数据
- 数据已经过垃圾信息过滤和质量筛选
- 情绪分数基于中文语义分析和关键词识别
- 数据获取时间: {result.get('timestamp', datetime.now().isoformat())}
- 建议结合基本面和技术面分析进行投资决策
"""
    
    return report.strip()


def _generate_fallback_response(ticker: str, curr_date: str, error_reason: str) -> str:
    """生成回退响应"""
    
    return f"""
## {ticker} 社交媒体情绪分析报告
**分析日期**: {curr_date}
**状态**: 数据获取受限

### ⚠️ 数据获取说明
由于以下原因，无法获取实时社交媒体数据：
{error_reason}

### 📋 建议的替代分析方法

**1. 手动监控平台**
- 新浪财经股票页面评论区
- 东方财富股吧相关讨论
- 雪球平台投资者观点
- 同花顺社区讨论

**2. 关注要点**
- 投资者对最新财报的反应
- 行业政策变化的讨论热度
- 机构研报发布后的市场反馈
- 重大事件公告的情绪影响

**3. 情绪判断指标**
- 讨论量变化（关注度）
- 正负面评论比例
- 关键意见领袖观点
- 散户与机构观点差异

### 💡 投资建议
在缺乏实时社交媒体数据的情况下，建议：
1. 重点关注基本面分析和财务数据
2. 结合技术分析判断市场趋势
3. 关注官方公告和权威财经媒体报道
4. 保持理性，避免情绪化投资决策

**注**: 完整的投资者情绪分析需要多维度数据支持，建议综合考虑各种因素。
"""


def get_chinese_social_sentiment(ticker: str, curr_date: str) -> str:
    """
    获取中国社交媒体情绪（兼容接口）
    """
    return get_stock_news_openai(ticker, curr_date)