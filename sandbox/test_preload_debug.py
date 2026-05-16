"""
调试预加载流程
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.unified_data_manager import get_unified_manager

manager = get_unified_manager()

print("=" * 70)
print("调试预加载流程")
print("=" * 70)

# 测试读取数据
start_date = '2024-12-31'
end_date = '2025-01-31'

print(f"\n[1] 测试 manager.read()")
print(f"   日期范围: {start_date} ~ {end_date}")

df = manager.read('stock_daily', start_date=start_date, end_date=end_date)

print(f"   数据形状: {df.shape}")
print(f"   列名: {df.columns}")

if not df.is_empty():
    print(f"\n   前3行:")
    print(df.head(3))
    
    # 检查日期范围
    if 'trade_date' in df.columns:
        dates = df['trade_date'].unique().sort()
        print(f"\n   日期范围: {dates[0]} ~ {dates[-1]}")
        print(f"   日期数量: {len(dates)}")
else:
    print(f"\n   ⚠️ 数据为空!")

# 检查库中的 symbols
print(f"\n[2] 检查 stock_daily 库中的 symbols")
lib = manager.arctic['stock_daily']
symbols = lib.list_symbols()
print(f"   Symbols: {symbols}")
