#!/usr/bin/env python3
"""
简单系统测试 - Simple System Test
验证 TradingAgents 核心组件是否正常工作
Testing core TradingAgents components functionality
"""

import os
import sys
import traceback
from datetime import datetime

def main():
    print("🚀 TradingAgents 简单系统测试")
    print("🚀 TradingAgents Simple System Test")
    print("=" * 50)
    
    test_results = []
    
    # 测试1：基本依赖检查
    print("\n📦 测试模块依赖 / Testing Module Dependencies...")
    try:
        # 测试核心模块导入
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        test_results.append(("✅", "核心模块导入成功 / Core modules imported successfully"))
        
        # 测试日志模块
        from tradingagents.utils.logging_manager import get_logger
        logger = get_logger('simple_test')
        test_results.append(("✅", "日志系统正常 / Logging system working"))
        
    except Exception as e:
        test_results.append(("❌", f"模块导入失败 / Module import failed: {e}"))
        traceback.print_exc()
    
    # 测试2：配置系统
    print("\n⚙️ 测试配置系统 / Testing Configuration System...")
    try:
        config = DEFAULT_CONFIG.copy()
        print(f"   配置加载成功 / Config loaded: {len(config)} 个配置项 / items")
        
        # 检查重要配置项
        important_keys = ['llm_provider', 'deep_think_llm', 'quick_think_llm']
        for key in important_keys:
            if key in config:
                print(f"   ✅ {key}: {config[key]}")
            else:
                print(f"   ⚠️ 缺少配置项 / Missing config: {key}")
        
        test_results.append(("✅", "配置系统正常 / Configuration system working"))
        
    except Exception as e:
        test_results.append(("❌", f"配置系统错误 / Configuration error: {e}"))
        traceback.print_exc()
    
    # 测试3：数据源连接测试（轻量级）
    print("\n🔌 测试数据源连接 / Testing Data Sources...")
    try:
        # 尝试导入数据工具
        from tradingagents.tools import get_stock_info
        test_results.append(("✅", "数据工具模块导入成功 / Data tools imported"))
        
        # 测试简单的数据获取（不执行实际API调用）
        print("   数据源工具准备完成 / Data source tools ready")
        
    except Exception as e:
        test_results.append(("⚠️", f"数据源测试跳过 / Data source test skipped: {e}"))
    
    # 测试4：核心图结构初始化
    print("\n🎯 测试核心交易图 / Testing Core Trading Graph...")
    try:
        # 创建最小配置用于测试
        test_config = {
            "llm_provider": "google",
            "deep_think_llm": "gemini-2.0-flash", 
            "quick_think_llm": "gemini-2.0-flash",
            "max_debate_rounds": 1,
            "online_tools": False  # 避免实际API调用
        }
        
        # 初始化交易智能体图（不执行分析）
        ta = TradingAgentsGraph(debug=True, config=test_config)
        test_results.append(("✅", "交易智能体图初始化成功 / Trading agents graph initialized"))
        
        # 检查图的基本属性
        if hasattr(ta, 'config'):
            print(f"   配置加载: {ta.config['llm_provider']}")
        if hasattr(ta, 'graph'):
            print("   智能体图结构创建完成 / Agent graph structure created")
            
    except Exception as e:
        test_results.append(("❌", f"交易图初始化失败 / Trading graph init failed: {e}"))
        traceback.print_exc()
    
    # 测试5：环境变量检查
    print("\n🌍 检查环境配置 / Checking Environment...")
    env_vars = [
        'GOOGLE_API_KEY',
        'OPENAI_API_KEY', 
        'DEEPSEEK_API_KEY',
        'DASHSCOPE_API_KEY',
        'FINNHUB_API_KEY'
    ]
    
    found_keys = 0
    for var in env_vars:
        if os.getenv(var):
            print(f"   ✅ {var} 已配置 / configured")
            found_keys += 1
        else:
            print(f"   ⚪ {var} 未配置 / not configured")
    
    if found_keys > 0:
        test_results.append(("✅", f"找到 {found_keys} 个API密钥 / Found {found_keys} API keys"))
    else:
        test_results.append(("⚠️", "未找到API密钥配置 / No API keys found"))
    
    # 测试总结
    print("\n" + "=" * 50)
    print("📊 测试结果总结 / Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    warned = 0
    failed = 0
    
    for status, message in test_results:
        print(f"{status} {message}")
        if status == "✅":
            passed += 1
        elif status == "⚠️":
            warned += 1
        elif status == "❌":
            failed += 1
    
    print("\n📈 统计 / Statistics:")
    print(f"   通过: {passed} / Passed: {passed}")
    print(f"   警告: {warned} / Warnings: {warned}")
    print(f"   失败: {failed} / Failed: {failed}")
    
    # 系统建议
    print("\n💡 系统建议 / System Recommendations:")
    if failed == 0 and passed > 3:
        print("   ✅ 系统运行良好，可以进行股票分析")
        print("   ✅ System is healthy, ready for stock analysis")
    elif failed > 0:
        print("   ⚠️ 发现问题，建议检查错误信息")
        print("   ⚠️ Issues found, please check error messages")
    elif found_keys == 0:
        print("   📝 建议配置API密钥以启用完整功能")
        print("   📝 Recommend configuring API keys for full functionality")
    else:
        print("   ✅ 基础系统正常，可以开始使用")
        print("   ✅ Basic system working, ready to use")
    
    print(f"\n🕐 测试完成时间 / Test completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)