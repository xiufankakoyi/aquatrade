"""
测试最优策略在2026年的表现 (更新到3.13)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sandbox.optimal_strategy import OptimalStrategy

strategy = OptimalStrategy()
result = strategy.run_backtest('2026-01-01', '2026-03-13')

print('=' * 60)
print('2026年回测结果 (2026.1.1 - 2026.3.13)')
print('=' * 60)
print(f'信号数: {result["signal_count"]}')
print(f'总收益: {result["total_return"]:.2f}%')

if result['equity_curve']:
    print(f'\n净值曲线点数: {len(result["equity_curve"])}')
    first = result['equity_curve'][0]
    last = result['equity_curve'][-1]
    print(f'起始日期: {first["date"]}, 净值: {first["equity"]:.2f}')
    print(f'结束日期: {last["date"]}, 净值: {last["equity"]:.2f}')
