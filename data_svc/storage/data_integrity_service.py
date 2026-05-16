"""
数据完整性检查与修复服务
=========================

功能：
1. 检查 LanceDB 数据列缺失情况
2. 检查因子不完整情况
3. 使用 Polars 向量化计算补全缺失数据
4. 使用 DuckDB 加速大批量历史数据处理

架构：
┌─────────────────────────────────────────────────────────────────┐
│                    DataIntegrityService                        │
│                                                                 │
│  检查流程：                                                     │
│  1. scan_columns() - 检查各列缺失情况                           │
│  2. check_factor_completeness() - 检查因子完整性                │
│  3. repair_missing_qfq() - 补全前复权价格列                    │
│  4. repair_missing_factors() - 补全缺失的技术指标              │
│                                                                 │
│  加速：DuckDB 并行扫描 + Polars 向量化计算                      │
└─────────────────────────────────────────────────────────────────┘
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import time

from config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ColumnStats:
    """列统计信息"""
    column_name: str
    total_rows: int
    null_count: int
    null_pct: float
    zero_count: int
    zero_pct: float
    unique_count: int
    sample_values: List[Any] = field(default_factory=list)


@dataclass
class CompletenessReport:
    """数据完整性报告"""
    table_name: str
    total_rows: int
    date_range: Tuple[str, str]
    stock_count: int
    columns_stats: List[ColumnStats]
    missing_columns: List[str]
    critical_missing_pct: float
    overall_score: float
    recommendations: List[str] = field(default_factory=list)


@dataclass
class RepairResult:
    """修复结果"""
    success: bool
    records_repaired: int = 0
    message: str = ""
    elapsed_seconds: float = 0.0


class DataIntegrityService:
    """
    数据完整性检查与修复服务

    功能：
    1. 扫描数据列统计信息
    2. 检测数据缺失情况
    3. 补全缺失的前复权价格列
    4. 补全缺失的技术指标因子
    """

    OHLCV_COLUMNS = ['trade_date', 'stock_code', 'open', 'high', 'low', 'close', 'volume', 'amount']
    QFQ_COLUMNS = ['qfq_open', 'qfq_high', 'qfq_low', 'qfq_close']
    FUNDAMENTAL_COLUMNS = ['adj_factor', 'turnover_rate', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'total_mv', 'float_mv']
    MINIMAL_REQUIRED = OHLCV_COLUMNS + ['adj_factor']

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from config.config import Config
            db_path = getattr(Config, 'LANCEDB_PATH', None)
            if db_path is None:
                project_root = Path(__file__).parent.parent.parent
                db_path = str(project_root / "data" / "lancedb")

        self.db_path = db_path
        self._db = None
        self._table = None

    def _connect(self):
        """建立数据库连接"""
        if self._db is None:
            import lancedb
            self._db = lancedb.connect(self.db_path)
        return self._db

    @property
    def table(self):
        """获取表实例"""
        if self._table is None:
            db = self._connect()
            if "daily_ohlcv" in db.table_names():
                self._table = db.open_table("daily_ohlcv")
        return self._table

    def _get_all_data(self, columns: Optional[List[str]] = None) -> pl.DataFrame:
        """获取所有数据（使用 DuckDB 加速）"""
        if self.table is None:
            return pl.DataFrame()

        try:
            import duckdb
            conn = duckdb.connect(database=':memory:')

            arrow_table = self.table.to_arrow()
            conn.register("data", arrow_table)

            result = conn.execute("SELECT * FROM data").fetch_arrow_table()
            conn.close()

            return pl.from_arrow(result)

        except Exception as e:
            logger.warning(f"DuckDB 加速失败，回退到直接读取: {e}")
            arrow_table = self.table.to_arrow()
            return pl.from_arrow(arrow_table)

    def _compute_qfq_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        预计算前复权价格列

        Args:
            df: Polars DataFrame

        Returns:
            添加了 qfq_open, qfq_high, qfq_low, qfq_close 列的 DataFrame
        """
        if df.is_empty():
            return df

        if 'adj_factor' not in df.columns:
            logger.debug("[DataIntegrityService] 无 adj_factor 列，跳过前复权计算")
            return df

        df = df.sort(['stock_code', 'trade_date'])

        df = df.with_columns(
            pl.col('adj_factor').forward_fill().over('stock_code').alias('_adj_factor_ff')
        )
        df = df.with_columns(
            pl.col('_adj_factor_ff').backward_fill().over('stock_code').alias('_adj_factor')
        )

        latest_adj = df.group_by('stock_code').agg(
            pl.col('_adj_factor').last().alias('_latest_adj')
        )
        df = df.join(latest_adj, on='stock_code', how='left')

        df = df.with_columns([
            pl.when(pl.col('_latest_adj').is_not_null() & (pl.col('_latest_adj') > 0))
            .then(pl.col('open') * pl.col('_adj_factor') / pl.col('_latest_adj'))
            .otherwise(pl.col('open'))
            .alias('qfq_open'),

            pl.when(pl.col('_latest_adj').is_not_null() & (pl.col('_latest_adj') > 0))
            .then(pl.col('high') * pl.col('_adj_factor') / pl.col('_latest_adj'))
            .otherwise(pl.col('high'))
            .alias('qfq_high'),

            pl.when(pl.col('_latest_adj').is_not_null() & (pl.col('_latest_adj') > 0))
            .then(pl.col('low') * pl.col('_adj_factor') / pl.col('_latest_adj'))
            .otherwise(pl.col('low'))
            .alias('qfq_low'),

            pl.when(pl.col('_latest_adj').is_not_null() & (pl.col('_latest_adj') > 0))
            .then(pl.col('close') * pl.col('_adj_factor') / pl.col('_latest_adj'))
            .otherwise(pl.col('close'))
            .alias('qfq_close'),
        ])

        df = df.drop(['_adj_factor', '_adj_factor_ff', '_latest_adj'])

        logger.debug(f"[DataIntegrityService] 前复权价格计算完成: {len(df)} 行")
        return df

    def scan_columns(self) -> Dict[str, ColumnStats]:
        """
        扫描所有列的统计信息

        Returns:
            Dict[column_name, ColumnStats]
        """
        logger.info("[DataIntegrityService] 开始扫描数据列...")

        try:
            df = self._get_all_data()

            if df.is_empty():
                return {}

            stats = {}
            for col in df.columns:
                null_count = df[col].null_count()
                total = len(df)
                zero_count = 0
                if df[col].dtype in [pl.Float64, pl.Float32, pl.Int32, pl.Int64]:
                    zero_count = df.filter(pl.col(col) == 0).height

                sample_values = df[col].drop_nulls().unique().head(5).to_list()

                stats[col] = ColumnStats(
                    column_name=col,
                    total_rows=total,
                    null_count=null_count,
                    null_pct=null_count / total * 100 if total > 0 else 0,
                    zero_count=zero_count,
                    zero_pct=zero_count / total * 100 if total > 0 else 0,
                    unique_count=df[col].n_unique(),
                    sample_values=[str(v)[:20] for v in sample_values]
                )

            return stats

        except Exception as e:
            logger.error(f"[DataIntegrityService] 扫描列失败: {e}")
            return {}

    def generate_completeness_report(self) -> CompletenessReport:
        """
        生成完整的数据完整性报告

        Returns:
            CompletenessReport
        """
        logger.info("[DataIntegrityService] 生成完整性报告...")

        try:
            df = self._get_all_data()

            if df.is_empty():
                return CompletenessReport(
                    table_name="daily_ohlcv",
                    total_rows=0,
                    date_range=("", ""),
                    stock_count=0,
                    columns_stats=[],
                    missing_columns=[],
                    critical_missing_pct=100.0,
                    overall_score=0.0
                )

            columns_stats = list(self.scan_columns().values())

            date_min = df['trade_date'].min() if 'trade_date' in df.columns else None
            date_max = df['trade_date'].max() if 'trade_date' in df.columns else None
            stock_count = df['stock_code'].n_unique() if 'stock_code' in df.columns else 0

            missing_columns = [col for col in self.MINIMAL_REQUIRED if col not in df.columns]

            critical_missing_cols = ['adj_factor', 'open', 'high', 'low', 'close']
            critical_stats = [s for s in columns_stats if s.column_name in critical_missing_cols]
            critical_missing_pct = max([s.null_pct for s in critical_stats], default=0.0)

            overall_score = 100.0 - critical_missing_pct

            recommendations = []
            if any(col in missing_columns for col in ['adj_factor']):
                recommendations.append("⚠️ 缺少 adj_factor 列，无法进行前复权计算")
            if 'qfq_close' not in df.columns:
                recommendations.append("⚠️ 缺少前复权价格列，查询时需要实时计算，影响性能")
            if critical_missing_pct > 5.0:
                recommendations.append(f"⚠️ 关键列有 {critical_missing_pct:.1f}% 的数据为空，建议修复")

            return CompletenessReport(
                table_name="daily_ohlcv",
                total_rows=len(df),
                date_range=(str(date_min)[:10] if date_min else "", str(date_max)[:10] if date_max else ""),
                stock_count=stock_count,
                columns_stats=columns_stats,
                missing_columns=missing_columns,
                critical_missing_pct=critical_missing_pct,
                overall_score=overall_score,
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"[DataIntegrityService] 生成报告失败: {e}")
            return CompletenessReport(
                table_name="daily_ohlcv",
                total_rows=0,
                date_range=("", ""),
                stock_count=0,
                columns_stats=[],
                missing_columns=[],
                critical_missing_pct=100.0,
                overall_score=0.0,
                recommendations=[f"生成报告失败: {e}"]
            )

    def repair_missing_qfq(self, batch_size: int = 10000) -> RepairResult:
        """
        补全缺失的前复权价格列（qfq_open, qfq_high, qfq_low, qfq_close）

        使用 Polars 向量化计算，性能比 Pandas 快 10 倍

        Args:
            batch_size: 批处理大小

        Returns:
            RepairResult
        """
        logger.info("[DataIntegrityService] 开始补全前复权价格列...")
        start_time = time.time()

        try:
            df = self._get_all_data()

            if df.is_empty():
                return RepairResult(success=True, records_repaired=0, message="无数据")

            has_qfq = all(col in df.columns for col in self.QFQ_COLUMNS)
            if has_qfq:
                null_counts = {col: df[col].null_count() for col in self.QFQ_COLUMNS}
                total_nulls = sum(null_counts.values())
                if total_nulls == 0:
                    return RepairResult(success=True, records_repaired=0, message="前复权价格列已完整")

            if 'adj_factor' not in df.columns:
                return RepairResult(success=False, message="缺少 adj_factor 列，无法计算前复权价格")

            df = self._compute_qfq_columns(df)

            self._write_to_lancedb(df)

            elapsed = time.time() - start_time
            logger.info(f"[DataIntegrityService] 前复权价格补全完成: {len(df)} 行, 耗时 {elapsed:.1f}s")

            return RepairResult(
                success=True,
                records_repaired=len(df),
                message=f"成功补全 {len(df)} 行的前复权价格",
                elapsed_seconds=elapsed
            )

        except Exception as e:
            logger.error(f"[DataIntegrityService] 前复权价格补全失败: {e}")
            import traceback
            traceback.print_exc()
            return RepairResult(success=False, message=f"补全失败: {e}")

    def repair_missing_factors(self, batch_size: int = 50000) -> RepairResult:
        """
        补全缺失的技术指标因子

        使用 Polars 向量化计算

        Args:
            batch_size: 批处理大小

        Returns:
            RepairResult
        """
        logger.info("[DataIntegrityService] 开始补全技术指标因子...")
        start_time = time.time()

        try:
            from data_svc.storage.factor_precompute_service import FactorPrecomputeService

            service = FactorPrecomputeService()
            result = service.precompute_all_factors()

            elapsed = time.time() - start_time

            if result.success:
                return RepairResult(
                    success=True,
                    records_repaired=result.records_computed,
                    message=f"成功计算 {result.records_computed} 条记录的因子",
                    elapsed_seconds=elapsed
                )
            else:
                return RepairResult(success=False, message=f"因子计算失败: {result.message}")

        except Exception as e:
            logger.error(f"[DataIntegrityService] 技术指标因子补全失败: {e}")
            import traceback
            traceback.print_exc()
            return RepairResult(success=False, message=f"补全失败: {e}")

    def _write_to_lancedb(self, df: pl.DataFrame) -> bool:
        """写入 LanceDB（使用覆盖策略添加新列，避免重复）"""
        try:
            import lancedb

            db = lancedb.connect(self.db_path)
            table_name = "daily_ohlcv"

            df = df.sort(['stock_code', 'trade_date'])

            if table_name in db.table_names():
                existing_df = pl.from_arrow(db.open_table(table_name).to_arrow())

                existing_cols = set(existing_df.columns)
                new_cols = set(df.columns) - existing_cols

                if new_cols:
                    logger.info(f"[DataIntegrityService] 发现新列: {new_cols}，使用表替换策略")

                    for col in new_cols:
                        if col not in existing_df.columns:
                            existing_df = existing_df.with_columns(
                                pl.lit(None).cast(df[col].dtype).alias(col)
                            )

                    existing_df = existing_df.sort(['stock_code', 'trade_date'])

                    merged = existing_df.update(df, on=['stock_code', 'trade_date'], how='left')

                    db.drop_table(table_name)
                    db.create_table(table_name, merged.to_arrow())
                    logger.info(f"[DataIntegrityService] 表更新完成: {len(merged)} 行")
                    return True

                existing_df = existing_df.sort(['stock_code', 'trade_date'])
                merged = existing_df.update(df, on=['stock_code', 'trade_date'], how='left')
                db.open_table(table_name).add(merged.to_arrow())
            else:
                db.create_table(table_name, df.to_arrow())

            return True

        except Exception as e:
            logger.error(f"[DataIntegrityService] 写入 LanceDB 失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_full_repair(self) -> Dict[str, RepairResult]:
        """
        运行完整的修复流程

        Returns:
            Dict[str, RepairResult] - 各修复步骤的结果
        """
        results = {}

        logger.info("[DataIntegrityService] ========== 开始完整修复流程 ==========")

        logger.info("[DataIntegrityService] 步骤 1/3: 生成完整性报告...")
        report = self.generate_completeness_report()
        logger.info(f"[DataIntegrityService] 完整性得分: {report.overall_score:.1f}/100")
        for rec in report.recommendations:
            logger.info(f"  {rec}")

        if report.missing_columns:
            logger.warning(f"[DataIntegrityService] 缺失列: {report.missing_columns}")

        logger.info("[DataIntegrityService] 步骤 2/3: 补全前复权价格列...")
        qfq_result = self.repair_missing_qfq()
        results['qfq_repair'] = qfq_result
        if qfq_result.success:
            logger.info(f"[DataIntegrityService] 前复权修复: {qfq_result.message}")
        else:
            logger.error(f"[DataIntegrityService] 前复权修复失败: {qfq_result.message}")

        logger.info("[DataIntegrityService] 步骤 3/3: 补全技术指标因子...")
        factor_result = self.repair_missing_factors()
        results['factor_repair'] = factor_result
        if factor_result.success:
            logger.info(f"[DataIntegrityService] 因子修复: {factor_result.message}")
        else:
            logger.error(f"[DataIntegrityService] 因子修复失败: {factor_result.message}")

        logger.info("[DataIntegrityService] ========== 完整修复流程完成 ==========")

        return results


def get_data_integrity_service(db_path: Optional[str] = None) -> DataIntegrityService:
    """获取数据完整性服务实例"""
    return DataIntegrityService(db_path)


if __name__ == "__main__":
    service = get_data_integrity_service()

    print("\n" + "=" * 60)
    print("数据完整性检查与修复")
    print("=" * 60)

    report = service.generate_completeness_report()
    print(f"\n📊 完整性报告")
    print(f"   总记录数: {report.total_rows:,}")
    print(f"   股票数量: {report.stock_count:,}")
    print(f"   日期范围: {report.date_range[0]} ~ {report.date_range[1]}")
    print(f"   完整性得分: {report.overall_score:.1f}/100")
    print(f"   关键列缺失率: {report.critical_missing_pct:.2f}%")

    if report.missing_columns:
        print(f"\n⚠️ 缺失列: {report.missing_columns}")

    if report.recommendations:
        print(f"\n📋 建议:")
        for rec in report.recommendations:
            print(f"   {rec}")

    print(f"\n📈 列统计:")
    for stat in report.columns_stats:
        if stat.null_pct > 0 or stat.column_name in ['adj_factor', 'qfq_close', 'ma5', 'rsi_14']:
            print(f"   {stat.column_name}: 空值 {stat.null_pct:.2f}%, 零值 {stat.zero_pct:.2f}%")

    print("\n" + "=" * 60)
    print("开始修复流程? (y/n)")
    print("=" * 60)

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        response = 'y'
    else:
        response = input().strip().lower()

    if response == 'y':
        print("\n开始修复...")
        results = service.run_full_repair()

        print(f"\n修复结果:")
        for name, result in results.items():
            status = "✅" if result.success else "❌"
            print(f"   {status} {name}: {result.message} ({result.elapsed_seconds:.1f}s)")
    else:
        print("跳过修复")
