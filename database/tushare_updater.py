import datetime
import os
import sqlite3
import sys
import time
from collections import deque

import pandas as pd
import tushare as ts

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from utils.config import Config

# ====== 常量配置 ======
ROLLING_MAX_WINDOW = 20  # 计算技术指标所需的最大窗口

# ===== Tushare 频控配置 =====
RATE_LIMIT_PER_MINUTE = 500  # 每分钟最多请求次数
_WINDOW_SECONDS = 60
_request_records = deque()


def call_with_rate_limit(api_callable, *args, **kwargs):
    """确保 API 调用遵循每分钟最多 500 次的限制。"""
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


# ===== 辅助函数 =====
def infer_board_flags(stock_meta: pd.DataFrame) -> pd.DataFrame:
    """补全 is_st/is_kc/is_cy 等标记，缺失时根据代码推断。"""
    stock_meta = stock_meta.copy()
    for col in ("is_st", "is_kc", "is_cy"):
        if col not in stock_meta.columns:
            stock_meta[col] = 0

    stock_meta["is_st"] = stock_meta["is_st"].fillna(0)

    def _is_kc(code: str) -> int:
        return 1 if isinstance(code, str) and code.startswith(("688", "689")) else 0

    def _is_cy(code: str) -> int:
        return 1 if isinstance(code, str) and code.startswith(("300", "301")) else 0

    stock_meta["is_kc"] = stock_meta["is_kc"].fillna(stock_meta["stock_code"].map(_is_kc))
    stock_meta["is_cy"] = stock_meta["is_cy"].fillna(stock_meta["stock_code"].map(_is_cy))
    return stock_meta[["stock_code", "is_st", "is_kc", "is_cy"]]


def fetch_stock_flags(conn: sqlite3.Connection) -> pd.DataFrame:
    """读取 stock_info 中的标记并做兜底推断。"""
    try:
        meta = pd.read_sql("SELECT stock_code, is_st, is_kc, is_cy FROM stock_info", conn)
    except Exception:
        meta = pd.DataFrame(columns=["stock_code", "is_st", "is_kc", "is_cy"])
    if meta.empty:
        return pd.DataFrame(columns=["stock_code", "is_st", "is_kc", "is_cy"])
    return infer_board_flags(meta)


def compute_limit_prices(df: pd.DataFrame, stock_flags: pd.DataFrame) -> pd.Series:
    """根据不同板块/标记推断涨跌停价格。"""
    df = df.merge(stock_flags, on="stock_code", how="left")
    df[["is_st", "is_kc", "is_cy"]] = df[["is_st", "is_kc", "is_cy"]].fillna(0)
    prev_close = df["prev_close"].fillna(df["close"])

    ratios = pd.Series(0.1, index=df.index)
    ratios = ratios.where(df["is_st"] != 1, 0.05)
    ratios = ratios.where(~((df["is_kc"] == 1) | (df["is_cy"] == 1)), 0.2)

    limit_up = (prev_close * (1 + ratios)).round(2)
    limit_down = (prev_close * (1 - ratios)).round(2)

    return limit_up, limit_down


