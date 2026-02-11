"""
指标计算服务
负责回测指标的计算（收益率、回撤、风险等）
"""
from typing import Dict, List, Any
import pandas as pd
try:
    import cupy as np
except ImportError:
    import numpy as np
from server.services.data_initialization_service import DataInitializationService
from server.services.stock_data_service import StockDataService


class MetricsService:
    """指标计算服务类"""
    
    def __init__(self, init_service: DataInitializationService, stock_data_service: StockDataService):
        self.init_service = init_service
        self.stock_data_service = stock_data_service
    
    def calculate_metrics_from_df(self, results_df: pd.DataFrame, trades_log: List[Dict]) -> Dict:
        """
        用于流式回测的最终指标计算
        
        Returns:
            dict: 包含所有回测指标的字典，若无交易则返回 EmptyMetrics 并设置 warning_level
        """
        # [Modified] 任务C：计算后端保护 - 短路处理无交易情况
        # 统计卖出交易数量
        sell_trades_count = len([t for t in trades_log if t.get('action') == 'sell'])
        
        if sell_trades_count == 0:
            # 无交易情况：返回预定义的 EmptyMetrics 并设置警告级别
            logger.warning("[Metrics] 无卖出交易记录，触发 EmptyMetrics 保护机制")
            return {
                "totalReturn": 0.0,
                "annualizedReturn": 0.0,
                "maxDrawdown": 0.0,
                "sharpeRatio": 0.0,
                "sortinoRatio": 0.0,
                "volatility": 0.0,
                "winRate": 0.0,
                "profitFactor": 0.0,
                "tradesCount": 0,
                "avgTradeReturn": 0.0,
                "maxWinningStreak": 0,
                "maxLosingStreak": 0,
                "calmarRatio": 0.0,
                "warning_level": "warning",  # [Added] 标记警告级别
                "_empty_metrics": True       # [Added] 标记为空指标
            }
        
        initial_capital = self.init_service.initial_capital
        final_value = results_df['total_value'].iloc[-1]
        total_return = (final_value / initial_capital - 1) * 100

        days = len(results_df)
        years = days / 252.0
        annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else total_return

        results_df['cummax'] = results_df['total_value'].cummax()
        results_df['drawdown'] = (results_df['total_value'] - results_df['cummax']) / results_df['cummax']
        max_drawdown = results_df['drawdown'].min() * 100

        # 日收益率
        daily_returns = results_df['total_value'].pct_change().dropna()
        if len(daily_returns) > 1:
            dr_mean = daily_returns.mean()
            dr_std = daily_returns.std()
            sharpe_ratio = (dr_mean / dr_std) * np.sqrt(252) if dr_std > 0 else 0

            downside_returns = daily_returns[daily_returns < 0]
            if len(downside_returns) > 0:
                downside_std = downside_returns.std()
                sortino_ratio = (dr_mean / downside_std) * np.sqrt(252) if downside_std > 0 else 0
            else:
                sortino_ratio = 0

            volatility = dr_std * np.sqrt(252) * 100  # 年化波动率（%）
        else:
            sharpe_ratio = 0
            sortino_ratio = 0
            volatility = 0

        # 交易统计
        trades_count = len(trades_log)
        win_trades = 0
        total_pnl = 0
        total_profit = 0
        total_loss = 0

        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0

        sum_trade_return_pct = 0.0  # 用来算"平均每笔收益率（%）"

        # 使用回测引擎已经计算好的profit_loss字段，而不是重新计算
        for trade in trades_log:
            action = trade['action']
            
            if action == 'sell':
                # 优先使用回测引擎已经计算好的profit_loss字段
                pnl = trade.get('profit_loss', 0)
                
                # 如果没有profit_loss字段，再使用回测引擎计算的roi和value来计算
                if pnl == 0 and 'roi' in trade and 'value' in trade:
                    pnl = (trade['roi'] / 100) * trade['value']

                # 统计盈亏次数 & 盈利/亏损总额
                if pnl > 0:
                    win_trades += 1
                    total_profit += pnl
                    current_win_streak += 1
                    max_win_streak = max(max_win_streak, current_win_streak)
                    current_loss_streak = 0
                elif pnl < 0:
                    total_loss += abs(pnl)
                    current_loss_streak += 1
                    max_loss_streak = max(max_loss_streak, current_loss_streak)
                    current_win_streak = 0
                else:
                    current_win_streak = 0
                    current_loss_streak = 0

                total_pnl += pnl

                # 单笔收益率（相对于成本）
                # 使用回测引擎已经计算好的trade_return_pct或roi字段
                if 'roi' in trade:
                    sum_trade_return_pct += trade['roi']
                elif 'trade_return_pct' in trade:
                    sum_trade_return_pct += trade['trade_return_pct']
                else:
                    # 如果没有这些字段，再使用pnl和cost计算
                    avg_cost = trade.get('entry_price', trade.get('price', 0))
                    exposure = avg_cost * trade.get('quantity', 0)
                    if exposure > 0:
                        trade_return_pct = (pnl / exposure) * 100
                        sum_trade_return_pct += trade_return_pct

        # [Unchanged] 后续逻辑保持不变
        avg_trade_return = (sum_trade_return_pct / sell_trades_count) if sell_trades_count > 0 else 0

        def _to_scalar(x: Any) -> float:
            try:
                if isinstance(x, (int, float)):
                    return float(x)
                arr = np.asarray(x)
                if arr.shape == ():
                    return float(arr)
                return float(arr.mean())
            except Exception:
                return 0.0

        total_return_v = _to_scalar(total_return)
        annualized_return_v = _to_scalar(annualized_return)
        max_drawdown_v = _to_scalar(max_drawdown)
        sharpe_ratio_v = _to_scalar(sharpe_ratio)
        sortino_ratio_v = _to_scalar(sortino_ratio)
        volatility_v = _to_scalar(volatility)
        win_rate_v = _to_scalar(win_rate)
        profit_factor_v = _to_scalar(profit_factor)
        avg_trade_return_v = _to_scalar(avg_trade_return)

        # Calmar 比率 = 年化收益率 / |最大回撤|
        calmar_ratio_v = 0.0
        if abs(max_drawdown_v) > 1e-8:
            calmar_ratio_v = annualized_return_v / abs(max_drawdown_v)

        return {
            "totalReturn": round(total_return_v, 2),
            "annualizedReturn": round(annualized_return_v, 2),
            "maxDrawdown": round(max_drawdown_v, 2),
            "sharpeRatio": round(sharpe_ratio_v, 2),
            "sortinoRatio": round(sortino_ratio_v, 2),
            "volatility": round(volatility_v, 2),
            "winRate": round(win_rate_v, 1),
            "profitFactor": round(profit_factor_v, 2),
            "tradesCount": trades_count,
            "avgTradeReturn": round(avg_trade_return_v, 2),       # 【注意】驼峰命名，单位 %
            "maxWinningStreak": int(max_win_streak),
            "maxLosingStreak": int(max_loss_streak),
            "calmarRatio": round(calmar_ratio_v, 3),
            "warning_level": "normal"  # [Added] 正常情况标记为 normal
        }
    
    def extract_equity_curve_from_df(self, results_df: pd.DataFrame, stock_data_service=None) -> Dict:
        """
        (此函数保持不变, 作为备用)
        CHANGED: 确保数据库已初始化
        """
        if not self.init_service._initialized:
            self.init_service.ensure_initialized()
        
        initial_capital = self.init_service.backtest_engine.initial_capital
        # (我们在这里也修复一下基准，让它查询数据库)
        # 将日期统一格式化为字符串，避免 pandas.Timestamp 直接传入 SQL 参数
        date_series = pd.to_datetime(results_df['date'])
        dates = date_series.dt.strftime('%Y-%m-%d').tolist()
        start_date_str = dates[0]
        end_date_str = dates[-1]
        if stock_data_service:
            benchmark_df = stock_data_service.get_benchmark_data_from_db('000300', start_date_str, end_date_str)
        else:
            benchmark_df = pd.DataFrame()
        benchmark_curve = []

        if not benchmark_df.empty:
             try:
                strategy_dates_df = pd.DataFrame({'date': dates})
                merged_df = pd.merge(strategy_dates_df, benchmark_df, on='date', how='left')
                merged_df['close'] = merged_df['close'].ffill().bfill()
                first_valid_benchmark = merged_df['close'].dropna().iloc[0]
                if first_valid_benchmark > 0:
                    normalized_curve = (merged_df['close'] / first_valid_benchmark) * initial_capital
                    benchmark_curve = normalized_curve.fillna(initial_capital).tolist()
             except: pass # (忽略错误)
        
        if not benchmark_curve:
             benchmark_curve = np.linspace(initial_capital, initial_capital, len(results_df)).tolist() 

        return {
            "dates": dates,
            "strategyReturns": results_df['total_value'].tolist(),
            "benchmarkReturns": benchmark_curve
        }
    
    def calculate_risk_from_df(self, results_df: pd.DataFrame) -> Dict:
        if results_df is None or results_df.empty:
            return {
                "drawdowns": [],
                "volatility": [],
                "returnDistribution": [],
                "monthlyReturns": []
            }
        # 1. 规范化基础数据
        df = results_df.copy()

        # 只保留我们关心的两列
        if 'total_value' not in df.columns:
            # 兜底：如果有 equity 或类似字段，可以在这里做一层映射
            raise ValueError("results_df 缺少 total_value 列，无法计算风险指标")

        df = df[['date', 'total_value']].copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 2. 从 total_value 计算逐日回撤
        df['cummax'] = df['total_value'].cummax()
        # drawdown 是一个负数（回撤），比如 -0.15 = 回撤 15%
        df['drawdown'] = df['total_value'] / df['cummax'] - 1.0

        # 3. 最大回撤 Top 5（按回撤深度排序，取最深的前 5 个点）
        drawdown_data = []
        drawdowns = df[df['drawdown'] < 0][['date', 'drawdown']]

        if not drawdowns.empty:
            for _, row in drawdowns.sort_values('drawdown').head(5).iterrows():
                drawdown_data.append({
                    "startDate": row['date'].strftime('%Y-%m-%d'),
                    "endDate": row['date'].strftime('%Y-%m-%d'),
                    "value": round(row['drawdown'] * 100, 2)  # 转成百分比
                })

        # 4. 月度收益热力图
        heatmap_data = []
        try:
            df_equity = df[['date', 'total_value']].copy()
            df_equity = df_equity.set_index('date')
            df_equity['year'] = df_equity.index.year
            df_equity['month'] = df_equity.index.month

            # 计算每个月的收益
            monthly_returns = []
            for (year, month), group in df_equity.groupby(['year', 'month']):
                first_value = group['total_value'].iloc[0]
                last_value = group['total_value'].iloc[-1]
                if first_value <= 0:
                    continue
                monthly_return = (last_value / first_value - 1) * 100  # 直接计算为百分比
                monthly_returns.append({
                    'year': int(year),
                    'month': int(month),
                    'return': monthly_return
                })

            # 整理数据为前端需要的格式
            if monthly_returns:
                # 获取所有年份
                years = sorted(set(item['year'] for item in monthly_returns))
                
                for year in years:
                    # 创建包含12个月的列表，初始值为0.0
                    year_data = {
                        'year': int(year),
                        'months': [0.0] * 12  # 1~12月，初始值为0.0
                    }
                    
                    # 填充实际数据
                    for item in monthly_returns:
                        if item['year'] == year:
                            m = int(item['month']) - 1  # 转换为0-based索引
                            year_data['months'][m] = round(item['return'], 2)
                    
                    heatmap_data.append(year_data)

        except Exception as e:
            print(f"计算月度收益失败: {e}")

        return {
            "drawdowns": drawdown_data,
            "volatility": [],          # 你后面如果想补充波动率 / 分布可以用这两个
            "returnDistribution": [],
            "monthlyReturns": heatmap_data
        }


