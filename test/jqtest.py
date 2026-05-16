# 导入函数库
import talib
import numpy as np
import pandas as pd
from datetime import datetime
from jqdata import *  # 聚宽数据源

def initialize(context):
    # 开启避免未来数据模式
    set_option("avoid_future_data", True)
    
    # 全市场股票（转为列表）
    g.stock_pool = get_all_securities(['stock']).index.tolist()
    log.info("全市场股票数量: %d" % len(g.stock_pool))
    
    # 缓存上市日期（静态数据）
    g.listing_date = {}
    for stock in g.stock_pool:
        try:
            listing_date = get_security_info(stock).start_date
            if isinstance(listing_date, str):
                listing_date = datetime.strptime(listing_date, '%Y-%m-%d').date()
            elif hasattr(listing_date, 'date'):
                listing_date = listing_date.date()
            g.listing_date[stock] = listing_date
        except:
            g.listing_date[stock] = None
    
    # ---------- 缓存所有交易日 ----------
    try:
        g.all_trade_days = list(get_all_trade_days())
        log.info("使用 get_all_trade_days 获取交易日，数量: %d" % len(g.all_trade_days))
    except NameError:
        import datetime
        start = datetime.date(1990, 1, 1)
        end = datetime.date(2050, 12, 31)
        g.all_trade_days = get_trade_days(start, end)
        log.info("使用 get_trade_days 获取交易日，数量: %d" % len(g.all_trade_days))
    
    # ---------- 策略参数 ----------
    # 均线周期
    g.ma_short = 5
    g.ma_mid = 10
    g.ma_long = 20
    
    # 主升浪识别参数
    g.lookback_days = 20
    g.breakout_days = 5
    g.touch_range = 0.03
    
    # 成交量参数
    g.volume_ratio_min = 1.5
    g.volume_ma_days = 20
    
    # 乖离限制（买入）
    g.buy_deviation_max = 0.05
    
    # 市值范围（单位：亿元）
    g.market_cap_min = 30
    g.market_cap_max = 2000
    
    # 仓位控制
    g.max_hold = 5
    g.position_ratio = 0.2
    
    # 卖出参数
    g.sell_deviation = 0.15
    
    # 运行每日函数
    run_daily(main, time='every_bar')

