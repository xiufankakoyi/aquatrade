from dataclasses import dataclass
from typing import Dict, List, Optional

import math
import pandas as pd

from strategies.strategy_framework import StrategyBase
from strategies.jq_volume_strategy import JQVolumeConfig, JQVolumeStrategy
from utils.config import Config


# ================== V6 专用配置 ==================

@dataclass(frozen=True)
class JQVolumeConfigV6(JQVolumeConfig):
    """
    V6 版配置：
    - 强势股筛选阈值（沿用你原来的 volume_ratio / turnover_rate）
    - 动量参数：用 close / ma20 做一个简易动量
    - 防守仓：银行/保险底仓比例 + 强势股最大持仓数量
    """
    # 强势股动量阈值（例如 0.05 表示价格高于 ma20 至少 5%）
    momentum_min: float = 0.05
    momentum_max: float = 0.25  # 太高视为可能高潮，避免只吃最后一口肉

    # 防守相关
    min_bank_weight: float = 0.3        # 防守仓最低占比（按“名额”近似）
    max_strong_slots: int = 2           # 同时持有的强势股最大数量

    # 卖出相关
    big_drop_pct: float = -0.05         # 大阴线阈值（-5%）
    big_drop_dist_ma: float = 0.03      # 距离 MA5 的偏离度（3%）

    # TODO: 按你自己的代码格式调整银行/保险白名单
    bank_whitelist: tuple = (
        "601288.SH",  # 农业银行
        "601398.SH",  # 工商银行
        "600000.SH",  # 浦发银行
        "601939.SH",  # 建设银行
        "601988.SH",  # 中国银行
    )
    insurance_whitelist: tuple = (
        "601318.SH",  # 中国平安
        "601336.SH",  # 新华保险
    )


# ================== V6 策略本体 ==================


