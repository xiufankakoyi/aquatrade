import tushare as ts
import pandas as pd

# ==========================================
# 1. 配置 Token
# ==========================================
# 请替换为你的 Tushare Token
token = 'c32d8386d48a5c9e453add46d222912cdf866b3026950cba05c8b90b'
pro = ts.pro_api(token)

test_date = '20241231'

print(f"🚀 开盘啦(kpl_list) 权限生死局 (测试日期: {test_date})...\n")

# ==========================================
# 2. 接口测试
# ==========================================
try:
    print(f"Testing [kpl_list] (请求开盘啦涨停数据)...", end="")
    
    # tag 默认为 '涨停', 也可以试 '炸板'
    df_kpl = pro.kpl_list(trade_date=test_date)
    
    if not df_kpl.empty:
        print(f" ✅ 成功! 获取到 {len(df_kpl)} 条数据")
        print("-" * 50)
        
        # 重点检查字段: lu_desc (原因), theme (题材), status (连板数)
        # 这些是你策略的“灵魂”
        cols_to_show = ['name', 'status', 'theme', 'lu_desc', 'bid_pct_chg']
        
        # 防止字段名变动，先取交集
        valid_cols = [c for c in cols_to_show if c in df_kpl.columns]
        
        print("✨ 核心数据预览 (策略大脑):")
        print(df_kpl[valid_cols].head(3).to_string())
        
        # 检查是否包含竞价数据 (用于弱转强策略)
        if 'bid_pct_chg' in df_kpl.columns:
            print(f"\n💡 包含竞价涨幅数据! 示例: {df_kpl['bid_pct_chg'].iloc[0]}%")
    else:
        print(" ⚠️ 请求成功但无数据 (可能是日期原因或休市)")

except Exception as e:
    print(f" ❌ 失败: {e}")
    # 如果报错提示权限不足，那就是硬性 5000 分限制

print("\n" + "="*30)