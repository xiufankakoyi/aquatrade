"""
直接测试 API 数据返回
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

import polars as pl
from core.dragon_eye.manager import DragonEyeManager

manager = DragonEyeManager()

print("测试 limit-up-trend 数据...")
df = manager.get_market_sentiment("2026-02-01", "2026-02-20")

print(f"数据形状: {df.shape}")
print(f"列名: {df.columns}")

if not df.is_empty():
    df = df.sort('trade_date')
    
    # 转换日期为字符串格式
    if 'trade_date' in df.columns:
        dates = df['trade_date'].dt.strftime('%Y-%m-%d').to_list()
        print(f"dates: {dates[:5]}...")
    
    result = {
        "dates": dates if 'dates' in dir() else [],
        "limit_up_counts": df['limit_up_count'].to_list() if 'limit_up_count' in df.columns else [],
        "max_heights": df['max_height'].to_list() if 'max_height' in df.columns else [],
        "broken_ratios": df['broken_ratio'].to_list() if 'broken_ratio' in df.columns else [],
    }
    
    print(f"\n结果:")
    print(f"  dates: {result['dates'][:5]}...")
    print(f"  limit_up_counts: {result['limit_up_counts'][:5]}...")
    print(f"  max_heights: {result['max_heights'][:5]}...")
