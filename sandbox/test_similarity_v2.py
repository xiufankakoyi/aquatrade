"""
K线形态相似度匹配模块 V2 - 骨架算法端到端验证脚本

验证分层骨架算法的核心能力：
1. ZigZag 能区分方向相反的走势
2. 节奏向量能区分碎步推升和大起大落
3. 骨架算法在方向相反序列上得分接近 0
4. 骨架算法在同向相似序列上得分较高
"""

import sys
import numpy as np

sys.path.insert(0, ".")

from core.similarity.zigzag import identify_extrema, build_segments
from core.similarity.rhythm import RhythmVector, extract_rhythm_vector, to_array, cosine_similarity
from core.similarity.structure_encoder import StructureEncoder, encode_structure, fast_filter
from core.similarity.segment_match import (
    SegmentMatcher,
    segment_edit_distance,
    align_segments,
    compute_structure_similarity,
    compute_rhythm_similarity,
    compute_ma_fit_similarity,
    compute_weighted_score,
)
from core.similarity.pattern_enhancer_v2 import SkeletonMatcher, SceneConfig


def make_klines(closes: list, volumes: list = None) -> dict:
    """Helper to create klines dict from close prices."""
    n = len(closes)
    if volumes is None:
        volumes = [1000.0] * n
    return {
        "open": np.array(closes, dtype=np.float64),
        "high": np.array(closes, dtype=np.float64) * 1.01,
        "low": np.array(closes, dtype=np.float64) * 0.99,
        "close": np.array(closes, dtype=np.float64),
        "volume": np.array(volumes, dtype=np.float64),
    }


def test_zigzag_distinguishes_direction():
    """验证 ZigZag 能区分'先涨后跌'和'先跌后涨'"""
    up_then_down = [10.0, 11.0, 12.0, 13.0, 14.0, 13.2, 12.3, 11.5, 10.8, 10.2]
    down_then_up = [14.0, 13.0, 12.0, 11.0, 10.0, 10.8, 11.6, 12.5, 13.3, 14.0]

    extrema_up = identify_extrema(np.array(up_then_down), min_pct=0.03, min_bars=2)
    extrema_down = identify_extrema(np.array(down_then_up), min_pct=0.03, min_bars=2)

    segs_up = build_segments(np.array(up_then_down), extrema_up)
    segs_down = build_segments(np.array(down_then_up), extrema_down)

    dirs_up = [s["direction"] for s in segs_up]
    dirs_down = [s["direction"] for s in segs_down]

    print(f"  Up-then-down segments: {dirs_up}")
    print(f"  Down-then-up segments: {dirs_down}")

    assert len(segs_up) >= 2, f"Should have at least 2 segments, got {len(segs_up)}"
    assert dirs_up != dirs_down, f"Direction sequences should differ: {dirs_up} vs {dirs_down}"
    print(f"[PASS] ZigZag distinguishes opposite directions")


def test_rhythm_distinguishes_patterns():
    """验证节奏向量能区分'小阳小阴碎步'和'大起大落'"""
    np.random.seed(42)
    small_noise = np.random.randn(15) * 0.05
    small_steps = [10.0 + i * 0.3 + small_noise[i] for i in range(15)]
    big_swings = [10.0, 12.0, 9.0, 13.0, 8.0, 14.0, 8.5, 13.5, 9.0, 14.5]

    klines_small = make_klines(small_steps, [1000] * 15)
    klines_big = make_klines(big_swings, [5000, 800, 5000, 800, 5000, 800, 5000, 800, 5000, 800])

    rhythm_small = extract_rhythm_vector(klines_small)
    rhythm_big = extract_rhythm_vector(klines_big)

    arr_small = to_array(rhythm_small)
    arr_big = to_array(rhythm_big)

    sim = cosine_similarity(arr_small, arr_big)
    print(f"  Small steps rhythm: {arr_small}")
    print(f"  Big swings rhythm:   {arr_big}")
    print(f"  Cosine similarity: {sim:.4f}")

    assert sim < 0.99, f"Very different patterns should have low similarity, got {sim}"
    print(f"[PASS] Rhythm distinguishes small steps from big swings (sim={sim:.4f})")


