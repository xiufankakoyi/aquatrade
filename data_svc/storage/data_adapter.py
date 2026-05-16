"""
统一数据适配器框架
==================

设计模式：数据适配器 (Data Adapter Pattern)

目标：
1. 定义内部统一的数据模型 (StandardDataFrame)
2. 为每个数据源编写适配器，将原始数据转换为标准格式
3. 解耦数据源与业务逻辑，便于切换数据源

架构：
┌─────────────────────────────────────────────────────────────────┐
│                      StandardDataFrame                          │
│  - stock_code, trade_date, open, high, low, close, volume     │
│  - adj_factor, qfq_open, qfq_high, qfq_low, qfq_close         │
│  - 所有技术指标因子                                             │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ 适配器转换
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────┴───────┐    ┌───────┴───────┐    ┌───────┴───────┐
│  TushareAdapter │   │  CSVAdapter    │   │ ParquetAdapter │
└───────────────┘    └───────────────┘    └───────────────┘

使用示例：
    # 使用 Tushare 适配器
    adapter = TushareAdapter()
    df = adapter.read_stock_daily("000001.SZ", "2024-01-01", "2024-12-31")
    standard_df = adapter.to_standard(df)

    # 使用统一读取接口
    reader = UnifiedDataReader()
    df = reader.read("000001.SZ", "2024-01-01", "2024-12-31")
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union, TypeVar, Generic
from datetime import datetime, date
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from config.logger import get_logger

logger = get_logger(__name__)


class DataSource(Enum):
    """数据源枚举"""
    TUSHARE = "tushare"
    CSV = "csv"
    PARQUET = "parquet"
    ARCTIC = "arctic"
    LANCEDB = "lancedb"
    UNKNOWN = "unknown"


@dataclass
class ColumnMapping:
    """列映射配置"""
    source_col: str
    target_col: str
    transform: Optional[str] = None


@dataclass
class StandardSchema:
    """
    标准数据模型 Schema

    所有数据源适配器必须输出符合此 Schema 的 DataFrame
    """
    MANDATORY_COLUMNS = [
        'stock_code',
        'trade_date',
        'open',
        'high',
        'low',
        'close',
        'volume',
    ]

    OPTIONAL_COLUMNS = [
        'amount',
        'adj_factor',
        'prev_close',
        'change_pct',
        'change_amount',
        'turnover_rate',
        'total_mv',
        'float_mv',
        'pe',
        'pe_ttm',
        'pb',
        'ps',
        'ps_ttm',
    ]

    QFQ_COLUMNS = [
        'qfq_open',
        'qfq_high',
        'qfq_low',
        'qfq_close',
    ]

    FACTOR_COLUMNS = [
        'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120',
        'ema12', 'ema26', 'ema50', 'ema200',
        'rsi_6', 'rsi_12', 'rsi_24',
        'macd_dif', 'macd_dea', 'macdbar',
        'kdj_k', 'kdj_d', 'kdj_j',
        'boll_upper', 'boll_mid', 'boll_lower', 'bb_width_20',
        'atr_14', 'cci_14', 'wr_14',
        'return_5d', 'return_20d', 'return_60d',
        'volatility_20d', 'max_drawdown_20d',
        'vol_ma5', 'vol_ma10', 'vol_ma20',
    ]

    @classmethod
    def get_all_columns(cls) -> List[str]:
        """获取所有列"""
        return cls.MANDATORY_COLUMNS + cls.OPTIONAL_COLUMNS + cls.QFQ_COLUMNS + cls.FACTOR_COLUMNS

    @classmethod
    def validate(cls, df: pl.DataFrame) -> tuple[bool, List[str]]:
        """
        验证 DataFrame 是否符合标准 Schema

        Returns:
            (is_valid, missing_columns)
        """
        missing = [col for col in cls.MANDATORY_COLUMNS if col not in df.columns]
        return len(missing) == 0, missing


T = TypeVar('T', bound=pl.DataFrame)


class BaseDataAdapter(ABC, Generic[T]):
    """
    数据适配器基类

    定义适配器的通用接口和转换逻辑
    """

    SOURCE_NAME: str = "unknown"
    SOURCE_COLUMNS: List[str] = []

    COLUMN_MAPPINGS: List[ColumnMapping] = []

    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def read_raw(self, *args, **kwargs) -> T:
        """读取原始数据（由子类实现）"""
        pass

    def to_standard(self, df: T) -> pl.DataFrame:
        """
        将原始 DataFrame 转换为标准格式

        Args:
            df: 原始 DataFrame

        Returns:
            标准格式 Polars DataFrame
        """
        try:
            if isinstance(df, pd.DataFrame):
                df_pl = pl.from_pandas(df)
            else:
                df_pl = df.clone()

            df_pl = self._apply_mappings(df_pl)
            df_pl = self._standardize_types(df_pl)
            df_pl = self._validate_and_fill(df_pl)

            return df_pl

        except Exception as e:
            self.logger.error(f"数据转换失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _apply_mappings(self, df: pl.DataFrame) -> pl.DataFrame:
        """应用列映射"""
        if not self.COLUMN_MAPPINGS:
            return df

        rename_map = {}
        for mapping in self.COLUMN_MAPPINGS:
            if mapping.source_col in df.columns:
                rename_map[mapping.source_col] = mapping.target_col

        if rename_map:
            df = df.rename(rename_map)

        return df

    def _standardize_types(self, df: pl.DataFrame) -> pl.DataFrame:
        """标准化列类型"""
        type_map = {
            'trade_date': pl.Date,
            'stock_code': pl.Utf8,
            'open': pl.Float64,
            'high': pl.Float64,
            'low': pl.Float64,
            'close': pl.Float64,
            'volume': pl.Float64,
            'amount': pl.Float64,
            'adj_factor': pl.Float64,
            'prev_close': pl.Float64,
            'change_pct': pl.Float64,
            'change_amount': pl.Float64,
        }

        for col, dtype in type_map.items():
            if col in df.columns:
                try:
                    if df[col].dtype != dtype:
                        df = df.with_columns(pl.col(col).cast(dtype))
                except:
                    pass

        return df

    def _validate_and_fill(self, df: pl.DataFrame) -> pl.DataFrame:
        """验证必填列并填充默认值"""
        missing = [col for col in StandardSchema.MANDATORY_COLUMNS if col not in df.columns]
        if missing:
            self.logger.warning(f"缺少必填列: {missing}")

        if 'trade_date' in df.columns and 'stock_code' in df.columns:
            df = df.sort(['stock_code', 'trade_date'])

        return df

    def compute_qfq(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算前复权价格"""
        if 'adj_factor' not in df.columns:
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

        ohlc_cols = ['open', 'high', 'low', 'close']
        for col in ohlc_cols:
            if col in df.columns:
                qfq_col = f'qfq_{col}'
                df = df.with_columns([
                    pl.when(pl.col('_latest_adj').is_not_null() & (pl.col('_latest_adj') > 0))
                    .then(pl.col(col) * pl.col('_adj_factor') / pl.col('_latest_adj'))
                    .otherwise(pl.col(col))
                    .alias(qfq_col)
                ])

        df = df.drop(['_adj_factor', '_adj_factor_ff', '_latest_adj'])

        return df


