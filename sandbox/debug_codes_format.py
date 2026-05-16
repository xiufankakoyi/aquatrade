"""
检查 factor_matrix 中 codes_str 的格式
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
    def _build_data_dict_fast(self, factor_slice, fm):
        result = super()._build_data_dict_fast(factor_slice, fm)
        
        # 检查 codes_str 格式
        codes = fm.codes_str
        print(f"\n  codes_str 前10个: {codes[:10]}")
        print(f"  codes_str 后10个: {codes[-10:]}")
        
        # 检查是否有截断的代码
        truncated = [c for c in codes if len(c) < 6]
        if truncated:
            print(f"  [警告] 截断的代码: {truncated[:20]}")
        
        return result

engine = DebugEngine(data_query=data_manager, config=config)
strategy = MainWaveTrendStrategy(
    data_manager=data_manager,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

start_date = '2025-11-07'
end_date = '2025-11-10'

print("=" * 60)
print("检查 factor_matrix 中 codes_str 的格式")
print("=" * 60)

for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'daily_equity_engine':
        data = event['data']
        print(f"\n{data['date']}: 权益={data['equity']:,.2f}")
    elif event.get('type') == 'stream_complete':
        break
