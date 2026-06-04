"""Background scheduler for IndustryChainRadar data auto updates."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from server.data_providers.base import normalize_trade_date
from server.industry_chain.loader import project_root

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _dt_text(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


class IndustryAutoUpdateScheduler:
    """Run IndustryDataSync automatically without requiring a daily manual CLI."""

    def __init__(self) -> None:
        self.enabled = _env_bool("INDUSTRY_AUTO_UPDATE_ENABLED", True)
        self.run_on_startup = _env_bool("INDUSTRY_AUTO_UPDATE_ON_STARTUP", True)
        self.skip_weekends = _env_bool("INDUSTRY_AUTO_UPDATE_SKIP_WEEKENDS", True)
        self.hour = _env_int("INDUSTRY_AUTO_UPDATE_HOUR", 16, 0, 23)
        self.minute = _env_int("INDUSTRY_AUTO_UPDATE_MINUTE", 30, 0, 59)
        self.startup_delay_seconds = _env_int("INDUSTRY_AUTO_UPDATE_STARTUP_DELAY_SECONDS", 15, 0, 3600)
        self.chain_id = os.getenv("INDUSTRY_AUTO_UPDATE_CHAIN", "").strip() or None
        self.output_dir = Path(
            os.getenv("INDUSTRY_AUTO_UPDATE_OUTPUT_DIR", str(project_root() / "data" / "industry"))
        )

        self._lock = threading.Lock()
        self._started = False
        self._running = False
        self._timer: threading.Timer | None = None
        self._startup_timer: threading.Timer | None = None
        self._next_run_at: datetime | None = None
        self._last_run_at: datetime | None = None
        self._last_finished_at: datetime | None = None
        self._last_status = "idle"
        self._last_error = ""
        self._last_summary: dict[str, Any] | None = None

    def start(self) -> None:
        """Start the background scheduler once per process."""
        with self._lock:
            if self._started:
                return
            self._started = True

            if not self.enabled:
                self._last_status = "disabled"
                logger.info("IndustryChainRadar auto update scheduler is disabled")
                return

            self._schedule_next_locked(datetime.now())

            if self.run_on_startup:
                self._startup_timer = threading.Timer(
                    self.startup_delay_seconds,
                    lambda: self.run_once(reason="startup", force=False),
                )
                self._startup_timer.daemon = True
                self._startup_timer.start()

        logger.info("IndustryChainRadar auto update scheduler started: %s", self.status())

    def stop(self) -> None:
        with self._lock:
            self._started = False
            for timer in (self._timer, self._startup_timer):
                if timer:
                    timer.cancel()
            self._timer = None
            self._startup_timer = None
            self._next_run_at = None
            if not self._running:
                self._last_status = "stopped"

    def run_once(self, reason: str = "manual", trade_date: str | None = None, force: bool = True) -> bool:
        """Queue one sync run in the background.

        Returns False when a run is already active or the scheduler is disabled.
        """
        if not self.enabled:
            with self._lock:
                self._last_status = "disabled"
            return False

        normalized_trade_date = normalize_trade_date(trade_date) if trade_date else self._default_trade_date()
        with self._lock:
            if self._running:
                self._last_status = "skipped_running"
                return False
            self._running = True
            self._last_status = "running"
            self._last_error = ""
            self._last_run_at = datetime.now()

        thread = threading.Thread(
            target=self._execute_sync,
            kwargs={"reason": reason, "trade_date": normalized_trade_date, "force": force},
            name="industry-chain-auto-update",
            daemon=True,
        )
        thread.start()
        return True

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "started": self._started,
                "running": self._running,
                "run_on_startup": self.run_on_startup,
                "startup_delay_seconds": self.startup_delay_seconds,
                "schedule": {
                    "hour": self.hour,
                    "minute": self.minute,
                    "timezone": "local",
                    "skip_weekends": self.skip_weekends,
                },
                "chain_id": self.chain_id or "all",
                "output_dir": str(self.output_dir),
                "next_run_at": _dt_text(self._next_run_at),
                "last_run_at": _dt_text(self._last_run_at),
                "last_finished_at": _dt_text(self._last_finished_at),
                "last_status": self._last_status,
                "last_error": self._last_error,
                "last_summary": self._last_summary,
                "default_trade_date": self._default_trade_date(),
            }

    def _execute_sync(self, reason: str, trade_date: str, force: bool) -> None:
        try:
            if not force and self._has_current_data(trade_date):
                with self._lock:
                    self._last_status = "skipped_current"
                    self._last_summary = {"trade_date": trade_date, "reason": reason}
                logger.info("IndustryChainRadar auto update skipped; data is current for %s", trade_date)
                return

            from server.data_sync.sync_industry_data import IndustryDataSync

            logger.info(
                "Running IndustryChainRadar auto update: reason=%s chain=%s trade_date=%s",
                reason,
                self.chain_id or "all",
                trade_date,
            )
            summary = IndustryDataSync(output_dir=self.output_dir).sync_all(
                chain_id=self.chain_id,
                trade_date=trade_date,
            )
            with self._lock:
                self._last_status = str(summary.get("status", "success"))
                self._last_summary = summary
                self._last_error = ""
        except Exception as exc:
            logger.exception("IndustryChainRadar auto update failed")
            with self._lock:
                self._last_status = "failed"
                self._last_error = str(exc)
                self._last_summary = {"trade_date": trade_date, "reason": reason}
        finally:
            with self._lock:
                self._running = False
                self._last_finished_at = datetime.now()

    def _schedule_next_locked(self, now: datetime) -> None:
        next_run = self._next_run_time(now)
        wait_seconds = max(1.0, (next_run - now).total_seconds())
        self._next_run_at = next_run

        def _scheduled_callback() -> None:
            self.run_once(reason="scheduled", force=True)
            with self._lock:
                if self._started and self.enabled:
                    self._schedule_next_locked(datetime.now())

        self._timer = threading.Timer(wait_seconds, _scheduled_callback)
        self._timer.daemon = True
        self._timer.start()

    def _next_run_time(self, now: datetime) -> datetime:
        target = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        if self.skip_weekends:
            while target.weekday() >= 5:
                target += timedelta(days=1)
        return target

    def _default_trade_date(self, now: datetime | None = None) -> str:
        value = now or datetime.now()
        if self.skip_weekends:
            while value.weekday() >= 5:
                value -= timedelta(days=1)
        return value.strftime("%Y-%m-%d")

    def _has_current_data(self, trade_date: str) -> bool:
        metrics_path = self.output_dir / "industry_node_metrics.parquet"
        candidates_path = self.output_dir / "industry_node_candidates.parquet"
        market_path = self.output_dir / "market_snapshot.parquet"
        if not metrics_path.exists() or not candidates_path.exists() or not market_path.exists():
            return False

        wanted = trade_date.replace("-", "")
        try:
            frame = pd.read_parquet(metrics_path, columns=["trade_date"])
            candidate_frame = pd.read_parquet(candidates_path, columns=["trade_date"])
            market_frame = pd.read_parquet(market_path, columns=["trade_date"])
            metric_dates = {str(value).replace("-", "") for value in frame["trade_date"].dropna().unique()}
            candidate_dates = {str(value).replace("-", "") for value in candidate_frame["trade_date"].dropna().unique()}
            market_dates = {str(value).replace("-", "") for value in market_frame["trade_date"].dropna().unique()}
            return (
                wanted in metric_dates
                and wanted in candidate_dates
                and wanted in market_dates
                and not candidate_frame.empty
                and not market_frame.empty
            )
        except Exception:
            return (
                datetime.fromtimestamp(metrics_path.stat().st_mtime).strftime("%Y%m%d") == wanted
                and candidates_path.stat().st_size > 6000
                and market_path.stat().st_size > 6000
            )


_scheduler: IndustryAutoUpdateScheduler | None = None


def get_industry_auto_update_scheduler() -> IndustryAutoUpdateScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = IndustryAutoUpdateScheduler()
    return _scheduler
