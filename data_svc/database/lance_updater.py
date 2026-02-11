"""
LanceDB 数据更新器 (data_svc/database/lance_updater.py)
整合 Tushare API 与 LanceDB，实现增量同步并在更新过程中报告进度。
"""
import os
import time
import datetime
from typing import Optional, Callable, Dict, Any, List
import pandas as pd
import tushare as ts
from config.config import Config
from config.logger import get_logger
from data_svc.lance_manager import LanceDBManager

logger = get_logger(__name__)

class LanceDBUpdater:
    def __init__(self, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        初始化更新器
        :param progress_callback: 进度回调函数，接收 Dict 包含 status, percentage, message 等
        """
        self.token = Config.TUSHARE_TOKEN
        if not self.token:
            raise ValueError("TUSHARE_TOKEN is missing in config.")
        
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.manager = LanceDBManager(table_name="stock_daily")
        self.progress_callback = progress_callback

    def report_progress(self, status: str, progress: float, message: str):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback({
                "status": status,
                "progress": progress,
                "message": message,
                "timestamp": time.time()
            })
        logger.info(f"[{status}] {progress}% - {message}")

    def get_update_days(self) -> List[str]:
        """获取需要更新的日期列表"""
        # 1. 获取 LanceDB 中最后一条数据的日期
        info = self.manager.get_table_info()
        if not info.get("exists") or info.get("rows", 0) == 0:
            # 如果没有数据，默认从 2024-01-01 开始 (作为示例，实际可由用户指定)
            last_date_str = "20240101"
        else:
            # 这是一个简化的获取最后日期的方法，LanceDB 建议通过查询获取
            try:
                # 查询最新的一条记录来获取日期
                df_last = self.manager.load_to_polars(
                    columns=["trade_date"], 
                    use_lazy=True
                ).sort("trade_date", descending=True).limit(1).collect()
                if len(df_last) > 0:
                    last_date_str = df_last["trade_date"][0].replace("-", "")
                else:
                    last_date_str = "20240101"
            except Exception as e:
                logger.error(f"Failed to get last date: {e}")
                last_date_str = "20240101"

        # 2. 获取 Tushare 交易日历
        today_str = datetime.date.today().strftime('%Y%m%d')
        start_date = (pd.to_datetime(last_date_str) + datetime.timedelta(days=1)).strftime('%Y%m%d')
        
        if start_date > today_str:
            return []

        cal = self.pro.trade_cal(exchange='', start_date=start_date, end_date=today_str)
        update_days = cal[cal['is_open'] == 1]['cal_date'].tolist()
        return update_days

    def run_sync(self):
        """运行同步过程"""
        try:
            self.report_progress("STARTING", 0, "开始同步 Tushare 数据...")
            
            update_days = self.get_update_days()
            if not update_days:
                self.report_progress("COMPLETED", 100, "数据已是最新，无需更新。")
                return True, "Already up to date"

            total_days = len(update_days)
            self.report_progress("FETCHING", 5, f"检测到 {total_days} 个交易日需要更新")

            for i, date_str in enumerate(update_days):
                progress_val = 5 + (i / total_days) * 90
                self.report_progress("UPDATING", progress_val, f"正在抓取 {date_str} 数据...")
                
                # 抓取日线行情
                df_daily = self.pro.daily(trade_date=date_str)
                if df_daily.empty:
                    continue
                
                # 抓取基本面数据 (PE, PB, 市值等)
                df_basic = self.pro.daily_basic(trade_date=date_str)
                
                # 合并数据
                df_merge = pd.merge(df_daily, df_basic[['ts_code', 'trade_date', 'turnover_rate', 'total_mv', 'circ_mv', 'pe', 'pb']], 
                                    on=['ts_code', 'trade_date'], how='left')
                
                # 格式化
                df_merge['stock_code'] = df_merge['ts_code'].str.split('.', expand=True)[0]
                df_merge['trade_date'] = pd.to_datetime(df_merge['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                
                # 重命名列以匹配 schema
                df_merge.rename(columns={
                    'vol': 'volume',
                    'pct_chg': 'change_pct',
                    'pre_close': 'prev_close',
                    'circ_mv': 'float_mv'
                }, inplace=True)
                
                # 写入到 LanceDB
                self.manager.upsert_daily_data(df_merge)
                
                # 限制频率 (Tushare 免费版限制)
                if total_days > 1:
                    time.sleep(0.5)

            self.report_progress("COMPLETED", 100, f"同步完成，共更新 {total_days} 个交易日。")
            return True, f"Updated {total_days} days"

        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            self.report_progress("FAILED", 0, f"同步失败: {str(e)}")
            return False, str(e)

if __name__ == "__main__":
    updater = LanceDBUpdater()
    updater.run_sync()
