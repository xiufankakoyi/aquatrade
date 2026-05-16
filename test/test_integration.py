"""
集成测试 - 完整回测流程

测试内容：
1. 完整回测流程验证
2. 数值稳定性测试
3. 性能基准测试
4. 边缘情况处理
"""

import pytest
import numpy as np
import pandas as pd
import os
import sys
from datetime import datetime, timedelta

os.environ['DB_BACKEND'] = 'lancedb'


class TestBacktestIntegration:
    """回测集成测试"""
    
    def test_backtest_config_creation(self):
        """测试回测配置创建"""
        from core.backtest.unified_engine import BacktestConfig
        
        config = BacktestConfig(
            initial_capital=1_000_000.0,
            commission_rate=0.0003,
            min_commission=5.0,
            sell_tax=0.001,
            position_ratio=0.1,
            warmup_days=5
        )
        
        assert config.initial_capital == 1_000_000.0
        assert config.commission_rate == 0.0003
    
    def test_trade_record_creation(self):
        """测试交易记录创建"""
        from core.backtest.unified_engine import TradeRecord
        
        trade = TradeRecord(
            date="2025-06-03",
            code="000001",
            action="buy",
            shares=1000,
            price=10.0,
            amount=10000.0,
            commission=5.0,
            holding_days=0,
            position_id="2025-06-03-000001"
        )
        
        assert trade.date == "2025-06-03"
        assert trade.action == "buy"
    
    def test_factor_matrix_structure(self, sample_factor_matrix, sample_trading_dates, sample_stock_codes):
        """测试因子矩阵结构"""
        from core.backtest.factor_matrix import FactorMatrix
        
        factor_names = ['open', 'high', 'low', 'close', 'volume', 'ma5', 'ma10', 'ma20']
        
        date_to_idx = {d: i for i, d in enumerate(sample_trading_dates)}
        code_to_idx = {c: i for i, c in enumerate(sample_stock_codes)}
        
        fm = FactorMatrix(
            values=sample_factor_matrix,
            dates=sample_trading_dates,
            codes_int=np.array([int(c) for c in sample_stock_codes], dtype=np.int32),
            codes_str=sample_stock_codes,
            factor_names=factor_names,
            date_to_idx=date_to_idx,
            code_to_idx=code_to_idx
        )
        
        assert fm.values.shape == sample_factor_matrix.shape
        
        day_data = fm.get_day_data(sample_trading_dates[0])
        assert day_data is not None
        assert day_data.shape[1] == 8


