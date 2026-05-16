"""Market data providers for AQUATRADE IndustryChainRadar."""

from __future__ import annotations

from server.data_providers.akshare_provider import AkshareProvider
from server.data_providers.baostock_provider import BaostockProvider
from server.data_providers.base import BaseMarketDataProvider
from server.data_providers.efinance_provider import EfinanceProvider
from server.data_providers.manual_provider import ManualProvider
from server.data_providers.provider_registry import ProviderRegistry
from server.data_providers.tushare_provider import TushareProvider

__all__ = [
    "AkshareProvider",
    "BaostockProvider",
    "BaseMarketDataProvider",
    "EfinanceProvider",
    "ManualProvider",
    "ProviderRegistry",
    "TushareProvider",
    "get_available_providers",
]


def get_available_providers() -> list[BaseMarketDataProvider]:
    return [
        ManualProvider(),
        EfinanceProvider(),
        AkshareProvider(),
        TushareProvider(),
        BaostockProvider(),
    ]
