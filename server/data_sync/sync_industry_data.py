"""Daily auto update pipeline for AQUATRADE IndustryChainRadar."""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

from server.data_providers.base import (
    BOARD_FUND_FLOW_COLUMNS,
    CONCEPT_BOARD_MEMBERS_COLUMNS,
    CONCEPT_BOARDS_COLUMNS,
    DAILY_BARS_COLUMNS,
    LIMIT_UP_POOL_COLUMNS,
    MARKET_SNAPSHOT_COLUMNS,
    STOCK_BASIC_INFO_COLUMNS,
    STOCK_FUND_FLOW_COLUMNS,
    empty_frame,
    ensure_columns,
    normalize_symbols,
    normalize_trade_date,
    now_text,
)
from server.data_providers.provider_registry import ProviderRegistry
from server.industry_chain.loader import ChainLoader, project_root

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = project_root() / "data" / "industry"

INDUSTRY_NODE_CANDIDATES_COLUMNS = [
    "trade_date",
    "chain_id",
    "node_id",
    "matched_board_name",
    "matched_keyword",
    "symbol",
    "stock_name",
    "candidate_source",
    "provider",
    "source_confidence",
    "auto_relevance_score",
    "updated_at",
]

INDUSTRY_NODE_METRICS_COLUMNS = [
    "trade_date",
    "chain_id",
    "node_id",
    "candidate_count",
    "avg_pct_chg",
    "max_pct_chg",
    "limit_up_count",
    "consecutive_limit_count_max",
    "total_amount",
    "main_net_inflow",
    "hot_score",
    "market_strength",
    "provider_summary",
    "updated_at",
]

INDUSTRY_GRAPH_CACHE_COLUMNS = [
    "trade_date",
    "chain_id",
    "chain_name",
    "node_id",
    "node_name",
    "layer",
    "node_type",
    "hot_score",
    "market_strength",
    "candidate_count",
    "limit_up_count",
    "avg_pct_chg",
    "total_amount",
    "provider_summary",
    "updated_at",
]