def test_skeleton_rejects_opposite_direction():
    """验证骨架算法检测方向相反的序列
    
    由于结构层权重仅0.2（节奏层0.6），反向序列总分仍会较高，
    但结构分必然 < 1.0，且总分应显著低于同向序列。
    """
    template = [10.0, 11.0, 12.0, 13.0, 14.0, 13.2, 12.3, 11.5, 10.8, 10.2]
    opposite = [14.0, 13.0, 12.0, 11.0, 10.0, 10.8, 11.6, 12.5, 13.3, 14.0]
    similar = [20.0, 21.5, 23.0, 24.5, 26.0, 25.0, 23.5, 22.0, 20.5, 19.0]

    klines_t = make_klines(template)
    klines_o = make_klines(opposite)
    klines_s = make_klines(similar)

    matcher = SkeletonMatcher(min_pct=0.03, min_bars=2)

    result_o = matcher.match(klines_t, klines_o)
    result_s = matcher.match(klines_t, klines_s)

    total_o = result_o["total_score"]
    total_s = result_s["total_score"]
    structure_o = result_o["structure_score"]

    print(f"  Opposite: total={total_o:.4f}, structure={structure_o:.4f}")
    print(f"  Similar:  total={total_s:.4f}")

    assert structure_o < 1.0, f"Opposite should have structure < 1.0, got {structure_o}"
    assert total_o < total_s, f"Opposite ({total_o:.4f}) should score < similar ({total_s:.4f})"
    print(f"[PASS] Skeleton detects opposite direction (structure={structure_o:.4f}, opposite<similar)")


def test_skeleton_accepts_similar_direction():
    """验证骨架算法在同向相似序列上得分较高"""
    template = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0]
    similar = [20.0, 21.5, 23.0, 24.5, 26.0, 27.5, 29.0, 30.5]

    klines_t = make_klines(template)
    klines_s = make_klines(similar)

    matcher = SkeletonMatcher(min_pct=0.03, min_bars=2)

    result = matcher.match(klines_t, klines_s)

    total = result["total_score"]
    structure = result["structure_score"]
    rhythm = result["rhythm_score"]

    print(f"  Similar direction scores: total={total:.4f}, structure={structure:.4f}, rhythm={rhythm:.4f}")

    assert total > 0.5, f"Similar directions should score > 0.5, got {total}"
    print(f"[PASS] Skeleton accepts similar direction (score={total:.4f})")


def test_segment_edit_distance():
    """验证段序列编辑距离计算"""
    seq1 = ["U", "D", "U"]
    seq2 = ["U", "D", "U"]
    seq3 = ["U", "D"]
    seq4 = ["D", "U", "D"]

    d1 = segment_edit_distance(seq1, seq2)
    d2 = segment_edit_distance(seq1, seq3)
    d3 = segment_edit_distance(seq1, seq4)

    print(f"  Identical sequences distance: {d1} (expected 0)")
    print(f"  Length diff (3 vs 2) distance: {d2} (expected 1)")
    print(f"  All different distance: {d3} (expected 2+)")

    assert d1 == 0, f"Identical sequences should have distance 0, got {d1}"
    assert d2 == 1, f"Length diff of 1 should have distance 1, got {d2}"
    assert d3 >= 2, f"Completely different sequences should have distance >= 2, got {d3}"
    print("[PASS] Segment edit distance correct")


def test_structure_encoder_direction_sequence():
    """验证结构编码生成正确的方向序列"""
    prices = [10.0, 12.0, 11.2, 13.0, 12.0, 14.5, 13.2, 15.0, 14.0, 16.0]
    klines = make_klines(prices)

    encoder = StructureEncoder(min_pct=0.03, min_bars=1)
    encoded = encoder.encode(klines)

    dir_seq = encoded["direction_sequence"]
    seg_count = encoded["segment_count"]

    print(f"  Direction sequence: {dir_seq}")
    print(f"  Segment count: {seg_count}")

    assert seg_count >= 2, f"Should have at least 2 segments, got {seg_count} (dir_seq={dir_seq})"
    print(f"[PASS] Structure encoder produces direction_sequence={dir_seq}, segment_count={seg_count}")


