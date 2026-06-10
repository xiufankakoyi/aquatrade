from __future__ import annotations

import importlib

import pandas as pd


def _reload_config(monkeypatch, backend: str, fallback: str | None = None):
    monkeypatch.setenv("DB_BACKEND", backend)
    if fallback is None:
        monkeypatch.delenv("ENABLE_PARQUET_FALLBACK", raising=False)
    else:
        monkeypatch.setenv("ENABLE_PARQUET_FALLBACK", fallback)

    import config.setting as setting_module
    import config.config as config_module

    importlib.reload(setting_module)
    importlib.reload(config_module)
    return config_module.Config


def test_lancedb_mode_disables_parquet_fallback_by_default(monkeypatch):
    config = _reload_config(monkeypatch, "lancedb")

    assert config.parquet_fallback_enabled() is False


def test_lancedb_mode_can_enable_legacy_parquet_fallback(monkeypatch):
    config = _reload_config(monkeypatch, "lancedb", "true")

    assert config.parquet_fallback_enabled() is True


def test_parquet_backend_keeps_legacy_parquet_reads_available(monkeypatch):
    config = _reload_config(monkeypatch, "parquet")

    assert config.parquet_fallback_enabled() is True


def test_provider_registry_skips_local_parquet_when_fallback_disabled(monkeypatch):
    from server.data_providers import provider_registry

    captured_orders = []

    def fake_failover(self, method_name, provider_order, columns, **kwargs):
        captured_orders.append(provider_order)
        return pd.DataFrame()

    monkeypatch.setattr(provider_registry.Config, "parquet_fallback_enabled", lambda: False)
    monkeypatch.setattr(provider_registry.ProviderRegistry, "_failover", fake_failover)

    registry = provider_registry.ProviderRegistry()
    registry.get_daily_bars("2026-01-01", "2026-01-02")
    registry.get_stock_basic_info()

    assert captured_orders[0] == ["tushare", "efinance", "akshare", "baostock"]
    assert captured_orders[1] == ["tushare", "akshare", "efinance", "baostock"]


def test_provider_registry_uses_local_parquet_when_fallback_enabled(monkeypatch):
    from server.data_providers import provider_registry

    captured_orders = []

    def fake_failover(self, method_name, provider_order, columns, **kwargs):
        captured_orders.append(provider_order)
        return pd.DataFrame()

    monkeypatch.setattr(provider_registry.Config, "parquet_fallback_enabled", lambda: True)
    monkeypatch.setattr(provider_registry.ProviderRegistry, "_failover", fake_failover)

    registry = provider_registry.ProviderRegistry()
    registry.get_daily_bars("2026-01-01", "2026-01-02")
    registry.get_stock_basic_info()

    assert captured_orders[0][0] == "local_parquet"
    assert captured_orders[1][0] == "local_stock_info"
