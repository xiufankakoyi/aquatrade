"""
统一股票数据更新脚本

功能：
1. 同时更新股票日线数据和指数数据
2. 自动计算技术指标（MA、成交量MA等）
3. 支持增量更新和全量更新
4. 自动处理Tushare频率限制

使用示例:
    python sandbox/update_all_stock_data.py                    # 增量更新
    python sandbox/update_all_stock_data.py --full-update      # 全量更新
    python sandbox/update_all_stock_data.py --start-date 20250101 --end-date 20260213
    python sandbox/update_all_stock_data.py --skip-benchmark   # 只更新股票数据
    python sandbox/update_all_stock_data.py --skip-stock       # 只更新指数数据
"""
import os
import sys
import time
import argparse
from datetime import datetime, date, timedelta
from typing import Optional, Set, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field

import pandas as pd
import polars as pl
import numpy as np
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
class UpdateResult:
    """更新结果"""
    success: bool
    message: str
    stock_dates_updated: int = 0
    stock_records_added: int = 0
    benchmark_dates_updated: int = 0
    benchmark_records_added: int = 0
    errors: List[str] = field(default_factory=list)


class TushareRateLimiter:
    """
    Tushare API 频率限制器
    处理不同接口的频率限制
    """
    RATE_LIMITS = {
        'daily': 80,
        'daily_basic': 80,
        'adj_factor': 80,
        'trade_cal': 500,
        'stock_basic': 500,
        'index_daily': 80,
    }

    def __init__(self):
        self.last_call_time: Dict[str, float] = {}
        self.call_counts: Dict[str, int] = {}
        self.minute_start: Dict[str, float] = {}

    def wait_if_needed(self, api_name: str):
        """检查是否需要等待以遵守频率限制"""
        now = time.time()
        limit = self.RATE_LIMITS.get(api_name, 80)

        if api_name not in self.minute_start:
            self.minute_start[api_name] = now
            self.call_counts[api_name] = 0

        elapsed = now - self.minute_start[api_name]
        if elapsed >= 60:
            self.minute_start[api_name] = now
            self.call_counts[api_name] = 0

        self.call_counts[api_name] += 1
        if self.call_counts[api_name] > limit:
            sleep_time = 60 - elapsed + 1
            logger.warning(f"[{api_name}] 达到频率限制({limit}/min)，等待 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)
            self.minute_start[api_name] = time.time()
            self.call_counts[api_name] = 1

        if api_name in self.last_call_time:
            time_since_last = now - self.last_call_time[api_name]
            min_interval = 60.0 / limit
            if time_since_last < min_interval:
                time.sleep(min_interval - time_since_last)

        self.last_call_time[api_name] = time.time()


class StockDataUpdater:
    """
    统一股票数据更新器
    同时处理股票数据和指数数据
    """

    # Parquet文件路径
    PARQUET_STOCK = "stock_daily.parquet"
    PARQUET_BENCHMARK = "benchmark_daily.parquet"

    # 基准指数代码
    BENCHMARK_CODES = {
        '000001.SH': '上证指数',
        '399001.SZ': '深证成指',
        '399006.SZ': '创业板指',
        '000300.SH': '沪深300',
        '000905.SH': '中证500',
        '000016.SH': '上证50',
    }

    def __init__(self, batch_size: int = 5):
        """
        初始化更新器

        Args:
            batch_size: 每批处理的日期数
        """
        self.token = Config.TUSHARE_TOKEN
        if not self.token:
            raise ValueError("TUSHARE_TOKEN 未配置，请在 .env 文件中设置")

        if not TUSHARE_AVAILABLE:
            raise ImportError("tushare 未安装，请运行: pip install tushare")

        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.batch_size = batch_size
        self.parquet_dir = Config.PARQUET_DIR
        self.stock_parquet_path = os.path.join(self.parquet_dir, self.PARQUET_STOCK)
        self.benchmark_parquet_path = os.path.join(self.parquet_dir, self.PARQUET_BENCHMARK)
        self.rate_limiter = TushareRateLimiter()

        os.makedirs(self.parquet_dir, exist_ok=True)

        logger.info(f"[StockDataUpdater] 初始化完成")
        logger.info(f"  股票数据: {self.stock_parquet_path}")
        logger.info(f"  指数数据: {self.benchmark_parquet_path}")

    def get_existing_dates(self, parquet_path: str) -> Set[str]:
        """获取Parquet文件中已有的所有日期"""
        if not os.path.exists(parquet_path):
            return set()

        try:
            df = pl.scan_parquet(parquet_path)
            dates = df.select("trade_date").unique().collect().to_series().to_list()

            result = set()
            for d in dates:
                if isinstance(d, str):
                    result.add(d.replace("-", ""))
                else:
                    result.add(pd.to_datetime(d).strftime("%Y%m%d"))

            return result
        except Exception as e:
            logger.error(f"读取Parquet日期列表失败: {e}")
            return set()

    def get_all_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """从Tushare获取指定范围内的所有交易日"""
        logger.info(f"获取交易日历: {start_date} ~ {end_date}")

        try:
            self.rate_limiter.wait_if_needed('trade_cal')
            cal = self.pro.trade_cal(exchange='', start_date=start_date, end_date=end_date)
            trade_dates = cal[cal['is_open'] == 1]['cal_date'].tolist()
            logger.info(f"找到 {len(trade_dates)} 个交易日")
            return trade_dates
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return []

    def fetch_stock_daily_data(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取指定日期的股票日线数据"""
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
                    df_daily, df_basic,
                    on=['ts_code', 'trade_date'], how='left'
                )

            if df_adj is not None and not df_adj.empty:
                df_daily = pd.merge(
                    df_daily, df_adj[['ts_code', 'trade_date', 'adj_factor']],
                    on=['ts_code', 'trade_date'], how='left'
                )

            logger.info(f"[{trade_date}] 获取 {len(df_daily)} 条股票记录")
            return df_daily

        except Exception as e:
            logger.error(f"[{trade_date}] 获取股票数据失败: {e}")
            return None

    def fetch_benchmark_data(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取指定日期的指数数据"""
        try:
            all_data = []
            for ts_code in self.BENCHMARK_CODES.keys():
                self.rate_limiter.wait_if_needed('index_daily')
                df = self.pro.index_daily(ts_code=ts_code, trade_date=trade_date)
                if df is not None and not df.empty:
                    all_data.append(df)

            if not all_data:
                logger.warning(f"[{trade_date}] 指数数据为空")
                return None

            df_combined = pd.concat(all_data, ignore_index=True)
            logger.info(f"[{trade_date}] 获取 {len(df_combined)} 条指数记录")
            return df_combined

        except Exception as e:
            logger.error(f"[{trade_date}] 获取指数数据失败: {e}")
            return None

    def _standardize_stock_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化股票数据列名和格式
        确保与Parquet文件结构一致
        """
        # 添加stock_code列
        df['stock_code'] = df['ts_code'].str.split('.', expand=True)[0]

        # 转换日期格式为 YYYY-MM-DD
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')

        # 重命名列以匹配Parquet格式
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

        # 确保数值类型正确
        numeric_cols = ['open', 'high', 'low', 'close', 'prev_close', 'change_amount',
                       'change_pct', 'volume', 'amount', 'adj_factor', 'turnover_rate',
                       'turnover_free', 'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps',
                       'ps_ttm', 'dividend_yield', 'dividend_yield_ttm', 'total_mv',
                       'float_mv', 'total_shares', 'float_shares', 'free_float_shares',
                       'limit_up', 'limit_down']

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        包括：MA均线、成交量MA、涨跌停价格
        """
        # 按股票代码分组计算
        def calc_for_stock(group):
            group = group.sort_values('trade_date')

            # 计算MA均线
            group['ma5'] = group['close'].rolling(window=5, min_periods=1).mean()
            group['ma10'] = group['close'].rolling(window=10, min_periods=1).mean()
            group['ma20'] = group['close'].rolling(window=20, min_periods=1).mean()

            # 计算成交量MA
            group['volume_ma5'] = group['volume'].rolling(window=5, min_periods=1).mean()

            # 计算均价MA
            group['ma3_avg_price'] = (group['amount'] / group['volume']).rolling(window=3, min_periods=1).mean()
            group['ma5_avg_price'] = (group['amount'] / group['volume']).rolling(window=5, min_periods=1).mean()
            group['ma10_avg_price'] = (group['amount'] / group['volume']).rolling(window=10, min_periods=1).mean()

            # 计算涨跌停价格
            prev_close = group['prev_close'].fillna(group['close'])

            # 根据板块判断涨跌幅限制
            def get_limit_ratio(stock_code):
                if pd.isna(stock_code):
                    return 0.1
                # ST股票
                if 'ST' in str(stock_code):
                    return 0.05
                # 科创板、创业板
                if str(stock_code).startswith(('688', '689', '300', '301')):
                    return 0.2
                return 0.1

            limit_ratios = group['stock_code'].apply(get_limit_ratio)
            group['limit_up'] = (prev_close * (1 + limit_ratios)).round(2)
            group['limit_down'] = (prev_close * (1 - limit_ratios)).round(2)

            return group

        df = df.groupby('stock_code', group_keys=False).apply(calc_for_stock)

        return df

    def _standardize_benchmark_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化指数数据列"""
        # 转换日期格式
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')

        # 添加指数名称
        df['name'] = df['ts_code'].map(self.BENCHMARK_CODES)

        # 重命名列
        column_mapping = {
            'pct_chg': 'change_pct',
            'change': 'change_amount',
            'pre_close': 'prev_close',
        }
        df.rename(columns=column_mapping, inplace=True)

        return df

    def _merge_with_existing(self, df_new: pd.DataFrame, parquet_path: str) -> pl.DataFrame:
        """将新数据与现有数据合并"""
        df_new_pl = pl.from_pandas(df_new)

        if not os.path.exists(parquet_path):
            logger.info("创建新的Parquet文件")
            return df_new_pl

        # 读取现有数据
        logger.info("读取现有数据...")
        df_existing = pl.scan_parquet(parquet_path)
        existing_schema = df_existing.collect_schema()
        existing_cols = set(existing_schema.names())
        new_cols = set(df_new_pl.columns)

        # 处理缺失列（添加空值）
        missing_cols = existing_cols - new_cols
        for col in missing_cols:
            df_new_pl = df_new_pl.with_columns(pl.lit(None).alias(col))
            logger.debug(f"添加缺失列: {col}")

        # 处理多余列（忽略）
        extra_cols = new_cols - existing_cols
        if extra_cols:
            logger.warning(f"新数据包含额外列 (将被忽略): {extra_cols}")

        # 选择相同列
        df_new_pl = df_new_pl.select(existing_schema.names())

        # 合并数据
        logger.info("合并数据...")
        df_combined = pl.concat([df_existing.collect(), df_new_pl])

        # 去重
        logger.info("去重...")
        if 'stock_code' in df_combined.columns:
            df_combined = df_combined.unique(subset=['stock_code', 'trade_date'], keep='last')
        else:
            df_combined = df_combined.unique(subset=['ts_code', 'trade_date'], keep='last')

        return df_combined

    def update_stock_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        batch_size: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        更新股票数据

        Returns:
            (更新的日期数, 添加的记录数)
        """
        if batch_size is None:
            batch_size = self.batch_size

        # 确定日期范围
        if start_date is None:
            existing_dates = self.get_existing_dates(self.stock_parquet_path)
            if existing_dates:
                last_date = max(existing_dates)
                start = datetime.strptime(last_date, "%Y%m%d") + timedelta(days=1)
                start_date = start.strftime("%Y%m%d")
            else:
                start_date = "20250101"

        if end_date is None:
            end_date = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

        logger.info(f"\n{'='*60}")
        logger.info("更新股票数据")
        logger.info(f"{'='*60}")
        logger.info(f"日期范围: {start_date} ~ {end_date}")

        # 获取需要更新的日期
        all_dates = self.get_all_trade_dates(start_date, end_date)
        existing_dates = self.get_existing_dates(self.stock_parquet_path)
        missing_dates = [d for d in all_dates if d not in existing_dates]

        if not missing_dates:
            logger.info("股票数据已是最新，无需更新")
            return 0, 0

        logger.info(f"需要更新 {len(missing_dates)} 个交易日")

        # 获取数据
        all_new_data = []
        for i, trade_date in enumerate(missing_dates):
            logger.info(f"[{i+1}/{len(missing_dates)}] 获取 {trade_date}...")
            df = self.fetch_stock_daily_data(trade_date)
            if df is not None and not df.empty:
                all_new_data.append(df)

            # 频率控制
            if (i + 1) % batch_size == 0:
                time.sleep(1)

        if not all_new_data:
            logger.warning("未能获取任何股票数据")
            return 0, 0

        # 处理数据
        logger.info("标准化数据...")
        df_all = pd.concat(all_new_data, ignore_index=True)
        df_all = self._standardize_stock_columns(df_all)

        # 计算技术指标
        logger.info("计算技术指标...")
        df_all = self._calculate_indicators(df_all)

        # 合并并保存
        logger.info("合并并保存...")
        df_combined = self._merge_with_existing(df_all, self.stock_parquet_path)
        df_combined.write_parquet(self.stock_parquet_path)

        logger.info(f"✅ 股票数据更新完成: {len(missing_dates)} 天, {len(df_all)} 条记录")
        return len(missing_dates), len(df_all)

    def update_benchmark_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        更新指数数据

        Returns:
            (更新的日期数, 添加的记录数)
        """
        # 确定日期范围
        if start_date is None:
            existing_dates = self.get_existing_dates(self.benchmark_parquet_path)
            if existing_dates:
                last_date = max(existing_dates)
                start = datetime.strptime(last_date, "%Y%m%d") + timedelta(days=1)
                start_date = start.strftime("%Y%m%d")
            else:
                start_date = "20250101"

        if end_date is None:
            end_date = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

        logger.info(f"\n{'='*60}")
        logger.info("更新指数数据")
        logger.info(f"{'='*60}")
        logger.info(f"日期范围: {start_date} ~ {end_date}")

        # 获取需要更新的日期
        all_dates = self.get_all_trade_dates(start_date, end_date)
        existing_dates = self.get_existing_dates(self.benchmark_parquet_path)
        missing_dates = [d for d in all_dates if d not in existing_dates]

        if not missing_dates:
            logger.info("指数数据已是最新，无需更新")
            return 0, 0

        logger.info(f"需要更新 {len(missing_dates)} 个交易日")

        # 获取数据
        all_new_data = []
        for i, trade_date in enumerate(missing_dates):
            logger.info(f"[{i+1}/{len(missing_dates)}] 获取 {trade_date}...")
            df = self.fetch_benchmark_data(trade_date)
            if df is not None and not df.empty:
                all_new_data.append(df)
            time.sleep(0.5)  # 频率控制

        if not all_new_data:
            logger.warning("未能获取任何指数数据")
            return 0, 0

        # 处理数据
        logger.info("标准化数据...")
        df_all = pd.concat(all_new_data, ignore_index=True)
        df_all = self._standardize_benchmark_columns(df_all)

        # 合并并保存
        logger.info("合并并保存...")
        df_combined = self._merge_with_existing(df_all, self.benchmark_parquet_path)
        df_combined.write_parquet(self.benchmark_parquet_path)

        logger.info(f"✅ 指数数据更新完成: {len(missing_dates)} 天, {len(df_all)} 条记录")
        return len(missing_dates), len(df_all)

    def run_update(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        batch_size: int = 5,
        skip_stock: bool = False,
        skip_benchmark: bool = False
    ) -> UpdateResult:
        """
        运行完整更新

        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            batch_size: 批次大小
            skip_stock: 是否跳过股票数据更新
            skip_benchmark: 是否跳过指数数据更新

        Returns:
            更新结果
        """
        result = UpdateResult(success=False, message="")

        try:
            print("\n" + "=" * 70)
            print("股票数据统一更新")
            print("=" * 70)
            print(f"股票数据路径: {self.stock_parquet_path}")
            print(f"指数数据路径: {self.benchmark_parquet_path}")
            print("=" * 70 + "\n")

            start_time = time.time()

            # 更新股票数据
            if not skip_stock:
                stock_dates, stock_records = self.update_stock_data(start_date, end_date, batch_size)
                result.stock_dates_updated = stock_dates
                result.stock_records_added = stock_records

            # 更新指数数据
            if not skip_benchmark:
                bench_dates, bench_records = self.update_benchmark_data(start_date, end_date)
                result.benchmark_dates_updated = bench_dates
                result.benchmark_records_added = bench_records

            elapsed = time.time() - start_time

            result.success = True
            result.message = (
                f"更新完成! 耗时: {elapsed:.1f}秒 | "
                f"股票: {result.stock_dates_updated}天/{result.stock_records_added}条 | "
                f"指数: {result.benchmark_dates_updated}天/{result.benchmark_records_added}条"
            )

            print("\n" + "=" * 70)
            print("✅ " + result.message)
            print("=" * 70 + "\n")

        except Exception as e:
            result.success = False
            result.message = f"更新失败: {str(e)}"
            logger.error(result.message)
            import traceback
            traceback.print_exc()

        return result


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='统一股票数据更新工具 - 同时更新股票和指数数据'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='开始日期 (YYYYMMDD格式，默认: 从已有数据后一天开始)'
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
    parser.add_argument(
        '--full-update',
        action='store_true',
        help='全量更新模式（从start-date开始更新所有数据）'
    )
    parser.add_argument(
        '--skip-stock',
        action='store_true',
        help='跳过股票数据更新'
    )
    parser.add_argument(
        '--skip-benchmark',
        action='store_true',
        help='跳过指数数据更新'
    )

    args = parser.parse_args()

    # 设置日志
    get_logger()

    # 创建更新器
    updater = StockDataUpdater(batch_size=args.batch_size)

    # 全量更新时，不检查已有数据
    if args.full_update and args.start_date:
        # 强制从指定日期开始
        pass
    elif args.full_update:
        args.start_date = "20250101"

    # 运行更新
    result = updater.run_update(
        start_date=args.start_date,
        end_date=args.end_date,
        batch_size=args.batch_size,
        skip_stock=args.skip_stock,
        skip_benchmark=args.skip_benchmark
    )

    # 退出码
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
