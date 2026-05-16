"""
Parquet 数据更新器 (data_svc/database/parquet_updater.py)
从 Tushare 获取增量数据并更新到 Parquet 文件
"""
import os
import time
import datetime
from typing import Optional, Callable, Dict, Any, List
import pandas as pd
import polars as pl
from config.config import Config
from config.logger import get_logger

logger = get_logger(__name__)

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None


class ParquetUpdater:
    """
    Parquet 数据更新器
    
    从 Tushare 获取增量数据并追加到 Parquet 文件
    """
    
    def __init__(self, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.token = Config.TUSHARE_TOKEN
        if not self.token:
            raise ValueError("TUSHARE_TOKEN 未配置，请在 .env 文件中设置")
        
        if not TUSHARE_AVAILABLE:
            raise ImportError("tushare 未安装，请运行: pip install tushare")
        
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.progress_callback = progress_callback
        self.parquet_dir = Config.PARQUET_DIR
        
    def report_progress(self, status: str, progress: float, message: str):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback({
                "status": status,
                "progress": progress,
                "message": message,
                "timestamp": time.time()
            })
        logger.info(f"[{status}] {progress:.1f}% - {message}")
    
    def get_last_trade_date(self) -> str:
        """获取 Parquet 文件中最后的交易日期"""
        return self._get_last_date() or "20200101"

    def _get_last_date(self) -> Optional[str]:
        """
        获取 Parquet 文件中最后的交易日期
        
        Returns:
            最后交易日期的 YYYYMMDD 格式字符串，如果数据库为空则返回 None
        """
        parquet_path = os.path.join(self.parquet_dir, "stock_daily.parquet")
        
        if not os.path.exists(parquet_path):
            logger.warning(f"Parquet 文件不存在: {parquet_path}")
            return None
        
        try:
            df = pl.scan_parquet(parquet_path)
            last_date = df.select(pl.col("trade_date").max()).collect().item()
            
            if last_date is None:
                return None
            
            if isinstance(last_date, str):
                # 处理 YYYY-MM-DD 格式
                return last_date.replace("-", "")
            else:
                return pd.to_datetime(last_date).strftime("%Y%m%d")
                
        except Exception as e:
            logger.error(f"读取 Parquet 文件失败: {e}")
            return None

    def _get_existing_dates(self) -> set:
        """
        获取数据库中已有的所有交易日期
        
        Returns:
            已有交易日期的集合，格式为 YYYYMMDD
        """
        parquet_path = os.path.join(self.parquet_dir, "stock_daily.parquet")
        
        if not os.path.exists(parquet_path):
            return set()
        
        try:
            df = pl.scan_parquet(parquet_path)
            dates = df.select("trade_date").unique().collect().to_series().to_list()
            
            # 统一转换为 YYYYMMDD 格式
            result = set()
            for d in dates:
                if isinstance(d, str):
                    result.add(d.replace("-", ""))
                else:
                    result.add(pd.to_datetime(d).strftime("%Y%m%d"))
            return result
                
        except Exception as e:
            logger.error(f"读取 Parquet 日期列表失败: {e}")
            return set()
    
    def get_update_days(self) -> List[str]:
        """获取需要更新的交易日列表"""
        last_date_str = self.get_last_trade_date()
        today_str = datetime.date.today().strftime('%Y%m%d')
        
        logger.info(f"[ParquetUpdater] 最后更新日期: {last_date_str}, 今天: {today_str}")
        
        start_date = (pd.to_datetime(last_date_str) + datetime.timedelta(days=1)).strftime('%Y%m%d')
        
        logger.info(f"[ParquetUpdater] 计划从 {start_date} 更新到 {today_str}")
        
        if start_date > today_str:
            logger.info("[ParquetUpdater] 数据已是最新，无需更新")
            return []
        
        try:
            cal = self.pro.trade_cal(exchange='', start_date=start_date, end_date=today_str)
            update_days = cal[cal['is_open'] == 1]['cal_date'].tolist()
            logger.info(f"[ParquetUpdater] 需要更新的交易日: {update_days}")
            return update_days
        except Exception as e:
            logger.error(f"[ParquetUpdater] 获取交易日历失败: {e}", exc_info=True)
            return []
    
    def fetch_daily_data(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取指定日期的日线数据"""
        try:
            df_daily = self.pro.daily(trade_date=trade_date)
            if df_daily is None or df_daily.empty:
                return None
            
            df_basic = self.pro.daily_basic(trade_date=trade_date, fields=[
                'ts_code', 'trade_date', 'turnover_rate', 'turnover_rate_f',
                'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm',
                'dv_ratio', 'dv_ttm', 'total_mv', 'circ_mv',
                'total_share', 'float_share', 'free_share'
            ])
            df_adj = self.pro.adj_factor(trade_date=trade_date)
            
            if df_basic is not None and not df_basic.empty:
                df_daily = pd.merge(df_daily, df_basic, on=['ts_code', 'trade_date'], how='left')
            
            if df_adj is not None and not df_adj.empty:
                df_daily = pd.merge(df_daily, df_adj[['ts_code', 'trade_date', 'adj_factor']], on=['ts_code', 'trade_date'], how='left')
            
            return df_daily
            
        except Exception as e:
            logger.error(f"获取 {trade_date} 数据失败: {e}")
            return None
    
    def run_sync(self):
        """运行同步过程"""
        try:
            logger.info("[ParquetUpdater] ========== 开始数据同步 ==========")
            self.report_progress("STARTING", 0, "开始同步 Tushare 数据到 Parquet...")
            
            update_days = self.get_update_days()
            if not update_days:
                logger.info("[ParquetUpdater] 没有需要更新的交易日，任务结束")
                self.report_progress("COMPLETED", 100, "数据已是最新，无需更新。")
                return True, "Already up to date"
            
            total_days = len(update_days)
            self.report_progress("FETCHING", 5, f"检测到 {total_days} 个交易日需要更新")
            
            all_new_data = []
            
            for i, date_str in enumerate(update_days):
                progress_val = 5 + (i / total_days) * 90
                self.report_progress("UPDATING", progress_val, f"正在抓取 {date_str} 数据...")
                
                df = self.fetch_daily_data(date_str)
                if df is not None and not df.empty:
                    all_new_data.append(df)
                    logger.info(f"[OK] {date_str}: {len(df)} 条记录")
                
                time.sleep(0.3)
            
            if not all_new_data:
                self.report_progress("COMPLETED", 100, "没有获取到新数据")
                return True, "No new data"
            
            df_all = pd.concat(all_new_data, ignore_index=True)
            
            df_all['stock_code'] = df_all['ts_code'].str.split('.', expand=True)[0]
            df_all['trade_date'] = pd.to_datetime(df_all['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
            
            df_all.rename(columns={
                'vol': 'volume',
                'pct_chg': 'change_pct',
                'change': 'change_amount',
                'pre_close': 'prev_close',
                'circ_mv': 'float_mv',
                'turnover_rate_f': 'turnover_free',
                'dv_ratio': 'dividend_yield',
                'dv_ttm': 'dividend_yield_ttm',
                'total_share': 'total_shares',
                'float_share': 'float_shares',
                'free_share': 'free_float_shares'
            }, inplace=True)
            
            parquet_path = os.path.join(self.parquet_dir, "stock_daily.parquet")
            
            self.report_progress("WRITING", 95, f"正在写入 {len(df_all)} 条记录到 Parquet...")
            
            df_new_pl = pl.from_pandas(df_all)
            
            if os.path.exists(parquet_path):
                df_existing = pl.scan_parquet(parquet_path)
                existing_schema = df_existing.collect_schema()
                existing_cols = set(existing_schema.names())
                new_cols = set(df_new_pl.columns)
                
                missing_cols = existing_cols - new_cols
                for col in missing_cols:
                    df_new_pl = df_new_pl.with_columns(pl.lit(None).alias(col))
                
                extra_cols = new_cols - existing_cols
                if extra_cols:
                    logger.warning(f"新数据包含额外列 (将被忽略): {extra_cols}")
                
                df_new_pl = df_new_pl.select(existing_schema.names())
                
                df_combined = pl.concat([df_existing.collect(), df_new_pl])
                df_combined.write_parquet(parquet_path)
            else:
                df_new_pl.write_parquet(parquet_path)
            
            self.report_progress("COMPLETED", 100, f"同步完成，共更新 {total_days} 个交易日，{len(df_all)} 条记录。")
            return True, f"Updated {total_days} days, {len(df_all)} records"
            
        except Exception as e:
            logger.error(f"同步失败: {e}", exc_info=True)
            self.report_progress("FAILED", 0, f"同步失败: {str(e)}")
            return False, str(e)


if __name__ == "__main__":
    updater = ParquetUpdater()
    updater.run_sync()
