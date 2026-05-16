"""
补全benchmark数据脚本

功能：
1. 检查benchmark_daily.parquet中缺失的交易日
2. 从Tushare获取缺失的指数数据（沪深300、上证50等）
3. 合并到benchmark_daily.parquet文件

使用示例:
    python sandbox/fill_missing_benchmark_data.py
"""
import os
import sys
import time
import argparse
from datetime import datetime, date, timedelta
from typing import Optional, Set, List, Dict, Any

import pandas as pd
import polars as pl
from loguru import logger

# 添加项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.config import Config

# 尝试导入tushare
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None


class TushareRateLimiter:
    """Tushare API 频率限制器"""

    RATE_LIMITS = {
        'index_daily': 80,
        'trade_cal': 500,
    }

    def __init__(self):
        self.last_call_time: Dict[str, float] = {}
        self.call_counts: Dict[str, int] = {}
        self.minute_start: Dict[str, float] = {}

    def wait_if_needed(self, api_name: str):
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


class BenchmarkDataFiller:
    """Benchmark数据补全器"""

    # 主要指数代码
    INDEX_CODES = {
        '000001.SH': '上证指数',
        '000300.SH': '沪深300',
        '000016.SH': '上证50',
        '000905.SH': '中证500',
        '399001.SZ': '深证成指',
        '399006.SZ': '创业板指',
    }

    def __init__(self):
        self.token = Config.TUSHARE_TOKEN
        if not self.token:
            raise ValueError("TUSHARE_TOKEN 未配置")

        if not TUSHARE_AVAILABLE:
            raise ImportError("tushare 未安装")

        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.rate_limiter = TushareRateLimiter()
        self.parquet_path = os.path.join(Config.PARQUET_DIR, "benchmark_daily.parquet")

    def get_existing_dates(self) -> Set[str]:
        """获取已有日期"""
        if not os.path.exists(self.parquet_path):
            return set()

        try:
            df = pl.scan_parquet(self.parquet_path)
            dates = df.select("date").unique().collect().to_series().to_list()
            return set(str(d) for d in dates)
        except Exception as e:
            logger.error(f"读取benchmark日期失败: {e}")
            return set()

    def get_all_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日历"""
        try:
            self.rate_limiter.wait_if_needed('trade_cal')
            cal = self.pro.trade_cal(exchange='', start_date=start_date, end_date=end_date)
            return cal[cal['is_open'] == 1]['cal_date'].tolist()
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return []

    def fetch_index_data(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取指数数据"""
        all_data = []

        for ts_code, name in self.INDEX_CODES.items():
            try:
                self.rate_limiter.wait_if_needed('index_daily')
                df = self.pro.index_daily(ts_code=ts_code, trade_date=trade_date)

                if df is not None and not df.empty:
                    df['name'] = name
                    all_data.append(df[['ts_code', 'trade_date', 'close', 'name']])

            except Exception as e:
                logger.warning(f"[{trade_date}] 获取 {name} 失败: {e}")

        if not all_data:
            return None

        return pd.concat(all_data, ignore_index=True)

    def fill_missing_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """补全缺失数据"""
        print("=" * 60)
        print("补全Benchmark数据")
        print("=" * 60)

        # 确定日期范围
        if start_date is None:
            # 从已有数据的最后一天开始
            existing_dates = self.get_existing_dates()
            if existing_dates:
                last_date = max(existing_dates)
                start = datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)
                start_date = start.strftime("%Y%m%d")
            else:
                start_date = "20250101"

        if end_date is None:
            end_date = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

        print(f"\n日期范围: {start_date} ~ {end_date}")

        # 获取缺失日期
        all_dates = self.get_all_trade_dates(start_date, end_date)
        existing_dates = self.get_existing_dates()
        missing_dates = [d for d in all_dates if d not in existing_dates]

        print(f"已有日期: {len(existing_dates)} 个")
        print(f"需要补全: {len(missing_dates)} 个交易日")

        if not missing_dates:
            print("\n✅ 数据已完整，无需补全")
            return True

        # 获取数据
        all_new_data = []
        for i, trade_date in enumerate(missing_dates):
            print(f"\n[{i+1}/{len(missing_dates)}] 获取 {trade_date}...")
            df = self.fetch_index_data(trade_date)
            if df is not None and not df.empty:
                all_new_data.append(df)
                print(f"  ✓ 获取 {len(df)} 条记录")
            else:
                print(f"  ⚠️ 无数据")

            time.sleep(0.5)

        if not all_new_data:
            print("\n❌ 未能获取任何新数据")
            return False

        # 处理数据
        print("\n处理数据...")
        df_all = pd.concat(all_new_data, ignore_index=True)
        df_all['trade_date'] = pd.to_datetime(df_all['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        df_all = df_all.rename(columns={'trade_date': 'date', 'ts_code': 'code'})

        # 合并
        print("合并到现有数据...")
        df_new_pl = pl.from_pandas(df_all[['date', 'code', 'close']])

        if os.path.exists(self.parquet_path):
            df_existing = pl.read_parquet(self.parquet_path)
            df_combined = pl.concat([df_existing, df_new_pl])
            # 去重
            df_combined = df_combined.unique(subset=['date', 'code'], keep='last')
        else:
            df_combined = df_new_pl

        # 保存
        print("保存...")
        df_combined.write_parquet(self.parquet_path)

        print(f"\n✅ 补全完成!")
        print(f"  新增记录: {len(df_all)}")
        print(f"  合并后总记录: {len(df_combined)}")

        return True


def main():
    parser = argparse.ArgumentParser(description='补全Benchmark数据')
    parser.add_argument('--start-date', type=str, help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (YYYYMMDD)')

    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    filler = BenchmarkDataFiller()
    success = filler.fill_missing_data(args.start_date, args.end_date)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
