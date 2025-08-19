"""
调试配置模块
控制详细日志输出
"""

import os
import json
from typing import Dict, Any
from pathlib import Path

class DebugConfig:
    """调试配置类"""
    
    def __init__(self):
        self.config_file = self._find_config_file()
        self.config = self._load_config()
        
    def _find_config_file(self) -> Path:
        """查找配置文件"""
        # 尝试多个可能的路径
        possible_paths = [
            Path("config/debug.json"),
            Path("../config/debug.json"),
            Path("/app/config/debug.json"),
            Path(os.path.dirname(__file__)).parent.parent / "config" / "debug.json"
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
                
        # 如果都不存在，使用默认路径
        return Path("config/debug.json")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('debug_settings', {})
            else:
                # 返回默认配置
                return {
                    'llm_interaction_debug': False,
                    'tool_result_debug': False,
                    'data_source_debug': False
                }
        except Exception as e:
            print(f"⚠️ 加载调试配置失败: {e}，使用默认配置")
            return {
                'llm_interaction_debug': False,
                'tool_result_debug': False,
                'data_source_debug': False
            }
        
    def is_llm_debug_enabled(self) -> bool:
        """检查是否启用LLM交互调试"""
        return self.config.get('llm_interaction_debug', False)
    
    def is_tool_debug_enabled(self) -> bool:
        """检查是否启用工具结果调试"""
        return self.config.get('tool_result_debug', False)
    
    def is_data_source_debug_enabled(self) -> bool:
        """检查是否启用数据源调试"""
        return self.config.get('data_source_debug', False)
    
    def reload_config(self):
        """重新加载配置"""
        self.config = self._load_config()
        
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'config_file': str(self.config_file),
            'llm_interaction_debug': self.is_llm_debug_enabled(),
            'tool_result_debug': self.is_tool_debug_enabled(),
            'data_source_debug': self.is_data_source_debug_enabled()
        }

# 全局调试配置实例
debug_config = DebugConfig()