import sys
import time
sys.path.insert(0, '.')

# 测试单次回测时间
from sandbox.bayesian_optimization import load_data, run_backtest

t0 = time.time()
daily_data = load_data('2024-01-01', '2024-12-31')
print(f'数据加载: {time.time()-t0:.2f}s, {len(daily_data)}只股票')

t0 = time.time()
config = {
    'start_date': '2024-01-01',
    'end_date': '2024-12-31',
    'vs_threshold': 0.5,
    'rsi_filter': True,
    'rsi_max': 50,
    'ma_diff_filter': False,
    'ma_diff_threshold': 0,
    'take_profit_pct': 0.05,
    'stop_loss_pct': 0.02,
    'trailing_stop_pct': 0.02,
    'max_holding_days': 10,
}
result = run_backtest(daily_data, config)
print(f'单次回测: {time.time()-t0:.2f}s')
print(f'  交易次数: {result["trade_count"]}')
print(f'  总收益: {result["total_return"]:.2f}%')
