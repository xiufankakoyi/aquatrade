"""
开发模式测试脚本 - 支持代码热重载，模型不重新加载
使用方法：
1. 运行: python -i test_dev.py
2. 修改 test.py 后，输入 reload_and_run() 来重新加载代码并运行
3. 模型会保持加载状态，不会重新加载
"""

import sys
import importlib

# 首次导入
import test
import model_cache

def reload_and_run():
    """重新加载 test 模块并运行测试（模型不会重新加载）"""
    print("\n" + "="*50)
    print("正在重新加载 test.py 模块...")
    
    # 重新加载 test 模块（模型缓存模块不重新加载）
    importlib.reload(test)
    
    print("代码重新加载完成！")
    print("模型保持加载状态（未重新加载）")
    print("="*50 + "\n")
    
    # 运行测试
    test.run_benchmark()

def reload():
    """仅重新加载 test 模块（不运行测试）"""
    print("\n正在重新加载 test.py 模块...")
    importlib.reload(test)
    print("代码重新加载完成！")
    print("提示：现在可以调用 test.run_benchmark() 运行测试")

if __name__ == "__main__":
    print("="*50)
    print("开发模式 - 支持代码热重载")
    print("="*50)
    print("提示：")
    print("1. 修改 test.py 后，输入 reload_and_run() 来重新加载代码并运行")
    print("2. 或者输入 reload() 仅重新加载，然后手动调用 test.run_benchmark()")
    print("3. 模型会保持加载状态，不会重新加载")
    print("="*50)
    print("\n首次运行测试（模型会首次加载）...")
    print("="*50)
    
    # 预加载模型（首次加载）
    model_cache.get_model()
    
    # 首次运行
    test.run_benchmark()
    
    print("\n" + "="*50)
    print("开发提示：")
    print("- 修改 test.py 后，输入 reload_and_run() 来重新加载代码并运行")
    print("- 模型会保持加载状态，不会重新加载（节省时间）")
    print("="*50)
