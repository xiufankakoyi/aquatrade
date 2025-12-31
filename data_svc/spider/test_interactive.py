"""
交互式测试脚本 - 模型持久化版本
使用方法：
1. 运行: python -i test_interactive.py
2. 在交互式环境中多次调用 run_benchmark() 而不会重新加载模型
3. 或者直接运行: python test_interactive.py 来执行一次测试
"""

from test import run_benchmark, get_model, hybrid_predict, single_char_model
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-i":
        # 交互式模式
        print("="*50)
        print("交互式模式已启动")
        print("模型将在第一次调用时加载，之后会保持加载状态")
        print("可以多次调用 run_benchmark() 而不会重新加载模型")
        print("="*50)
        print("\n提示：输入 run_benchmark() 来运行测试")
    else:
        # 直接运行模式
        run_benchmark()

