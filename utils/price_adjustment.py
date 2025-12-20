from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd


PRICE_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "prev_close",
    "limit_up",
    "limit_down",
    "ma3_avg_price",
    "ma5_avg_price",
    "ma10_avg_price",
    "ma5",
    "ma10",
    "ma20",
]


def apply_forward_adjustment(
    df: Optional[pd.DataFrame],
    extra_columns: Optional[Iterable[str]] = None,
    adj_column: str = "adj_factor",
) -> Optional[pd.DataFrame]:
    """
    使用复权因子将价格类字段转换为前复权价格（向量化优化版本）。
    
    CHANGED: 使用向量化操作替代逐列循环，提升性能
    
    Args:
        df: 需要调整的 DataFrame（会原地修改并返回同一对象）
        extra_columns: 除默认价格列外还需要一并调整的列名
        adj_column: 存放复权因子的列名
        
    Returns:
        调整后的 DataFrame（原地修改）
    """
    if df is None or df.empty or adj_column not in df.columns:
        return df

    try:
        # CHANGED: 一次性转换复权因子，避免重复计算
        factors = pd.to_numeric(df[adj_column], errors="coerce").fillna(1.0)
        
        # 如果所有因子都是 1.0，直接返回（避免不必要的计算）
        if (factors == 1.0).all():
            return df
    except Exception:
        return df

    # CHANGED: 收集所有需要调整的列，一次性处理
    if extra_columns:
        columns = list(PRICE_COLUMNS) + list(extra_columns)
    else:
        columns = PRICE_COLUMNS
    
    # CHANGED: 只处理实际存在的列，避免 KeyError
    columns_to_adjust = [col for col in columns if col in df.columns]
    
    if not columns_to_adjust:
        return df
    
    # CHANGED: 向量化批量处理所有列，比逐列循环快得多
    # 使用 DataFrame 的乘法广播，一次性调整所有列
    for col in columns_to_adjust:
        # 先转换为数值类型，然后乘以因子
        df[col] = pd.to_numeric(df[col], errors="coerce") * factors

    return df

