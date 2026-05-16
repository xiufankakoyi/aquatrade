"""
检查交易盈亏计算
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

engine = UnifiedBacktestEngine(data_query=data_manager, config=config)
strategy = MainWaveTrendStrategy(
    data_manager=data_manager,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

start_date = '2025-06-02'
end_date = '2025-11-19'

print("=" * 60)
print("检查交易盈亏计算")
print("=" * 60)

results = None
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'stream_complete':
        results = event.get('data')
        break

if results:
    trades = results['trades']
    
    # 分离买入和卖出交易
    buy_trades = [t for t in trades if t['action'] == 'buy']
    sell_trades = [t for t in trades if t['action'] == 'sell']
    
    print(f"\n交易统计:")
    print(f"  买入交易: {len(buy_trades)} 笔")
    print(f"  卖出交易: {len(sell_trades)} 笔")
    
    # 计算卖出交易的盈亏
    if sell_trades:
        profit_losses = [t['profit_loss'] for t in sell_trades]
        rois = [t['roi'] for t in sell_trades]
        
        total_profit = sum(p for p in profit_losses if p > 0)
        total_loss = sum(abs(p) for p in profit_losses if p < 0)
        win_count = sum(1 for p in profit_losses if p > 0)
        loss_count = sum(1 for p in profit_losses if p < 0)
        
        print(f"\n盈亏分析:")
        print(f"  盈利交易: {win_count} 笔, 总盈利: {total_profit:,.2f}")
        print(f"  亏损交易: {loss_count} 笔, 总亏损: {total_loss:,.2f}")
        print(f"  净盈亏: {sum(profit_losses):,.2f}")
        print(f"  胜率: {win_count / len(sell_trades) * 100:.2f}%")
        print(f"  盈亏比: {total_profit / total_loss:.2f}" if total_loss > 0 else "  盈亏比: N/A")
        
        print(f"\n前10笔卖出交易详情:")
        for t in sell_trades[:10]:
            print(f"  {t['date']} {t['code']}: 盈亏={t['profit_loss']:,.2f}, ROI={t['roi']:.2f}%")
    
    # 检查买入总金额 vs 卖出总金额
    buy_amount = sum(t['cost'] for t in buy_trades)
    sell_revenue = sum(t['revenue'] for t in sell_trades)
    
    print(f"\n资金流向:")
    print(f"  买入总成本: {buy_amount:,.2f}")
    print(f"  卖出总收入: {sell_revenue:,.2f}")
    print(f"  差额: {sell_revenue - buy_amount:,.2f}")
