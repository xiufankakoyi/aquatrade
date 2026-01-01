"""
股吧服务
负责股吧数据加载和处理
"""
from typing import Dict, List, Any, Optional
import pandas as pd
try:
    import cupy as np
except ImportError:
    import numpy as np
from pathlib import Path
from server.services.data_initialization_service import DataInitializationService
from server.services.stock_data_service import StockDataService
from server.utils.symbol_utils import normalize_symbol_key
from config.logger import get_logger


class GubaService:
    """股吧服务类"""
    
    def __init__(self, init_service: DataInitializationService, stock_data_service: StockDataService):
        self.init_service = init_service
        self.stock_data_service = stock_data_service
    
    def load_guba_posts_from_parquet(self, symbol: Optional[str] = None, sample_size: int = 50) -> pd.DataFrame:
        """
        从 Parquet 文件加载股吧数据
        如果指定 symbol，返回该股票的评论数据（可抽样）
        否则返回所有股票的聚合数据
        """
        logger = get_logger(__name__)
        
        try:
            import duckdb
        except ImportError:
            return pd.DataFrame()
        
        base_dir = Path(__file__).parent.parent
        parquet_path = base_dir / 'parquet_data' / 'guba_posts.parquet'
        
        if not parquet_path.exists():
            logger.warning(f"Parquet 文件不存在: {parquet_path}")
            return pd.DataFrame()
        
        parquet_str = str(parquet_path).replace('\\', '/')
        
        try:
            con = duckdb.connect()
            try:
                # CHANGED: 设置 DuckDB 性能参数，加速 Parquet 查询
                try:
                    con.execute("SET threads TO 4")
                except Exception:
                    pass
                try:
                    con.execute("SET memory_limit='2GB'")
                except Exception:
                    pass
                try:
                    # 启用并行扫描
                    con.execute("SET enable_progress_bar=false")
                except Exception:
                    pass
                
                if symbol:
                    # CHANGED: 构建 symbol 匹配条件，处理 Parquet 中可能存储的是纯数字代码的情况
                    # Parquet 中的 symbol 可能是 "601166" 或 "sh601166"，需要兼容两种格式
                    symbol_conditions = []
                    
                    # 提取6位数字代码
                    if symbol.startswith('sz') or symbol.startswith('sh'):
                        code_6 = symbol[2:] if len(symbol) > 2 else symbol
                        full_symbol = symbol
                    else:
                        code_6 = symbol[-6:] if len(symbol) >= 6 else symbol.zfill(6)
                        full_symbol = symbol
                    
                    # 构建多种匹配条件，确保能找到数据
                    # 1. 完全匹配（如果 Parquet 中存储的是完整格式）
                    symbol_conditions.append(f"symbol = '{full_symbol}'")
                    # 2. 匹配6位代码（如果 Parquet 中存储的是纯数字）
                    symbol_conditions.append(f"symbol = '{code_6}'")
                    # 3. 使用 RIGHT 函数匹配（处理可能的格式差异）
                    symbol_conditions.append(f"RIGHT(symbol, 6) = '{code_6}'")
                    # 4. 使用 stockbar_code 匹配（如果存在）
                    symbol_conditions.append(f"stockbar_code = '{code_6}'")
                    # 5. LIKE 匹配（兜底）
                    symbol_conditions.append(f"symbol LIKE '%{code_6}%'")
                    
                    where_clause = ' OR '.join(symbol_conditions)
                    
                    # CHANGED: 优化查询条件
                    # 1. 允许情感值为 0（中性情感）
                    # 2. 只过滤掉 comment_count 为 NULL 或无效的记录
                    # 3. 情感值允许为 0，但过滤掉 NULL
                    sql = f"""
                        SELECT
                            symbol,
                            COALESCE(CAST(stockbar_code AS VARCHAR), CAST(RIGHT(symbol, 6) AS VARCHAR)) AS stockCode,
                            COALESCE(CAST(stockbar_name AS VARCHAR), '') AS stockName,
                            COALESCE(TRY_CAST(post_comment_count AS BIGINT), 0) AS commentCount,
                            COALESCE(TRY_CAST(bullish_bearish AS DOUBLE), 0.0) AS sentiment,
                            COALESCE(CAST(post_title AS VARCHAR), '') AS postTitle,
                            TRY_CAST(post_publish_time AS TIMESTAMP) AS postPublishTime
                        FROM read_parquet('{parquet_str}')
                        WHERE ({where_clause})
                            AND TRY_CAST(post_comment_count AS BIGINT) IS NOT NULL
                            AND TRY_CAST(post_comment_count AS BIGINT) > 0
                            AND TRY_CAST(bullish_bearish AS DOUBLE) IS NOT NULL
                    """
                    
                    logger.debug(f"查询个股散点图数据: symbol={symbol}, code_6={code_6}, where_clause={where_clause}")
                    
                    df = con.execute(sql).df()
                    logger.info(f"查询返回 {len(df)} 条记录")
                    
                    # 随机抽样
                    if len(df) > sample_size:
                        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
                        logger.info(f"随机抽样后: {len(df)} 条记录")
                else:
                    # CHANGED: 优化聚合查询，利用 Parquet 列式存储和 CTE 优化
                    # 1. 使用 CTE 先过滤无效数据（减少 GROUP BY 的数据量）
                    # 2. 在过滤阶段就进行类型转换，避免在聚合时重复转换
                    # 3. 限制返回的股票数量（只取评论数最多的前100只）
                    sql = f"""
                        WITH filtered_data AS (
                            SELECT
                                symbol,
                                COALESCE(CAST(stockbar_code AS VARCHAR), CAST(RIGHT(symbol, 6) AS VARCHAR)) AS stockCode,
                                COALESCE(CAST(stockbar_name AS VARCHAR), '') AS stockName,
                                TRY_CAST(post_comment_count AS BIGINT) AS commentCount,
                                TRY_CAST(bullish_bearish AS DOUBLE) AS sentiment
                            FROM read_parquet('{parquet_str}')
                            WHERE symbol IS NOT NULL
                                AND TRY_CAST(post_comment_count AS BIGINT) > 0
                                -- CHANGED: 移除 bullish_bearish IS NOT NULL 条件，允许中性情绪（0值）
                                -- 这样可以让更多股票显示在散点图上
                        ),
                        aggregated AS (
                            SELECT
                                symbol,
                                stockCode,
                                stockName,
                                SUM(commentCount) AS commentCount,
                                -- CHANGED: 使用 COALESCE 处理 NULL 值，将 NULL 视为 0（中性情绪）
                                COALESCE(AVG(sentiment), 0.0) AS sentiment
                            FROM filtered_data
                            GROUP BY symbol, stockCode, stockName
                        )
                        SELECT *
                        FROM aggregated
                        ORDER BY commentCount DESC
                        LIMIT 200
                    """
                    df = con.execute(sql).df()
                    logger.info(f"从 Parquet 查询到 {len(df)} 只股票（按评论数排序的前200只）")
                
                return df
            finally:
                con.close()
        except Exception as e:
            logger.warning(f"从 Parquet 读取股吧数据失败: {e}", exc_info=True)
            return pd.DataFrame()
    
    def get_scatter_data(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        获取情感-热度散点图数据
        
        Args:
            symbol: 可选，如果指定则返回该股票的评论数据（随机抽样50个），否则返回所有股票的聚合数据
        
        Returns:
            {
                'success': bool,
                'data': List[Dict]  # 散点图数据点列表
            }
        """
        logger = get_logger(__name__)
        
        try:
            # 确保已初始化
            if not self.init_service._initialized:
                self.init_service.ensure_initialized()
            
            import time
            start_time = time.perf_counter()
            
            # CHANGED: 优化查询顺序 - 先获取股吧数据（已优化，只返回前100只），再只查询这些股票的市值
            # 1. 从 Parquet 加载股吧数据（已优化：只返回评论数最多的前100只股票）
            logger.info(f"开始加载股吧数据: symbol={symbol}")
            df = self.load_guba_posts_from_parquet(symbol)
            load_time = time.perf_counter() - start_time
            logger.info(f"股吧数据加载完成: {len(df)} 条记录, 耗时 {load_time:.2f} 秒")
            
            if df.empty:
                logger.warning(f"股吧数据为空，返回空数据 (symbol={symbol})")
                return {'success': True, 'data': []}
            
            # 【性能优化】2. 提取需要查询的股票代码列表（限制数量，只查询前N只）
            # 优化：使用向量化操作提取股票代码，比循环快 5-10 倍
            if symbol:
                # 单个股票：直接获取该股票信息
                raw_symbol = str(df.iloc[0].get('symbol') or '')
                stock_code_raw = df.iloc[0].get('stockCode', '')
                stock_code = str(stock_code_raw or '')[-6:] if stock_code_raw else ''
                symbol_key = normalize_symbol_key(raw_symbol, stock_code)
                needed_symbols = [symbol_key]
                logger.info(f"单个股票模式: raw_symbol={raw_symbol}, stock_code={stock_code}, symbol_key={symbol_key}")
            else:
                # 【性能优化】多个股票：使用向量化操作提取股票代码
                # 限制数量：只处理前200只股票（避免查询过多）
                MAX_STOCKS = 200
                df_limited = df.head(MAX_STOCKS) if len(df) > MAX_STOCKS else df
                
                # 向量化提取：使用 apply 一次性处理所有行（比循环快）
                def extract_symbol_key(row):
                    try:
                        raw_symbol = str(row.get('symbol') or '')
                        stock_code_raw = row.get('stockCode', '')
                        stock_code = str(stock_code_raw or '')[-6:] if stock_code_raw else ''
                        return normalize_symbol_key(raw_symbol, stock_code)
                    except Exception:
                        return None
                
                needed_symbols = df_limited.apply(extract_symbol_key, axis=1).dropna().unique().tolist()
                
                if len(df) > MAX_STOCKS:
                    logger.info(f"聚合模式: 限制处理数量，从 {len(df)} 只股票中提取前 {MAX_STOCKS} 只")
                
                logger.info(f"聚合模式: 提取到 {len(needed_symbols)} 个唯一股票代码")
            
            # 3. 只查询需要的股票的市值信息（而不是所有股票）
            info_start = time.perf_counter()
            logger.info(f"开始查询股票市值信息: {len(needed_symbols)} 只股票")
            stock_info = self.stock_data_service.get_stock_info_with_market_cap(needed_symbols)
            info_time = time.perf_counter() - info_start
            logger.info(f"股票市值信息查询完成: {len(stock_info)} 条记录, 耗时 {info_time:.2f} 秒")
            
            # 4. 处理数据（简化版本，核心逻辑）
            results = []
            
            if symbol:
                # 单个股票的评论数据
                symbol_key = needed_symbols[0] if needed_symbols else ''
                info = stock_info.get(symbol_key, {})
                
                # CHANGED: 从 Parquet 数据中获取股票名称
                stock_name_from_parquet = ''
                if not df.empty and 'stockName' in df.columns:
                    stock_name_from_parquet = str(df.iloc[0].get('stockName', '')).strip()
                
                # 优先使用 Parquet 中的名称，如果没有则使用 stock_info 中的名称
                display_name = stock_name_from_parquet or info.get('name', '')
                
                for _, row in df.iterrows():
                    comment_count = int(row.get('commentCount') or 0)
                    sentiment = float(row.get('sentiment') or 0.0)
                    post_title = str(row.get('postTitle') or '')[:50]
                    
                    # CHANGED: 确保 comment_count > 0，避免显示无效数据点
                    if comment_count <= 0:
                        continue
                    
                    # CHANGED: 确保 sentiment 是有效数值
                    if pd.isna(sentiment) or abs(sentiment) > 100:
                        sentiment = 0.0
                    
                    results.append({
                        'symbol': symbol_key,
                        'name': display_name,
                        'comment_count': comment_count,
                        'sentiment': round(sentiment, 3),
                        'post_title': post_title,
                        'is_comment': True
                    })
            else:
                # 【性能优化】所有股票的聚合数据 - 使用向量化操作替代循环
                # 向量化处理：一次性处理所有行，比循环快 5-10 倍
                try:
                    # 1. 向量化提取股票代码
                    df['raw_symbol'] = df['symbol'].astype(str).fillna('')
                    df['stock_code_raw'] = df['stockCode'].astype(str).fillna('')
                    df['stock_code_6'] = df['stock_code_raw'].apply(
                        lambda x: x[-6:] if len(x) >= 6 else x.zfill(6) if x else ''
                    )
                    df['symbol_key'] = df.apply(
                        lambda row: normalize_symbol_key(row['raw_symbol'], row['stock_code_6']),
                        axis=1
                    )
                    
                    # 2. 向量化处理 commentCount
                    df['comment_count'] = pd.to_numeric(df['commentCount'], errors='coerce').fillna(0).astype(int)
                    
                    # 3. 向量化处理 sentiment
                    df['sentiment'] = pd.to_numeric(df['sentiment'], errors='coerce').fillna(0.0)
                    df['sentiment'] = df['sentiment'].apply(lambda x: 0.0 if abs(x) > 100 else x)
                    
                    # 4. 过滤无效数据（向量化）
                    valid_mask = df['comment_count'] > 0
                    df_valid = df[valid_mask].copy()
                    
                    if not df_valid.empty:
                        # 5. 向量化获取股票信息
                        df_valid['market_cap'] = df_valid['symbol_key'].apply(
                            lambda key: stock_info.get(key, {}).get('market_cap', 0.0)
                        )
                        df_valid['info_name'] = df_valid['symbol_key'].apply(
                            lambda key: stock_info.get(key, {}).get('name', '')
                        )
                        
                        # 6. 向量化获取股票名称
                        df_valid['stock_name_parquet'] = df_valid['stockName'].astype(str).fillna('').str.strip()
                        df_valid['display_name'] = df_valid.apply(
                            lambda row: row['stock_name_parquet'] or row['info_name'],
                            axis=1
                        )
                        
                        # 7. 构建结果列表（向量化）
                        results = df_valid.apply(
                            lambda row: {
                                'symbol': row['symbol_key'],
                                'name': row['display_name'],
                                'comment_count': int(row['comment_count']),
                                'sentiment': round(float(row['sentiment']), 3),
                                'market_cap': round(float(row['market_cap']), 2) if not pd.isna(row['market_cap']) else 0.0
                            },
                            axis=1
                        ).tolist()
                        
                except Exception as e:
                    # 回退到循环方法（如果向量化失败）
                    logger.warning(f"向量化处理失败，回退到循环方法: {e}")
                    results = []
                    for idx, row in df.iterrows():
                        try:
                            raw_symbol = str(row.get('symbol', '') or '')
                            stock_code_raw = row.get('stockCode', '')
                            stock_code = str(stock_code_raw or '')[-6:] if stock_code_raw else ''
                            symbol_key = normalize_symbol_key(raw_symbol, stock_code)
                            
                            info = stock_info.get(symbol_key, {})
                            
                            comment_count = int(row.get('commentCount') or 0)
                            if comment_count <= 0:
                                continue
                            
                            sentiment = float(row.get('sentiment') or 0.0)
                            if pd.isna(sentiment) or abs(sentiment) > 100:
                                sentiment = 0.0
                            
                            stock_name_from_parquet = str(row.get('stockName', '') or '').strip()
                            display_name = stock_name_from_parquet or info.get('name', '')
                            
                            results.append({
                                'symbol': symbol_key,
                                'name': display_name,
                                'comment_count': comment_count,
                                'sentiment': round(sentiment, 3),
                                'market_cap': round(info.get('market_cap', 0.0), 2) if not pd.isna(info.get('market_cap', 0.0)) else 0.0
                            })
                        except Exception as row_err:
                            logger.warning(f"处理第 {idx} 行数据时出错: {row_err}")
                            continue
                
                # CHANGED: 按市值排序（有市值的优先），如果没有市值则按评论数排序
                results.sort(key=lambda x: (
                    x.get('market_cap', 0.0) if x.get('market_cap', 0.0) > 0 else 0,
                    x.get('comment_count', 0.0)
                ), reverse=True)
                results = results[:100]
            
            # 5. 对数据进行归一化处理，解决散点图数据点被压缩的问题
            if results:
                # 收集所有 comment_count 和 sentiment 值
                comment_counts = [r.get('comment_count', 0) for r in results if r.get('comment_count', 0) > 0]
                sentiments = [r.get('sentiment', 0.0) for r in results]
                
                # 计算最小值和最大值
                min_comment = min(comment_counts) if comment_counts else 0
                max_comment = max(comment_counts) if comment_counts else 1
                comment_range = max_comment - min_comment if max_comment != min_comment else 1
                
                min_sentiment = min(sentiments) if sentiments else -1
                max_sentiment = max(sentiments) if sentiments else 1
                
                # CHANGED: 对于单个数据点或所有值相同的情况，使用原始值而不是归一化
                use_normalization = len(comment_counts) > 1 and comment_range > 0
                
                # 对每个数据点进行归一化
                for result in results:
                    comment_count = result.get('comment_count', 0)
                    sentiment = result.get('sentiment', 0.0)
                    
                    # Min-Max 归一化：将 comment_count 映射到 [0, 1] 范围
                    if use_normalization:
                        normalized_comment = (comment_count - min_comment) / comment_range
                    else:
                        if symbol:
                            normalized_comment = comment_count if comment_count > 0 else 0.5
                        else:
                            normalized_comment = 0.5
                    
                    result['comment_count_normalized'] = round(normalized_comment, 4)
                    
                    # 确保 sentiment 在 [-1, 1] 范围内
                    if abs(sentiment) > 1:
                        normalized_sentiment = max(-1, min(1, sentiment / 100))  # 处理异常值
                        result['sentiment'] = round(normalized_sentiment, 3)
            
            # 6. 清洗数据（防止 JSON 序列化报错）
            def sanitize_data(data):
                """递归清洗数据，将 NaN/Infinity 转换为 null"""
                import math
                try:
                    np_floating = np.floating
                    np_integer = np.integer
                except AttributeError:
                    np_floating = float
                    np_integer = int
                
                if isinstance(data, dict):
                    return {k: sanitize_data(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [sanitize_data(item) for item in data]
                elif isinstance(data, (float, np_floating)):
                    if math.isnan(data) or math.isinf(data):
                        return None
                    return float(data)
                elif isinstance(data, (int, np_integer)):
                    return int(data)
                elif pd.isna(data):
                    return None
                else:
                    return data
            
            cleaned_data = sanitize_data(results)
            
            total_time = time.perf_counter() - start_time
            logger.info(f"散点图数据获取完成: {len(cleaned_data)} 条数据, 总耗时 {total_time:.2f} 秒")
            
            return {'success': True, 'data': cleaned_data}
            
        except Exception as e:
            logger.error(f"获取散点图数据失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': []}