class JQVolumeStrategyV6(JQVolumeStrategy):
    """
    聚宽量比市值策略 V6
    -----------------------------------------------------
    核心思想：
    1）进攻：用 V3 的选股 + 动量分级过滤，只在趋势中段上车，避免纯尾巴；
    2）防守：始终保留一定比例的银行/保险仓位（min_bank_weight），
        熊市 / 指数走弱时用银行填满空仓；
    3）卖出：在 V3 的 5 日线基础上叠加“大阴线 + 远离 5 日线”智能止损，
        避免瀑布砸盘。
    """

    strategy_name = "聚宽量比市值策略V6_动量_银行防守"

    def __init__(self, config: Optional[JQVolumeConfigV6] = None):
        if config is None:
            # 保留你之前 JQVolumeConfig 的默认参数
            base_cfg = JQVolumeConfig()
            # 从 base_cfg 创建字典，将 max_stocks_per_day 映射为 max_hold_num（如果代码中需要）
            base_dict = base_cfg.__dict__.copy()
            # JQVolumeConfigV6 继承自 JQVolumeConfig，所以直接传递所有字段即可
            config = JQVolumeConfigV6(**base_dict)
        self.config: JQVolumeConfigV6 = config  # type: ignore
        super().__init__(config=config)

    # ------------------------------------------------------------------
    # 1. 买入逻辑：强势股 + 银行/保险动态配比
    # ------------------------------------------------------------------

    def _pick_defensive_codes(self, stock_pool: pd.DataFrame) -> List[str]:
        """从当日股票池里挑出银行/保险作为防守标的。"""
        codes = []

        if "industry_name" in stock_pool.columns:
            bank_mask = stock_pool["industry_name"].astype(str).str.contains("银行|保险", na=False)
            codes.extend(stock_pool.loc[bank_mask, "stock_code"].tolist())

        # 使用白名单兜底
        if not codes and "stock_code" in stock_pool.columns:
            universe = set(stock_pool["stock_code"].tolist())
            for c in list(self.config.bank_whitelist) + list(self.config.insurance_whitelist):
                if c in universe:
                    codes.append(c)

        # 去重
        return list(dict.fromkeys(codes))

    def _evaluate_buy_candidates(
        self,
        pre_screened_codes: List[str],
        stock_pool_snapshot: pd.DataFrame,
    ) -> List[str]:
        """
        V6 买入逻辑（供 generate_signals 调用）：

        1）先用 V3 原有逻辑筛一遍强势股（如果存在）；
        2）在此基础上加动量过滤（close / ma20）；
        3）根据 max_strong_slots 决定强势股名额；
        4）用银行/保险填满剩余名额，保证 min_bank_weight。
        """
        if not pre_screened_codes or stock_pool_snapshot.empty:
            return []

        # 1. 先保留预筛结果中的股票
        pool = stock_pool_snapshot[stock_pool_snapshot["stock_code"].isin(pre_screened_codes)].copy()
        if pool.empty:
            return []

        # ---- 动量计算：用 close / ma20 - 1 作为简易动量 ----
        has_ma20 = "ma20" in pool.columns
        if not has_ma20:
            # 没有 ma20 就退回 V3 原始行为
            try:
                return super()._evaluate_buy_candidates(pre_screened_codes, stock_pool_snapshot)  # type: ignore
            except AttributeError:
                return []

        close = pool["close"]
        ma20 = pool["ma20"].replace(0, pd.NA)

        pool["momentum"] = close / ma20 - 1.0

        # ---- 多头趋势过滤：MA5 > MA10 > MA20 + 价格站上 MA20 一定幅度 ----
        ma5 = pool.get("ma5")
        ma10 = pool.get("ma10")
        trend_ok = ma5.notna() & ma10.notna() & (ma5 > ma10) & (ma10 > ma20)

        momentum = pool["momentum"]
        mom_ok = (momentum >= self.config.momentum_min) & (momentum <= self.config.momentum_max)

        # 量能过滤（沿用原有 volume_ratio / turnover_rate）
        vol_ratio = pool.get("volume_ratio", pd.Series(0, index=pool.index)).fillna(0)
        turnover = pool.get("turnover_rate", pd.Series(0, index=pool.index)).fillna(0)
        vol_ok = (vol_ratio >= self.config.volume_ratio_threshold) & (
            turnover >= self.config.turnover_rate_threshold
        )

        strong_mask = trend_ok & mom_ok & vol_ok
        strong_pool = pool[strong_mask].copy()

        if strong_pool.empty:
            strong_codes: List[str] = []
        else:
            # 动量从高到低排序，优先买更强的
            strong_pool = strong_pool.sort_values("momentum", ascending=False)
            strong_codes = strong_pool["stock_code"].tolist()

        # ---- 防守标的 ----
        defensive_pool = stock_pool_snapshot.copy()
        defensive_codes = self._pick_defensive_codes(defensive_pool)

        # ---- 综合名额分配 ----
        # 使用 max_stocks_per_day（来自父类 JQVolumeConfig）作为最大持仓数
        max_hold_num = getattr(self.config, "max_stocks_per_day", 5)
        max_strong = min(self.config.max_strong_slots, max_hold_num)

        # 优先留出防守名额
        min_defensive_slots = math.ceil(max_hold_num * self.config.min_bank_weight)

        # 实际能用的强势股名额
        strong_slots = min(len(strong_codes), max_strong)
        remaining_slots = max_hold_num - strong_slots

        # 防守仓名额 = 至少 min_defensive_slots，最多 remaining_slots
        defensive_slots = min(len(defensive_codes), max(min_defensive_slots, remaining_slots))

        # 如果剩余名额 > 防守需求，可以再多放一点强势股
        if remaining_slots > defensive_slots:
            extra_strong = min(len(strong_codes) - strong_slots, remaining_slots - defensive_slots)
            strong_slots += max(extra_strong, 0)

        final_strong = strong_codes[:strong_slots]
        final_defensive = defensive_codes[:defensive_slots]

        final_list = final_strong + final_defensive
        # 去重，保持顺序
        final_list = list(dict.fromkeys(final_list))

        return final_list

    # ------------------------------------------------------------------
    # 2. V6 卖出逻辑：5 日线 + 大阴线 + 轻量趋势破坏
    # ------------------------------------------------------------------

    def _get_sell_signals(self, stock_pool: pd.DataFrame, date: str, data_query) -> List[str]:
        """
        卖出条件（满足任一）：
        1）收盘价跌破 MA5（正常趋势离场）；
        2）大阴线：跌幅 <= big_drop_pct 且 (MA5 - close)/MA5 >= big_drop_dist_ma；
        3）辅助：连续两根收盘价低于 MA10（如果有 ma10 列）。
        """
        if stock_pool is None or stock_pool.empty:
            return []

        close = stock_pool["close"]
        open_price = stock_pool["open"].replace(0, pd.NA)

        # ---------- 1) 跌破 MA5 ----------
        if "ma5" in stock_pool.columns:
            ma5 = stock_pool["ma5"]
            cond_break_ma5 = ma5.notna() & (close < ma5)
        else:
            cond_break_ma5 = pd.Series(False, index=stock_pool.index)

        # ---------- 2) 大阴线 + 远离 MA5 ----------
        # 优先使用 pct_chg / change_pct 字段
        cond_big_drop = pd.Series(False, index=stock_pool.index)
        for col in ("pct_chg", "change_pct"):
            if col in stock_pool.columns:
                pct = stock_pool[col].astype(float)
                if pct.abs().max() > 1.0:
                    cond_big_drop = pct <= (self.config.big_drop_pct * 100)
                else:
                    cond_big_drop = pct <= self.config.big_drop_pct
                break
        else:
            intraday_ret = (close - open_price) / open_price
            cond_big_drop = intraday_ret <= self.config.big_drop_pct

        cond_far_from_ma5 = pd.Series(False, index=stock_pool.index)
        if "ma5" in stock_pool.columns:
            ma5 = stock_pool["ma5"].replace(0, pd.NA)
            dist = (ma5 - close) / ma5
            cond_far_from_ma5 = ma5.notna() & (dist >= self.config.big_drop_dist_ma)

        cond_big_bear = cond_big_drop & cond_far_from_ma5

        # ---------- 3) 连续两日收盘价低于 MA10（轻量趋势破坏） ----------
        cond_break_trend = pd.Series(False, index=stock_pool.index)
        if "ma10" in stock_pool.columns and data_query is not None:
            try:
                codes = stock_pool["stock_code"].tolist()
                hist = data_query.get_price(
                    codes=codes,
                    end_date=date,
                    count=3,
                    fields=["close", "ma10"],
                )
                # 假设返回 MultiIndex: (date, stock_code)
                hist = hist.reset_index().rename(columns={"level_0": "trade_date", "level_1": "stock_code"})
                last2 = hist.groupby("stock_code").tail(2)
                last2["below_ma10"] = last2["close"] < last2["ma10"]
                below_count = last2.groupby("stock_code")["below_ma10"].sum()
                broken_codes = set(below_count[below_count >= 2].index)
                cond_break_trend = stock_pool["stock_code"].isin(broken_codes)
            except Exception:
                # 数据接口不符合预期就忽略这个条件，避免拖慢
                cond_break_trend = pd.Series(False, index=stock_pool.index)

        sell_mask = cond_break_ma5 | cond_big_bear | cond_break_trend
        return stock_pool.loc[sell_mask, "stock_code"].tolist()
