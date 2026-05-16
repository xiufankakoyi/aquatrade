"""
core/utils/llm_client.py LLM客户端补充测试

测试内容：
1. Mock HTTP 请求
2. 代码清洗功能
3. 流式生成
4. 错误处理
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock, call


class TestAquaLLMGenerateCode:
    """LLM客户端代码生成测试"""
    
    @patch('core.utils.llm_client.openai')
    @patch('core.utils.llm_client.Config')
    def test_generate_code_success(self, mock_config, mock_openai):
        """测试成功生成代码"""
        mock_config.LLM_API_BASE = "http://localhost:1234/v1"
        mock_config.LLM_API_KEY = "test_key"
        mock_config.LLM_MODEL_NAME = "test_model"
        mock_config.LLM_TEMPERATURE = 0.7
        mock_config.LLM_MAX_TOKENS = 2000
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "```python\nprint('hello')\n```"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client
        
        from core.utils.llm_client import AquaLLM
        
        llm = AquaLLM()
        result = llm.generate_code("写一个hello world程序")
        
        assert isinstance(result, str)
        assert "print('hello')" in result
    
    @patch('core.utils.llm_client.openai')
    @patch('core.utils.llm_client.Config')
    def test_generate_code_with_custom_system_prompt(self, mock_config, mock_openai):
        """测试自定义系统提示词"""
        mock_config.LLM_API_BASE = "http://localhost:1234/v1"
        mock_config.LLM_API_KEY = "test_key"
        mock_config.LLM_MODEL_NAME = "test_model"
        mock_config.LLM_TEMPERATURE = 0.7
        mock_config.LLM_MAX_TOKENS = 2000
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "test code"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client
        
        from core.utils.llm_client import AquaLLM
        
        llm = AquaLLM()
        result = llm.generate_code(
            user_prompt="写一个策略",
            system_prompt="你是一个量化策略专家"
        )
        
        assert isinstance(result, str)


class TestAquaLLMCleanCode:
    """LLM客户端代码清洗测试"""
    
    @patch('core.utils.llm_client.openai')
    @patch('core.utils.llm_client.Config')
    def test_clean_code_removes_markdown(self, mock_config, mock_openai):
        """测试去除Markdown标记"""
        mock_config.LLM_API_BASE = "http://localhost:1234/v1"
        mock_config.LLM_API_KEY = "test_key"
        mock_config.LLM_MODEL_NAME = "test_model"
        mock_config.LLM_TEMPERATURE = 0.7
        mock_config.LLM_MAX_TOKENS = 2000
        
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        from core.utils.llm_client import AquaLLM
        
        llm = AquaLLM()
        
        raw_text = "```python\nprint('hello')\n```"
        clean = llm._clean_code(raw_text)
        
        assert "```" not in clean
        assert "print('hello')" in clean
    
    @patch('core.utils.llm_client.openai')
    @patch('core.utils.llm_client.Config')
    def test_clean_code_removes_think_tags(self, mock_config, mock_openai):
        """测试去除思考标签"""
        mock_config.LLM_API_BASE = "http://localhost:1234/v1"
        mock_config.LLM_API_KEY = "test_key"
        mock_config.LLM_MODEL_NAME = "test_model"
        mock_config.LLM_TEMPERATURE = 0.7
        mock_config.LLM_MAX_TOKENS = 2000
        
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        from core.utils.llm_client import AquaLLM
        
        llm = AquaLLM()
        
        raw_text = "思索过程实际代码print('hello')"
        clean = llm._clean_code(raw_text)
        
        assert "思索过程" not in clean
        assert "print('hello')" in clean
    
    @patch('core.utils.llm_client.openai')
    @patch('core.utils.llm_client.Config')
    def test_clean_code_removes_reasoning_tags(self, mock_config, mock_openai):
        """测试去除推理标签"""
        mock_config.LLM_API_BASE = "http://localhost:1234/v1"
        mock_config.LLM_API_KEY = "test_key"
        mock_config.LLM_MODEL_NAME = "test_model"
        mock_config.LLM_TEMPERATURE = 0.7
        mock_config.LLM_MAX_TOKENS = 2000
        
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        from core.utils.llm_client import AquaLLM
        
        llm = AquaLLM()
        
        raw_text = "推理过程实际代码print('hello')"
        clean = llm._clean_code(raw_text)
        
        assert "推理过程" not in clean
        assert "print('hello')" in clean
    
    @patch('core.utils.llm_client.openai')
    @patch('core.utils.llm_client.Config')
    def test_clean_code_empty_string(self, mock_config, mock_openai):
        """测试空字符串"""
        mock_config.LLM_API_BASE = "http://localhost:1234/v1"
        mock_config.LLM_API_KEY = "test_key"
        mock_config.LLM_MODEL_NAME = "test_model"
        mock_config.LLM_TEMPERATURE = 0.7
        mock_config.LLM_MAX_TOKENS = 2000
        
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        from core.utils.llm_client import AquaLLM
        
        llm = AquaLLM()
        
        clean = llm._clean_code("")
        
        assert clean == ""
    
    @patch('core.utils.llm_client.openai')
    @patch('core.utils.llm_client.Config')
    def test_clean_code_plain_text(self, mock_config, mock_openai):
        """测试普通文本"""
        mock_config.LLM_API_BASE = "http://localhost:1234/v1"
        mock_config.LLM_API_KEY = "test_key"
        mock_config.LLM_MODEL_NAME = "test_model"
        mock_config.LLM_TEMPERATURE = 0.7
        mock_config.LLM_MAX_TOKENS = 2000
        
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        from core.utils.llm_client import AquaLLM
        
        llm = AquaLLM()
        
        raw_text = "print('hello')"
        clean = llm._clean_code(raw_text)
        
        assert "print('hello')" in clean


class TestAquaLLMErrorHandling:
    """LLM客户端错误处理测试"""
    
    @patch('core.utils.llm_client.openai')
    @patch('core.utils.llm_client.Config')
    def test_generate_code_handles_exception(self, mock_config, mock_openai):
        """测试异常处理"""
        mock_config.LLM_API_BASE = "http://localhost:1234/v1"
        mock_config.LLM_API_KEY = "test_key"
        mock_config.LLM_MODEL_NAME = "test_model"
        mock_config.LLM_TEMPERATURE = 0.7
        mock_config.LLM_MAX_TOKENS = 2000
        
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.OpenAI.return_value = mock_client
        
        from core.utils.llm_client import AquaLLM
        
        llm = AquaLLM()
        
        with pytest.raises(Exception) as exc_info:
            llm.generate_code("写一个程序")
        
        assert "LLM 调用失败" in str(exc_info.value)
