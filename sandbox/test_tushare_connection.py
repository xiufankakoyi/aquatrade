# test_tushare_connection.py
"""
测试 Tushare API 连接和权限
"""
import sys
import os

# 添加项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.config import Config
import tushare as ts

print("=" * 70)
print("🔍 Tushare API 连接测试")
print("=" * 70)

# 1. 检查 Token
print(f"\n1. Token 配置:")
token = Config.TUSHARE_TOKEN
if token:
    # 只显示前后几位，中间打码
    masked_token = token[:8] + "..." + token[-8:] if len(token) > 16 else token
    print(f"   ✓ Token 已配置: {masked_token}")
else:
    print("   ❌ Token 未配置")
    sys.exit(1)

# 2. 初始化 API
print(f"\n2. 初始化 Tushare API:")
try:
    pro = ts.pro_api(token)
    print("   ✓ API 初始化成功")
except Exception as e:
    print(f"   ❌ API 初始化失败: {e}")
    sys.exit(1)

# 3. 测试基本接口 (stock_basic)
print(f"\n3. 测试基本接口 (stock_basic):")
try:
    df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name')
    if df is not None and not df.empty:
        print(f"   ✓ 获取成功，共 {len(df)} 只股票")
        print(f"   示例: {df.head(1).to_dict('records')}")
    else:
        print("   ⚠️ 返回数据为空")
except Exception as e:
    print(f"   ❌ 接口调用失败: {e}")

# 4. 测试概念接口 (concept)
print(f"\n4. 测试概念接口 (concept):")
try:
    df = pro.concept(src='ts', fields='code,name')
    if df is not None and not df.empty:
        print(f"   ✓ 获取成功，共 {len(df)} 个概念")
        print(f"   示例: {df.head(3)[['code', 'name']].to_string(index=False)}")
    else:
        print("   ⚠️ 返回数据为空")
except Exception as e:
    print(f"   ❌ 接口调用失败: {e}")

# 5. 测试涨停接口 (limit_list_d)
print(f"\n5. 测试涨停接口 (limit_list_d):")
test_date = '20241231'
try:
    df = pro.limit_list_d(trade_date=test_date, limit_type='U')
    if df is not None and not df.empty:
        print(f"   ✓ 获取成功，{test_date} 共 {len(df)} 只涨停")
        print(f"   示例: {df.head(1)[['ts_code', 'name']].to_dict('records')}")
    else:
        print(f"   ⚠️ {test_date} 无涨停数据（可能是休市或数据未更新）")
except Exception as e:
    print(f"   ❌ 接口调用失败: {e}")

# 6. 测试机构资金接口 (top_inst)
print(f"\n6. 测试机构资金接口 (top_inst):")
try:
    df = pro.top_inst(trade_date=test_date)
    if df is not None and not df.empty:
        print(f"   ✓ 获取成功，{test_date} 共 {len(df)} 条记录")
    else:
        print(f"   ⚠️ {test_date} 无机构资金数据")
except Exception as e:
    print(f"   ❌ 接口调用失败: {e}")
    print(f"   提示: 此接口可能需要更高权限")

print("\n" + "=" * 70)
print("✅ 测试完成")
print("=" * 70)
