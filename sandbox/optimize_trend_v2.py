"""
回测优化中长期趋势策略 V2
"""
import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.trend_follow_v2 import TrendFollowStrategyV2, TrendFollowV2Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def run_backtest(strategy_params: dict, start_date: str, end_date: str) -> dict:
    """运行单次回测"""
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(data_query)
    strategy = TrendFollowStrategyV2(**strategy_params)
    
    all_trades = []
    daily_equity = []
    final_metrics = None
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        update_type = update.get('type')
        data = update.get('data', {})
        
        if update_type == 'daily_equity_engine':
            daily_equity.append({
                'date': data.get('date'),
                'equity': safe_float(data.get('equity')),
            })
        elif update_type in ('new_trade', 'new_trade_engine'):
            all_trades.append(data)
        elif update_type == 'final_metrics':
            final_metrics = data
    
    if daily_equity:
        df_equity = pd.DataFrame(daily_equity)
        actual_return = (df_equity['equity'].iloc[-1] / df_equity['equity'].iloc[0] - 1) * 100
    else:
        actual_return = 0
    
    closed_trades = [t for t in all_trades if t.get('action') == 'sell']
    wins = [t for t in closed_trades if safe_float(t.get('profit_loss')) > 0]
    
    return {
        'total_return': final_metrics.get('totalReturn', actual_return) if final_metrics else actual_return,
        'max_drawdown': final_metrics.get('maxDrawdown', 0) if final_metrics else 0,
        'sharpe': final_metrics.get('sharpeRatio', 0) if final_metrics else 0,
        'win_rate': final_metrics.get('winRate', 0) if final_metrics else 0,
        'trade_count': len(closed_trades),
        'win_count': len(wins),
    }


def quick_test():
    """快速测试默认参数"""
    print("=" * 80)
    print("快速测试 V2 策略")
    print("=" * 80)
    
    params = {}
    
    print("\n测试区间: 2024-01-01 ~ 2025-06-30")
    result = run_backtest(params, "2024-01-01", "2025-06-30")
    
    print(f"\n结果:")
    print(f"  总收益: {result['total_return']:.2f}%")
    print(f"  最大回撤: {result['max_drawdown']:.2f}%")
    print(f"  夏普比率: {result['sharpe']:.2f}")
    print(f"  胜率: {result['win_rate']:.1f}%")
    print(f"  交易次数: {result['trade_count']}")
    
    print("\n" + "=" * 80)
    print("参数优化")
    print("=" * 80)
    
    best_params = optimize_parameters()
    
    if best_params:
        validate_strategy(best_params)
    
    return result


def optimize_parameters():
    """参数优化"""
    print("\n" + "=" * 80)
    print("V2 策略参数优化")
    print("=" * 80)
    
    start_date = "2024-01-01"
    end_date = "2025-06-30"
    
    param_grid = {
        'bias_threshold_high': [0.08, 0.10, 0.12],
        'stop_loss_pct': [0.08, 0.10, 0.12],
        'trailing_stop_pct': [0.06, 0.08, 0.10],
        'volume_ratio_min': [1.2, 1.5, 2.0],
    }
    
    results = []
    total = (
        len(param_grid['bias_threshold_high']) * 
        len(param_grid['stop_loss_pct']) * 
        len(param_grid['trailing_stop_pct']) *
        len(param_grid['volume_ratio_min'])
    )
    
    print(f"\n总共 {total} 种参数组合")
    print(f"回测区间: {start_date} ~ {end_date}")
    print("-" * 80)
    
    count = 0
    for bias in param_grid['bias_threshold_high']:
        for stop_loss in param_grid['stop_loss_pct']:
            for trailing in param_grid['trailing_stop_pct']:
                for vol_ratio in param_grid['volume_ratio_min']:
                    count += 1
                    params = {
                        'bias_threshold_high': bias,
                        'stop_loss_pct': stop_loss,
                        'trailing_stop_pct': trailing,
                        'volume_ratio_min': vol_ratio,
                    }
                    
                    print(f"\n[{count}/{total}] bias={bias*100:.0f}%, sl={stop_loss*100:.0f}%, tr={trailing*100:.0f}%, vol={vol_ratio:.1f}")
                    
                    try:
                        result = run_backtest(params, start_date, end_date)
                        result['params'] = params
                        results.append(result)
                        
                        print(f"  收益: {result['total_return']:.2f}%, 回撤: {result['max_drawdown']:.2f}%, 夏普: {result['sharpe']:.2f}")
                    except Exception as e:
                        print(f"  错误: {e}")
    
    print("\n" + "=" * 80)
    print("优化结果排序（按夏普比率）")
    print("=" * 80)
    
    results.sort(key=lambda x: x['sharpe'], reverse=True)
    
    print(f"\n{'排名':<4} {'收益%':<10} {'回撤%':<10} {'夏普':<8} {'胜率%':<8} {'交易数':<8} 参数")
    print("-" * 80)
    
    for i, r in enumerate(results[:10]):
        p = r['params']
        print(f"{i+1:<4} {r['total_return']:<10.2f} {r['max_drawdown']:<10.2f} {r['sharpe']:<8.2f} {r['win_rate']:<8.1f} {r['trade_count']:<8} bias={p['bias_threshold_high']*100:.0f}%, sl={p['stop_loss_pct']*100:.0f}%")
    
    if results:
        best = results[0]
        print(f"\n最佳参数组合:")
        print(f"  bias_threshold_high: {best['params']['bias_threshold_high']*100}%")
        print(f"  stop_loss_pct: {best['params']['stop_loss_pct']*100}%")
        print(f"  trailing_stop_pct: {best['params']['trailing_stop_pct']*100}%")
        print(f"  volume_ratio_min: {best['params']['volume_ratio_min']}")
        
        return best['params']
    
    return None


def validate_strategy(params: dict):
    """验证策略在完整区间的表现"""
    print("\n" + "=" * 80)
    print("验证策略表现 (2024-01-01 ~ 2026-01-31)")
    print("=" * 80)
    
    result = run_backtest(params, "2024-01-01", "2026-01-31")
    
    print(f"\n验证结果:")
    print(f"  总收益: {result['total_return']:.2f}%")
    print(f"  最大回撤: {result['max_drawdown']:.2f}%")
    print(f"  夏普比率: {result['sharpe']:.2f}")
    print(f"  胜率: {result['win_rate']:.1f}%")
    print(f"  交易次数: {result['trade_count']}")
    
    return result


if __name__ == "__main__":
    quick_test()