def compute_rolling_indicators(conn: sqlite3.Connection, df_new: pd.DataFrame) -> pd.DataFrame:
    """结合历史数据，计算 ma/avg_price/volume 指标。支持 GPU 加速。"""
    if df_new.empty:
        return df_new

    # 尝试使用 GPU 加速
    try:
        from utils.gpu_acceleration import is_gpu_enabled, calculate_ma_indicators_gpu
        use_gpu = is_gpu_enabled()
    except ImportError:
        use_gpu = False

    df_new = df_new.copy()
    df_new["trade_date_dt"] = pd.to_datetime(df_new["trade_date"])
    min_new_date = df_new["trade_date_dt"].min()
    history_start = (min_new_date - datetime.timedelta(days=ROLLING_MAX_WINDOW * 2)).strftime("%Y-%m-%d")

    # 只取需要的列以降低 IO
    history = pd.read_sql(
        """
        SELECT stock_code, trade_date, open, high, low, close, volume
        FROM stock_daily
        WHERE trade_date >= ? AND trade_date < ?
        """,
        conn,
        params=(history_start, min_new_date.strftime("%Y-%m-%d")),
    )
    if history.empty:
        history = pd.DataFrame(columns=["stock_code", "trade_date_dt", "close", "volume", "avg_price"])
    else:
        history["trade_date_dt"] = pd.to_datetime(history["trade_date"])
        history["avg_price"] = (
            history["open"] + history["high"] + history["low"] + history["close"]
        ) / 4
        history = history[["stock_code", "trade_date_dt", "close", "volume", "avg_price"]]

    df_new["avg_price"] = (
        df_new["open"] + df_new["high"] + df_new["low"] + df_new["close"]
    ) / 4

    history_cols = ["stock_code", "trade_date_dt", "close", "volume", "avg_price"]
    frames = [history[history_cols]] if not history.empty else []
    frames.append(df_new[history_cols])
    combined = pd.concat(frames, ignore_index=True)
    combined.sort_values(["stock_code", "trade_date_dt"], inplace=True)

    # 使用 GPU 加速计算（如果可用）
    if use_gpu:
        try:
            # 批量计算所有指标（更高效）
            from utils.gpu_acceleration import calculate_ma_indicators_gpu
            
            # 计算 avg_price 的 MA (3, 5, 10)
            for window in [3, 5, 10]:
                combined = calculate_ma_indicators_gpu(
                    combined,
                    columns=["avg_price"],
                    windows=[window],
                    group_by="stock_code"
                )
                # 重命名列
                combined = combined.rename(columns={
                    f'ma{window}_avg_price': f'ma{window}_avg_price'
                })
            
            # 计算 close 的 MA (5, 10, 20)
            for window in [5, 10, 20]:
                combined = calculate_ma_indicators_gpu(
                    combined,
                    columns=["close"],
                    windows=[window],
                    group_by="stock_code"
                )
                # 重命名列（ma5_close -> ma5, ma10_close -> ma10, ma20_close -> ma20）
                if window == 5:
                    combined = combined.rename(columns={'ma5_close': 'ma5'})
                elif window == 10:
                    combined = combined.rename(columns={'ma10_close': 'ma10'})
                elif window == 20:
                    combined = combined.rename(columns={'ma20_close': 'ma20'})
            
            # 计算 volume 的 MA5
            combined = calculate_ma_indicators_gpu(
                combined,
                columns=["volume"],
                windows=[5],
                group_by="stock_code"
            )
            combined = combined.rename(columns={'ma5_volume': 'volume_ma5'})
            
            # 确保数值精度
            for col in ['ma3_avg_price', 'ma5_avg_price', 'ma10_avg_price']:
                if col in combined.columns:
                    combined[col] = combined[col].round(4)
            for col in ['ma5', 'ma10', 'ma20', 'volume_ma5']:
                if col in combined.columns:
                    combined[col] = combined[col].round(2)
                    
        except Exception as e:
            print(f"[WARN] GPU 计算失败，回退到 CPU: {e}")
            import traceback
            traceback.print_exc()
            use_gpu = False

    # CPU 回退或原始逻辑
    if not use_gpu:
        grouped = combined.groupby("stock_code", group_keys=False)
        combined["ma3_avg_price"] = (
            grouped["avg_price"].rolling(3, min_periods=1).mean().round(4).reset_index(level=0, drop=True)
        )
        combined["ma5_avg_price"] = (
            grouped["avg_price"].rolling(5, min_periods=1).mean().round(4).reset_index(level=0, drop=True)
        )
        combined["ma10_avg_price"] = (
            grouped["avg_price"].rolling(10, min_periods=1).mean().round(4).reset_index(level=0, drop=True)
        )

        combined["ma5"] = (
            grouped["close"].rolling(5, min_periods=1).mean().round(2).reset_index(level=0, drop=True)
        )
        combined["ma10"] = (
            grouped["close"].rolling(10, min_periods=1).mean().round(2).reset_index(level=0, drop=True)
        )
        combined["ma20"] = (
            grouped["close"].rolling(20, min_periods=1).mean().round(2).reset_index(level=0, drop=True)
        )
        combined["volume_ma5"] = (
            grouped["volume"].rolling(5, min_periods=1).mean().round(2).reset_index(level=0, drop=True)
        )

    combined = combined[combined["trade_date_dt"] >= min_new_date].copy()
    combined.loc[:, "trade_date"] = combined["trade_date_dt"].dt.strftime("%Y-%m-%d")

    indicators = combined[
        [
            "stock_code",
            "trade_date",
            "ma3_avg_price",
            "ma5_avg_price",
            "ma10_avg_price",
            "ma5",
            "ma10",
            "ma20",
            "volume_ma5",
        ]
    ]

    df_new.loc[:, "trade_date"] = df_new["trade_date_dt"].dt.strftime("%Y-%m-%d")
    df_new = df_new.drop(columns=["trade_date_dt", "avg_price"])
    return df_new.merge(indicators, on=["stock_code", "trade_date"], how="left")


