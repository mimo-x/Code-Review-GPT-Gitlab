"""
Redis 客户端工具类
用于管理认证 token
"""
import os
import redis
from typing import Optional


class RedisClient:
    """Redis 客户端单例"""
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            try:
                self._client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # 测试连接
                self._client.ping()
                print(f"✓ Redis 连接成功: {redis_url}")
            except Exception as e:
                print(f"✗ Redis 连接失败: {e}")
                raise RuntimeError(f"Redis 连接失败，认证功能需要 Redis 支持: {redis_url}") from e

    def get_client(self):
        """获取 Redis 客户端"""
        return self._client

    def set_token(self, token: str, username: str, expire_seconds: int = 604800) -> bool:
        """
        存储 token
        :param token: token 字符串
        :param username: 用户名
        :param expire_seconds: 过期时间（秒），默认 7 天
        :return: 是否成功
        """
        try:
            self._client.setex(
                f"auth_token:{token}",
                expire_seconds,
                username
            )
            return True
        except Exception as e:
            print(f"存储 token 失败: {e}")
            return False

    def get_token(self, token: str) -> Optional[str]:
        """
        获取 token 对应的用户名
        :param token: token 字符串
        :return: 用户名，如果不存在或已过期返回 None
        """
        try:
            username = self._client.get(f"auth_token:{token}")
            return username
        except Exception as e:
            print(f"获取 token 失败: {e}")
            return None

    def delete_token(self, token: str) -> bool:
        """
        删除 token
        :param token: token 字符串
        :return: 是否成功
        """
        try:
            self._client.delete(f"auth_token:{token}")
            return True
        except Exception as e:
            print(f"删除 token 失败: {e}")
            return False

    def refresh_token(self, token: str, expire_seconds: int = 604800) -> bool:
        """
        刷新 token 过期时间
        :param token: token 字符串
        :param expire_seconds: 过期时间（秒），默认 7 天
        :return: 是否成功
        """
        try:
            return self._client.expire(f"auth_token:{token}", expire_seconds)
        except Exception as e:
            print(f"刷新 token 失败: {e}")
            return False


# 创建全局实例
redis_client = RedisClient()
