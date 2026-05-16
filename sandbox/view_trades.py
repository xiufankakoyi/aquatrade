"""查看原版策略的交易记录"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sandbox.backtest_report_optimized import run_backtest, get_cache

data = get_cache()
equity_curve, trades = run_backtest(data, '2024-01-01', '2024-03-31')

print(f'总交易数: {len(trades)}')
print('\n前20笔交易:')
for t in trades[:20]:
    print(f'{t["buy_date"]} 买入 {t["stock_code"]} 卖出 {t["sell_date"]} 收益 {t["return"]*100:.2f}%')
