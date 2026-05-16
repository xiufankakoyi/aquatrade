"""
IndustryChainRadar Schema Definitions

定义产业链雷达模块的数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChainLayer:
    """产业链层级定义。"""

    id: str
    name: str
    order: int


@dataclass
class ChainNode:
    """产业链节点定义。"""

    id: str
    name: str
    type: str
    layer: str
    order: int
    aliases: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    description: str = ""
    importance: float = 5.0


@dataclass
class ChainEdge:
    """产业链边（关系）定义。"""

    source: str
    target: str
    relation: str
    label: str
    description: str = ""


@dataclass
class IndustryChain:
    """产业链定义。"""

    chain_id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    layers: List[ChainLayer] = field(default_factory=list)
    nodes: List[ChainNode] = field(default_factory=list)
    edges: List[ChainEdge] = field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[ChainNode]:
        """根据 ID 获取节点。"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_layer(self, layer_id: str) -> Optional[ChainLayer]:
        """根据 ID 获取层级。"""
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def get_upstream_nodes(self, node_id: str) -> List[ChainNode]:
        """获取指定节点的上游节点。"""
        upstream_ids = {e.source for e in self.edges if e.target == node_id}
        return [n for n in self.nodes if n.id in upstream_ids]

    def get_downstream_nodes(self, node_id: str) -> List[ChainNode]:
        """获取指定节点的下游节点。"""
        downstream_ids = {e.target for e in self.edges if e.source == node_id}
        return [n for n in self.nodes if n.id in downstream_ids]

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "chain_id": self.chain_id,
            "name": self.name,
            "aliases": self.aliases,
            "description": self.description,
            "layers": [{"id": l.id, "name": l.name, "order": l.order} for l in self.layers],
            "nodes": [{"id": n.id, "name": n.name, "type": n.type, "layer": n.layer, "order": n.order,
                       "aliases": n.aliases, "keywords": n.keywords, "description": n.description,
                       "importance": n.importance} for n in self.nodes],
            "edges": [{"source": e.source, "target": e.target, "relation": e.relation,
                       "label": e.label, "description": e.description} for e in self.edges],
        }


@dataclass
class StockMapping:
    """个股与产业链节点映射。"""

    chain_id: str
    node_id: str
    symbol: str
    stock_name: str
    chain_position: str = ""
    relevance_score: float = 0.0
    purity_score: float = 0.0
    evidence_score: float = 0.0
    market_confirm_score: float = 0.0
    final_score: float = 0.0
    evidence_type: str = ""
    evidence_text: str = ""
    evidence_source: str = ""
    updated_at: str = ""
    is_verified: bool = False
    is_sample: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "chain_id": self.chain_id,
            "node_id": self.node_id,
            "symbol": self.symbol,
            "stock_name": self.stock_name,
            "chain_position": self.chain_position,
            "relevance_score": round(self.relevance_score, 2),
            "purity_score": round(self.purity_score, 2),
            "evidence_score": round(self.evidence_score, 2),
            "market_confirm_score": round(self.market_confirm_score, 2),
            "final_score": round(self.final_score, 2),
            "evidence_type": self.evidence_type,
            "evidence_text": self.evidence_text,
            "evidence_source": self.evidence_source,
            "updated_at": self.updated_at,
            "is_verified": self.is_verified,
            "is_sample": self.is_sample,
        }


@dataclass
class NodeMetrics:
    """节点市场指标。"""

    node_id: str
    hot_score: float = 0.0
    market_strength: float = 0.0
    stock_count: int = 0
    limit_up_count: int = 0
    avg_return_1d: float = 0.0
    avg_return_5d: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "node_id": self.node_id,
            "hot_score": round(self.hot_score, 2),
            "market_strength": round(self.market_strength, 2),
            "stock_count": self.stock_count,
            "limit_up_count": self.limit_up_count,
            "avg_return_1d": round(self.avg_return_1d, 2),
            "avg_return_5d": round(self.avg_return_5d, 2),
        }


@dataclass
class ChainSummary:
    """产业链摘要。"""

    chain_id: str
    chain_name: str
    hot_score: float = 0.0
    market_strength: float = 0.0
    top_node: str = ""
    top_node_name: str = ""
    limit_up_count: int = 0
    turnover_change: float = 0.0
    node_count: int = 0
    stock_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "chain_id": self.chain_id,
            "chain_name": self.chain_name,
            "hot_score": round(self.hot_score, 2),
            "market_strength": round(self.market_strength, 2),
            "top_node": self.top_node,
            "top_node_name": self.top_node_name,
            "limit_up_count": self.limit_up_count,
            "turnover_change": round(self.turnover_change, 2),
            "node_count": self.node_count,
            "stock_count": self.stock_count,
        }
