# strategies/jq_volume_strategy.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List
import time

import pandas as pd
import numpy as np

from core.strategies.strategy_framework import StrategyBase
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


class JQVolumeStrategypro(StrategyBase):
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
        final_signals: Dict[str, str] = {code: "sell" for code in sell_signals}
        for stock in buy_candidates:
            # 如果同一只股票既有卖出又有买入信号，通常买入逻辑优先（或根据T+1规则）
            # 这里简单覆盖为 buy，或者您可以选择忽略买入
            final_signals[stock] = "buy"

        return final_signals

    def _get_previous_day_pool(self, date: str, data_query):
        """获取带缓存的昨日股票池"""
        if date in self._yesterday_cache:
            return self._yesterday_cache[date]

        try:
            # 获取全市场股票池基础数据
            pool = data_query.get_stock_pool(date, use_cache=True, filters={"min_mv": 0})
            if pool is None or pool.empty:
                return None
        except Exception as exc:
            print(f"[{date}] JQ策略: 获取股票池失败: {exc}")
            return None

        self._yesterday_cache[date] = pool
        if len(self._yesterday_cache) > 5:
            self._yesterday_cache.pop(next(iter(self._yesterday_cache)))
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
        第二步筛选（买入核心）：
        1. 仅保留 volume_ratio > 3 的股票
        """
        t0 = time.perf_counter()
        if not pre_screened_codes or stock_pool_snapshot is None:
            return []

        # 检查必要列
        if "volume_ratio" not in stock_pool_snapshot.columns:
            # 如果数据源没有预计算的量比，这里需要自行计算（通常数据源会有）
            print("[JQ策略] 警告：股票池缺少 volume_ratio 列，无法进行量比筛选")
            return []

        # 提取候选池
        candidates = stock_pool_snapshot[
            stock_pool_snapshot["stock_code"].isin(pre_screened_codes)
        ].copy()

        if candidates.empty:
            return []
        
        # 填充缺失值
        # 注意：使用 loc 避免 SettingWithCopyWarning
        candidates.loc[:, "volume_ratio"] = candidates["volume_ratio"].fillna(0)

        # === 核心逻辑：量比 > 3 ===
        # 原策略：yesterday_volume / avg_volume_5d > 3
        # 假设数据源的 volume_ratio 已经是对齐该定义的（通常是 量比 = 当日量 / 5日均量）
        final_mask = candidates["volume_ratio"] > self.config.volume_ratio_threshold

        # 排除停牌（成交量为0）
        if "volume" in candidates.columns:
             final_mask &= (candidates["volume"] > 0)

        result = candidates.loc[final_mask, "stock_code"].tolist()
        
        dt = (time.perf_counter() - t0) * 1000
        print(f"[PROFILE][JQ] Buy Logic: {len(pre_screened_codes)} -> {len(result)} buys, {dt:.1f} ms")
        
        return result

    def _get_sell_signals(self, stock_pool, date, data_query):
        """
        卖出逻辑（基于昨日数据，避免未来函数）：
        昨日收盘价跌破昨日 MA5 (昨日Close < 昨日MA5)
        
        注意：stock_pool 是昨日的数据，包含昨日的收盘价和MA5。
        如果昨日收盘价跌破MA5，则在今日开盘时执行卖出。
        """
        if stock_pool is None or stock_pool.empty:
            return []

        # 如果 stock_pool 已经包含了昨日的 MA5 和 Close，直接向量化计算
        if "ma5" in stock_pool.columns and "close" in stock_pool.columns:
            # 卖出条件：昨日Close < 昨日MA5
            # 这是安全的，因为使用的是昨日收盘后的数据，在今日开盘时可以执行
            sell_mask = (stock_pool["close"] < stock_pool["ma5"])
            return stock_pool.loc[sell_mask, "stock_code"].tolist()

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
                return []

            snapshot = snapshot.dropna(subset=["ma_value"])
            # 筛选跌破均线的股票
            return snapshot.loc[snapshot["close"] < snapshot["ma_value"], "stock_code"].tolist()

        except Exception as exc:
            print(f"[{date}] JQ策略: 计算卖出信号失败: {exc}")
            return []