from pathlib import Path

from server.news_lab.news_dedup import dedup_news
from server.news_lab.news_entity_matcher import match_related_concepts
from server.news_lab.news_ingest import LocalNewsStore


def test_news_keyword_matches_concepts():
    concepts = match_related_concepts({"title": "CPO 与硅光技术路线受到关注", "summary": ""})
    assert "cpo" in concepts
    assert "silicon_photonics" in concepts


def test_news_dedup_by_title_source_and_date():
    rows = [
        {"title": "  CPO 进展 ", "source": "sample", "publish_time": "2024-01-02 09:00:00"},
        {"title": "CPO进展", "source": "sample", "publish_time": "2024-01-02 12:00:00"},
    ]
    assert len(dedup_news(rows)) == 1


def test_local_news_import_and_query(tmp_path: Path):
    store = LocalNewsStore(db_path=tmp_path / "news.db")
    summary = store.import_local_file("data/sample_news.csv")
    rows = store.query_recent()

    assert summary["rows_read"] == 1
    assert summary["rows_imported"] == 1
    assert len(rows) == 1
    assert "cpo" in rows[0]["related_concepts"]
