"""
策略生成服务

将用户的自然语言描述转换为符合 AIStrategyBase 规范的策略代码。
整合了 Prompt 工程和代码生成逻辑。
"""

import os
import re
import time
import logging
from core.utils.llm_client import AquaLLM
from core.strategies.templates.prompt_template import build_prompt
from config.config import Config

logger = logging.getLogger(__name__)


class StrategyGenerator:
    """
    策略生成器
    
    使用示例:
        generator = StrategyGenerator()
        filename = generator.create_strategy(
            user_description="写一个策略：股价突破20日均线买入，RSI大于70卖出",
            strategy_name="AI突破策略"
        )
    """
    
    def __init__(self):
        """初始化策略生成器"""
        self.llm = AquaLLM()
        logger.info("策略生成器已初始化")
    
    def create_strategy(
        self, 
        user_description: str, 
        strategy_name: str = "AI策略"
    ) -> str:
        """
        生成策略文件并保存
        
        参数:
            user_description: 用户的自然语言描述
            strategy_name: 策略名称
        
        返回:
            str: 生成的文件名 (e.g. ai_gen_17123456.py)
        
        异常:
            Exception: 如果生成失败
        """
        timestamp = int(time.time())
        strategy_id = f"ai_gen_{timestamp}"
        class_name = f"Strategy_ai_gen_{timestamp}"
        
        logger.info(f"开始生成策略: {strategy_name} (ID: {strategy_id}, Class: {class_name})")
        
        # 1. 添加策略特定的信息（策略ID和名称）
        # 在用户描述前添加策略信息
        enhanced_user_description = f"""
策略ID: {strategy_id}
策略名称: {strategy_name}
类名: {class_name}

用户需求:
{user_description}

请生成完整的策略代码，类名必须使用 {class_name}（避免类名冲突），strategy_name 设置为 "{strategy_name}"。
"""
        
        # 2. 使用我们之前创建的 Prompt 模板构建完整的 Prompt
        # build_prompt 已经包含了系统提示词、硬性约束、代码模板等
        # 将完整的 prompt 作为 user_prompt 传给 LLM
        full_prompt = build_prompt(enhanced_user_description)
        
        # 3. 调用 LLM 生成代码
        # build_prompt 返回的内容已经包含了系统提示词，所以直接作为 user_prompt
        # 使用简单的系统提示词，因为 build_prompt 中已经有详细的系统提示
        logger.info(f"正在调用 LLM 生成策略代码...")
        try:
            code = self.llm.generate_code(
                user_prompt=full_prompt,
                system_prompt="你是一个专业的量化策略代码生成器。严格按照用户提供的规范生成代码。"
            )
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise Exception(f"策略生成失败: LLM 调用失败 - {e}")
        
        if not code:
            raise Exception("策略生成失败: LLM 返回为空")
        
        # 4. 后处理：确保代码包含正确的类名和策略名称
        code = self._post_process_code(code, strategy_id, strategy_name, class_name)
        
        # 5. 保存文件到 core/strategies/user/ 目录
        filename = f"ai_gen_{timestamp}.py"
        save_dir = os.path.join(Config.BASE_DIR, 'core', 'strategies', 'user')
        os.makedirs(save_dir, exist_ok=True)
        
        file_path = os.path.join(save_dir, filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            logger.info(f"策略已保存至: {file_path}")
            print(f"✅ 策略已保存至: {file_path}")
            
            return filename
            
        except Exception as e:
            logger.error(f"保存策略文件失败: {e}")
            raise Exception(f"保存策略文件失败: {e}")
    
    def _post_process_code(
        self, 
        code: str, 
        strategy_id: str, 
        strategy_name: str,
        class_name: str
    ) -> str:
        """
        后处理生成的代码，确保包含正确的类名和策略名称
        
        参数:
            code: 生成的代码
            strategy_id: 策略ID
            strategy_name: 策略名称
            class_name: 策略类名（避免冲突）
        
        返回:
            str: 处理后的代码
        """
        # 替换类名（确保唯一性）
        code = re.sub(
            r'class\s+AIGeneratedStrategy\s*\(',
            f'class {class_name}(',
            code
        )
        code = re.sub(
            r'class\s+\w+Strategy\s*\([^)]*AIStrategyBase',
            f'class {class_name}(AIStrategyBase',
            code
        )
        
        # 如果代码中已经有 strategy_name，确保它是正确的
        if 'strategy_name' in code:
            code = re.sub(
                r'strategy_name\s*=\s*["\'][^"\']*["\']',
                f'strategy_name = "{strategy_name}"',
                code
            )
        else:
            # 如果类定义后没有 strategy_name，添加它
            lines = code.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith('class ') and 'AIStrategyBase' in line:
                    indent = len(line) - len(line.lstrip())
                    lines.insert(i + 1, ' ' * (indent + 4) + f'strategy_name = "{strategy_name}"')
                    break
            code = '\n'.join(lines)
        
        return code


# 测试入口
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    gen = StrategyGenerator()
    
    # 示例调用
    try:
        filename = gen.create_strategy(
            user_description="写一个双均线策略，当5日均线上穿20日均线时买入，下穿时卖出。",
            strategy_name="AI双均线测试"
        )
        print(f"\n✅ 策略生成成功: {filename}")
    except Exception as e:
        print(f"\n❌ 策略生成失败: {e}")
        import traceback
        traceback.print_exc()

