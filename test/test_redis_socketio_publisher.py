"""
core/utils/redis_socketio_publisher.py Redis发布器测试

测试内容：
1. RedisSocketIOPublisher 类初始化
2. 方法存在性验证
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestRedisSocketIOPublisherInit:
    """Redis发布器初始化测试"""
    
    @patch('core.utils.redis_socketio_publisher.redis')
    def test_init_with_url(self, mock_redis):
        """测试带URL初始化"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.from_url.return_value = mock_client
        
        from core.utils.redis_socketio_publisher import RedisSocketIOPublisher
        
        publisher = RedisSocketIOPublisher(
            redis_url="redis://localhost:6379/0",
            channel_prefix="test_channel"
        )
        
        assert publisher.redis_url == "redis://localhost:6379/0"
        assert publisher.channel_prefix == "test_channel"


class TestRedisSocketIOPublisherMethods:
    """Redis发布器方法测试"""
    
    def test_has_emit(self):
        """测试是否有emit方法"""
        from core.utils.redis_socketio_publisher import RedisSocketIOPublisher
        
        assert hasattr(RedisSocketIOPublisher, 'emit')
    
    def test_has_emit_progress(self):
        """测试是否有emit_progress方法"""
        from core.utils.redis_socketio_publisher import RedisSocketIOPublisher
        
        assert hasattr(RedisSocketIOPublisher, 'emit_progress')
    
    def test_has_emit_evaluation(self):
        """测试是否有emit_evaluation方法"""
        from core.utils.redis_socketio_publisher import RedisSocketIOPublisher
        
        assert hasattr(RedisSocketIOPublisher, 'emit_evaluation')
    
    def test_has_emit_error(self):
        """测试是否有emit_error方法"""
        from core.utils.redis_socketio_publisher import RedisSocketIOPublisher
        
        assert hasattr(RedisSocketIOPublisher, 'emit_error')