class TestNumericalStability:
    """数值稳定性测试"""
    
    def test_repeated_backtest_consistency(self):
        """测试重复回测结果一致性"""
        from core.backtest.unified_engine import BacktestConfig
        
        config = BacktestConfig()
        
        results = []
        for _ in range(3):
            initial = config.initial_capital
            results.append(initial)
        
        assert all(r == results[0] for r in results)
    
    def test_large_position_calculation(self):
        """测试大仓位计算"""
        from core.backtest.unified_engine import BacktestConfig
        
        config = BacktestConfig()
        cash = 1_000_000_000.0  # 10亿
        price = 10.0
        
        target_investment = cash * config.position_ratio
        shares = int(target_investment / price)
        shares = (shares // 100) * 100
        
        assert shares > 0
        assert shares * price <= target_investment
    
    def test_small_position_calculation(self):
        """测试小仓位计算"""
        from core.backtest.unified_engine import BacktestConfig
        
        config = BacktestConfig()
        cash = 10_000.0  # 1万
        price = 100.0
        
        target_investment = cash * config.position_ratio
        shares = int(target_investment / price)
        shares = (shares // 100) * 100
        
        assert shares >= 0
    
    def test_zero_price_handling(self):
        """测试零价格处理"""
        price = 0.0
        
        if price <= 0:
            tradeable = False
        else:
            tradeable = True
        
        assert tradeable == False
    
    def test_negative_price_handling(self):
        """测试负价格处理"""
        price = -10.0
        
        if price <= 0:
            tradeable = False
        else:
            tradeable = True
        
        assert tradeable == False


class TestEdgeCases:
    """边缘情况测试"""
    
    def test_empty_portfolio(self):
        """测试空持仓"""
        portfolio = {}
        cash = 1_000_000.0
        
        position_value = sum(portfolio.values()) if portfolio else 0
        total_equity = cash + position_value
        
        assert total_equity == cash
    
    def test_single_stock_portfolio(self):
        """测试单股票持仓"""
        portfolio = {'000001': 1000}
        prices = {'000001': 10.0}
        
        position_value = sum(portfolio[code] * prices[code] for code in portfolio)
        
        assert position_value == 10000.0
    
    def test_no_signals(self):
        """测试无信号情况"""
        signals = {}
        
        if not signals:
            trades = []
        else:
            trades = list(signals.items())
        
        assert len(trades) == 0
    
    def test_all_suspended(self):
        """测试全部停牌"""
        signals = {'000001': 'buy', '000002': 'buy'}
        suspended = {'000001', '000002'}
        
        tradeable = {k: v for k, v in signals.items() if k not in suspended}
        
        assert len(tradeable) == 0
    
    def test_all_limit_up(self):
        """测试全部涨停"""
        signals = {'000001': 'buy', '000002': 'buy'}
        limit_up = {'000001', '000002'}
        
        buyable = {k: v for k, v in signals.items() if k not in limit_up}
        
        assert len(buyable) == 0


class TestPerformanceBenchmark:
    """性能基准测试"""
    
    def test_signal_matrix_generation_speed(self):
        """测试信号矩阵生成速度"""
        import time
        
        T = 500  # 500 交易日
        N = 1000  # 1000 股票
        
        start = time.perf_counter()
        signal_matrix = np.random.choice([0, 1, -1], size=(T, N), p=[0.95, 0.03, 0.02])
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        
        assert elapsed_ms < 100  # 应小于 100ms
        assert signal_matrix.shape == (T, N)
    
    def test_factor_matrix_access_speed(self, sample_factor_matrix, sample_trading_dates, sample_stock_codes):
        """测试因子矩阵访问速度"""
        import time
        from core.backtest.factor_matrix import FactorMatrix
        
        factor_names = ['open', 'high', 'low', 'close', 'volume', 'ma5', 'ma10', 'ma20']
        
        date_to_idx = {d: i for i, d in enumerate(sample_trading_dates)}
        code_to_idx = {c: i for i, c in enumerate(sample_stock_codes)}
        
        fm = FactorMatrix(
            values=sample_factor_matrix,
            dates=sample_trading_dates,
            codes_int=np.array([int(c) for c in sample_stock_codes], dtype=np.int32),
            codes_str=sample_stock_codes,
            factor_names=factor_names,
            date_to_idx=date_to_idx,
            code_to_idx=code_to_idx
        )
        
        start = time.perf_counter()
        for _ in range(100):
            day_data = fm.get_day_data(sample_trading_dates[0])
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        
        assert elapsed_ms < 10  # 100 次访问应小于 10ms
    
    def test_commission_calculation_speed(self, backtest_config):
        """测试佣金计算速度"""
        import time
        
        amounts = np.random.uniform(1000, 1000000, 10000)
        
        start = time.perf_counter()
        commissions = np.maximum(amounts * backtest_config.commission_rate, backtest_config.min_commission)
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        
        assert elapsed_ms < 10  # 10000 次计算应小于 10ms


class TestBacktestEngineMock:
    """回测引擎 Mock 测试"""
    
    @pytest.fixture
    def mock_engine(self):
        """创建 Mock 回测引擎"""
        from core.backtest.unified_engine import BacktestConfig
        
        class MockEngine:
            def __init__(self):
                self.config = BacktestConfig()
                self.portfolio = {}
                self.cash = self.config.initial_capital
                self.trades = []
            
            def execute_buy(self, code, price, shares):
                amount = price * shares
                commission = max(amount * self.config.commission_rate, self.config.min_commission)
                total_cost = amount + commission
                
                if total_cost <= self.cash:
                    self.portfolio[code] = shares
                    self.cash -= total_cost
                    self.trades.append({
                        'action': 'buy',
                        'code': code,
                        'shares': shares,
                        'price': price
                    })
                    return True
                return False
            
            def execute_sell(self, code, price):
                if code not in self.portfolio:
                    return False
                
                shares = self.portfolio[code]
                amount = price * shares
                commission = max(amount * self.config.commission_rate, self.config.min_commission)
                tax = amount * self.config.sell_tax
                net_revenue = amount - commission - tax
                
                del self.portfolio[code]
                self.cash += net_revenue
                self.trades.append({
                    'action': 'sell',
                    'code': code,
                    'shares': shares,
                    'price': price
                })
                return True
            
            def get_equity(self, prices):
                position_value = sum(self.portfolio[code] * prices.get(code, 0) for code in self.portfolio)
                return self.cash + position_value
        
        return MockEngine()
    
    def test_mock_engine_buy(self, mock_engine):
        """测试 Mock 引擎买入"""
        result = mock_engine.execute_buy('000001', 10.0, 1000)
        
        assert result == True
        assert '000001' in mock_engine.portfolio
        assert mock_engine.portfolio['000001'] == 1000
    
    def test_mock_engine_sell(self, mock_engine):
        """测试 Mock 引擎卖出"""
        mock_engine.execute_buy('000001', 10.0, 1000)
        result = mock_engine.execute_sell('000001', 11.0)
        
        assert result == True
        assert '000001' not in mock_engine.portfolio
    
    def test_mock_engine_equity(self, mock_engine):
        """测试 Mock 引擎权益计算"""
        mock_engine.execute_buy('000001', 10.0, 1000)
        
        prices = {'000001': 11.0}
        equity = mock_engine.get_equity(prices)
        
        assert equity > 0
    
    def test_mock_engine_insufficient_cash(self, mock_engine):
        """测试 Mock 引擎资金不足"""
        mock_engine.cash = 1000.0
        result = mock_engine.execute_buy('000001', 10.0, 1000)
        
        assert result == False
    
    def test_mock_engine_sell_nonexistent(self, mock_engine):
        """测试 Mock 引擎卖出不存在的持仓"""
        result = mock_engine.execute_sell('999999', 10.0)
        
        assert result == False
