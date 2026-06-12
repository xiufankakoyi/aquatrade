import polars as pl


class _FakeReader:
    def __init__(self):
        self.calls = []

    def read_table(self, table_name, symbols, start_date, end_date, fields=None):
        self.calls.append((table_name, symbols, start_date, end_date, fields))
        return pl.DataFrame(
            {
                "trade_date": [
                    "2026-06-10",
                    "2026-06-09",
                    "2026-06-10",
                ]
            }
        )


def test_lancedb_trading_dates_use_primary_store(monkeypatch):
    from data_svc.storage import lancedb_reader
    from data_svc.database.optimized_data_query import OptimizedStockDataQuery

    reader = _FakeReader()
    monkeypatch.setenv("DB_BACKEND", "lancedb")
    monkeypatch.setattr(lancedb_reader, "get_lancedb_reader", lambda: reader)

    query = OptimizedStockDataQuery(warmup=False)
    query._warmup_done = True
    query._preload_dates_done = True

    dates = query.get_trading_dates("2026-06-01", "2026-06-12")

    assert dates == ["2026-06-09", "2026-06-10"]
    assert reader.calls == [
        (
            "daily_ohlcv",
            None,
            "2026-06-01",
            "2026-06-12",
            ["trade_date"],
        )
    ]