def main(context):
    # 一次性获取实时数据
    current_data = get_current_data()
    
    # 基础筛选：ST、停牌、上市不足60天
    stock_list_tmp = get_valid_stocks_basic(context, current_data)
    if not stock_list_tmp:
        log.warn("没有有效股票，跳过今日交易")
        return
    
    # ---------- 稳健获取市值数据（不使用 get_previous_trading_date） ----------
    target_date = context.current_dt.date()
    all_days = g.all_trade_days
    
    if target_date in all_days:
        idx = all_days.index(target_date)
        # 取当天之前的交易日（不包含当天）
        candidate_dates = all_days[:idx]  # 从早到晚
        # 反转，从最近到最远
        candidate_dates = candidate_dates[::-1]
    else:
        # target_date 不是交易日，取所有小于它的交易日
        candidate_dates = [d for d in all_days if d < target_date]
        # 从最近到最远
        candidate_dates = candidate_dates[::-1]
    
    if not candidate_dates:
        log.warn("无法找到 target_date 之前的交易日，跳过今日交易")
        return
    
    # 尝试最多 30 个交易日
    df = None
    used_date = None
    for check_date in candidate_dates[:30]:
        q = query(valuation.code, valuation.capitalization).filter(valuation.code.in_(stock_list_tmp))
        df = get_fundamentals(q, date=check_date)
        if not df.empty:
            used_date = check_date
            break
    else:
        log.warn("无法获取任何近期的财务数据，跳过今日交易")
        return
    
    log.info("使用 %s 的财务数据（从 %s 向前追溯）" % (used_date, target_date))
    
    # 市值筛选
    df['cap_billion'] = df['capitalization'] / 1000.0
    mask = (df['cap_billion'] >= g.market_cap_min) & (df['cap_billion'] <= g.market_cap_max)
    stock_list = df[mask]['code'].tolist()
    
    # 调试输出市值分布
    log.info("原始财务数据行数: %d" % len(df))
    log.info("市值分布: 小于30亿: %d, 30亿-2000亿: %d, 大于2000亿: %d" % (
        len(df[df['cap_billion'] < 30]),
        len(df[(df['cap_billion'] >= 30) & (df['cap_billion'] <= 2000)]),
        len(df[df['cap_billion'] > 2000])
    ))
    log.info("市值缺失或为0的数量: %d" % len(df[df['cap_billion'].isnull() | (df['cap_billion'] == 0)]))
    log.info("市值筛选后股票数量: %d" % len(stock_list))
    
    if not stock_list:
        return
    
    # ---------- 获取历史数据 ----------
    price_volume_data = get_price(stock_list, count=max(g.volume_ma_days, g.lookback_days, 60)+1,
                                  frequency='daily', fields=['close', 'volume'], skip_paused=True, panel=False)
    price_wide = price_volume_data.pivot(index='time', columns='code', values='close').sort_index()
    volume_wide = price_volume_data.pivot(index='time', columns='code', values='volume').sort_index()
    
    g.hist_close = {}
    g.hist_volume = {}
    for stock in stock_list:
        if stock not in price_wide.columns or stock not in volume_wide.columns:
            continue
        close_series = price_wide[stock].dropna()
        vol_series = volume_wide[stock].dropna()
        if len(close_series) >= max(g.ma_long, g.volume_ma_days) + 1 and len(vol_series) >= g.volume_ma_days + 1:
            g.hist_close[stock] = close_series.values
            g.hist_volume[stock] = vol_series.values
    
    # 持仓处理
    hold_list = list(context.portfolio.positions.keys())
    for stock in hold_list:
        if stock not in stock_list:
            continue
        sell_flag, reason = check_sell_signal(stock, current_data)
        if sell_flag:
            order_target_value(stock, 0)
            log.info("卖出 %s，原因：%s" % (stock, reason))
    
    hold_list = list(context.portfolio.positions.keys())
    if len(hold_list) >= g.max_hold:
        return
    
    # 买入预筛选（快速过滤）
    valid_stocks = [s for s in stock_list if s in current_data]
    cur_prices = [current_data[s].last_price for s in valid_stocks]
    cur_price_series = pd.Series(cur_prices, index=valid_stocks)
    
    if price_wide.shape[0] >= g.ma_long:
        simple_ma20 = price_wide[valid_stocks].iloc[-g.ma_long:, :].mean(axis=0)
        mask = cur_price_series > simple_ma20
        pre_candidates = cur_price_series[mask].index.tolist()
        reject_stats = {"价格低于简单20日线": len(valid_stocks) - len(pre_candidates)}
    else:
        pre_candidates = valid_stocks
        reject_stats = {}
    
    # 精确买入判断
    buy_candidates = []
    for stock in pre_candidates:
        if stock in hold_list:
            continue
        close_arr = g.hist_close.get(stock)
        vol_arr = g.hist_volume.get(stock)
        if close_arr is None or vol_arr is None:
            reject_stats["无历史数据"] = reject_stats.get("无历史数据", 0) + 1
            continue
        ok, reason = check_buy_signal(stock, cur_price_series[stock], close_arr, vol_arr)
        if ok:
            buy_candidates.append(stock)
        else:
            reject_stats[reason] = reject_stats.get(reason, 0) + 1
    
    log.info("今日符合买入条件的股票数量：%d" % len(buy_candidates))
    log.info("拒绝原因统计：%s" % str(reject_stats))
    
    if buy_candidates:
        cash = context.portfolio.available_cash
        num_to_buy = min(len(buy_candidates), g.max_hold - len(hold_list))
        if num_to_buy > 0:
            value_per_stock = cash / num_to_buy
            for stock in buy_candidates[:num_to_buy]:
                order_target_value(stock, value_per_stock)
                log.info("买入 %s，仓位 %.2f" % (stock, value_per_stock))

