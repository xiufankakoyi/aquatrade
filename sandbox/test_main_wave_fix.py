"""
测试修复后的主浪趋势策略回测
验证深市主板股票是否能被正确选中
"""
import os
import sys
import pandas as pd
from datetime import datetime

# 添加项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
from config.config import Config

print("=" * 70)
print("主浪趋势策略回测 - 修复验证")
print("=" * 70)
print(f"回测区间: 2025-01-01 ~ 2025-01-31")
print(f"初始资金: 100000")
print("=" * 70)

try:
    # 初始化数据查询
    print("\n[1/3] 初始化数据查询...")
    data_query = OptimizedStockDataQuery()
    print(f"  ✓ 数据查询初始化完成")

    # 检查2025-01-02的数据
    print("\n[2/3] 检查2025-01-02股票池...")
    df = data_query.get_market_data('2025-01-02')
    print(f"  ✓ 获取到 {len(df)} 只股票")

    # 统计各板块
    codes = df['stock_code'].unique().tolist()
    sz_count = sum(1 for c in codes if str(c).startswith('0'))
    cyb_count = sum(1 for c in codes if str(c).startswith('3'))
    sh_count = sum(1 for c in codes if str(c).startswith('6'))
    kcb_count = sum(1 for c in codes if str(c).startswith('688'))

    print(f"\n  股票分布:")
    print(f"    沪市主板(6开头): {sh_count}")
    print(f"    科创板(688): {kcb_count}")
    print(f"    深市主板(0开头): {sz_count}")
    print(f"    创业板(3开头): {cyb_count}")

    # 检查聚宽买入的股票
    print(f"\n  聚宽买入的股票:")
    target_stocks = ['000030', '002626', '002403']
    for code in target_stocks:
        found = code in codes
        print(f"    {code}: {'✓ 存在' if found else '✗ 不存在'}")

    # 创建策略和回测引擎
    print("\n[3/3] 初始化策略和回测引擎...")
    strategy = MainWaveTrendStrategy()
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 策略: {strategy.name}")
    print(f"  ✓ 回测引擎初始化完成")

    # 运行回测
    print("\n" + "=" * 70)
    print("开始回测...")
    print("=" * 70)

    # 收集回测结果
    results_list = []
    trades_log = []

    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2025-01-31',
        strategy=strategy
    ):
        results_list.append(event)

        # 记录交易
        if event.get('type') == 'trade':
            trades_log.append(event)

        # 显示进度
        if event.get('type') == 'day_end':
            date = event.get('date', '')
            nav = event.get('nav', 0)
            print(f"  {date}: NAV={nav:.2f}")

    # 获取最终结果
    if results_list:
        final_result = results_list[-1]

        print("\n" + "=" * 70)
        print("回测结果")
        print("=" * 70)

        metrics = final_result.get('metrics', {})
        print(f"\n  策略收益: {metrics.get('total_return', 0):.2%}")
        print(f"  基准收益: {metrics.get('benchmark_return', 0):.2%}")
        print(f"  超额收益: {metrics.get('excess_return', 0):.2%}")
        print(f"  夏普比率: {metrics.get('sharpe_ratio', 0):.3f}")
        print(f"  最大回撤: {metrics.get('max_drawdown', 0):.2%}")
        print(f"  胜率: {metrics.get('win_rate', 0):.2%}")
        print(f"  交易次数: {metrics.get('total_trades', 0)}")

        # 显示交易记录
        if trades_log:
            print(f"\n  交易记录 (前10条):")
            for i, trade in enumerate(trades_log[:10]):
                trade_data = trade.get('trade', {})
                print(f"    {trade_data}")

    print("\n" + "=" * 70)
    print("回测完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
