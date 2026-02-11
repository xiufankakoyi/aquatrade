
import sys
import os
import time
import datetime
import pandas as pd
import polars as pl
import tushare as ts
from collections import deque

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import Config
from data_svc.database.questdb_manager import QuestDBManager

# ==================== Rate Limiter ====================
RATE_LIMIT_PER_MINUTE = 200
_WINDOW_SECONDS = 60
_request_records = deque()

def call_with_rate_limit(api_callable, *args, **kwargs):
    while True:
        now = time.time()
        while _request_records and now - _request_records[0] >= _WINDOW_SECONDS:
            _request_records.popleft()
        if len(_request_records) < RATE_LIMIT_PER_MINUTE:
            break
        sleep_seconds = _WINDOW_SECONDS - (now - _request_records[0]) + 0.01
        time.sleep(max(sleep_seconds, 0.05))
    
    result = api_callable(*args, **kwargs)
    _request_records.append(time.time())
    return result

# ==================== Indicator Calculation (Polars) ====================
def compute_indicators(df: pl.DataFrame) -> pl.DataFrame:
    """Compute all momentum indicators required by factors_momentum table"""
    # Sort by code and date
    df = df.sort(["code", "ts"])
    
    # === 1. RSI (14) ===
    # Using simplistic calculation for batch
    # Polars expression for RSI
    period = 14
    rsi_expr = (
        pl.col("close").diff().alias("diff")
    ).map_batches(lambda s: s) # Placeholder, actual logic below
    
    # We define reusable expressions
    # ...Actually, pasting logic from compute_indicators.py is better
    
    # Define Expressions
    # RSI
    def rsi(p):
        diff = pl.col("close").diff()
        gain = pl.when(diff > 0).then(diff).otherwise(0)
        loss = pl.when(diff < 0).then(-diff).otherwise(0)
        avg_gain = gain.ewm_mean(span=p, min_periods=p)
        avg_loss = loss.ewm_mean(span=p, min_periods=p)
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - 100 / (1 + rs)
    
    # KDJ
    def kdj(n=9, m1=3, m2=3):
        # Rolling min/max
        low_n = pl.col("low").rolling_min(n)
        high_n = pl.col("high").rolling_max(n)
        rsv = (pl.col("close") - low_n) / (high_n - low_n + 1e-10) * 100
        # EWM for K, D
        k = rsv.ewm_mean(span=m1, min_periods=m1) # simplified
        # Actually standard KDJ uses SMA for K from RSV? No, usually EMA or SMA.
        # compute_indicators.py used ewm_mean.
        return rsv, k 
        
    q = df.lazy()
    
    # --- Basic Indicators ---
    q = q.with_columns([
        rsi(14).over("code").alias("rsi_14"),
        
        # ATR
        pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("prev_close").shift(1)).abs(), # pre_close is better but we might have gaps. base_daily has prev_close?
            (pl.col("low") - pl.col("prev_close").shift(1)).abs()
        ).rolling_mean(14).over("code").alias("atr_14"),
        
        # MA
        pl.col("close").rolling_mean(5).over("code").alias("ma5"),
        pl.col("close").rolling_mean(10).over("code").alias("ma10"),
        pl.col("close").rolling_mean(20).over("code").alias("ma20"),
        pl.col("close").rolling_mean(60).over("code").alias("ma60"),
        pl.col("close").rolling_mean(120).over("code").alias("ma120"),
        pl.col("close").rolling_mean(250).over("code").alias("ma250"),
        
        # MACD
        (pl.col("close").ewm_mean(span=12) - pl.col("close").ewm_mean(span=26)).over("code").alias("macd_dif"),
    ])
    
    q = q.with_columns([
        pl.col("macd_dif").ewm_mean(span=9).over("code").alias("macd_dea"),
        
        # KDJ parts
        ((pl.col("close") - pl.col("low").rolling_min(9).over("code")) / 
         (pl.col("high").rolling_max(9).over("code") - pl.col("low").rolling_min(9).over("code") + 1e-10) * 100).alias("rsv"),
         
        # Bollinger
        pl.col("close").rolling_mean(20).over("code").alias("boll_mid"),
        pl.col("close").rolling_std(20).over("code").alias("boll_std"),
        
        # BIAS
        ((pl.col("close") - pl.col("ma5"))/pl.col("ma5")*100).alias("bias_5"),
        ((pl.col("close") - pl.col("ma10"))/pl.col("ma10")*100).alias("bias_10"),
        ((pl.col("close") - pl.col("ma20"))/pl.col("ma20")*100).alias("bias_20"),
    ])
    
    q = q.with_columns([
        (pl.col("macd_dif") - pl.col("macd_dea") * 2).alias("macd_histogram"),
        # KDJ - K
        pl.col("rsv").ewm_mean(span=3).over("code").alias("kdj_k"),
        # BOLL
        (pl.col("boll_mid") + 2*pl.col("boll_std")).alias("boll_upper"),
        (pl.col("boll_mid") - 2*pl.col("boll_std")).alias("boll_lower"),
    ])
    
    q = q.with_columns([
        # KDJ - D
        pl.col("kdj_k").ewm_mean(span=3).over("code").alias("kdj_d")
    ])
    
    q = q.with_columns([
        # KDJ - J
        (3*pl.col("kdj_k") - 2*pl.col("kdj_d")).alias("kdj_j")
    ])
    
    return q.collect()


