"""
MACD四阴线策略 - 快速优化版

使用随机搜索代替遗传算法，大大加快速度
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import random
import json
import time
from typing import List, Dict

from sandbox.top3_backtest import run_backtest, load_data


def calc_calmar_ratio(total_return: float, max_drawdown: float, years: float) -> float:
    """Calmar = 年化收益 / |最大回撤|"""
    annual_return = (1 + total_return / 100) ** (1 / years) - 1
    if max_drawdown == 0:
        return 0
    return annual_return / (max_drawdown / 100)


def random_search(daily_data, n_trials: int = 100) -> List[Dict]:
    """随机搜索，返回Top 10参数"""
    param_space = {
        'vs_threshold': (0, 1.0),
        'rsi_max': (30, 70),
        'ma_diff_threshold': (0, 0.1),
        'take_profit_pct': (0.02, 0.10),
        'stop_loss_pct': (0.01, 0.05),
        'trailing_stop_pct': (0.01, 0.05),
        'max_holding_days': (5, 15),
    }
    
    results = []
    
    for i in range(n_trials):
        config = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'vs_threshold': random.uniform(*param_space['vs_threshold']),
            'rsi_filter': random.choice([True, False]),
            'rsi_max': random.uniform(*param_space['rsi_max']),
            'ma_diff_filter': random.choice([True, False]),
            'ma_diff_threshold': random.uniform(*param_space['ma_diff_threshold']),
            'take_profit_pct': random.uniform(*param_space['take_profit_pct']),
            'stop_loss_pct': random.uniform(*param_space['stop_loss_pct']),
            'trailing_stop_pct': random.uniform(*param_space['trailing_stop_pct']),
            'max_holding_days': random.randint(*param_space['max_holding_days']),
        }
        
        equity_curve, total_return, trade_count, all_trades = run_backtest(daily_data, config['start_date'], config['end_date'], config)
        
        # 计算最大回撤
        equity_arr = np.array([e['equity'] for e in equity_curve])
        cummax = np.maximum.accumulate(equity_arr)
        drawdown = (cummax - equity_arr) / cummax
        max_drawdown = np.max(drawdown) * 100 if len(equity_arr) > 0 else 0
        
        result = {
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'trade_count': trade_count,
        }
        
        # 检查交易次数
        if result['trade_count'] < 50:
            continue
            
        calmar = calc_calmar_ratio(
            result['total_return'],
            result['max_drawdown'],
            1.0
        )
        
        results.append({
            'config': config,
            'calmar': calmar,
            'result': result
        })
        
        if (i + 1) % 10 == 0:
            print(f"  已完成 {i+1}/{n_trials}...")
    
    # 按Calmar排序，返回Top 10
    results.sort(key=lambda x: x['calmar'], reverse=True)
    return results[:10]


def validate_on_windows(daily_data, config: Dict) -> Dict:
    """在3个窗口上验证"""
    windows = [
        ("2024-01-01", "2024-12-31", "2024"),
        ("2025-01-01", "2025-06-30", "2025上半年"),
    ]
    
    all_results = []
    
    for start, end, name in windows:
        cfg = {
            'start_date': start,
            'end_date': end,
            **config
        }
        equity_curve, total_return, trade_count, all_trades = run_backtest(daily_data, cfg['start_date'], cfg['end_date'], cfg)
        
        equity_arr = np.array([e['equity'] for e in equity_curve])
        cummax = np.maximum.accumulate(equity_arr)
        drawdown = (cummax - equity_arr) / cummax
        max_drawdown = np.max(drawdown) * 100 if len(equity_arr) > 0 else 0
        
        result = {
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'trade_count': trade_count,
        }

        years = (pd.to_datetime(end) - pd.to_datetime(start)).days / 365
        calmar = calc_calmar_ratio(
            result['total_return'],
            result['max_drawdown'],
            years
        )
        
        print(f"  {name}: 收益={result['total_return']:.1f}%, 回撤={result['max_drawdown']:.1f}%, Calmar={calmar:.2f}, 交易={result['trade_count']}")
        
        all_results.append({
            'window': name,
            'calmar': calmar,
            'return': result['total_return'],
            'drawdown': result['max_drawdown'],
            'trades': result['trade_count']
        })
    
    avg_calmar = np.mean([r['calmar'] for r in all_results])
    return {
        'avg_calmar': avg_calmar,
        'details': all_results
    }


def main():
    print("=" * 60)
    print("MACD四阴线策略 - 快速优化版")
    print("=" * 60)
    
    # 加载数据
    t0 = time.time()
    daily_data = load_data('2024-01-01', '2024-12-31')
    print(f"数据加载: {time.time()-t0:.1f}s, {len(daily_data)}只股票")
    
    # 随机搜索
    print("\n随机搜索 (100次)...")
    t0 = time.time()
    top_configs = random_search(daily_data, n_trials=100)
    print(f"搜索完成: {time.time()-t0:.1f}s")
    
    if not top_configs:
        print("没有找到有效参数！")
        return
    
    print(f"\n找到 {len(top_configs)} 个有效参数")
    
    # 在3个窗口上验证Top 5
    print("\n验证 Top 5 参数...")
    best_overall = None
    best_avg_calmar = -999
    
    for i, item in enumerate(top_configs[:5]):
        config = item['config']
        print(f"\n参数 {i+1}:")
        validation = validate_on_windows(daily_data, config)
        
        if validation['avg_calmar'] > best_avg_calmar:
            best_avg_calmar = validation['avg_calmar']
            best_overall = {
                'config': config,
                'validation': validation
            }
    
    # 输出最佳结果
    print("\n" + "=" * 60)
    print("最佳参数")
    print("=" * 60)
    print(f"平均Calmar: {best_avg_calmar:.2f}")
    print(f"\n参数:")
    for k, v in best_overall['config'].items():
        print(f"  {k}: {v}")
    
    # 保存结果
    output_path = Path(__file__).parent / "quick_optimization_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(best_overall, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    main()
