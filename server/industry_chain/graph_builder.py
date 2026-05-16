"""
IndustryChainRadar Graph Builder

构建适配前端 ECharts Graph 的图谱数据。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.industry_chain.schema import IndustryChain
from server.industry_chain.stock_mapping_service import StockMappingService


class GraphBuilder:
    """图谱构建器。"""

    # 层级颜色映射
    LAYER_COLORS = {
        "upstream": "#FF6B6B",
        "component": "#4ECDC4",
        "product": "#45B7D1",
        "application": "#96CEB4",
    }

    # 节点类型大小映射
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
        self.mapping_service = StockMappingService()

    def build_graph(
        self,
        chain: IndustryChain,
        trade_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        构建 ECharts Graph 数据。

        使用 layer/order 固定布局，形成：
        上游材料 → 中游器件 → 下游产品 → 应用场景
        """
        if chain is None:
            return {"nodes": [], "edges": [], "layers": [], "summary": {}}

        # 获取节点指标
        metrics_map = self.mapping_service.get_chain_metrics(chain.chain_id)

        # 构建层级列表
        layers = sorted(chain.layers, key=lambda l: l.order)
        layer_dict = {l.id: l for l in layers}

        # 计算每个层级的 X 坐标
        layer_x_positions = {}
        if layers:
            step = 800 / max(len(layers) - 1, 1)
            for i, layer in enumerate(layers):
                layer_x_positions[layer.id] = i * step

        # 构建节点
        nodes: List[Dict[str, Any]] = []
        for node in chain.nodes:
            layer = layer_dict.get(node.layer)
            metrics = metrics_map.get(node.id)

            # 计算位置
            x = layer_x_positions.get(node.layer, 0)
            # 同一层级内根据 order 垂直分布
            same_layer_nodes = [n for n in chain.nodes if n.layer == node.layer]
            same_layer_nodes.sort(key=lambda n: n.order)
            node_index = same_layer_nodes.index(node) if node in same_layer_nodes else 0
            layer_height = max(len(same_layer_nodes) * 80, 200)
            y = (node_index - (len(same_layer_nodes) - 1) / 2) * 80 + layer_height / 2

            # 节点大小基于 importance 和 hot_score
            base_size = self.TYPE_SIZES.get(node.type, 40)
            importance_factor = node.importance / 10.0
            hot_score = metrics.get("hot_score", 0.0) if metrics else 0.0
            hot_factor = hot_score / 100.0
            size = base_size * (0.6 + 0.4 * importance_factor + 0.2 * hot_factor)

            nodes.append({
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
                "hot_score": metrics.get("hot_score", 0.0) if metrics else 0.0,
                "hot_score_source": "本地映射" if metrics and metrics.get("stock_count", 0) else "",
                "market_strength": metrics.get("market_strength", 0.0) if metrics else 0.0,
                "stock_count": metrics.get("stock_count", 0) if metrics else 0,
                "verified_stock_count": metrics.get("verified_stock_count", 0) if metrics else 0,
                "candidate_stock_count": metrics.get("candidate_stock_count", 0) if metrics else 0,
                "limit_up_count": metrics.get("limit_up_count", 0) if metrics else 0,
                "avg_return_1d": metrics.get("avg_return_1d", 0.0) if metrics else 0.0,
                "avg_return_5d": metrics.get("avg_return_5d", 0.0) if metrics else 0.0,
                "total_amount": metrics.get("total_amount", 0.0) if metrics else 0.0,
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
            })

        # 构建边
        edges: List[Dict[str, Any]] = []
        for edge in chain.edges:
            edges.append({
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "label": {
                    "show": True,
                    "formatter": edge.label,
                    "fontSize": 10,
                    "color": "#64748b",
                },
                "lineStyle": {
                    "color": "#475569",
                    "width": 1.5,
                    "curveness": 0.2,
                },
                "description": edge.description,
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "layers": [{"id": l.id, "name": l.name, "order": l.order} for l in layers],
            "summary": self._build_summary(chain, metrics_map),
        }

    def _build_summary(
        self,
        chain: IndustryChain,
        metrics_map: Dict[str, Any],
    ) -> Dict[str, Any]:
        """构建产业链摘要。"""
        total_hot = 0.0
        total_strength = 0.0
        total_limit_up = 0
        total_stocks = 0
        top_node = ""
        top_hot = -1.0

        for node in chain.nodes:
            metrics = metrics_map.get(node.id)
            if metrics:
                total_hot += metrics.get("hot_score", 0.0)
                total_strength += metrics.get("market_strength", 0.0)
                total_limit_up += metrics.get("limit_up_count", 0)
                total_stocks += metrics.get("stock_count", 0)
                if metrics.get("hot_score", 0.0) > top_hot:
                    top_hot = metrics.get("hot_score", 0.0)
                    top_node = node.id

        node_count = len(chain.nodes)
        avg_hot = total_hot / max(node_count, 1)
        avg_strength = total_strength / max(node_count, 1)

        top_node_name = ""
        if top_node:
            node = chain.get_node(top_node)
            if node:
                top_node_name = node.name

        return {
            "chain_id": chain.chain_id,
            "chain_name": chain.name,
            "hot_score": round(avg_hot, 2),
            "market_strength": round(avg_strength, 2),
            "top_node": top_node,
            "top_node_name": top_node_name,
            "limit_up_count": total_limit_up,
            "turnover_change": 0.0,
            "node_count": node_count,
            "stock_count": total_stocks,
        }
