#!/usr/bin/env python3
"""
启动可视化API服务
"""

import os
import sys
from app import app

def main():
    # 检查并启用 GPU 加速（如果可用）
    try:
        from utils.gpu_acceleration import check_gpu_availability, enable_gpu
        from utils.config import Config
        
        if Config.USE_GPU_ACCELERATION:
            gpu_info = check_gpu_availability()
            if gpu_info['any_available']:
                enable_gpu()
            else:
                print("⚠️ 配置了启用 GPU，但未检测到可用的 GPU 库")
                print("   将使用 CPU 模式运行")
    except ImportError:
        pass
    
    print("🚀 启动量化回测数据可视化API服务...")
    print(f"📊 服务地址: http://localhost:5000")
    print(f"📈 API文档:")
    print(f"   GET  /api/strategies          - 获取策略列表")
    print(f"   GET  /api/performance/<id>    - 获取策略绩效")
    print(f"   GET  /api/equity_curve/<id>   - 获取收益曲线")
    print(f"   GET  /api/risk_analysis/<id>  - 获取风险分析")
    print(f"   GET  /api/trade_records/<id>  - 获取交易记录")
    print(f"   GET  /api/monthly_returns/<id> - 获取月度收益")
    print(f"   POST /api/run_backtest        - 运行回测")
    print(f"   GET  /api/benchmark/<code>    - 获取基准数据")
    print("\n按 Ctrl+C 停止服务")
    
    from app import socketio
    debug = os.getenv("AQUATRADE_DEBUG", "0") == "1"
    try:
        socketio.run(app, debug=debug, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")

if __name__ == '__main__':
    main()