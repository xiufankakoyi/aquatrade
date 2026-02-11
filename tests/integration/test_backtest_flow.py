# tests/integration/test_backtest_flow.py
import pytest
import sys
from pathlib import Path
from core.backtest.optimized_backtest_engine import OptimizedBacktestEngine
from core.strategies.strategy_factory import StrategyFactory
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

@pytest.fixture(scope="module")
def backtest_setup():
    data_query = OptimizedStockDataQuery()
    engine = OptimizedBacktestEngine(data_query)
    yield engine, data_query
    data_query.close()

def test_streaming_metrics_generation(backtest_setup):
    """验证回测引擎是否能正确生成最终指标和交易记录"""
    engine, data_query = backtest_setup
    
    # 使用简单测试策略
    strategy = StrategyFactory.create_strategy("simple_test", use_simple=True)
    assert strategy is not None
    
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    
    final_metrics = None
    trades = []
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        update_type = update.get('type')
        data = update.get('data', {})
        
        if update_type == 'new_trade':
            trades.append(data)
        elif update_type == 'final_metrics':
            final_metrics = data
            
    # 验证指标是否存在
    assert final_metrics is not None, "回测未生成最终指标"
    assert 'winRate' in final_metrics
    assert 'profitFactor' in final_metrics
    
    # 验证交易流水的一致性 (如果有交易)
    if trades:
        sell_trades = [t for t in trades if t.get('action') == 'sell']
        if sell_trades:
            # 至少验证卖出记录包含盈亏信息
            assert any('profit_loss' in t for t in sell_trades), "卖出记录缺少盈亏字段"
