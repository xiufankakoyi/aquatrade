"""
Sandbox 验证脚本：DragonEye sentiment 分析器

用法：python sandbox/test_dragon_eye_sentiment.py
退出码 0 表示通过，非 0 表示失败。
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

# 把项目根加入 sys.path，确保 core.* 可被 import
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.dragon_eye.sentiment_analyzer import (  # noqa: E402
    analyze_sentiment,
    judge_cycle_phase,
    judge_risk_level,
    judge_theme_flow,
    calculate_total_score,
    score_to_dict,
    PHASE_ICE,
    PHASE_PEAK,
    PHASE_FADE,
    PHASE_RECOVER,
    RISK_HIGH,
    RISK_SAFE,
    SCORE_BULLISH_THRESHOLD,
    SCORE_PANIC_THRESHOLD,
    THEME_FLOW_INFLOW,
    THEME_FLOW_OUTFLOW,
    THEME_FLOW_STABLE,
    THEME_FLOW_NONE,
)


def build_cur(overrides: dict | None = None) -> dict:
    """构造一个标准的当日 sentiment 字典，方便测试"""
    base = {
        "date": "2026-01-10",
        "marketSentiment": {"rise": 3000, "fall": 1500},
        "emotionMetrics": {
            "brokenRatio": 0.15,
            "brokenCount": 5,
            "limitDownCount": 3,
            "limitUpCount": 50,
            "promotionRates": {"1to2": 30, "2to3": 20, "high": 10},
        },
        "ladder": {"1": [{"code": "1"}] * 20, "2": [{"code": "2"}] * 5, "5": [{"code": "5"}] * 1},
        "themes": [{"name": "AI"}, {"name": "新能源"}],
    }
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v
    return base


def case(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        sys.exit(1)


def test_judge_cycle_phase() -> None:
    # 冰点期
    cur = build_cur({"marketSentiment": {"rise": 500, "fall": 4000}, "emotionMetrics": {"brokenRatio": 0.5, "limitDownCount": 60}})
    r = judge_cycle_phase(cur, prev=None)
    case("冰点期判定", r.phase == PHASE_ICE, f"got={r.phase}, score={r.score}")

    # 高潮期
    cur = build_cur({"marketSentiment": {"rise": 4500, "fall": 500}, "emotionMetrics": {"brokenRatio": 0.1}})
    r = judge_cycle_phase(cur, prev=None)
    case("高潮期判定", r.phase == PHASE_PEAK, f"got={r.phase}, score={r.score}")

    # 退潮期
    cur = build_cur({"emotionMetrics": {"brokenRatio": 0.35, "limitDownCount": 25}})
    r = judge_cycle_phase(cur, prev=None)
    case("退潮期判定", r.phase == PHASE_FADE, f"got={r.phase}, score={r.score}")

    # 复苏期：需要 prev 对比，max_height 不能 >=5，否则优先匹配发酵期
    cur = build_cur({
        "marketSentiment": {"rise": 2500, "fall": 2000},
        "emotionMetrics": {"brokenRatio": 0.20, "limitDownCount": 5},
        "ladder": {"1": [{"code": "1"}] * 20, "2": [{"code": "2"}] * 5, "3": [{"code": "3"}] * 1},
        "themes": [{"name": "新题材X"}],
    })
    prev = build_cur({
        "date": "2026-01-09",
        "marketSentiment": {"rise": 2000, "fall": 2500},
        "emotionMetrics": {"brokenRatio": 0.30},
        "themes": [{"name": "完全不同的旧题材Y"}],
    })
    r = judge_cycle_phase(cur, prev=prev)
    case("复苏期判定", r.phase == PHASE_RECOVER, f"got={r.phase}, score={r.score}")

    # 缺数据降级
    r = judge_cycle_phase({}, prev=None)
    case("缺数据降级", r.phase is not None, f"got={r.phase}")


def test_judge_risk_level() -> None:
    case("高风险", judge_risk_level(25, 0) == RISK_HIGH)
    case("风险可控", judge_risk_level(2, 1) == RISK_SAFE)
    case("None 输入", judge_risk_level(None, None) == RISK_SAFE)


def test_calculate_total_score() -> None:
    # 强势：周期高分 + 普涨 + 高涨停 + 高接力
    score, summary = calculate_total_score(
        cycle_score=95, rise_count=4200, fall_count=300,
        limit_up_count=120, limit_down_count=2, promotion_avg=60,
    )
    case("强势档位", score >= SCORE_BULLISH_THRESHOLD and summary == "强势", f"score={score}, summary={summary}")

    score, summary = calculate_total_score(
        cycle_score=20, rise_count=500, fall_count=4000,
        limit_up_count=10, limit_down_count=50, promotion_avg=5,
    )
    case("恐慌档位", score < SCORE_PANIC_THRESHOLD and summary == "恐慌", f"score={score}, summary={summary}")


def test_analyze_sentiment_full() -> None:
    cur = build_cur()
    prev = build_cur({"date": "2026-01-09"})
    s = analyze_sentiment(cur, prev, None)
    d = score_to_dict(s)
    required = [
        "cycle_phase", "cycle_reasons", "risk_level",
        "promotion_1to2", "promotion_2to3", "promotion_high",
        "theme_continuity", "theme_flow", "total_score", "summary",
    ]
    for k in required:
        case(f"字段存在: {k}", k in d)
    case("综合分范围", 0.0 <= s.total_score <= 100.0, f"score={s.total_score}")
    case("主题连续性范围", 0.0 <= s.theme_continuity <= 1.0, f"cont={s.theme_continuity}")
    case("theme_flow 合法", s.theme_flow in {THEME_FLOW_INFLOW, THEME_FLOW_OUTFLOW, THEME_FLOW_STABLE, THEME_FLOW_NONE}, f"flow={s.theme_flow}")


def test_judge_theme_flow() -> None:
    # 稳定：今日题材与昨日有交集
    cur_themes = [{"name": "AI"}, {"name": "新能源"}]
    prev_themes = [{"name": "AI"}, {"name": "军工"}]
    case("theme_flow 稳定", judge_theme_flow(cur_themes, prev_themes) == THEME_FLOW_STABLE)

    # 流出：今日题材全部不在 prev 中
    cur_themes = [{"name": "医药"}]
    prev_themes = [{"name": "AI"}]
    case("theme_flow 流出", judge_theme_flow(cur_themes, prev_themes) == THEME_FLOW_OUTFLOW)

    # 无主线：cur 为空
    case("theme_flow 无主线(cur 空)", judge_theme_flow([], [{"name": "AI"}]) == THEME_FLOW_NONE)
    # 无主线：prev 为空（无法判断流入/流出）
    case("theme_flow 无主线(prev 空)", judge_theme_flow([{"name": "AI"}], []) == THEME_FLOW_NONE)
    # 全部为 None 输入
    case("theme_flow None 输入", judge_theme_flow(None, None) == THEME_FLOW_NONE)


def test_analyze_sentiment_empty() -> None:
    s = analyze_sentiment({})
    case("空数据不抛异常", s is not None)
    case("空数据默认震荡期", s.cycle_phase == "震荡期", f"got={s.cycle_phase}")
    case("空数据默认无主线", s.theme_flow == THEME_FLOW_NONE, f"got={s.theme_flow}")


def test_persistence_fields() -> None:
    """验证 service.py 的 sentiment 字段集合是否齐全（静态检查）"""
    from core.dragon_eye import service as svc
    src = Path(svc.__file__).read_text(encoding="utf-8")
    expected = [
        "cycle_phase", "cycle_reasons", "risk_level",
        "promotion_1to2", "promotion_2to3", "promotion_high",
        "theme_continuity", "theme_flow", "sentiment_score", "summary",
    ]
    for f in expected:
        case(f"service.py 含字段 {f}", f"'{f}'" in src)


def main() -> None:
    print("=== DragonEye Sentiment Analyzer Sandbox ===")
    try:
        test_judge_cycle_phase()
        test_judge_risk_level()
        test_calculate_total_score()
        test_judge_theme_flow()
        test_analyze_sentiment_full()
        test_analyze_sentiment_empty()
        test_persistence_fields()
    except Exception:
        print("UNEXPECTED EXCEPTION:")
        traceback.print_exc()
        sys.exit(1)
    print("\nALL TESTS PASSED.")


if __name__ == "__main__":
    main()
