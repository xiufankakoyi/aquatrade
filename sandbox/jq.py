# 策略名称：MACD绿柱收缩 + 波动率强度（聚宽版）
# 策略逻辑：见下方注释

import numpy as np
import pandas as pd
from jqlib.technical_analysis import *

pd.set_option('mode.chained_assignment', None)

def initialize(context):
    # ========== 策略参数 ==========
    g.vs_threshold = 0.5
    g.rsi_max = 50
    g.take_profit_trigger = 0.03
    g.trailing_stop = 0.02
    g.max_hold_days = 10
    g.max_holdings = 5
    g.position_pct = 0.18

    # ========== 股票池静态过滤（仅剔除上市不满60天） ==========
    all_stocks = get_all_securities(['stock']).index.tolist()
    g.stock_pool = []
    for stock in all_stocks:
        start_date = get_security_info(stock).start_date
        # 统一转换为date再相减
        days_on_market = (context.current_dt.date() - start_date).days
        if days_on_market >= 60:
            g.stock_pool.append(stock)
    log.info('初始股票池数量（上市≥60天）：' + str(len(g.stock_pool)))

    # ========== 全局变量 ==========
    g.holdings = {}
    g.pending_signals = []
    g.last_date = None

    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.set_level('order', 'error')

def handle_data(context, data):
    current_date = context.current_dt.date()
    if g.last_date is None:
        g.last_date = current_date
        return

    # 获取当前数据（用于ST、停牌等状态）
    current_data = get_current_data()

    # ---------- 1. 处理持仓卖出 ----------
    for stock in list(g.holdings.keys()):
        if stock not in context.portfolio.positions:
            del g.holdings[stock]
            continue

        pos = g.holdings[stock]
        # 从 data 获取价格
        try:
            current_price = data[stock].close
            high = data[stock].high
        except:
            continue
        if np.isnan(current_price) or current_price <= 0 or np.isnan(high):
            continue

        # 更新峰值
        if high > pos['peak']:
            pos['peak'] = high

        pos['days'] += 1

        # 检查是否触发止盈条件
        if not pos['triggered']:
            if (high - pos['buy_price']) / pos['buy_price'] >= g.take_profit_trigger:
                pos['triggered'] = True

        # 检查卖出条件
        sell = False
        reason = ''
        if pos['days'] >= g.max_hold_days:
            sell = True
            reason = 'max_days'
        elif pos['triggered']:
            dd = (pos['peak'] - current_price) / pos['peak']
            if dd >= g.trailing_stop:
                sell = True
                reason = 'trailing_stop'

        if sell:
            order_target_value(stock, 0)
            ret = (current_price - pos['buy_price']) / pos['buy_price'] * 100
            log.info('[%s] 卖出 %s，原因：%s，持有天数：%d，收益：%.2f%%' %
                     (current_date, stock, reason, pos['days'], ret))
            del g.holdings[stock]

    # ---------- 2. 处理买入（执行T-1日的信号） ----------
    if len(g.holdings) < g.max_holdings and g.pending_signals:
        slots = g.max_holdings - len(g.holdings)
        to_buy = []
        for stock in g.pending_signals:
            if stock in g.holdings or stock in context.portfolio.positions:
                continue
            # 检查股票状态（ST、停牌）
            cd = current_data[stock]
            if cd.is_st or cd.paused:
                continue
            # 检查开盘价有效性
            try:
                open_price = data[stock].open
                if np.isnan(open_price) or open_price <= 0:
                    continue
            except:
                continue
            to_buy.append(stock)
            if len(to_buy) >= slots:
                break

        for stock in to_buy:
            price = data[stock].open
            value = context.portfolio.total_value * g.position_pct
            order_target_value(stock, value)
            g.holdings[stock] = {
                'buy_price': price,
                'peak': price,
                'triggered': False,
                'days': 0
            }
            log.info('[%s] 买入 %s，价格：%.2f' % (current_date, stock, price))
        g.pending_signals = []

    # ---------- 3. 检测新信号（T日）- 优化版 ----------
    # 生成候选股票：从静态池中剔除已持仓、ST、停牌、价格无效的
    candidates = []
    for stock in g.stock_pool:
        if stock in g.holdings or stock in context.portfolio.positions:
            continue
        cd = current_data[stock]
        if cd.is_st or cd.paused:
            continue
        try:
            if np.isnan(data[stock].open) or data[stock].open <= 0:
                continue
        except:
            continue
        candidates.append(stock)

    if not candidates:
        return

    # 批量获取历史数据（200天足够MACD计算准确）
    # 使用 history() 比 get_price() 快
    try:
        close_df = history(200, '1d', 'close', candidates)
        high_df = history(200, '1d', 'high', candidates)
        low_df = history(200, '1d', 'low', candidates)
    except Exception as e:
        return

    if close_df is None or high_df is None or low_df is None:
        return

    # 取三个DataFrame中都存在的股票
    available_stocks = set(close_df.columns) & set(high_df.columns) & set(low_df.columns)

    signals = []  # 存储 (vs, stock)
    
    for stock in candidates:
        if stock not in available_stocks:
            continue
        
        try:
            close = close_df[stock].values
            high = high_df[stock].values
            low = low_df[stock].values
            
            if len(close) < 50 or np.any(np.isnan(close[-30:])):
                continue
            
            # 计算 MACD（使用 numba 加速版本，与聚宽 MACD API 一致）
            macd_hist = calc_macd_fast(close)
            
            # 检测绿柱收缩
            if not detect_contraction(macd_hist):
                continue

            # 计算RSI（最后一天）
            rsi_last = calc_rsi_last(close, period=14)
            if rsi_last >= g.rsi_max:
                continue

            # 计算波动率强度VS（最后一天）
            vs = calc_vs(close, high, low)
            if vs < g.vs_threshold:
                continue

            signals.append((vs, stock))
        except:
            continue

    if signals:
        # 按VS降序排序，优先买入强度高的
        signals.sort(key=lambda x: x[0], reverse=True)
        g.pending_signals = [s[1] for s in signals]
        log.info('[%s] 检测到 %d 个信号，前5只：%s' %
                 (current_date, len(signals), str(g.pending_signals[:5])))


