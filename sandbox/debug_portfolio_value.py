"""
检查权益计算时 data_dict 的结构
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
            print(f"  持仓: {list(positions.keys())[:5]}... (共{len(positions)}只)")
            print(f"  data_dict 类型: {type(data_dict)}")
            print(f"  data_dict 键: {list(data_dict.keys())[:10]}...")
            
            # 检查 data_dict 中是否有股票数据
            for code in list(positions.keys())[:3]:
                stock_data = data_dict.get(code, {})
                print(f"  {code} 数据: {stock_data}")
        
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
print("检查权益计算时 data_dict 的结构")
print("=" * 60)

for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'daily_equity_engine':
        data = event['data']
        print(f"\n{data['date']}: 权益={data['equity']:,.2f}, 现金={data['cash']:,.2f}, 持仓={data['positions']}")
    elif event.get('type') == 'stream_complete':
        break
