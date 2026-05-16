"""
快速随机搜索 - 使用快速防未来函数回测
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import random
import time
from sandbox.fast_no_lookahead import fast_no_lookahead_backtest
from sandbox.top3_backtest import load_data


def random_search(daily_data, start_date, end_date, n_trials=30):
    """随机搜索"""
    param_space = {
        'vs_threshold': (0, 1.0),
        'rsi_filter': [True, False],
        'rsi_max': (30, 70),
        'ma_diff_filter': [True, False],
        'ma_diff_threshold': (0, 0.1),
        'take_profit_pct': (0.02, 0.10),
        'stop_loss_pct': (0.01, 0.05),
        'trailing_stop_pct': (0.01, 0.05),
        'max_holding_days': (5, 15),
    }
    
    results = []
    
    for i in range(n_trials):
        config = {
            'vs_threshold': random.uniform(*param_space['vs_threshold']),
            'rsi_filter': random.choice(param_space['rsi_filter']),
            'rsi_max': random.uniform(*param_space['rsi_max']),
            'ma_diff_filter': random.choice(param_space['ma_diff_filter']),
            'ma_diff_threshold': random.uniform(*param_space['ma_diff_threshold']),
            'take_profit_pct': random.uniform(*param_space['take_profit_pct']),
            'stop_loss_pct': random.uniform(*param_space['stop_loss_pct']),
            'trailing_stop_pct': random.uniform(*param_space['trailing_stop_pct']),
            'max_holding_days': random.randint(*param_space['max_holding_days']),
        }
        
        result = fast_no_lookahead_backtest(daily_data, config, start_date, end_date)
        
        # 计算Calmar
        years = 1.0
        annual_return = (1 + result['total_return'] / 100) ** (1/years) - 1
        calmar = annual_return / (result['max_drawdown'] / 100) if result['max_drawdown'] > 0 else 0
        
        results.append({
            'config': config,
            'result': result,
            'calmar': calmar
        })
        
        print(f"  {i+1}/{n_trials}: 交易={result['trade_count']}, 收益={result['total_return']:.1f}%, 回撤={result['max_drawdown']:.1f}%, Calmar={calmar:.2f}")
    
    # 筛选交易次数>=100的参数
    valid = [r for r in results if r['result']['trade_count'] >= 100]
    if valid:
        valid.sort(key=lambda x: x['calmar'], reverse=True)
        return valid
    else:
        results.sort(key=lambda x: x['calmar'], reverse=True)
        return results[:3]


if __name__ == "__main__":
    print("加载数据...")
    t0 = time.time()
    daily_data = load_data('2024-01-01', '2024-12-31')
    print(f"数据加载: {time.time()-t0:.1f}s")
    
    print("\n随机搜索 (30次)...")
    t0 = time.time()
    top_results = random_search(daily_data, '2024-01-01', '2024-12-31', n_trials=30)
    print(f"\n搜索完成: {time.time()-t0:.1f}s")
    
    print("\n=== Top 3 结果 ===")
    for i, r in enumerate(top_results[:3]):
        print(f"\n{i+1}. Calmar: {r['calmar']:.2f}")
        print(f"   交易: {r['result']['trade_count']}, 收益: {r['result']['total_return']:.1f}%, 回撤: {r['result']['max_drawdown']:.1f}%")
        print(f"   参数: {r['config']}")
