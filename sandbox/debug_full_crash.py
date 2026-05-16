"""
检查完整回测中 2025-11-10 的情况
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

data_manager = UnifiedDataManager()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

# 继承并添加调试
class DebugEngine(UnifiedBacktestEngine):
    def _calculate_portfolio_value(self, positions, data_dict):
        if not positions or not data_dict:
            return 0.0
        
        import numpy as np
        codes = list(positions.keys())
        shares = np.array([positions[c] for c in codes], dtype=np.float64)
        
        prices = np.array([
            float(data_dict.get(c, {}).get('close', 0)) 
            for c in codes
        ], dtype=np.float64)
        
        market_value = float(np.dot(shares, prices))
        
        # 检查是否有价格为 0 的情况
        zero_price_codes = [c for i, c in enumerate(codes) if prices[i] == 0]
        if zero_price_codes:
            print(f"  [警告] 以下股票收盘价为 0: {zero_price_codes}")
        
        return market_value

engine = DebugEngine(data_query=data_manager, config=config)
strategy = MainWaveTrendStrategy(
    data_manager=data_manager,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

start_date = '2025-06-02'
end_date = '2025-11-12'

print("=" * 60)
print("检查完整回测中 2025-11-10 前后的情况")
print("=" * 60)

for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'daily_equity_engine':
        data = event['data']
        if data['date'] in ['2025-11-07', '2025-11-10', '2025-11-11', '2025-11-12']:
            print(f"\n{data['date']}:")
            print(f"  权益: {data['equity']:,.2f}")
            print(f"  现金: {data['cash']:,.2f}")
            print(f"  持仓数: {data['positions']}")
    elif event.get('type') == 'stream_complete':
        break
