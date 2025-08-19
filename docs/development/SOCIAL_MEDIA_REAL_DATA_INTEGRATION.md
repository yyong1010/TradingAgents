# 🔄 Social Media Analyst 真实数据源改造技术方案

## 📋 项目概述
将Social Media Analyst从模拟数据升级为真实数据源，采用**免费API优先 + 公共网页爬取**的混合策略，确保在零成本前提下获取真实的中国社交媒体情绪数据。

## 🎯 数据源技术方案

### 1️⃣ 免费API数据源（无需API Key）

#### 📰 新浪财经RSS接口
- **接口地址**: `https://feed.sina.com.cn/api/news/rss`
- **数据类型**: 财经新闻、股票相关报道
- **获取方式**: RSS订阅，无需API Key
- **更新频率**: 实时更新
- **数据格式**: XML/RSS标准格式

#### 🐧 腾讯财经API
- **接口地址**: `https://stock.qq.com/api/hq`
- **数据类型**: 股票新闻、市场热点
- **获取方式**: 公开API，无限制访问
- **更新频率**: 每30分钟
- **数据格式**: JSON

#### 📊 东方财富网公开接口
- **接口地址**: `https://emweb.securities.eastmoney.com/PC_HSF10/NewsResearch/Index`
- **数据类型**: 公司公告、研报、新闻
- **获取方式**: 公开HTTP接口
- **限制**: 无明确限制，合理频率即可

### 2️⃣ 网页爬取策略（公共网页）

#### 🏦 东方财富股吧
- **目标页面**: `https://guba.eastmoney.com/list,股票代码,f_1.html`
- **数据类型**: 投资者讨论、情绪表达
- **爬取内容**: 帖子标题、点赞数、回复数、发布时间
- **反爬策略**: 随机User-Agent + 请求间隔2-5秒

#### 📱 雪球网（简化版）
- **目标页面**: `https://xueqiu.com/S/股票代码`
- **数据类型**: 讨论热度、关注人数变化
- **爬取内容**: 帖子列表、互动数据
- **注意**: 需要处理JavaScript渲染

#### 🔍 微博财经话题
- **目标页面**: `https://s.weibo.com/weibo/股票代码`
- **数据类型**: 社交媒体情绪、热点话题
- **爬取内容**: 微博内容、转发数、点赞数

## 🔧 技术架构设计

### 核心模块结构
```
tradingagents/
└── dataflows/
    ├── social_media/
    │   ├── __init__.py
    │   ├── sina_finance_api.py      # 新浪财经RSS
    │   ├── eastmoney_scraper.py     # 东方财富爬取
    │   ├── tencent_finance_api.py   # 腾讯财经API
    │   ├── weibo_scraper.py         # 微博数据
    │   └── sentiment_analyzer.py    # 情绪分析引擎
    └── real_china_social_media.py   # 统一接口
```

### 数据流架构
```
用户请求 → 数据源选择器 → 多源并行获取 → 数据清洗 → 情绪分析 → 结果合并 → 缓存 → 返回
```

## 🎛️ 环境变量配置

### 无需API Key的配置
```bash
# 可选配置项（不设置也有默认值）
SOCIAL_MEDIA_CACHE_TTL=3600    # 缓存时间（秒）
SOCIAL_MEDIA_REQUEST_DELAY=2   # 请求间隔（秒）
SOCIAL_MEDIA_MAX_RETRIES=3     # 最大重试次数
```

### 预留环境变量（未来扩展用）
```bash
# 预留字段（当前不需要，未来可能用到）
WEIBO_COOKIE=                  # 微博cookie（可选）
XUEQIU_COOKIE=                 # 雪球cookie（可选）
```

## 🔄 降级策略设计

### 四级降级机制
1. **Level 1**: 所有免费API正常
2. **Level 2**: 部分API失效，其余补充
3. **Level 3**: 仅网页爬取可用
4. **Level 4**: 回退到当前模拟数据

### 故障检测机制
```python
# 实时健康检查
- API响应时间监控（>5秒标记为不可用）
- HTTP状态码检查
- 数据完整性验证
- 异常数据过滤
```

## 📊 数据结构设计

