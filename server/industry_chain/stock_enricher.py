"""
StockEnricher

合并多源数据，输出给前端的 stock rows。

数据源:
1. concept_stock_mapping.csv (本地正宗映射)
2. manual_concept_members.csv (手工维护)
3. Tushare/AKShare concept_members (外部候选)
4. company_evidence.csv (本地证据)
5. stock_market_snapshot (行情确认)

规则:
- 本地 concept_stock_mapping 和 company_evidence 标记为 verified
- Tushare/AKShare/东方财富来源标记为 candidate
- candidate 不得显示为"正宗"，只能显示为"外部候选"
- final_score 对 candidate 默认较低，除非有 evidence
- 如果没有行情数据，行情字段显示 null
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from server.data_sync.normalizer import normalize_symbols
from server.industry_chain.loader import MappingLoader, project_root

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = project_root() / "data" / "industry"
DEFAULT_KNOWLEDGE_DIR = project_root() / "knowledge"


class StockEnricher:
    """个股数据富化器。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        knowledge_dir: Path | None = None,
    ) -> None:
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.knowledge_dir = knowledge_dir or DEFAULT_KNOWLEDGE_DIR
        self.mapping_loader = MappingLoader(mapping_path=self.knowledge_dir / "stock_concept_mapping.csv")

    def get_node_stocks(
        self,
        chain_id: str,
        node_id: str,
        include_candidates: bool = True,
        verified_only: bool = False,
        sort_by: str = "final_score",
    ) -> list[dict[str, Any]]:
        """
        获取 enriched 后的节点个股列表。

        Args:
            chain_id: 产业链 ID
            node_id: 节点 ID
            include_candidates: 是否包含外部候选
            verified_only: 是否只看已验证
            sort_by: 排序字段 (final_score/hot_score/pct_chg/amount)

        Returns:
            enriched stock rows 列表
        """
        rows: list[dict[str, Any]] = []
        symbol_map: dict[str, dict[str, Any]] = {}

        # 1. 加载本地 mapping (verified)
        try:
            local_mappings = self.mapping_loader.load_mappings(chain_id=chain_id, node_id=node_id)
            for m in local_mappings:
                sym = m.symbol
                if not sym:
                    continue
                symbol_map[sym] = {
                    "symbol": sym,
                    "stock_name": m.stock_name,
                    "chain_id": chain_id,
                    "node_id": node_id,
                    "source": "local_mapping",
                    "source_concept_name": "",
                    "is_verified": True,
                    "is_candidate": False,
                    "relevance_score": m.relevance_score,
                    "purity_score": m.purity_score,
                    "evidence_score": m.evidence_score,
                    "market_confirm_score": m.market_confirm_score,
                    "final_score": m.final_score,
                    "evidence_type": m.evidence_type,
                    "evidence_text": m.evidence_text,
                    "evidence_source": m.evidence_source,
                    "updated_at": m.updated_at,
                    "pct_chg": None,
                    "return_5d": None,
                    "amount": None,
                    "amount_change_ratio": None,
                    "limit_status": None,
                    "pattern_signal": None,
                }
        except Exception as exc:
            logger.warning(f"加载本地 mapping 失败: {exc}")

        # 2. 加载 manual_concept_members (verified)
        manual_df = self._load_manual_concept_members()
        if not manual_df.empty:
            try:
                filtered = manual_df[
                    (manual_df.get("chain_id") == chain_id) &
                    (manual_df.get("node_id") == node_id)
                ]
                for _, row in filtered.iterrows():
                    sym = str(row.get("symbol", ""))
                    if not sym:
                        continue
                    if sym in symbol_map:
                        # 合并更新
                        symbol_map[sym]["source"] = "manual"
                        symbol_map[sym]["source_concept_name"] = str(row.get("source_concept_name", ""))
                        symbol_map[sym]["is_verified"] = True
                        symbol_map[sym]["is_candidate"] = False
                        if row.get("updated_at"):
                            symbol_map[sym]["updated_at"] = str(row["updated_at"])
                    else:
                        symbol_map[sym] = {
                            "symbol": sym,
                            "stock_name": str(row.get("stock_name", "")),
                            "chain_id": chain_id,
                            "node_id": node_id,
                            "source": "manual",
                            "source_concept_name": str(row.get("source_concept_name", "")),
                            "is_verified": True,
                            "is_candidate": False,
                            "relevance_score": 0.0,
                            "purity_score": 0.0,
                            "evidence_score": 0.0,
                            "market_confirm_score": 0.0,
                            "final_score": 0.3,
                            "evidence_type": "",
                            "evidence_text": str(row.get("notes", "")),
                            "evidence_source": str(row.get("source", "")),
                            "updated_at": str(row.get("updated_at", "")),
                            "pct_chg": None,
                            "return_5d": None,
                            "amount": None,
                            "amount_change_ratio": None,
                            "limit_status": None,
                            "pattern_signal": None,
                        }
            except Exception as exc:
                logger.warning(f"加载 manual_concept_members 失败: {exc}")

        # 3. 加载外部候选 (candidate)
        concept_df = self._load_concept_members()
        if not concept_df.empty and include_candidates:
            try:
                filtered = concept_df[
                    (concept_df.get("chain_id") == chain_id) &
                    (concept_df.get("node_id") == node_id)
                ]
                for _, row in filtered.iterrows():
                    sym = str(row.get("symbol", ""))
                    if not sym:
                        continue
                    if sym in symbol_map:
                        # 已有本地证据，不覆盖 verified 状态，但可补充来源
                        continue
                    symbol_map[sym] = {
                        "symbol": sym,
                        "stock_name": str(row.get("stock_name", "")),
                        "chain_id": chain_id,
                        "node_id": node_id,
                        "source": str(row.get("source", "external")),
                        "source_concept_name": str(row.get("source_concept_name", "")),
                        "is_verified": False,
                        "is_candidate": True,
                        "relevance_score": 0.0,
                        "purity_score": 0.0,
                        "evidence_score": 0.0,
                        "market_confirm_score": 0.0,
                        "final_score": 0.1,
                        "evidence_type": "",
                        "evidence_text": "",
                        "evidence_source": str(row.get("source", "")),
                        "updated_at": str(row.get("updated_at", "")),
                        "pct_chg": None,
                        "return_5d": None,
                        "amount": None,
                        "amount_change_ratio": None,
                        "limit_status": None,
                        "pattern_signal": None,
                    }
            except Exception as exc:
                logger.warning(f"加载外部候选失败: {exc}")

        # 4. 加载证据并合并分数
        evidence_df = self._load_evidence()
        if not evidence_df.empty:
            try:
                ev_filtered = evidence_df[
                    (evidence_df.get("chain_id") == chain_id) &
                    (evidence_df.get("node_id") == node_id)
                ]
                for _, row in ev_filtered.iterrows():
                    sym = str(row.get("symbol", ""))
                    if not sym or sym not in symbol_map:
                        continue
                    item = symbol_map[sym]
                    item["is_verified"] = True
                    item["is_candidate"] = False
                    item["evidence_type"] = str(row.get("evidence_type", ""))
                    item["evidence_text"] = str(row.get("evidence_text", ""))
                    item["evidence_source"] = str(row.get("evidence_source", ""))
                    confidence = pd.to_numeric(row.get("confidence"), errors="coerce")
                    if confidence and confidence > 0:
                        item["evidence_score"] = float(confidence)
                        item["final_score"] = max(item["final_score"], float(confidence))
                    if row.get("updated_at"):
                        item["updated_at"] = str(row["updated_at"])
            except Exception as exc:
                logger.warning(f"合并证据失败: {exc}")

        # 5. 合并行情数据
        market_df = self._load_market_snapshot()
        if not market_df.empty:
            try:
                for sym, item in symbol_map.items():
                    row = market_df[market_df["symbol"] == sym]
                    if row.empty:
                        continue
                    r = row.iloc[0]
                    item["pct_chg"] = float(r["pct_chg"]) if pd.notna(r.get("pct_chg")) else None
                    item["amount"] = float(r["amount"]) if pd.notna(r.get("amount")) else None
                    item["return_5d"] = None
                    item["amount_change_ratio"] = None
                    if item["pct_chg"] is not None and item["pct_chg"] >= 9.5:
                        item["limit_status"] = "涨停"
                    elif item["pct_chg"] is not None and item["pct_chg"] <= -9.5:
                        item["limit_status"] = "跌停"
                    else:
                        item["limit_status"] = None
            except Exception as exc:
                logger.warning(f"合并行情失败: {exc}")

        # 6. 过滤与排序
        rows = list(symbol_map.values())
        if verified_only:
            rows = [r for r in rows if r["is_verified"]]
        if not include_candidates:
            rows = [r for r in rows if not r["is_candidate"]]

        reverse_sort = True
        if sort_by == "final_score":
            rows.sort(key=lambda x: x["final_score"] or 0, reverse=True)
        elif sort_by == "hot_score":
            rows.sort(key=lambda x: x.get("hot_score", 0) or 0, reverse=True)
        elif sort_by == "pct_chg":
            rows.sort(key=lambda x: x["pct_chg"] if x["pct_chg"] is not None else -9999, reverse=True)
        elif sort_by == "amount":
            rows.sort(key=lambda x: x["amount"] if x["amount"] is not None else 0, reverse=True)
        else:
            rows.sort(key=lambda x: x["final_score"] or 0, reverse=True)

        return rows

    def _load_manual_concept_members(self) -> pd.DataFrame:
        """加载手工概念成员。"""
        parquet_path = self.output_dir / "concept_members.parquet"
        csv_path = self.knowledge_dir / "data_sources" / "manual_concept_members.csv"
        try:
            if parquet_path.exists():
                return pd.read_parquet(parquet_path)
            if csv_path.exists():
                return pd.read_csv(csv_path, dtype=str)
        except Exception as exc:
            logger.warning(f"加载 manual_concept_members 失败: {exc}")
        return pd.DataFrame()

    def _load_concept_members(self) -> pd.DataFrame:
        """加载概念成员（含外部候选）。"""
        parquet_path = self.output_dir / "concept_members.parquet"
        try:
            if parquet_path.exists():
                return pd.read_parquet(parquet_path)
        except Exception as exc:
            logger.warning(f"加载 concept_members 失败: {exc}")
        return pd.DataFrame()

    def _load_evidence(self) -> pd.DataFrame:
        """加载证据数据。"""
        parquet_path = self.output_dir / "company_evidence.parquet"
        csv_path = self.knowledge_dir / "data_sources" / "company_evidence.csv"
        try:
            if parquet_path.exists():
                return pd.read_parquet(parquet_path)
            if csv_path.exists():
                return pd.read_csv(csv_path, dtype=str)
        except Exception as exc:
            logger.warning(f"加载 evidence 失败: {exc}")
        return pd.DataFrame()

    def _load_market_snapshot(self) -> pd.DataFrame:
        """加载行情快照。"""
        parquet_path = self.output_dir / "stock_market_snapshot.parquet"
        try:
            if parquet_path.exists():
                return pd.read_parquet(parquet_path)
        except Exception as exc:
            logger.warning(f"加载 market_snapshot 失败: {exc}")
        return pd.DataFrame()
