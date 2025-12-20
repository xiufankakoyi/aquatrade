"""
启用 GPU 加速的辅助脚本

使用方法：
1. 安装 GPU 依赖：pip install -r requirements_gpu.txt
2. 运行此脚本检查 GPU 可用性
3. 设置环境变量 USE_GPU=true 启用 GPU 加速
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from utils.gpu_acceleration import check_gpu_availability, enable_gpu

def main():
    print("=" * 60)
    print("GPU 加速检查工具")
    print("=" * 60)
    
    gpu_info = check_gpu_availability()
    
    print("\n检测结果：")
    print(f"  CuPy (NumPy CUDA): {'✅ 可用' if gpu_info['cupy'] else '❌ 不可用'}")
    print(f"  cuDF (pandas CUDA): {'✅ 可用' if gpu_info['cudf'] else '❌ 不可用'}")
    print(f"  Numba CUDA: {'✅ 可用' if gpu_info['numba_cuda'] else '❌ 不可用'}")
    print(f"  GPU 设备数量: {gpu_info['device_count']}")
    print(f"  总体状态: {'✅ 可以使用 GPU' if gpu_info['any_available'] else '❌ 无法使用 GPU'}")
    
    if gpu_info['any_available']:
        print("\n✅ 检测到 GPU，可以启用加速！")
        print("\n启用方法：")
        print("  1. 设置环境变量：")
        print("     Windows: set USE_GPU=true")
        print("     Linux/Mac: export USE_GPU=true")
        print("  2. 或者在代码中调用：")
        print("     from utils.gpu_acceleration import enable_gpu")
        print("     enable_gpu()")
        
        # 尝试启用
        if enable_gpu():
            print("\n✅ GPU 加速已启用！")
        else:
            print("\n⚠️ GPU 加速启用失败")
    else:
        print("\n❌ 未检测到可用的 GPU 库")
        print("\n安装建议：")
        print("  1. 确保已安装 CUDA Toolkit")
        print("  2. 安装 GPU 库：")
        print("     pip install -r requirements_gpu.txt")
        print("  3. 或使用 conda（推荐）：")
        print("     conda install -c conda-forge cupy numba")
        if sys.platform == "linux":
            print("     conda install -c rapidsai -c conda-forge -c nvidia cudf")
        print("\n注意：Windows 上 GPU 支持有限，建议使用 Linux 或 WSL2")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