def get_valid_stocks_basic(context, current_data):
    stock_list = []
    total = len(g.stock_pool)
    st_count = 0
    paused_count = 0
    listed_count = 0
    error_count = 0
    today = context.current_dt.date() if hasattr(context.current_dt, 'date') else context.current_dt
    
    for stock in g.stock_pool:
        try:
            if current_data[stock].is_st:
                st_count += 1
                continue
            if current_data[stock].paused:
                paused_count += 1
                continue
            listing_date = g.listing_date.get(stock)
            if listing_date is None:
                listed_count += 1
                continue
            delta = today - listing_date
            if delta.days < 60:
                listed_count += 1
                continue
            stock_list.append(stock)
        except Exception:
            error_count += 1
            continue
    
    log.info("基础筛选: 总数=%d, ST剔除=%d, 停牌剔除=%d, 上市不足60天剔除=%d, 异常=%d, 剩余=%d" %
             (total, st_count, paused_count, listed_count, error_count, len(stock_list)))
    return stock_list

def check_sell_signal(stock, current_data):
    if stock not in g.hist_close:
        return False, "无历史数据"
    close = g.hist_close[stock]
    if len(close) < g.ma_long + 1:
        return False, "数据不足"
    
    ma5 = talib.MA(close, timeperiod=g.ma_short)[-1]
    ma10 = talib.MA(close, timeperiod=g.ma_mid)[-1]
    ma20 = talib.MA(close, timeperiod=g.ma_long)[-1]
    
    if stock not in current_data:
        return False, "无实时数据"
    current_price = current_data[stock].last_price
    
    if current_price > ma5 * (1 + g.sell_deviation):
        return True, "向上乖离过大"
    if current_price < ma10 or current_price < ma20:
        return True, "跌破均线"
    return False, ""

def check_buy_signal(stock, current_price, close_arr, vol_arr):
    ma5 = talib.MA(close_arr, timeperiod=g.ma_short)
    ma10 = talib.MA(close_arr, timeperiod=g.ma_mid)
    ma20 = talib.MA(close_arr, timeperiod=g.ma_long)
    
    if not (ma5[-1] > ma10[-1] > ma20[-1]):
        return False, "均线未多头排列"
    
    deviation = (current_price - ma5[-1]) / ma5[-1]
    if deviation > g.buy_deviation_max:
        return False, "向上乖离过大"
    if deviation < -g.buy_deviation_max:
        return False, "向下乖离过大"
    
    if len(vol_arr) < g.volume_ma_days + 1:
        return False, "成交量数据不足"
    current_vol = vol_arr[-1]
    avg_vol = np.mean(vol_arr[-g.volume_ma_days-1:-1])
    if avg_vol == 0:
        return False, "成交量均值为0"
    if current_vol / avg_vol < g.volume_ratio_min:
        return False, "成交量不足"
    
    lookback = g.lookback_days
    if len(close_arr) < lookback + 1:
        return False, "历史数据不足"
    
    high_n = np.max(close_arr[-lookback-1:-1])
    breakthrough = (current_price > high_n)
    
    yesterday_close = close_arr[-2] if len(close_arr) >= 2 else None
    ma20_yesterday = ma20[-2] if len(ma20) >= 2 else None
    if yesterday_close is not None and ma20_yesterday is not None:
        cross_ma20 = (current_price > ma20[-1]) and (yesterday_close <= ma20_yesterday)
    else:
        cross_ma20 = False
    
    touch_ma5 = abs(current_price - ma5[-1]) / ma5[-1] <= g.touch_range
    touch_ma10 = abs(current_price - ma10[-1]) / ma10[-1] <= g.touch_range
    pullback = touch_ma5 or touch_ma10
    
    if not (breakthrough or cross_ma20 or pullback):
        return False, "无主升浪信号"
    
    return True, "满足条件"