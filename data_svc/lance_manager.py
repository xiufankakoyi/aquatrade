# data_svc/lance_manager.py
"""
LanceDB 数据管理器

将 DuckDB/Parquet 存储层迁移到 LanceDB，实现：
1. 快速读取（零拷贝到 Polars）
2. 增量更新（Upsert 今日数据）
3. 高性能回测查询

LanceDB 优势：
- 列式存储，读取速度快
- 支持增量更新，无需重写整个文件
- 与 Polars 零拷贝集成
- 支持向量搜索（未来可扩展）
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import pandas as pd
import polars as pl

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    lancedb = None

try:
    import pyarrow as pa
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False
    pa = None

from config.config import Config
from config.logger import get_logger

logger = get_logger(__name__)


class LanceDBManager:
    """LanceDB 数据管理器"""
    
    def __init__(self, lance_dir: Optional[str] = None, table_name: str = "stock_daily"):
        """
        初始化 LanceDB 管理器
        
        Args:
            lance_dir: LanceDB 数据目录（默认: parquet_data/lance_db）
            table_name: 表名（默认: stock_daily）
        """
        if not LANCEDB_AVAILABLE:
            raise ImportError("LanceDB is required: pip install lancedb")
        
        # 确定数据目录
        if lance_dir is None:
            parquet_dir = getattr(Config, 'PARQUET_DIR', 'parquet_data')
            lance_dir = os.path.join(parquet_dir, 'lance_db')
        
        self.lance_dir = Path(lance_dir)
        self.lance_dir.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        
        # 连接数据库（共享同一个目录，不同表名）
        self.db = lancedb.connect(str(self.lance_dir))
        logger.info(f"LanceDB 连接已建立: {self.lance_dir}, 表: {self.table_name}")
    
    def convert_parquet_to_lance(self, parquet_path: str, 
                                 batch_size: int = 500000) -> None:
        """
        将 Parquet 文件转换为 LanceDB 表（已修复：强制排序以提升查询性能）
        """
        parquet_path = Path(parquet_path)
        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet 文件不存在: {parquet_path}")
        
        logger.info(f"开始转换 Parquet 到 LanceDB: {parquet_path}")
        
        # 使用 Polars 读取 (Scan)
        logger.info("读取 Parquet 文件...")
        lf = pl.scan_parquet(str(parquet_path))
        
        # ---------------------------------------------------------
        # 关键修复：在内存中对数据进行物理重排 (Clustering)
        # ---------------------------------------------------------
        if self.table_name in ["stock_daily", "stock_limit_status", "benchmark_data"]:
            logger.info(f"正在对 {self.table_name} 进行物理排序 (Date-First)...")
            # 优先按 trade_date 排序，其次按 stock_code
            # 这样会让 DuckDB/LanceDB 在查询特定日期时，直接跳到对应的磁盘块
            if 'trade_date' in lf.columns:
                 lf = lf.sort(['trade_date', 'stock_code'])
            elif 'date' in lf.columns: # 兼容 benchmark
                 lf = lf.sort(['date', 'code'])
        
        # 执行计算并收集到内存
        logger.info("执行排序并加载到内存 (这可能需要一些时间)...")
        df_pl = lf.collect()
        
        logger.info(f"数据形状: {df_pl.shape}")
        
        # 转换为 Pandas
        logger.info("转换为 Pandas DataFrame...")
        df_pd = df_pl.to_pandas()
        
        # 处理特殊列结构
        if self.table_name == "stock_info":
            if 'stock_code' not in df_pd.columns:
                raise ValueError("stock_info 表必须包含 'stock_code' 列")
            df_pd['_id'] = df_pd['stock_code'].astype(str)
            if 'trade_date' not in df_pd.columns:
                df_pd['trade_date'] = '1900-01-01'
        
        elif self.table_name == "benchmark_data":
            if 'code' not in df_pd.columns or 'date' not in df_pd.columns:
                raise ValueError("benchmark_data 表必须包含 'code' 和 'date' 列")
            df_pd['stock_code'] = df_pd['code'].astype(str)
            df_pd['trade_date'] = df_pd['date'].astype(str)
            if pd.api.types.is_datetime64_any_dtype(df_pd['trade_date']):
                df_pd['trade_date'] = df_pd['trade_date'].dt.strftime('%Y-%m-%d')
            df_pd['_id'] = df_pd['stock_code'].astype(str) + '_' + df_pd['trade_date'].astype(str)
        
        else:
            # stock_daily, stock_limit_status
            if 'stock_code' not in df_pd.columns or 'trade_date' not in df_pd.columns:
                raise ValueError(f"{self.table_name} 表必须包含 'stock_code' 和 'trade_date' 列")
            if pd.api.types.is_datetime64_any_dtype(df_pd['trade_date']):
                df_pd['trade_date'] = df_pd['trade_date'].dt.strftime('%Y-%m-%d')
            elif not isinstance(df_pd['trade_date'].dtype, object):
                df_pd['trade_date'] = df_pd['trade_date'].astype(str)
            df_pd['_id'] = df_pd['stock_code'].astype(str) + '_' + df_pd['trade_date'].astype(str)
        
        # 写入 LanceDB
        total_rows = len(df_pd)
        logger.info(f"开始写入 {total_rows} 行数据（已排序）...")
        
        # 使用 overwrite 模式覆盖旧表，确保数据紧凑
        # 如果文件过大，一次性写入是最高效的（如果内存允许）
        try:
            self.db.create_table(self.table_name, df_pd, mode="overwrite")
            logger.info(f"✓ 表创建完成 (Overwrite): {self.table_name}")
        except Exception as e:
            logger.warning(f"一次性写入失败 ({e})，尝试分批写入...")
            # 如果一次性写入失败（OOM），回退到分批
            if self.table_name in self.db.table_names():
                self.db.drop_table(self.table_name)
            
            table = None
            for i in range(0, total_rows, batch_size):
                batch = df_pd.iloc[i:i+batch_size]
                if table is None:
                    table = self.db.create_table(self.table_name, batch)
                else:
                    table.add(batch)
                logger.info(f"  进度: {min(i+batch_size, total_rows)}/{total_rows}")

        logger.info(f"✓ 转换完成！表名: {self.table_name}, 行数: {total_rows}")
    
    def load_to_polars_lazy(self,
                           stock_codes: Optional[List[str]] = None,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           columns: Optional[List[str]] = None,
                           date_column: Optional[str] = None) -> pl.LazyFrame:
        """
        从 LanceDB 加载数据 (已修复：使用下推过滤，杜绝全表扫描)
        
        Args:
            stock_codes: 股票代码列表（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            columns: 要加载的列（可选，默认全部）
            date_column: 日期列名（可选，默认根据表名自动推断：benchmark_data 使用 'date'，其他使用 'trade_date'）
            
        Returns:
            Polars LazyFrame（需要调用 .collect() 才执行）
        """
        if self.table_name not in self.db.table_names():
            raise ValueError(f"表 {self.table_name} 不存在")
        
        table = self.db.open_table(self.table_name)
        
        # 自动推断日期列名
        if date_column is None:
            if self.table_name == "benchmark_data":
                date_column = "date"
            else:
                date_column = "trade_date"
        
        # 1. 构建 SQL 风格的过滤条件
        conditions = []
        if start_date:
            conditions.append(f"{date_column} >= '{start_date}'")
        if end_date:
            conditions.append(f"{date_column} <= '{end_date}'")
        if stock_codes:
            # list 转 SQL string: ('000001', '000002')
            codes_str = "', '".join(stock_codes)
            # 根据表名选择代码列名
            code_column = "code" if self.table_name == "benchmark_data" else "stock_code"
            conditions.append(f"{code_column} IN ('{codes_str}')")
        
        # 特殊处理：stock_info 表没有日期列，如果只有 stock_codes 过滤，也要构建 where 子句
        if self.table_name == "stock_info" and stock_codes and not conditions:
            codes_str = "', '".join(stock_codes)
            conditions.append(f"stock_code IN ('{codes_str}')")
            
        where_clause = " AND ".join(conditions) if conditions else None
        
        # 2. 决定需要读取的列 (减少 IO)
        # 注意：LanceDB 需要列名列表，不能是 None
        columns_to_load = columns if columns else None

        try:
            if not PYARROW_AVAILABLE:
                raise ImportError("pyarrow not available")

            # === 核心修复开始 ===
            _t_query_start = time.perf_counter()
            if where_clause:
                logger.info(f"⚡ [LanceDB] 执行过滤查询: {where_clause}")
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"lance_manager.py:load_to_polars_lazy","message":"开始执行下推查询","data":{"where_clause":where_clause,"start_date":start_date,"end_date":end_date,"has_stock_codes":stock_codes is not None},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"I"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                
                # 【优化】尝试使用更明确的查询方式以触发索引使用
                # 对于日期范围查询，确保使用索引列作为过滤条件
                try:
                    # 方法1：使用 search().where() 下推过滤（推荐，会使用索引）
                    # 注意：LanceDB 的标量索引会在 where 子句包含索引列时自动使用
                    search_query = table.search()
                    
                    # 如果只有日期过滤，优先使用日期索引
                    if start_date and end_date and not stock_codes:
                        # 优化：明确使用日期列过滤，触发索引
                        # 使用 BETWEEN 语法可能更有利于索引使用
                        date_filter = f"{date_column} >= '{start_date}' AND {date_column} <= '{end_date}'"
                        logger.debug(f"[LanceDB] 使用日期范围过滤: {date_filter}")
                        arrow_table = search_query.where(date_filter).to_arrow()
                    else:
                        # 其他情况使用完整 where 子句
                        logger.debug(f"[LanceDB] 使用完整过滤条件: {where_clause}")
                        arrow_table = search_query.where(where_clause).to_arrow()
                    
                    _t_query_end = time.perf_counter()
                    query_time = _t_query_end - _t_query_start
                    num_rows = arrow_table.num_rows if arrow_table else 0
                    
                    # 性能警告：如果查询时间过长，可能索引未被使用
                    if query_time > 1.0:
                        # 计算数据密度（行数/秒），用于判断是否使用了索引
                        rows_per_sec = num_rows / query_time if query_time > 0 else 0
                        logger.warning(
                            f"⚠️ [LanceDB] 查询耗时较长 ({query_time:.3f}s)，可能索引未被使用。"
                            f"表: {self.table_name}, 条件: {where_clause}, 行数: {num_rows}, "
                            f"速度: {rows_per_sec:.0f} 行/秒"
                        )
                        
                        # 检查索引是否存在并尝试重建
                        try:
                            schema = table.schema
                            logger.debug(f"[LanceDB] 表结构: {schema.names}")
                            
                            # 尝试检查并重建索引（如果查询很慢）
                            if query_time > 1.5 and num_rows > 100000:
                                logger.warning(
                                    f"⚠️ [LanceDB] 查询非常慢，建议运行 'python data.py' 重建索引。"
                                    f"表: {self.table_name}, 日期列: {date_column}"
                                )
                        except:
                            pass
                    else:
                        rows_per_sec = num_rows / query_time if query_time > 0 else 0
                        logger.info(
                            f"✓ [LanceDB] 查询完成 ({query_time:.3f}s)，行数: {num_rows}, "
                            f"速度: {rows_per_sec:.0f} 行/秒, 表: {self.table_name}"
                        )
                        
                except Exception as e:
                    logger.warning(f"⚠️ [LanceDB] 优化查询失败，回退到标准查询: {e}")
                    # 回退到标准查询
                    arrow_table = table.search().where(where_clause).to_arrow()
                    _t_query_end = time.perf_counter()
                
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"lance_manager.py:load_to_polars_lazy","message":"下推查询完成","data":{"elapsed":_t_query_end-_t_query_start,"rows":arrow_table.num_rows if arrow_table else 0},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"I"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
            else:
                # 只有在没有过滤条件时，才全量读取
                # 对于 stock_info 表，全表扫描是正常的（表小，只有几千条记录）
                if self.table_name != "stock_info":
                    logger.warning("⚠️ [LanceDB] 无过滤条件，执行全表扫描！")
                else:
                    logger.debug(f"[LanceDB] stock_info 表全表扫描（表小，正常）")
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"lance_manager.py:load_to_polars_lazy","message":"警告：无过滤条件，执行全表扫描","data":{"table_name":self.table_name},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"I"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                arrow_table = table.to_arrow()
                _t_query_end = time.perf_counter()
            # === 核心修复结束 ===

            # 转换为 Polars LazyFrame
            df_eager = pl.from_arrow(arrow_table)
            lazy_df = df_eager.lazy()
            
            # 再次应用列选择 (Polars层面的双重保险)
            if columns:
                valid_cols = [c for c in columns if c in df_eager.columns and c != '_id']
                if valid_cols:
                    lazy_df = lazy_df.select(valid_cols)
            elif '_id' in df_eager.columns:
                lazy_df = lazy_df.drop('_id')
                
            return lazy_df
            
        except Exception as e:
            logger.error(f"LanceDB 查询失败: {e}")
            # 【关键修复】最后的保底：即使失败也要尝试使用过滤，避免全表扫描
            try:
                # 尝试使用更简单的过滤方式
                if where_clause:
                    logger.warning(f"⚠️ [LanceDB] 尝试使用备用过滤方法: {where_clause}")
                    try:
                        # 尝试直接使用 search().where()，即使之前失败
                        arrow_table = table.search().where(where_clause).to_arrow()
                        df_eager = pl.from_arrow(arrow_table)
                        lazy_df = df_eager.lazy()
                        if columns:
                            valid_cols = [c for c in columns if c in df_eager.columns and c != '_id']
                            if valid_cols:
                                lazy_df = lazy_df.select(valid_cols)
                        elif '_id' in df_eager.columns:
                            lazy_df = lazy_df.drop('_id')
                        logger.warning(f"✓ [LanceDB] 备用过滤方法成功，行数: {len(df_eager)}")
                        return lazy_df
                    except Exception as e2:
                        logger.error(f"⚠️ [LanceDB] 备用过滤方法也失败: {e2}")
                
                # 如果所有过滤方法都失败，才全表加载（这是最后的保底）
                logger.error("⚠️ [LanceDB] 所有过滤方法都失败，执行全表扫描（性能较差）")
                result = table.to_pandas()
                
                # 即使全表加载，也要在 Polars 层面应用过滤
                df_pl = pl.from_pandas(result)
                if start_date:
                    df_pl = df_pl.filter(pl.col(date_column) >= start_date)
                if end_date:
                    df_pl = df_pl.filter(pl.col(date_column) <= end_date)
                if stock_codes:
                    code_col = "code" if self.table_name == "benchmark_data" else "stock_code"
                    df_pl = df_pl.filter(pl.col(code_col).is_in(stock_codes))
                if columns:
                    valid_cols = [c for c in columns if c in df_pl.columns and c != '_id']
                    if valid_cols:
                        df_pl = df_pl.select(valid_cols)
                elif '_id' in df_pl.columns:
                    df_pl = df_pl.drop('_id')
                
                return df_pl.lazy()
            except Exception as e3:
                # 如果连这个都失败，才真正全表加载（不应该到这里）
                logger.critical(f"⚠️ [LanceDB] 所有方法都失败，执行全表扫描: {e3}")
                result = table.to_pandas()
                return pl.from_pandas(result).lazy()
    
    def load_to_polars(self, 
                      stock_codes: Optional[List[str]] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      columns: Optional[List[str]] = None,
                      use_lazy: bool = True) -> pl.DataFrame:
        """
        从 LanceDB 加载数据到 Polars DataFrame
        
        Args:
            stock_codes: 股票代码列表（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            columns: 要加载的列（可选，默认全部）
            use_lazy: 是否使用 Lazy API（默认 True，推荐）
            
        Returns:
            Polars DataFrame
        """
        if use_lazy:
            # 使用 Lazy API（推荐，内存安全）
            lazy_df = self.load_to_polars_lazy(
                stock_codes=stock_codes,
                start_date=start_date,
                end_date=end_date,
                columns=columns
            )
            # 执行查询（此时才真正加载数据）
            df_pl = lazy_df.collect()
            logger.info(f"加载完成 (Lazy): {df_pl.shape}")
            return df_pl
        else:
            # 回退到原有 Eager API（兼容性）
            return self._load_to_polars_eager(
                stock_codes=stock_codes,
                start_date=start_date,
                end_date=end_date,
                columns=columns
            )
    
    def _load_to_polars_eager(self,
                              stock_codes: Optional[List[str]] = None,
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None,
                              columns: Optional[List[str]] = None) -> pl.DataFrame:
        """
        原有的 Eager API 实现（已修复：使用下推过滤，避免全表扫描）
        """
        if self.table_name not in self.db.table_names():
            raise ValueError(f"表 {self.table_name} 不存在，请先运行 convert_parquet_to_lance()")
        
        table = self.db.open_table(self.table_name)
        
        # 自动推断日期列名
        date_column = "date" if self.table_name == "benchmark_data" else "trade_date"
        
        try:
            if not PYARROW_AVAILABLE:
                raise ImportError("pyarrow not available")
            
            # 【关键修复】使用 search().where() 下推过滤，避免全表扫描
            # 构建过滤条件
            conditions = []
            if start_date:
                conditions.append(f"{date_column} >= '{start_date}'")
            if end_date:
                conditions.append(f"{date_column} <= '{end_date}'")
            if stock_codes:
                code_column = "code" if self.table_name == "benchmark_data" else "stock_code"
                codes_str = "', '".join(stock_codes)
                conditions.append(f"{code_column} IN ('{codes_str}')")
            
            where_clause = " AND ".join(conditions) if conditions else None
            
            if where_clause:
                # 使用下推过滤，只加载符合条件的数据
                logger.debug(f"[LanceDB Eager] 使用下推过滤: {where_clause}")
                arrow_table = table.search().where(where_clause).to_arrow()
            else:
                # 只有在没有过滤条件时，才全量读取
                logger.warning("⚠️ [LanceDB Eager] 无过滤条件，执行全表扫描！")
                arrow_table = table.to_arrow()
            
            df_pl = pl.from_arrow(arrow_table)
            
            # 再次应用过滤（双重保险，但此时数据已经过滤过了）
            if stock_codes:
                df_pl = df_pl.filter(pl.col('stock_code').is_in(stock_codes))
            if start_date:
                df_pl = df_pl.filter(pl.col('trade_date') >= start_date)
            if end_date:
                df_pl = df_pl.filter(pl.col('trade_date') <= end_date)
            
            if columns:
                available_cols = [col for col in columns if col in df_pl.columns]
                if available_cols:
                    df_pl = df_pl.select(available_cols)
            
            if '_id' in df_pl.columns:
                df_pl = df_pl.drop('_id')
            
            return df_pl
        except Exception as e:
            logger.warning(f"Eager 加载失败，尝试回退: {e}")
            # 最后的保底：如果 search().where() 失败，尝试使用 Pandas 但也要先过滤
            try:
                # 尝试使用 search().where() 先过滤，再转 Pandas
                if where_clause:
                    arrow_table = table.search().where(where_clause).to_arrow()
                    result = arrow_table.to_pandas()
                else:
                    result = table.to_pandas()
            except:
                # 如果还是失败，才全表加载（这是最后的保底）
                logger.error("⚠️ [LanceDB Eager] 所有过滤方法都失败，执行全表扫描（性能较差）")
                result = table.to_pandas()
            
            df_pl = pl.from_pandas(result)
            
            # 应用过滤（如果之前没有过滤成功）
            if stock_codes:
                df_pl = df_pl.filter(pl.col('stock_code').is_in(stock_codes))
            if start_date:
                df_pl = df_pl.filter(pl.col('trade_date') >= start_date)
            if end_date:
                df_pl = df_pl.filter(pl.col('trade_date') <= end_date)
            
            if columns:
                available_cols = [col for col in columns if col in df_pl.columns]
                if available_cols:
                    df_pl = df_pl.select(available_cols)
            
            if '_id' in df_pl.columns:
                df_pl = df_pl.drop('_id')
            
            return df_pl
    
    def upsert_daily_data(self, new_data: pd.DataFrame) -> None:
        """
        增量更新今日数据（Upsert）
        
        如果数据已存在（相同的 stock_code + trade_date），则更新
        如果不存在，则插入
        
        Args:
            new_data: 新的日线数据 DataFrame，必须包含 stock_code 和 trade_date 列
        """
        if self.table_name not in self.db.table_names():
            raise ValueError(f"表 {self.table_name} 不存在，请先运行 convert_parquet_to_lance()")
        
        if 'stock_code' not in new_data.columns or 'trade_date' not in new_data.columns:
            raise ValueError("new_data 必须包含 'stock_code' 和 'trade_date' 列")
        
        logger.info(f"开始 Upsert {len(new_data)} 行数据...")
        
        # 准备数据
        df = new_data.copy()
        
        # 确保日期格式
        if pd.api.types.is_datetime64_any_dtype(df['trade_date']):
            df['trade_date'] = df['trade_date'].dt.strftime('%Y-%m-%d')
        elif not isinstance(df['trade_date'].dtype, object):
            df['trade_date'] = df['trade_date'].astype(str)
        
        # 创建复合 ID
        df['_id'] = df['stock_code'].astype(str) + '_' + df['trade_date'].astype(str)
        
        # 打开表
        table = self.db.open_table(self.table_name)
        
        # 获取现有数据的 ID 集合（用于判断是更新还是插入）
        try:
            existing_df = table.to_pandas()
            existing_ids = set(existing_df['_id'].unique()) if '_id' in existing_df.columns else set()
        except:
            existing_ids = set()
        
        new_ids = set(df['_id'].unique())
        
        to_update = new_ids & existing_ids
        to_insert = new_ids - existing_ids
        
        logger.info(f"  更新: {len(to_update)} 条")
        logger.info(f"  插入: {len(to_insert)} 条")
        
        # 执行 Upsert
        # LanceDB 的 Upsert 策略：先删除旧数据，再插入新数据
        if to_update:
            # 批量删除需要更新的记录
            ids_to_delete = list(to_update)
            
            # 方法1：尝试使用 delete 方法（如果支持）
            try:
                # LanceDB 可能支持批量删除
                for _id in ids_to_delete:
                    try:
                        table.delete(f"_id = '{_id}'")
                    except (AttributeError, TypeError) as e:
                        # 如果不支持 delete，使用方法2
                        raise e
            except (AttributeError, TypeError):
                # 方法2：读取现有数据，删除旧记录，重建表
                logger.info("  使用重建表方式实现 Upsert...")
                existing_df = table.to_pandas()
                
                # 删除需要更新的记录
                existing_df = existing_df[~existing_df['_id'].isin(ids_to_delete)]
                
                # 合并新旧数据
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                
                # 删除旧表并重建
                self.db.drop_table(self.table_name)
                table = self.db.create_table(self.table_name, combined_df)
                logger.info(f"✓ Upsert 完成（重建表方式）")
                return
        
        # 插入新数据（如果没有更新，直接追加）
        try:
            table.add(df, mode="append")
        except (TypeError, AttributeError):
            # 如果不支持 mode 参数，使用默认追加
            table.add(df)
        
        logger.info(f"✓ Upsert 完成")
    
    def get_table_info(self) -> Dict[str, Any]:
        """获取表信息"""
        if self.table_name not in self.db.table_names():
            return {"exists": False}
        
        table = self.db.open_table(self.table_name)
        df = table.to_pandas()
        
        return {
            "exists": True,
            "rows": len(df),
            "columns": list(df.columns),
            "date_range": {
                "min": df['trade_date'].min() if 'trade_date' in df.columns else None,
                "max": df['trade_date'].max() if 'trade_date' in df.columns else None,
            },
            "stock_count": df['stock_code'].nunique() if 'stock_code' in df.columns else None,
        }
    
    def optimize_table(self) -> None:
        """优化表（压缩、重建索引）"""
        if self.table_name not in self.db.table_names():
            raise ValueError(f"表 {self.table_name} 不存在")
        
        logger.info("优化表...")
        table = self.db.open_table(self.table_name)
        
        # LanceDB 自动处理压缩和优化
        # 可以手动触发合并操作（如果支持）
        try:
            if hasattr(table, 'compact_files'):
                table.compact_files()
                logger.info("✓ 表优化完成")
            else:
                logger.info("✓ 表已就绪（LanceDB 自动优化）")
        except Exception as e:
            logger.info(f"✓ 表已就绪（优化操作跳过: {e}）")


def migrate_parquet_to_lance(parquet_path: str, 
                             lance_dir: Optional[str] = None,
                             table_name: str = "stock_daily") -> LanceDBManager:
    """
    便捷函数：将 Parquet 文件迁移到 LanceDB
    
    Args:
        parquet_path: Parquet 文件路径
        lance_dir: LanceDB 数据目录
        table_name: 表名
        
    Returns:
        LanceDBManager 实例
    """
    manager = LanceDBManager(lance_dir=lance_dir, table_name=table_name)
    manager.convert_parquet_to_lance(parquet_path)
    return manager


def demo_usage():
    """演示用法"""
    print("=" * 60)
    print("LanceDB 管理器演示")
    print("=" * 60)
    
    # 1. 初始化管理器
    print("\n[1] 初始化 LanceDB 管理器...")
    manager = LanceDBManager(table_name="stock_daily")
    
    # 2. 转换 Parquet 到 LanceDB
    parquet_path = os.path.join(Config.PARQUET_DIR, "stock_daily.parquet")
    if os.path.exists(parquet_path):
        print(f"\n[2] 转换 Parquet 到 LanceDB: {parquet_path}")
        manager.convert_parquet_to_lance(parquet_path, batch_size=100000)
    else:
        print(f"\n[2] Parquet 文件不存在: {parquet_path}")
        print("   跳过转换步骤")
    
    # 3. 查询数据（零拷贝到 Polars）
    print("\n[3] 从 LanceDB 加载数据到 Polars...")
    try:
        # 查询最近 10 天的数据
        df = manager.load_to_polars(
            start_date="2024-12-01",
            end_date="2024-12-10",
            columns=['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
        )
        print(f"   加载了 {len(df)} 行数据")
        print(f"   列: {df.columns}")
        print(f"   示例数据:")
        print(df.head(5))
    except Exception as e:
        print(f"   查询失败: {e}")
    
    # 4. 演示 Upsert
    print("\n[4] 演示 Upsert（增量更新）...")
    try:
        # 创建示例数据
        today = datetime.now().strftime('%Y-%m-%d')
        sample_data = pd.DataFrame({
            'stock_code': ['000001', '000002', '600000'],
            'trade_date': [today, today, today],
            'open': [10.0, 20.0, 30.0],
            'high': [10.5, 20.5, 30.5],
            'low': [9.8, 19.8, 29.8],
            'close': [10.2, 20.2, 30.2],
            'volume': [1000000, 2000000, 3000000],
        })
        
        manager.upsert_daily_data(sample_data)
        print(f"   ✓ Upsert 完成: {len(sample_data)} 条记录")
    except Exception as e:
        print(f"   Upsert 失败: {e}")
    
    # 5. 显示表信息
    print("\n[5] 表信息:")
    info = manager.get_table_info()
    print(f"   存在: {info.get('exists', False)}")
    if info.get('exists'):
        print(f"   行数: {info.get('rows', 0):,}")
        print(f"   股票数: {info.get('stock_count', 0):,}")
        print(f"   日期范围: {info.get('date_range', {})}")
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    demo_usage()