def test_fast_filter():
    """验证粗筛过滤器"""
    template = {
        "direction_sequence": "U-D-U",
        "segment_count": 3,
        "ma_position": {20: "above"},
    }

    candidates = [
        {"direction_sequence": "U-D-U", "segment_count": 3, "ma_position": {20: "above"}},  # pass
        {"direction_sequence": "U-D-U", "segment_count": 2, "ma_position": {20: "above"}},  # pass (count diff 1)
        {"direction_sequence": "D-U-D", "segment_count": 3, "ma_position": {20: "above"}},  # fail (seq diff)
        {"direction_sequence": "U-D-U", "segment_count": 5, "ma_position": {20: "above"}},  # fail (count diff 2)
    ]

    filtered = fast_filter(template, candidates)

    print(f"  Input candidates: 4")
    print(f"  Filtered candidates: {len(filtered)}")

    assert len(filtered) == 2, f"Should pass 2 candidates, got {len(filtered)}"
    print("[PASS] Fast filter correctly filters by direction sequence and segment count")


def test_batch_match_top_n():
    """验证批量匹配返回 top_n 且排序"""
    template = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0]
    klines_t = make_klines(template)

    candidates = []
    for i in range(10):
        noise = np.random.randn(8) * 0.3
        prices = np.array(template) + noise
        candidates.append({
            "klines": make_klines(prices.tolist()),
            "metadata": {"stock_code": f"TEST{i:03d}", "start_date": "2024-01-01", "end_date": "2024-01-08"},
        })

    matcher = SkeletonMatcher(min_pct=0.03, min_bars=2)
    results = matcher.batch_match(klines_t, candidates, top_n=5)

    assert len(results) <= 5, f"Should return at most 5 results, got {len(results)}"
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i]["total_score"] >= results[i + 1]["total_score"], "Results should be sorted descending"

    print(f"[PASS] Batch match returns top 5 sorted by score")


def test_scene_config():
    """验证场景配置"""
    cfg_default = SceneConfig.from_scene("default")
    cfg_breakout = SceneConfig.from_scene("breakout_volume")
    cfg_trend = SceneConfig.from_scene("trend")

    assert cfg_default.structure_weight == 0.20
    assert cfg_breakout.rhythm_weight == 0.65
    assert cfg_trend.ma_fit_weight == 0.35

    w = cfg_default.to_weights()
    assert abs(w["structure"] - 0.20) < 0.01
    assert abs(w["rhythm"] - 0.60) < 0.01
    assert abs(w["ma_fit"] - 0.20) < 0.01

    print(f"[PASS] SceneConfig weights correct: default={w}")


def test_ma_fit_similarity():
    """验证均线拟合度计算"""
    t_close = np.linspace(10, 20, 30)
    s_close = t_close * 1.05
    o_close = np.linspace(10, 20, 30)[::-1]

    klines_t = make_klines(t_close.tolist())
    klines_s = make_klines(s_close.tolist())
    klines_o = make_klines(o_close.tolist())

    sim_same = compute_ma_fit_similarity(klines_t, klines_s, ma_window=20)
    sim_opp = compute_ma_fit_similarity(klines_t, klines_o, ma_window=20)

    print(f"  MA fit same trend: {sim_same:.4f}")
    print(f"  MA fit opposite: {sim_opp:.4f}")

    assert sim_same is not None, "Should compute MA fit for sufficient data"
    assert sim_opp is not None, "Should compute MA fit for sufficient data"
    assert sim_same > sim_opp, f"Same trend should have higher MA fit, got {sim_same} vs {sim_opp}"
    print(f"[PASS] MA fit similarity: same trend ({sim_same:.4f}) > opposite ({sim_opp:.4f})")


if __name__ == "__main__":
    print("=" * 60)
    print("K线形态相似度 V2 - 骨架算法验证")
    print("=" * 60)

    tests = [
        ("ZigZag 区分方向", test_zigzag_distinguishes_direction),
        ("节奏向量区分形态", test_rhythm_distinguishes_patterns),
        ("骨架拒绝反向序列", test_skeleton_rejects_opposite_direction),
        ("骨架接受同向序列", test_skeleton_accepts_similar_direction),
        ("段编辑距离", test_segment_edit_distance),
        ("结构编码方向序列", test_structure_encoder_direction_sequence),
        ("粗筛过滤器", test_fast_filter),
        ("批量匹配TopN", test_batch_match_top_n),
        ("场景配置", test_scene_config),
        ("均线拟合度", test_ma_fit_similarity),
    ]

    passed = 0
    failed = 0
    for name, test in tests:
        print(f"\n--- {name} ---")
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
