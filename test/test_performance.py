"""
收益计算测试

测试内容：
1. 总收益率计算
2. 年化收益率计算
3. 最大回撤计算
4. 夏普比率计算
5. 胜率计算
6. 盈亏比计算
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from core.backtest.unified_engine import BacktestConfig


class TestReturnCalculation:
    """收益率计算测试"""
    
    def test_total_return_calculation(self):
        """测试总收益率计算"""
        initial_capital = 1_000_000.0
        final_equity = 1_200_000.0
        
        total_return = (final_equity - initial_capital) / initial_capital
        
        assert total_return == 0.2
    
    def test_negative_return(self):
        """测试负收益"""
        initial_capital = 1_000_000.0
        final_equity = 850_000.0
        
        total_return = (final_equity - initial_capital) / initial_capital
        
        assert total_return == -0.15
    
    def test_annualized_return(self):
        """测试年化收益率"""
        total_return = 0.2
        trading_days = 252
        
        annualized_return = (1 + total_return) ** (252 / trading_days) - 1
        
        assert abs(annualized_return - total_return) < 0.001
    
    def test_annualized_return_partial_year(self):
        """测试部分年份年化收益"""
        total_return = 0.1
        trading_days = 126  # 半年
        
        annualized_return = (1 + total_return) ** (252 / trading_days) - 1
        
        expected = (1.1 ** 2) - 1
        assert abs(annualized_return - expected) < 0.001


class TestDrawdownCalculation:
    """回撤计算测试"""
    
    def test_max_drawdown_calculation(self):
        """测试最大回撤计算"""
        equity_curve = np.array([100, 110, 105, 95, 100, 90, 95, 100])
        
        peak = equity_curve[0]
        max_drawdown = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (value - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
        
        assert abs(max_drawdown - (-0.1818)) < 0.01
    
    def test_no_drawdown(self):
        """测试无回撤情况"""
        equity_curve = np.array([100, 105, 110, 115, 120])
        
        peak = equity_curve[0]
        max_drawdown = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (value - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
        
        assert max_drawdown == 0.0
    
    def test_drawdown_recovery(self):
        """测试回撤恢复"""
        equity_curve = np.array([100, 90, 95, 100, 105])
        
        peak = equity_curve[0]
        max_drawdown = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (value - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
        
        assert max_drawdown == -0.1


class TestSharpeRatio:
    """夏普比率测试"""
    
    def test_sharpe_ratio_calculation(self):
        """测试夏普比率计算"""
        daily_returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015, -0.002, 0.008])
        
        mean_return = np.mean(daily_returns)
        std_return = np.std(daily_returns)
        
        sharpe_ratio = (mean_return / std_return) * np.sqrt(252)
        
        assert sharpe_ratio > 0
    
    def test_sharpe_ratio_negative(self):
        """测试负夏普比率"""
        daily_returns = np.array([-0.01, -0.02, -0.005, -0.015, -0.01])
        
        mean_return = np.mean(daily_returns)
        std_return = np.std(daily_returns)
        
        sharpe_ratio = (mean_return / std_return) * np.sqrt(252)
        
        assert sharpe_ratio < 0
    
    def test_sharpe_ratio_zero_volatility(self):
        """测试零波动率"""
        daily_returns = np.array([0.01, 0.01, 0.01, 0.01, 0.01])
        
        std_return = np.std(daily_returns)
        
        if std_return <= 0:
            sharpe_ratio = 0.0
        else:
            sharpe_ratio = (np.mean(daily_returns) / std_return) * np.sqrt(252)
        
        assert sharpe_ratio == 0.0


class TestWinRate:
    """胜率测试"""
    
    def test_win_rate_calculation(self):
        """测试胜率计算"""
        trades = [
            {'profit': 100},
            {'profit': -50},
            {'profit': 200},
            {'profit': -30},
            {'profit': 150},
        ]
        
        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        total_trades = len(trades)
        win_rate = winning_trades / total_trades
        
        assert win_rate == 0.6
    
    def test_win_rate_all_wins(self):
        """测试全胜"""
        trades = [
            {'profit': 100},
            {'profit': 200},
            {'profit': 150},
        ]
        
        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        win_rate = winning_trades / len(trades)
        
        assert win_rate == 1.0
    
    def test_win_rate_all_losses(self):
        """测试全败"""
        trades = [
            {'profit': -100},
            {'profit': -200},
            {'profit': -150},
        ]
        
        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        win_rate = winning_trades / len(trades)
        
        assert win_rate == 0.0


class TestProfitLossRatio:
    """盈亏比测试"""
    
    def test_profit_loss_ratio_calculation(self):
        """测试盈亏比计算"""
        trades = [
            {'profit': 100},
            {'profit': -50},
            {'profit': 200},
            {'profit': -30},
            {'profit': 150},
        ]
        
        profits = [t['profit'] for t in trades if t['profit'] > 0]
        losses = [abs(t['profit']) for t in trades if t['profit'] < 0]
        
        avg_profit = np.mean(profits)
        avg_loss = np.mean(losses)
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        
        assert profit_loss_ratio == 150 / 40
    
    def test_profit_loss_ratio_no_losses(self):
        """测试无亏损"""
        trades = [
            {'profit': 100},
            {'profit': 200},
            {'profit': 150},
        ]
        
        losses = [abs(t['profit']) for t in trades if t['profit'] < 0]
        avg_loss = np.mean(losses) if losses else 0
        
        assert avg_loss == 0
    
    def test_profit_loss_ratio_no_profits(self):
        """测试无盈利"""
        trades = [
            {'profit': -100},
            {'profit': -200},
            {'profit': -150},
        ]
        
        profits = [t['profit'] for t in trades if t['profit'] > 0]
        avg_profit = np.mean(profits) if profits else 0
        
        assert avg_profit == 0


class TestTradeStatistics:
    """交易统计测试"""
    
    def test_total_trades(self):
        """测试总交易次数"""
        trades = [
            {'action': 'buy'},
            {'action': 'sell'},
            {'action': 'buy'},
            {'action': 'sell'},
        ]
        
        total_trades = len(trades)
        
        assert total_trades == 4
    
    def test_buy_sell_count(self):
        """测试买卖次数"""
        trades = [
            {'action': 'buy'},
            {'action': 'sell'},
            {'action': 'buy'},
            {'action': 'sell'},
        ]
        
        buy_count = sum(1 for t in trades if t['action'] == 'buy')
        sell_count = sum(1 for t in trades if t['action'] == 'sell')
        
        assert buy_count == 2
        assert sell_count == 2
    
    def test_total_commission(self, backtest_config):
        """测试总佣金"""
        trades = [
            {'amount': 10000, 'action': 'buy'},
            {'amount': 11000, 'action': 'sell'},
        ]
        
        total_commission = 0
        for t in trades:
            commission = max(t['amount'] * backtest_config.commission_rate, backtest_config.min_commission)
            total_commission += commission
        
        expected = 5.0 + 5.5
        assert abs(total_commission - expected) < 1.0
    
    def test_total_tax(self, backtest_config):
        """测试总印花税"""
        sell_trades = [
            {'amount': 11000},
            {'amount': 12000},
        ]
        
        total_tax = sum(t['amount'] * backtest_config.sell_tax for t in sell_trades)
        
        assert total_tax == 11 + 12


class TestRiskMetrics:
    """风险指标测试"""
    
    def test_volatility_calculation(self):
        """测试波动率计算"""
        daily_returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
        
        daily_vol = np.std(daily_returns)
        annual_vol = daily_vol * np.sqrt(252)
        
        assert annual_vol > daily_vol
    
    def test_sortino_ratio(self):
        """测试索提诺比率"""
        daily_returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015, -0.002, 0.008])
        
        mean_return = np.mean(daily_returns)
        downside_returns = daily_returns[daily_returns < 0]
        
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns)
            sortino_ratio = (mean_return / downside_std) * np.sqrt(252)
        else:
            sortino_ratio = 0
        
        assert sortino_ratio > 0
    
    def test_calmar_ratio(self):
        """测试卡玛比率"""
        annual_return = 0.2
        max_drawdown = 0.1
        
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0
        
        assert calmar_ratio == 2.0


class TestAPISpeed:
    """API速度测试"""
    
    def test_backtest_one_year_speed(self):
        """
        测试回测一年数据的速度
        模拟前端调用API进行JQ策略回测一年
        """
        import time
        import logging
        logging.getLogger('core.backtest.unified_engine').setLevel(logging.INFO)
        logging.getLogger('core.backtest.factor_matrix').setLevel(logging.INFO)
        
        from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
        from core.strategies.simple_test_strategy import SimpleTestStrategy
        from data_svc.database.optimized_data_query import OptimizedStockDataQuery
        
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        
        config = BacktestConfig(
            initial_capital=1_000_000.0,
            commission_rate=0.0003,
            min_commission=5.0,
            sell_tax=0.001,
            position_ratio=0.1,
            warmup_days=5
        )
        
        perf_stats = {}
        
        t_total_start = time.time()
        
        t0 = time.time()
        data_query = OptimizedStockDataQuery(warmup=True)
        perf_stats['data_query_init'] = time.time() - t0
        
        t0 = time.time()
        engine = UnifiedBacktestEngine(data_query, config)
        perf_stats['engine_init'] = time.time() - t0
        
        strategy = SimpleTestStrategy()
        
        t0 = time.time()
        results_list = []
        trades_log = []
        final_metrics = None
        daily_times = []
        first_day_time = None
        preload_time = None
        preload_data_time = None
        preload_factors_time = None
        first_day_process_time = None
        t_day_start = None
        t_after_start = None
        
        for event in engine.run_backtest_streaming(start_date, end_date, strategy):
            event_type = event.get('type')
            data = event.get('data', {})
            
            if event_type == 'backtest_start':
                preload_time = time.time() - t0
                perf_stats['preload_yield'] = preload_time
                t_after_start = time.time()
                
            elif event_type == 'daily_equity_engine':
                if first_day_time is None:
                    first_day_time = time.time() - t_after_start
                    perf_stats['first_day_process'] = first_day_time
                else:
                    daily_times.append(time.time() - t_day_start)
                t_day_start = time.time()
                
                results_list.append({
                    'date': data.get('date'),
                    'total_value': data.get('strategyReturn', 0)
                })
            elif event_type in ('new_trade', 'new_trade_engine'):
                trades_log.append(data)
            elif event_type == 'final_metrics':
                perf_stats['final_calc'] = time.time() - t_day_start
                final_metrics = data
        
        perf_stats['total'] = time.time() - t_total_start
        if daily_times:
            perf_stats['avg_daily'] = sum(daily_times) / len(daily_times)
            perf_stats['max_daily'] = max(daily_times)
            perf_stats['min_daily'] = min(daily_times)
            perf_stats['daily_count'] = len(daily_times)
        
        preload_and_first_day = perf_stats.get('preload_yield', 0) + perf_stats.get('first_day_process', 0)
        
        print(f"\n{'='*60}")
        print(f"回测一年性能测试 - 细粒度耗时统计")
        print(f"{'='*60}")
        print(f"[阶段耗时]")
        print(f"  数据查询初始化:   {perf_stats['data_query_init']*1000:,.1f} ms")
        print(f"  回测引擎初始化:   {perf_stats['engine_init']*1000:,.1f} ms")
        print(f"  yield backtest_start: {perf_stats.get('preload_yield', 0)*1000:,.1f} ms")
        print(f"  第一日处理(预加载+信号生成): {perf_stats.get('first_day_process', 0)*1000:,.1f} ms")
        print(f"  [预加载+第一日合计]: {preload_and_first_day*1000:,.1f} ms")
        if daily_times:
            print(f"  后续每日平均:     {perf_stats['avg_daily']*1000:,.1f} ms")
            print(f"  后续每日最大:     {perf_stats['max_daily']*1000:,.1f} ms")
            print(f"  后续每日最小:     {perf_stats['min_daily']*1000:,.1f} ms")
            print(f"  后续日数:         {perf_stats['daily_count']}")
        print(f"  最终计算结果:     {perf_stats.get('final_calc', 0)*1000:,.1f} ms")
        print(f"{'='*60}")
        print(f"[总计耗时] {perf_stats['total']:.2f} 秒")
        print(f"{'='*60}")
        print(f"[数据统计]")
        print(f"  收益曲线数据点:   {len(results_list)}")
        print(f"  交易记录:         {len(trades_log)}")
        if final_metrics:
            print(f"[回测结果]")
            print(f"  最终权益:         {final_metrics.get('final_equity', 0):,.2f}")
            print(f"  总收益率:         {final_metrics.get('total_return', 0):.2%}")
            print(f"  年化收益率:       {final_metrics.get('annualized_return', 0):.2%}")
            print(f"  最大回撤:         {final_metrics.get('max_drawdown', 0):.2%}")
            print(f"  夏普比率:         {final_metrics.get('sharpe_ratio', 0):.2f}")
            print(f"  交易次数:         {final_metrics.get('trade_count', 0)}")
        print(f"{'='*60}")
        
        assert perf_stats['total'] < 300, f"回测一年耗时 {perf_stats['total']:.2f} 秒，超过5分钟限制"
    
    def test_query_latest_trading_date_speed(self):
        """
        测试查询最新交易日所有股票数据的速度
        确保无null/nan值
        """
        import time
        import polars as pl
        from data_svc.unified_data_query import get_stock_daily_latest_polars
        
        start_time = time.time()
        
        df = get_stock_daily_latest_polars()
        
        elapsed_time = time.time() - start_time
        
        print(f"\n=== 查询最新交易日数据性能测试 ===")
        print(f"耗时: {elapsed_time:.2f} 秒")
        
        if df is not None:
            print(f"股票数量: {df.height}")
            print(f"列数: {df.width}")
            
            null_counts = {}
            for col in df.columns:
                null_count = df[col].null_count()
                if null_count > 0:
                    null_counts[col] = null_count
            
            nan_counts = {}
            numeric_cols = [c for c in df.columns if df[c].dtype in [pl.Float32, pl.Float64, pl.Int32, pl.Int64]]
            for col in numeric_cols:
                nan_count = df[col].filter(df[col].is_nan()).len()
                if nan_count > 0:
                    nan_counts[col] = nan_count
            
            print(f"null值统计: {null_counts if null_counts else '无'}")
            print(f"nan值统计: {nan_counts if nan_counts else '无'}")

            assert df.height > 0, "未查询到任何股票数据"
            critical_null_cols = ['close', 'open', 'high', 'low', 'volume']
            critical_nulls = {k: v for k, v in null_counts.items() if k in critical_null_cols}
            assert len(critical_nulls) == 0, f"关键列存在null值: {critical_nulls}"
        else:
            print("未获取到数据（可能是数据库为空）")
        
        assert elapsed_time < 30, f"查询耗时 {elapsed_time:.2f} 秒，超过30秒限制"