class IndustryDataSync:
    """Auto-update industry chain data into local parquet files."""

    def __init__(self, output_dir: Path | None = None, registry: ProviderRegistry | None = None) -> None:
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry or ProviderRegistry()
        self.summary: dict[str, Any] = {}

    def sync_all(self, chain_id: str | None = None, trade_date: str | None = None) -> dict[str, Any]:
        trade_date = normalize_trade_date(trade_date)
        chains = self._load_chains(chain_id)
        if not chains:
            return {"status": "no_chains", "trade_date": trade_date, "chains_synced": []}

        logger.info("Start IndustryChainRadar auto update: chain_id=%s trade_date=%s", chain_id, trade_date)

        market_snapshot = self.registry.get_realtime_quotes(trade_date=trade_date)
        self._write("market_snapshot.parquet", market_snapshot, MARKET_SNAPSHOT_COLUMNS)
        self._write("stock_market_snapshot.parquet", market_snapshot, MARKET_SNAPSHOT_COLUMNS)

        daily_bars = self.registry.get_daily_bars(start_date=trade_date, end_date=trade_date, symbols=None)
        self._write("daily_bars_latest.parquet", daily_bars, DAILY_BARS_COLUMNS)

        concept_boards = self.registry.get_concept_boards(trade_date=trade_date)
        self._write("concept_boards.parquet", concept_boards, CONCEPT_BOARDS_COLUMNS)

        board_matches = self._match_boards_to_nodes(chains, concept_boards, trade_date)
        concept_members = self._fetch_matched_board_members(board_matches, trade_date)
        self._write("concept_board_members.parquet", concept_members, CONCEPT_BOARD_MEMBERS_COLUMNS)

        limit_up_pool = self.registry.get_limit_up_pool(trade_date=trade_date)
        self._write("limit_up_pool.parquet", limit_up_pool, LIMIT_UP_POOL_COLUMNS)

        board_fund_flow = self.registry.get_board_fund_flow(trade_date=trade_date)
        self._write("board_fund_flow.parquet", board_fund_flow, BOARD_FUND_FLOW_COLUMNS)

        stock_fund_flow = self.registry.get_stock_fund_flow(trade_date=trade_date)
        self._write("stock_fund_flow.parquet", stock_fund_flow, STOCK_FUND_FLOW_COLUMNS)

        stock_symbols = sorted(set(concept_members.get("symbol", pd.Series(dtype=str)).dropna().astype(str)))
        stock_basic_info = self.registry.get_stock_basic_info(symbols=stock_symbols or None)
        self._write("stock_basic_info.parquet", stock_basic_info, STOCK_BASIC_INFO_COLUMNS)

        candidates = self._build_node_candidates(
            board_matches=board_matches,
            concept_members=concept_members,
            market_snapshot=market_snapshot,
            limit_up_pool=limit_up_pool,
            stock_fund_flow=stock_fund_flow,
            stock_basic_info=stock_basic_info,
            trade_date=trade_date,
        )
        self._write("industry_node_candidates.parquet", candidates, INDUSTRY_NODE_CANDIDATES_COLUMNS)
        self._write("concept_members.parquet", candidates, INDUSTRY_NODE_CANDIDATES_COLUMNS)

        metrics = self._calc_node_metrics(
            chains=chains,
            candidates=candidates,
            market_snapshot=market_snapshot,
            limit_up_pool=limit_up_pool,
            board_fund_flow=board_fund_flow,
            stock_fund_flow=stock_fund_flow,
            trade_date=trade_date,
        )
        self._write("industry_node_metrics.parquet", metrics, INDUSTRY_NODE_METRICS_COLUMNS)
        self._write("node_market_metrics.parquet", metrics, INDUSTRY_NODE_METRICS_COLUMNS)

        graph_cache = self._build_graph_cache(chains, metrics, trade_date)
        self._write("industry_graph_cache.parquet", graph_cache, INDUSTRY_GRAPH_CACHE_COLUMNS)

        source_log = self.registry.log_frame()
        self._write("data_source_log.parquet", source_log, list(source_log.columns))

        top_nodes = self._top_nodes_by_chain(metrics, chains)
        provider_report = self._provider_report(source_log)
        self.summary = {
            "status": "success",
            "trade_date": trade_date,
            "chains_synced": [chain.chain_id for chain in chains],
            "provider_report": provider_report,
            "market_snapshot_count": len(market_snapshot),
            "daily_bars_count": len(daily_bars),
            "concept_boards_count": len(concept_boards),
            "concept_board_members_count": len(concept_members),
            "limit_up_count": len(limit_up_pool),
            "board_fund_flow_count": len(board_fund_flow),
            "stock_fund_flow_count": len(stock_fund_flow),
            "stock_basic_info_count": len(stock_basic_info),
            "node_candidates_count": len(candidates),
            "node_metrics_count": len(metrics),
            "top_nodes": top_nodes,
            "failed_sources": [
                {
                    "method": str(row.get("method", "")),
                    "provider": str(row.get("provider_used", "")),
                    "context": str(row.get("context", "")),
                    "error": str(row.get("error_message", "")),
                }
                for _, row in source_log[source_log.get("success") == False].iterrows()
            ]
            if not source_log.empty and "success" in source_log.columns
            else [],
        }
        logger.info("IndustryChainRadar auto update finished: %s", self.summary)
        return self.summary

    def _load_chains(self, chain_id: str | None) -> list[Any]:
        loader = ChainLoader()
        if chain_id:
            chain = loader.load_chain(chain_id)
            return [chain] if chain else []
        chains = [loader.load_chain(item["chain_id"]) for item in loader.list_chains()]
        return [chain for chain in chains if chain is not None]

    def _match_boards_to_nodes(self, chains: list[Any], concept_boards: pd.DataFrame, trade_date: str) -> pd.DataFrame:
        columns = [
            "trade_date",
            "chain_id",
            "node_id",
            "board_code",
            "board_name",
            "board_type",
            "matched_keyword",
            "source_confidence",
            "provider",
            "updated_at",
        ]
        if concept_boards.empty:
            return empty_frame(columns)

        rows: list[dict[str, Any]] = []
        for _, board in concept_boards.iterrows():
            board_name = str(board.get("board_name", "")).strip()
            board_code = str(board.get("board_code", "")).strip()
            if not board_name:
                continue
            board_text = _normalize_match_text(board_name)
            for chain in chains:
                for node in chain.nodes:
                    keywords = _node_keywords(node)
                    matched = [kw for kw in keywords if _keyword_matches(_normalize_match_text(kw), board_text)]
                    if not matched:
                        continue
                    confidence = min(1.0, 0.45 + 0.1 * min(len(matched), 4) + (0.1 if board_text in [_normalize_match_text(kw) for kw in matched] else 0))
                    rows.append(
                        {
                            "trade_date": trade_date,
                            "chain_id": chain.chain_id,
                            "node_id": node.id,
                            "board_code": board_code,
                            "board_name": board_name,
                            "board_type": str(board.get("board_type", "concept") or "concept"),
                            "matched_keyword": ";".join(sorted(set(matched))),
                            "source_confidence": round(confidence, 4),
                            "provider": str(board.get("provider", "")),
                            "updated_at": now_text(),
                        }
                    )
        return ensure_columns(pd.DataFrame(rows), columns) if rows else empty_frame(columns)

    def _fetch_matched_board_members(self, board_matches: pd.DataFrame, trade_date: str) -> pd.DataFrame:
        if board_matches.empty:
            return empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)
        frames: list[pd.DataFrame] = []
        seen: set[tuple[str, str]] = set()
        for _, row in board_matches[["board_code", "board_name"]].drop_duplicates().iterrows():
            board_code = str(row.get("board_code", "") or "")
            board_name = str(row.get("board_name", "") or "")
            key = (board_code, board_name)
            if key in seen:
                continue
            seen.add(key)
            df = self.registry.get_concept_board_members(
                board_code_or_name=board_code or board_name,
                board_name=board_name,
                trade_date=trade_date,
            )
            if df is not None and not df.empty:
                frames.append(df)
        return pd.concat(frames, ignore_index=True).drop_duplicates() if frames else empty_frame(CONCEPT_BOARD_MEMBERS_COLUMNS)

    def _build_node_candidates(
        self,
        board_matches: pd.DataFrame,
        concept_members: pd.DataFrame,
        market_snapshot: pd.DataFrame,
        limit_up_pool: pd.DataFrame,
        stock_fund_flow: pd.DataFrame,
        stock_basic_info: pd.DataFrame,
        trade_date: str,
    ) -> pd.DataFrame:
        if board_matches.empty or concept_members.empty:
            return empty_frame(INDUSTRY_NODE_CANDIDATES_COLUMNS)

        matches = board_matches.copy()
        members = concept_members.copy()
        for df in (matches, members):
            df["board_code"] = df.get("board_code", "").astype(str)
            df["board_name"] = df.get("board_name", "").astype(str)
        merged = members.merge(
            matches,
            on=["board_code", "board_name"],
            how="inner",
            suffixes=("_member", "_match"),
        )
        if merged.empty:
            return empty_frame(INDUSTRY_NODE_CANDIDATES_COLUMNS)

        limit_symbols = set(limit_up_pool.get("symbol", pd.Series(dtype=str)).dropna().astype(str))
        flow_map = _df_by_symbol(stock_fund_flow)
        market_map = _df_by_symbol(market_snapshot)
        basic_map = _df_by_symbol(stock_basic_info)

        rows: list[dict[str, Any]] = []
        group_cols = ["chain_id", "node_id", "symbol"]
        for (chain_id, node_id, symbol), group in merged.groupby(group_cols, dropna=True):
            stock_name = _first_non_empty(group.get("stock_name", pd.Series(dtype=str)))
            board_names = sorted(set(str(v) for v in group["board_name"].dropna().astype(str) if str(v)))
            matched_keywords = sorted(_split_keywords(group.get("matched_keyword", pd.Series(dtype=str))))
            providers = sorted(set(str(v) for v in pd.concat([group.get("provider_member", pd.Series(dtype=str)), group.get("provider_match", pd.Series(dtype=str))]).dropna() if str(v)))
            source_confidence = _safe_float(group.get("source_confidence", pd.Series([0])).max())
            board_hit_count = len(board_names)
            auto_score = 0.35 + min(board_hit_count, 4) * 0.08 + min(source_confidence, 1.0) * 0.15
            if symbol in limit_symbols:
                auto_score += 0.10
            flow_row = flow_map.get(symbol, {})
            if _safe_float(flow_row.get("main_net_inflow")) > 0:
                auto_score += 0.08
            market_row = market_map.get(symbol, {})
            if _safe_float(market_row.get("pct_chg")) > 0:
                auto_score += 0.04
            if _profile_hits_keywords(stock_name, basic_map.get(symbol, {}), matched_keywords):
                auto_score += 0.08
            auto_score = round(min(max(auto_score, 0.0), 1.0), 4)

            rows.append(
                {
                    "trade_date": trade_date,
                    "chain_id": str(chain_id),
                    "node_id": str(node_id),
                    "matched_board_name": ";".join(board_names),
                    "matched_keyword": ";".join(matched_keywords),
                    "symbol": str(symbol),
                    "stock_name": stock_name,
                    "candidate_source": "auto_concept_board",
                    "provider": ";".join(providers),
                    "source_confidence": round(source_confidence, 4),
                    "auto_relevance_score": auto_score,
                    "updated_at": now_text(),
                }
            )
        return ensure_columns(pd.DataFrame(rows), INDUSTRY_NODE_CANDIDATES_COLUMNS) if rows else empty_frame(INDUSTRY_NODE_CANDIDATES_COLUMNS)

    def _calc_node_metrics(
        self,
        chains: list[Any],
        candidates: pd.DataFrame,
        market_snapshot: pd.DataFrame,
        limit_up_pool: pd.DataFrame,
        board_fund_flow: pd.DataFrame,
        stock_fund_flow: pd.DataFrame,
        trade_date: str,
    ) -> pd.DataFrame:
        market_map = _df_by_symbol(market_snapshot)
        limit_map = _df_by_symbol(limit_up_pool)
        stock_flow_map = _df_by_symbol(stock_fund_flow)
        board_flow_map = {str(row.get("board_name", "")): row.to_dict() for _, row in board_fund_flow.iterrows()} if not board_fund_flow.empty else {}
        rows: list[dict[str, Any]] = []

        for chain in chains:
            for node in chain.nodes:
                node_candidates = candidates[
                    (candidates.get("chain_id", "") == chain.chain_id) &
                    (candidates.get("node_id", "") == node.id)
                ] if not candidates.empty else pd.DataFrame()
                symbols = sorted(set(node_candidates.get("symbol", pd.Series(dtype=str)).dropna().astype(str)))
                pct_values = [_safe_float(market_map.get(symbol, {}).get("pct_chg")) for symbol in symbols if symbol in market_map]
                pct_values = [value for value in pct_values if not math.isnan(value)]
                amounts = [_safe_float(market_map.get(symbol, {}).get("amount")) for symbol in symbols if symbol in market_map]
                avg_pct_chg = sum(pct_values) / len(pct_values) if pct_values else 0.0
                max_pct_chg = max(pct_values) if pct_values else 0.0
                limit_up_symbols = [symbol for symbol in symbols if symbol in limit_map]
                consecutive_max = max([_safe_float(limit_map[symbol].get("consecutive_limit_count")) for symbol in limit_up_symbols] or [0])
                stock_flow_total = sum(_safe_float(stock_flow_map.get(symbol, {}).get("main_net_inflow")) for symbol in symbols)
                board_names = _split_keywords(node_candidates.get("matched_board_name", pd.Series(dtype=str))) if not node_candidates.empty else []
                board_flow_total = sum(_safe_float(board_flow_map.get(board_name, {}).get("main_net_inflow")) for board_name in set(board_names))
                provider_summary = {
                    "candidate": _provider_counts(node_candidates.get("provider", pd.Series(dtype=str))) if not node_candidates.empty else {},
                    "market": _provider_counts(pd.Series([market_map.get(symbol, {}).get("provider", "") for symbol in symbols])),
                    "fund_flow": _provider_counts(pd.Series([stock_flow_map.get(symbol, {}).get("provider", "") for symbol in symbols])),
                }
                source_confidence = _safe_float(node_candidates.get("source_confidence", pd.Series([0])).mean()) if not node_candidates.empty else 0.0
                rows.append(
                    {
                        "trade_date": trade_date,
                        "chain_id": chain.chain_id,
                        "node_id": node.id,
                        "candidate_count": len(symbols),
                        "avg_pct_chg": round(avg_pct_chg, 2),
                        "max_pct_chg": round(max_pct_chg, 2),
                        "limit_up_count": len(limit_up_symbols),
                        "consecutive_limit_count_max": int(consecutive_max),
                        "total_amount": round(sum(amount for amount in amounts if not math.isnan(amount)), 2),
                        "main_net_inflow": round(stock_flow_total + board_flow_total, 2),
                        "_board_match_score": min(max(source_confidence * 100, len(set(board_names)) * 18), 100),
                        "provider_summary": json.dumps(provider_summary, ensure_ascii=False),
                        "updated_at": now_text(),
                    }
                )

        if not rows:
            return empty_frame(INDUSTRY_NODE_METRICS_COLUMNS)

        max_amount = max([_safe_float(row["total_amount"]) for row in rows] or [0])
        max_flow = max([max(_safe_float(row["main_net_inflow"]), 0.0) for row in rows] or [0])
        for row in rows:
            candidate_count = int(row["candidate_count"])
            avg_pct_chg = _safe_float(row["avg_pct_chg"])
            board_match_score = _safe_float(row.pop("_board_match_score"))
            avg_pct_chg_score = min(max(avg_pct_chg / 10.0 * 100, 0), 100)
            limit_up_score = min(int(row["limit_up_count"]) * 25, 100)
            amount_score = min(_safe_float(row["total_amount"]) / max_amount * 100, 100) if max_amount > 0 else 0.0
            fund_flow_score = min(max(_safe_float(row["main_net_inflow"]), 0.0) / max_flow * 100, 100) if max_flow > 0 else 0.0
            breadth_score = min(candidate_count / 20.0 * 100, 100)
            hot_score = (
                board_match_score * 0.20
                + avg_pct_chg_score * 0.20
                + limit_up_score * 0.25
                + amount_score * 0.15
                + fund_flow_score * 0.10
                + breadth_score * 0.10
            )
            row["hot_score"] = round(min(max(hot_score, 0.0), 100.0), 2)
            row["market_strength"] = _market_strength(row["hot_score"])

        return ensure_columns(pd.DataFrame(rows), INDUSTRY_NODE_METRICS_COLUMNS)

    def _build_graph_cache(self, chains: list[Any], metrics: pd.DataFrame, trade_date: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        metric_map = {
            (str(row.get("chain_id", "")), str(row.get("node_id", ""))): row.to_dict()
            for _, row in metrics.iterrows()
        } if not metrics.empty else {}
        for chain in chains:
            for node in chain.nodes:
                item = metric_map.get((chain.chain_id, node.id), {})
                rows.append(
                    {
                        "trade_date": trade_date,
                        "chain_id": chain.chain_id,
                        "chain_name": chain.name,
                        "node_id": node.id,
                        "node_name": node.name,
                        "layer": node.layer,
                        "node_type": node.type,
                        "hot_score": _safe_float(item.get("hot_score")),
                        "market_strength": str(item.get("market_strength", "很弱")),
                        "candidate_count": int(_safe_float(item.get("candidate_count"))),
                        "limit_up_count": int(_safe_float(item.get("limit_up_count"))),
                        "avg_pct_chg": _safe_float(item.get("avg_pct_chg")),
                        "total_amount": _safe_float(item.get("total_amount")),
                        "provider_summary": str(item.get("provider_summary", "")),
                        "updated_at": now_text(),
                    }
                )
        return ensure_columns(pd.DataFrame(rows), INDUSTRY_GRAPH_CACHE_COLUMNS) if rows else empty_frame(INDUSTRY_GRAPH_CACHE_COLUMNS)

    def _write(self, filename: str, df: pd.DataFrame, columns: list[str]) -> None:
        path = self.output_dir / filename
        frame = ensure_columns(df, columns) if df is not None and not df.empty else empty_frame(columns)
        frame.to_parquet(path, index=False)
        logger.info("Saved %s rows to %s", len(frame), path)

    def _provider_report(self, source_log: pd.DataFrame) -> dict[str, Any]:
        if source_log.empty:
            return {"success": [], "failed": []}
        success_rows = source_log[source_log["success"] == True]
        failed_rows = source_log[source_log["success"] == False]
        return {
            "success": [
                {
                    "method": method,
                    "provider": provider,
                    "rows": int(group["row_count"].max()),
                }
                for (method, provider), group in success_rows.groupby(["method", "provider_used"])
            ],
            "failed": [
                {
                    "method": str(row.get("method", "")),
                    "provider": str(row.get("provider_used", "")),
                    "context": str(row.get("context", "")),
                    "error": str(row.get("error_message", "")),
                }
                for _, row in failed_rows.iterrows()
            ],
        }

    def _top_nodes_by_chain(self, metrics: pd.DataFrame, chains: list[Any]) -> list[dict[str, Any]]:
        if metrics.empty:
            return []
        node_name_map = {(chain.chain_id, node.id): node.name for chain in chains for node in chain.nodes}
        rows = []
        for chain_id, group in metrics.groupby("chain_id"):
            top = group.sort_values("hot_score", ascending=False).head(1)
            if top.empty:
                continue
            row = top.iloc[0]
            rows.append(
                {
                    "chain_id": str(chain_id),
                    "node_id": str(row.get("node_id", "")),
                    "node_name": node_name_map.get((str(chain_id), str(row.get("node_id", ""))), ""),
                    "hot_score": _safe_float(row.get("hot_score")),
                    "market_strength": str(row.get("market_strength", "")),
                }
            )
        return rows


def _node_keywords(node: Any) -> list[str]:
    values = [node.name, getattr(node, "id", "")]
    values.extend(getattr(node, "aliases", []) or [])
    values.extend(getattr(node, "keywords", []) or [])
    return [value for value in dict.fromkeys(str(item).strip() for item in values) if value]


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value).lower())


