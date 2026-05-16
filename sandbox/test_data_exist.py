"""检查数据是否存在"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.unified_data_interface import get_unified_data_interface

interface = get_unified_data_interface()

# 列出所有股票
symbols = interface.storage.list_symbols("daily")
print(f"ArcticDB 中共有 {len(symbols)} 只股票")
if symbols:
    print(f"前5只: {symbols[:5]}")
    
    # 检查第一只股票的数据
    df = interface.get_stock_data(symbols[0], "2020-01-01", "2026-12-31", "daily")
    print(f"\n{symbols[0]}: {len(df)} 条记录")
    if not df.empty:
        print(f"日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
        print(f"\n前3行:")
        print(df.head(3))
