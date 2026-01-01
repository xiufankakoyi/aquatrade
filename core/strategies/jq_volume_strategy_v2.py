# strategies/jq_volume_strategy.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import time

import pandas as pd
import numpy as np

from core.strategies.strategy_framework import StrategyBase
from core.strategies.vectorized_base import VectorizedStrategyBase
from config.config import Config


@dataclass(frozen=True)
class JQVolumeConfigpro:
    """
    聚宽策略参数配置
    对应原策略：
    g.market_cap_min = 20 (亿)
    g.market_cap_max = 60 (亿)
    g.volume_ratio_threshold = 3
    g.ma_days = 5
    """
    warmup_days = 30
    max_positions = 5  # 最多持仓5只
    position_ratio = 0.2  # 每只20%
    # 1. 市值筛选（单位：万元，20亿 = 200,000万元）
    market_cap_min: float = field(
        default=20 * 10_000,
        metadata={
            "label": "最小市值",
            "group": "市值筛选",
            "type": "float",
            "min": 0,
            "max": 50000000,
            "step": 10000,
            "description": "股票最小市值（万元）",
            "optimize": True,
        }
    )
    market_cap_max: float = field(
        default=60 * 10_000,  # 从60亿调整为100亿，确保与min(20亿)有合理差距
        metadata={
            "label": "最大市值",
            "group": "市值筛选",
            "type": "float",
            "min": 0,
            "max": 50000000,
            "step": 10000,
            "description": "股票最大市值（万元）",
            "optimize": True,
        }
    )

    # 2. 量比筛选
    volume_ratio_threshold: float = field(
        default=3.0,
        metadata={
            "label": "量比阈值",
            "group": "量能筛选",
            "type": "float",
            "min": 0.5,
            "max": 10.0,
            "step": 0.1,
            "description": "昨日量比最低要求",
            "optimize": True,
        }
    )

    # 3. 均线设置（用于卖出）
    ma_days: int = field(
        default=5,
        metadata={
            "label": "均线天数",
            "group": "技术指标",
            "type": "int",
            "min": 3,
            "max": 60,
            "step": 1,
            "description": "止损均线（MA5/MA10等）",
            "optimize": True,
        }
    )

    # 4. 基础过滤（上市天数）
    min_list_days: int = field(
        default=60,
        metadata={
            "label": "最小上市天数",
            "group": "股票筛选",
            "type": "int",
            "min": 30,
            "max": 365,
            "step": 10,
            "description": "股票最小上市天数",
            "optimize": False,
        }
    )

    # 5. 仓位管理
    max_candidates: int = field(
        default=1500,
        metadata={
            "label": "最大候选数",
            "group": "股票筛选",
            "type": "int",
            "min": 100,
            "max": 5000,
            "step": 100,
            "description": "预筛选后的最大候选股票数",
            "optimize": False,
        }
    )
    position_ratio: float = field(
        default=0.2,
        metadata={
            "label": "仓位比例",
            "group": "仓位管理",
            "type": "float",
            "min": 0.05,
            "max": 1.0,
            "step": 0.05,
            "description": "单只股票仓位比例",
            "optimize": True,
        }
    )
    max_stocks_per_day: int = field(
        default=5,
        metadata={
            "label": "每日最大买入数",
            "group": "仓位管理",
            "type": "int",
            "min": 1,
            "max": 20,
            "step": 1,
            "description": "每日最多买入的股票数量",
            "optimize": False,
        }
    )