def main():
    print("="*60)
    print("🚀 QuestDB 每日增量更新脚本")
    print("="*60)
    
    # 1. Initialize
    qm = QuestDBManager()
    if not qm.health_check():
        print("❌ QuestDB 连接失败")
        return
        
    ts_token = Config.TUSHARE_TOKEN
    if not ts_token:
        print("⚠️ Config.TUSHARE_TOKEN works bad, trying fallback...")
        ts_token = 'c32d8386d48a5c9e453add46d222912cdf866b3026950cba05c8b90b'
        
    ts.set_token(ts_token)
    pro = ts.pro_api()
    
    # 2. Get Last Date
    print("🔍 检查最新数据日期...")
    try:
        # QuestDB uses 'timestamp' as designated timestamp column
        df_last = qm.query("SELECT max(timestamp) FROM base_daily")
        if df_last.is_empty() or df_last.item(0,0) is None:
            last_date_str = "2020-01-01"
            print("   ⚠️  数据库为空，默认从 2020-01-01 开始")
        else:
            # QuestDB returns timestamp string usually "2024-01-01T00:00:00.000000Z"
            last_ts = df_last.item(0,0)
            if isinstance(last_ts, str):
                last_date_str = last_ts[:10]
            else:
                last_date_str = last_ts.strftime("%Y-%m-%d")
            print(f"   📅 数据库最新日期: {last_date_str}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return

    # 3. Determine Range
    start_dt = datetime.datetime.strptime(last_date_str, "%Y-%m-%d") + datetime.timedelta(days=1)
    start_str = start_dt.strftime("%Y%m%d")
    end_dt = datetime.datetime.now()
    if end_dt.hour < 16: # Before 4PM, maybe today's data is not ready
        end_dt = end_dt - datetime.timedelta(days=0) # fetch anyway? 
        # Tushare usually updates around 15:30-16:00.
        pass
    end_str = end_dt.strftime("%Y%m%d")
    
    if start_str > end_str:
        print("✅ 数据已是最新，无需更新。")
        qm.close()
        return
        
    print(f"📥 准备获取数据: {start_str} -> {end_str}")
    
    # 4. Fetch Calendar
    cal = call_with_rate_limit(pro.trade_cal, start_date=start_str, end_date=end_str, is_open='1')
    if cal is None:
        print("❌ Tushare returned None for trade_cal.")
        return
        
    print(f"DEBUG: cal shape={cal.shape}, columns={cal.columns}")
    if cal.empty:
        print("DEBUG: cal is empty")
        
    trade_dates = cal['cal_date'].tolist()
    
    if not trade_dates:
        print("✅ 期间无交易日。")
        qm.close()
        return
    
    # 5. Loop Days
    for date_str in trade_dates:
        print(f"🔄 处理 {date_str} ...")
        
        # Fetch Data
        try:
            # Daily
            df_daily = call_with_rate_limit(pro.daily, trade_date=date_str)
            if df_daily.empty: continue
            
            # Adj Factor
            df_adj = call_with_rate_limit(pro.adj_factor, trade_date=date_str)
            
            # Daily Basic
            df_basic = call_with_rate_limit(pro.daily_basic, trade_date=date_str)
            
        except Exception as e:
            print(f"   ❌ Tushare 请求失败: {e}")
            continue
            
        # Merge
        # daily + adj
        df_merge = pd.merge(df_daily, df_adj[['ts_code', 'adj_factor']], on='ts_code', how='left')
        df_merge['adj_factor'] = df_merge['adj_factor'].fillna(1.0)
        
        # + basic
        if not df_basic.empty:
            df_merge = pd.merge(df_merge, df_basic, on=['ts_code', 'trade_date'], how='left')
            
        # Transform for QuestDB
        # 1. base_daily
        # Schema: ts, code, open, high, low, close, volume, amount, adj_factor, prev_close
        # Tushare: trade_date (YYYYMMDD), ts_code (000001.SZ), open, high, low, close, vol, amount, pre_close
        
        # Prepare TS and Code
        df_merge['ts'] = pd.to_datetime(df_merge['trade_date']) # datetime64[ns]
        df_merge['code'] = df_merge['ts_code'].str.split('.').str[0] # 000001
        
        # Extract base_daily
        df_base = df_merge[['ts', 'code', 'open', 'high', 'low', 'close', 'vol', 'amount', 'adj_factor', 'pre_close']].copy()
        df_base.columns = ['ts', 'code', 'open', 'high', 'low', 'close', 'volume', 'amount', 'adj_factor', 'prev_close']
        
        # Insert base_daily
        try:
            qm.insert_base_daily(pl.from_pandas(df_base))
            print(f"   Running insert base_daily: {len(df_base)} rows")
        except Exception as e:
            print(f"   ❌ 插入 base_daily 失败: {e}")
            
        # 2. factors_valuation
        # Schema: ts, code, pe, pe_ttm, pb, ps, ps_ttm, total_mv, float_mv, turnover_rate, turnover_free, volume_ratio, dividend_yield
        # Tushare: pe, pe_ttm, pb, ps, ps_ttm, total_mv, circ_mv, turnover_rate, turnover_rate_f, volume_ratio, dv_ratio
        
        val_map = {
            'pe': 'pe', 'pe_ttm': 'pe_ttm', 'pb': 'pb', 'ps': 'ps', 'ps_ttm': 'ps_ttm',
            'total_mv': 'total_mv', 'circ_mv': 'float_mv', 'turnover_rate': 'turnover_rate',
            'turnover_rate_f': 'turnover_free', 'volume_ratio': 'volume_ratio', 'dv_ratio': 'dividend_yield'
        }
        
        df_val = df_merge[['ts', 'code'] + [k for k in val_map.keys() if k in df_merge.columns]].copy()
        df_val = df_val.rename(columns=val_map)
        
        try:
            qm.insert_factors_valuation(pl.from_pandas(df_val))
            print(f"   Running insert factors_valuation: {len(df_val)} rows")
        except Exception as e:
            print(f"   ❌ 插入 factors_valuation 失败: {e}")
            
        # 3. factors_momentum
        # This requires rolling history. 
        # Tushare daily only gives today's data.
        # We need to fetch previous N days data from QuestDB to compute rolling indicators for today.
        # N ~ 250 (for ma250)
        
        print("   ⏳ 计算动量因子 (需回溯历史)...")
        # Reuse logic? We need to query QuestDB for history.
        past_days = 300
        lookback_start = (df_base['ts'].iloc[0] - datetime.timedelta(days=past_days)).strftime("%Y-%m-%d")
        
        # Load history from QuestDB base_daily
        # Schema: ts, code, close, high, low, prev_close
        # Just need cols for indicators
        try:
            q_hist = f"""
            SELECT timestamp as ts, code, close, high, low, prev_close 
            FROM base_daily 
            WHERE timestamp >= '{lookback_start}'
            """
            hist_pl = qm.query(q_hist)
            
            # Convert current day df_base to Polars and stack
            current_pl = pl.from_pandas(df_base[['ts', 'code', 'close', 'high', 'low', 'prev_close']])
            
            # Combine
            if not hist_pl.is_empty():
                # Ensure schema match
                 combined_pl = pl.concat([hist_pl, current_pl], how='vertical')
                 combined_pl = combined_pl.unique(subset=['ts', 'code'], keep='last') # Dedup if any
            else:
                 combined_pl = current_pl
            
            # Compute
            indicators_pl = compute_indicators(combined_pl)
            
            # Filter only today's data
            target_ts = df_base['ts'].iloc[0] # Timestamp
            # Polars filter: ts is datetime? or string?
            # QuestDB returns datetime64[ns] usually in Polars via Arrow
            # Tushare df_base['ts'] is datetime64[ns]
            
            # Debug types if needed
            # print(f"DEBUG types: hist_ts={hist_pl['ts'].dtype}, curr_ts={current_pl['ts'].dtype}")
            
            today_factors = indicators_pl.filter(pl.col('ts') == target_ts)
            
            if not today_factors.is_empty():
                # qm.insert_factors_momentum expects Polars DataFrame
                # Convert back to Pandas to filter cols? No, Polars is fine.
                # But we did today_pd logic. Let's stick to it but convert back.
                
                # Filter columns (using Polars directly is better but let's minimize change)
                # ... reusing previous logic which made final_mom (pandas)
                
                qm.insert_factors_momentum(pl.from_pandas(final_mom))
                print(f"   Running insert factors_momentum: {len(final_mom)} rows")
            else:
                print("   ⚠️  无法计算今日因子 (可能数据不足)")

        except Exception as e:
            print(f"   ❌ 因子计算/插入失败: {e}")
            import traceback
            traceback.print_exc()

    qm.close()
    print("✨ 所有任务完成")

if __name__ == "__main__":
    main()
