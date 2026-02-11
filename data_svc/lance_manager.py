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
from tqdm import tqdm

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
            parquet_dir = getattr(Config, 'PARQUET_DIR', 'data/parquet_data')
            lance_dir = os.path.join(parquet_dir, 'lance_db')
        
        self.lance_dir = Path(lance_dir)
        self.lance_dir.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        
        # 连接数据库（共享同一个目录，不同表名）
        self.db = lancedb.connect(str(self.lance_dir))
        logger.info(f"LanceDB 连接已建立: {self.lance_dir}, 表: {self.table_name}")
    
    def convert_csv_to_lance(self, source_path: str, batch_size: int = 1000000) -> None:
        """
        [断点续传版] 针对 16GB 分时数据的写入
        - 特性: 支持中断后继续运行 (不会从头开始)
        - 修复: 正确处理 trade_time 和 stock_code
        - 内存: 保持用完即焚
        """
        import gc
        import os
        from tqdm import tqdm
        
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"路径不存在: {path}")

        if path.is_dir():
            all_files = list(path.glob("*.csv"))
            logger.info(f"扫描目录: {path} (共 {len(all_files)} 个文件)")
        else:
            all_files = [path]

        # --- [新增] 断点续传逻辑 ---
        progress_file = Path("migration_progress.txt")
        processed_files = set()
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                processed_files = set(line.strip() for line in f if line.strip())
            logger.info(f"检测到断点记录，已跳过 {len(processed_files)} 个文件")

        # 过滤掉已处理的文件
        files_to_process = [f for f in all_files if f.name not in processed_files]
        if not files_to_process:
            logger.info("所有文件均已处理完毕，无需操作。")
            return

        # 进度条
        pbar = tqdm(files_to_process, desc="断点续传写入", unit="file")
        
        for i, f in enumerate(pbar):
            try:
                pbar.set_postfix(file=f.name)
                
                # 1. 读取数据
                df_chunk = pd.read_csv(f, dtype={'code': str, 'stock_code': str, 'symbol': str})
                
                # 2. 列名映射 (抢救时间列)
                rename_map = {}
                if 'Unnamed: 0' in df_chunk.columns: rename_map['Unnamed: 0'] = 'trade_time'
                if 'code' in df_chunk.columns and 'stock_code' not in df_chunk.columns: rename_map['code'] = 'stock_code'
                if 'symbol' in df_chunk.columns and 'stock_code' not in df_chunk.columns: rename_map['symbol'] = 'stock_code'
                if 'time' in df_chunk.columns and 'trade_time' not in df_chunk.columns: rename_map['time'] = 'trade_time'
                
                if rename_map: df_chunk.rename(columns=rename_map, inplace=True)
                
                # 3. 清洗
                if 'index' in df_chunk.columns: df_chunk.drop(columns=['index'], inplace=True)
                
                if 'stock_code' not in df_chunk.columns or 'trade_time' not in df_chunk.columns:
                    del df_chunk
                    continue

                # 4. 格式化
                df_chunk['stock_code'] = df_chunk['stock_code'].astype(str).str.split('.').str[0]
                df_chunk['trade_time'] = df_chunk['trade_time'].astype(str)
                df_chunk.sort_values(['stock_code', 'trade_time'], inplace=True)
                
                # 5. 写入逻辑
                # 判断表是否存在 (如果存在则追加，不存在则创建)
                table_exists = self.table_name in self.db.table_names()
                
                if not table_exists:
                    # 第一次创建
                    self.db.create_table(self.table_name, df_chunk)
                else:
                    # 追加模式
                    tbl = self.db.open_table(self.table_name)
                    # Schema 对齐
                    valid_cols = tbl.schema.names
                    current_cols = df_chunk.columns.tolist()
                    extra_cols = [c for c in current_cols if c not in valid_cols]
                    if extra_cols: df_chunk.drop(columns=extra_cols, inplace=True)
                    
                    tbl.add(df_chunk)
                    del tbl
                
                # 6. [新增] 记录成功文件
                with open(progress_file, "a", encoding="utf-8") as pf:
                    pf.write(f.name + "\n")
                
                # 7. 内存清理
                del df_chunk
                gc.collect()
                
            except Exception as e:
                tqdm.write(f"❌ 文件 {f.name} 失败: {e}")
                gc.collect()

        logger.info(f"✓ 本批次任务完成！")
    
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
        从 LanceDB 加载数据 (已修复：自动识别 trade_time/trade_date)
        """
        if self.table_name not in self.db.table_names():
            raise ValueError(f"表 {self.table_name} 不存在")
        
        table = self.db.open_table(self.table_name)
        
        # 【DEBUG】记录表结构和请求参数 - 针对 stock_limit_status 表
        if self.table_name == "stock_limit_status":
            logger.info(f"[DEBUG] stock_limit_status: 请求参数 - start_date={start_date}, end_date={end_date}, date_column={date_column}")
            logger.info(f"[DEBUG] stock_limit_status: 表 schema - {table.schema.names}")
        
        # --- [核心修复] 自动推断日期列名 ---
        if date_column is None:
            schema_names = table.schema.names
            
            # 【优先处理】针对 stock_limit_status 表的特殊处理
            if self.table_name == "stock_limit_status":
                logger.info(f"[DEBUG] stock_limit_status: 开始推断日期列，当前 schema_names: {schema_names}")
                # 首先检查标准日期列
                if "trade_date" in schema_names:
                    date_column = "trade_date"
                    logger.info(f"[DEBUG] stock_limit_status: 找到 trade_date 列")
                elif "date" in schema_names:
                    date_column = "date"
                    logger.info(f"[DEBUG] stock_limit_status: 找到 date 列")
                else:
                    # 尝试其他候选列
                    date_candidates = ["limit_date", "trade_datetime"]
                    logger.info(f"[DEBUG] stock_limit_status: 尝试候选日期列: {date_candidates}")
                    for candidate in date_candidates:
                        if candidate in schema_names:
                            date_column = candidate
                            logger.info(f"[DEBUG] stock_limit_status: 找到匹配的日期列: {candidate}")
                            break
                    # 如果没有找到合适的日期列，使用 trade_date 作为最终兜底
                    if date_column is None:
                        date_column = "trade_date"
                        logger.info(f"[DEBUG] stock_limit_status: 未找到匹配的日期列，使用 trade_date 作为兜底")
            else:
                # 常规表的日期列推断
                if "trade_time" in schema_names:
                    date_column = "trade_time"  # 分时数据用这个
                elif "trade_date" in schema_names:
                    date_column = "trade_date"  # 日线数据用这个
                elif "date" in schema_names:
                    date_column = "date"        # Benchmark 用这个
                else:
                    date_column = "trade_date"  # 默认兜底
        # --------------------------------
        
        # 【DEBUG】验证日期列是否存在
        if self.table_name == "stock_limit_status":
            if date_column not in table.schema.names:
                logger.warning(f"[DEBUG] stock_limit_status: 警告！推断的日期列 {date_column} 不在 schema 中！schema: {table.schema.names}")
                # 强制使用存在的日期列
                if "trade_date" in table.schema.names:
                    date_column = "trade_date"
                    logger.warning(f"[DEBUG] stock_limit_status: 切换到 trade_date 列")
                elif "date" in table.schema.names:
                    date_column = "date"
                    logger.warning(f"[DEBUG] stock_limit_status: 切换到 date 列")
                else:
                    logger.error(f"[DEBUG] stock_limit_status: 错误！表中没有可用的日期列！schema: {table.schema.names}")
        
        # 1. 构建标准 SQL 风格的过滤条件（LanceDB 使用 SQL 语法）
        conditions = []
        
        # 【DEBUG】记录日期参数和 date_column
        if self.table_name == "stock_limit_status":
            logger.info(f"[DEBUG] stock_limit_status: 构建条件 - date_column={date_column}, start_date={start_date} (type: {type(start_date)}), end_date={end_date} (type: {type(end_date)}), stock_codes={stock_codes}")
        
        # 【修复】确保日期过滤条件被添加
        if start_date is not None:
            logger.info(f"[DEBUG] 添加 start_date 条件: {date_column} >= '{start_date}'")
            conditions.append(f"{date_column} >= '{start_date}'")
        else:
            logger.debug(f"[DEBUG] start_date 是 None，跳过条件")
            
        if end_date is not None:
            logger.info(f"[DEBUG] 添加 end_date 条件: {date_column} <= '{end_date}'")
            conditions.append(f"{date_column} <= '{end_date}'")
        else:
            logger.debug(f"[DEBUG] end_date 是 None，跳过条件")

        
        # 【修复】正确处理 stock_codes 为 None 的情况
        if stock_codes is not None and len(stock_codes) > 0:
            code_column = "code" if "code" in table.schema.names and "stock_code" not in table.schema.names else "stock_code"
            codes_str = "', '".join(stock_codes)
            conditions.append(f"{code_column} IN ('{codes_str}')")
        
        # 构建标准 SQL 风格的 where_clause（使用 AND 连接条件）
        where_clause = " AND ".join(conditions) if conditions else None
        
        try:
            if not PYARROW_AVAILABLE: raise ImportError("pyarrow not available")

            # 执行查询
            if where_clause:
                logger.info(f"⚡ [LanceDB] 执行过滤查询: {where_clause}")
                logger.info(f"⚡ [LanceDB] 查询参数 - table: {self.table_name}, where_clause:  {where_clause}")
                # 尝试优化查询
                try:
                    search_query = table.search()
                    # 检查日期列是否存在于表中
                    if date_column not in table.schema.names:
                        logger.error(f"[ERROR] 日期列 {date_column} 不存在于表 {self.table_name} 的 schema 中！schema: {table.schema.names}")
                    # 如果只有日期范围，尝试强制使用索引逻辑（LanceDB 自动优化）
                    arrow_table = search_query.where(where_clause).to_arrow()
                    logger.info(f"⚡ [LanceDB] 查询成功，返回行数: {len(arrow_table)}")
                except Exception as e:
                    logger.warning(f"⚠️ [LanceDB] 优化查询失败，回退: {e}")
                    arrow_table = table.search().where(where_clause).to_arrow()
            else:
                # 【修复】只对应该有日期过滤的表发出警告
                # stock_info 和 benchmark_data 的某些查询确实不需要日期过滤
                if self.table_name in ["stock_limit_status", "stock_daily"] and (start_date or end_date):
                    logger.warning(f"⚠️ [LanceDB] {self.table_name} 表缺少日期过滤条件！start_date={start_date}, end_date={end_date}")
                    logger.warning(f"⚠️ [LanceDB] 日期列: {date_column}, 是否在 schema 中: {date_column in table.schema.names}")
                    logger.warning(f"⚠️ [LanceDB] 构建条件时的条件列表: {conditions}")
                
                arrow_table = table.to_arrow()
                logger.info(f"⚠️ [LanceDB] 全表扫描 {self.table_name}，返回行数: {len(arrow_table)}")


            # 转换为 Polars
            df_eager = pl.from_arrow(arrow_table)
            lazy_df = df_eager.lazy()
            
            # 列选择
            if columns:
                valid_cols = [c for c in columns if c in df_eager.columns and c != '_id']
                if valid_cols: lazy_df = lazy_df.select(valid_cols)
            elif '_id' in df_eager.columns:
                lazy_df = lazy_df.drop('_id')
                
            return lazy_df
            
        except Exception as e:
            logger.error(f"LanceDB 查询失败: {e}")
            # 最后的保底逻辑... (保持原样即可，或者直接抛出)
            raise e
    
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
        # 【DEBUG】记录接收到的参数
        logger.info(f"[DEBUG] load_to_polars 接收参数: table={self.table_name}, "
                    f"start_date={start_date} (type: {type(start_date).__name__}), "
                    f"end_date={end_date} (type: {type(end_date).__name__}), "
                    f"stock_codes={'None' if stock_codes is None else f'List[{len(stock_codes)}]'}, "
                    f"use_lazy={use_lazy}")
        
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
        Eager API 实现（已修复：自动识别 trade_time/trade_date）
        """
        if self.table_name not in self.db.table_names():
            raise ValueError(f"表 {self.table_name} 不存在")
        
        table = self.db.open_table(self.table_name)
        
        # --- [核心修复] 自动推断日期列名 ---
        schema_names = table.schema.names
        if "trade_time" in schema_names:
            date_column = "trade_time"
        elif "trade_date" in schema_names:
            date_column = "trade_date"
        elif "date" in schema_names:
            date_column = "date"
        else:
            date_column = "trade_date"
        # --------------------------------
        
        try:
            # 构建过滤条件
            conditions = []
            if start_date:
                conditions.append(f"{date_column} >= '{start_date}'")
            if end_date:
                conditions.append(f"{date_column} <= '{end_date}'")
            if stock_codes:
                code_column = "code" if "code" in schema_names and "stock_code" not in schema_names else "stock_code"
                codes_str = "', '".join(stock_codes)
                conditions.append(f"{code_column} IN ('{codes_str}')")
            
            where_clause = " AND ".join(conditions) if conditions else None
            
            if where_clause:
                arrow_table = table.search().where(where_clause).to_arrow()
            else:
                arrow_table = table.to_arrow()
            
            df_pl = pl.from_arrow(arrow_table)
            
            # 列裁剪
            if columns:
                available_cols = [col for col in columns if col in df_pl.columns]
                if available_cols: df_pl = df_pl.select(available_cols)
            
            if '_id' in df_pl.columns: df_pl = df_pl.drop('_id')
            
            return df_pl
            
        except Exception as e:
            logger.error(f"Eager 加载失败: {e}")
            raise e
    
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
        """
        [轻量版] 获取表信息
        只读取元数据，不加载全量数据，防止 16GB 数据撑爆内存
        """
        if self.table_name not in self.db.table_names():
            return {"exists": False}
        
        try:
            table = self.db.open_table(self.table_name)
            
            # 【关键修改】绝对不要调用 to_pandas()！
            # 使用 count_rows() 直接从元数据读取行数，速度极快且不占内存
            row_count = table.count_rows()
            
            # 获取列名
            schema_names = table.schema.names
            
            # 对于大表，不再计算 min/max 日期，因为需要全表扫描
            return {
                "exists": True,
                "rows": row_count,
                "columns": schema_names,
                "note": "Big table mode: detailed stats skipped for performance"
            }
        except Exception as e:
            return {"exists": True, "error": str(e)}
    
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
                logger.info("✓ 表文件压缩完成")
            
            # 【新增】创建标量索引 (Scalar Index) 以加速过滤查询
            if hasattr(table, 'create_scalar_index'):
                schema_names = table.schema.names
                
                # 针对 trade_date 创建索引 (加速范围查询)
                date_col = None
                if 'trade_date' in schema_names: date_col = 'trade_date'
                elif 'date' in schema_names: date_col = 'date'
                
                if date_col:
                    logger.info(f"正在为 {self.table_name} 创建日期索引 ({date_col})...")
                    try:
                        table.create_scalar_index(date_col)
                        logger.info(f"✓ 日期索引创建完成: {date_col}")
                    except Exception as idx_err:
                        logger.warning(f"创建一个日期索引失败: {idx_err}")

                # 针对 stock_code 创建索引 (加速精确查询)
                code_col = None
                if 'stock_code' in schema_names: code_col = 'stock_code'
                elif 'code' in schema_names: code_col = 'code'
                
                if code_col:
                    logger.info(f"正在为 {self.table_name} 创建代码索引 ({code_col})...")
                    try:
                        table.create_scalar_index(code_col)
                        logger.info(f"✓ 代码索引创建完成: {code_col}")
                    except Exception as idx_err:
                        logger.warning(f"创建一个代码索引失败: {idx_err}")

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

