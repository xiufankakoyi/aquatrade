"""
持仓管理测试

测试内容：
1. 持仓创建和更新
2. 持仓成本计算
3. 持仓市值计算
4. 持仓天数计算
5. 止损止盈检查
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from core.backtest.unified_engine import BacktestConfig


class TestPositionManagement:
    """持仓管理测试"""
    
    def test_position_creation(self):
        """测试持仓创建"""
        portfolio = {}
        position_info = {}
        
        code = "000001"
        shares = 1000
        cost = 10.5
        entry_date = "2025-06-03"
        
        portfolio[code] = shares
        position_info[code] = {
            'cost': cost,
            'entry_date': entry_date,
            'position_id': f"{entry_date}-{code}"
        }
        
        assert code in portfolio
        assert portfolio[code] == shares
        assert position_info[code]['cost'] == cost
    
    def test_position_update_after_buy(self):
        """测试买入后持仓更新"""
        portfolio = {'000001': 1000}
        cash = 1_000_000.0
        
        new_code = "000002"
        new_shares = 500
        new_cost = 20.0
        total_cost = new_shares * new_cost + 5.0  # 加佣金
        
        portfolio[new_code] = new_shares
        cash -= total_cost
        
        assert len(portfolio) == 2
        assert cash < 1_000_000.0
    
    def test_position_update_after_sell(self):
        """测试卖出后持仓更新"""
        portfolio = {'000001': 1000, '000002': 500}
        cash = 1_000_000.0
        
        sell_code = "000001"
        sell_shares = 1000
        sell_price = 11.0
        net_revenue = sell_shares * sell_price - 5.5 - 11  # 减佣金和印花税
        
        del portfolio[sell_code]
        cash += net_revenue
        
        assert len(portfolio) == 1
        assert '000001' not in portfolio
        assert cash > 1_000_000.0
    
    def test_position_cost_calculation(self, backtest_config):
        """测试持仓成本计算"""
        shares = 1000
        price = 10.0
        
        amount = shares * price
        commission = max(amount * backtest_config.commission_rate, backtest_config.min_commission)
        total_cost = amount + commission
        cost_per_share = total_cost / shares
        
        assert cost_per_share > price
        assert abs(cost_per_share - 10.005) < 0.001
    
    def test_position_market_value(self):
        """测试持仓市值计算"""
        portfolio = {'000001': 1000, '000002': 500}
        prices = {'000001': 11.0, '000002': 21.0}
        
        market_value = sum(portfolio[code] * prices[code] for code in portfolio)
        
        assert market_value == 1000 * 11.0 + 500 * 21.0


class TestHoldingDays:
    """持仓天数测试"""
    
    def test_holding_days_calculation(self):
        """测试持仓天数计算"""
        entry_date = datetime(2025, 6, 3)
        current_date = datetime(2025, 6, 10)
        
        holding_days = (current_date - entry_date).days
        
        assert holding_days == 7
    
    def test_holding_days_with_weekend(self):
        """测试包含周末的持仓天数"""
        entry_date = datetime(2025, 6, 6)  # 周五
        current_date = datetime(2025, 6, 9)  # 周一
        
        holding_days = (current_date - entry_date).days
        
        assert holding_days == 3
    
    def test_max_holding_days_check(self):
        """测试最大持仓天数检查"""
        max_holding_days = 10
        entry_date = datetime(2025, 6, 1)
        current_date = datetime(2025, 6, 12)
        
        holding_days = (current_date - entry_date).days
        should_sell = holding_days >= max_holding_days
        
        assert should_sell


class TestStopLossTakeProfit:
    """止损止盈测试"""
    
    def test_stop_loss_trigger(self):
        """测试止损触发"""
        stop_loss = -0.1  # -10%
        entry_price = 10.0
        current_price = 8.9
        
        pnl_pct = (current_price - entry_price) / entry_price
        should_stop_loss = pnl_pct <= stop_loss
        
        assert should_stop_loss
    
    def test_stop_loss_not_trigger(self):
        """测试止损未触发"""
        stop_loss = -0.1
        entry_price = 10.0
        current_price = 9.5
        
        pnl_pct = (current_price - entry_price) / entry_price
        should_stop_loss = pnl_pct <= stop_loss
        
        assert not should_stop_loss
    
    def test_take_profit_trigger(self):
        """测试止盈触发"""
        take_profit = 0.2  # 20%
        entry_price = 10.0
        current_price = 12.5
        
        pnl_pct = (current_price - entry_price) / entry_price
        should_take_profit = pnl_pct >= take_profit
        
        assert should_take_profit
    
    def test_take_profit_not_trigger(self):
        """测试止盈未触发"""
        take_profit = 0.2
        entry_price = 10.0
        current_price = 11.5
        
        pnl_pct = (current_price - entry_price) / entry_price
        should_take_profit = pnl_pct >= take_profit
        
        assert not should_take_profit


class TestPositionLimit:
    """持仓限制测试"""
    
    def test_max_positions_limit(self):
        """测试最大持仓数限制"""
        max_positions = 5
        current_positions = 3
        
        can_buy = max_positions - current_positions
        
        assert can_buy == 2
    
    def test_max_positions_full(self):
        """测试持仓已满"""
        max_positions = 5
        current_positions = 5
        
        can_buy = max_positions - current_positions
        
        assert can_buy == 0
    
    def test_position_ratio_limit(self, backtest_config):
        """测试仓位比例限制"""
        cash = 1_000_000.0
        price = 10.0
        
        target_investment = cash * backtest_config.position_ratio
        max_shares = int(target_investment / price)
        
        assert max_shares == 10000


class TestPortfolioValue:
    """组合价值测试"""
    
    def test_total_equity_calculation(self):
        """测试总权益计算"""
        cash = 800_000.0
        portfolio = {'000001': 1000, '000002': 500}
        prices = {'000001': 11.0, '000002': 21.0}
        
        position_value = sum(portfolio[code] * prices[code] for code in portfolio)
        total_equity = cash + position_value
        
        expected = 800_000 + 1000 * 11 + 500 * 21
        assert total_equity == expected
    
    def test_position_weight_calculation(self):
        """测试持仓权重计算"""
        cash = 800_000.0
        portfolio = {'000001': 1000, '000002': 500}
        prices = {'000001': 11.0, '000002': 21.0}
        
        position_value = sum(portfolio[code] * prices[code] for code in portfolio)
        total_equity = cash + position_value
        
        weights = {}
        for code in portfolio:
            weights[code] = portfolio[code] * prices[code] / total_equity
        
        assert abs(sum(weights.values()) - position_value / total_equity) < 0.001
    
    def test_cash_ratio_calculation(self):
        """测试现金比例计算"""
        cash = 800_000.0
        total_equity = 1_000_000.0
        
        cash_ratio = cash / total_equity
        
        assert cash_ratio == 0.8
