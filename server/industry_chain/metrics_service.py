"""
IndustryChainRadar Metrics Service

市场指标计算服务（降级处理）。
"""

from __future__ import annotations

from typing import Any, Dict, List

from server.industry_chain.loader import MappingLoader
from server.industry_chain.schema import StockMapping


class MetricsService:
    """市场指标服务。"""

    def __init__(self) -> None:
        self.mapping_loader = MappingLoader()

    def calc_chain_summary(self, chain_id: str) -> Dict[str, Any]:
        """计算产业链摘要指标。"""
        try:
            mappings = self.mapping_loader.load_mappings(chain_id=chain_id)
            if not mappings:
                return self._empty_summary(chain_id)

            node_ids = {m.node_id for m in mappings}
            total_stocks = len(mappings)
            sample_count = sum(1 for m in mappings if m.is_sample)

            # 计算平均分
            avg_relevance = sum(m.relevance_score for m in mappings) / total_stocks
            avg_purity = sum(m.purity_score for m in mappings) / total_stocks
            hot_score = (avg_relevance * 0.5 + avg_purity * 0.5) * 100

            return {
                "chain_id": chain_id,
                "hot_score": round(hot_score, 2),
                "market_strength": 0.0,
                "limit_up_count": 0,
                "turnover_change": 0.0,
                "node_count": len(node_ids),
                "stock_count": total_stocks,
                "sample_count": sample_count,
            }
        except Exception:
            return self._empty_summary(chain_id)

    def calc_node_metrics(self, chain_id: str, node_id: str) -> Dict[str, Any]:
        """计算节点指标。"""
        try:
            mappings = self.mapping_loader.load_mappings(chain_id=chain_id, node_id=node_id)
            if not mappings:
                return self._empty_metrics(node_id)

            count = len(mappings)
            sample_count = sum(1 for m in mappings if m.is_sample)
            avg_relevance = sum(m.relevance_score for m in mappings) / count
            avg_purity = sum(m.purity_score for m in mappings) / count
            hot_score = (avg_relevance * 0.5 + avg_purity * 0.5) * 100

            return {
                "node_id": node_id,
                "hot_score": round(hot_score, 2),
                "market_strength": 0.0,
                "stock_count": count,
                "limit_up_count": 0,
                "avg_return_1d": 0.0,
                "avg_return_5d": 0.0,
                "sample_count": sample_count,
            }
        except Exception:
            return self._empty_metrics(node_id)

    def _empty_summary(self, chain_id: str) -> Dict[str, Any]:
        """空摘要。"""
        return {
            "chain_id": chain_id,
            "hot_score": 0.0,
            "market_strength": 0.0,
            "limit_up_count": 0,
            "turnover_change": 0.0,
            "node_count": 0,
            "stock_count": 0,
            "sample_count": 0,
        }

    def _empty_metrics(self, node_id: str) -> Dict[str, Any]:
        """空指标。"""
        return {
            "node_id": node_id,
            "hot_score": 0.0,
            "market_strength": 0.0,
            "stock_count": 0,
            "limit_up_count": 0,
            "avg_return_1d": 0.0,
            "avg_return_5d": 0.0,
            "sample_count": 0,
        }