### 统一返回格式
```python
{
    "source": "real_data",
    "timestamp": "2025-07-24 14:30:00",
    "sentiment_score": 7.2,
    "confidence": 0.85,
    "data_sources": ["sina_finance", "eastmoney"],
    "news_data": [
        {
            "title": "科蓝软件获机构看好，数字化转型加速",
            "sentiment": "positive",
            "source": "新浪财经",
            "time": "2025-07-24 10:30:00",
            "url": "https://finance.sina.com.cn/..."
        }
    ],
    "forum_data": [
        {
            "content": "科蓝软件这波上涨有基本面支撑",
            "sentiment": "positive",
            "platform": "东方财富股吧",
            "likes": 156,
            "replies": 23
        }
    ],
    "hot_topics": ["数字化转型", "金融科技", "银行IT"]
}
```

## 🛡️ 反爬虫策略

### 请求控制
- **频率控制**: 每IP每分钟最多20次请求
- **随机间隔**: 2-5秒随机延迟
- **User-Agent轮换**: 10种常见浏览器UA
- **代理池**: 支持HTTP/HTTPS代理（可选）

### 数据缓存
- **缓存策略**: Redis/Memory双重缓存
- **缓存TTL**: 1小时（新闻）/ 30分钟（论坛）
- **缓存键**: 基于股票代码+时间戳

## ⚡ 性能优化方案

### 并发处理
```python
# 异步并发获取
async def fetch_all_sources(symbol):
    tasks = [
        fetch_sina_news(symbol),
        fetch_eastmoney_posts(symbol),
        fetch_tencent_news(symbol)
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### 智能降级
```python
# 基于响应时间的智能选择
if response_time > 3.0:
    switch_to_fallback_source()
```

## 📈 质量评估指标

### 数据质量监控
- **覆盖率**: 目标股票的信息获取比例
- **时效性**: 数据延迟时间（目标<1小时）
- **准确性**: 情绪分析准确率（人工抽样验证）
- **稳定性**: 7天内服务可用性（目标>95%）

### 用户体验指标
- **响应时间**: <3秒
- **成功率**: >90%
- **数据新鲜度**: 显示最后更新时间

## 🧪 测试方案

### 测试用例
```python
# 1. 数据源可用性测试
test_data_sources_availability()

# 2. 情绪分析准确性测试
test_sentiment_accuracy()

# 3. 降级机制测试
test_fallback_mechanism()

# 4. 性能测试
test_response_time()
```

### 验证股票
- **A股**: 000001, 300663, 600036
- **港股**: 00700, 03690
- **美股**: AAPL, TSLA

## 🚀 实施路线图

### Phase 1: 基础设施（2天）
- [ ] 创建真实数据源模块
- [ ] 实现RSS解析器
- [ ] 添加网页爬取基础功能

### Phase 2: 核心功能（3天）
- [ ] 集成新浪财经API
- [ ] 实现东方财富爬取
- [ ] 添加情绪分析引擎

### Phase 3: 优化完善（2天）
- [ ] 添加缓存机制
- [ ] 实现降级策略
- [ ] 性能优化和测试

## 📋 实施检查清单

### 开发前准备
- [ ] 确认技术方案
- [ ] 准备测试环境
- [ ] 设置监控日志

### 开发完成后
- [ ] 功能测试通过
- [ ] 性能测试达标
- [ ] 文档更新完成
- [ ] 回滚方案准备

## 🔍 实时监控Dashboard

### 监控指标
- 各数据源成功率
- 平均响应时间
- 缓存命中率
- 错误率统计
- 用户反馈收集

### 日志记录
```python
logger.info(f"[SocialMedia] {stock_code} 数据源: {source} 响应时间: {response_time}s")
logger.warning(f"[SocialMedia] {stock_code} 数据源降级: {from_source} -> {to_source}")
```

---

## 📝 版本历史
- **v1.0**: 初始技术方案设计
- **v1.1**: 添加监控Dashboard和测试方案
- **v1.2**: 完善降级策略和性能优化

## 📞 联系方式
- 技术负责人：开发团队
- 最后更新：2025-07-24
- 状态：待实施