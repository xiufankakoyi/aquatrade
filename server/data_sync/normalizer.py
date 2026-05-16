"""
Normalizer

统一股票代码格式和字段命名。

输入可能是:
    000001
    000001.SZ
    SZ000001
    sh600000
    600000.SH

统一输出:
    symbol: 000001.SZ / 600000.SH
    exchange: SZ / SH
    raw_symbol: 原始代码

同时统一字段:
    pct_chg, amount, close, stock_name, trade_date
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# 交易所映射
_EXCHANGE_MAP = {
    "SZ": "SZ",
    "SH": "SH",
    "sz": "SZ",
    "sh": "SH",
    "shenzhen": "SZ",
    "shanghai": "SH",
}


def normalize_symbol(raw: str) -> dict[str, Any]:
    """
    归一化股票代码。

    Args:
        raw: 原始股票代码字符串。

    Returns:
        dict 包含:
            - symbol: 标准格式 (如 000001.SZ)
            - exchange: 交易所 (SZ/SH)
            - raw_symbol: 原始输入
    """
    if not raw:
        return {"symbol": "", "exchange": "", "raw_symbol": ""}

    raw_str = str(raw).strip().upper()

    # 匹配 6 位数字
    match = re.search(r'(\d{6})', raw_str)
    if not match:
        return {"symbol": raw_str, "exchange": "", "raw_symbol": raw}

    code = match.group(1)

    # 判断交易所
    if code.startswith("6") or code.startswith("5") or code.startswith("9"):
        exchange = "SH"
    elif code.startswith("0") or code.startswith("3") or code.startswith("2"):
        exchange = "SZ"
    elif code.startswith("4") or code.startswith("8"):
        exchange = "BJ"
    else:
        exchange = ""

    # 如果原始字符串包含交易所信息，优先使用
    if ".SH" in raw_str or "SH" in raw_str[:2]:
        exchange = "SH"
    elif ".SZ" in raw_str or "SZ" in raw_str[:2]:
        exchange = "SZ"
    elif ".BJ" in raw_str or "BJ" in raw_str[:2]:
        exchange = "BJ"

    symbol = f"{code}.{exchange}" if exchange else code
    return {"symbol": symbol, "exchange": exchange, "raw_symbol": raw}


def normalize_symbols(series: Any) -> Any:
    """
    对 pandas Series 批量归一化股票代码。

    Args:
        series: pandas Series，元素为原始股票代码。

    Returns:
        pandas Series，元素为归一化后的 symbol。
    """
    import pandas as pd
    if not isinstance(series, pd.Series):
        series = pd.Series(series)
    return series.astype(str).apply(lambda x: normalize_symbol(x)["symbol"])


def normalize_field_names(df: Any) -> Any:
    """
    统一 DataFrame 字段名。

    支持的映射:
        - 涨跌幅: pct_chg, pct_change, change_pct, 涨跌幅
        - 成交额: amount, turnover, vol_amount, 成交额
        - 收盘价: close, closing_price, 收盘价
        - 股票名称: stock_name, name, 名称
        - 交易日期: trade_date, date, 日期
    """
    import pandas as pd
    if not isinstance(df, pd.DataFrame):
        return df

    column_map = {
        "pct_change": "pct_chg",
        "change_pct": "pct_chg",
        "涨跌幅": "pct_chg",
        "turnover": "amount",
        "vol_amount": "amount",
        "成交额": "amount",
        "closing_price": "close",
        "收盘价": "close",
        "name": "stock_name",
        "名称": "stock_name",
        "date": "trade_date",
        "日期": "trade_date",
    }

    renamed = {}
    for col in df.columns:
        target = column_map.get(col.lower(), col)
        renamed[col] = target

    df = df.rename(columns=renamed)
    return df