class TushareAdapter(BaseDataAdapter[pd.DataFrame]):
    """
    Tushare 数据适配器

    将 Tushare API 返回的原始数据转换为标准格式
    """

    SOURCE_NAME = "tushare"

    COLUMN_MAPPINGS = [
        ColumnMapping('ts_code', 'stock_code'),
        ColumnMapping('trade_date', 'trade_date'),
        ColumnMapping('vol', 'volume'),
        ColumnMapping('pct_chg', 'change_pct'),
        ColumnMapping('pre_close', 'prev_close'),
        ColumnMapping('change', 'change_amount'),
        ColumnMapping('turnover_rate_f', 'turnover_rate'),
        ColumnMapping('circ_mv', 'float_mv'),
    ]

    def __init__(self, token: Optional[str] = None):
        super().__init__()
        self.token = token
        if self.token is None:
            from config.config import Config
            self.token = getattr(Config, 'TUSHARE_TOKEN', None)

    def read_stock_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adj: str = 'qfq'
    ) -> pd.DataFrame:
        """
        读取股票日线数据

        Args:
            ts_code: 股票代码 (如 000001.SZ)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            adj: 复权类型 (qfq/hfq/none)

        Returns:
            Pandas DataFrame
        """
        try:
            import tushare as ts
            pro = ts.pro_api(self.token)

            df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)

            if df is None or df.empty:
                return pd.DataFrame()

            if adj != 'none':
                adj_df = pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if adj_df is not None and not adj_df.empty:
                    df = pd.merge(df, adj_df[['trade_date', 'adj_factor']], on='trade_date', how='left')

            basic_df = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if basic_df is not None and not basic_df.empty:
                cols_to_keep = ['trade_date', 'turnover_rate_f', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'total_mv', 'circ_mv']
                cols_to_keep = [c for c in cols_to_keep if c in basic_df.columns]
                if 'trade_date' not in cols_to_keep:
                    cols_to_keep.insert(0, 'trade_date')
                basic_df = basic_df[cols_to_keep]
                df = pd.merge(df, basic_df, on='trade_date', how='left')

            return df

        except Exception as e:
            self.logger.error(f"读取 Tushare 数据失败: {e}")
            return pd.DataFrame()

    def read_index_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """读取指数日线数据"""
        try:
            import tushare as ts
            pro = ts.pro_api(self.token)
            df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            self.logger.error(f"读取指数数据失败: {e}")
            return pd.DataFrame()

    def read_raw(self, *args, **kwargs) -> pd.DataFrame:
        """实现基类接口"""
        return self.read_stock_daily(*args, **kwargs)


