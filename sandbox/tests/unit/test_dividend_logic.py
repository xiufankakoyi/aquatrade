
import pytest
import pandas as pd
from unittest.mock import MagicMock
from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.strategy_framework import StrategyBase

class MockStrategy(StrategyBase):
    def generate_signals(self, current_date, stock_pool_today, data_query):
        return {}  # No signals

def test_dividend_handling():
    # 1. Setup engine and mocks
    data_query = MagicMock()
    engine = UnifiedBacktestEngine(data_query)
    engine.initial_capital = 100000.0
    
    # 2. Mock trading dates
    dates = ["2024-01-01", "2024-01-02"]
    data_query.get_trading_dates.return_value = dates
    
    # 3. Mock stock pool for Day 1
    # Stock 601988, Price 10, Factor 1.0, MV 10000 (Shares 1000)
    day1_pool = pd.DataFrame([{
        'stock_code': '601988',
        'trade_date': '2024-01-01',
        'open': 10.0,
        'high': 10.5,
        'low': 9.8,
        'close': 10.0,
        'volume': 100000,
        'adj_factor': 1.0,
        'total_mv': 1000000.0,
        'is_suspended': 0,
        'is_limit_up': 0,
        'is_limit_down': 0
    }])
    
    # Day 2: Dividend event
    # Factor 1.0 -> 1.1 (Approx 0.91 dividend per share)
    # Price drops due to dividend, but MV/Close (shares) remains stable
    # New factor 1.1, New Price approx 9.09
    day2_pool = pd.DataFrame([{
        'stock_code': '601988',
        'trade_date': '2024-01-02',
        'open': 9.09,
        'high': 9.2,
        'low': 9.0,
        'close': 9.09,
        'volume': 100000,
        'adj_factor': 1.1,
        'total_mv': 1000000.0 * (9.09 / 10.0), # MV adjusts with price
        'is_suspended': 0,
        'is_limit_up': 0,
        'is_limit_down': 0
    }])
    
    # total_mv / close logic:
    # Day 1: 1000000 / 10 = 100000 shares
    # Day 2: 909000 / 9.09 = 100000 shares (Stable)
    
    def side_effect(date):
        if date == "2024-01-01": return day1_pool
        return day2_pool
    
    # For daily granularity, engine calls get_stock_pool in its loop
    # Wait, the engine uses data_query.get_stock_pool implicitly via _get_stock_pool_at_time
    # but run_backtest_streaming calls self.data_query.get_stock_pool(current_date_str)
    # and if vectorized_mode is false, it uses strategy.generate_signals
    
    data_query.get_stock_pool.side_effect = side_effect
    data_query.get_all_daily_data_for_period.return_value = pd.concat([day1_pool, day2_pool])
    
    # 4. Inject initial position
    # We need to simulate having a position at the end of Day 1
    # FlexibleBacktestEngine doesn't have an 'initial_portfolio' param in run_backtest_streaming
    # but we can mock _execute_trades or pre-set it if we were testing internal methods.
    # To test the integration, we'll let it run.
    
    strategy = MockStrategy()
    
    # We need a way to have a position. Let's subclass and force a position.
    class DividendTestEngine(FlexibleBacktestEngine):
        def __init__(self, dq):
            super().__init__(dq)
            self.test_shares = 1000
            
        def run_backtest_streaming(self, start_date, end_date, strategy, **kwargs):
            # Override to inject position before loop
            gen = super().run_backtest_streaming(start_date, end_date, strategy, **kwargs)
            return gen

    engine = DividendTestEngine(data_query)
    
    # Actually, let's just use a simple Buy strategy for Day 1
    class BuyOnceStrategy(StrategyBase):
        def generate_signals(self, current_date, stock_pool_today, data_query):
            if current_date == "2024-01-01":
                return {'601988': 'buy'}
            return {}

    # Run backtest
    results = list(engine.run_backtest_streaming("2024-01-01", "2024-01-02", BuyOnceStrategy()))
    
    # 5. Verify
    # Initial Cash 100,000
    # Day 1: Buy 601988 at 10.0. Shares = 100,000 * 0.95 / 10 = 9500 shares.
    # (Assuming default position ratio 0.95)
    # Cash left: 100,000 - 95,000 = 5,000 (approx)
    # Day 2: Dividend detected.
    # Dividend per share = 10.0 * (1 - 1.0/1.1) = 10.0 * (0.1 / 1.1) = 0.90909...
    # Total Dividend = 9500 * 0.90909 = 8636.36
    # Final Cash should be approx 5000 + 8636 = 13636
    
    complete_event = next(e for e in results if e['type'] == 'stream_complete')
    final_equity = complete_event['data']['finalEquity']
    
    # Equity on Day 2 should reflect price 9.09 + dividend
    # 9500 * 9.09 + (5000 + 8636) = 86355 + 13636 = 99991 (approx 100k)
    # The important part is that dividend_payout event was yielded
    
    dividend_events = [e for e in results if e['type'] == 'dividend_payout']
    assert len(dividend_events) > 0
    assert dividend_events[0]['data']['code'] == '601988'
    assert dividend_events[0]['data']['dividend'] > 0
    
    print(f"✅ Dividend Test Passed! Total Dividend: {dividend_events[0]['data']['dividend']}")

if __name__ == "__main__":
    test_dividend_handling()
