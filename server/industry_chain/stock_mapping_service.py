"""
IndustryChainRadar Stock Mapping Service

个股映射查询服务，支持降级处理。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.industry_chain.loader import MappingLoader
from server.industry_chain.schema import StockMapping


class StockMappingService:
    """个股映射服务。"""

    def __init__(self) -> None:
        self.loader = MappingLoader()

    def get_node_stocks(self, chain_id: str, node_id: str) -> List[Dict[str, Any]]:
        """获取节点的相关个股。"""
        try:
            mappings = self.loader.load_mappings(chain_id=chain_id, node_id=node_id)
            return [m.to_dict() for m in mappings]
        except Exception:
            return []

    def get_chain_stocks(self, chain_id: str) -> List[Dict[str, Any]]:
        """获取产业链的所有个股。"""
        try:
            mappings = self.loader.load_mappings(chain_id=chain_id)
            return [m.to_dict() for m in mappings]
        except Exception:
            return []

    def get_node_metrics(self, chain_id: str, node_id: str) -> Dict[str, Any]:
        """获取节点的市场指标。"""
        try:
            mappings = self.loader.load_mappings(chain_id=chain_id, node_id=node_id)
            return self._calc_metrics(mappings)
        except Exception:
            return self._empty_metrics()

    def get_chain_metrics(self, chain_id: str) -> Dict[str, Dict[str, Any]]:
        """获取产业链所有节点的市场指标。"""
        result: Dict[str, Dict[str, Any]] = {}
        try:
            mappings = self.loader.load_mappings(chain_id=chain_id)
            # 按 node_id 分组
            node_mappings: Dict[str, List[StockMapping]] = {}
            for m in mappings:
                if m.node_id not in node_mappings:
                    node_mappings[m.node_id] = []
                node_mappings[m.node_id].append(m)

            for node_id, maps in node_mappings.items():
                result[node_id] = self._calc_metrics(maps)

            return result
        except Exception:
            return result

    def _calc_metrics(self, mappings: List[StockMapping]) -> Dict[str, Any]:
        """计算指标。"""
        if not mappings:
            return self._empty_metrics()

        count = len(mappings)
        sample_count = sum(1 for m in mappings if m.is_sample)

        # 基于映射数据计算热度（简化版）
        avg_relevance = sum(m.relevance_score for m in mappings) / count
        avg_purity = sum(m.purity_score for m in mappings) / count
        hot_score = (avg_relevance * 0.5 + avg_purity * 0.5) * 100

        return {
            "node_id": mappings[0].node_id if mappings else "",
            "hot_score": round(hot_score, 2),
            "market_strength": 0.0,
            "stock_count": count,
            "verified_stock_count": sum(1 for m in mappings if m.is_verified),
            "candidate_stock_count": 0,
            "limit_up_count": 0,
            "avg_return_1d": 0.0,
            "avg_return_5d": 0.0,
            "total_amount": 0.0,
            "sample_count": sample_count,
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        """空指标。"""
        return {
            "node_id": "",
            "hot_score": 0.0,
            "market_strength": 0.0,
            "stock_count": 0,
            "verified_stock_count": 0,
            "candidate_stock_count": 0,
            "limit_up_count": 0,
            "avg_return_1d": 0.0,
            "avg_return_5d": 0.0,
            "total_amount": 0.0,
            "sample_count": 0,
        }
