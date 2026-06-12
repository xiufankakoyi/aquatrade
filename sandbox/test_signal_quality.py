"""
Sandbox 验证脚本：策略信号质量评估器（mock 引擎版）

说明：真实回测引擎依赖大量数据/IO，这里用一个最小的 MockUnifiedBacktestEngine
来验证 SignalQualityEvaluator 的逻辑正确性。
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.strategies.signal_quality import (  # noqa: E402
    SignalQualityEvaluator,
    QualityDimension,
    SignalQualityReport,
    _score_to_grade,
    QUALITY_A_GRADE_THRESHOLD,
    QUALITY_B_GRADE_THRESHOLD,
    QUALITY_C_GRADE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Mock 数据
# ---------------------------------------------------------------------------
class MockConfig:
    commission_rate = 0.0003
    min_commission = 5.0


class MockEngine:
    """极简 mock，仅产出 final_metrics，不实际计算"""
    config = MockConfig()

    def __init__(self, scenario: str = "good"):
        self.scenario = scenario

    def _metrics(self, base: float = 0.0) -> Dict[str, Any]:
        # scenario 控制指标"好坏"。base 仅作微调，避免随机化为反向。
        if self.scenario == "good":
            return {
                "totalReturn": 25.0 + (base % 5),
                "sharpeRatio": 1.8 + (base % 5) / 50,
                "winRate": 0.62,
                "profitFactor": 1.8,
                "avgTradeReturn": 0.8,
                "maxDrawdown": 8.0,
                "tradeCount": 200,
            }
        if self.scenario == "bad":
            return {
                "totalReturn": -10.0 - (base % 5),
                "sharpeRatio": -0.4 - (base % 5) / 50,
                "winRate": 0.35,
                "profitFactor": 0.7,
                "avgTradeReturn": -0.5,
                "maxDrawdown": 25.0,
                "tradeCount": 200,
            }
        if self.scenario == "soso":
            return {
                "totalReturn": 3.0 + (base % 3) - 1,
                "sharpeRatio": 0.3 + (base % 3) / 100,
                "winRate": 0.50,
                "profitFactor": 1.1,
                "avgTradeReturn": 0.1,
                "maxDrawdown": 12.0,
                "tradeCount": 200,
            }
        return {"totalReturn": 0, "sharpeRatio": 0, "winRate": 0, "profitFactor": 0, "avgTradeReturn": 0}

    def run_backtest_streaming(
        self, start_date: str, end_date: str, strategy: Any
    ) -> Generator[Dict[str, Any], None, None]:
        # 给个 base 让不同窗口/参数能产生波动
        try:
            base = hash((start_date, end_date, str(strategy.__dict__))) % 30
        except Exception:
            base = 0
        yield {"type": "final_metrics", "data": self._metrics(base=base)}


class MockStrategy:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def case(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------
def test_score_to_grade() -> None:
    case("A 档", _score_to_grade(85) == "A")
    case("B 档", _score_to_grade(70) == "B")
    case("C 档", _score_to_grade(50) == "C")
    case("D 档", _score_to_grade(20) == "D")
    case("A 阈值边界", _score_to_grade(QUALITY_A_GRADE_THRESHOLD) == "A")
    case("B 阈值边界", _score_to_grade(QUALITY_B_GRADE_THRESHOLD) == "B")
    case("C 阈值边界", _score_to_grade(QUALITY_C_GRADE_THRESHOLD) == "C")


def test_signal_profitability_good() -> None:
    engine = MockEngine(scenario="good")
    ev = SignalQualityEvaluator(engine=engine)
    dim = ev.evaluate_signal_profitability(lambda: MockStrategy(), "2024-01-01", "2024-12-31")
    case("好策略 - 维度名", dim.name == "signal_profitability")
    case("好策略 - 分数较高", dim.score >= 50.0, f"score={dim.score}")
    case("好策略 - summary 提到正收益", "正收益" in dim.summary or "微利" in dim.summary, dim.summary)


def test_signal_profitability_bad() -> None:
    engine = MockEngine(scenario="bad")
    ev = SignalQualityEvaluator(engine=engine)
    dim = ev.evaluate_signal_profitability(lambda: MockStrategy(), "2024-01-01", "2024-12-31")
    case("差策略 - 分数较低", dim.score < 50.0, f"score={dim.score}")
    case("差策略 - summary 提到亏损", "亏损" in dim.summary, dim.summary)


def test_long_term_validity() -> None:
    engine = MockEngine(scenario="good")
    ev = SignalQualityEvaluator(engine=engine)
    dim = ev.evaluate_long_term_validity(lambda: MockStrategy(), "2024-01-01", "2024-12-31", n_windows=4)
    case("长期有效性 - 维度名", dim.name == "long_term_validity")
    case("长期有效性 - 包含 windows", "windows" in dim.detail)
    case("长期有效性 - score 在 [0, 100]", 0.0 <= dim.score <= 100.0, f"score={dim.score}")


def test_long_term_validity_short_range() -> None:
    engine = MockEngine(scenario="good")
    ev = SignalQualityEvaluator(engine=engine)
    dim = ev.evaluate_long_term_validity(lambda: MockStrategy(), "2024-01-01", "2024-01-15")
    case("短时间范围降级", dim.score == 50.0, f"score={dim.score}")


def test_parameter_stability() -> None:
    engine = MockEngine(scenario="good")
    ev = SignalQualityEvaluator(engine=engine)
    dim = ev.evaluate_parameter_stability(
        lambda **p: MockStrategy(**p),
        {"fast_window": [3, 5, 7], "slow_window": [15, 20, 25]},
        "2024-01-01",
        "2024-12-31",
    )
    case("参数稳健性 - 维度名", dim.name == "parameter_stability")
    case("参数稳健性 - 有 trials", "trials" in dim.detail)
    case("参数稳健性 - score 范围", 0.0 <= dim.score <= 100.0, f"score={dim.score}")


def test_parameter_stability_empty_grid() -> None:
    engine = MockEngine(scenario="good")
    ev = SignalQualityEvaluator(engine=engine)
    dim = ev.evaluate_parameter_stability(lambda: MockStrategy(), {}, "2024-01-01", "2024-12-31")
    case("空网格不抛异常", dim is not None)
    case("空网格默认分", dim.score == 50.0, f"score={dim.score}")


def test_overfit_risk() -> None:
    engine = MockEngine(scenario="good")
    ev = SignalQualityEvaluator(engine=engine)
    dim = ev.evaluate_overfit_risk(lambda: MockStrategy(), "2024-01-01", "2024-12-31", n_permutations=3)
    case("过拟合检测 - 维度名", dim.name == "overfit_risk")
    case("过拟合检测 - 有 baseline", "baseline_sharpe" in dim.detail)
    case("过拟合检测 - score 范围", 0.0 <= dim.score <= 100.0, f"score={dim.score}")
    # 验证 engine.config.commission_rate 已被还原
    case("engine config 还原", abs(engine.config.commission_rate - 0.0003) < 1e-9,
         f"rate={engine.config.commission_rate}")


def test_evaluate_all_good() -> None:
    engine = MockEngine(scenario="good")
    ev = SignalQualityEvaluator(engine=engine)
    report = ev.evaluate_all(
        lambda **p: MockStrategy(**p),
        "test_strategy",
        "2024-01-01",
        "2024-12-31",
        param_grid={"window": [5, 10, 15]},
    )
    case("综合 - report 字段齐全", report.strategy_id == "test_strategy")
    case("综合 - 4 个维度", len(report.dimensions) == 4, f"n={len(report.dimensions)}")
    case("综合 - 总分范围", 0.0 <= report.total_score <= 100.0, f"score={report.total_score}")
    case("综合 - grade 合法", report.grade in ("A", "B", "C", "D"), f"grade={report.grade}")
    d = report.to_dict()
    case("to_dict 序列化", "dimensions" in d and "total_score" in d)


def test_evaluate_all_bad() -> None:
    engine = MockEngine(scenario="bad")
    ev = SignalQualityEvaluator(engine=engine)
    report = ev.evaluate_all(lambda: MockStrategy(), "bad_strategy", "2024-01-01", "2024-12-31")
    case("差策略 - 报告生成", report is not None)
    # score 较低，但可能仍 >= D 档最低 0
    case("差策略 - grade 为 C/D", report.grade in ("C", "D"), f"grade={report.grade}")


def test_engine_failure_resilience() -> None:
    """回测失败的容错性"""
    class FailingEngine:
        config = MockConfig()

        def run_backtest_streaming(self, *a, **kw):
            raise RuntimeError("mock failure")

    ev = SignalQualityEvaluator(engine=FailingEngine())
    d1 = ev.evaluate_signal_profitability(lambda: MockStrategy(), "2024-01-01", "2024-12-31")
    d2 = ev.evaluate_long_term_validity(lambda: MockStrategy(), "2024-01-01", "2024-12-31")
    d3 = ev.evaluate_parameter_stability(lambda **p: MockStrategy(**p), {"x": [1, 2]}, "2024-01-01", "2024-12-31")
    d4 = ev.evaluate_overfit_risk(lambda: MockStrategy(), "2024-01-01", "2024-12-31")
    case("失败容错 signal", d1.score == 0.0)
    case("失败容错 long_term", d2.score == 0.0)
    case("失败容错 param", d3.score == 0.0)
    case("失败容错 overfit", d4.score == 0.0)


def main() -> None:
    print("=== Signal Quality Evaluator Sandbox ===")
    try:
        test_score_to_grade()
        test_signal_profitability_good()
        test_signal_profitability_bad()
        test_long_term_validity()
        test_long_term_validity_short_range()
        test_parameter_stability()
        test_parameter_stability_empty_grid()
        test_overfit_risk()
        test_evaluate_all_good()
        test_evaluate_all_bad()
        test_engine_failure_resilience()
    except Exception:
        print("UNEXPECTED EXCEPTION:")
        traceback.print_exc()
        sys.exit(1)
    print("\nALL TESTS PASSED.")


if __name__ == "__main__":
    main()
