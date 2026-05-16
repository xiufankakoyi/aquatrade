"""
测试 equity curve 重复日期修复
"""
import sys
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')

from datetime import datetime
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from config.config import Config

# 创建数据查询
print("初始化数据查询...")
data_query = OptimizedStockDataQuery()

# 创建策略实例
strategy = MainWaveTrendStrategy()

# 创建回测配置
backtest_config = BacktestConfig(
    initial_capital=Config.INITIAL_CAPITAL,
    commission_rate=Config.COMMISSION_RATE,
    min_commission=Config.MIN_COMMISSION,
    sell_tax=Config.SELL_TAX
)

# 创建回测引擎
engine = UnifiedBacktestEngine(
    data_query=data_query,
    config=backtest_config
)

# 运行回测
start_date = "2024-01-02"
end_date = "2024-01-31"  # 只测试一个月，便于观察

print(f"开始回测: {start_date} 到 {end_date}")
print(f"策略: {strategy.name}")
print("=" * 60)

try:
    results = list(engine.run_backtest(
        start_date=start_date,
        end_date=end_date,
        strategy=strategy
    ))
    
    print(f"\n回测完成，共 {len(results)} 个结果")
    
    # 直接从引擎获取 equity_history
    equity_history = engine._equity_history
    print(f"\n=== Equity Curve 统计 (从 _equity_history) ===")
    print(f"总记录数: {len(equity_history)}")
    
    # 计算预期交易日数量 (从 data_query)
    trading_days = data_query.get_trading_dates(start_date, end_date)
    print(f"预期交易日数量: {len(trading_days)}")
    
    if equity_history:
        dates = [d for d, _ in equity_history]
        from collections import Counter
        date_counts = Counter(dates)
        dupes = {d: c for d, c in date_counts.items() if c > 1}
        
        if dupes:
            print(f"⚠️ 发现重复日期: {dupes}")
            print("❌ 修复失败 - 仍有重复日期")
        else:
            print(f"✅ 没有重复日期")
            if len(equity_history) == len(trading_days):
                print(f"✅ 修复成功! 记录数与交易日数量一致")
            else:
                print(f"⚠️ 记录数 ({len(equity_history)}) 与交易日数量 ({len(trading_days)}) 不一致")
        
        # 显示所有 equity curve 数据
        print(f"\n所有 equity curve 记录:")
        for i, (d, v) in enumerate(equity_history):
            print(f"  {i+1}. {d}: {v:,.2f}")
    
    # 也检查 final_metrics 中的 equity_curve
    final_metrics = None
    for r in results:
        if r.get('type') == 'final_metrics':
            final_metrics = r.get('data', {})
            break
    
    if final_metrics:
        print(f"\n=== Final Metrics ===")
        print(f"总收益率: {final_metrics.get('totalReturn', 0):.2f}%")
        print(f"年化收益率: {final_metrics.get('annualizedReturn', 0):.2f}%")
        print(f"最大回撤: {final_metrics.get('maxDrawdown', 0):.2f}%")
        print(f"夏普比率: {final_metrics.get('sharpeRatio', 0):.2f}")
            
except Exception as e:
    print(f"\n❌ 回测出错: {e}")
    import traceback
    traceback.print_exc()
