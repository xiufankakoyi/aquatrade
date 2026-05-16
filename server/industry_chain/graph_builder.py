"""Build ECharts graph data for IndustryChainRadar."""

from __future__ import annotations

from typing import Any

from server.industry_chain.node_metrics_service import NodeMetricsService
from server.industry_chain.schema import IndustryChain


class GraphBuilder:
    """Convert chain definitions plus auto metrics into frontend graph data."""

    LAYER_COLORS = {
        "upstream": "#3dd6a3",
        "component": "#4cc9f0",
        "product": "#f5b84b",
        "application": "#a78bfa",
    }

    TYPE_SIZES = {
        "theme": 80,
        "product": 60,
        "component": 50,
        "material": 45,
        "technology": 45,
        "service": 40,
        "application": 55,
    }

    def __init__(self) -> None:
        self.metrics_service = NodeMetricsService()

    def build_graph(self, chain: IndustryChain, trade_date: str | None = None) -> dict[str, Any]:
        if chain is None:
            return {"nodes": [], "edges": [], "layers": [], "summary": {}}

        metrics_map = self.metrics_service.get_chain_metrics(chain.chain_id, trade_date)
        layers = sorted(chain.layers, key=lambda layer: layer.order)
        layer_dict = {layer.id: layer for layer in layers}
        layer_x_positions = {}
        if layers:
            step = 800 / max(len(layers) - 1, 1)
            for index, layer in enumerate(layers):
                layer_x_positions[layer.id] = index * step

        nodes: list[dict[str, Any]] = []
        for node in chain.nodes:
            layer = layer_dict.get(node.layer)
            metrics = metrics_map.get(node.id, {})
            same_layer_nodes = sorted([item for item in chain.nodes if item.layer == node.layer], key=lambda item: item.order)
            node_index = same_layer_nodes.index(node) if node in same_layer_nodes else 0
            layer_height = max(len(same_layer_nodes) * 80, 200)
            x = layer_x_positions.get(node.layer, 0)
            y = (node_index - (len(same_layer_nodes) - 1) / 2) * 80 + layer_height / 2
            hot_score = _to_float(metrics.get("hot_score"))
            base_size = self.TYPE_SIZES.get(node.type, 40)
            size = base_size * (0.6 + 0.4 * (node.importance / 10.0) + 0.2 * (hot_score / 100.0))
            candidate_count = _to_int(metrics.get("candidate_count", metrics.get("stock_count", 0)))

            nodes.append(
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.type,
                    "layer": node.layer,
                    "layer_name": layer.name if layer else node.layer,
                    "order": node.order,
                    "aliases": node.aliases,
                    "keywords": node.keywords,
                    "description": node.description,
                    "x": x,
                    "y": y,
                    "fixed": True,
                    "importance": node.importance,
                    "hot_score": hot_score,
                    "hot_score_source": "自动更新" if candidate_count else "",
                    "market_strength": str(metrics.get("market_strength", "很弱") or "很弱"),
                    "stock_count": candidate_count,
                    "candidate_count": candidate_count,
                    "verified_stock_count": _to_int(metrics.get("verified_stock_count")),
                    "candidate_stock_count": candidate_count,
                    "limit_up_count": _to_int(metrics.get("limit_up_count")),
                    "avg_return_1d": _to_float(metrics.get("avg_pct_chg", metrics.get("avg_return_1d"))),
                    "avg_pct_chg": _to_float(metrics.get("avg_pct_chg", metrics.get("avg_return_1d"))),
                    "avg_return_5d": _to_float(metrics.get("avg_return_5d")),
                    "total_amount": _to_float(metrics.get("total_amount")),
                    "main_net_inflow": _to_float(metrics.get("main_net_inflow")),
                    "provider_summary": str(metrics.get("provider_summary", "")),
                    "updated_at": str(metrics.get("updated_at", "")),
                    "symbolSize": min(size, 100),
                    "itemStyle": {
                        "color": self.LAYER_COLORS.get(node.layer, "#94a3b8"),
                        "borderColor": "#fff",
                        "borderWidth": 1,
                        "shadowBlur": 10,
                        "shadowColor": self.LAYER_COLORS.get(node.layer, "#94a3b8"),
                    },
                    "label": {
                        "show": True,
                        "fontSize": 12,
                        "color": "#e2e8f0",
                        "fontWeight": "bold",
                    },
                }
            )

        edges = [
            {
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "label": {"show": True, "formatter": edge.label, "fontSize": 10, "color": "#64748b"},
                "lineStyle": {"color": "#475569", "width": 1.5, "curveness": 0.2},
                "description": edge.description,
            }
            for edge in chain.edges
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "layers": [{"id": layer.id, "name": layer.name, "order": layer.order} for layer in layers],
            "summary": self._build_summary(chain, metrics_map),
        }

    def _build_summary(self, chain: IndustryChain, metrics_map: dict[str, Any]) -> dict[str, Any]:
        total_hot = 0.0
        total_limit_up = 0
        total_stocks = 0
        top_node = ""
        top_hot = -1.0
        latest_update = ""

        for node in chain.nodes:
            metrics = metrics_map.get(node.id, {})
            hot_score = _to_float(metrics.get("hot_score"))
            total_hot += hot_score
            total_limit_up += _to_int(metrics.get("limit_up_count"))
            total_stocks += _to_int(metrics.get("candidate_count", metrics.get("stock_count", 0)))
            if str(metrics.get("updated_at", "")) > latest_update:
                latest_update = str(metrics.get("updated_at", ""))
            if hot_score > top_hot:
                top_hot = hot_score
                top_node = node.id

        node_count = len(chain.nodes)
        avg_hot = total_hot / max(node_count, 1)
        top_node_name = chain.get_node(top_node).name if top_node and chain.get_node(top_node) else ""
        return {
            "chain_id": chain.chain_id,
            "chain_name": chain.name,
            "hot_score": round(avg_hot, 2),
            "market_strength": _market_strength(avg_hot),
            "top_node": top_node,
            "top_node_name": top_node_name,
            "limit_up_count": total_limit_up,
            "turnover_change": 0.0,
            "node_count": node_count,
            "stock_count": total_stocks,
            "updated_at": latest_update,
        }


def _market_strength(hot_score: float) -> str:
    if hot_score >= 80:
        return "很强"
    if hot_score >= 60:
        return "强"
    if hot_score >= 40:
        return "中"
    if hot_score >= 20:
        return "弱"
    return "很弱"


def _to_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(float(value)) if value is not None else 0
    except (TypeError, ValueError):
        return 0
