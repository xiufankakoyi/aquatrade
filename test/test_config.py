"""
BacktestConfig 和 TradeRecord 单元测试

测试内容：
1. BacktestConfig 默认值验证
2. BacktestConfig 自定义值验证
3. TradeRecord 创建和属性验证
4. TradeRecord 盈亏计算验证
"""

import pytest
import numpy as np
from datetime import datetime
from dataclasses import asdict

from core.backtest.unified_engine import (
    BacktestConfig,
    TradeRecord,
    TimeGranularity
)


class TestBacktestConfig:
    """BacktestConfig 配置测试"""
    
    def test_default_values(self):
        """测试默认配置值"""
        config = BacktestConfig()
        
        assert config.initial_capital == 1_000_000.0
        assert config.commission_rate == 0.0003
        assert config.min_commission == 5.0
        assert config.sell_tax == 0.001
        assert config.time_granularity == TimeGranularity.DAILY
        assert config.max_positions is None
        assert config.position_ratio == 0.1
        assert config.max_stocks_per_day is None
        assert config.stop_loss is None
        assert config.take_profit is None
        assert config.max_holding_days is None
        assert config.warmup_days == 30
        assert config.execution_price == "open"
    
    def test_custom_values(self):
        """测试自定义配置值"""
        config = BacktestConfig(
            initial_capital=500_000.0,
            commission_rate=0.0005,
            min_commission=10.0,
            sell_tax=0.002,
            max_positions=10,
            position_ratio=0.2,
            max_stocks_per_day=5,
            stop_loss=-0.1,
            take_profit=0.2,
            max_holding_days=30,
            warmup_days=60,
            execution_price="close"
        )
        
        assert config.initial_capital == 500_000.0
        assert config.commission_rate == 0.0005
        assert config.min_commission == 10.0
        assert config.sell_tax == 0.002
        assert config.max_positions == 10
        assert config.position_ratio == 0.2
        assert config.max_stocks_per_day == 5
        assert config.stop_loss == -0.1
        assert config.take_profit == 0.2
        assert config.max_holding_days == 30
        assert config.warmup_days == 60
        assert config.execution_price == "close"
    
    def test_time_granularity_enum(self):
        """测试时间粒度枚举"""
        assert TimeGranularity.DAILY.value == "daily"
        assert TimeGranularity.MINUTE.value == "minute"
        assert TimeGranularity.TICK.value == "tick"
    
    def test_config_immutability(self):
        """测试配置不可变性（dataclass 默认可变，但验证字段类型）"""
        config = BacktestConfig()
        
        assert isinstance(config.initial_capital, float)
        assert isinstance(config.commission_rate, float)
        assert isinstance(config.min_commission, float)
        assert isinstance(config.warmup_days, int)
    
    def test_config_to_dict(self):
        """测试配置转换为字典"""
        config = BacktestConfig(initial_capital=500_000.0)
        config_dict = asdict(config)
        
        assert isinstance(config_dict, dict)
        assert config_dict['initial_capital'] == 500_000.0
        assert 'commission_rate' in config_dict
        assert 'position_ratio' in config_dict


