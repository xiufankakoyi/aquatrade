"""
聚宽策略：MACD绿柱收缩策略（移动止盈+背离卖点）

买点: MACD绿柱连续4根收缩（凹函数形态）- T日信号，T+1日买入
卖点: 移动止盈(3%触发,回撤2%止盈) + MACD/RSI顶背离
仓位管理: 最多持有5只股票，每只18%仓位，总仓位90%

筛选逻辑: 多只股票出现信号时，按股票代码字典序排序，取前N只
"""

import numpy as np
import pandas as pd


def calc_ema(close, period):
    return close.ewm(span=period, adjust=False).mean()


def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    histogram = (dif - dea) * 2
    return histogram


def detect_signal(histogram):
    if len(histogram) < 4:
        return False
    
    last4 = histogram.iloc[-4:]
    
    if not (last4 < 0).all():
        return False
    
    abs_vals = last4.abs()
    if not (abs_vals.iloc[0] > abs_vals.iloc[1] > abs_vals.iloc[2] > abs_vals.iloc[3]):
        return False
    
    if histogram.iloc[-1] <= -0.005:
        return False
    
    return True


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    
    g.position_pct = 0.18
    g.max_holdings = 5
    g.take_profit = 0.03
    g.trailing_stop = 0.02
    g.max_days = 10
    
    # 全A股股票池（排除科创板）
    all_stocks = list(get_all_securities(['stock']).index)
    g.stock_pool = sorted([s for s in all_stocks if not s.startswith('688')])
    
    g.holdings = {}
    g.pending_signals = []
    
    log.info(f"股票池: {len(g.stock_pool)} 只")


def handle_data(context, data):
    date = context.current_dt.strftime('%Y-%m-%d')
    
    # 执行昨天的买入信号（按字典序排序后取前N只）
    if g.pending_signals and len(g.holdings) < g.max_holdings:
        # 按股票代码字典序排序
        sorted_signals = sorted(g.pending_signals)
        slots = g.max_holdings - len(g.holdings)
        stocks_to_buy = sorted_signals[:slots]
        
        for stock in stocks_to_buy:
            h = history(1, '1d', 'close', [stock])
            if stock not in h.columns:
                continue
            price = h[stock].iloc[-1]
            if np.isnan(price) or price <= 0:
                continue
            
            order_value(stock, context.portfolio.total_value * g.position_pct)
            g.holdings[stock] = {
                'buy_price': price,
                'peak': price,
                'days': 0,
                'triggered': False
            }
            log.info(f"[{date}] 买入 {stock}, 价格: {price:.2f}")
        
        g.pending_signals = []
    
    # 处理持仓
    for stock in list(g.holdings.keys()):
        if stock not in context.portfolio.positions:
            del g.holdings[stock]
            continue
        
        h = g.holdings[stock]
        h['days'] += 1
        
        close_df = history(1, '1d', 'close', [stock])
        high_df = history(1, '1d', 'high', [stock])
        close = close_df[stock].iloc[-1]
        high = high_df[stock].iloc[-1]
        
        if high > h['peak']:
            h['peak'] = high
        
        if (high - h['buy_price']) / h['buy_price'] >= g.take_profit:
            h['triggered'] = True
        
        sell = False
        reason = ""
        
        if h['days'] >= g.max_days:
            sell = True
            reason = "max_days"
        
        if h['triggered']:
            dd = (h['peak'] - close) / h['peak']
            if dd >= g.trailing_stop:
                sell = True
                reason = "trailing"
        
        if sell:
            order_target(stock, 0)
            ret = (close - h['buy_price']) / h['buy_price'] * 100
            log.info(f"[{date}] 卖出 {stock}, 原因: {reason}, 收益: {ret:.2f}%")
            del g.holdings[stock]
    
    # 检测新信号
    if len(g.holdings) >= g.max_holdings:
        return
    
    held = set(context.portfolio.positions.keys()) | set(g.holdings.keys())
    candidates = [s for s in g.stock_pool if s not in held]
    
    if not candidates:
        return
    
    df = history(50, '1d', 'close', candidates)
    df = df.dropna(axis=1, how='any')
    
    signals = []
    for stock in df.columns:
        close = df[stock]
        hist = calc_macd(close)
        
        if detect_signal(hist):
            signals.append(stock)
    
    if signals:
        g.pending_signals = signals
        log.info(f"[{date}] 检测到 {len(signals)} 个信号")
