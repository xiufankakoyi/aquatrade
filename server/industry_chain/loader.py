"""
IndustryChainRadar Loader

加载产业链配置和个股映射，支持缓存。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.industry_chain.schema import (
    ChainEdge,
    ChainLayer,
    ChainNode,
    IndustryChain,
    StockMapping,
)


# 全局缓存
_chain_cache: Dict[str, IndustryChain] = {}
_mapping_cache: Dict[str, List[StockMapping]] = {}
_chains_list_cache: Optional[List[Dict[str, Any]]] = None


def project_root() -> Path:
    """获取项目根目录。"""
    return Path(__file__).resolve().parents[2]


def default_knowledge_dir() -> Path:
    """获取知识库目录。"""
    return project_root() / "knowledge"


def clear_cache() -> None:
    """清除缓存。"""
    global _chain_cache, _mapping_cache, _chains_list_cache
    _chain_cache.clear()
    _mapping_cache.clear()
    _chains_list_cache = None


class ChainLoader:
    """产业链配置加载器。"""

    def __init__(self, chains_dir: Optional[Path] = None) -> None:
        self.chains_dir = chains_dir or (default_knowledge_dir() / "industry_chains")

    def list_chains(self) -> List[Dict[str, Any]]:
        """列出所有可用的产业链。"""
        global _chains_list_cache
        if _chains_list_cache is not None:
            return _chains_list_cache

        results: List[Dict[str, Any]] = []
        if not self.chains_dir.exists():
            _chains_list_cache = results
            return results

        for file_path in self.chains_dir.glob("*.yaml"):
            try:
                chain = self._load_single(file_path)
                results.append({
                    "chain_id": chain.chain_id,
                    "name": chain.name,
                    "aliases": chain.aliases,
                    "description": chain.description,
                    "node_count": len(chain.nodes),
                })
            except Exception:
                continue

        _chains_list_cache = results
        return results

    def load_chain(self, chain_id: str) -> Optional[IndustryChain]:
        """加载指定产业链配置。"""
        if chain_id in _chain_cache:
            return _chain_cache[chain_id]

        file_path = self.chains_dir / f"{chain_id}.yaml"
        if not file_path.exists():
            return None

        chain = self._load_single(file_path)
        _chain_cache[chain_id] = chain
        return chain

    def _load_single(self, file_path: Path) -> IndustryChain:
        """从 YAML 文件加载单个产业链。"""
        text = file_path.read_text(encoding="utf-8-sig").strip()
        if not text:
            raise ValueError(f"Empty file: {file_path}")

        data = json.loads(text)
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid format in {file_path}")

        layers = [
            ChainLayer(
                id=str(l.get("id", "")),
                name=str(l.get("name", "")),
                order=int(l.get("order", 0)),
            )
            for l in data.get("layers", [])
        ]

        nodes = [
            ChainNode(
                id=str(n.get("id", "")),
                name=str(n.get("name", "")),
                type=str(n.get("type", "")),
                layer=str(n.get("layer", "")),
                order=int(n.get("order", 0)),
                aliases=_as_list(n.get("aliases")),
                keywords=_as_list(n.get("keywords")),
                description=str(n.get("description", "")),
                importance=float(n.get("importance", 5.0)),
            )
            for n in data.get("nodes", [])
        ]

        edges = [
            ChainEdge(
                source=str(e.get("source", "")),
                target=str(e.get("target", "")),
                relation=str(e.get("relation", "")),
                label=str(e.get("label", "")),
                description=str(e.get("description", "")),
            )
            for e in data.get("edges", [])
        ]

        return IndustryChain(
            chain_id=str(data.get("chain_id", "")),
            name=str(data.get("name", "")),
            aliases=_as_list(data.get("aliases")),
            description=str(data.get("description", "")),
            layers=layers,
            nodes=nodes,
            edges=edges,
        )


class MappingLoader:
    """个股映射加载器。"""

    def __init__(self, mapping_path: Optional[Path] = None) -> None:
        self.mapping_path = mapping_path or (default_knowledge_dir() / "concept_stock_mapping.csv")

    def load_mappings(
        self,
        chain_id: Optional[str] = None,
        node_id: Optional[str] = None,
        include_samples: bool = False,
    ) -> List[StockMapping]:
        """加载个股映射。"""
        cache_key = f"{chain_id or '_all'}:{node_id or '_all'}:{'sample' if include_samples else 'verified'}"
        if cache_key in _mapping_cache:
            return _mapping_cache[cache_key]

        if not self.mapping_path.exists():
            return []

        rows: List[StockMapping] = []
        with self.mapping_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not (row.get("symbol") or "").strip():
                    continue
                if chain_id and row.get("chain_id") != chain_id:
                    continue
                if node_id and row.get("node_id") != node_id:
                    continue
                mapping = _parse_mapping_row(row)
                if mapping.is_sample and not include_samples:
                    continue
                rows.append(mapping)

        _mapping_cache[cache_key] = rows
        return rows

    def get_node_stock_count(self, chain_id: str, node_id: str) -> int:
        """获取节点的个股数量。"""
        mappings = self.load_mappings(chain_id=chain_id, node_id=node_id)
        return len(mappings)


def _as_list(value: Any) -> List[str]:
    """将值转换为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace("；", ";").split(";") if part.strip()]


def _parse_mapping_row(row: Dict[str, str]) -> StockMapping:
    """解析 CSV 行到 StockMapping。"""
    return StockMapping(
        chain_id=str(row.get("chain_id", "")),
        node_id=str(row.get("node_id", "")),
        symbol=str(row.get("symbol", "")),
        stock_name=str(row.get("stock_name", "")),
        chain_position=str(row.get("chain_position", "")),
        relevance_score=_parse_float(row.get("relevance_score", "0")),
        purity_score=_parse_float(row.get("purity_score", "0")),
        evidence_score=_parse_float(row.get("evidence_score", "0")),
        market_confirm_score=_parse_float(row.get("market_confirm_score", "0")),
        final_score=_parse_float(row.get("final_score", "0")),
        evidence_type=str(row.get("evidence_type", "")),
        evidence_text=str(row.get("evidence_text", "")),
        evidence_source=str(row.get("evidence_source", "")),
        updated_at=str(row.get("updated_at", "")),
        is_verified=str(row.get("is_verified", "")).lower() in ("true", "1", "yes"),
        is_sample=str(row.get("is_sample", "")).lower() in ("true", "1", "yes"),
    )


def _parse_float(value: str) -> float:
    """安全解析浮点数。"""
    try:
        return float(value) if value else 0.0
    except (TypeError, ValueError):
        return 0.0
