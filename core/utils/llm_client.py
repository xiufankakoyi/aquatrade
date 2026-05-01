"""
LLM 客户端 - 系统与 AI 对话的桥梁

支持连接到本地 LLM 服务（如 LM Studio）或 OpenAI API。
会自动处理 Markdown 格式清洗，确保生成的代码能直接用。
"""

import openai
import logging
import re
from config.config import Config

logger = logging.getLogger(__name__)


class AquaLLM:
    """
    AquaTrade LLM 客户端
    
    使用示例:
        llm = AquaLLM()
        code = llm.generate_code(
            user_prompt="写一个策略：股价突破20日均线买入",
            system_prompt="你是一个专业的量化策略代码生成器。"
        )
    """
    
    def __init__(self):
        """
        初始化 LLM 客户端，连接到本地 LLM 服务或 OpenAI API
        """
        # 初始化 OpenAI 客户端，连接到本地 LM Studio 或 OpenAI
        self.client = openai.OpenAI(
            base_url=Config.LLM_API_BASE,
            api_key=Config.LLM_API_KEY
        )
        self.logger = logging.getLogger("AquaLLM")
        
        self.logger.info(
            f"LLM 客户端已初始化: base_url={Config.LLM_API_BASE}, "
            f"model={Config.LLM_MODEL_NAME}"
        )
    
    def generate_code(
        self, 
        user_prompt: str, 
        system_prompt: str = None
    ) -> str:
        """
        专门用于生成代码的接口，会自动清洗 Markdown 标记和思考过程
        
        参数:
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选，有默认值）
        
        返回:
            str: 清洗后的代码
        """
        if not system_prompt:
            system_prompt = (
                "你是一个专业的量化交易策略代码生成器。"
                "只输出 Python 代码，不要输出任何解释。"
            )
        
        return self._generate_content(user_prompt, system_prompt)
    
    def generate_report(
        self, 
        user_prompt: str, 
        system_prompt: str = None
    ) -> str:
        """
        专门用于生成报告的接口 (非流式)
        """
        if not system_prompt:
            system_prompt = (
                "你是一位拥有20年经验的量化基金风控总监。"
                "你的任务是阅读用户的策略和回测数据，生成一份专业的投资分析报告。"
            )
        
        return self._generate_content(user_prompt, system_prompt)

    def generate_report_stream(
        self, 
        user_prompt: str, 
        system_prompt: str = None
    ):
        """
        流式生成报告接口
        
        返回:
            Generator yielding cleaned text chunks
        """
        if not system_prompt:
            system_prompt = (
                "你是一位拥有20年经验的量化基金风控总监。"
                "你的任务是阅读用户的策略和回测数据，生成一份专业的投资分析报告。"
            )
        
        return self._generate_content_stream(user_prompt, system_prompt)
    
    def _generate_content(
        self, 
        user_prompt: str, 
        system_prompt: str
    ) -> str:
        """
        核心生成方法 (非流式)
        """
        try:
            self.logger.info(f"调用 LLM 生成内容 (同步)，长度: {len(user_prompt)}")
            response = self.client.chat.completions.create(
                model=Config.LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=Config.LLM_TEMPERATURE,
                max_tokens=Config.LLM_MAX_TOKENS,
                stream=False
            )
            
            content = response.choices[0].message.content
            return self._clean_code(content)
            
        except Exception as e:
            self.logger.error(f"LLM 调用失败: {e}", exc_info=True)
            raise Exception(f"LLM 调用失败: {e}")

    def _generate_content_stream(
        self, 
        user_prompt: str, 
        system_prompt: str
    ):
        """
        核心生成方法 (流式)
        """
        try:
            self.logger.info(f"调用 LLM 生成内容 (流式)，长度: {len(user_prompt)}")
            stream = self.client.chat.completions.create(
                model=Config.LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=Config.LLM_TEMPERATURE,
                max_tokens=Config.LLM_MAX_TOKENS,
                stream=True
            )
            
            # 由于流式无法直接使用 _clean_code（因为它需要完整文本）
            # 我们这里采取简单处理：实时 yield 原始文本块
            # 复杂的 <think> 过滤需要更精细的流处理，这里先保持简单
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
                    
        except Exception as e:
            self.logger.error(f"LLM 流式调用失败: {e}", exc_info=True)
            yield f"\n[ERROR] LLM 流式调用失败: {str(e)}"
    
    def _clean_code(self, raw_text: str) -> str:
        """
        清洗 LLM 输出，去除思考过程和 Markdown 标记
        
        处理内容:
        1. 去除 DeepSeek R1 的思考标签 <think>...</think>
        2. 去除其他可能的思考标签（如 <think>...</think>）
        3. 去除 Markdown 代码块标记 (```python ... ```)
        4. 去除多余的空行
        
        参数:
            raw_text: 原始 LLM 输出
        
        返回:
            str: 清洗后的代码
        """
        if not raw_text:
            return ""
        
        clean = raw_text.strip()
        
        # 1. 去除 DeepSeek R1 的思考标签 <think>...</think>
        clean = re.sub(
            r'<think>.*?</think>', 
            '', 
            clean, 
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # 2. 去除其他可能的思考标签
        clean = re.sub(
            r'<think>.*?</think>', 
            '', 
            clean, 
            flags=re.DOTALL | re.IGNORECASE
        )
        
        clean = re.sub(
            r'<reasoning>.*?</reasoning>', 
            '', 
            clean, 
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # 2.1 去除中文思考标签
        clean = re.sub(
            r'思索过程.*?实际代码',
            '实际代码',
            clean,
            flags=re.DOTALL
        )
        
        clean = re.sub(
            r'推理过程.*?实际代码',
            '实际代码',
            clean,
            flags=re.DOTALL
        )
        
        # 3. 去除 Markdown 代码块标记
        clean = clean.strip()
        if clean.startswith("```"):
            lines = clean.split('\n')
            # 去掉第一行 (```python 或 ```)
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            # 去掉最后一行 (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines)
        
        # 4. 去除多余的空行（保留最多2个连续空行）
        clean = re.sub(r'\n{3,}', '\n\n', clean)
        
        # 5. 去除行首行尾空白
        clean = clean.strip()
        
        return clean


