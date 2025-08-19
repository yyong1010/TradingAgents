#!/usr/bin/env python3
"""
全局LLM交互调试工具
为所有LLM调用提供统一的调试日志功能
"""

import logging
from functools import wraps
from typing import Any, List, Dict
from tradingagents.config.debug_config import debug_config

logger = logging.getLogger(__name__)

def debug_llm_interaction(func):
    """LLM交互调试装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 检查是否启用LLM调试
        if not debug_config.is_llm_debug_enabled():
            return func(*args, **kwargs)
        
        # 尝试从参数中提取相关信息
        agent_name = "Unknown"
        messages = None
        
        # 从args中查找消息和agent信息
        for arg in args:
            if hasattr(arg, '__class__'):
                class_name = arg.__class__.__name__
                if 'Agent' in class_name or 'Analyst' in class_name or 'Manager' in class_name:
                    agent_name = class_name
            elif isinstance(arg, list) and arg:
                # 检查是否是消息列表
                if hasattr(arg[0], 'content') or hasattr(arg[0], 'tool_calls'):
                    messages = arg
        
        # 从kwargs中查找消息
        if 'messages' in kwargs:
            messages = kwargs['messages']
        
        # 记录发送给LLM的内容
        if messages:
            logger.info(f"🔍 [全局LLM调试] {agent_name} 发送给LLM的消息序列:")
            for i, msg in enumerate(messages):
                if hasattr(msg, 'content'):
                    content = str(msg.content)
                    content_preview = content[:200] + "..." if len(content) > 200 else content
                    logger.info(f"  消息{i+1} ({type(msg).__name__}): {content_preview}")
                elif hasattr(msg, 'tool_calls'):
                    tool_count = len(msg.tool_calls) if msg.tool_calls else 0
                    logger.info(f"  消息{i+1} ({type(msg).__name__}): 工具调用 - {tool_count}个工具")
                else:
                    logger.info(f"  消息{i+1} ({type(msg).__name__}): {str(msg)[:100]}...")
        
        # 执行原函数
        result = func(*args, **kwargs)
        
        # 记录LLM返回的内容
        if hasattr(result, 'content'):
            content = str(result.content)
            logger.info(f"🔍 [全局LLM调试] {agent_name} LLM返回内容长度: {len(content)}")
            logger.info(f"🔍 [全局LLM调试] {agent_name} LLM返回内容预览: {content[:300]}...")
        else:
            logger.info(f"🔍 [全局LLM调试] {agent_name} LLM返回结果: {str(result)[:200]}...")
        
        return result
    
    return wrapper

def log_llm_messages(agent_name: str, messages: List[Any], prefix: str = "发送给LLM"):
    """记录LLM消息的辅助函数"""
    if not debug_config.is_llm_debug_enabled():
        return
    
    logger.info(f"🔍 [全局LLM调试] {agent_name} {prefix}的消息序列:")
    for i, msg in enumerate(messages):
        if hasattr(msg, 'content'):
            content = str(msg.content)
            content_preview = content[:200] + "..." if len(content) > 200 else content
            logger.info(f"  消息{i+1} ({type(msg).__name__}): {content_preview}")
        elif hasattr(msg, 'tool_calls'):
            tool_count = len(msg.tool_calls) if msg.tool_calls else 0
            logger.info(f"  消息{i+1} ({type(msg).__name__}): 工具调用 - {tool_count}个工具")
        elif isinstance(msg, dict):
            # 处理字典格式的消息（如风险管理中的格式）
            role = msg.get('role', 'unknown')
            content = str(msg.get('content', ''))
            content_preview = content[:200] + "..." if len(content) > 200 else content
            logger.info(f"  消息{i+1} (dict-{role}): {content_preview}")
        else:
            logger.info(f"  消息{i+1} ({type(msg).__name__}): {str(msg)[:100]}...")

def log_llm_response(agent_name: str, response: Any, prefix: str = "LLM返回"):
    """记录LLM响应的辅助函数"""
    if not debug_config.is_llm_debug_enabled():
        return
    
    if hasattr(response, 'content'):
        content = str(response.content)
        logger.info(f"🔍 [全局LLM调试] {agent_name} {prefix}内容长度: {len(content)}")
        logger.info(f"🔍 [全局LLM调试] {agent_name} {prefix}内容预览: {content[:300]}...")
    else:
        logger.info(f"🔍 [全局LLM调试] {agent_name} {prefix}结果: {str(response)[:200]}...")