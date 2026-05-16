"""
完整回测数据验证脚本
验证：基准曲线、收益分布、指标计算
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings('ignore')

from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3, SimpleVolumeConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine


def test_backtest_data():
    """验证回测数据完整性"""
    print("=" * 80)
    print("回测数据完整性验证")
    print("=" * 80)
    
    # 初始化
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(
        data_query=data_query,
        initial_capital=1_000_000
    )
    
    config = SimpleVolumeConfig()
    strategy = SimpleVolumeStrategyV3(config=config)
    
    # 运行回测
    start_date = '2024-01-01'
    end_date = '2024-06-30'
    
    print(f"\n回测期间: {start_date} ~ {end_date}")
    print("-" * 80)
    
    final_data = None
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        if update.get('type') == 'stream_complete':
            final_data = update.get('data', {})
            break
    
    if not final_data:
        print("ERROR: 没有收到 stream_complete 事件")
        return False
    
    # 验证数据
    print("\n[1] 验证基础数据:")
    print("-" * 40)
    
    # 权益曲线
    equity_curve = final_data.get('equityCurve', [])
    print(f"  权益曲线点数: {len(equity_curve)}")
    if equity_curve:
        print(f"  首日权益: {equity_curve[0].get('equity'):,.2f}")
        print(f"  末日权益: {equity_curve[-1].get('equity'):,.2f}")
    
    # 基准曲线
    benchmark_curve = final_data.get('benchmarkCurve', [])
    print(f"  基准曲线点数: {len(benchmark_curve)}")
    if benchmark_curve:
        print(f"  首日基准: {benchmark_curve[0].get('equity'):,.2f}")
        print(f"  末日基准: {benchmark_curve[-1].get('equity'):,.2f}")
    
    # 交易记录
    trades = final_data.get('trades', [])
    print(f"  交易记录数: {len(trades)}")
    
    # 月度收益
    monthly_returns = final_data.get('monthlyReturns', [])
    print(f"  月度收益数据: {len(monthly_returns)} 条")
    
    print("\n[2] 验证指标计算:")
    print("-" * 40)
    
    # 基础指标
    total_return = final_data.get('totalReturn', 0)
    annualized_return = final_data.get('annualizedReturn', 0)
    max_drawdown = final_data.get('maxDrawdown', 0)
    sharpe_ratio = final_data.get('sharpeRatio', 0)
    calmar_ratio = final_data.get('calmarRatio', 0)
    
    print(f"  总收益: {total_return}%")
    print(f"  年化收益: {annualized_return}%")
    print(f"  最大回撤: {max_drawdown}%")
    print(f"  夏普比率: {sharpe_ratio}")
    print(f"  卡尔玛比率: {calmar_ratio}")
    
    # 手动验证计算
    if equity_curve:
        initial_equity = equity_curve[0].get('equity', 1_000_000)
        final_equity = equity_curve[-1].get('equity', 1_000_000)
        
        # 计算总收益
        calc_total_return = (final_equity - initial_equity) / initial_equity * 100
        print(f"\n  [验证] 计算总收益: {calc_total_return:.2f}% (后端: {total_return}%)")
        
        # 计算日收益率
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1].get('equity', 0)
            curr_equity = equity_curve[i].get('equity', 0)
            if prev_equity > 0:
                daily_returns.append((curr_equity - prev_equity) / prev_equity)
        
        if daily_returns:
            import numpy as np
            daily_returns = np.array(daily_returns)
            
            # 年化波动率
            annual_volatility = np.std(daily_returns) * np.sqrt(252) * 100
            print(f"  [验证] 年化波动率: {annual_volatility:.2f}%")
            
            # 夏普比率 (假设无风险利率 3%)
            risk_free_rate = 3.0
            if annual_volatility > 0:
                calc_sharpe = (annualized_return - risk_free_rate) / annual_volatility
                print(f"  [验证] 计算夏普比率: {calc_sharpe:.2f} (后端: {sharpe_ratio})")
            
            # 计算最大回撤
            equity_values = [e.get('equity', 0) for e in equity_curve]
            peak = equity_values[0]
            max_dd = 0
            for eq in equity_values:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak * 100
                if dd > max_dd:
                    max_dd = dd
            print(f"  [验证] 计算最大回撤: {max_dd:.2f}% (后端: {max_drawdown}%)")
            
            # 卡尔玛比率
            if max_dd > 0:
                calc_calmar = annualized_return / max_dd
                print(f"  [验证] 计算卡尔玛比率: {calc_calmar:.2f} (后端: {calmar_ratio})")
    
    print("\n[3] 验证收益分布:")
    print("-" * 40)
    
    if monthly_returns:
        for mr in monthly_returns:
            print(f"  {mr.get('month')}: {mr.get('return')}%")
    else:
        print("  [WARN] 需要后端生成月度收益数据")
    
    print("\n[4] 问题汇总:")
    print("-" * 40)
    
    issues = []
    if not benchmark_curve:
        issues.append("[X] 缺少基准曲线数据")
    if not monthly_returns:
        issues.append("[X] 缺少月度收益数据")
    if calmar_ratio == 0:
        issues.append("[X] 卡尔玛比率为 0")
    if not equity_curve:
        issues.append("[X] 缺少权益曲线数据")
    
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  [OK] 所有数据正常")
    
    return len(issues) == 0


if __name__ == "__main__":
    test_backtest_data()
