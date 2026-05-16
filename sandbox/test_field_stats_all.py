#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试所有可能的 field_stats 请求
"""
import requests
import json

base_url = "http://localhost:5000"

# 从 INDICATOR_CATEGORIES 中获取所有字段
fields = [
    "stock_code", "trade_date",
    "close", "open", "high", "low", "change_pct", "volume", "amount", "turnover_rate", "volume_ratio",
    "ma5", "ma10", "ma20", "ma30", "ma60",
    "rsi_6", "rsi_12", "rsi_24",
    "macd_dif", "macd_dea", "macd_bar",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_mid", "boll_lower",
    "cci", "wr", "obv", "dmi_plus", "dmi_minus", "dmi_adx",
    "psy", "vr", "asi", "roc", "mtm", "trix", "uos", "mass",
    "ar", "br", "cr", "emv", "wvad", "pvt", "ad", "cmf", "mfi",
    "total_mv", "float_mv", "pe", "pb", "ps", "pcf", "roe", "roa", "gross_profit_margin", "net_profit_margin", "debt_ratio", "current_ratio", "quick_ratio", "inventory_turnover", "receivable_turnover", "asset_turnover",
    "volatility_20", "volatility_60", "beta", "alpha", "sharpe", "sortino", "max_drawdown", "var_95", "cvar_95", "skewness", "kurtosis"
]

print(f"Testing {len(fields)} fields...\n")

errors = []
for field in fields:
    try:
        response = requests.post(
            f"{base_url}/api/screener/field_stats",
            json={"field": field, "date": "2026-02-04"},
            timeout=10
        )
        if response.status_code == 500:
            errors.append((field, response.status_code, response.text))
            print(f"❌ {field}: 500 ERROR")
        elif response.status_code == 400:
            print(f"⚠️  {field}: 400 Invalid field")
        elif response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ {field}: OK (count={data['data']['count']})")
            else:
                errors.append((field, response.status_code, data.get('error')))
                print(f"❌ {field}: Error - {data.get('error')}")
        else:
            errors.append((field, response.status_code, response.text))
            print(f"❌ {field}: {response.status_code}")
    except Exception as e:
        errors.append((field, "Exception", str(e)))
        print(f"❌ {field}: Exception - {e}")

print(f"\n{'='*50}")
print(f"Total fields: {len(fields)}")
print(f"Errors: {len(errors)}")
if errors:
    print("\nError details:")
    for field, status, error in errors:
        print(f"  {field}: {status} - {error[:100]}")
