"""
dragon_eye/service.py DragonEye 服务测试

测试内容：
1. 服务初始化
2. 日志捕获器
3. 任务管理
4. 错误处理
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestLogCapture:
    """日志捕获器测试"""
    
    def test_log_capture_creation(self):
        """测试日志捕获器创建"""
        from core.dragon_eye.service import LogCapture
        
        capture = LogCapture(job_id="test_job")
        
        assert capture.job_id == "test_job"
        assert len(capture.subscribers) == 0
    
    def test_log_capture_subscribe(self):
        """测试日志订阅"""
        from core.dragon_eye.service import LogCapture
        
        capture = LogCapture(job_id="test_job")
        callback = Mock()
        
        capture.subscribe(callback)
        
        assert len(capture.subscribers) == 1
    
    def test_log_capture_unsubscribe(self):
        """测试取消订阅"""
        from core.dragon_eye.service import LogCapture
        
        capture = LogCapture(job_id="test_job")
        callback1 = Mock()
        callback2 = Mock()
        
        capture.subscribe(callback1)
        capture.subscribe(callback2)
        capture.unsubscribe(callback1)
        
        assert len(capture.subscribers) == 1
        assert callback2 in capture.subscribers
    
    def test_log_capture_notify_subscribers(self):
        """测试通知订阅者"""
        from core.dragon_eye.service import LogCapture
        
        capture = LogCapture(job_id="test_job")
        callback = Mock()
        capture.subscribe(callback)
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': 'info',
            'message': 'test message'
        }
        
        capture._notify_subscribers(log_entry)
        
        callback.assert_called_once_with(log_entry)
    
    def test_log_capture_stop(self):
        """测试停止捕获"""
        from core.dragon_eye.service import LogCapture
        
        capture = LogCapture(job_id="test_job")
        
        capture.stop()
        
        assert capture._stop_event.is_set()


class TestDragonEyeService:
    """DragonEye 服务测试"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        with patch('core.dragon_eye.service.Config') as mock:
            mock.BASE_DIR = '/test/path'
            yield mock
    
    @pytest.fixture
    def service(self, mock_config):
        """创建服务实例"""
        with patch('core.dragon_eye.service.DragonEyeManager'):
            from core.dragon_eye.service import DragonEyeService
            return DragonEyeService()
    
    def test_service_creation(self, service):
        """测试服务创建"""
        assert service is not None
        assert hasattr(service, 'manager')
        assert hasattr(service, '_active_captures')
    
    def test_service_has_required_paths(self, service):
        """测试服务路径配置"""
        assert hasattr(service, 'quant_dir')
        assert hasattr(service, 'spider_path')
        assert hasattr(service, 'cleaner_path')
    
    def test_service_active_captures_empty(self, service):
        """测试初始无活动捕获"""
        assert len(service._active_captures) == 0


class TestDragonEyeServiceJobManagement:
    """DragonEye 服务任务管理测试"""
    
    @pytest.fixture
    def service(self):
        """创建服务实例"""
        with patch('core.dragon_eye.service.Config') as mock_config:
            mock_config.BASE_DIR = '/test/path'
            with patch('core.dragon_eye.service.DragonEyeManager'):
                from core.dragon_eye.service import DragonEyeService
                return DragonEyeService()
    
    def test_run_crawler_returns_job_id(self, service):
        """测试爬虫任务返回 job_id"""
        with patch.object(service, '_run_crawler_task'):
            job_id = service.run_crawler('2025-01-01')
            
            assert job_id is not None
            assert isinstance(job_id, str)
    
    def test_process_and_persist_returns_job_id(self, service):
        """测试清洗任务返回 job_id"""
        with patch.object(service, '_process_task'):
            job_id = service.process_and_persist('2025-01-01')
            
            assert job_id is not None
            assert isinstance(job_id, str)
    
    def test_run_full_pipeline_returns_job_id(self, service):
        """测试完整工作流返回 job_id"""
        with patch.object(service, '_run_pipeline_task'):
            job_id = service.run_full_pipeline('2025-01-01')
            
            assert job_id is not None
            assert isinstance(job_id, str)


class TestDragonEyeServiceErrorHandling:
    """DragonEye 服务错误处理测试"""
    
    @pytest.fixture
    def service(self):
        """创建服务实例"""
        with patch('core.dragon_eye.service.Config') as mock_config:
            mock_config.BASE_DIR = '/test/path'
            with patch('core.dragon_eye.service.DragonEyeManager'):
                from core.dragon_eye.service import DragonEyeService
                return DragonEyeService()
    
    def test_process_task_missing_data_dir(self, service):
        """测试数据目录不存在"""
        from core.dragon_eye.job_manager import job_manager
        
        job = job_manager.create_job('clean')
        
        with patch('pathlib.Path.exists', return_value=False):
            service._process_task('2025-01-01', job.job_id)
        
        updated_job = job_manager.get_job(job.job_id)
        assert updated_job is not None


class TestFindQuantDir:
    """查找 quant 目录测试"""
    
    def test_find_quant_dir_function(self):
        """测试查找 quant 目录函数"""
        from core.dragon_eye.service import _find_quant_dir
        
        result = _find_quant_dir()
        
        assert result is not None
