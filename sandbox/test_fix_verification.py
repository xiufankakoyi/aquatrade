import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
import polars as pl

from server.routes.screener_routes import get_latest_trade_date, get_all_trade_dates
from server.routes.screener_data_service import get_screener_service

print("=== 测试修复后的 API ===\n")

# 1. 测试最新日期
print("1. get_latest_trade_date():", get_latest_trade_date())

# 2. 测试 get_data
service = get_screener_service()
service.clear_cache()

latest_date = get_latest_trade_date()
print(f"\n2. 使用日期 {latest_date} 调用 get_data()")

df = service.get_data(date=latest_date, fields=None, conditions=None)
if df is not None and not df.is_empty():
    print(f"   返回行数: {len(df)}")
    print(f"   列: {list(df.columns)}")

    # 检查关键列的 null 情况
    key_cols = ['change_pct', 'volume', 'amount', 'turnover_rate']
    for col in key_cols:
        if col in df.columns:
            null_count = df.filter(pl.col(col).is_null()).height
            print(f"   {col}: null={null_count}/{len(df)}")
        else:
            print(f"   {col}: 不存在")

    # 显示第一条数据
    if not df.is_empty():
        row = df.head(1)
        print(f"\n3. 第一条数据示例:")
        for col in ['stock_code', 'close', 'change_pct', 'volume', 'turnover_rate']:
            if col in row.columns:
                print(f"   {col}: {row[col][0]}")
else:
    print("   数据为空!")