def _keyword_matches(keyword: str, text: str) -> bool:
    if not keyword or len(keyword) < 2:
        return False
    return keyword in text or text in keyword


def _split_keywords(series: pd.Series) -> list[str]:
    values: list[str] = []
    for item in series.dropna().astype(str):
        for part in re.split(r"[;,，、\s]+", item):
            part = part.strip()
            if part:
                values.append(part)
    return sorted(set(values))


def _df_by_symbol(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if df.empty or "symbol" not in df.columns:
        return {}
    result = {}
    for _, row in df.dropna(subset=["symbol"]).iterrows():
        result[str(row.get("symbol", ""))] = row.to_dict()
    return result


def _first_non_empty(series: pd.Series) -> str:
    for value in series.dropna().astype(str):
        if value:
            return value
    return ""


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        number = float(value)
        if math.isnan(number):
            return 0.0
        return number
    except (TypeError, ValueError):
        return 0.0


def _profile_hits_keywords(stock_name: str, profile: dict[str, Any], keywords: list[str]) -> bool:
    haystack = _normalize_match_text(
        " ".join(
            [
                stock_name,
                str(profile.get("stock_name", "")),
                str(profile.get("industry", "")),
                str(profile.get("business_scope", "")),
                str(profile.get("main_business", "")),
            ]
        )
    )
    return any(_normalize_match_text(keyword) in haystack for keyword in keywords if keyword)


def _provider_counts(series: pd.Series) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in series.dropna().astype(str):
        for provider in [part.strip() for part in item.split(";") if part.strip()]:
            counts[provider] = counts.get(provider, 0) + 1
    return counts


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
