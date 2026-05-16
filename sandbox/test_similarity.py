"""
K线形态相似度匹配模块 - 端到端验证脚本

验证核心算法模块的完整流水线：
归一化 -> 相关系数粗筛 -> DTW精细匹配 -> 模式增强 -> 结果输出
"""

import sys
import numpy as np

sys.path.insert(0, ".")

from core.similarity.normalizer import normalize_kline
from core.similarity.correlation_filter import correlation_filter
from core.similarity.dtw_matcher import dtw_match, _dtw_distance
from core.similarity.pattern_enhancer import PatternEnhancer
from core.similarity.window_generator import generate_sliding_windows
from core.similarity import SimilarityEngine


def test_normalize():
    """测试Z-Score归一化"""
    prices = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
    result = normalize_kline(prices)

    assert len(result) == 5, f"Expected length 5, got {len(result)}"
    assert abs(np.mean(result)) < 1e-10, f"Mean should be ~0, got {np.mean(result)}"
    assert abs(np.std(result) - 1.0) < 1e-10, f"Std should be ~1, got {np.std(result)}"

    empty = normalize_kline(np.array([]))
    assert len(empty) == 0, "Empty input should return empty array"

    constant = normalize_kline(np.array([5.0, 5.0, 5.0]))
    assert np.all(constant == 0), "Constant input should return all zeros"

    print("[PASS] normalize_kline")


def test_correlation_filter():
    """测试皮尔逊相关系数粗筛"""
    template = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    template_norm = normalize_kline(template)

    high_corr = {"normalized": normalize_kline(np.array([2.0, 4.0, 6.0, 8.0, 10.0])), "metadata": {"id": "high"}}
    low_corr = {"normalized": normalize_kline(np.array([5.0, 4.0, 3.0, 2.0, 1.0])), "metadata": {"id": "low"}}
    med_corr = {"normalized": normalize_kline(np.array([1.0, 2.5, 3.0, 4.5, 5.0])), "metadata": {"id": "med"}}

    result = correlation_filter(template_norm, [high_corr, low_corr, med_corr], threshold=0.85)

    assert len(result) >= 1, "At least high_corr should pass"
    passed_ids = [r["metadata"]["id"] for r in result]
    assert "high" in passed_ids, "high_corr (corr=1.0) should pass"
    assert "low" not in passed_ids, "low_corr (inverse) should be filtered"

    for r in result:
        assert "corr_score" in r, "Result should contain corr_score"
        assert r["corr_score"] >= 0.85, f"corr_score {r['corr_score']} should be >= 0.85"

    print("[PASS] correlation_filter")


def test_dtw_match():
    """测试DTW精细匹配"""
    template = normalize_kline(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))

    identical = {"normalized": normalize_kline(np.array([1.0, 2.0, 3.0, 4.0, 5.0])), "metadata": {"id": "identical"}}
    similar = {"normalized": normalize_kline(np.array([1.0, 2.1, 3.0, 4.1, 5.0])), "metadata": {"id": "similar"}}
    different = {"normalized": normalize_kline(np.array([5.0, 4.0, 3.0, 2.0, 1.0])), "metadata": {"id": "different"}}

    result = dtw_match(template, [identical, similar, different], top_n=3)

    assert len(result) == 3, f"Expected 3 results, got {len(result)}"
    assert result[0]["metadata"]["id"] == "identical", "Identical should rank first"
    assert result[0]["similarity_score"] > result[1]["similarity_score"], "Identical should have higher score"
    assert result[1]["similarity_score"] > result[2]["similarity_score"], "Similar should rank above different"

    for r in result:
        assert 0 <= r["similarity_score"] <= 1, f"Score {r['similarity_score']} should be in [0, 1]"

    print("[PASS] dtw_match")


def test_dtw_fallback():
    """测试DTW回退实现"""
    s1 = np.array([1.0, 2.0, 3.0])
    s2 = np.array([1.0, 2.0, 3.0])
    dist = _dtw_distance(s1, s2)
    assert dist >= 0, "DTW distance should be non-negative"
    assert dist < 0.01, f"Identical sequences should have near-zero distance, got {dist}"

    s3 = np.array([3.0, 2.0, 1.0])
    dist2 = _dtw_distance(s1, s3)
    assert dist2 > dist, "Different sequences should have larger distance"

    print("[PASS] _dtw_distance fallback")


