"""
股票数据补全脚本

功能：
1. 检查Parquet文件中2025年至今缺失的交易日
2. 从Tushare获取缺失日期的数据
3. 合并到Parquet文件

使用示例:
    python sandbox/fill_missing_stock_data.py
    python sandbox/fill_missing_stock_data.py --start-date 2025-01-01 --end-date 2025-06-30
"""
import os
import sys
import time
import argparse
from datetime import datetime, date, timedelta
from typing import Optional, Set, List, Dict, Any, Callable
from dataclasses import dataclass

import pandas as pd
import polars as pl
from loguru import logger

# 添加项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.config import Config
from config.logger import get_logger

# 尝试导入tushare
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    message: str
    missing_dates: List[str]
    fetched_records: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class TushareRateLimiter:
    """
    Tushare API 频率限制器

    处理不同接口的频率限制：
    - daily: 每分钟80次
    - daily_basic: 每分钟80次
    - adj_factor: 每分钟80次
    - trade_cal: 每分钟500次
    """

    # 各接口的频率限制（次/分钟）
    RATE_LIMITS = {
        'daily': 80,
        'daily_basic': 80,
        'adj_factor': 80,
        'trade_cal': 500,
        'stock_basic': 500,
    }

    def __init__(self):
        self.last_call_time: Dict[str, float] = {}
        self.call_counts: Dict[str, int] = {}
        self.minute_start: Dict[str, float] = {}

    def wait_if_needed(self, api_name: str):
        """
        检查是否需要等待以遵守频率限制

        Args:
            api_name: API接口名称
        """
        now = time.time()
        limit = self.RATE_LIMITS.get(api_name, 80)

        # 初始化该API的统计
        if api_name not in self.minute_start:
            self.minute_start[api_name] = now
            self.call_counts[api_name] = 0

        # 检查是否超过一分钟窗口
        elapsed = now - self.minute_start[api_name]
        if elapsed >= 60:
            # 重置计数器
            self.minute_start[api_name] = now
            self.call_counts[api_name] = 0

        # 检查是否达到限制
        self.call_counts[api_name] += 1
        if self.call_counts[api_name] > limit:
            # 需要等待到下一分钟
            sleep_time = 60 - elapsed + 1  # 多等1秒确保安全
            logger.warning(f"[{api_name}] 达到频率限制({limit}/min)，等待 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)
            # 重置
            self.minute_start[api_name] = time.time()
            self.call_counts[api_name] = 1

        # 基础延迟，避免请求过快
        if api_name in self.last_call_time:
            time_since_last = now - self.last_call_time[api_name]
            min_interval = 60.0 / limit  # 每次请求的最小间隔
            if time_since_last < min_interval:
                time.sleep(min_interval - time_since_last)

        self.last_call_time[api_name] = time.time()


class StockDataFiller:
    """
    股票数据补全器

    功能：
    1. 分析Parquet文件中缺失的交易日
    2. 从Tushare获取缺失数据
    3. 合并并保存到Parquet文件
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        batch_size: int = 5  # 每批处理的日期数
    ):
        """
        初始化数据补全器

        Args:
            progress_callback: 进度回调函数
            batch_size: 每批处理的日期数，避免单次请求过多
        """
        self.token = Config.TUSHARE_TOKEN
        if not self.token:
            raise ValueError("TUSHARE_TOKEN 未配置，请在 .env 文件中设置")

        if not TUSHARE_AVAILABLE:
            raise ImportError("tushare 未安装，请运行: pip install tushare")

        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.progress_callback = progress_callback
        self.batch_size = batch_size
        self.parquet_dir = Config.PARQUET_DIR
        self.parquet_path = os.path.join(self.parquet_dir, "stock_daily.parquet")
        self.rate_limiter = TushareRateLimiter()

        # 确保目录存在
        os.makedirs(self.parquet_dir, exist_ok=True)

        logger.info(f"[StockDataFiller] 初始化完成，Parquet路径: {self.parquet_path}")

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

    def get_existing_dates(self) -> Set[str]:
        """
        获取Parquet文件中已有的所有交易日期

        Returns:
            已有交易日期的集合，格式为 YYYYMMDD
        """
        if not os.path.exists(self.parquet_path):
            logger.warning(f"Parquet文件不存在: {self.parquet_path}")
            return set()

        try:
            logger.info("[StockDataFiller] 读取现有数据日期...")
            df = pl.scan_parquet(self.parquet_path)
            dates = df.select("trade_date").unique().collect().to_series().to_list()

            # 统一转换为YYYYMMDD格式
            result = set()
            for d in dates:
                if isinstance(d, str):
                    result.add(d.replace("-", ""))
                else:
                    result.add(pd.to_datetime(d).strftime("%Y%m%d"))

            logger.info(f"[StockDataFiller] 现有数据包含 {len(result)} 个交易日")
            return result

        except Exception as e:
            logger.error(f"读取Parquet日期列表失败: {e}")
            return set()

    def get_all_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        从Tushare获取指定范围内的所有交易日

        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            交易日列表 (YYYYMMDD)
        """
        logger.info(f"[StockDataFiller] 获取交易日历: {start_date} ~ {end_date}")

        try:
            self.rate_limiter.wait_if_needed('trade_cal')
            cal = self.pro.trade_cal(exchange='', start_date=start_date, end_date=end_date)
            trade_dates = cal[cal['is_open'] == 1]['cal_date'].tolist()
            logger.info(f"[StockDataFiller] 找到 {len(trade_dates)} 个交易日")
            return trade_dates
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return []

    def find_missing_dates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[str]:
        """
        找出缺失的交易日

        Args:
            start_date: 开始日期 (YYYYMMDD)，默认2025-01-01
            end_date: 结束日期 (YYYYMMDD)，默认昨天

        Returns:
            缺失的交易日列表
        """
        # 默认范围：2025年至今
        if start_date is None:
            start_date = "20250101"
        if end_date is None:
            yesterday = date.today() - timedelta(days=1)
            end_date = yesterday.strftime("%Y%m%d")

        logger.info(f"[StockDataFiller] 检查缺失日期范围: {start_date} ~ {end_date}")

        # 获取所有交易日
        all_trade_dates = self.get_all_trade_dates(start_date, end_date)
        if not all_trade_dates:
            return []

        # 获取已有日期
        existing_dates = self.get_existing_dates()

        # 找出缺失的日期
        missing_dates = [d for d in all_trade_dates if d not in existing_dates]

        logger.info(f"[StockDataFiller] 缺失 {len(missing_dates)} 个交易日")
        if missing_dates:
            logger.info(f"[StockDataFiller] 缺失日期: {missing_dates[:10]}...")  # 只显示前10个

        return missing_dates

    def fetch_daily_data(self, trade_date: str) -> Optional[pd.DataFrame]:
        """
        获取指定日期的日线数据

        Args:
            trade_date: 交易日期 (YYYYMMDD)

        Returns:
            包含日线数据的DataFrame，失败返回None
        """
        try:
            # 获取日线数据
            self.rate_limiter.wait_if_needed('daily')
            df_daily = self.pro.daily(trade_date=trade_date)
            if df_daily is None or df_daily.empty:
                logger.warning(f"[{trade_date}] 日线数据为空")
                return None

            # 获取基本面数据
            self.rate_limiter.wait_if_needed('daily_basic')
            df_basic = self.pro.daily_basic(
                trade_date=trade_date,
                fields=[
                    'ts_code', 'trade_date', 'turnover_rate', 'turnover_rate_f',
                    'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm',
                    'dv_ratio', 'dv_ttm', 'total_mv', 'circ_mv',
                    'total_share', 'float_share', 'free_share'
                ]
            )

            # 获取复权因子
            self.rate_limiter.wait_if_needed('adj_factor')
            df_adj = self.pro.adj_factor(trade_date=trade_date)

            # 合并数据
            if df_basic is not None and not df_basic.empty:
                df_daily = pd.merge(
                    df_daily,
                    df_basic,
                    on=['ts_code', 'trade_date'],
                    how='left'
                )

            if df_adj is not None and not df_adj.empty:
                df_daily = pd.merge(
                    df_daily,
                    df_adj[['ts_code', 'trade_date', 'adj_factor']],
                    on=['ts_code', 'trade_date'],
                    how='left'
                )

            logger.info(f"[{trade_date}] 获取 {len(df_daily)} 条记录")
            return df_daily

        except Exception as e:
            logger.error(f"[{trade_date}] 获取数据失败: {e}")
            return None

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化列名和格式

        Args:
            df: 原始DataFrame

        Returns:
            标准化后的DataFrame
        """
        # 添加stock_code列
        df['stock_code'] = df['ts_code'].str.split('.', expand=True)[0]

        # 转换日期格式
        df['trade_date'] = pd.to_datetime(
            df['trade_date'],
            format='%Y%m%d'
        ).dt.strftime('%Y-%m-%d')

        # 重命名列
        column_mapping = {
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
        }
        df.rename(columns=column_mapping, inplace=True)

        return df

    def _merge_with_existing(self, df_new: pd.DataFrame) -> pl.DataFrame:
        """
        将新数据与现有数据合并

        Args:
            df_new: 新数据

        Returns:
            合并后的Polars DataFrame
        """
        df_new_pl = pl.from_pandas(df_new)

        if not os.path.exists(self.parquet_path):
            logger.info("[StockDataFiller] 创建新的Parquet文件")
            return df_new_pl

        # 读取现有数据
        logger.info("[StockDataFiller] 读取现有数据...")
        df_existing = pl.scan_parquet(self.parquet_path)
        existing_schema = df_existing.collect_schema()
        existing_cols = set(existing_schema.names())
        new_cols = set(df_new_pl.columns)

        # 处理缺失列
        missing_cols = existing_cols - new_cols
        for col in missing_cols:
            df_new_pl = df_new_pl.with_columns(pl.lit(None).alias(col))
            logger.debug(f"添加缺失列: {col}")

        # 处理多余列
        extra_cols = new_cols - existing_cols
        if extra_cols:
            logger.warning(f"新数据包含额外列 (将被忽略): {extra_cols}")

        # 选择相同列
        df_new_pl = df_new_pl.select(existing_schema.names())

        # 合并数据
        logger.info("[StockDataFiller] 合并数据...")
        df_combined = pl.concat([df_existing.collect(), df_new_pl])

        # 去重：保留最新数据
        logger.info("[StockDataFiller] 去重...")
        df_combined = df_combined.unique(
            subset=['stock_code', 'trade_date'],
            keep='last'
        )

        return df_combined

    def fill_missing_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> SyncResult:
        """
        补全缺失数据的主函数

        Args:
            start_date: 开始日期 (YYYYMMDD)，默认2025-01-01
            end_date: 结束日期 (YYYYMMDD)，默认昨天

        Returns:
            同步结果
        """
        result = SyncResult(success=False, message="", missing_dates=[])

        try:
            logger.info("=" * 60)
            logger.info("[StockDataFiller] 开始补全缺失数据")
            logger.info("=" * 60)

            self.report_progress("ANALYZING", 0, "分析缺失数据...")

            # 找出缺失日期
            missing_dates = self.find_missing_dates(start_date, end_date)
            result.missing_dates = missing_dates

            if not missing_dates:
                result.success = True
                result.message = "数据已完整，无需补全"
                self.report_progress("COMPLETED", 100, result.message)
                return result

            total_days = len(missing_dates)
            logger.info(f"[StockDataFiller] 需要补全 {total_days} 个交易日")

            all_new_data = []
            errors = []

            # 分批获取数据
            for i, trade_date in enumerate(missing_dates):
                progress = (i / total_days) * 90
                self.report_progress(
                    "FETCHING",
                    progress,
                    f"获取 {trade_date} 数据 ({i+1}/{total_days})"
                )

                df = self.fetch_daily_data(trade_date)
                if df is not None and not df.empty:
                    all_new_data.append(df)
                else:
                    errors.append(f"{trade_date}: 获取失败")

                # 每batch_size个日期后暂停一下，避免频率限制
                if (i + 1) % self.batch_size == 0:
                    time.sleep(1)

            if not all_new_data:
                result.success = False
                result.message = "未能获取任何新数据"
                result.errors = errors
                self.report_progress("FAILED", 0, result.message)
                return result

            # 合并所有新数据
            self.report_progress("PROCESSING", 90, "处理数据...")
            df_all = pd.concat(all_new_data, ignore_index=True)
            df_all = self._standardize_columns(df_all)

            # 与现有数据合并
            self.report_progress("MERGING", 95, "合并数据...")
            df_combined = self._merge_with_existing(df_all)

            # 保存
            self.report_progress("SAVING", 98, "保存到Parquet...")
            df_combined.write_parquet(self.parquet_path)

            result.success = True
            result.fetched_records = len(df_all)
            result.message = (
                f"补全完成: 获取 {total_days} 个交易日, "
                f"{len(df_all)} 条记录, "
                f"合并后共 {len(df_combined)} 条记录"
            )
            result.errors = errors

            self.report_progress("COMPLETED", 100, result.message)

            logger.info("=" * 60)
            logger.info(f"[StockDataFiller] {result.message}")
            logger.info("=" * 60)

            return result

        except Exception as e:
            error_msg = f"补全失败: {str(e)}"
            logger.error(error_msg)
            result.success = False
            result.message = error_msg
            self.report_progress("FAILED", 0, error_msg)
            return result


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='股票数据补全工具 - 补全Parquet文件中缺失的交易日数据'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='20250101',
        help='开始日期 (YYYYMMDD格式，默认: 20250101)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='结束日期 (YYYYMMDD格式，默认: 昨天)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='每批处理的日期数 (默认: 5)'
    )

    args = parser.parse_args()

    # 设置日志
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )

    # 创建补全器并运行
    filler = StockDataFiller(batch_size=args.batch_size)
    result = filler.fill_missing_data(
        start_date=args.start_date,
        end_date=args.end_date
    )

    # 输出结果
    print("\n" + "=" * 60)
    print("补全结果")
    print("=" * 60)
    print(f"状态: {'成功' if result.success else '失败'}")
    print(f"消息: {result.message}")
    print(f"缺失日期数: {len(result.missing_dates)}")
    print(f"获取记录数: {result.fetched_records}")
    if result.errors:
        print(f"错误数: {len(result.errors)}")
        print("错误详情:")
        for error in result.errors[:10]:  # 只显示前10个错误
            print(f"  - {error}")
    print("=" * 60)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
