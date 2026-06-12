import pandas as pd
import polars as pl


class _FakeLanceDBReader:
    def __init__(self):
        self.calls = []

    def read_table(self, table_name, symbol, start_date, end_date, fields=None):
        self.calls.append((table_name, symbol, start_date, end_date, fields))
        return pl.DataFrame(
            {
                "trade_date": [pd.Timestamp("2026-06-10")],
                "close": [3500.0],
            }
        )


def test_benchmark_accepts_exchange_suffix(monkeypatch):
    from data_svc.storage import lancedb_reader
    from server.visualization_api import BacktestVisualizationAPI

    reader = _FakeLanceDBReader()
    monkeypatch.setattr(lancedb_reader, "get_lancedb_reader", lambda: reader)

    api = BacktestVisualizationAPI.__new__(BacktestVisualizationAPI)
    result = api._get_benchmark_data_from_db(
        "000300.SH",
        "2026-06-01",
        "2026-06-12",
    )

    assert reader.calls == [
        (
            "index_daily",
            "000300.SH",
            "2026-06-01",
            "2026-06-12",
            ["trade_date", "close"],
        )
    ]
    assert result.to_dict("records") == [
        {"date": "2026-06-10", "close": 3500.0}
    ]


def test_benchmark_accepts_plain_code(monkeypatch):
    from data_svc.storage import lancedb_reader
    from server.visualization_api import BacktestVisualizationAPI

    reader = _FakeLanceDBReader()
    monkeypatch.setattr(lancedb_reader, "get_lancedb_reader", lambda: reader)

    api = BacktestVisualizationAPI.__new__(BacktestVisualizationAPI)
    api._get_benchmark_data_from_db("000905", "2026-06-01", "2026-06-12")

    assert reader.calls[0][1] == "000905.SH"
