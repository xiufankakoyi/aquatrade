from pathlib import Path
from uuid import uuid4

import polars as pl

from data_svc.storage.memory_map_service import MemoryMapService


def _cache_dir() -> Path:
    path = Path("cache") / "test_memory_map_service"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_memory_map_roundtrip_with_projection_and_filter():
    table_name = f"daily_ohlcv_{uuid4().hex}"
    service = MemoryMapService(cache_dir=str(_cache_dir()))
    df = pl.DataFrame(
        {
            "stock_code": ["000002.SZ", "000001.SZ", "000001.SZ"],
            "trade_date": ["2024-01-02", "2024-01-01", "2024-01-02"],
            "close": [20.0, 10.0, 11.0],
            "volume": [200, 100, 110],
        }
    )

    assert service.write_mmap(df, table_name) is True

    result = service.read_mmap(
        table_name,
        columns=["stock_code", "trade_date", "close"],
        filters={"stock_code": "000001.SZ"},
    )

    assert result is not None
    assert result.columns == ["stock_code", "trade_date", "close"]
    assert result["stock_code"].to_list() == ["000001.SZ", "000001.SZ"]
    assert result["close"].to_list() == [10.0, 11.0]
    assert (_cache_dir() / f"{table_name}.arrow").exists()
    service.delete(table_name)


def test_memory_map_projection_only_reads_selected_columns():
    table_name = f"daily_ohlcv_{uuid4().hex}"
    service = MemoryMapService(cache_dir=str(_cache_dir()))
    df = pl.DataFrame(
        {
            "stock_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["2024-01-01", "2024-01-01"],
            "close": [10.0, 20.0],
        }
    )
    assert service.write_mmap(df, table_name) is True

    result = service.read_mmap(table_name, columns=["close"], filters=None)

    assert result is not None
    assert result.columns == ["close"]
    service.delete(table_name)
