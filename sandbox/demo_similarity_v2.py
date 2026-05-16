"""
K线形态相似度骨架算法 Demo

演示分层骨架算法的核心能力：
1. ZigZag 骨架提取
2. 节奏向量计算
3. 骨架匹配：同向 vs 反向
4. 场景差异化权重
"""

import numpy as np

np.random.seed(42)


def make_klines(closes: list, volumes: list = None) -> dict:
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


print("=" * 60)
print("K线形态相似度骨架算法 Demo")
print("=" * 60)

print("\n[1] ZigZag 骨架提取")
print("-" * 40)

from core.similarity.zigzag import identify_extrema, build_segments

prices_up_down = [10.0, 12.0, 11.0, 13.0, 14.0, 12.0, 10.0]
prices_down_up = [14.0, 12.0, 13.0, 11.0, 10.0, 12.0, 14.0]

e1 = identify_extrema(np.array(prices_up_down), min_pct=0.05, min_bars=1)
e2 = identify_extrema(np.array(prices_down_up), min_pct=0.05, min_bars=1)

s1 = build_segments(np.array(prices_up_down), e1)
s2 = build_segments(np.array(prices_down_up), e2)

print(f"  走势A [先涨后跌]: {[(seg['direction'], f'{seg['pct_change']*100:.0f}%') for seg in s1]}")
print(f"  走势B [先跌后涨]: {[(seg['direction'], f'{seg['pct_change']*100:.0f}%') for seg in s2]}")
if len(s1) >= 2 and len(s2) >= 2:
    print(f"  -> 骨架方向序列: {s1[0]['direction'][0].upper()}{s1[1]['direction'][0].upper()} vs {s2[0]['direction'][0].upper()}{s2[1]['direction'][0].upper()}")


print("\n[2] 节奏向量提取")
print("-" * 40)

from core.similarity.rhythm import extract_rhythm_vector, to_array, cosine_similarity

small_steps = [10.0 + i * 0.3 + np.random.randn() * 0.05 for i in range(15)]
big_swings = [10.0, 12.0, 9.0, 13.0, 8.0, 14.0, 8.5, 13.5, 9.0, 14.5]

r_small = extract_rhythm_vector(make_klines(small_steps))
r_big = extract_rhythm_vector(make_klines(big_swings))

print(f"  小阳碎步节奏向量: {to_array(r_small).round(2)}")
print(f"  大起大落节奏向量: {to_array(r_big).round(2)}")
print(f"  节奏余弦相似度: {cosine_similarity(to_array(r_small), to_array(r_big)):.4f}")


print("\n[3] 骨架匹配：同向 vs 反向")
print("-" * 40)

from core.similarity.pattern_enhancer_v2 import SkeletonMatcher

matcher = SkeletonMatcher(min_pct=0.05, min_bars=1)

template = [10.0, 12.0, 11.0, 13.0, 14.0, 12.0, 10.0]
opposite = [14.0, 12.0, 13.0, 11.0, 10.0, 12.0, 14.0]
similar = [20.0, 24.0, 22.0, 26.0, 28.0, 24.0, 20.0]

klines_t = make_klines(template)
klines_o = make_klines(opposite)
klines_s = make_klines(similar)

r_opposite = matcher.match(klines_t, klines_o)
r_similar = matcher.match(klines_t, klines_s)

print(f"  模板 vs 反向走势: 总分={r_opposite['total_score']:.4f} (结构={r_opposite['structure_score']:.4f}, 节奏={r_opposite['rhythm_score']:.4f})")
print(f"  模板 vs 同向走势: 总分={r_similar['total_score']:.4f} (结构={r_similar['structure_score']:.4f}, 节奏={r_similar['rhythm_score']:.4f})")
print(f"  -> 反向得分 < 同向得分: {r_opposite['total_score']:.4f} < {r_similar['total_score']:.4f}")


print("\n[4] 场景差异化权重")
print("-" * 40)

from core.similarity.pattern_enhancer_v2 import SceneConfig

for scene in ["default", "breakout_volume", "limit_break", "n_shape", "trend"]:
    cfg = SceneConfig.from_scene(scene)
    w = cfg.to_weights()
    print(f"  {scene:20s}: 结构={w['structure']:.2f}, 节奏={w['rhythm']:.2f}, 均线={w['ma_fit']:.2f}")


print("\n[5] 批量匹配 Top3")
print("-" * 40)

candidates = []
for i in range(5):
    noise = np.random.randn(7) * 0.5
    prices = np.array(template) + noise
    candidates.append({
        "klines": make_klines(prices.tolist()),
        "metadata": {"stock_code": f"TEST{i:03d}"},
    })

results = matcher.batch_match(klines_t, candidates, top_n=3)

for i, r in enumerate(results):
    print(f"  Top {i+1}: {r['metadata']['stock_code']} 得分={r['total_score']:.4f}")


print("\n" + "=" * 60)
print("Demo 完成！")
print("=" * 60)
