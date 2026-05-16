"""
K线形态相似度匹配服务

编排归一化→粗筛→精筛→模式增强→结果输出全流程，
管理离线预处理缓存和后续K线走势查询。
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import polars as pl
from loguru import logger

from core.similarity import (
    SimilarityEngine,
    generate_sliding_windows,
    normalize_kline,
)
from data_svc.storage.lancedb_reader import LanceDBDataReader, get_lancedb_reader

# 尝试导入 SkeletonMatcher v2
try:
    from core.similarity.pattern_enhancer_v2 import SkeletonMatcher, SceneConfig
except ImportError:
    SkeletonMatcher = None
    SceneConfig = None
    logger.warning("SkeletonMatcher not available, falling back to DTW")


class SimilarityService:
    """
    K线形态相似度匹配服务

    编排归一化→粗筛→精筛→模式增强→结果输出全流程，
    管理离线预处理缓存和后续K线走势查询。
    """

    def __init__(self):
        """初始化服务，设置缓存和引擎"""
        self._preprocess_cache: dict[int, list[dict]] = {}
        self._preprocess_status: dict = {
            "preprocessed": False,
            "window_sizes": [],
            "cache_sizes": {},
            "last_preprocess_time": None,
        }
        self._reader: Optional[LanceDBDataReader] = None

    def _get_reader(self) -> LanceDBDataReader:
        """获取LanceDB数据读取器（延迟初始化）"""
        if self._reader is None:
            self._reader = get_lancedb_reader()
        return self._reader

    def match(
        self,
        stock_code: str,
        window_size: int = 20,
        top_n: int = 10,
        pattern_type: str = None,
        corr_threshold: float = 0.85,
        subsequent_days: int = 10,
        algorithm: str = "dtw",
        scene: str = "default",
    ) -> list[dict]:
        """
        执行K线形态相似度匹配

        Args:
            stock_code: 目标股票代码
            window_size: 历史时间窗口大小（K线根数）
            top_n: 返回的最大匹配结果数
            pattern_type: 模式增强类型，None/"breakout_volume"/"limit_break"/"n_shape"
            corr_threshold: 相关系数粗筛阈值
            subsequent_days: 后续走势展示天数
            algorithm: 匹配算法，"dtw"（默认）或 "skeleton"（骨架算法v2）
            scene: 场景配置，用于 skeleton 算法

        Returns:
            匹配结果列表，每个dict包含:
            - stock_code: 匹配的股票代码
            - start_date: 匹配片段开始日期
            - end_date: 匹配片段结束日期
            - similarity_score: 相似度得分
            - subsequent_kline: 后续K线数据列表
            - enhanced_score: 增强得分（如有模式增强）
            - corr_score: 相关系数（如有）
            - structure_score: 结构得分（skeleton算法）
            - rhythm_score: 节奏得分（skeleton算法）
            - ma_fit_score: 均线拟合得分（skeleton算法）
        """
        if algorithm == "skeleton":
            return self._match_skeleton(
                stock_code=stock_code,
                window_size=window_size,
                top_n=top_n,
                pattern_type=pattern_type,
                subsequent_days=subsequent_days,
                scene=scene,
            )

        reader = self._get_reader()

        df = reader.read(stock_code)
        if df.is_empty():
            logger.warning(f"SimilarityService: stock {stock_code} not found")
            return []

        df = df.sort("trade_date", descending=True)
        if df.height < window_size:
            logger.warning(
                f"SimilarityService: stock {stock_code} has only {df.height} rows, "
                f"need {window_size}"
            )
            return []

        template_df = df.head(window_size).sort("trade_date")
        template_close = template_df["close"].cast(pl.Float64).to_numpy()
        template_normalized = normalize_kline(template_close)

        candidate_windows = self._get_candidate_windows(window_size)
        if not candidate_windows:
            logger.info("SimilarityService: no cached windows, computing on-the-fly")
            candidate_windows = self._compute_candidate_windows(window_size)

        candidate_windows = [
            w for w in candidate_windows
            if w.get("metadata", {}).get("stock_code") != stock_code
        ]

        if not candidate_windows:
            logger.warning("SimilarityService: no candidate windows available")
            return []

        engine = SimilarityEngine(
            corr_threshold=corr_threshold,
            pattern_type=pattern_type,
        )
        matched = engine.match(template_normalized, candidate_windows, top_n=top_n)

        # 批量获取股票名称
        stock_codes = [item.get("stock_code") for item in matched]
        stock_name_map = self._get_stock_names(stock_codes)

        results = []
        for item in matched:
            result = dict(item)
            start_date = result.get("start_date")
            end_date = result.get("end_date")
            result_stock_code = result.get("stock_code")

            # 添加股票名称
            result["stock_name"] = stock_name_map.get(result_stock_code, "")

            if end_date and result_stock_code:
                result["subsequent_kline"] = self._get_subsequent_kline(
                    result_stock_code, end_date, subsequent_days
                )
                # 添加匹配段K线数据
                result["matched_kline"] = self._get_matched_kline(
                    result_stock_code, start_date, end_date
                )
                # 添加前序K线数据（前10天）
                result["preceding_kline"] = self._get_preceding_kline(
                    result_stock_code, start_date, days=10
                )
            else:
                result["subsequent_kline"] = []
                result["matched_kline"] = []
                result["preceding_kline"] = []
            results.append(result)

        logger.info(
            f"SimilarityService: matched {len(results)} results for "
            f"{stock_code} (window={window_size}, top_n={top_n})"
        )
        return results

    def preprocess(self, window_size: int = 20) -> dict:
        """
        离线预处理全市场K线片段

        对近三年全市场数据按指定窗口大小生成归一化特征缓存。

        Args:
            window_size: 滑动窗口大小

        Returns:
            预处理结果统计信息
        """
        reader = self._get_reader()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")

        logger.info(
            f"SimilarityService: preprocessing window_size={window_size}, "
            f"date_range={start_date}~{end_date}"
        )

        df = reader.read(
            None,
            start_date=start_date,
            end_date=end_date,
            fields=["stock_code", "trade_date", "close", "volume"],
        )

        if df.is_empty():
            logger.warning("SimilarityService: no data available for preprocessing")
            return {
                "window_size": window_size,
                "total_windows": 0,
                "symbols_count": 0,
            }

        windows = generate_sliding_windows(df, window_size)

        self._preprocess_cache[window_size] = windows
        symbols_count = len(set(
            w["metadata"]["stock_code"] for w in windows
        ))

        self._preprocess_status["preprocessed"] = True
        if window_size not in self._preprocess_status["window_sizes"]:
            self._preprocess_status["window_sizes"].append(window_size)
        self._preprocess_status["cache_sizes"][str(window_size)] = len(windows)
        self._preprocess_status["last_preprocess_time"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        logger.info(
            f"SimilarityService: preprocessing done, "
            f"{len(windows)} windows, {symbols_count} symbols"
        )

        return {
            "window_size": window_size,
            "total_windows": len(windows),
            "symbols_count": symbols_count,
        }

    def get_status(self) -> dict:
        """
        获取预处理状态

        Returns:
            状态信息dict，包含:
            - preprocessed: 是否已预处理
            - window_sizes: 已缓存的窗口大小列表
            - cache_sizes: 各窗口大小的缓存条目数
            - last_preprocess_time: 上次预处理时间
        """
        return dict(self._preprocess_status)

    def _get_subsequent_kline(
        self,
        stock_code: str,
        end_date: str,
        days: int,
    ) -> list[dict]:
        """
        查询匹配片段后续N根K线的真实走势

        Args:
            stock_code: 股票代码
            end_date: 匹配片段结束日期
            days: 需要查询的后续天数

        Returns:
            后续K线数据列表，每个dict包含 trade_date, open, high, low, close, volume
            若后续数据不足，返回实际可用的数据
        """
        reader = self._get_reader()

        try:
            parsed_end = datetime.strptime(end_date[:10], "%Y-%m-%d")
            search_start = (parsed_end + timedelta(days=1)).strftime("%Y-%m-%d")
            search_end = (parsed_end + timedelta(days=days * 3)).strftime("%Y-%m-%d")
        except ValueError:
            search_start = None
            search_end = None

        df = reader.read(
            stock_code,
            start_date=search_start,
            end_date=search_end,
            fields=["trade_date", "open", "high", "low", "close", "volume"],
        )

        if df.is_empty():
            return []

        df = df.sort("trade_date").head(days)

        kline_fields = ["trade_date", "open", "high", "low", "close", "volume"]
        available_fields = [f for f in kline_fields if f in df.columns]

        results = []
        for row in df.iter_rows(named=True):
            item = {}
            for field in available_fields:
                val = row[field]
                if isinstance(val, (np.integer,)):
                    val = int(val)
                elif isinstance(val, (np.floating,)):
                    val = float(val)
                elif hasattr(val, "isoformat"):
                    val = val.isoformat()[:10]
                else:
                    val = str(val)
                item[field] = val
            results.append(item)

        return results

    def _get_subsequent_klines_batch(
        self,
        stock_codes: list,
        end_dates: list,
        days: int,
    ) -> dict:
        """
        批量获取多个匹配片段的后续K线

        Args:
            stock_codes: 股票代码列表
            end_dates: 对应的结束日期列表
            days: 需要查询的后续天数

        Returns:
            dict，key 为 (stock_code, end_date) 元组，value 为后续K线列表
        """
        if not stock_codes or not end_dates:
            return {}

        reader = self._get_reader()
        result = {}
        max_days = days * 3

        for stock_code, end_date in zip(stock_codes, end_dates):
            if not stock_code or not end_date:
                result[(stock_code, end_date)] = []
                continue

            try:
                parsed_end = datetime.strptime(end_date[:10], "%Y-%m-%d")
                search_start = (parsed_end + timedelta(days=1)).strftime("%Y-%m-%d")
                search_end = (parsed_end + timedelta(days=max_days)).strftime("%Y-%m-%d")
            except ValueError:
                result[(stock_code, end_date)] = []
                continue

            df = reader.read(
                stock_code,
                start_date=search_start,
                end_date=search_end,
                fields=["trade_date", "open", "high", "low", "close", "volume"],
            )

            if df.is_empty():
                result[(stock_code, end_date)] = []
                continue

            df = df.sort("trade_date").head(days)

            kline_fields = ["trade_date", "open", "high", "low", "close", "volume"]
            available_fields = [f for f in kline_fields if f in df.columns]

            results = []
            for row in df.iter_rows(named=True):
                item = {}
                for field in available_fields:
                    val = row[field]
                    if isinstance(val, (np.integer, np.floating)):
                        val = float(val)
                    elif hasattr(val, 'isoformat'):
                        val = val.isoformat()[:10]
                    else:
                        val = str(val)
                    item[field] = val
                results.append(item)

            result[(stock_code, end_date)] = results

        return result

    def _get_matched_kline(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """
        查询匹配段的K线数据

        Args:
            stock_code: 股票代码
            start_date: 匹配片段开始日期
            end_date: 匹配片段结束日期

        Returns:
            匹配段K线数据列表，每个dict包含 trade_date, open, high, low, close, volume
        """
        reader = self._get_reader()

        df = reader.read(
            stock_code,
            start_date=start_date,
            end_date=end_date,
            fields=["trade_date", "open", "high", "low", "close", "volume"],
        )

        if df.is_empty():
            return []

        df = df.sort("trade_date")

        kline_fields = ["trade_date", "open", "high", "low", "close", "volume"]
        available_fields = [f for f in kline_fields if f in df.columns]

        results = []
        for row in df.iter_rows(named=True):
            item = {}
            for field in available_fields:
                val = row[field]
                if isinstance(val, (np.integer,)):
                    val = int(val)
                elif isinstance(val, (np.floating,)):
                    val = float(val)
                elif hasattr(val, "isoformat"):
                    val = val.isoformat()[:10]
                else:
                    val = str(val)
                item[field] = val
            results.append(item)

        return results

    def _get_preceding_kline(
        self,
        stock_code: str,
        start_date: str,
        days: int = 10,
    ) -> list[dict]:
        """
        查询匹配片段前序N根K线数据

        Args:
            stock_code: 股票代码
            start_date: 匹配片段开始日期
            days: 需要查询的前序天数（默认10天）

        Returns:
            前序K线数据列表，每个dict包含 trade_date, open, high, low, close, volume
        """
        reader = self._get_reader()

        try:
            # 处理可能的日期格式
            if isinstance(start_date, str) and len(start_date) >= 10:
                date_str = start_date[:10]
            else:
                date_str = str(start_date)[:10]
            parsed_start = datetime.strptime(date_str, "%Y-%m-%d")
            # 多查一些天数确保有足够数据（考虑节假日）
            search_start = (parsed_start - timedelta(days=days * 3)).strftime("%Y-%m-%d")
            search_end = (parsed_start - timedelta(days=1)).strftime("%Y-%m-%d")
        except (ValueError, TypeError) as e:
            logger.warning(f"[_get_preceding_kline] 日期解析失败: {start_date}, error: {e}")
            return []

        logger.debug(f"[_get_preceding_kline] {stock_code}: 查询 {search_start} ~ {search_end}")

        df = reader.read(
            stock_code,
            start_date=search_start,
            end_date=search_end,
            fields=["trade_date", "open", "high", "low", "close", "volume"],
        )

        logger.debug(f"[_get_preceding_kline] {stock_code}: 查询到 {len(df)} 条数据")

        if df.is_empty():
            return []

        # 排序并取最后N条
        df = df.sort("trade_date").tail(days)

        kline_fields = ["trade_date", "open", "high", "low", "close", "volume"]
        available_fields = [f for f in kline_fields if f in df.columns]

        results = []
        for row in df.iter_rows(named=True):
            item = {}
            for field in available_fields:
                val = row[field]
                if isinstance(val, (np.integer,)):
                    val = int(val)
                elif isinstance(val, (np.floating,)):
                    val = float(val)
                elif hasattr(val, "isoformat"):
                    val = val.isoformat()[:10]
                else:
                    val = str(val)
                item[field] = val
            results.append(item)

        logger.debug(f"[_get_preceding_kline] {stock_code}: 返回 {len(results)} 条结果")
        return results

    def _get_stock_names(self, stock_codes: list) -> dict:
        """
        批量获取股票名称

        Args:
            stock_codes: 股票代码列表

        Returns:
            dict，key 为股票代码，value 为股票名称
        """
        if not stock_codes:
            return {}

        # 去重
        unique_codes = list(set([code for code in stock_codes if code]))
        if not unique_codes:
            return {}

        reader = self._get_reader()
        result = {}

        try:
            # 尝试从 stock_info 表获取名称
            df = reader.read(
                None,  # 读取所有股票
                fields=["stock_code", "stock_name"],
            )

            if not df.is_empty() and "stock_code" in df.columns and "stock_name" in df.columns:
                for row in df.iter_rows(named=True):
                    code = row.get("stock_code")
                    name = row.get("stock_name")
                    if code and name:
                        result[str(code)] = str(name)
        except Exception as e:
            logger.warning(f"获取股票名称失败: {e}")

        return result

    def _get_matched_klines_batch(
        self,
        stock_codes: list,
        start_dates: list,
        end_dates: list,
    ) -> dict:
        """
        批量获取多个匹配片段的K线数据

        Args:
            stock_codes: 股票代码列表
            start_dates: 对应的开始日期列表
            end_dates: 对应的结束日期列表

        Returns:
            dict，key 为 (stock_code, end_date) 元组，value 为匹配段K线列表
        """
        if not stock_codes or not start_dates or not end_dates:
            return {}

        reader = self._get_reader()
        result = {}

        for stock_code, start_date, end_date in zip(stock_codes, start_dates, end_dates):
            if not stock_code or not start_date or not end_date:
                result[(stock_code, end_date)] = []
                continue

            df = reader.read(
                stock_code,
                start_date=start_date,
                end_date=end_date,
                fields=["trade_date", "open", "high", "low", "close", "volume"],
            )

            if df.is_empty():
                result[(stock_code, end_date)] = []
                continue

            df = df.sort("trade_date")

            kline_fields = ["trade_date", "open", "high", "low", "close", "volume"]
            available_fields = [f for f in kline_fields if f in df.columns]

            results = []
            for row in df.iter_rows(named=True):
                item = {}
                for field in available_fields:
                    val = row[field]
                    if isinstance(val, (np.integer, np.floating)):
                        val = float(val)
                    elif hasattr(val, 'isoformat'):
                        val = val.isoformat()[:10]
                    else:
                        val = str(val)
                    item[field] = val
                results.append(item)

            result[(stock_code, end_date)] = results

        return result

    def _get_candidate_windows(self, window_size: int) -> list[dict]:
        """获取指定窗口大小的缓存候选窗口"""
        return self._preprocess_cache.get(window_size, [])

    def _compute_candidate_windows(self, window_size: int) -> list[dict]:
        """实时计算候选窗口"""
        reader = self._get_reader()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        df = reader.read(
            None,
            start_date=start_date,
            end_date=end_date,
            fields=["stock_code", "trade_date", "close", "volume"],
        )

        if df.is_empty():
            return []

        return generate_sliding_windows(df, window_size)

    def _match_skeleton(
        self,
        stock_code: str,
        window_size: int = 20,
        top_n: int = 10,
        pattern_type: str = None,
        subsequent_days: int = 10,
        scene: str = "default",
    ) -> list[dict]:
        """
        使用骨架算法v2执行K线形态相似度匹配

        Args:
            stock_code: 目标股票代码
            window_size: 历史时间窗口大小（K线根数）
            top_n: 返回的最大匹配结果数
            pattern_type: 模式增强类型（用于自动推导 scene）
            subsequent_days: 后续走势展示天数
            scene: 场景配置

        Returns:
            匹配结果列表，每个dict包含:
            - stock_code: 匹配的股票代码
            - start_date: 匹配片段开始日期
            - end_date: 匹配片段结束日期
            - similarity_score: 相似度得分（即 total_score）
            - structure_score: 结构得分
            - rhythm_score: 节奏得分
            - ma_fit_score: 均线拟合得分
            - subsequent_kline: 后续K线数据列表
        """
        if SkeletonMatcher is None or SceneConfig is None:
            logger.error("SkeletonMatcher not available, cannot use skeleton algorithm")
            return []

        # 自动推导 scene
        if scene == "default" and pattern_type is not None:
            scene_mapping = {
                "breakout_volume": "breakout_volume",
                "limit_break": "limit_break",
                "n_shape": "n_shape",
            }
            scene = scene_mapping.get(pattern_type, "default")

        reader = self._get_reader()

        # 读取模板股票数据
        df = reader.read(stock_code)
        if df.is_empty():
            logger.warning(f"SimilarityService: stock {stock_code} not found")
            return []

        df = df.sort("trade_date", descending=True)
        if df.height < window_size:
            logger.warning(
                f"SimilarityService: stock {stock_code} has only {df.height} rows, "
                f"need {window_size}"
            )
            return []

        # 构建模板 klines dict（需要完整 OHLCV 字段）
        template_df = df.head(window_size).sort("trade_date")
        template_klines = self._df_to_klines_dict(template_df)

        # 获取候选窗口列表（使用缓存或实时计算）
        candidate_windows = self._get_candidate_windows(window_size)

        # skeleton 算法需要完整 OHLCV 数据，检查缓存是否满足
        needs_full_ohlcv = True
        if candidate_windows:
            sample = candidate_windows[0]
            klines = sample.get("klines", {}) if isinstance(sample, dict) else sample
            needs_full_ohlcv = not all(
                col in klines for col in ["open", "high", "low", "close", "volume"]
            )

        if not candidate_windows or needs_full_ohlcv:
            logger.info("SimilarityService: no valid cached windows for skeleton, computing on-the-fly")
            template_close = np.asarray(template_klines["close"], dtype=np.float64)
            num_seg = 4
            seg_sz = window_size / num_seg
            template_parts = []
            for j in range(num_seg):
                s = int(j * seg_sz)
                e = int((j + 1) * seg_sz)
                seg = template_close[s:e]
                pct = (seg[-1] - seg[0]) / seg[0] if seg[0] != 0 else 0
                if abs(pct) < 0.02:
                    template_parts.append("F")
                elif pct > 0:
                    template_parts.append("U")
                else:
                    template_parts.append("D")
            template_seq = "-".join(template_parts)
            dir_str_to_arr = {"U": 1, "D": -1, "F": 0}
            template_dirs = np.array([dir_str_to_arr.get(d, 0) for d in template_seq.split("-")])
            candidate_windows = self._compute_candidate_windows_skeleton(window_size, template_close, template_dirs)

        # 过滤掉目标股票自身的窗口
        candidate_windows = [
            w for w in candidate_windows
            if w.get("metadata", {}).get("stock_code") != stock_code
        ]

        if not candidate_windows:
            logger.warning("SimilarityService: no candidate windows available")
            return []

        # 构建 SkeletonMatcher 实例
        # 根据窗口大小动态调整 MA 窗口，确保数据足够
        ma_window = min(20, window_size)
        # 降低 min_pct 阈值，让小波动也能被检测到，提高形态匹配精度
        min_pct = 0.015 if window_size <= 10 else 0.02
        matcher = SkeletonMatcher(scene=scene, ma_window=ma_window, min_pct=min_pct, min_bars=1)

        # 执行批量匹配（跳过 Layer 1 因为已在候选生成时过滤）
        matched = matcher.batch_match(
            template_klines, candidate_windows, top_n=top_n * 3, skip_layer1=True
        )

        # 分段趋势一致性过滤：要求候选窗口的各段走势方向与模板完全一致
        template_close = np.asarray(template_klines["close"], dtype=np.float64)
        n = len(template_close)
        if n > 2:
            num_segments = 4
            seg_size = n / num_segments

            # 计算模板各段的涨跌方向
            template_seg_dirs = []
            for seg_idx in range(num_segments):
                s = int(seg_idx * seg_size)
                e = int((seg_idx + 1) * seg_size)
                if e > n:
                    e = n
                if s < e and template_close[s] != 0:
                    pct = (template_close[e-1] - template_close[s]) / abs(template_close[s])
                    if pct > 0.01:
                        template_seg_dirs.append(1)   # 上涨
                    elif pct < -0.01:
                        template_seg_dirs.append(-1)  # 下跌
                    else:
                        template_seg_dirs.append(0)   # 平盘
                else:
                    template_seg_dirs.append(0)

            trend_filtered = []
            for item in matched:
                cand_klines = item.get("klines", {})
                cand_close = np.asarray(cand_klines.get("close", []), dtype=np.float64)
                cn = len(cand_close)

                if cn > 2:
                    cand_seg_dirs = []
                    match_count = 0
                    total_check = min(len(template_seg_dirs), num_segments)

                    for seg_idx in range(total_check):
                        s = int(seg_idx * cn / num_segments)
                        e = int((seg_idx + 1) * cn / num_segments)
                        if e > cn:
                            e = cn
                        if s < e and cand_close[s] != 0:
                            pct = (cand_close[e-1] - cand_close[s]) / abs(cand_close[s])
                            if pct > 0.01:
                                cand_dir = 1
                            elif pct < -0.01:
                                cand_dir = -1
                            else:
                                cand_dir = 0
                        else:
                            cand_dir = 0
                        cand_seg_dirs.append(cand_dir)

                        # 检查方向是否一致（允许平盘匹配任意方向）
                        if (template_seg_dirs[seg_idx] == 0 or
                            cand_dir == 0 or
                            template_seg_dirs[seg_idx] == cand_dir):
                            match_count += 1

                    # 要求至少75%的分段方向一致
                    if match_count >= total_check * 0.75:
                        trend_filtered.append(item)
                else:
                    trend_filtered.append(item)

            matched = trend_filtered

        # 截取 top_n 结果
        matched = matched[:top_n]

        # 构建结果（批量获取后续K线）
        stock_codes = []
        end_dates = []
        for item in matched:
            stock_codes.append(item.get("metadata", {}).get("stock_code"))
            end_dates.append(item.get("metadata", {}).get("end_date"))

        subsequent_map = self._get_subsequent_klines_batch(stock_codes, end_dates, subsequent_days)

        # 批量获取匹配段K线数据
        start_dates = []
        for item in matched:
            start_dates.append(item.get("metadata", {}).get("start_date"))
        matched_kline_map = self._get_matched_klines_batch(stock_codes, start_dates, end_dates)

        # 批量获取股票名称
        stock_name_map = self._get_stock_names(stock_codes)

        results = []
        for item in matched:
            result_stock_code = item.get("metadata", {}).get("stock_code")
            start_date = item.get("metadata", {}).get("start_date")
            end_date = item.get("metadata", {}).get("end_date")

            result = {
                "stock_code": result_stock_code,
                "stock_name": stock_name_map.get(result_stock_code, ""),
                "start_date": start_date,
                "end_date": end_date,
                "similarity_score": item.get("total_score"),
                "structure_score": item.get("structure_score"),
                "rhythm_score": item.get("rhythm_score"),
                "ma_fit_score": item.get("ma_fit_score"),
            }
            key = (result_stock_code, end_date)
            result["subsequent_kline"] = subsequent_map.get(key, [])
            # 添加匹配段K线数据
            result["matched_kline"] = matched_kline_map.get(key, [])
            # 添加前序K线数据（前10天）
            result["preceding_kline"] = self._get_preceding_kline(
                result_stock_code, start_date, days=10
            )
            results.append(result)

        logger.info(
            f"SimilarityService: skeleton matched {len(results)} results for "
            f"{stock_code} (window={window_size}, top_n={top_n}, scene={scene})"
        )
        return results

    def _df_to_klines_dict(self, df: pl.DataFrame) -> dict:
        """
        将 Polars DataFrame 转换为 klines dict

        Args:
            df: 包含 kline 数据的 DataFrame

        Returns:
            klines dict，包含 open/high/low/close/volume 列表
        """
        klines = {}
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                klines[col] = df[col].cast(pl.Float64).to_list()
        return klines

    def _compute_candidate_windows_skeleton(
        self,
        window_size: int,
        template_close: np.ndarray = None,
        template_dirs: np.ndarray = None,
    ) -> list[dict]:
        """
        实时计算候选窗口（用于 skeleton 算法，需要完整 OHLCV 数据）
        
        两阶段优化策略：
        1. 第一阶段：只读取 stock_code + close 列，用 LazyFrame + Streaming 计算方向预过滤
        2. 第二阶段：只对候选股票读取完整 OHLCV 数据

        Args:
            window_size: 窗口大小
            template_close: 可选的模板收盘价数组，用于方向预过滤
            template_dirs: 可选的模板方向数组

        Returns:
            候选窗口列表，每个 dict 包含 klines 和 metadata
        """
        reader = self._get_reader()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        if template_dirs is None and template_close is not None:
            template_close = np.asarray(template_close, dtype=np.float64)
            num_seg = 4
            seg_sz = window_size / num_seg
            template_parts = []
            for j in range(num_seg):
                s = int(j * seg_sz)
                e = int((j + 1) * seg_sz)
                seg = template_close[s:e]
                pct = (seg[-1] - seg[0]) / seg[0] if seg[0] != 0 else 0
                if abs(pct) < 0.02:
                    template_parts.append("F")
                elif pct > 0:
                    template_parts.append("U")
                else:
                    template_parts.append("D")
            template_seq = "-".join(template_parts)
            dir_str_to_arr = {"U": 1, "D": -1, "F": 0}
            template_dirs = np.array([dir_str_to_arr.get(d, 0) for d in template_seq.split("-")])

        num_segments = len(template_dirs) if template_dirs is not None else 4
        seg_size = window_size / num_segments

        df_minimal = reader.read(
            None,
            start_date=start_date,
            end_date=end_date,
            fields=["stock_code", "trade_date", "close"],
        )

        if df_minimal.is_empty():
            return []

        stock_stats = (
            df_minimal.lazy()
            .sort(["stock_code", "trade_date"])
            .group_by("stock_code")
            .agg([
                pl.col("close").count().alias("n_rows"),
                pl.col("close").first().alias("first_close"),
                pl.col("close").last().alias("last_close"),
            ])
            .filter(pl.col("n_rows") >= window_size)
            .with_columns(
                ((pl.col("last_close") - pl.col("first_close")) / pl.col("first_close")).alias("pct_change")
            )
            .with_columns(
                pl.when(pl.col("pct_change") > 0.02).then(1)
                .when(pl.col("pct_change") < -0.02).then(-1)
                .otherwise(0)
                .alias("overall_dir")
            )
            .collect(streaming=True)
        )

        template_first_dir = int(template_dirs[0]) if template_dirs is not None else 0

        if template_dirs is not None:
            candidate_stocks = stock_stats.filter(
                pl.col("overall_dir") == template_first_dir
            )["stock_code"].to_list()
        else:
            candidate_stocks = stock_stats["stock_code"].to_list()

        if not candidate_stocks:
            return []

        df = reader.read(
            None,
            start_date=start_date,
            end_date=end_date,
            fields=["stock_code", "trade_date", "open", "high", "low", "close", "volume"],
        )

        if df.is_empty():
            return []

        df = df.sort(["stock_code", "trade_date"])
        df_filtered = df.filter(pl.col("stock_code").is_in(candidate_stocks))

        result = []
        unique_symbols = df_filtered["stock_code"].unique().to_list()

        for symbol in unique_symbols:
            symbol_df = df_filtered.filter(pl.col("stock_code") == symbol).sort("trade_date")
            n_rows = symbol_df.height

            close_arr = symbol_df["close"].cast(pl.Float64).to_numpy()
            if np.isnan(close_arr).any():
                continue

            n_windows = n_rows - window_size + 1
            if n_windows < 1:
                continue

            close_windows = np.lib.stride_tricks.sliding_window_view(close_arr, window_size)
            if close_windows.ndim != 2 or close_windows.shape[0] < n_windows:
                continue
            close_windows = close_windows[:n_windows]

            all_dirs = []
            for seg_idx in range(num_segments):
                seg_start = int(seg_idx * seg_size)
                seg_end = int((seg_idx + 1) * seg_size)
                if seg_start >= window_size:
                    break
                seg_pct = (close_windows[:, seg_end - 1] - close_windows[:, seg_start]) / (close_windows[:, seg_start] + 1e-10)
                # 降低阈值，让小波动也能被识别，提高匹配精度
                seg_dir = np.where(seg_pct > 0.01, 1, np.where(seg_pct < -0.01, -1, 0))
                all_dirs.append(seg_dir)

            matching_mask = np.ones(n_windows, dtype=bool)
            for seg_idx, expected_dir in enumerate(template_dirs):
                matching_mask &= (all_dirs[seg_idx] == expected_dir)

            matching_indices = np.where(matching_mask)[0]

            if len(matching_indices) == 0:
                continue

            open_arr = symbol_df["open"].cast(pl.Float64).to_numpy()
            high_arr = symbol_df["high"].cast(pl.Float64).to_numpy()
            low_arr = symbol_df["low"].cast(pl.Float64).to_numpy()
            volume_arr = symbol_df["volume"].cast(pl.Float64).to_numpy()
            date_arr = symbol_df["trade_date"].to_numpy()

            for i in matching_indices:
                window_close = close_arr[i:i + window_size]
                if np.isnan(window_close).any():
                    continue
                result.append({
                    "klines": {
                        "open": open_arr[i:i + window_size],
                        "high": high_arr[i:i + window_size],
                        "low": low_arr[i:i + window_size],
                        "close": window_close,
                        "volume": volume_arr[i:i + window_size],
                    },
                    "metadata": {
                        "stock_code": symbol,
                        "start_date": str(date_arr[i]),
                        "end_date": str(date_arr[i + window_size - 1]),
                    },
                })

        return result


_similarity_service: Optional[SimilarityService] = None


def get_similarity_service() -> SimilarityService:
    """获取SimilarityService单例"""
    global _similarity_service
    if _similarity_service is None:
        _similarity_service = SimilarityService()
    return _similarity_service
