"""
检查 data_dict 键格式
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

# 继承 UnifiedBacktestEngine 并添加调试
class DebugEngine(UnifiedBacktestEngine):
    def _calculate_portfolio_value(self, positions, data_dict):
        if positions and data_dict:
            print(f"\n_calculate_portfolio_value 调用:")
            print(f"  持仓键: {list(positions.keys())[:5]}")
            print(f"  data_dict 键 (前10个): {list(data_dict.keys())[:10]}")
            
            # 检查持仓股票是否在 data_dict 中
            for code in list(positions.keys())[:3]:
                # 尝试不同的键格式
                found = False
                for key_format in [code, code.zfill(6), code.lstrip('0')]:
                    if key_format in data_dict:
                        print(f"  {code} -> 找到键 '{key_format}': close={data_dict[key_format].get('close', 'N/A')}")
                        found = True
                        break
                if not found:
                    print(f"  {code} -> 未找到对应键!")
        
        return super()._calculate_portfolio_value(positions, data_dict)

engine = DebugEngine(data_query=data_manager, config=config)
strategy = MainWaveTrendStrategy(
    data_manager=data_manager,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

start_date = '2025-06-02'
end_date = '2025-06-05'

print("=" * 60)
print("检查 data_dict 键格式")
print("=" * 60)

for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'daily_equity_engine':
        data = event['data']
        print(f"\n{data['date']}: 权益={data['equity']:,.2f}, 持仓={data['positions']}")
    elif event.get('type') == 'stream_complete':
        break
