import gc
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import cupy as np
except ImportError:
    import numpy as np
import pandas as pd
from tqdm import tqdm

from utils.config import Config


class FastStockDataProcessor:
    """
    High-speed CSV -> SQLite loader with post-processing for technical indicators.
    Rewritten to retain all original stock_daily columns during indicator calculation.
    """

    DAILY_COLUMNS = [
        "stock_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "prev_close",
        "change_amount",
        "change_pct",
        "volume",
        "amount",
        "total_mv",
        "float_mv",
        "turnover_rate",
        "turnover_free",
        "volume_ratio",
        "pe",
        "pe_ttm",
        "pb",
        "ps",
        "ps_ttm",
        "dividend_yield",
        "dividend_yield_ttm",
        "total_shares",
        "float_shares",
        "free_float_shares",
        "limit_up",
        "limit_down",
        "adj_factor",
        "ts_code",
    ]

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)

        # CHANGED: 使用统一的性能优化 PRAGMA（写入时使用更激进的设置）
        from database.db_utils import apply_performance_pragmas
        # 写入时使用更激进的设置
        cur = self.conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")  # 写入时使用 NORMAL 而不是 OFF（更安全）
        cur.execute("PRAGMA temp_store=MEMORY;")
        cur.execute("PRAGMA mmap_size=30000000000;")
        cur.execute("PRAGMA cache_size=-200000;")  # 约 200MB
        cur.execute("PRAGMA busy_timeout=8000;")
        self.conn.commit()

    # ------------------------------------------------------------------ schema
    def create_tables(self) -> None:
        """Reset and create stock_info and stock_daily without indexes."""
        cursor = self.conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS stock_info")
        cursor.execute("DROP TABLE IF EXISTS stock_daily")

        cursor.execute(
            """
            CREATE TABLE stock_info (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                industry TEXT,
                region TEXT,
                list_date DATE,
                is_st BOOLEAN DEFAULT 0,
                is_kc BOOLEAN DEFAULT 0,
                is_cy BOOLEAN DEFAULT 0
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE stock_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                trade_date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                prev_close REAL,
                change_amount REAL,
                change_pct REAL,
                volume INTEGER,
                amount REAL,
                total_mv REAL,
                float_mv REAL,
                turnover_rate REAL,
                turnover_free REAL,
                volume_ratio REAL,
                pe REAL,
                pe_ttm REAL,
                pb REAL,
                ps REAL,
                ps_ttm REAL,
                dividend_yield REAL,
                dividend_yield_ttm REAL,
                total_shares REAL,
                float_shares REAL,
                free_float_shares REAL,
                limit_up REAL,
                limit_down REAL,
                adj_factor REAL,
                ts_code TEXT
            )
            """
        )
        self.conn.commit()
        print("数据库表创建完成")

    # ------------------------------------------------------------------ parsing
    def _parse_csv_file(self, file_path: Path) -> Tuple[Optional[Dict], Optional[List[Tuple]]]:
        """Parse a single CSV file and return stock info + daily tuples."""
        try:
            desired_cols = [
                "股票代码",
                "名称",
                "所属行业",
                "地域",
                "上市日期",
                "TS代码",
                "交易日期",
                "开盘价",
                "最高价",
                "最低价",
                "收盘价",
                "前收盘价",
                "涨跌额",
                "涨跌幅(%)",
                "成交量(股)",
                "成交量(手)",
                "成交额(千元)",
                "总市值(万元)",
                "流通市值(万元)",
                "换手率(%)",
                "换手率(自由流通股)",
                "量比",
                "市盈率",
                "市盈率(TTM,亏损的PE为空)",
                "市净率",
                "市销率",
                "市销率(TTM)",
                "股息率(%)",
                "股息率(TTM)(%)",
                "总股本(万股)",
                "流通股本(万股)",
                "自由流通股本(万股)",
                "今日涨停价",
                "今日跌停价",
                "复权因子",
            ]
            df = pd.read_csv(file_path, low_memory=False, usecols=lambda c: c in desired_cols)
            if df.empty:
                return None, None

            if "成交量(手)" in df.columns:
                volume_lots = pd.to_numeric(df["成交量(手)"], errors="coerce")
                if "成交量(股)" in df.columns:
                    volume_shares = pd.to_numeric(df["成交量(股)"], errors="coerce")
                else:
                    volume_shares = pd.Series(0, index=df.index, dtype="float64")
                df["成交量(股)"] = volume_shares.fillna(0) + volume_lots.fillna(0) * 100
                df = df.drop(columns=["成交量(手)"])

            stock_code = str(df.iloc[0]["股票代码"])
            stock_name = str(df.iloc[0]["名称"])

            stock_info = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "industry": str(df.iloc[0]["所属行业"]),
                "region": str(df.iloc[0]["地域"]),
                "list_date": str(df.iloc[0]["上市日期"]),
                "is_st": 1 if "ST" in stock_name else 0,
                "is_kc": 1 if stock_code.startswith("688") else 0,
                "is_cy": 1 if stock_code.startswith("300") else 0,
            }

            df_daily = df.copy()
            df_daily["stock_code"] = stock_code
            df_daily["trade_date"] = (
                pd.to_datetime(df_daily["交易日期"].astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
            )

            column_mapping = {
                "开盘价": "open",
                "最高价": "high",
                "最低价": "low",
                "收盘价": "close",
                "前收盘价": "prev_close",
                "涨跌额": "change_amount",
                "涨跌幅(%)": "change_pct",
                "成交量(股)": "volume",
                "成交额(千元)": "amount",
                "总市值(万元)": "total_mv",
                "流通市值(万元)": "float_mv",
                "换手率(%)": "turnover_rate",
                "换手率(自由流通股)": "turnover_free",
                "量比": "volume_ratio",
                "市盈率": "pe",
                "市盈率(TTM,亏损的PE为空)": "pe_ttm",
                "市净率": "pb",
                "市销率": "ps",
                "市销率(TTM)": "ps_ttm",
                "股息率(%)": "dividend_yield",
                "股息率(TTM)(%)": "dividend_yield_ttm",
                "总股本(万股)": "total_shares",
                "流通股本(万股)": "float_shares",
                "自由流通股本(万股)": "free_float_shares",
                "今日涨停价": "limit_up",
                "今日跌停价": "limit_down",
                "复权因子": "adj_factor",
                "TS代码": "ts_code",
            }
            df_daily = df_daily.rename(columns=column_mapping)

            numeric_cols = [
                "open",
                "high",
                "low",
                "close",
                "prev_close",
                "change_amount",
                "change_pct",
                "volume",
                "amount",
                "total_mv",
                "float_mv",
                "turnover_rate",
                "turnover_free",
                "volume_ratio",
                "pe",
                "pe_ttm",
                "pb",
                "ps",
                "ps_ttm",
                "dividend_yield",
                "dividend_yield_ttm",
                "total_shares",
                "float_shares",
                "free_float_shares",
                "limit_up",
                "limit_down",
                "adj_factor",
            ]
            for col in numeric_cols:
                if col in df_daily.columns:
                    df_daily[col] = pd.to_numeric(df_daily[col], errors="coerce")

            daily_columns = self.DAILY_COLUMNS.copy()
            for col in daily_columns:
                if col not in df_daily.columns:
                    df_daily[col] = np.nan

            df_daily["ts_code"] = df_daily.get("ts_code", stock_code)
            df_daily["ts_code"] = df_daily["ts_code"].fillna(stock_code).astype(str)

            df_daily = df_daily[daily_columns].replace([np.inf, -np.inf], np.nan)
            daily_data_tuples = [tuple(x) for x in df_daily.to_numpy()]

            return stock_info, daily_data_tuples
        except Exception:
            return None, None

    # ---------------------------------------------------------------- inserts
    def _batch_insert_stock_info(self, stock_info_list: List[Dict]) -> None:
        if not stock_info_list:
            return
        cursor = self.conn.cursor()
        try:
            placeholders = ",".join(["?"] * len(stock_info_list[0]))
            query = f"""
                INSERT OR REPLACE INTO stock_info 
                (stock_code, stock_name, industry, region, list_date, is_st, is_kc, is_cy) 
                VALUES ({placeholders})
            """
            data = [
                (
                    d["stock_code"],
                    d["stock_name"],
                    d["industry"],
                    d["region"],
                    d["list_date"],
                    d["is_st"],
                    d["is_kc"],
                    d["is_cy"],
                )
                for d in stock_info_list
            ]
            cursor.executemany(query, data)
            self.conn.commit()
        except Exception as e:
            print(f"批量插入 stock_info 失败: {e}")
            self.conn.rollback()

    def _batch_insert_daily_data(self, daily_data_list: List[Tuple]) -> None:
        if not daily_data_list:
            return
        cursor = self.conn.cursor()
        try:
            placeholders = ",".join(["?"] * len(self.DAILY_COLUMNS))
            query = f"""
                INSERT INTO stock_daily 
                (stock_code, trade_date, open, high, low, close,
                 prev_close, change_amount, change_pct,
                 volume, amount, total_mv, float_mv,
                 turnover_rate, turnover_free, volume_ratio,
                 pe, pe_ttm, pb, ps, ps_ttm,
                 dividend_yield, dividend_yield_ttm,
                 total_shares, float_shares, free_float_shares,
                 limit_up, limit_down, adj_factor, ts_code)
                VALUES ({placeholders})
            """
            cursor.executemany(query, daily_data_list)
            self.conn.commit()
        except Exception as e:
            print(f"批量插入 stock_daily 失败: {e}")
            self.conn.rollback()

    # ----------------------------------------------------------------- import
    def process_files_in_batches(self, batch_size: int = 100) -> None:
        csv_files = list(Path(Config.DATA_DIR).glob("*.csv"))
        print(f"找到 {len(csv_files)} 个CSV文件，按批次处理（每批{batch_size}个文件）")

        for i in tqdm(range(0, len(csv_files), batch_size), desc="处理批次"):
            batch_files = csv_files[i : i + batch_size]
            stock_info_batch: List[Dict] = []
            daily_data_batch: List[Tuple] = []

            for file_path in batch_files:
                stock_info, daily_data = self._parse_csv_file(file_path)
                if stock_info:
                    stock_info_batch.append(stock_info)
                if daily_data:
                    daily_data_batch.extend(daily_data)

            self._batch_insert_stock_info(stock_info_batch)
            self._batch_insert_daily_data(daily_data_batch)
            del stock_info_batch, daily_data_batch
            gc.collect()

        print("所有文件处理完毕")

    # ---------------------------------------------------------- backfilling
    def backfill_missing_volume_and_limits(self, commit_every: int = 5000) -> None:
        """
        仅补齐 volume / limit_up / limit_down 空值，不重写已有记录。
        从原始 CSV 读取需要的列，逐行 UPDATE（只有列为 NULL 时才写入）。
        """
        csv_files = list(Path(Config.DATA_DIR).glob("*.csv"))
        if not csv_files:
            print("未找到任何 CSV 文件，无法补全缺失列。")
            return

        cursor = self.conn.cursor()
        update_sql = """
            UPDATE stock_daily
            SET
                volume = CASE WHEN volume IS NULL AND ? IS NOT NULL THEN ? ELSE volume END,
                limit_up = CASE WHEN limit_up IS NULL AND ? IS NOT NULL THEN ? ELSE limit_up END,
                limit_down = CASE WHEN limit_down IS NULL AND ? IS NOT NULL THEN ? ELSE limit_down END
            WHERE stock_code = ? AND trade_date = ?
        """

        updates: List[Tuple] = []
        total_candidates = 0
        filled_rows = 0

        column_index = {name: idx for idx, name in enumerate(self.DAILY_COLUMNS)}
        idx_stock = column_index["stock_code"]
        idx_trade_date = column_index["trade_date"]
        idx_volume = column_index["volume"]
        idx_limit_up = column_index["limit_up"]
        idx_limit_down = column_index["limit_down"]

        for file_path in tqdm(csv_files, desc="补齐缺失列"):
            try:
                _, daily_rows = self._parse_csv_file(file_path)
            except Exception as exc:
                print(f"[WARN] 解析 {file_path.name} 失败: {exc}")
                continue

            if not daily_rows:
                continue

            for row in daily_rows:
                total_candidates += 1
                updates.append(
                    (
                        row[idx_volume],
                        row[idx_volume],
                        row[idx_limit_up],
                        row[idx_limit_up],
                        row[idx_limit_down],
                        row[idx_limit_down],
                        row[idx_stock],
                        row[idx_trade_date],
                    )
                )

                if len(updates) >= commit_every:
                    cursor.executemany(update_sql, updates)
                    self.conn.commit()
                    filled_rows += cursor.rowcount if cursor.rowcount is not None else 0
                    updates.clear()

        if updates:
            cursor.executemany(update_sql, updates)
            self.conn.commit()
            filled_rows += cursor.rowcount if cursor.rowcount is not None else 0

        print(
            f"补齐 volume / limit_up / limit_down: 处理 {total_candidates} 行（SQL 更新 {filled_rows} 行，仅改 NULL 列）。"
        )

    def recompute_volume_ma5_for_gaps(self, batch_size: int = 50) -> None:
        """
        针对 volume_ma5 仍为空的股票，按股票分批重新计算（使用最新 volume）。
        """
        codes_df = pd.read_sql(
            "SELECT DISTINCT stock_code FROM stock_daily WHERE volume_ma5 IS NULL", self.conn
        )
        if codes_df.empty:
            print("没有 volume_ma5 缺失的股票。")
            return

        codes = codes_df["stock_code"].tolist()
        cursor = self.conn.cursor()
        total_updates = 0

        for i in tqdm(range(0, len(codes), batch_size), desc="补齐 volume_ma5"):
            batch_codes = codes[i : i + batch_size]
            placeholders = ",".join(["?"] * len(batch_codes))
            query = f"""
                SELECT id, stock_code, trade_date, volume, volume_ma5
                FROM stock_daily
                WHERE stock_code IN ({placeholders})
                ORDER BY stock_code, trade_date
            """
            df_batch = pd.read_sql(query, self.conn, params=batch_codes)
            if df_batch.empty:
                continue

            updates: List[Tuple[float, int]] = []
            for _, group in df_batch.groupby("stock_code"):
                group = group.sort_values("trade_date")
                computed = (
                    group["volume"].rolling(window=5, min_periods=1).mean().round(2)
                )
                needs_update = group["volume_ma5"].isna() & computed.notna()
                if not needs_update.any():
                    continue

                for idx in group.index[needs_update]:
                    updates.append((float(computed.loc[idx]), int(group.loc[idx, "id"])))

            if updates:
                cursor.executemany(
                    "UPDATE stock_daily SET volume_ma5 = ? WHERE id = ?", updates
                )
                self.conn.commit()
                total_updates += len(updates)

        print(f"补齐 volume_ma5 完成，共更新 {total_updates} 行。")

    # ----------------------------------------------------------------- indexes
    def create_indexes(self) -> None:
        print("开始创建索引...")
        cursor = self.conn.cursor()
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_date ON stock_daily(stock_code, trade_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_stock ON stock_daily(trade_date, stock_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON stock_daily(trade_date)")
            self.conn.commit()
            print("索引创建完成")
        except Exception as e:
            print(f"创建索引失败: {e}")

    # ------------------------------------------------------------- indicators
    def calculate_technical_indicators_fast(self) -> None:
        """
        Compute technical indicators while retaining all original stock_daily columns.
        """
        print("开始极速计算技术指标（保留全部原始列）...")
        cursor = self.conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS stock_daily_processed")
        cursor.execute(
            """
            CREATE TABLE stock_daily_processed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                trade_date DATE NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                prev_close REAL, change_amount REAL, change_pct REAL,
                volume INTEGER, amount REAL, total_mv REAL, float_mv REAL,
                turnover_rate REAL, turnover_free REAL, volume_ratio REAL,
                pe REAL, pe_ttm REAL, pb REAL, ps REAL, ps_ttm REAL,
                dividend_yield REAL, dividend_yield_ttm REAL,
                total_shares REAL, float_shares REAL, free_float_shares REAL,
                limit_up REAL, limit_down REAL,
                adj_factor REAL, ts_code TEXT,
                ma3_avg_price REAL, ma5_avg_price REAL, ma10_avg_price REAL,
                ma5 REAL, ma10 REAL, ma20 REAL, volume_ma5 REAL
            )
            """
        )
        self.conn.commit()

        base_cols = [
            "stock_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "prev_close",
            "change_amount",
            "change_pct",
            "volume",
            "amount",
            "total_mv",
            "float_mv",
            "turnover_rate",
            "turnover_free",
            "volume_ratio",
            "pe",
            "pe_ttm",
            "pb",
            "ps",
            "ps_ttm",
            "dividend_yield",
            "dividend_yield_ttm",
            "total_shares",
            "float_shares",
            "free_float_shares",
            "limit_up",
            "limit_down",
            "adj_factor",
            "ts_code",
        ]

        stock_codes = pd.read_sql("SELECT DISTINCT stock_code FROM stock_daily", self.conn)["stock_code"].tolist()
        print(f"将为 {len(stock_codes)} 只股票计算指标...")

        batch_size = 50
        total_batches = (len(stock_codes) + batch_size - 1) // batch_size

        try:
            for batch_idx in tqdm(range(total_batches), desc="处理批次"):
                batch_codes = stock_codes[batch_idx * batch_size : (batch_idx + 1) * batch_size]
                placeholders = ",".join(["?"] * len(batch_codes))
                select_cols = ", ".join(["id"] + base_cols)
                query = f"""
                    SELECT {select_cols}
                    FROM stock_daily
                    WHERE stock_code IN ({placeholders})
                    ORDER BY stock_code, trade_date
                """
                df_batch = pd.read_sql(query, self.conn, params=batch_codes)
                if df_batch.empty:
                    continue

                all_processed: List[Tuple] = []

                for code in batch_codes:
                    data = df_batch[df_batch["stock_code"] == code].copy()
                    if data.empty:
                        continue

                    if len(data) < 5:
                        for _, row in data.iterrows():
                            avg_price = (row["open"] + row["high"] + row["low"] + row["close"]) / 4
                            all_processed.append(
                                (
                                    row["stock_code"],
                                    row["trade_date"],
                                    row["open"],
                                    row["high"],
                                    row["low"],
                                    row["close"],
                                    row["prev_close"],
                                    row["change_amount"],
                                    row["change_pct"],
                                    row["volume"],
                                    row["amount"],
                                    row["total_mv"],
                                    row["float_mv"],
                                    row["turnover_rate"],
                                    row["turnover_free"],
                                    row["volume_ratio"],
                                    row["pe"],
                                    row["pe_ttm"],
                                    row["pb"],
                                    row["ps"],
                                    row["ps_ttm"],
                                    row["dividend_yield"],
                                    row["dividend_yield_ttm"],
                                    row["total_shares"],
                                    row["float_shares"],
                                    row["free_float_shares"],
                                    row["limit_up"],
                                    row["limit_down"],
                                    row["adj_factor"],
                                    row["ts_code"],
                                    avg_price,
                                    avg_price,
                                    avg_price,
                                    row["close"],
                                    row["close"],
                                    row["close"],
                                    row["volume"],
                                )
                            )
                        continue

                    data = data.sort_values("trade_date")
                    data["avg_price"] = (data["open"] + data["high"] + data["low"] + data["close"]) / 4

                    data["ma3_avg_price"] = data["avg_price"].rolling(3, min_periods=1).mean().round(4)
                    data["ma5_avg_price"] = data["avg_price"].rolling(5, min_periods=1).mean().round(4)
                    data["ma10_avg_price"] = data["avg_price"].rolling(10, min_periods=1).mean().round(4)

                    data["ma5"] = data["close"].rolling(5, min_periods=1).mean().round(2)
                    data["ma10"] = data["close"].rolling(10, min_periods=1).mean().round(2)
                    data["ma20"] = data["close"].rolling(20, min_periods=1).mean().round(2)
                    data["volume_ma5"] = data["volume"].rolling(5, min_periods=1).mean().round(2)

                    data["ma3_avg_price"] = data["ma3_avg_price"].fillna(data["avg_price"])
                    data["ma5_avg_price"] = data["ma5_avg_price"].fillna(data["avg_price"])
                    data["ma10_avg_price"] = data["ma10_avg_price"].fillna(data["avg_price"])
                    data["ma5"] = data["ma5"].fillna(data["close"])
                    data["ma10"] = data["ma10"].fillna(data["close"])
                    data["ma20"] = data["ma20"].fillna(data["close"])
                    data["volume_ma5"] = data["volume_ma5"].fillna(data["volume"])

                    for _, row in data.iterrows():
                        all_processed.append(
                            (
                                row["stock_code"],
                                row["trade_date"],
                                row["open"],
                                row["high"],
                                row["low"],
                                row["close"],
                                row["prev_close"],
                                row["change_amount"],
                                row["change_pct"],
                                row["volume"],
                                row["amount"],
                                row["total_mv"],
                                row["float_mv"],
                                row["turnover_rate"],
                                row["turnover_free"],
                                row["volume_ratio"],
                                row["pe"],
                                row["pe_ttm"],
                                row["pb"],
                                row["ps"],
                                row["ps_ttm"],
                                row["dividend_yield"],
                                row["dividend_yield_ttm"],
                                row["total_shares"],
                                row["float_shares"],
                                row["free_float_shares"],
                                row["limit_up"],
                                row["limit_down"],
                                row["adj_factor"],
                                row["ts_code"],
                                row["ma3_avg_price"],
                                row["ma5_avg_price"],
                                row["ma10_avg_price"],
                                row["ma5"],
                                row["ma10"],
                                row["ma20"],
                                row["volume_ma5"],
                            )
                        )

                if all_processed:
                    placeholders = ",".join(["?"] * 37)
                    insert_sql = f"""
                        INSERT INTO stock_daily_processed (
                            stock_code, trade_date, open, high, low, close,
                            prev_close, change_amount, change_pct,
                            volume, amount, total_mv, float_mv,
                            turnover_rate, turnover_free, volume_ratio,
                            pe, pe_ttm, pb, ps, ps_ttm,
                            dividend_yield, dividend_yield_ttm,
                            total_shares, float_shares, free_float_shares,
                            limit_up, limit_down, adj_factor, ts_code,
                            ma3_avg_price, ma5_avg_price, ma10_avg_price,
                            ma5, ma10, ma20, volume_ma5
                        ) VALUES ({placeholders})
                    """
                    cursor.executemany(insert_sql, all_processed)
                    self.conn.commit()

                del df_batch, all_processed
                gc.collect()

        except Exception as e:
            print(f"\n处理批次 {batch_idx} 时发生错误: {e}")
            self.conn.rollback()
            return

        print("\n数据迁移完成。正在替换旧表并创建索引...")
        try:
            cursor.execute("DROP TABLE IF EXISTS stock_daily")
            cursor.execute("ALTER TABLE stock_daily_processed RENAME TO stock_daily")
            cursor.execute("CREATE INDEX idx_stock_date ON stock_daily(stock_code, trade_date)")
            cursor.execute("CREATE INDEX idx_date_stock ON stock_daily(trade_date, stock_code)")
            cursor.execute("CREATE INDEX idx_date ON stock_daily(trade_date)")
            self.conn.commit()
            print("技术指标计算完成，索引已创建。")
        except Exception as e:
            print(f"替换表或创建索引失败: {e}")
            self.conn.rollback()

    # ------------------------------------------------------------------ close
    def close(self) -> None:
        """Close DB connection and restore pragmas."""
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.close()
