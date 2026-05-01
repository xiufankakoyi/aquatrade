# test_ma_strategy.py

import sys
import pandas as pd
from core.backtest.unified_engine import UnifiedBacktestEngine
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.strategies.ma_comparison_strategy import MAComparisonStrategy

def run_test():
    print("=" * 80)
    print("双均线策略 (MA5 vs MA10) 纯指标校准测试")
    print("标的: 601988 (中国银行)")
    print("配置: 初始资金 100,000, 零摩擦 (0佣金, 0滑点)")
    print("=" * 80)

    # 1. 初始化数据和引擎
    data_query = OptimizedStockDataQuery()
    
    # 严格配置：初始资金 100,000，手续费 0，最小手续费 0
    engine = UnifiedBacktestEngine(
        data_query=data_query,
    )
    
    # 初始化策略
    strategy = MAComparisonStrategy()
    
    # 2. 设置回测范围
    # 设计一个足够长的时间段，例如 2024 全年
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    
    print(f"\n开始回测: {start_date} 至 {end_date} ...")
    
    results = []
    trades = []
    
    # 3. 运行回测
    try:
        for update in engine.run_backtest_streaming(start_date, end_date, strategy):
            utype = update.get('type')
            if utype == 'daily_equity_engine':
                results.append(update['data'])
            elif utype == 'new_trade_engine':
                trades.append(update['data'])
            elif utype == 'stream_complete':
                final_data = update['data']
                print(f"\n回测完成！")
                print(f"最终权益: {final_data['finalEquity']:.2f}")
                print(f"累计收益: {final_data['totalReturn']:.2f}%")
                print(f"交易次数: {final_data['totalTrades']}")
                print(f"胜率: {final_data['winRate']:.1f}%")
    except Exception as e:
        print(f"回测过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 打印所有交易明细
    if trades:
        print("\n所有交易记录:")
        print("=" * 80)
        print(f"{'日期':<12} {'方向':<6} {'价格':<10} {'数量':<10} {'成交额':<15} {'盈亏':<10}")
        for t in trades:
            action = "买入" if t['action'] == 'buy' else "卖出"
            price = t['price']
            shares = t['shares']
            amount = t.get('revenue') or t.get('cost') or (price * shares)
            pnl = t.get('profit_loss', 0.0)
            print(f"{t['date']:<12} {action:<6} {price:<10.2f} {shares:<10} {amount:<15.2f} {pnl:<10.2f}")
        print("=" * 80)
    else:
        print("\n未产生任何交易。")

    print("\n" + "=" * 80)
    print("测试任务结束")
    print("=" * 80)

if __name__ == "__main__":
    run_test()