def backfill_recent_indicators(
    conn: sqlite3.Connection,
    latest_trade_date: datetime.date,
    recent_days: int = ROLLING_MAX_WINDOW * 3,
) -> None:
    """在没有新增交易日时，回填最近一段时间的技术指标与涨跌停价。"""
    fetch_start = (latest_trade_date - datetime.timedelta(days=recent_days)).strftime("%Y-%m-%d")
    df_recent = pd.read_sql(
        """
        SELECT id, stock_code, trade_date, open, high, low, close, prev_close, volume
        FROM stock_daily
        WHERE trade_date >= ?
        """,
        conn,
        params=(fetch_start,),
    )

    if df_recent.empty:
        print("没有需要回填的记录。")
        return

    df_calc = df_recent[
        ["stock_code", "trade_date", "open", "high", "low", "close", "prev_close", "volume"]
    ].copy()
    df_calc = compute_rolling_indicators(conn, df_calc)

    stock_flags = fetch_stock_flags(conn)
    limit_up, limit_down = compute_limit_prices(
        df_calc[["stock_code", "close", "prev_close"]].copy(), stock_flags
    )
    df_calc["limit_up"] = limit_up
    df_calc["limit_down"] = limit_down

    update_df = df_recent[["id", "stock_code", "trade_date"]].merge(
        df_calc[
            [
                "stock_code",
                "trade_date",
                "ma3_avg_price",
                "ma5_avg_price",
                "ma10_avg_price",
                "ma5",
                "ma10",
                "ma20",
                "volume_ma5",
                "limit_up",
                "limit_down",
            ]
        ],
        on=["stock_code", "trade_date"],
        how="left",
    )

    cursor = conn.cursor()
    updates = [
        (
            row.ma3_avg_price,
            row.ma5_avg_price,
            row.ma10_avg_price,
            row.ma5,
            row.ma10,
            row.ma20,
            row.volume_ma5,
            row.limit_up,
            row.limit_down,
            int(row.id),
        )
        for row in update_df.itertuples(index=False)
    ]

    if not updates:
        print("没有可更新的数据。")
        return

    cursor.executemany(
        """
        UPDATE stock_daily
        SET
            ma3_avg_price = ?,
            ma5_avg_price = ?,
            ma10_avg_price = ?,
            ma5 = ?,
            ma10 = ?,
            ma20 = ?,
            volume_ma5 = ?,
            limit_up = ?,
            limit_down = ?
        WHERE id = ?
        """,
        updates,
    )
    conn.commit()
    print(f"回填最近 {len(update_df)} 条记录的技术指标与涨跌停价。")


