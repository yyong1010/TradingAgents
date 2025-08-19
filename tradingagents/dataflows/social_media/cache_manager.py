"""
社交媒体数据缓存管理器
提供数据缓存和降级机制
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging
import os
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class SocialMediaCache:
    """社交媒体数据缓存管理器"""
    
    def __init__(self, cache_dir: str = None, ttl: int = 3600):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'cache', 'social_media')
        self.ttl = ttl
        
        # 确保缓存目录存在
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"社交媒体缓存目录: {self.cache_dir}, TTL: {self.ttl}秒")
    
    def _generate_cache_key(self, symbol: str, data_type: str, **kwargs) -> str:
        """生成缓存键"""
        key_data = {
            'symbol': symbol,
            'type': data_type,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get(self, symbol: str, data_type: str, **kwargs) -> Optional[Dict]:
        """获取缓存数据"""
        try:
            cache_key = self._generate_cache_key(symbol, data_type, **kwargs)
            cache_path = self._get_cache_path(cache_key)
            
            if not os.path.exists(cache_path):
                return None
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查是否过期
            timestamp = cache_data.get('timestamp', 0)
            if time.time() - timestamp > self.ttl:
                logger.debug(f"缓存数据已过期: {symbol} - {data_type}")
                return None
            
            logger.debug(f"从缓存获取数据: {symbol} - {data_type}")
            return cache_data.get('data')
            
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            return None
    
    def set(self, symbol: str, data_type: str, data: Dict, **kwargs) -> bool:
        """设置缓存数据"""
        try:
            cache_key = self._generate_cache_key(symbol, data_type, **kwargs)
            cache_path = self._get_cache_path(cache_key)
            
            cache_data = {
                'symbol': symbol,
                'type': data_type,
                'data': data,
                'timestamp': time.time(),
                'created_at': datetime.now().isoformat(),
                'kwargs': kwargs
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"缓存数据已保存: {symbol} - {data_type}")
            return True
            
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False
    
    def delete(self, symbol: str, data_type: str, **kwargs) -> bool:
        """删除缓存数据"""
        try:
            cache_key = self._generate_cache_key(symbol, data_type, **kwargs)
            cache_path = self._get_cache_path(cache_key)
            
            if os.path.exists(cache_path):
                os.remove(cache_path)
                logger.debug(f"缓存数据已删除: {symbol} - {data_type}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"删除缓存失败: {e}")
            return False
    
    def clear_expired(self) -> int:
        """清除过期缓存"""
        try:
            cache_files = os.listdir(self.cache_dir)
            expired_count = 0
            current_time = time.time()
            
            for filename in cache_files:
                if not filename.endswith('.json'):
                    continue
                    
                file_path = os.path.join(self.cache_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    timestamp = cache_data.get('timestamp', 0)
                    if current_time - timestamp > self.ttl:
                        os.remove(file_path)
                        expired_count += 1
                        
                except Exception as e:
                    logger.warning(f"处理过期缓存文件失败: {filename}, {e}")
                    # 删除损坏的文件
                    try:
                        os.remove(file_path)
                        expired_count += 1
                    except:
                        pass
            
            logger.info(f"清除过期缓存: {expired_count} 个文件")
            return expired_count
            
        except Exception as e:
            logger.error(f"清除过期缓存失败: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        try:
            cache_files = os.listdir(self.cache_dir)
            total_files = len([f for f in cache_files if f.endswith('.json')])
            
            file_sizes = []
            for filename in cache_files:
                if filename.endswith('.json'):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        file_sizes.append(os.path.getsize(file_path))
                    except:
                        pass
            
            total_size = sum(file_sizes)
            
            return {
                'total_files': total_files,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'cache_dir': self.cache_dir,
                'ttl_hours': self.ttl / 3600
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {'error': str(e)}


class FallbackManager:
    """降级管理器"""
    
    def __init__(self):
        self.failure_counts = {}
        self.last_success_times = {}
        self.circuit_breaker_threshold = 5  # 连续失败5次后开启熔断
        self.circuit_breaker_timeout = 300  # 熔断5分钟后重试
    
    def record_failure(self, data_source: str) -> bool:
        """记录数据源失败"""
        current_time = time.time()
        
        if data_source not in self.failure_counts:
            self.failure_counts[data_source] = 0
        
        self.failure_counts[data_source] += 1
        
        # 检查是否达到熔断阈值
        if self.failure_counts[data_source] >= self.circuit_breaker_threshold:
            logger.warning(f"数据源 {data_source} 触发熔断，暂停使用")
            return True
        
        return False
    
    def record_success(self, data_source: str) -> None:
        """记录数据源成功"""
        self.failure_counts[data_source] = 0
        self.last_success_times[data_source] = time.time()
    
    def is_circuit_breaker_open(self, data_source: str) -> bool:
        """检查熔断器是否开启"""
        if data_source not in self.failure_counts:
            return False
        
        if self.failure_counts[data_source] < self.circuit_breaker_threshold:
            return False
        
        # 检查是否已经过了熔断时间
        if data_source in self.last_success_times:
            time_since_last_success = time.time() - self.last_success_times[data_source]
            if time_since_last_success > self.circuit_breaker_timeout:
                # 重置熔断器
                self.failure_counts[data_source] = 0
                return False
        
        return True
    
    def get_health_status(self) -> Dict:
        """获取健康状态"""
        return {
            'failure_counts': self.failure_counts,
            'circuit_breaker_status': {
                source: {
                    'is_open': self.is_circuit_breaker_open(source),
                    'failures': self.failure_counts.get(source, 0)
                }
                for source in ['sina_finance', 'eastmoney', 'tencent_finance']
            }
        }
    
    def should_use_fallback(self, data_sources: List[str]) -> bool:
        """判断是否应该使用备用数据"""
        available_sources = [
            source for source in data_sources
            if not self.is_circuit_breaker_open(source)
        ]
        
        return len(available_sources) == 0


class CacheWrapper:
    """缓存包装器，提供缓存装饰器功能"""
    
    def __init__(self, cache: SocialMediaCache, fallback: FallbackManager):
        self.cache = cache
        self.fallback = fallback
    
    async def cached_async_call(self, func, symbol: str, data_type: str, **kwargs):
        """带缓存的异步调用包装"""
        try:
            # 先尝试从缓存获取
            cached_data = self.cache.get(symbol, data_type, **kwargs)
            if cached_data is not None:
                logger.debug(f"使用缓存数据: {symbol} - {data_type}")
                return cached_data
            
            # 检查熔断器
            if self.fallback.is_circuit_breaker_open(data_type):
                logger.warning(f"数据源 {data_type} 熔断中，跳过调用")
                return None
            
            # 执行真实调用
            result = await func(symbol, **kwargs)
            
            if result and isinstance(result, dict) and 'error' not in result:
                # 记录成功
                self.fallback.record_success(data_type)
                
                # 缓存结果
                self.cache.set(symbol, data_type, result, **kwargs)
                
                return result
            else:
                # 记录失败
                should_fallback = self.fallback.record_failure(data_type)
                if should_fallback:
                    logger.warning(f"数据源 {data_type} 连续失败，触发降级")
                
                return result
                
        except Exception as e:
            logger.error(f"缓存包装调用失败: {e}")
            self.fallback.record_failure(data_type)
            return None


# 全局实例
_cache_instance = None
_fallback_instance = None
_wrapper_instance = None


def get_cache_manager() -> SocialMediaCache:
    """获取缓存管理器单例"""
    global _cache_instance
    if _cache_instance is None:
        ttl = int(os.getenv('SOCIAL_MEDIA_CACHE_TTL', 3600))
        _cache_instance = SocialMediaCache(ttl=ttl)
    return _cache_instance


def get_fallback_manager() -> FallbackManager:
    """获取降级管理器单例"""
    global _fallback_instance
    if _fallback_instance is None:
        _fallback_instance = FallbackManager()
    return _fallback_instance


def get_cache_wrapper() -> CacheWrapper:
    """获取缓存包装器单例"""
    global _wrapper_instance
    if _wrapper_instance is None:
        cache = get_cache_manager()
        fallback = get_fallback_manager()
        _wrapper_instance = CacheWrapper(cache, fallback)
    return _wrapper_instance


# 测试用例
if __name__ == "__main__":
    import asyncio
    
    async def test_cache_system():
        """测试缓存系统"""
        cache = get_cache_manager()
        fallback = get_fallback_manager()
        
        # 测试缓存统计
        stats = cache.get_cache_stats()
        print("缓存统计:", stats)
        
        # 测试缓存操作
        test_data = {'test': 'data', 'timestamp': datetime.now().isoformat()}
        cache.set('test', 'sentiment', test_data, days=1)
        
        cached = cache.get('test', 'sentiment', days=1)
        print("缓存测试结果:", cached is not None)
        
        # 测试降级机制
        fallback.record_failure('test_source')
        print("降级管理器状态:", fallback.get_health_status())
        
        # 清除过期缓存
        cleared = cache.clear_expired()
        print(f"清除过期缓存: {cleared} 个文件")
    
    asyncio.run(test_cache_system())