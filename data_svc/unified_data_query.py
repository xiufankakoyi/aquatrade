
import polars as pl
import pandas as pd
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import os

from data_svc.unified_data_manager import get_unified_data_manager
from config.config import Config

class UnifiedDataQueryAdapter:
    """
    Adapter to make UnifiedDataManager compatible with OptimizedStockDataQuery interface.
    Used by FlexibleBacktestEngine and BacktestVisualizationAPI.
    """
    
    def __init__(self, db_path: str = None):
        self.udm = get_unified_data_manager()
        self.db_path = db_path
        
        # Architecture flags for engine detection
        self._use_lancedb = False
        self._use_duckdb = False
        
        # Cache
        self._cache = {}
        self._preloaded_data_pl: Optional[pl.DataFrame] = None
        self._preloaded_date_range = None
        
        # Stock Info Cache
        self._stock_info_df: Optional[pd.DataFrame] = None
        
    def get_trading_dates(self, start_date=None, end_date=None) -> List[str]:
        return self.udm.get_trading_dates(start_date, end_date)
        
    def get_prev_trade_date(self, date: str) -> Optional[str]:
        return self.udm.get_prev_trade_date(date)
        
    def get_next_trade_date(self, date: str) -> Optional[str]:
        return self.udm.get_next_trade_date(date)
        
    def is_trading_day(self, date: str) -> bool:
        # Check if date is in trading calendar
        # Optimization: Check cache first? 
        # For check, querying UDM might be slow if it queries DB.
        # But UDM caches dates.
        dates = self.udm.get_trading_dates(start_date=date, end_date=date)
        return len(dates) > 0

    def preload_backtest_data(self, start_date: str, end_date: str):
        """Preload data into one big Polars DataFrame"""
        print(f"[UnifiedAdapter] Preloading data from {start_date} to {end_date}...")
        try:
            # 1. Get Price Data
            # Note: We need ALL stocks. codes=None means all.
            # UDM returns (ts, code) sorted pl.DataFrame
            df = self.udm.get_price(codes=None, start_date=start_date, end_date=end_date)
            
            # 2. Rename 'ts' to 'trade_date', 'code' to 'stock_code' to match Engine expectations?
            # FlexibleBacktestEngine uses what columns?
            # It accesses row dictionary keys. 
            # If I look at `cleaner.py` results: stock_code, trade_date...
            # QuestDB returns ts, code.
            # I should rename here or in UDM. UDM returns `ts`, `code`.
            # Engine likely expects `stock_code` (based on `current_day_data_dict = stock_pool.set_index('stock_code')...`)
            # And `trade_date`? Engine iterates `time_series`.
            
            mapping = {"ts": "trade_date", "code": "stock_code"}
            rename_ops = {}
            for k, v in mapping.items():
                if k in df.columns:
                    rename_ops[k] = v
            
            if rename_ops:
                df = df.rename(rename_ops)
                
            self._preloaded_data_pl = df
            self._preloaded_date_range = (start_date, end_date)
            print(f"[UnifiedAdapter] Preloaded {len(df)} rows.")
            
        except Exception as e:
            print(f"[UnifiedAdapter] Preload failed: {e}")
            self._preloaded_data_pl = None

    def get_stock_pool_pl(self, date: str) -> Optional[pl.DataFrame]:
        """Get Polars DataFrame for a specific date"""
        # 1. Try preloaded data
        if self._preloaded_data_pl is not None:
             # Fast filter on 'trade_date' (was 'ts')
             # Start/End date check? Engine ensures date is within range usually.
             
             # Polars filtering on string date column
             # Ensure date format matches (YYYY-MM-DD usually)
             try:
                 # Assume trade_date is string YYYY-MM-DD or datetime
                 # UDM returns what? QuestDB returns ISO string or timestamp?
                 # My test script showed "2021-01-08" style strings if I parsed them?
                 # No, QuestDB returns `timestamp` as string if querying via HTTP API, but if UDM processes it...
                 # UDM `_query_hot` returns whatever QuestDB returns.
                 # Let's verify UDM output type in get_stock_pool_pl.
                 
                 # If preloaded, filter:
                 return self._preloaded_data_pl.filter(pl.col("trade_date") == date)
             except Exception as e:
                 print(f"Error filtering preloaded data: {e}")
                 return None
                 
        # 2. Fallback: Query UDM hot/cold for single day
        # Slow but works
        df = self.udm.get_price(codes=None, start_date=date, end_date=date)
        if not df.is_empty():
            df = df.rename({"ts": "trade_date", "code": "stock_code"})
        return df

    def get_stock_history(self, code: str, start_date: str, end_date: str, columns: List[str] = None) -> pd.DataFrame:
        """Get history for single stock (Pandas)"""
        # UDM get_price returns Polars
        # Map renamed columns back if needed for UDM input (UDM expects generic)
        # UDM `get_price` takes generic args.
        
        # Handle column names: UDM output has 'ts', 'code'.
        # Caller expects 'trade_date', 'stock_code'.
        # Input `columns` might contain 'trade_date'.
        
        # Translate requested columns
        udm_cols = None
        if columns:
            udm_cols = []
            for c in columns:
                if c == 'trade_date': udm_cols.append('ts')
                elif c == 'stock_code': udm_cols.append('code')
                else: udm_cols.append(c)
        
        df_pl = self.udm.get_price([code], start_date, end_date, fields=udm_cols)
        
        if df_pl.is_empty():
            return pd.DataFrame()
            
        # Rename output
        df_pl = df_pl.rename({"ts": "trade_date", "code": "stock_code"})
        return df_pl.to_pandas()

    def get_latest_daily(self, code: str, target_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get latest daily data for a stock as a dictionary.
        Replaces raw SQL query: SELECT ... ORDER BY trade_date DESC LIMIT 1
        """
        end = target_date if target_date else datetime.now().strftime("%Y-%m-%d")
        
        # Look back 365 days to ensure we find data even if suspended
        try:
            start_dt = datetime.strptime(end, "%Y-%m-%d") - pd.Timedelta(days=365)
            start = start_dt.strftime("%Y-%m-%d")
        except:
            start = "2020-01-01"
            
        # UDM get_price returns sorted by ts ASC
        df_pl = self.udm.get_price([code], start_date=start, end_date=end)
        
        if df_pl.is_empty():
            return None
            
        # Get last row
        last_row = df_pl.tail(1).to_dicts()[0]
        
        # Rename to match legacy schema expectations
        # UDM returns 'ts', 'code'. API expects 'trade_date', 'stock_code' + 'open', 'close', 'prev_close', 'adj_factor'
        if 'ts' in last_row: last_row['trade_date'] = last_row['ts']
        if 'code' in last_row: last_row['stock_code'] = last_row['code']
        
        return last_row

    # --- Legacy / Internal calls from Visualization API ---
    
    def _query_df(self, sql: str, params: Optional[List] = None) -> pd.DataFrame:
        """
        Handle raw SQL queries from API.
        This is a hack to support legacy API calls without rewriting everything.
        """
        sql_lower = sql.lower()
        
        # 1. stock_info query
        if "stock_info" in sql_lower:
            return self._get_stock_info_df()
            
        # 2. benchmark_data query (used in _get_benchmark_data_from_db)
        if "benchmark_data" in sql_lower:
            # Parse simple WHERE clause? 
            # Or just delegate to UDM? 
            # API calls: SELECT date, close FROM benchmark_data WHERE code=? AND date>=? ...
            # I can implement this by loading benchmark parquet.
            return self._query_benchmark(sql, params)
            
        # 3. get_latest_prices calls stock_daily directly
        if "stock_daily" in sql_lower and "adj_factor" in sql_lower and "limit 1" in sql_lower:
             # This is likely `_get_global_latest_factor` or `get_latest_prices`
             # Extract code?
             # It's safer to let API fail or rewrite API.
             # But if I *must* support it:
             pass
             
        print(f"[UnifiedAdapter] Warning: efficient raw SQL not supported: {sql[:50]}...")
        return pd.DataFrame()

    def _get_stock_info_df(self) -> pd.DataFrame:
        if self._stock_info_df is not None:
             return self._stock_info_df
             
        # Load from Parquet
        # Requires Config.PARQUET_DIR
        path = os.path.join(Config.PARQUET_DIR, "stock_info.parquet")
        if os.path.exists(path):
            self._stock_info_df = pd.read_parquet(path)
            return self._stock_info_df
        return pd.DataFrame()
        
    def _query_benchmark(self, sql, params) -> pd.DataFrame:
         # Load benchmark parquet
         path = os.path.join(Config.PARQUET_DIR, "benchmark_daily.parquet")
         if not os.path.exists(path): return pd.DataFrame()
         
         df = pl.read_parquet(path).to_pandas()
         # Filter if needed (naive)
         # Params usually [code, start, end]
         if params and len(params) >= 3:
             code, start, end = params[0], params[1], params[2]
             df = df[(df['code'] == code) & (df['date'] >= start) & (df['date'] <= end)]
             
         return df

    def close(self):
        pass
