"""Flask API for IndustryChainRadar."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Blueprint, jsonify, request

from server.data_providers.provider_registry import ProviderRegistry
from server.data_sync.sync_industry_data import IndustryDataSync
from server.industry_chain.evidence_service import EvidenceService
from server.industry_chain.graph_builder import GraphBuilder
from server.industry_chain.loader import ChainLoader, MappingLoader, default_knowledge_dir, project_root
from server.industry_chain.node_metrics_service import NodeMetricsService
from server.industry_chain.stock_enricher import StockEnricher

industry_chain_bp = Blueprint("industry_chain", __name__, url_prefix="/api/industry-chain")

RESEARCH_BOUNDARY = "仅展示本地维护的产业链资料、证据、自动候选和市场统计，不构成买入、卖出、仓位、止盈或止损建议。"
EMPTY_UPDATE_MESSAGE = "自动调度尚未生成产业链数据，请等待后端启动后的自动更新；排障时可使用 python tools/update_industry_data_daily.py --all"


def _response(data: Any, message: str | None = None, count: int | None = None):
    payload: dict[str, Any] = {"success": True, "data": data, "research_boundary": RESEARCH_BOUNDARY}
    if message is not None:
        payload["message"] = message
    if count is not None:
        payload["count"] = count
    return jsonify(payload)


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message, "research_boundary": RESEARCH_BOUNDARY}), status


@industry_chain_bp.route("/chains", methods=["GET"])
def list_chains():
    loader = ChainLoader()
    chains = loader.list_chains()
    return _response(chains, count=len(chains))


@industry_chain_bp.route("/graph", methods=["GET"])
def get_graph():
    chain_id = request.args.get("chain_id", "").strip()
    trade_date = request.args.get("trade_date", "").strip() or None
    if not chain_id:
        return _error("chain_id is required", 400)

    chain = ChainLoader().load_chain(chain_id)
    if chain is None:
        return _error(f"unknown chain_id: {chain_id}", 404)

    graph_data = GraphBuilder().build_graph(chain, trade_date)
    return _response(graph_data)


@industry_chain_bp.route("/node/<node_id>", methods=["GET"])
def get_node(node_id: str):
    chain_id = request.args.get("chain_id", "").strip()
    trade_date = request.args.get("trade_date", "").strip() or None
    if not chain_id:
        return _error("chain_id is required", 400)

    chain = ChainLoader().load_chain(chain_id)
    if chain is None:
        return _error(f"unknown chain_id: {chain_id}", 404)
    node = chain.get_node(node_id)
    if node is None:
        return _error(f"unknown node_id: {node_id}", 404)

    layer = chain.get_layer(node.layer)
    metrics = NodeMetricsService().get_node_metrics(chain_id, node_id, trade_date)
    stocks = StockEnricher().get_node_stocks(chain_id, node_id, include_candidates=True, verified_only=False)
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
        "upstream": [{"id": item.id, "name": item.name, "type": item.type} for item in chain.get_upstream_nodes(node_id)],
        "downstream": [{"id": item.id, "name": item.name, "type": item.type} for item in chain.get_downstream_nodes(node_id)],
        "metrics": metrics,
        "stock_count": len(stocks),
        "stocks": stocks,
    }
    return _response(data)


@industry_chain_bp.route("/node/<node_id>/stocks", methods=["GET"])
def get_node_stocks(node_id: str):
    chain_id = request.args.get("chain_id", "").strip()
    if not chain_id:
        return _error("chain_id is required", 400)

    chain = ChainLoader().load_chain(chain_id)
    if chain is None:
        return _error(f"unknown chain_id: {chain_id}", 404)
    if chain.get_node(node_id) is None:
        return _error(f"unknown node_id: {node_id}", 404)

    include_candidates = request.args.get("include_candidates", "true").lower() == "true"
    verified_only = request.args.get("verified_only", "false").lower() == "true"
    sort_by = request.args.get("sort_by", "system_relevance_score").strip()

    stocks = StockEnricher().get_node_stocks(
        chain_id=chain_id,
        node_id=node_id,
        include_candidates=include_candidates,
        verified_only=verified_only,
        sort_by=sort_by,
    )
    evidence_summary = EvidenceService().get_node_evidence_summary(chain_id, node_id)
    market_metrics = NodeMetricsService().get_node_metrics(chain_id, node_id)
    data = {
        "verified_stocks": [item for item in stocks if item.get("is_verified")],
        "candidate_stocks": [item for item in stocks if item.get("is_candidate")],
        "evidence_summary": evidence_summary,
        "market_metrics": market_metrics,
        "rows": stocks,
    }
    return _response(data, message=None if stocks else EMPTY_UPDATE_MESSAGE, count=len(stocks))


@industry_chain_bp.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return _error("q is required", 400)
    query = q.lower()
    loader = ChainLoader()
    results: dict[str, Any] = {"chains": [], "nodes": []}
    for chain_summary in loader.list_chains():
        chain = loader.load_chain(chain_summary["chain_id"])
        if chain is None:
            continue
        chain_text = " ".join([chain.chain_id, chain.name, " ".join(chain.aliases), chain.description]).lower()
        if query in chain_text:
            results["chains"].append(
                {
                    "chain_id": chain.chain_id,
                    "name": chain.name,
                    "aliases": chain.aliases,
                    "description": chain.description,
                }
            )
        for node in chain.nodes:
            node_text = " ".join([node.id, node.name, " ".join(node.aliases), " ".join(node.keywords), node.description]).lower()
            if query not in node_text:
                continue
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
    output_dir = project_root() / "data" / "industry"
    file_names = [
        "market_snapshot.parquet",
        "daily_bars_latest.parquet",
        "concept_boards.parquet",
        "concept_board_members.parquet",
        "limit_up_pool.parquet",
        "board_fund_flow.parquet",
        "stock_fund_flow.parquet",
        "stock_basic_info.parquet",
        "industry_node_candidates.parquet",
        "industry_node_metrics.parquet",
        "industry_graph_cache.parquet",
        "data_source_log.parquet",
    ]
    parquet_files = {name.replace(".parquet", ""): (output_dir / name).exists() for name in file_names}
    parquet_files.update(
        {
            "concept_members": (output_dir / "concept_members.parquet").exists(),
            "company_evidence": (output_dir / "company_evidence.parquet").exists(),
            "stock_market_snapshot": (output_dir / "stock_market_snapshot.parquet").exists(),
            "node_market_metrics": (output_dir / "node_market_metrics.parquet").exists(),
        }
    )

    last_sync = None
    for name, exists in parquet_files.items():
        path = output_dir / f"{name}.parquet"
        if exists and path.exists():
            dt = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            if last_sync is None or dt > last_sync:
                last_sync = dt

    recent_log = []
    log_path = output_dir / "data_source_log.parquet"
    if log_path.exists():
        try:
            recent_log = pd.read_parquet(log_path).tail(20).to_dict("records")
        except Exception:
            recent_log = []

    parquet_row_counts: dict[str, int] = {}
    for name in ("market_snapshot", "industry_node_candidates", "industry_node_metrics"):
        path = output_dir / f"{name}.parquet"
        if not path.exists():
            parquet_row_counts[name] = 0
            continue
        try:
            parquet_row_counts[name] = int(len(pd.read_parquet(path)))
        except Exception:
            parquet_row_counts[name] = 0

    data = {
        "providers": ProviderRegistry().status(),
        "last_sync": last_sync,
        "parquet_files": parquet_files,
        "parquet_row_counts": parquet_row_counts,
        "recent_source_log": recent_log,
        "empty_hint": EMPTY_UPDATE_MESSAGE,
    }
    try:
        from server.industry_chain.auto_update_scheduler import get_industry_auto_update_scheduler

        scheduler = get_industry_auto_update_scheduler()
        scheduler.start()
        if (
            parquet_row_counts.get("industry_node_candidates", 0) == 0
            or parquet_row_counts.get("industry_node_metrics", 0) == 0
            or parquet_row_counts.get("market_snapshot", 0) == 0
        ):
            scheduler.run_once(reason="api_status_empty", force=False)
        data["auto_update_scheduler"] = scheduler.status()
    except Exception as exc:
        data["auto_update_scheduler"] = {"enabled": False, "last_status": "unavailable", "last_error": str(exc)}
    return _response(data)


@industry_chain_bp.route("/debug", methods=["GET"])
def debug_status():
    root = project_root()
    knowledge_path = default_knowledge_dir()
    chains_dir = knowledge_path / "industry_chains"
    loader = ChainLoader(chains_dir=chains_dir)
    loaded_chains = loader.list_chains()
    optical_chain = loader.load_chain("optical_communication")
    stock_mapping_count = len(MappingLoader().load_mappings(chain_id="optical_communication"))
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
    chain_id = request.args.get("chain_id", "").strip() or None
    trade_date = request.args.get("trade_date", "").strip() or None
    summary = IndustryDataSync().sync_all(chain_id=chain_id, trade_date=trade_date)
    return _response(summary)