def test_pattern_enhancer_breakout_volume():
    """测试5进6爆量模式增强"""
    template_close = np.array([10.0, 10.5, 11.0, 11.5, 12.0, 13.0, 14.0, 15.0])
    template_volume = np.array([100.0, 110.0, 120.0, 130.0, 140.0, 500.0, 600.0, 700.0])

    results = [
        {
            "similarity_score": 0.9,
            "close": np.array([20.0, 21.0, 22.0, 23.0, 24.0, 26.0, 28.0, 30.0]),
            "volume": np.array([200.0, 210.0, 220.0, 230.0, 240.0, 800.0, 900.0, 1000.0]),
            "metadata": {"id": "vol_match"},
        },
        {
            "similarity_score": 0.85,
            "close": np.array([20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0]),
            "volume": np.array([200.0, 210.0, 220.0, 230.0, 240.0, 250.0, 260.0, 270.0]),
            "metadata": {"id": "no_vol"},
        },
    ]

    enhancer = PatternEnhancer(pattern_type="breakout_volume")
    enhanced = enhancer.enhance(results, {"close": template_close, "volume": template_volume})

    assert len(enhanced) == 2, f"Expected 2 results, got {len(enhanced)}"
    assert "enhanced_score" in enhanced[0], "Result should contain enhanced_score"
    assert "volume_ratio" in enhanced[0], "Result should contain volume_ratio"

    print("[PASS] PatternEnhancer breakout_volume")


def test_pattern_enhancer_limit_break():
    """测试断板推新模式增强"""
    template_close = np.array([10.0, 11.0, 12.1, 13.3, 13.0, 14.0])
    results = [
        {
            "similarity_score": 0.85,
            "close": np.array([20.0, 22.0, 24.2, 26.6, 26.0, 28.0]),
            "metadata": {"id": "limit_match"},
        },
    ]

    enhancer = PatternEnhancer(pattern_type="limit_break")
    enhanced = enhancer.enhance(results, {"close": template_close})

    assert len(enhanced) == 1
    assert "enhanced_score" in enhanced[0]
    assert "label_match" in enhanced[0]

    print("[PASS] PatternEnhancer limit_break")


def test_pattern_enhancer_n_shape():
    """测试N字走势模式增强"""
    template_close = np.array([10.0, 12.0, 11.0, 13.0, 15.0])
    results = [
        {
            "similarity_score": 0.9,
            "close": np.array([20.0, 24.0, 22.0, 26.0, 30.0]),
            "metadata": {"id": "n_shape"},
        },
    ]

    enhancer = PatternEnhancer(pattern_type="n_shape")
    enhanced = enhancer.enhance(results, {"close": template_close})

    assert len(enhanced) == 1
    assert "enhanced_score" in enhanced[0]
    assert "curvature_score" in enhanced[0]

    print("[PASS] PatternEnhancer n_shape")


def test_similarity_engine():
    """测试SimilarityEngine完整流水线"""
    template = normalize_kline(np.array([10.0, 11.0, 12.0, 13.0, 14.0]))

    candidates = []
    for i in range(20):
        offset = np.random.randn(5) * 0.5
        base = np.array([10.0, 11.0, 12.0, 13.0, 14.0]) + offset
        candidates.append({
            "normalized": normalize_kline(base),
            "metadata": {
                "stock_code": f"TEST{i:03d}",
                "start_date": f"2024-01-{i+1:02d}",
                "end_date": f"2024-01-{i+5:02d}",
            },
        })

    engine = SimilarityEngine(corr_threshold=0.5)
    results = engine.match(template, candidates, top_n=5)

    assert len(results) <= 5, f"Expected at most 5 results, got {len(results)}"
    for r in results:
        assert "similarity_score" in r, "Result should contain similarity_score"
        assert "stock_code" in r, "Result should contain stock_code"
        assert 0 <= r["similarity_score"] <= 1, f"Score should be in [0, 1], got {r['similarity_score']}"

    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i]["similarity_score"] >= results[i + 1]["similarity_score"], \
                "Results should be sorted by similarity_score descending"

    print("[PASS] SimilarityEngine")


def test_window_generator():
    """测试滑动窗口生成"""
    import polars as pl

    dates = [f"2024-01-{d:02d}" for d in range(1, 26)]
    df = pl.DataFrame({
        "stock_code": ["TEST001"] * 25,
        "trade_date": dates,
        "close": np.linspace(10.0, 20.0, 25).tolist(),
        "volume": np.linspace(100.0, 200.0, 25).tolist(),
    })

    windows = generate_sliding_windows(df, window_size=5)

    expected_count = 25 - 5 + 1
    assert len(windows) == expected_count, f"Expected {expected_count} windows, got {len(windows)}"

    for w in windows:
        assert "normalized" in w, "Window should contain normalized"
        assert "close" in w, "Window should contain close"
        assert "volume" in w, "Window should contain volume"
        assert "metadata" in w, "Window should contain metadata"
        assert len(w["normalized"]) == 5, f"Window length should be 5, got {len(w['normalized'])}"
        assert "stock_code" in w["metadata"]
        assert "start_date" in w["metadata"]
        assert "end_date" in w["metadata"]

    print("[PASS] generate_sliding_windows")


if __name__ == "__main__":
    print("=" * 60)
    print("K线形态相似度匹配模块 - 端到端验证")
    print("=" * 60)

    tests = [
        test_normalize,
        test_correlation_filter,
        test_dtw_match,
        test_dtw_fallback,
        test_pattern_enhancer_breakout_volume,
        test_pattern_enhancer_limit_break,
        test_pattern_enhancer_n_shape,
        test_similarity_engine,
        test_window_generator,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
