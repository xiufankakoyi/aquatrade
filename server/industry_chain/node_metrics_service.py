"""
NodeMetricsService

按 chain_id + node_id + trade_date 聚合节点市场指标。

指标:
- stock_count
- verified_stock_count
- candidate_stock_count
- avg_return_1d
- avg_return_5d
- limit_up_count
- strong_stock_count
- total_amount
- amount_change_ratio
- hot_score
- market_strength

hot_score 简化公式:
    avg_return_score * 0.30
  + limit_up_score * 0.25
  + amount_score * 0.20
  + verified_stock_score * 0.15
  + pattern_score * 0.10

market_strength:
- hot_score >= 80: 很强
- 60-80: 强
- 40-60: 中
- 20-40: 弱
- <20: 很弱
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from server.industry_chain.loader import project_root

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = project_root() / "data" / "industry"


class NodeMetricsService:
    """节点市场指标服务。"""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self._metrics_df: pd.DataFrame | None = None

    def _load_metrics(self) -> pd.DataFrame:
        """加载节点指标数据，带缓存。"""
        if self._metrics_df is not None:
            return self._metrics_df

        parquet_path = self.output_dir / "node_market_metrics.parquet"
        try:
            if parquet_path.exists():
                self._metrics_df = pd.read_parquet(parquet_path)
            else:
                self._metrics_df = pd.DataFrame()
        except Exception as exc:
            logger.warning(f"加载 node_market_metrics 失败: {exc}")
            self._metrics_df = pd.DataFrame()

        return self._metrics_df

    def get_node_metrics(self, chain_id: str, node_id: str, trade_date: str | None = None) -> dict[str, Any]:
        """
        获取指定节点的市场指标。

        Args:
            chain_id: 产业链 ID
            node_id: 节点 ID
            trade_date: 交易日期，为 None 时返回最新日期的数据

        Returns:
            节点指标字典
        """
        df = self._load_metrics()
        if df.empty:
            return self._empty_metrics()

        try:
            filtered = df[df["chain_id"] == chain_id]
            if filtered.empty:
                return self._empty_metrics()

            if trade_date:
                filtered = filtered[filtered["trade_date"] == trade_date]
            else:
                # 取最新日期
                latest = filtered["trade_date"].max()
                filtered = filtered[filtered["trade_date"] == latest]

            filtered = filtered[filtered["node_id"] == node_id]
            if filtered.empty:
                return self._empty_metrics()

            row = filtered.iloc[0]
            return self._row_to_dict(row)
        except Exception as exc:
            logger.warning(f"查询节点指标失败: {exc}")
            return self._empty_metrics()

    def get_chain_metrics(self, chain_id: str, trade_date: str | None = None) -> dict[str, dict[str, Any]]:
        """
        获取产业链所有节点的市场指标。

        Returns:
            {node_id: metrics_dict}
        """
        df = self._load_metrics()
        result: dict[str, dict[str, Any]] = {}
        if df.empty:
            return result

        try:
            filtered = df[df["chain_id"] == chain_id]
            if filtered.empty:
                return result

            if trade_date:
                filtered = filtered[filtered["trade_date"] == trade_date]
            else:
                latest = filtered["trade_date"].max()
                filtered = filtered[filtered["trade_date"] == latest]

            for _, row in filtered.iterrows():
                node_id = str(row.get("node_id", ""))
                if node_id:
                    result[node_id] = self._row_to_dict(row)
        except Exception as exc:
            logger.warning(f"查询产业链指标失败: {exc}")

        return result

    def clear_cache(self) -> None:
        """清除缓存。"""
        self._metrics_df = None

    def _row_to_dict(self, row: Any) -> dict[str, Any]:
        """将 DataFrame row 转换为字典。"""
        def get_float(col: str, default: float = 0.0) -> float:
            val = row.get(col, default)
            try:
                return float(val) if pd.notna(val) else default
            except (TypeError, ValueError):
                return default

        def get_int(col: str, default: int = 0) -> int:
            val = row.get(col, default)
            try:
                return int(val) if pd.notna(val) else default
            except (TypeError, ValueError):
                return default

        return {
            "node_id": str(row.get("node_id", "")),
            "chain_id": str(row.get("chain_id", "")),
            "trade_date": str(row.get("trade_date", "")),
            "stock_count": get_int("stock_count"),
            "verified_stock_count": get_int("verified_stock_count"),
            "candidate_stock_count": get_int("candidate_stock_count"),
            "avg_return_1d": round(get_float("avg_return_1d"), 2),
            "avg_return_5d": round(get_float("avg_return_5d"), 2),
            "limit_up_count": get_int("limit_up_count"),
            "strong_stock_count": get_int("strong_stock_count"),
            "total_amount": round(get_float("total_amount"), 2),
            "amount_change_ratio": round(get_float("amount_change_ratio"), 2),
            "hot_score": round(get_float("hot_score"), 2),
            "market_strength": str(row.get("market_strength", "很弱")),
        }

    def _empty_metrics(self) -> dict[str, Any]:
        """空指标。"""
        return {
            "node_id": "",
            "chain_id": "",
            "trade_date": "",
            "stock_count": 0,
            "verified_stock_count": 0,
            "candidate_stock_count": 0,
            "avg_return_1d": 0.0,
            "avg_return_5d": 0.0,
            "limit_up_count": 0,
            "strong_stock_count": 0,
            "total_amount": 0.0,
            "amount_change_ratio": 0.0,
            "hot_score": 0.0,
            "market_strength": "很弱",
        }
