import pandas as pd
import polars as pl
import pyarrow as pa

from data_svc.unified_data_query import UnifiedDataQuery


class FakeReader:
    def __init__(self):
        self.calls = []

    def read_table(self, table_name, symbols, start_date=None, end_date=None, fields=None, as_of=None):
        self.calls.append((table_name, symbols, start_date, end_date, fields))
        df = pl.DataFrame(
            {
                "stock_code": ["000001.SZ", "000001.SZ"],
                "trade_date": ["2024-01-01", "2024-01-02"],
                "close": [10.0, 11.0],
                "volume": [100, 110],
            }
        )
        return df.select(fields) if fields else df


def test_stock_history_polars_avoids_pandas_materialization():
    query = UnifiedDataQuery(db_path="unused")
    query._reader = FakeReader()

    result = query.get_stock_history_polars(
        "000001.SZ",
        "2024-01-01",
        "2024-01-02",
        columns=["stock_code", "close"],
    )

    assert isinstance(result, pl.DataFrame)
    assert result.columns == ["stock_code", "close"]
    assert query._reader.calls[0] == (
        "daily_ohlcv",
        "000001.SZ",
        "2024-01-01",
        "2024-01-02",
        ["stock_code", "close"],
    )


def test_stock_history_arrow_and_pandas_compatibility():
    query = UnifiedDataQuery(db_path="unused")
    query._reader = FakeReader()

    arrow_result = query.get_stock_history_arrow("000001.SZ", "2024-01-01", "2024-01-02")
    pandas_result = query.get_stock_history("000001.SZ", "2024-01-01", "2024-01-02")

    assert isinstance(arrow_result, pa.Table)
    assert arrow_result.num_rows == 2
    assert isinstance(pandas_result, pd.DataFrame)
    assert list(pandas_result["close"]) == [10.0, 11.0]