def run_incremental_update() -> None:
    ts.set_token('c32d8386d48a5c9e453add46d222912cdf866b3026950cba05c8b90b')
    pro = ts.pro_api()

    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    from database.db_utils import apply_performance_pragmas, ensure_indexes

    apply_performance_pragmas(conn, read_only=False)
    ensure_indexes(conn)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_daily';")
    if cursor.fetchone() is None:
        print("数据库缺少 stock_daily 表，请先初始化表结构。")
        conn.close()
        return

    cursor.execute("SELECT MAX(trade_date) FROM stock_daily;")
    result = cursor.fetchone()
    last_date_str = None
    if result is not None:
        last_date_str = result[0]
    if not last_date_str:
        print("数据库中没有现有数据，请检查表结构或初始数据。")
        conn.close()
        return

    try:
        last_date_dt = pd.to_datetime(last_date_str)
    except Exception:
        last_date_dt = pd.to_datetime(last_date_str, format='%Y%m%d')
    last_date_dt = last_date_dt.date()
    next_date_dt = last_date_dt + datetime.timedelta(days=1)
    start_date_str = next_date_dt.strftime('%Y%m%d')

    today_dt = datetime.date.today()
    today_str = today_dt.strftime('%Y%m%d')

    cal_recent = call_with_rate_limit(
        pro.trade_cal,
        exchange='',
        start_date=(today_dt - datetime.timedelta(days=10)).strftime('%Y%m%d'),
        end_date=today_str,
        fields='cal_date,is_open'
    )
    open_days = cal_recent[cal_recent['is_open'] == 1]['cal_date'].sort_values().tolist()
    if not open_days:
        target_date_str = today_str
    else:
        last_open_date = open_days[-1]
        if last_open_date == today_str:
            current_hour = datetime.datetime.now().hour
            if current_hour < 17:
                if len(open_days) >= 2:
                    target_date_str = open_days[-2]
                else:
                    target_date_str = last_open_date
            else:
                target_date_str = today_str
        else:
            target_date_str = last_open_date

    if pd.to_datetime(target_date_str) <= pd.to_datetime(start_date_str):
        backfill_recent_indicators(conn, last_date_dt)
        print("数据已经是最新，无新增记录，已回填最近技术指标。")
        conn.close()
        return

    cal_update = call_with_rate_limit(
        pro.trade_cal,
        exchange='',
        start_date=start_date_str,
        end_date=target_date_str,
        fields='cal_date,is_open'
    )
    update_days = cal_update[cal_update['is_open'] == 1]['cal_date'].tolist()

    col_order = [
        'stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'prev_close',
        'change_amount', 'change_pct', 'volume', 'amount', 'total_mv', 'float_mv',
        'turnover_rate', 'turnover_free', 'volume_ratio', 'pe', 'pe_ttm', 'pb',
        'ps', 'ps_ttm', 'dividend_yield', 'dividend_yield_ttm', 'total_shares',
        'float_shares', 'free_float_shares', 'limit_up', 'limit_down',
        'adj_factor', 'ts_code', 'ma3_avg_price', 'ma5_avg_price', 'ma10_avg_price',
        'ma5', 'ma10', 'ma20', 'volume_ma5'
    ]

    all_new_data = []

    for date_str in update_days:
        df_daily = call_with_rate_limit(
            pro.daily,
            trade_date=date_str,
            fields='ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount'
        )
        if df_daily is None or df_daily.empty:
            continue
        df_basic = call_with_rate_limit(
            pro.daily_basic,
            ts_code='',
            trade_date=date_str,
            fields='ts_code,trade_date,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv'
        )
        if df_basic is None or df_basic.empty:
            continue
        df_adj = call_with_rate_limit(pro.adj_factor, ts_code='', trade_date=date_str)
        if df_adj is None or df_adj.empty:
            continue

        df_merge = pd.merge(df_daily, df_basic, on=['ts_code', 'trade_date'], how='inner')
        df_merge = pd.merge(df_merge, df_adj, on=['ts_code', 'trade_date'], how='inner')

        df_merge.rename(columns={
            'pre_close': 'prev_close',
            'change': 'change_amount',
            'pct_chg': 'change_pct',
            'vol': 'volume',
            'turnover_rate_f': 'turnover_free',
            'circ_mv': 'float_mv',
            'total_share': 'total_shares',
            'float_share': 'float_shares',
            'free_share': 'free_float_shares',
            'dv_ratio': 'dividend_yield',
            'dv_ttm': 'dividend_yield_ttm'
        }, inplace=True)

        df_merge['stock_code'] = df_merge['ts_code'].str.split('.', expand=True)[0]

        for col in col_order:
            if col not in df_merge.columns:
                df_merge[col] = None

        df_merge = df_merge[col_order]

        df_merge['trade_date'] = pd.to_datetime(df_merge['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')

        all_new_data.append(df_merge)
        print(f"{date_str} 数据获取完成，股票数: {len(df_merge)}")

    if all_new_data:
        df_all_new = pd.concat(all_new_data, ignore_index=True)
        numeric_for_calc = [
            'open', 'high', 'low', 'close', 'prev_close', 'volume'
        ]
        for col in numeric_for_calc:
            if col in df_all_new.columns:
                df_all_new[col] = pd.to_numeric(df_all_new[col], errors='coerce')

        df_all_new = compute_rolling_indicators(conn, df_all_new)

        stock_flags = fetch_stock_flags(conn)
        limit_up, limit_down = compute_limit_prices(df_all_new[["stock_code", "close", "prev_close"]].copy(), stock_flags)
        df_all_new["limit_up"] = limit_up
        df_all_new["limit_down"] = limit_down

        df_all_new = df_all_new[col_order]

        try:
            df_all_new.to_sql('stock_daily', conn, if_exists='append', index=False)
            print(f"成功更新至 {target_date_str}，共插入 {len(df_all_new)} 条记录。")
        except Exception as e:
            print("数据插入数据库时发生错误:", e)
    else:
        print("没有获取到新的日线数据，无数据插入。")

    conn.close()


if __name__ == "__main__":
    if os.getenv("ENABLE_TUSHARE_UPDATER", "1") != "1":
        sys.exit(0)
    run_incremental_update()
