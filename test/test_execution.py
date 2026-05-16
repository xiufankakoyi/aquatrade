"""
交易执行测试

测试内容：
1. 买入执行逻辑
2. 卖出执行逻辑
3. 佣金计算
4. 涨跌停处理
5. 停牌处理
"""

import pytest
import numpy as np
import polars as pl
from datetime import datetime

from core.backtest.unified_engine import BacktestConfig, TradeRecord


class TestBuyExecution:
    """买入执行测试"""
    
    def test_basic_buy_execution(self, backtest_config):
        """测试基本买入执行"""
        cash = 1_000_000.0
        price = 10.0
        target_investment = cash * backtest_config.position_ratio
        
        shares = int(target_investment / (price * (1 + backtest_config.commission_rate)))
        shares = (shares // 100) * 100
        
        amount = shares * price
        commission = max(amount * backtest_config.commission_rate, backtest_config.min_commission)
        total_cost = amount + commission
        
        assert shares == 9900
        assert total_cost <= cash
    
    def test_buy_with_min_commission(self, backtest_config):
        """测试最低佣金买入"""
        price = 100.0
        shares = 100
        
        amount = shares * price
        commission = max(amount * backtest_config.commission_rate, backtest_config.min_commission)
        
        assert commission == backtest_config.min_commission
    
    def test_buy_shares_rounding(self):
        """测试股数取整（100股为单位）"""
        raw_shares = 1234
        rounded_shares = (raw_shares // 100) * 100
        
        assert rounded_shares == 1200
    
    def test_buy_insufficient_cash(self, backtest_config):
        """测试资金不足"""
        cash = 5000.0
        price = 100.0
        
        shares = int(cash / price)
        shares = (shares // 100) * 100
        
        assert shares == 0 or shares * price <= cash
    
    def test_buy_creates_trade_record(self, backtest_config):
        """测试买入创建交易记录"""
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
        
        assert trade.action == "buy"
        assert trade.shares == 1000
        assert trade.holding_days == 0


class TestSellExecution:
    """卖出执行测试"""
    
    def test_basic_sell_execution(self, backtest_config):
        """测试基本卖出执行"""
        shares = 1000
        price = 11.0
        
        amount = shares * price
        commission = max(amount * backtest_config.commission_rate, backtest_config.min_commission)
        tax = amount * backtest_config.sell_tax
        net_revenue = amount - commission - tax
        
        expected = 11000 - 5.5 - 11
        assert abs(net_revenue - expected) < 1.0
    
    def test_sell_with_profit(self, backtest_config):
        """测试盈利卖出"""
        buy_price = 10.0
        sell_price = 11.0
        shares = 1000
        
        buy_amount = shares * buy_price
        buy_commission = max(buy_amount * backtest_config.commission_rate, backtest_config.min_commission)
        total_cost = buy_amount + buy_commission
        
        sell_amount = shares * sell_price
        sell_commission = max(sell_amount * backtest_config.commission_rate, backtest_config.min_commission)
        sell_tax = sell_amount * backtest_config.sell_tax
        net_revenue = sell_amount - sell_commission - sell_tax
        
        profit = net_revenue - total_cost
        roi = profit / total_cost * 100
        
        assert profit > 0
        assert roi > 0
    
    def test_sell_with_loss(self, backtest_config):
        """测试亏损卖出"""
        buy_price = 10.0
        sell_price = 9.0
        shares = 1000
        
        buy_amount = shares * buy_price
        buy_commission = max(buy_amount * backtest_config.commission_rate, backtest_config.min_commission)
        total_cost = buy_amount + buy_commission
        
        sell_amount = shares * sell_price
        sell_commission = max(sell_amount * backtest_config.commission_rate, backtest_config.min_commission)
        sell_tax = sell_amount * backtest_config.sell_tax
        net_revenue = sell_amount - sell_commission - sell_tax
        
        profit = net_revenue - total_cost
        
        assert profit < 0
    
    def test_sell_creates_trade_record(self, backtest_config):
        """测试卖出创建交易记录"""
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
            entry_price=10.0,
            entry_date="2025-06-03",
            exit_price=11.0,
            exit_date="2025-06-10",
            holding_days=7,
            position_id="2025-06-03-000001"
        )
        
        assert trade.action == "sell"
        assert trade.profit_loss > 0
        assert trade.holding_days == 7


class TestLimitHandling:
    """涨跌停处理测试"""
    
    def test_limit_up_no_buy(self):
        """测试涨停不买入"""
        signals = {'000001': 'buy', '000002': 'buy'}
        limit_up_stocks = {'000001'}
        
        buyable = {k: v for k, v in signals.items() if k not in limit_up_stocks}
        
        assert '000001' not in buyable
        assert len(buyable) == 1
    
    def test_limit_down_no_sell(self):
        """测试跌停不卖出"""
        signals = {'000001': 'sell', '000002': 'sell'}
        limit_down_stocks = {'000001'}
        
        sellable = {k: v for k, v in signals.items() if k not in limit_down_stocks}
        
        assert '000001' not in sellable
        assert len(sellable) == 1
    
    def test_limit_detection(self):
        """测试涨跌停检测"""
        close = 10.0
        prev_close = 9.0
        
        change_pct = (close - prev_close) / prev_close * 100
        
        is_limit_up = change_pct >= 9.9
        is_limit_down = change_pct <= -9.9
        
        assert is_limit_up


class TestSuspensionHandling:
    """停牌处理测试"""
    
    def test_suspended_no_trade(self):
        """测试停牌不交易"""
        signals = {'000001': 'buy', '000002': 'buy'}
        suspended_stocks = {'000001'}
        
        tradeable = {k: v for k, v in signals.items() if k not in suspended_stocks}
        
        assert '000001' not in tradeable
        assert len(tradeable) == 1
    
    def test_suspension_data_missing(self):
        """测试停牌数据缺失"""
        data = {
            '000001': {'open': 10.0, 'close': 10.5},
            '000002': {'open': 0, 'close': 0, 'is_suspended': True}
        }
        
        for code, d in data.items():
            if d.get('is_suspended') or d.get('open', 0) == 0:
                data[code]['tradeable'] = False
            else:
                data[code]['tradeable'] = True
        
        assert data['000001']['tradeable'] == True
        assert data['000002']['tradeable'] == False


class TestVectorizedExecution:
    """向量化执行测试"""
    
    def test_build_signals_df(self):
        """测试构建信号 DataFrame"""
        signal_rows = [
            {'code': '000001', 'action': 'buy', 'indicators': {}},
            {'code': '000002', 'action': 'buy', 'indicators': {}},
            {'code': '000003', 'action': 'sell', 'indicators': {}},
        ]
        
        signals_df = pl.DataFrame(signal_rows)
        
        assert len(signals_df) == 3
        assert signals_df['action'].to_list() == ['buy', 'buy', 'sell']
    
    def test_build_market_df(self):
        """测试构建市场 DataFrame"""
        market_rows = [
            {'code': '000001', 'open': 10.0, 'close': 10.5, 'is_suspended': False, 'is_limit_up': False},
            {'code': '000002', 'open': 20.0, 'close': 20.5, 'is_suspended': False, 'is_limit_up': False},
        ]
        
        market_df = pl.DataFrame(market_rows)
        
        assert len(market_df) == 2
        assert market_df['open'].to_list() == [10.0, 20.0]
    
    def test_filter_buyable_signals(self):
        """测试过滤可买入信号"""
        signals_df = pl.DataFrame([
            {'code': '000001', 'action': 'buy'},
            {'code': '000002', 'action': 'buy'},
        ])
        
        market_df = pl.DataFrame([
            {'code': '000001', 'open': 10.0, 'close': 10.5, 'is_suspended': False, 'is_limit_up': False},
            {'code': '000002', 'open': 0, 'close': 0, 'is_suspended': True, 'is_limit_up': False},
            {'code': '000003', 'open': 15.0, 'close': 15.5, 'is_suspended': False, 'is_limit_up': False},
        ])
        
        buy_signals = signals_df.filter(pl.col('action') == 'buy')
        
        buyable = buy_signals.join(
            market_df.select(['code', 'close', 'open', 'is_suspended', 'is_limit_up']),
            on='code', how='inner'
        ).filter(
            ((pl.col('close') > 0) | (pl.col('open') > 0)) &
            (pl.col('is_suspended') == False) &
            (pl.col('is_limit_up') == False)
        )
        
        assert len(buyable) == 1
        assert buyable['code'].to_list() == ['000001']
    
    def test_calculate_shares_vectorized(self, backtest_config):
        """测试向量化计算股数"""
        buyable = pl.DataFrame([
            {'code': '000001', 'open': 10.0, 'close': 10.5},
            {'code': '000002', 'open': 20.0, 'close': 20.5},
        ])
        
        new_cash = 1_000_000.0
        target_investment = new_cash * backtest_config.position_ratio
        
        buyable = buyable.with_columns([
            pl.when(pl.col('open') > 0)
            .then(pl.col('open'))
            .otherwise(pl.col('close'))
            .alias('trade_price')
        ])
        
        buyable = buyable.with_columns([
            (target_investment / (pl.col('trade_price') * (1 + backtest_config.commission_rate)))
            .floor().alias('raw_shares'),
        ]).with_columns([
            ((pl.col('raw_shares') // 100) * 100).alias('shares'),
        ])
        
        shares_list = buyable['shares'].to_list()
        assert all(s >= 100 for s in shares_list)