# ---------- 技术指标计算函数 ----------

from numba import njit

@njit
def calc_ema_fast(arr, period):
    """EMA 计算（与通达信/聚宽一致）"""
    ema = np.zeros(len(arr))
    ema[0] = arr[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * mult + ema[i-1]
    return ema

@njit
def calc_macd_fast(close, fast=12, slow=26, signal=9):
    """MACD 计算（与通达信/聚宽一致）"""
    ema_fast = calc_ema_fast(close, fast)
    ema_slow = calc_ema_fast(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema_fast(dif, signal)
    histogram = (dif - dea) * 2
    return histogram

def detect_contraction(hist):
    """检测最后4根MACD绿柱是否连续收缩（凹函数形态）"""
    if len(hist) < 4:
        return False
    last4 = hist[-4:]
    # 检查是否有NaN或无效值
    if np.any(np.isnan(last4)):
        return False
    # 全部为负
    if np.any(last4 >= 0):
        return False
    abs_vals = np.abs(last4)
    # 连续递减
    if not (abs_vals[0] > abs_vals[1] > abs_vals[2] > abs_vals[3]):
        return False
    # 最后一根大于 -0.005（即绿柱很短）
    if last4[-1] <= -0.005:
        return False
    return True

def calc_rsi_last(close, period=14):
    """仅计算最后一天的RSI值（加速计算）"""
    if len(close) < period + 1:
        return 50.0
    # 计算涨跌幅
    deltas = np.diff(close[-period-1:])
    gains = deltas[deltas > 0].sum()
    losses = -deltas[deltas < 0].sum()
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)
    return rsi

def calc_vs(close, high, low):
    """
    计算最后一天的波动率强度（VS）
    公式：VS = 0.35*(ATR%-3)/1.5 + 0.30*(振幅%-2.5)/1.5 
                + 0.20*(20日波动率%-3.5)/1.5 + 0.15*(下影线%-1.5)/1.5
    """
    n = len(close)
    if n < 20:
        return -999.0  # 数据不足返回极小值

    # 计算ATR(14)
    atr = np.zeros(n)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    atr[0] = tr[0]
    for i in range(1, n):
        atr[i] = (atr[i-1] * 13 + tr[i]) / 14
    atr_pct = atr[-1] / close[-1] * 100 if close[-1] > 0 else 0

    # 当日振幅（相对于前一日收盘）
    high_low_range = (high[-1] - low[-1]) / close[-2] * 100 if n >= 2 and close[-2] > 0 else 0

    # 20日波动率（标准差）
    std20 = np.std(close[-20:])
    std20_pct = std20 / close[-1] * 100 if close[-1] > 0 else 0

    # 下影线（相对于前一日收盘）
    lower_shadow = (close[-1] - low[-1]) / close[-2] * 100 if n >= 2 and close[-2] > 0 else 0

    # 标准化并加权求和
    vs = (0.35 * (atr_pct - 3.0) / 1.5 +
          0.30 * (high_low_range - 2.5) / 1.5 +
          0.20 * (std20_pct - 3.5) / 1.5 +
          0.15 * (lower_shadow - 1.5) / 1.5)
    return vs