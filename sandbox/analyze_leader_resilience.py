"""
Explore whether leaders are more resilient during weak market windows.

This script only uses local parquet data and keeps the definitions simple:
1. Limit-up chain leaders from dragon_eye/dragon_stock.parquet.
2. Industry market-cap leaders from stock_daily + stock_info.
3. Policy/theme leaders from dragon_stock reason text.
4. Fragile leaders using recent return, turnover, volume ratio, volatility.

Outputs CSV files under sandbox/leader_resilience_outputs by default.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "parquet_data"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "leader_resilience_outputs"

DAILY_COLS = [
    "stock_code",
    "trade_date",
    "close",
    "prev_close",
    "change_pct",
    "amount",
    "total_mv",
    "float_mv",
    "turnover_rate",
    "volume_ratio",
    "pe",
    "pb",
]

MOMENTUM_COLS = [
    "stock_code",
    "trade_date",
    "return_20d",
    "volatility_20d",
    "max_drawdown_20d",
    "beta_60d",
    "alpha_60d",
]

POLICY_KEYWORDS = [
    "国企",
    "国资",
    "改革",
    "政策",
    "自贸",
    "一带一路",
    "新质生产力",
    "人工智能",
    "机器人",
    "半导体",
    "芯片",
    "信创",
    "低空",
    "商业航天",
    "数据要素",
    "算力",
    "新能源",
    "光伏",
    "储能",
    "军工",
    "卫星",
    "两岸",
    "福建",
    "重组",
    "并购",
]


def normalize_code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.extract(r"(\d+)", expand=False).str.zfill(6)


def normalize_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.strftime("%Y-%m-%d")


def read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path, columns=columns)


def calc_forward_returns(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    horizons: Iterable[int],
    prefix: str = "fwd_ret",
) -> pd.DataFrame:
    df = df.sort_values([group_col, "trade_date"]).copy()
    for horizon in horizons:
        future = df.groupby(group_col, sort=False)[value_col].shift(-horizon)
        df[f"{prefix}_{horizon}d"] = future / df[value_col] - 1.0
    return df


def calc_single_series_forward_returns(
    df: pd.DataFrame,
    value_col: str,
    horizons: Iterable[int],
    prefix: str,
) -> pd.DataFrame:
    df = df.sort_values("trade_date").copy()
    for horizon in horizons:
        df[f"{prefix}_{horizon}d"] = df[value_col].shift(-horizon) / df[value_col] - 1.0
    return df


def calc_forward_down_returns(
    returns_df: pd.DataFrame,
    market_returns: pd.DataFrame,
    horizons: Iterable[int],
) -> pd.DataFrame:
    """Average stock return on T+1..T+N days where benchmark daily return is negative."""
    daily = returns_df[["stock_code", "trade_date", "daily_ret"]].copy()
    daily = daily.merge(market_returns, on="trade_date", how="left")
    daily = daily.sort_values(["stock_code", "trade_date"])
    down_stock = daily["daily_ret"].where(daily["benchmark_daily_ret"] < 0)
    down_market = daily["benchmark_daily_ret"].where(daily["benchmark_daily_ret"] < 0)

    for horizon in horizons:
        daily[f"future_down_ret_{horizon}d"] = (
            down_stock.groupby(daily["stock_code"], sort=False)
            .rolling(horizon, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
            .groupby(daily["stock_code"], sort=False)
            .shift(-horizon)
        )
        daily[f"future_down_bench_{horizon}d"] = (
            down_market.groupby(daily["stock_code"], sort=False)
            .rolling(horizon, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
            .groupby(daily["stock_code"], sort=False)
            .shift(-horizon)
        )

    cols = ["stock_code", "trade_date"]
    for horizon in horizons:
        cols.extend([f"future_down_ret_{horizon}d", f"future_down_bench_{horizon}d"])
    return daily[cols]


def zscore_by_date(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in columns:
        def _z(s: pd.Series) -> pd.Series:
            std = s.std(ddof=0)
            if not np.isfinite(std) or std == 0:
                return pd.Series(0.0, index=s.index)
            return (s - s.mean()) / std

        result[f"{col}_z"] = result.groupby("trade_date")[col].transform(_z)
    return result


def add_quantile_group(
    df: pd.DataFrame,
    value_col: str,
    group_name: str,
    by: list[str],
    q: int = 5,
) -> pd.DataFrame:
    def _rank_to_bucket(s: pd.Series) -> pd.Series:
        pct = s.rank(method="first", pct=True)
        bucket = np.ceil(pct * q).clip(1, q)
        return bucket.astype("Int64")

    out = df.copy()
    out[group_name] = out.groupby(by)[value_col].transform(_rank_to_bucket)
    return out


def summarize_groups(
    df: pd.DataFrame,
    group_col: str,
    horizons: list[int],
    label: str,
) -> pd.DataFrame:
    rows = []
    for horizon in horizons:
        ret_col = f"fwd_ret_{horizon}d"
        bench_col = f"benchmark_fwd_ret_{horizon}d"
        excess_col = f"excess_ret_{horizon}d"
        down_col = f"future_down_excess_{horizon}d"
        weak = df[df[bench_col] < 0].copy()
        for group, part in df.groupby(group_col, dropna=False):
            weak_part = weak[weak[group_col] == group]
            rows.append(
                {
                    "analysis": label,
                    "horizon": horizon,
                    "group": str(group),
                    "n_all": int(part[ret_col].notna().sum()),
                    "mean_ret": part[ret_col].mean(),
                    "mean_excess": part[excess_col].mean(),
                    "win_rate_excess": (part[excess_col] > 0).mean(),
                    "n_weak_windows": int(weak_part[ret_col].notna().sum()),
                    "weak_mean_ret": weak_part[ret_col].mean(),
                    "weak_mean_excess": weak_part[excess_col].mean(),
                    "weak_win_rate_excess": (weak_part[excess_col] > 0).mean(),
                    "down_day_mean_excess": part[down_col].mean() if down_col in part else np.nan,
                }
            )
    return pd.DataFrame(rows)


def pairwise_spread(
    summary: pd.DataFrame,
    analysis: str,
    high_group: str,
    low_group: str,
) -> pd.DataFrame:
    part = summary[summary["analysis"] == analysis]
    rows = []
    for horizon, hdf in part.groupby("horizon"):
        high = hdf[hdf["group"] == high_group]
        low = hdf[hdf["group"] == low_group]
        if high.empty or low.empty:
            continue
        high_row = high.iloc[0]
        low_row = low.iloc[0]
        rows.append(
            {
                "analysis": analysis,
                "horizon": horizon,
                "high_group": high_group,
                "low_group": low_group,
                "weak_excess_spread": high_row["weak_mean_excess"] - low_row["weak_mean_excess"],
                "all_excess_spread": high_row["mean_excess"] - low_row["mean_excess"],
                "down_day_excess_spread": high_row["down_day_mean_excess"] - low_row["down_day_mean_excess"],
            }
        )
    return pd.DataFrame(rows)


def load_main_data(start: str, end: str, horizons: list[int], benchmark: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_horizon = max(horizons)
    print("Loading stock_daily.parquet ...")
    daily = read_parquet(DATA_DIR / "stock_daily.parquet", columns=DAILY_COLS)
    daily["stock_code"] = normalize_code(daily["stock_code"])
    daily["trade_date"] = normalize_date(daily["trade_date"])
    daily = daily[(daily["trade_date"] >= start) & (daily["trade_date"] <= end)].copy()
    daily = daily.dropna(subset=["stock_code", "trade_date", "close"])
    daily["daily_ret"] = daily["close"] / daily["prev_close"] - 1.0
    fallback_ret = daily["change_pct"] / 100.0
    daily["daily_ret"] = daily["daily_ret"].where(np.isfinite(daily["daily_ret"]), fallback_ret)

    print("Loading stock_info.parquet ...")
    info = read_parquet(DATA_DIR / "stock_info.parquet")
    info["stock_code"] = normalize_code(info["stock_code"])
    info = info[["stock_code", "stock_name", "industry", "market", "list_status", "is_hs"]]
    daily = daily.merge(info, on="stock_code", how="left")
    daily = daily[(daily["list_status"].isna()) | (daily["list_status"] == "L")]
    daily = daily[daily["industry"].notna()].copy()

    print("Loading factors_momentum_hot.parquet ...")
    momentum = read_parquet(DATA_DIR / "factors_momentum_hot.parquet", columns=MOMENTUM_COLS)
    momentum["stock_code"] = normalize_code(momentum["stock_code"])
    momentum["trade_date"] = normalize_date(momentum["trade_date"])
    momentum = momentum[(momentum["trade_date"] >= start) & (momentum["trade_date"] <= end)].copy()
    daily = daily.merge(momentum, on=["stock_code", "trade_date"], how="left")

    daily = calc_forward_returns(daily, "stock_code", "close", horizons)

    print("Loading benchmark_daily.parquet ...")
    benchmark_df = read_parquet(DATA_DIR / "benchmark_daily.parquet")
    benchmark_df["code"] = normalize_code(benchmark_df["code"])
    benchmark_df["trade_date"] = normalize_date(benchmark_df["date"])
    benchmark_df = benchmark_df[benchmark_df["code"] == benchmark].copy()
    if benchmark_df.empty:
        raise ValueError(f"Benchmark {benchmark} not found in benchmark_daily.parquet")
    benchmark_df = benchmark_df[["trade_date", "close"]].sort_values("trade_date")
    benchmark_df["benchmark_daily_ret"] = benchmark_df["close"].pct_change()
    benchmark_df = calc_single_series_forward_returns(benchmark_df, "close", horizons, prefix="benchmark_fwd_ret")
    benchmark_df = benchmark_df.drop(columns=["close"])

    daily = daily.merge(benchmark_df, on="trade_date", how="left")
    for horizon in horizons:
        daily[f"excess_ret_{horizon}d"] = daily[f"fwd_ret_{horizon}d"] - daily[f"benchmark_fwd_ret_{horizon}d"]

    down = calc_forward_down_returns(
        daily[["stock_code", "trade_date", "daily_ret"]],
        benchmark_df[["trade_date", "benchmark_daily_ret"]],
        horizons,
    )
    daily = daily.merge(down, on=["stock_code", "trade_date"], how="left")
    for horizon in horizons:
        daily[f"future_down_excess_{horizon}d"] = (
            daily[f"future_down_ret_{horizon}d"] - daily[f"future_down_bench_{horizon}d"]
        )

    # Keep rows that can still see the requested future horizon.
    min_future_date = sorted(daily["trade_date"].dropna().unique())[:-max_horizon]
    if min_future_date:
        daily = daily[daily["trade_date"] <= min_future_date[-1]].copy()

    return daily, benchmark_df


def build_industry_leader_panel(daily: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "stock_code",
        "stock_name",
        "trade_date",
        "industry",
        "total_mv",
        "float_mv",
        "amount",
        "turnover_rate",
        "volume_ratio",
        "return_20d",
        "volatility_20d",
        "max_drawdown_20d",
        "pe",
        "pb",
    ]
    panel = daily[cols + [c for c in daily.columns if c.startswith(("fwd_ret_", "benchmark_fwd_ret_", "excess_ret_", "future_down_excess_"))]].copy()
    panel = panel.dropna(subset=["industry", "total_mv", "amount"])
    panel = panel.groupby(["trade_date", "industry"]).filter(lambda x: len(x) >= 10)

    panel = add_quantile_group(panel, "total_mv", "mv_bucket", ["trade_date", "industry"], q=5)
    panel = add_quantile_group(panel, "amount", "amount_bucket", ["trade_date", "industry"], q=5)
    panel["industry_leader_group"] = np.where(
        (panel["mv_bucket"] == 5) & (panel["amount_bucket"] >= 4),
        "leader",
        np.where(panel["mv_bucket"] <= 2, "laggard", "middle"),
    )
    return panel


def build_dragon_panel(daily: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    path = DATA_DIR / "dragon_eye" / "dragon_stock.parquet"
    print("Loading dragon_eye/dragon_stock.parquet ...")
    dragon = read_parquet(path)
    dragon["stock_code"] = normalize_code(dragon["stock_code"])
    dragon["trade_date"] = normalize_date(dragon["trade_date"])
    dragon = dragon[(dragon["trade_date"] >= start) & (dragon["trade_date"] <= end)].copy()
    if dragon.empty:
        return dragon

    keep = [
        "trade_date",
        "stock_code",
        "stock_name",
        "industry",
        "continue_num",
        "high_days_value",
        "limit_up_type",
        "open_num",
        "currency_value",
        "turnover_rate",
        "order_amount",
        "trading_amount",
        "reason_type",
        "reason_info",
        "limit_up_suc_rate",
        "tags",
    ]
    dragon = dragon[[c for c in keep if c in dragon.columns]].copy()
    text = (
        dragon.get("reason_type", pd.Series("", index=dragon.index)).fillna("").astype(str)
        + " "
        + dragon.get("reason_info", pd.Series("", index=dragon.index)).fillna("").astype(str)
        + " "
        + dragon.get("tags", pd.Series("", index=dragon.index)).fillna("").astype(str)
    )
    dragon["is_policy_theme"] = text.apply(lambda x: any(keyword in x for keyword in POLICY_KEYWORDS))
    dragon["dragon_group"] = np.where(dragon["continue_num"].fillna(0) >= 2, "chain_leader", "first_board")
    dragon["board_type_group"] = np.where(dragon["limit_up_type"].astype(str).str.contains("一字", na=False), "one_price", "turnover_board")
    dragon["seal_ratio"] = dragon["order_amount"] / dragon["currency_value"].replace(0, np.nan)

    merge_cols = [
        "stock_code",
        "trade_date",
        "return_20d",
        "volatility_20d",
        "max_drawdown_20d",
        "volume_ratio",
        "pe",
        "pb",
    ]
    forward_cols = [c for c in daily.columns if c.startswith(("fwd_ret_", "benchmark_fwd_ret_", "excess_ret_", "future_down_excess_"))]
    merged = dragon.merge(
        daily[merge_cols + forward_cols],
        on=["stock_code", "trade_date"],
        how="left",
        suffixes=("_dragon", ""),
    )
    merged["turnover_for_fragility"] = merged["turnover_rate"]
    return merged


def add_fragility_groups(df: pd.DataFrame, source: str) -> pd.DataFrame:
    out = df.copy()
    if source == "dragon":
        cols = ["return_20d", "turnover_for_fragility", "volume_ratio", "volatility_20d"]
    else:
        cols = ["return_20d", "turnover_rate", "volume_ratio", "volatility_20d"]

    for col in cols:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")

    zcols = [c for c in cols if out[c].notna().sum() > 0]
    out = zscore_by_date(out, zcols)
    out["fragility_score"] = sum(out[f"{c}_z"].fillna(0) for c in zcols)
    out = add_quantile_group(out, "fragility_score", "fragility_bucket", ["trade_date"], q=3)
    out["fragility_group"] = out["fragility_bucket"].map({1: "low_fragility", 2: "mid_fragility", 3: "high_fragility"})
    return out


def print_summary(summary: pd.DataFrame, title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    display_cols = [
        "analysis",
        "horizon",
        "group",
        "n_all",
        "mean_excess",
        "n_weak_windows",
        "weak_mean_excess",
        "weak_win_rate_excess",
        "down_day_mean_excess",
    ]
    view = summary[display_cols].copy()
    for col in ["mean_excess", "weak_mean_excess", "weak_win_rate_excess", "down_day_mean_excess"]:
        view[col] = view[col].astype(float).map(lambda x: "" if pd.isna(x) else f"{x * 100:.2f}%")
    print(view.to_string(index=False))


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Saved: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze A-share leader resilience with local parquet data.")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2025-11-20")
    parser.add_argument("--benchmark", default="000001", help="Benchmark code in benchmark_daily.parquet, default SH Composite.")
    parser.add_argument("--horizons", nargs="+", type=int, default=[1, 3, 5, 10])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--save-panels", action="store_true", help="Save large stock-date panels for deeper inspection.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    daily, _benchmark_df = load_main_data(args.start, args.end, args.horizons, args.benchmark)
    print(f"Daily panel rows: {len(daily):,}, stocks: {daily['stock_code'].nunique():,}")

    all_summaries = []
    spreads = []

    industry_panel = build_industry_leader_panel(daily)
    industry_summary = summarize_groups(industry_panel, "industry_leader_group", args.horizons, "Q2_industry_mv_leader")
    all_summaries.append(industry_summary)
    spreads.append(pairwise_spread(industry_summary, "Q2_industry_mv_leader", "leader", "laggard"))

    dragon_panel = build_dragon_panel(daily, args.start, args.end)
    if not dragon_panel.empty:
        dragon_summary = summarize_groups(dragon_panel, "dragon_group", args.horizons, "Q1_chain_leader")
        all_summaries.append(dragon_summary)
        spreads.append(pairwise_spread(dragon_summary, "Q1_chain_leader", "chain_leader", "first_board"))

        policy_panel = dragon_panel.copy()
        policy_panel["policy_group"] = np.where(policy_panel["is_policy_theme"], "policy_theme", "other_theme")
        policy_summary = summarize_groups(policy_panel, "policy_group", args.horizons, "Q3_policy_theme_leader")
        all_summaries.append(policy_summary)
        spreads.append(pairwise_spread(policy_summary, "Q3_policy_theme_leader", "policy_theme", "other_theme"))

        fragile_dragon = add_fragility_groups(dragon_panel[dragon_panel["dragon_group"] == "chain_leader"].copy(), "dragon")
        fragility_summary = summarize_groups(fragile_dragon, "fragility_group", args.horizons, "Q4_fragile_chain_leader")
        all_summaries.append(fragility_summary)
        spreads.append(pairwise_spread(fragility_summary, "Q4_fragile_chain_leader", "low_fragility", "high_fragility"))

        save_csv(dragon_panel, output_dir / "dragon_event_panel.csv")
        save_csv(fragile_dragon, output_dir / "fragile_dragon_panel.csv")
    else:
        print("No dragon_stock rows in selected date range.")

    fragile_industry = add_fragility_groups(industry_panel[industry_panel["industry_leader_group"] == "leader"].copy(), "industry")
    fragile_industry_summary = summarize_groups(fragile_industry, "fragility_group", args.horizons, "Q4_fragile_industry_leader")
    all_summaries.append(fragile_industry_summary)
    spreads.append(pairwise_spread(fragile_industry_summary, "Q4_fragile_industry_leader", "low_fragility", "high_fragility"))

    summary = pd.concat(all_summaries, ignore_index=True)
    spread_df = pd.concat([s for s in spreads if not s.empty], ignore_index=True) if spreads else pd.DataFrame()

    print_summary(summary, "Leader resilience summary")
    if not spread_df.empty:
        print("\n" + "=" * 100)
        print("Key spreads: positive weak_excess_spread means the first group was more resilient in weak windows")
        print("=" * 100)
        view = spread_df.copy()
        for col in ["weak_excess_spread", "all_excess_spread", "down_day_excess_spread"]:
            view[col] = view[col].astype(float).map(lambda x: "" if pd.isna(x) else f"{x * 100:.2f}%")
        print(view.to_string(index=False))

    save_csv(summary, output_dir / "leader_resilience_summary.csv")
    save_csv(spread_df, output_dir / "leader_resilience_spreads.csv")
    if args.save_panels:
        save_csv(industry_panel, output_dir / "industry_leader_panel.csv")
        save_csv(fragile_industry, output_dir / "fragile_industry_leader_panel.csv")


if __name__ == "__main__":
    main()
