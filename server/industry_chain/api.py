"""
IndustryChainRadar API

Flask Blueprint for industry chain radar APIs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from server.data_providers import get_available_providers
from server.data_providers.manual_provider import ManualProvider
from server.data_providers.tushare_provider import TushareProvider
from server.data_providers.akshare_provider import AkshareProvider
from server.data_sync.sync_industry_data import IndustryDataSync
from server.industry_chain.evidence_service import EvidenceService
from server.industry_chain.graph_builder import GraphBuilder
from server.industry_chain.loader import ChainLoader, MappingLoader, default_knowledge_dir, project_root
from server.industry_chain.metrics_service import MetricsService
from server.industry_chain.node_metrics_service import NodeMetricsService
from server.industry_chain.stock_enricher import StockEnricher
from server.industry_chain.stock_mapping_service import StockMappingService

industry_chain_bp = Blueprint("industry_chain", __name__, url_prefix="/api/industry-chain")


RESEARCH_BOUNDARY = "仅展示本地维护的产业链资料、证据和市场统计，不构成买入、卖出或仓位建议。"


def _response(data: Any, message: str | None = None, count: int | None = None):
    payload: Dict[str, Any] = {
        "success": True,
        "data": data,
        "research_boundary": RESEARCH_BOUNDARY,
    }
    if message is not None:
        payload["message"] = message
    if count is not None:
        payload["count"] = count
    return jsonify(payload)


def _error(message: str, status: int = 400):
    return (
        jsonify(
            {
                "success": False,
                "error": message,
                "research_boundary": RESEARCH_BOUNDARY,
            }
        ),
        status,
    )


@industry_chain_bp.route("/chains", methods=["GET"])
def list_chains():
    """List all available industry chains."""
    loader = ChainLoader()
    chains = loader.list_chains()
    return _response(chains, count=len(chains))


@industry_chain_bp.route("/graph", methods=["GET"])
def get_graph():
    """Get ECharts Graph data for a chain."""
    chain_id = request.args.get("chain_id", "").strip()
    trade_date = request.args.get("trade_date", "").strip() or None

    if not chain_id:
        return _error("chain_id is required", 400)

    loader = ChainLoader()
    chain = loader.load_chain(chain_id)
    if chain is None:
        return _error(f"unknown chain_id: {chain_id}", 404)

    builder = GraphBuilder()
    graph_data = builder.build_graph(chain, trade_date)
    return _response(graph_data)


@industry_chain_bp.route("/node/<node_id>", methods=["GET"])
def get_node(node_id: str):
    """Get node details with upstream/downstream info."""
    chain_id = request.args.get("chain_id", "").strip()
    if not chain_id:
        return _error("chain_id is required", 400)

    loader = ChainLoader()
    chain = loader.load_chain(chain_id)
    if chain is None:
        return _error(f"unknown chain_id: {chain_id}", 404)

    node = chain.get_node(node_id)
    if node is None:
        return _error(f"unknown node_id: {node_id}", 404)

    layer = chain.get_layer(node.layer)
    upstream = chain.get_upstream_nodes(node_id)
    downstream = chain.get_downstream_nodes(node_id)

    metrics_service = MetricsService()
    metrics = metrics_service.calc_node_metrics(chain_id, node_id)

    mapping_service = StockMappingService()
    stocks = mapping_service.get_node_stocks(chain_id, node_id)

    data = {
        "node": {
            "id": node.id,
            "name": node.name,
            "type": node.type,
            "layer": node.layer,
            "layer_name": layer.name if layer else node.layer,
            "order": node.order,
            "aliases": node.aliases,
            "keywords": node.keywords,
            "description": node.description,
            "importance": node.importance,
        },
        "upstream": [{"id": n.id, "name": n.name, "type": n.type} for n in upstream],
        "downstream": [{"id": n.id, "name": n.name, "type": n.type} for n in downstream],
        "metrics": metrics,
        "stock_count": len(stocks),
        "stocks": stocks,
    }

    return _response(data)


@industry_chain_bp.route("/node/<node_id>/stocks", methods=["GET"])
def get_node_stocks(node_id: str):
    """Get enriched stock list for a node."""
    chain_id = request.args.get("chain_id", "").strip()
    if not chain_id:
        return _error("chain_id is required", 400)

    loader = ChainLoader()
    chain = loader.load_chain(chain_id)
    if chain is None:
        return _error(f"unknown chain_id: {chain_id}", 404)

    if chain.get_node(node_id) is None:
        return _error(f"unknown node_id: {node_id}", 404)

    include_candidates = request.args.get("include_candidates", "true").lower() == "true"
    verified_only = request.args.get("verified_only", "false").lower() == "true"
    sort_by = request.args.get("sort_by", "final_score").strip()

    enricher = StockEnricher()
    stocks = enricher.get_node_stocks(
        chain_id=chain_id,
        node_id=node_id,
        include_candidates=include_candidates,
        verified_only=verified_only,
        sort_by=sort_by,
    )

    evidence_service = EvidenceService()
    evidence_summary = evidence_service.get_node_evidence_summary(chain_id, node_id)

    node_metrics_service = NodeMetricsService()
    market_metrics = node_metrics_service.get_node_metrics(chain_id, node_id)

    data = {
        "verified_stocks": [s for s in stocks if s.get("is_verified")],
        "candidate_stocks": [s for s in stocks if s.get("is_candidate")],
        "evidence_summary": evidence_summary,
        "market_metrics": market_metrics,
        "rows": stocks,
    }

    message = None
    if not stocks:
        message = "当前仅有产业链结构，暂无本地公司证据。请维护 company_evidence.csv 或运行 sync_industry_data.py 获取外部候选。"

    return _response(data, message=message, count=len(stocks))


@industry_chain_bp.route("/search", methods=["GET"])
def search():
    """Search chains and nodes by keyword."""
    q = request.args.get("q", "").strip()
    if not q:
        return _error("q is required", 400)

    query = q.lower()
    loader = ChainLoader()
    all_chains = loader.list_chains()

    results: Dict[str, Any] = {
        "chains": [],
        "nodes": [],
    }

    for chain_summary in all_chains:
        chain_id = chain_summary["chain_id"]
        chain = loader.load_chain(chain_id)
        if chain is None:
            continue

        haystack = " ".join(
            [
                chain.chain_id,
                chain.name,
                " ".join(chain.aliases),
                chain.description,
            ]
        ).lower()
        if query in haystack:
            results["chains"].append(
                {
                    "chain_id": chain.chain_id,
                    "name": chain.name,
                    "aliases": chain.aliases,
                    "description": chain.description,
                }
            )

        for node in chain.nodes:
            node_haystack = " ".join(
                [
                    node.id,
                    node.name,
                    " ".join(node.aliases),
                    " ".join(node.keywords),
                    node.description,
                ]
            ).lower()
            if query in node_haystack:
                layer = chain.get_layer(node.layer)
                results["nodes"].append(
                    {
                        "chain_id": chain.chain_id,
                        "chain_name": chain.name,
                        "node_id": node.id,
                        "node_name": node.name,
                        "type": node.type,
                        "layer": node.layer,
                        "layer_name": layer.name if layer else node.layer,
                        "aliases": node.aliases,
                        "keywords": node.keywords,
                        "description": node.description,
                    }
                )

    return _response(results, count=len(results["chains"]) + len(results["nodes"]))


@industry_chain_bp.route("/data-sources/status", methods=["GET"])
def data_sources_status():
    """返回各数据源状态。"""
    manual = ManualProvider()
    tushare = TushareProvider()
    akshare = AkshareProvider()

    output_dir = Path(__file__).resolve().parents[2] / "data" / "industry"
    parquet_files = {
        "concept_members": (output_dir / "concept_members.parquet").exists(),
        "company_evidence": (output_dir / "company_evidence.parquet").exists(),
        "stock_market_snapshot": (output_dir / "stock_market_snapshot.parquet").exists(),
        "node_market_metrics": (output_dir / "node_market_metrics.parquet").exists(),
    }

    # 最近同步时间
    last_sync = None
    for fname in parquet_files:
        fpath = output_dir / f"{fname}.parquet"
        if fpath.exists():
            mtime = fpath.stat().st_mtime
            from datetime import datetime
            dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            if last_sync is None or dt > last_sync:
                last_sync = dt

    data = {
        "manual_provider": manual.health(),
        "tushare": tushare.health(),
        "akshare": akshare.health(),
        "last_sync": last_sync,
        "parquet_files": parquet_files,
    }
    return _response(data)


@industry_chain_bp.route("/debug", methods=["GET"])
def debug_status():
    """返回产业链雷达诊断信息，便于定位空页面原因。"""
    root = project_root()
    knowledge_path = default_knowledge_dir()
    chains_dir = knowledge_path / "industry_chains"

    loader = ChainLoader(chains_dir=chains_dir)
    loaded_chains = loader.list_chains()
    optical_chain = loader.load_chain("optical_communication")

    mapping_loader = MappingLoader()
    stock_mapping_count = len(mapping_loader.load_mappings(chain_id="optical_communication"))

    data = {
        "project_root": str(root),
        "knowledge_path": str(knowledge_path),
        "industry_chain_files": sorted(path.name for path in chains_dir.glob("*.yaml")) if chains_dir.exists() else [],
        "loaded_chains": [item.get("chain_id", "") for item in loaded_chains],
        "optical_communication_exists": optical_chain is not None,
        "node_count": len(optical_chain.nodes) if optical_chain else 0,
        "edge_count": len(optical_chain.edges) if optical_chain else 0,
        "stock_mapping_count": stock_mapping_count,
    }
    return _response(data)


@industry_chain_bp.route("/sync", methods=["POST"])
def trigger_sync():
    """触发一次同步（可选）。"""
    chain_id = request.args.get("chain_id", "").strip() or None
    trade_date = request.args.get("trade_date", "").strip() or None

    sync = IndustryDataSync()
    summary = sync.sync_all(chain_id=chain_id, trade_date=trade_date)
    return _response(summary)