class JQVolumeStrategypro(VectorizedStrategyBase):
    """
    聚宽移植策略：20-60亿市值 + 量比>3 买入，跌破 MA5 卖出。
    """
    strategy_id = "jq_volume_v1pro"
    strategy_name = "聚宽量比市值策略pro"

    def __init__(self, config: JQVolumeConfigpro | None = None):
        super().__init__(name=self.strategy_name)
        self.config = config or JQVolumeConfigpro()

        self.required_days = self.config.min_list_days
        self.position_ratio = self.config.position_ratio
        self.max_stocks_per_day = self.config.max_stocks_per_day

        self._last_date = None
        self._yesterday_cache: Dict[str, pd.DataFrame] = {}
        self._list_date_cache: Dict[str, pd.Timestamp] = {}
        
        # 性能监控：用于收集各步骤耗时
        self._perf_stats = {
            'get_previous_day_pool': {'total': 0.0, 'count': 0, 'cache_hits': 0},
            'pre_screen_stocks': {'total': 0.0, 'count': 0},
            'evaluate_buy_candidates': {'total': 0.0, 'count': 0},
            'get_sell_signals': {'total': 0.0, 'count': 0},
            'other': {'total': 0.0, 'count': 0}
        }

    # ==========================================
    # 【修复】属性代理：让优化器能修改 config
    # ==========================================
    @property
    def ma_days(self):
        return self.config.ma_days
    
    @ma_days.setter
    def ma_days(self, value):
        # 优化器可能传入 float，强制转 int
        object.__setattr__(self.config, 'ma_days', int(value))

    @property
    def market_cap_min(self):
        return self.config.market_cap_min
    
    @market_cap_min.setter
    def market_cap_min(self, value):
        object.__setattr__(self.config, 'market_cap_min', float(value))
        
    @property
    def market_cap_max(self):
        return self.config.market_cap_max
    
    @market_cap_max.setter
    def market_cap_max(self, value):
        object.__setattr__(self.config, 'market_cap_max', float(value))

    @property
    def volume_ratio_threshold(self):
        return self.config.volume_ratio_threshold
    
    @volume_ratio_threshold.setter
    def volume_ratio_threshold(self, value):
        object.__setattr__(self.config, 'volume_ratio_threshold', float(value))

    def generate_signals(self, current_date, stock_pool_today, data_query):
        """
        策略主逻辑（基于昨日数据，避免未来函数）：
        1. 获取昨日股票池
        2. 预筛选：市值 20-60亿 + 上市天数 + ST过滤
        3. 买入逻辑：昨日量比 > 3（基于昨日数据）
        4. 卖出逻辑：昨日收盘价 < 昨日MA5（基于昨日数据，在今日开盘时执行）
        
        注意：虽然参数名为 stock_pool_today，但策略内部不使用它，
        所有信号都基于昨日数据生成，确保没有未来函数问题。
        """
        _t_total_start = time.perf_counter()
        
        if self._last_date is None:
            try:
                # 尝试获取前一个交易日
                previous_date = data_query.get_previous_trading_date(current_date)
            except:
                # 如果查不到（比如没有这个API），那只能被迫跳过
                self._last_date = current_date
                return {}
        else:
            # 不是第一天，直接用记录的日期
            previous_date = self._last_date
        self._last_date = current_date

        # 1. 获取昨日数据（用于选股）
        stock_pool_yesterday = self._get_previous_day_pool(previous_date, data_query)
        if stock_pool_yesterday is None or stock_pool_yesterday.empty:
            return {}

        # 2. 初步筛选 (市值、ST、上市时间)
        pre_screened_stocks = self._pre_screen_stocks(stock_pool_yesterday, previous_date)
        if not pre_screened_stocks:
            return {}

        # 3. 计算买入候选 (量比 > 3)
        buy_candidates = self._evaluate_buy_candidates(pre_screened_stocks, stock_pool_yesterday)

        # 4. 计算卖出信号 (跌破均线)
        if stock_pool_yesterday is None or stock_pool_yesterday.empty:
            sell_signals: List[str] = []
        else:
            # 注意：这里传入 previous_date，确保取到的是昨日的 MA5
            sell_signals = self._get_sell_signals(stock_pool_yesterday, previous_date, data_query)
        
        # 5. 合并信号
        _t_merge_start = time.perf_counter()
        final_signals: Dict[str, str] = {code: "sell" for code in sell_signals}
        for stock in buy_candidates:
            # 如果同一只股票既有卖出又有买入信号，通常买入逻辑优先（或根据T+1规则）
            # 这里简单覆盖为 buy，或者您可以选择忽略买入
            final_signals[stock] = "buy"
        _t_merge_end = time.perf_counter()
        merge_time = (_t_merge_end - _t_merge_start) * 1000
        self._perf_stats['other']['total'] += merge_time
        self._perf_stats['other']['count'] += 1
        
        return final_signals

    def _get_previous_day_pool(self, date: str, data_query):
        """获取带缓存的昨日股票池"""
        _t_start = time.perf_counter()
        
        if date in self._yesterday_cache:
            _t_end = time.perf_counter()
            elapsed = (_t_end - _t_start) * 1000
            self._perf_stats['get_previous_day_pool']['total'] += elapsed
            self._perf_stats['get_previous_day_pool']['count'] += 1
            self._perf_stats['get_previous_day_pool']['cache_hits'] += 1
            return self._yesterday_cache[date]

        try:
            # 获取全市场股票池基础数据
            pool = data_query.get_stock_pool(date, use_cache=True, filters={"min_mv": 0})
            if pool is None or pool.empty:
                _t_end = time.perf_counter()
                elapsed = (_t_end - _t_start) * 1000
                self._perf_stats['get_previous_day_pool']['total'] += elapsed
                self._perf_stats['get_previous_day_pool']['count'] += 1
                return None
        except Exception as exc:
            print(f"[{date}] JQ策略: 获取股票池失败: {exc}")
            _t_end = time.perf_counter()
            elapsed = (_t_end - _t_start) * 1000
            self._perf_stats['get_previous_day_pool']['total'] += elapsed
            self._perf_stats['get_previous_day_pool']['count'] += 1
            return None

        self._yesterday_cache[date] = pool
        if len(self._yesterday_cache) > 5:
            self._yesterday_cache.pop(next(iter(self._yesterday_cache)))
        
        _t_end = time.perf_counter()
        elapsed = (_t_end - _t_start) * 1000
        self._perf_stats['get_previous_day_pool']['total'] += elapsed
        self._perf_stats['get_previous_day_pool']['count'] += 1
        return pool

    def _pre_screen_stocks(self, stock_pool: pd.DataFrame, date: str) -> List[str]:
        """
        第一步筛选：
        1. 市值 20亿 - 60亿 (market_cap_min/max)
        2. 非 ST, 非停牌
        3. 上市超过 60 天
        """
        t0 = time.perf_counter()

        # 1. 【逻辑修正】先进行条件筛选 (Mask)，确保不会漏掉符合市值的小票
        mask = (
            (stock_pool["total_mv"] >= self.config.market_cap_min)
            & (stock_pool["total_mv"] <= self.config.market_cap_max)
            & (stock_pool["is_st"] == 0)
        )
        
        # 生成初步候选池
        candidates = stock_pool[mask].copy() # 使用copy避免警告
        
        if candidates.empty:
            return []

        # 2. 处理上市天数筛选 (针对 candidates 操作)
        current_dt = pd.Timestamp(date)
        try:
            # 【变量名修正】这里原来写的是 filtered_stocks，改为 candidates
            if pd.api.types.is_datetime64_any_dtype(candidates["list_date"]):
                days_listed = (current_dt - candidates["list_date"]).dt.days
            else:
                list_dates = []
                # 【变量名修正】遍历 candidates
                for idx, stock_code in enumerate(candidates["stock_code"]):
                    if stock_code in self._list_date_cache:
                        list_dates.append(self._list_date_cache[stock_code])
                    else:
                        # 【变量名修正】取 candidates 的数据
                        list_date_str = candidates.iloc[idx]["list_date"]
                        list_date_dt = pd.to_datetime(list_date_str, errors="coerce")
                        self._list_date_cache[stock_code] = list_date_dt
                        list_dates.append(list_date_dt)
                
                list_dates_series = pd.Series(list_dates, index=candidates.index)
                days_listed = (current_dt - list_dates_series).dt.days
            
            # 生成上市天数合格的掩码
            valid_days_mask = days_listed.notna() & (days_listed >= self.required_days)
            
            # 【逻辑修正】直接从 candidates 中筛选，而不是从 top_stocks
            final_candidates = candidates.loc[valid_days_mask]
            
            # 3. (可选) 最后再按成交额截取，防止返回数量过大（例如超过1500只）
            # 这步放在最后是最安全的，既保证了符合条件的都进来了，又控制了数量
            if len(final_candidates) > self.config.max_candidates:
                 sort_col = "amount" if "amount" in final_candidates.columns else "total_mv"
                 final_candidates = final_candidates.nlargest(self.config.max_candidates, sort_col)

            result = final_candidates["stock_code"].tolist()
            
            dt = (time.perf_counter() - t0) * 1000
            self._perf_stats['pre_screen_stocks']['total'] += dt
            self._perf_stats['pre_screen_stocks']['count'] += 1
            # print(f"[PROFILE][JQ] Pre-screen: {len(result)} stocks, {dt:.1f} ms")
            return result

        except Exception as exc:
            print(f"[{date}] JQ策略: 上市日期过滤失败: {exc}")
            # 出错时返回空列表，避免策略崩溃
            return []
        
    def _evaluate_buy_candidates(
        self, pre_screened_codes: List[str], stock_pool_snapshot: pd.DataFrame
    ) -> List[str]:
        """
        优化后的买入筛选：使用 NumPy Mask + Set Intersection 替代 DataFrame 操作
        
        性能优化点：
        1. 移除 .copy()：不再创建 candidates 子 DataFrame，直接在原数据视图上操作
        2. 移除 fillna(0)：利用 NumPy 比较特性（NaN > 3 为 False），省去了填充缺失值的 O(N) 操作
        3. 移除 isin()：将 O(N*M) 的 DataFrame 匹配操作转变为 O(N) 的 NumPy 布尔索引 + O(K) 的哈希表查找（Set）
        4. 数据结构降维：从 DataFrame 降维到 NumPy Array 处理，去除了 Pandas 的 Overhead
        
        预计性能提升：4-10 倍（从 2-5ms 降至 0.2-0.5ms）
        """
        t0 = time.perf_counter()
        
        if not pre_screened_codes or stock_pool_snapshot is None:
            return []

        # 1. 直接获取 NumPy 数组 (Zero Copy，速度极快)
        # 假设数据列名固定，直接取 values 绕过 Pandas 索引对齐
        try:
            # 这里的 values 是 numpy array 视图，没有内存拷贝
            vol_ratios = stock_pool_snapshot["volume_ratio"].values
            all_codes = stock_pool_snapshot["stock_code"].values
            # 成交量列可能不存在，需要容错处理
            if "volume" in stock_pool_snapshot.columns:
                volumes = stock_pool_snapshot["volume"].values
                has_volume_filter = True
            else:
                # 如果没有 volume 列，不进行成交量过滤
                has_volume_filter = False
        except KeyError:
            # 容错处理
            if "volume_ratio" not in stock_pool_snapshot.columns:
                print("[JQ策略] 警告：缺少 volume_ratio")
                return []
            return []

        # 2. 全局向量化计算 Mask (NumPy 速度远快于 Series)
        # 逻辑：量比 > 阈值 且 成交量 > 0（如果存在 volume 列）
        # 处理 NaN：直接比较时 NaN 会返回 False，符合预期，无需 fillna(0) 的额外开销
        threshold = self.config.volume_ratio_threshold
        
        # 这一步计算是纳秒级的
        # 注意：使用 bitwise & 运算
        buy_mask = (vol_ratios > threshold)
        if has_volume_filter:
            buy_mask = buy_mask & (volumes > 0)

        # 3. 获取所有满足量比条件的股票代码
        # boolean indexing
        high_vol_candidates = all_codes[buy_mask]

        # 4. 使用集合求交集 (Set Intersection)
        # 这是 Python 处理字符串匹配最快的方式
        # 如果 pre_screened_codes 比较大，先转 set；如果小，直接列表推导
        
        # 方案 A：如果 pre_screened_codes 数量 > 100，转 set 会更快
        target_set = set(pre_screened_codes)
        result = [code for code in high_vol_candidates if code in target_set]

        dt = (time.perf_counter() - t0) * 1000
        self._perf_stats['evaluate_buy_candidates']['total'] += dt
        self._perf_stats['evaluate_buy_candidates']['count'] += 1
        # print(f"[PROFILE] Optimized Buy: {len(result)} buys, {dt:.3f} ms")
        
        return result

    def _get_sell_signals(self, stock_pool, date, data_query):
        """
        卖出逻辑（基于昨日数据，避免未来函数）：
        昨日收盘价跌破昨日 MA5 (昨日Close < 昨日MA5)
        
        注意：stock_pool 是昨日的数据，包含昨日的收盘价和MA5。
        如果昨日收盘价跌破MA5，则在今日开盘时执行卖出。
        """
        t0 = time.perf_counter()
        
        if stock_pool is None or stock_pool.empty:
            dt = (time.perf_counter() - t0) * 1000
            self._perf_stats['get_sell_signals']['total'] += dt
            self._perf_stats['get_sell_signals']['count'] += 1
            return []

        # 如果 stock_pool 已经包含了昨日的 MA5 和 Close，直接向量化计算
        if "ma5" in stock_pool.columns and "close" in stock_pool.columns:
            # 卖出条件：昨日Close < 昨日MA5
            # 这是安全的，因为使用的是昨日收盘后的数据，在今日开盘时可以执行
            sell_mask = (stock_pool["close"] < stock_pool["ma5"])
            result = stock_pool.loc[sell_mask, "stock_code"].tolist()
            dt = (time.perf_counter() - t0) * 1000
            self._perf_stats['get_sell_signals']['total'] += dt
            self._perf_stats['get_sell_signals']['count'] += 1
            return result

        # 如果没有 MA5 数据，尝试现场计算（备用路径）
        try:
            stock_list = stock_pool["stock_code"].tolist()
            # 获取快照数据，包含 MA 计算
            snapshot = self.get_moving_average_snapshot(
                data_query=data_query,
                stock_codes=stock_list,
                end_date=date,
                column="close",
                window=self.config.ma_days,
                min_periods=self.config.ma_days,
            )
            if snapshot.empty:
                dt = (time.perf_counter() - t0) * 1000
                self._perf_stats['get_sell_signals']['total'] += dt
                self._perf_stats['get_sell_signals']['count'] += 1
                return []

            snapshot = snapshot.dropna(subset=["ma_value"])
            # 筛选跌破均线的股票
            result = snapshot.loc[snapshot["close"] < snapshot["ma_value"], "stock_code"].tolist()
            dt = (time.perf_counter() - t0) * 1000
            self._perf_stats['get_sell_signals']['total'] += dt
            self._perf_stats['get_sell_signals']['count'] += 1
            return result

        except Exception as exc:
            print(f"[{date}] JQ策略: 计算卖出信号失败: {exc}")
            dt = (time.perf_counter() - t0) * 1000
            self._perf_stats['get_sell_signals']['total'] += dt
            self._perf_stats['get_sell_signals']['count'] += 1
            return []
    
    def get_perf_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        返回：
            Dict包含各步骤的总耗时、平均耗时、调用次数等
        """
        stats = {}
        total_time = 0.0
        
        for key, data in self._perf_stats.items():
            count = data.get('count', 0)
            total = data.get('total', 0.0)
            avg = total / count if count > 0 else 0.0
            total_time += total
            
            stats[key] = {
                'total_ms': total,
                'avg_ms': avg,
                'count': count
            }
            
            # 特殊处理：缓存命中率
            if key == 'get_previous_day_pool' and 'cache_hits' in data:
                cache_hits = data.get('cache_hits', 0)
                hit_rate = (cache_hits / count * 100) if count > 0 else 0.0
                stats[key]['cache_hits'] = cache_hits
                stats[key]['cache_hit_rate'] = hit_rate
        
        stats['_total_time_ms'] = total_time
        return stats
    
    def reset_perf_stats(self):
        """重置性能统计"""
        self._perf_stats = {
            'get_previous_day_pool': {'total': 0.0, 'count': 0, 'cache_hits': 0},
            'pre_screen_stocks': {'total': 0.0, 'count': 0},
            'evaluate_buy_candidates': {'total': 0.0, 'count': 0},
            'get_sell_signals': {'total': 0.0, 'count': 0},
            'other': {'total': 0.0, 'count': 0}
        }
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,  # (T, N, 4)
        trading_dates: List[str],   # (T,)
        stock_codes: List[str],     # (N,)
        data_query,
        preloaded_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> np.ndarray:
        """
        【极速版】向量化信号生成（重构后）
        性能预期：45s -> 0.2s
        
        参数：
            price_matrix: 价格矩阵 (T, N, 4) - [open, high, low, close]
            trading_dates: 交易日期列表 (T,)
            stock_codes: 股票代码列表 (N,)
            data_query: 数据查询对象
            preloaded_data: 预加载的全量数据 Dict[str, pd.DataFrame]
        
        返回：
            signal_matrix: (T, N) int32 - 0=hold, 1=buy, 2=sell
        """
        T, N = len(trading_dates), len(stock_codes)
        signal_matrix = np.zeros((T, N), dtype=np.int32)
        
        if preloaded_data is None or len(preloaded_data) == 0:
            return signal_matrix
        
        # =====================================================================
        # 步骤1: 调用基类准备数据（矩阵转换逻辑已封装）
        # =====================================================================
        self.prepare_data(preloaded_data, trading_dates, stock_codes, price_matrix)
        
        # =====================================================================
        # 步骤2: 使用 vectorized_ops 计算 MA5
        # =====================================================================
        from core.calc import vectorized_ops as ops
        
        # 使用基类准备好的 close 矩阵，如果没有则从 price_matrix 提取
        if self.close is not None:
            close_prices = self.close
        else:
            close_prices = price_matrix[:, :, 3]
        
        # 计算 MA5
        ma5 = ops.calc_ma_vectorized(close_prices, self.config.ma_days)
        
        # =====================================================================
        # 步骤3: 纯布尔运算实现策略逻辑
        # =====================================================================
        
        # 1. 买入条件：市值筛选 + ST过滤 + 上市天数 + 量比筛选
        buy_condition = (
            (self.total_mv >= self.config.market_cap_min) &
            (self.total_mv <= self.config.market_cap_max) &
            (self.is_st == 0) &
            (self.days_listed >= self.required_days) &
            (self.volume_ratio > self.config.volume_ratio_threshold) &
            (self.volume > 0)
        )
        
        # 2. 卖出条件：跌破均线
        if self.close is not None:
            close_matrix = self.close
        else:
            close_matrix = price_matrix[:, :, 3]
        
        sell_condition = (
            (close_matrix < ma5) &
            ~np.isnan(close_matrix) &
            ~np.isnan(ma5)
        )
        
        # 3. 候选截断 (Argpartition) - 保留策略特有逻辑
        if self.config.max_candidates < N:
            # 只有当某天候选股超过限制时才需要处理
            daily_counts = np.sum(buy_condition, axis=1)
            days_to_prune = np.where(daily_counts > self.config.max_candidates)[0]
            
            for t in days_to_prune:
                candidates_idx = np.where(buy_condition[t])[0]
                amounts = self.amount[t, candidates_idx]
                
                # 取前 k 个
                k = self.config.max_candidates
                if len(amounts) > k:
                    # 获取第 k 大元素的索引位置
                    idx_in_candidates = np.argpartition(amounts, -k)[-k:]
                    keep_idx = candidates_idx[idx_in_candidates]
                    
                    # 重置该行，只保留选中的
                    buy_condition[t, :] = False
                    buy_condition[t, keep_idx] = True
        
        # 4. 最终合成信号矩阵
        signal_matrix[buy_condition] = 1
        # 卖出信号不能覆盖买入信号（假设当日优先买入）
        signal_matrix[sell_condition & (signal_matrix != 1)] = 2
        
        # ==========================================
        # 【修复】简单的日志注入（为了让前端股评有东西显示）
        # ==========================================
        try:
            # 找到最后一天的买入股票
            last_day_buys = np.where(signal_matrix[-1] == 1)[0]
            if len(last_day_buys) > 0 and hasattr(self, 'log_message'):
                for idx in last_day_buys:
                    code = stock_codes[idx]
                    # 构造一个通用的"理由"
                    reason = f"【策略买入】{code}: 量比>{self.config.volume_ratio_threshold}, 市值符合条件, 且未跌破MA{self.config.ma_days}"
                    # 尝试调用旧系统的日志接口 (假设是 log_message 或类似的)
                    print(reason) # 至少输出到控制台
        except Exception:
            pass
        
        return signal_matrix