class CSVAdapter(BaseDataAdapter[pl.DataFrame]):
    """
    CSV 文件适配器

    读取本地 CSV 文件并转换为标准格式
    """

    SOURCE_NAME = "csv"

    def __init__(self, csv_dir: Optional[str] = None):
        super().__init__()
        if csv_dir is None:
            project_root = Path(__file__).parent.parent.parent
            csv_dir = str(project_root / "data" / "csv")
        self.csv_dir = Path(csv_dir)

    def read_raw(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        读取 CSV 文件

        Args:
            symbol: 股票代码 (如 000001)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            Polars DataFrame
        """
        csv_path = self.csv_dir / f"{symbol}.csv"

        if not csv_path.exists():
            self.logger.warning(f"CSV 文件不存在: {csv_path}")
            return pl.DataFrame()

        try:
            df = pl.read_csv(csv_path)

            if 'trade_date' in df.columns:
                df = df.with_columns(
                    pl.col('trade_date').str.to_date('%Y%m%d')
                )

            if start_date:
                df = df.filter(pl.col('trade_date') >= pl.lit(start_date).str.to_date())
            if end_date:
                df = df.filter(pl.col('trade_date') <= pl.lit(end_date).str.to_date())

            return df

        except Exception as e:
            self.logger.error(f"读取 CSV 失败: {e}")
            return pl.DataFrame()

    def read_batch(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """批量读取多个 CSV 文件"""
        all_dfs = []
        for symbol in symbols:
            df = self.read_raw(symbol, start_date, end_date)
            if not df.is_empty():
                all_dfs.append(df)

        if not all_dfs:
            return pl.DataFrame()

        return pl.concat(all_dfs)


class ParquetAdapter(BaseDataAdapter[pl.DataFrame]):
    """
    Parquet 文件适配器

    读取 Parquet 文件并转换为标准格式
    """

    SOURCE_NAME = "parquet"

    def __init__(self, parquet_dir: Optional[str] = None):
        super().__init__()
        if parquet_dir is None:
            project_root = Path(__file__).parent.parent.parent
            parquet_dir = str(project_root / "data" / "parquet")
        self.parquet_dir = Path(parquet_dir)

    def read_raw(
        self,
        table_name: str = "daily_ohlcv",
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        读取 Parquet 文件

        Args:
            table_name: 表名
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Polars DataFrame
        """
        parquet_path = self.parquet_dir / f"{table_name}.parquet"

        if not parquet_path.exists():
            self.logger.warning(f"Parquet 文件不存在: {parquet_path}")
            return pl.DataFrame()

        try:
            df = pl.read_parquet(parquet_path)

            if symbols:
                df = df.filter(pl.col('stock_code').is_in(symbols))
            if start_date:
                df = df.filter(pl.col('trade_date') >= pl.lit(start_date).str.to_date())
            if end_date:
                df = df.filter(pl.col('trade_date') <= pl.lit(end_date).str.to_date())

            return df

        except Exception as e:
            self.logger.error(f"读取 Parquet 失败: {e}")
            return pl.DataFrame()

    def write(self, df: pl.DataFrame, table_name: str = "daily_ohlcv") -> bool:
        """写入 Parquet 文件"""
        try:
            parquet_path = self.parquet_dir / f"{table_name}.parquet"
            parquet_path.parent.mkdir(parents=True, exist_ok=True)
            df.write_parquet(parquet_path)
            return True
        except Exception as e:
            self.logger.error(f"写入 Parquet 失败: {e}")
            return False


class LanceDBAdapter(BaseDataAdapter[pl.DataFrame]):
    """
    LanceDB 数据适配器

    从 LanceDB 读取数据并转换为标准格式
    """

    SOURCE_NAME = "lancedb"

    def __init__(self, db_path: Optional[str] = None):
        super().__init__()
        if db_path is None:
            from config.config import Config
            db_path = getattr(Config, 'LANCEDB_PATH', None)
            if db_path is None:
                project_root = Path(__file__).parent.parent.parent
                db_path = str(project_root / "data" / "lancedb")
        self.db_path = db_path

    def read_raw(
        self,
        symbols: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
    ) -> pl.DataFrame:
        """
        从 LanceDB 读取数据

        Args:
            symbols: 股票代码或代码列表
            start_date: 开始日期
            end_date: 结束日期
            fields: 要读取的字段

        Returns:
            Polars DataFrame
        """
        try:
            import lancedb
            db = lancedb.connect(self.db_path)

            if "daily_ohlcv" not in db.table_names():
                return pl.DataFrame()

            table = db.open_table("daily_ohlcv")
            
            lance_ds = table.to_lance()
            if hasattr(lance_ds, 'scanner'):
                scanner = lance_ds.scanner(columns=fields)
                df = pl.from_arrow(scanner.to_table())
            else:
                df = pl.from_arrow(table.to_arrow())
                if fields:
                    df = df.select(fields)

            if symbols:
                if isinstance(symbols, str):
                    df = df.filter(pl.col('stock_code') == symbols)
                else:
                    df = df.filter(pl.col('stock_code').is_in(symbols))

            if start_date:
                df = df.filter(pl.col('trade_date') >= pl.lit(start_date).str.to_date())
            if end_date:
                df = df.filter(pl.col('trade_date') <= pl.lit(end_date).str.to_date())

            return df

        except Exception as e:
            self.logger.error(f"读取 LanceDB 失败: {e}")
            return pl.DataFrame()

    def to_standard(self, df: pl.DataFrame) -> pl.DataFrame:
        """LanceDB 已有标准格式，只需验证"""
        return self._validate_and_fill(df)


class UnifiedDataReader:
    """
    统一数据读取接口

    自动选择最优的数据适配器，提供一致的读取接口
    """

    def __init__(self, preferred_source: DataSource = DataSource.LANCEDB):
        self.preferred_source = preferred_source
        self._adapters: Dict[DataSource, BaseDataAdapter] = {}
        self._init_adapters()

    def _init_adapters(self):
        """初始化所有适配器"""
        try:
            self._adapters[DataSource.LANCEDB] = LanceDBAdapter()
        except:
            pass

        try:
            self._adapters[DataSource.TUSHARE] = TushareAdapter()
        except:
            pass

        self._adapters[DataSource.CSV] = CSVAdapter()
        self._adapters[DataSource.PARQUET] = ParquetAdapter()

    def read(
        self,
        symbols: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        source: Optional[DataSource] = None,
    ) -> pl.DataFrame:
        """
        统一读取接口

        Args:
            symbols: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            fields: 要读取的字段
            source: 指定数据源，None 表示自动选择

        Returns:
            标准格式 Polars DataFrame
        """
        if source is None:
            source = self.preferred_source

        adapter = self._adapters.get(source)
        if adapter is None:
            logger.error(f"数据源不可用: {source}")
            return pl.DataFrame()

        try:
            if source == DataSource.TUSHARE:
                symbol = symbols if isinstance(symbols, str) else (symbols[0] if symbols else None)
                raw_df = adapter.read_raw(symbol, start_date, end_date)
            else:
                raw_df = adapter.read_raw(symbols, start_date, end_date, fields)

            return adapter.to_standard(raw_df)

        except Exception as e:
            logger.error(f"读取数据失败: {e}")
            return pl.DataFrame()


def get_adapter(source: DataSource) -> Optional[BaseDataAdapter]:
    """获取指定数据源的适配器"""
    adapters = {
        DataSource.TUSHARE: TushareAdapter,
        DataSource.CSV: CSVAdapter,
        DataSource.PARQUET: ParquetAdapter,
        DataSource.LANCEDB: LanceDBAdapter,
    }
    adapter_cls = adapters.get(source)
    if adapter_cls:
        return adapter_cls()
    return None


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("数据适配器测试")
    print("=" * 60)

    print("\n1. 测试 Tushare 适配器:")
    tushare_adapter = TushareAdapter()
    print(f"   适配器名称: {tushare_adapter.SOURCE_NAME}")

    print("\n2. 测试 LanceDB 适配器:")
    lancedb_adapter = LanceDBAdapter()
    print(f"   适配器名称: {lancedb_adapter.SOURCE_NAME}")

    print("\n3. 测试标准 Schema:")
    all_cols = StandardSchema.get_all_columns()
    print(f"   标准列数量: {len(all_cols)}")
    print(f"   必填列: {StandardSchema.MANDATORY_COLUMNS}")
    print(f"   QFQ列: {StandardSchema.QFQ_COLUMNS}")

    print("\n4. 测试统一读取接口:")
    reader = UnifiedDataReader()
    print(f"   首选数据源: {reader.preferred_source}")
    print(f"   可用适配器: {list(reader._adapters.keys())}")

    print("\n" + "=" * 60)
