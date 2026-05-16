"""
Parquet数据管理器

完全替代SQLite，所有数据存储在Parquet文件中
优势：
- 高性能：Polars查询速度比SQLite快10-100倍
- 压缩率高：Parquet格式比SQLite节省50-70%空间
- 兼容性好：与Pandas/Polars无缝集成
- 适合大数据：支持TB级数据

数据文件结构：
- data/parquet_data/
  - stock_daily.parquet      # 股票日线数据
  - stock_info.parquet       # 股票基本信息（含行业）
  - benchmark_daily.parquet  # 指数数据
  - trade_records.parquet    # 交易记录
  - backtest_results.parquet # 回测结果
  - portfolio_positions.parquet # 持仓数据
  - fund_basic.parquet       # 基金基本信息
  - fund_nav.parquet         # 基金净值
"""
import os
import json
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

import pandas as pd
import polars as pl
from loguru import logger

from config.config import Config


class ParquetDataManager:
    """
    Parquet数据管理器
    统一管理所有Parquet文件的读写操作
    """

    def __init__(self, parquet_dir: Optional[str] = None):
        """
        初始化Parquet数据管理器

        Args:
            parquet_dir: Parquet文件目录，默认使用Config.PARQUET_DIR
        """
        self.parquet_dir = parquet_dir or Config.PARQUET_DIR
        os.makedirs(self.parquet_dir, exist_ok=True)

        # 定义所有数据文件路径
        self.files = {
            'stock_daily': os.path.join(self.parquet_dir, 'stock_daily.parquet'),
            'stock_info': os.path.join(self.parquet_dir, 'stock_info.parquet'),
            'benchmark_daily': os.path.join(self.parquet_dir, 'benchmark_daily.parquet'),
            'trade_records': os.path.join(self.parquet_dir, 'trade_records.parquet'),
            'backtest_results': os.path.join(self.parquet_dir, 'backtest_results.parquet'),
            'portfolio_positions': os.path.join(self.parquet_dir, 'portfolio_positions.parquet'),
            'fund_basic': os.path.join(self.parquet_dir, 'fund_basic.parquet'),
            'fund_nav': os.path.join(self.parquet_dir, 'fund_nav.parquet'),
        }

        logger.info(f"[ParquetDataManager] 初始化完成，目录: {self.parquet_dir}")

    def _get_path(self, name: str) -> str:
        """获取文件路径"""
        if name not in self.files:
            # 动态生成路径
            return os.path.join(self.parquet_dir, f"{name}.parquet")
        return self.files[name]

    def read(self, name: str, columns: Optional[List[str]] = None) -> Optional[pl.DataFrame]:
        """
        读取Parquet文件

        Args:
            name: 数据名称
            columns: 指定列，None表示读取所有列

        Returns:
            Polars DataFrame 或 None
        """
        path = self._get_path(name)

        if not os.path.exists(path):
            logger.debug(f"[ParquetDataManager] 文件不存在: {path}")
            return None

        try:
            if columns:
                return pl.scan_parquet(path).select(columns).collect()
            return pl.read_parquet(path)
        except Exception as e:
            logger.error(f"[ParquetDataManager] 读取失败 {name}: {e}")
            return None

    def write(self, name: str, df: Union[pd.DataFrame, pl.DataFrame], mode: str = 'overwrite') -> bool:
        """
        写入Parquet文件

        Args:
            name: 数据名称
            df: DataFrame数据
            mode: 写入模式，'overwrite'覆盖，'append'追加

        Returns:
            是否成功
        """
        path = self._get_path(name)

        try:
            # 转换为Polars DataFrame
            if isinstance(df, pd.DataFrame):
                df_pl = pl.from_pandas(df)
            else:
                df_pl = df

            if mode == 'append' and os.path.exists(path):
                # 追加模式：读取现有数据，合并后写入
                existing = pl.read_parquet(path)
                df_pl = pl.concat([existing, df_pl])

                # 去重逻辑（根据数据类型）
                if name == 'stock_daily':
                    df_pl = df_pl.unique(subset=['stock_code', 'trade_date'], keep='last')
                elif name == 'stock_info':
                    df_pl = df_pl.unique(subset=['stock_code'], keep='last')
                elif name == 'trade_records':
                    df_pl = df_pl.unique(subset=['id'], keep='last')

            df_pl.write_parquet(path)
            logger.info(f"[ParquetDataManager] 写入成功 {name}: {len(df_pl)} 条记录")
            return True

        except Exception as e:
            logger.error(f"[ParquetDataManager] 写入失败 {name}: {e}")
            return False

    def exists(self, name: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(self._get_path(name))

    def get_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """获取文件统计信息"""
        path = self._get_path(name)

        if not os.path.exists(path):
            return None

        try:
            df = pl.scan_parquet(path)
            schema = df.collect_schema()

            return {
                'name': name,
                'path': path,
                'size_mb': os.path.getsize(path) / (1024 * 1024),
                'rows': df.select(pl.count()).collect().item(),
                'columns': len(schema.names()),
                'column_names': schema.names(),
            }
        except Exception as e:
            logger.error(f"[ParquetDataManager] 获取统计失败 {name}: {e}")
            return None

    def query(self, name: str, filters: Optional[Dict[str, Any]] = None) -> Optional[pl.DataFrame]:
        """
        条件查询

        Args:
            name: 数据名称
            filters: 过滤条件，如 {'trade_date': '2025-01-01', 'stock_code': '000001'}

        Returns:
            过滤后的DataFrame
        """
        path = self._get_path(name)

        if not os.path.exists(path):
            return None

        try:
            df = pl.scan_parquet(path)

            if filters:
                for col, value in filters.items():
                    if isinstance(value, list):
                        df = df.filter(pl.col(col).is_in(value))
                    else:
                        df = df.filter(pl.col(col) == value)

            return df.collect()
        except Exception as e:
            logger.error(f"[ParquetDataManager] 查询失败 {name}: {e}")
            return None

    def migrate_from_sqlite(self, sqlite_path: str, table_name: str, parquet_name: str = None) -> bool:
        """
        从SQLite迁移数据到Parquet

        Args:
            sqlite_path: SQLite数据库路径
            table_name: SQLite表名
            parquet_name: Parquet文件名，默认与表名相同

        Returns:
            是否成功
        """
        import sqlite3

        if parquet_name is None:
            parquet_name = table_name

        logger.info(f"[ParquetDataManager] 迁移 {table_name} -> {parquet_name}")

        try:
            conn = sqlite3.connect(sqlite_path)
            df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
            conn.close()

            if df.empty:
                logger.info(f"[ParquetDataManager] {table_name} 无数据，跳过")
                return True

            return self.write(parquet_name, df)

        except Exception as e:
            logger.error(f"[ParquetDataManager] 迁移失败 {table_name}: {e}")
            return False


class TradeRecordManager:
    """
    交易记录管理器（基于Parquet）
    替代SQLite的trade_records表
    """

    def __init__(self, data_manager: Optional[ParquetDataManager] = None):
        self.dm = data_manager or ParquetDataManager()

    def get_all_records(self) -> Optional[pd.DataFrame]:
        """获取所有交易记录"""
        df = self.dm.read('trade_records')
        if df is not None:
            return df.to_pandas()
        return None

    def get_records_by_backtest(self, backtest_id: int) -> Optional[pd.DataFrame]:
        """获取指定回测的交易记录"""
        df = self.dm.query('trade_records', {'backtest_id': backtest_id})
        if df is not None:
            return df.to_pandas()
        return None

    def add_record(self, record: Dict[str, Any]) -> bool:
        """添加交易记录"""
        df = pd.DataFrame([record])
        return self.dm.write('trade_records', df, mode='append')

    def add_records(self, records: List[Dict[str, Any]]) -> bool:
        """批量添加交易记录"""
        if not records:
            return True
        df = pd.DataFrame(records)
        return self.dm.write('trade_records', df, mode='append')


class PortfolioPositionManager:
    """
    持仓管理器（基于Parquet）
    替代SQLite的portfolio_positions表
    """

    def __init__(self, data_manager: Optional[ParquetDataManager] = None):
        self.dm = data_manager or ParquetDataManager()

    def get_all_positions(self, active_only: bool = True) -> Optional[pd.DataFrame]:
        """获取所有持仓"""
        df = self.dm.read('portfolio_positions')
        if df is None:
            return None

        df_pd = df.to_pandas()
        if active_only:
            df_pd = df_pd[df_pd['is_active'] == True]
        return df_pd

    def get_position(self, position_id: int) -> Optional[Dict[str, Any]]:
        """获取单个持仓"""
        df = self.dm.query('portfolio_positions', {'id': position_id})
        if df is not None and len(df) > 0:
            return df.to_pandas().iloc[0].to_dict()
        return None

    def add_position(self, position: Dict[str, Any]) -> bool:
        """添加持仓"""
        position['created_at'] = datetime.now().isoformat()
        position['updated_at'] = datetime.now().isoformat()
        df = pd.DataFrame([position])
        return self.dm.write('portfolio_positions', df, mode='append')

    def update_position(self, position_id: int, updates: Dict[str, Any]) -> bool:
        """更新持仓"""
        df = self.dm.read('portfolio_positions')
        if df is None:
            return False

        df_pd = df.to_pandas()
        mask = df_pd['id'] == position_id
        if not mask.any():
            return False

        for key, value in updates.items():
            df_pd.loc[mask, key] = value
        df_pd.loc[mask, 'updated_at'] = datetime.now().isoformat()

        return self.dm.write('portfolio_positions', df_pd, mode='overwrite')

    def delete_position(self, position_id: int) -> bool:
        """删除持仓（软删除）"""
        return self.update_position(position_id, {'is_active': False})


# 全局实例
_parquet_manager: Optional[ParquetDataManager] = None


def get_parquet_manager() -> ParquetDataManager:
    """获取全局Parquet数据管理器实例"""
    global _parquet_manager
    if _parquet_manager is None:
        _parquet_manager = ParquetDataManager()
    return _parquet_manager
