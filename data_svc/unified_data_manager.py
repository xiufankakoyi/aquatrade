"""
Unified Data Manager
====================
Transparent data access layer routing queries to QuestDB (Hot) or Parquet (Cold).

Usage:
    from data_svc.unified_data_manager import UnifiedDataManager
    
    udm = UnifiedDataManager()
    
    # Auto-routes to QuestDB, Parquet, or Both based on date range
    df = udm.get_price(["000001.SZ"], "2019-01-01", "2023-01-01")
"""

import os
import polars as pl
from typing import List, Optional, Union
from datetime import datetime
from data_svc.database.questdb_manager import get_questdb_manager, QuestDBManager
from config.config import Config

class UnifiedDataManager:
    SPLIT_DATE = "2020-01-01"
    
    def __init__(self):
        self.questdb: QuestDBManager = get_questdb_manager()
        self.parquet_dir = Config.PARQUET_DIR if hasattr(Config, 'PARQUET_DIR') else r"d:\aquatrade\data\parquet_data"
        
        # Cold Data Paths
        self.cold_files = {
            "base_daily": os.path.join(self.parquet_dir, "base_daily_archive.parquet"),
            "factors_momentum": os.path.join(self.parquet_dir, "factors_momentum_archive.parquet"),
            "factors_valuation": os.path.join(self.parquet_dir, "factors_valuation_archive.parquet")
        }
        
    def get_price(self, 
                  codes: Optional[List[str]] = None, 
                  start_date: Optional[str] = None, 
                  end_date: Optional[str] = None,
                  frequency: str = '1d', 
                  fields: Optional[List[str]] = None) -> pl.DataFrame:
        """
        Get Price Data (OHLCV + Adj)
        
        Args:
            codes: List of stock codes (None for all)
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
            frequency: '1d' only for now
            fields: List of fields to select (e.g. ['open', 'close'])
            
        Returns:
            polars.DataFrame sorted by (ts, code)
        """
        return self._route_query("base_daily", codes, start_date, end_date, fields)

    def get_factors(self, 
                    codes: Optional[List[str]] = None, 
                    factors: Optional[List[str]] = None, 
                    start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> pl.DataFrame:
        """
        Get Factor Data (Momentum & Valuation)
        
        Args:
            codes: List of stock codes
            factors: List of factor names (e.g. ['rsi_14', 'pe_ttm'])
            start_date: Start date
            end_date: End date
            
        Returns:
            polars.DataFrame with 'ts', 'code' and requested factors
        """
        # Determine which tables contain the requested factors
        # This is a simplified implementation assuming caller knows what they want
        # For a full implementation, we'd need a registry mapping factor -> table
        
        # For now, let's implement a simple direct table query if requested
        # Or we can scan both tables if factors are mixed.
        # To keep iteration 1 simple, let's allow querying specific tables via _route_query
        # or implement logic to join tables.
        
        # Strategy:
        # 1. Identify needed tables based on factor names
        # 2. Query each table for the date range
        # 3. Join results on (ts, code)
        
        # Simplified for Phase 1: Support querying specific tables via separate methods or generic query
        # Let's provide table-specific wrappers first for clarity
        pass

    def get_momentum_factors(self, 
                           codes: Optional[List[str]] = None, 
                           start_date: Optional[str] = None, 
                           end_date: Optional[str] = None) -> pl.DataFrame:
        return self._route_query("factors_momentum", codes, start_date, end_date)

    def get_valuation_factors(self, 
                            codes: Optional[List[str]] = None, 
                            start_date: Optional[str] = None, 
                            end_date: Optional[str] = None) -> pl.DataFrame:
        return self._route_query("factors_valuation", codes, start_date, end_date)

    # --- Internal Routing Logic ---

    def _route_query(self, 
                     table_name: str, 
                     codes: Optional[List[str]], 
                     start_date: str, 
                     end_date: str,
                     columns: Optional[List[str]] = None) -> pl.DataFrame:
        """
        Core routing logic: Hot vs Cold vs Hybrid
        """
        # 1. Normalize dates
        start = start_date or "1990-01-01"
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        
        # 2. Determine Route
        if start >= self.SPLIT_DATE:
            # Case A: Hot Only
            return self._query_hot(table_name, codes, start, end, columns)
        
        elif end < self.SPLIT_DATE:
            # Case B: Cold Only
            return self._query_cold(table_name, codes, start, end, columns)
            
        else:
            # Case C: Hybrid
            # Split Range: [start, 2019-12-31] + [2020-01-01, end]
            df_cold = self._query_cold(table_name, codes, start, "2019-12-31", columns)
            df_hot = self._query_hot(table_name, codes, self.SPLIT_DATE, end, columns)
            
            # Combine
            if df_cold.is_empty(): return df_hot
            if df_hot.is_empty(): return df_cold
            
            # Align columns for concatenation
            # 1. Intersection of columns
            common_cols = [c for c in df_cold.columns if c in df_hot.columns]
            
            # 2. Reorder both to match
            if not common_cols:
                return pl.DataFrame() # Or raise error?
                
            df_cold = df_cold.select(common_cols)
            df_hot = df_hot.select(common_cols)
            
            return pl.concat([df_cold, df_hot]).sort(["ts", "code"])

    def _normalize_code_for_cold(self, code: str) -> str:
        """
        Normalize code for cold storage (e.g. '000001.SZ' -> '1')
        Removes suffix and leading zeros.
        """
        if not code: return code
        # Remove suffix
        c = code.split('.')[0]
        # Remove leading zeros by converting to int then str
        try:
            return str(int(c))
        except:
            return c

    @property
    def _benchmark_file(self):
        return os.path.join(self.parquet_dir, "benchmark_daily.parquet")

    def get_trading_dates(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[str]:
        """Get list of trading dates (poly-filled from Hot and Cold sources)"""
        # Cache key could be implemented, but Polars is fast enough for now if we use LazyFrame
        # Ideally we cache the FULL list once.
        
        full_dates = self._get_cached_all_dates()
        
        # Filter
        start = start_date or "1990-01-01"
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        
        return [d for d in full_dates if start <= d <= end]

    def get_prev_trade_date(self, date: str) -> Optional[str]:
        dates = self.get_trading_dates(end_date=date)
        # Filter out the date itself if present
        dates = [d for d in dates if d < date]
        if dates: return dates[-1]
        return None

    def get_next_trade_date(self, date: str) -> Optional[str]:
        dates = self.get_trading_dates(start_date=date)
        # Filter out the date itself if present
        dates = [d for d in dates if d > date]
        if dates: return dates[0]
        return None

    def _get_cached_all_dates(self) -> List[str]:
        """Fetch and cache all trading dates from cold (benchmark) and hot (base_daily)"""
        if hasattr(self, "_cached_dates") and self._cached_dates:
            return self._cached_dates
            
        dates = set()
        
        # 1. Cold Dates from benchmark_daily.parquet
        try:
            if os.path.exists(self._benchmark_file):
                df = pl.read_parquet(self._benchmark_file, columns=["date"])
                cold_dates = df["date"].to_list()
                dates.update([d.split(' ')[0] for d in str(cold_dates) if isinstance(d, str)] if cold_dates else [])
                # Handle varying formats if necessary, assuming YYYY-MM-DD string or date object
                # Polars likely returns str or date.
                dates.update([str(d) for d in cold_dates])
        except Exception as e:
            print(f"Error reading cold dates: {e}")
            
        # 2. Hot Dates from QuestDB
        # We query DISTINCT timestamp from base_daily.
        try:
            sql = "SELECT DISTINCT timestamp FROM base_daily"
            df_hot = self.questdb.query(sql)
            if not df_hot.is_empty():
                hot_dates = df_hot["timestamp"].to_list()
                
                for t in hot_dates:
                    if isinstance(t, str):
                        dates.add(t[:10]) # First 10 chars: YYYY-MM-DD
                        
        except Exception as e:
            print(f"Error reading hot dates: {e}")
            
        sorted_dates = sorted(list(dates))
        self._cached_dates = sorted_dates
        return sorted_dates

    def _normalize_code_for_hot(self, code: str) -> str:
        """
        Normalize code for hot storage (e.g. '000001.SZ' -> '000001')
        Removes suffix but keeps 6-digit (or original length) format.
        """
        if not code: return code
        return code.split('.')[0]

    def _query_hot(self,
                   table_name: str, 
                   codes: Optional[List[str]], 
                   start: str, 
                   end: str,
                   columns: Optional[List[str]] = None) -> pl.DataFrame:
        """Query QuestDB"""
        # QuestDB Schema: timestamp (partition), stock_code (symbol) - Verified via probe
        ts_col = "timestamp"
        code_col = "stock_code"
        
        # Build SQL
        where_clauses = [f"{ts_col} BETWEEN '{start}' AND '{end}'"]
        if codes:
            # Normalize codes for QuestDB: 000001.SZ -> 000001
            norm_codes = [self._normalize_code_for_hot(c) for c in codes]
            code_list = ",".join([f"'{c}'" for c in norm_codes])
            where_clauses.append(f"{code_col} IN ({code_list})")
            
        where_sql = " AND ".join(where_clauses)
        
        select_cols = "*"
        if columns:
            # Map unified names back to DB names if needed
            # For now, select * is safer to ensure we get everything, then filter/rename
            # But for performance with many columns, we should select specific ones.
            # Assuming columns passed are unified names (ts, code, open, close...)
            
            db_cols = []
            for col in columns:
                if col == 'ts': db_cols.append(ts_col)
                elif col == 'code': db_cols.append(code_col)
                else: db_cols.append(col)
            
            # Ensure mandatory cols
            if ts_col not in db_cols: db_cols.append(ts_col)
            if code_col not in db_cols: db_cols.append(code_col)
            
            select_cols = ",".join(db_cols)
            
        sql = f"SELECT {select_cols} FROM {table_name} WHERE {where_sql} ORDER BY {ts_col}, {code_col}"
        
        try:
            df = self.questdb.query(sql)
            if not df.is_empty():
                # Rename to unified schema
                rename_map = {}
                if ts_col in df.columns: rename_map[ts_col] = 'ts'
                if code_col in df.columns: rename_map[code_col] = 'code'
                df = df.rename(rename_map)
            return df
        except Exception as e:
            # print(f"Error querying QuestDB ({table_name}): {e}") # Reduce noise
            return pl.DataFrame()

    def _query_cold(self,
                    table_name: str, 
                    codes: Optional[List[str]], 
                    start: str, 
                    end: str,
                    columns: Optional[List[str]] = None) -> pl.DataFrame:
        """Query Parquet Archive"""
        file_path = self.cold_files.get(table_name)
        if not file_path or not os.path.exists(file_path):
            print(f"Cold data file not found: {file_path}")
            return pl.DataFrame()
            
        try:
            # Lazy Scan
            lz = pl.scan_parquet(file_path)
            schema = lz.collect_schema()
            
            # Detect Column Names
            ts_col = 'trade_date' if 'trade_date' in schema.names() else 'ts'
            code_col = 'stock_code' if 'stock_code' in schema.names() else 'code'
            
            # Filter Time
            lz = lz.filter(
                (pl.col(ts_col) >= start) & 
                (pl.col(ts_col) <= end)
            )
            
            # Filter Codes (Normalized)
            if codes:
                norm_codes = [self._normalize_code_for_cold(c) for c in codes]
                lz = lz.filter(pl.col(code_col).is_in(norm_codes))
            
            # Select Columns
            if columns:
                mapped_cols = []
                for c in columns:
                    if c == 'ts': mapped_cols.append(ts_col)
                    elif c == 'code': mapped_cols.append(code_col)
                    elif c in schema.names(): mapped_cols.append(c)
                
                # Ensure keys exist
                if ts_col not in mapped_cols: mapped_cols.append(ts_col)
                if code_col not in mapped_cols: mapped_cols.append(code_col)
                
                lz = lz.select(mapped_cols)
            
            # Rename to standard
            rename_map = {}
            if ts_col != 'ts': rename_map[ts_col] = 'ts'
            if code_col != 'code': rename_map[code_col] = 'code'
            
            if rename_map:
                lz = lz.rename(rename_map)
            
            # Normalize codes back to standard format in result?
            # Ideally yes, but that's expensive. The user asked for specific codes, they know.
            # But "1" -> "000001.SZ" mapping is hard without a map.
            # For now, return what is in the file.
                
            return lz.collect().sort(["ts", "code"])
            
        except Exception as e:
            print(f"Error querying Cold Data ({table_name}): {e}")
            return pl.DataFrame()

# Singleton
_instance: Optional[UnifiedDataManager] = None

def get_unified_data_manager() -> UnifiedDataManager:
    global _instance
    if _instance is None:
        _instance = UnifiedDataManager()
    return _instance