class TestTradeRecord:
    """TradeRecord 交易记录测试"""
    
    def test_buy_trade_creation(self):
        """测试买入交易记录创建"""
        trade = TradeRecord(
            date="2025-06-03",
            code="000001",
            action="buy",
            shares=1000,
            price=10.5,
            amount=10500.0,
            commission=5.25,
            tax=0.0,
            holding_days=0,
            position_id="2025-06-03-000001"
        )
        
        assert trade.date == "2025-06-03"
        assert trade.code == "000001"
        assert trade.action == "buy"
        assert trade.shares == 1000
        assert trade.price == 10.5
        assert trade.amount == 10500.0
        assert trade.commission == 5.25
        assert trade.tax == 0.0
        assert trade.holding_days == 0
        assert trade.position_id == "2025-06-03-000001"
    
    def test_sell_trade_creation(self):
        """测试卖出交易记录创建"""
        trade = TradeRecord(
            date="2025-06-10",
            code="000001",
            action="sell",
            shares=1000,
            price=11.0,
            amount=11000.0,
            commission=5.5,
            tax=11.0,
            profit_loss=483.25,
            roi=4.6,
            entry_price=10.5,
            entry_date="2025-06-03",
            exit_price=11.0,
            exit_date="2025-06-10",
            holding_days=7,
            position_id="2025-06-03-000001"
        )
        
        assert trade.action == "sell"
        assert trade.profit_loss == 483.25
        assert trade.roi == 4.6
        assert trade.entry_price == 10.5
        assert trade.exit_price == 11.0
        assert trade.holding_days == 7
    
    def test_trade_profit_calculation(self):
        """测试交易盈亏计算逻辑"""
        buy_amount = 1000 * 10.5
        buy_commission = max(buy_amount * 0.0003, 5.0)
        
        sell_amount = 1000 * 11.0
        sell_commission = max(sell_amount * 0.0003, 5.0)
        sell_tax = sell_amount * 0.001
        
        total_cost = buy_amount + buy_commission
        total_revenue = sell_amount - sell_commission - sell_tax
        profit = total_revenue - total_cost
        
        expected_profit = 11000 - 5.5 - 11 - 10500 - 5.25
        assert abs(profit - expected_profit) < 1.0
    
    def test_trade_default_values(self):
        """测试交易记录默认值"""
        trade = TradeRecord(
            date="2025-06-03",
            code="000001",
            action="buy",
            shares=100,
            price=10.0,
            amount=1000.0,
            commission=5.0
        )
        
        assert trade.tax == 0.0
        assert trade.profit_loss == 0.0
        assert trade.roi == 0.0
        assert trade.entry_price == 0.0
        assert trade.entry_date == ""
        assert trade.exit_price == 0.0
        assert trade.exit_date == ""
        assert trade.holding_days == 0
        assert trade.position_id == ""
        assert trade.indicators == {}
    
    def test_trade_with_indicators(self):
        """测试带指标的交易记录"""
        indicators = {
            'ma5': 10.2,
            'ma10': 10.0,
            'rsi': 65.5,
            'volume_ratio': 1.5
        }
        
        trade = TradeRecord(
            date="2025-06-03",
            code="000001",
            action="buy",
            shares=100,
            price=10.0,
            amount=1000.0,
            commission=5.0,
            indicators=indicators
        )
        
        assert trade.indicators['ma5'] == 10.2
        assert trade.indicators['rsi'] == 65.5


class TestCommissionCalculation:
    """佣金计算测试"""
    
    def test_min_commission_applied(self):
        """测试最低佣金应用"""
        config = BacktestConfig()
        
        small_amount = 1000.0
        calculated_commission = small_amount * config.commission_rate
        actual_commission = max(calculated_commission, config.min_commission)
        
        assert actual_commission == config.min_commission
        assert actual_commission == 5.0
    
    def test_normal_commission(self):
        """测试正常佣金计算"""
        config = BacktestConfig()
        
        large_amount = 100_000.0
        calculated_commission = large_amount * config.commission_rate
        actual_commission = max(calculated_commission, config.min_commission)
        
        assert abs(actual_commission - 30.0) < 0.01
        assert actual_commission > config.min_commission
    
    def test_sell_tax_calculation(self):
        """测试卖出印花税计算"""
        config = BacktestConfig()
        
        sell_amount = 100_000.0
        tax = sell_amount * config.sell_tax
        
        assert tax == 100.0
    
    def test_total_transaction_cost_buy(self):
        """测试买入总成本"""
        config = BacktestConfig()
        
        price = 10.0
        shares = 1000
        amount = price * shares
        commission = max(amount * config.commission_rate, config.min_commission)
        total_cost = amount + commission
        
        assert total_cost == 10005.0
    
    def test_total_transaction_cost_sell(self):
        """测试卖出总收入"""
        config = BacktestConfig()
        
        price = 11.0
        shares = 1000
        amount = price * shares
        commission = max(amount * config.commission_rate, config.min_commission)
        tax = amount * config.sell_tax
        net_revenue = amount - commission - tax
        
        expected = 11000 - 5.5 - 11
        assert abs(net_revenue - expected) < 1.0


class TestPositionSizing:
    """仓位计算测试"""
    
    def test_position_ratio_calculation(self):
        """测试仓位比例计算"""
        config = BacktestConfig()
        
        cash = 1_000_000.0
        target_investment = cash * config.position_ratio
        
        assert target_investment == 100_000.0
    
    def test_max_shares_calculation(self):
        """测试最大股数计算"""
        config = BacktestConfig()
        
        target_investment = 100_000.0
        price = 10.0
        commission_rate = config.commission_rate
        
        max_shares = int(target_investment / (price * (1 + commission_rate)))
        rounded_shares = (max_shares // 100) * 100
        
        assert rounded_shares == 9900
    
    def test_position_limit_respected(self):
        """测试仓位限制遵守"""
        config = BacktestConfig(max_positions=5)
        
        current_positions = 3
        can_buy = config.max_positions - current_positions
        
        assert can_buy == 2
    
    def test_position_limit_full(self):
        """测试仓位已满"""
        config = BacktestConfig(max_positions=5)
        
        current_positions = 5
        can_buy = config.max_positions - current_positions
        
        assert can_buy == 0
