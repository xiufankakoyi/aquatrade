from server.concept_lab.concept_loader import ConceptLoader
from server.concept_lab.concept_score_engine import calculate_concept_score, score_stock_mappings


def test_concepts_load_and_search_alias():
    loader = ConceptLoader()
    concepts = loader.load_concepts()
    assert len(concepts) >= 13

    results = loader.search_concepts("InP")
    assert any(item["concept_id"] == "indium_phosphide" for item in results)


def test_empty_mapping_is_supported():
    loader = ConceptLoader()
    rows = [row for row in loader.load_mapping() if row.get("concept_id") == "indium_phosphide"]
    assert rows == []
    assert score_stock_mappings(rows) == []


def test_concept_score_rule():
    score = calculate_concept_score(
        {
            "relevance_score": 0.8,
            "purity_score": 0.6,
            "evidence_type": "annual_report",
        },
        market_confirm_score=0.5,
    )
    assert score == 0.735
