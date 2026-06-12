"""
Sandbox 验证脚本：回测真实性（停牌/ST/涨跌停/成交量/滑点/不可成交订单）

策略：
- 构造最小化数据结构（不走数据库）
- 用 polars 关闭的姿势直接测核心 _execute_trades 行为
- 验证：
  1. 停牌 -> rejected
  2. ST -> rejected
  3. 涨停 -> rejected
  4. 跌停 -> rejected
  5. 成交量不足 -> rejected
  6. 滑点成本被正确计算
  7. RejectedOrderStat 累加正确
  8. 资金不足 -> rejected
  9. BacktestResult 包含真实性统计字段
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 关闭 polars 走量化代码路径，让单元测试只跑核心小循环
import os
os.environ.setdefault("AQUATRADE_TEST_FORCE_SIMPLE", "1")

from core.backtest.unified_engine import (  # noqa: E402
    BacktestConfig,
    RejectedOrderStat,
    UnifiedBacktestEngine,
    BacktestResult,
)


class FakeDataQuery:
    """最小化的 data_query 桩，确保 _execute_trades 不会触发 IO"""

    def __init__(self):
        self.conn = None
        self._cache_loaded = False
        self._preloaded_date_range = None

    def get_trading_dates(self, start: str, end: str) -> List[str]:
        return []


import pandas as pd  # noqa: E402

CURRENT_TIME = pd.Timestamp("2026-01-15")


def case(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        sys.exit(1)


def make_engine() -> UnifiedBacktestEngine:
    cfg = BacktestConfig(
        initial_capital=1_000_000.0,
        commission_rate=0.0003,
        min_commission=5.0,
        sell_tax=0.001,
        slippage_rate=0.001,
        exclude_st=True,
        volume_cap_ratio=0.05,
        min_trade_amount=1000.0,
        max_positions=10,
    )
    return UnifiedBacktestEngine(data_query=FakeDataQuery(), config=cfg)


def build_data_dict(
    code: str,
    *,
    open_price: float = 10.0,
    close_price: float = 10.5,
    is_suspended: bool = False,
    is_limit_up: bool = False,
    is_limit_down: bool = False,
    is_st: bool = False,
    volume: float = 100_000.0,
) -> Dict[str, Any]:
    return {
        "open": open_price,
        "close": close_price,
        "is_suspended": 1 if is_suspended else 0,
        "is_limit_up": 1 if is_limit_up else 0,
        "is_limit_down": 1 if is_limit_down else 0,
        "is_st": 1 if is_st else 0,
        "volume": volume,
        "adj_factor": 1.0,
        "total_mv": 1e8,
    }


def test_suspended_blocks_buy() -> None:
    engine = make_engine()
    engine.reset_realism_stats()
    data_dict = {
        "000001": build_data_dict("000001", is_suspended=True),
    }
    signals = {"000001": {"action": "buy", "indicators": {}}}
    new_portfolio, new_cash, trades = engine._execute_trades(
        current_time=CURRENT_TIME,
        stock_pool=None,
        signals=signals,
        portfolio={},
        cash=1_000_000.0,
        position_info={},
        data_dict=data_dict,
    )
    case("停牌股票未被买入", len(trades) == 0)
    case("停牌订单被计入 suspended", engine._rejected_stats.suspended >= 1, f"suspended={engine._rejected_stats.suspended}")


def test_st_blocks_buy() -> None:
    engine = make_engine()
    engine.reset_realism_stats()
    data_dict = {"000002": build_data_dict("000002", is_st=True)}
    signals = {"000002": {"action": "buy"}}
    _, _, trades = engine._execute_trades(CURRENT_TIME, None, signals, {}, 1_000_000.0, {}, data_dict)
    case("ST 股票未被买入", len(trades) == 0)
    case("ST 订单被计入 st", engine._rejected_stats.st >= 1, f"st={engine._rejected_stats.st}")


def test_limit_up_blocks_buy() -> None:
    engine = make_engine()
    engine.reset_realism_stats()
    data_dict = {"000003": build_data_dict("000003", is_limit_up=True, open_price=11.0)}
    signals = {"000003": {"action": "buy"}}
    _, _, trades = engine._execute_trades(CURRENT_TIME, None, signals, {}, 1_000_000.0, {}, data_dict)
    case("涨停股票未被买入", len(trades) == 0)
    case("涨停订单被计入 limitUp", engine._rejected_stats.limit_up >= 1, f"limit_up={engine._rejected_stats.limit_up}")


def test_limit_down_blocks_sell() -> None:
    engine = make_engine()
    engine.reset_realism_stats()
    data_dict = {"000004": build_data_dict("000004", is_limit_down=True, open_price=9.0)}
    signals = {"000004": {"action": "sell"}}
    portfolio = {"000004": 1000}
    position_info = {"000004": {"cost": 10.0, "entry_date": "2026-01-01"}}
    _, _, trades = engine._execute_trades(CURRENT_TIME, None, signals, portfolio, 900_000.0, position_info, data_dict)
    case("跌停股票未卖出", len(trades) == 0)
    case("跌停订单被计入 limitDown", engine._rejected_stats.limit_down >= 1, f"limit_down={engine._rejected_stats.limit_down}")


def test_volume_cap_clamps_buy() -> None:
    """成交量过小 -> 钳制买入股数"""
    engine = make_engine()
    engine.reset_realism_stats()
    data_dict = {"000005": build_data_dict("000005", open_price=10.0, volume=1000.0)}
    signals = {"000005": {"action": "buy"}}
    _, _, trades = engine._execute_trades(CURRENT_TIME, None, signals, {}, 1_000_000.0, {}, data_dict)
    case("成交量过小未被买入", len(trades) == 0)
    case("成交量约束被计入 volume", engine._rejected_stats.volume >= 1, f"volume={engine._rejected_stats.volume}")


def test_normal_buy_succeeds_with_slippage() -> None:
    """正常买入应成交，滑点应被记录"""
    engine = make_engine()
    engine.reset_realism_stats()
    data_dict = {"000006": build_data_dict("000006", open_price=10.0, volume=10_000_000.0)}
    signals = {"000006": {"action": "buy"}}
    portfolio, cash, trades = engine._execute_trades(CURRENT_TIME, None, signals, {}, 1_000_000.0, {}, data_dict)
    case("正常买入成交", len(trades) == 1, f"trades={len(trades)}")
    if trades:
        case("滑点抬高出价", trades[0].price > 10.0, f"price={trades[0].price}")
    case("滑点成本被累计", engine._slippage_cost_total > 0, f"slippage={engine._slippage_cost_total}")


def test_rejected_stats_total() -> None:
    stat = RejectedOrderStat()
    stat.suspended = 1
    stat.limit_up = 2
    stat.st = 3
    stat.volume = 1
    case("total 统计", stat.total() == 7)
    d = stat.to_dict()
    case("to_dict 字段", d["total"] == 7 and d["limitUp"] == 2 and d["st"] == 3)


def test_backtest_result_contains_realism_fields() -> None:
    """验证 BacktestResult dataclass 字段"""
    r = BacktestResult(
        final_equity=1_000_000.0,
        total_return=0.0,
        annualized_return=0.0,
        max_drawdown=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        volatility=0.0,
        win_rate=0.0,
        profit_factor=0.0,
        trade_count=0,
        avg_trade_return=0.0,
        max_winning_streak=0,
        max_losing_streak=0,
        calmar_ratio=0.0,
        rejected_orders={"suspended": 1, "limitUp": 0, "limitDown": 0, "st": 0, "volume": 0, "insufficientCash": 0, "invalidPrice": 0, "other": 0, "total": 1},
        slippage_cost=123.45,
        filter_stats={"slippageRate": 0.001, "excludeSt": True, "volumeCapRatio": 0.05, "minTradeAmount": 1000.0},
    )
    case("BacktestResult.rejected_orders 存在", r.rejected_orders.get("total") == 1)
    case("BacktestResult.slippage_cost 存在", abs(r.slippage_cost - 123.45) < 1e-6)
    case("BacktestResult.filter_stats 存在", r.filter_stats.get("excludeSt") is True)


def test_config_fields() -> None:
    """验证 BacktestConfig 新增真实性参数"""
    cfg = BacktestConfig()
    case("slippage_rate 默认", cfg.slippage_rate == 0.001)
    case("exclude_st 默认", cfg.exclude_st is True)
    case("volume_cap_ratio 默认", cfg.volume_cap_ratio == 0.05)
    case("min_trade_amount 默认", cfg.min_trade_amount == 1000.0)


def main() -> None:
    print("=== Backtest Authenticity Sandbox ===")
    try:
        test_config_fields()
        test_rejected_stats_total()
        test_backtest_result_contains_realism_fields()
        test_normal_buy_succeeds_with_slippage()
        test_suspended_blocks_buy()
        test_st_blocks_buy()
        test_limit_up_blocks_buy()
        test_limit_down_blocks_sell()
        test_volume_cap_clamps_buy()
    except Exception:
        print("UNEXPECTED EXCEPTION:")
        traceback.print_exc()
        sys.exit(1)
    print("\nALL TESTS PASSED.")


if __name__ == "__main__":
    main()
