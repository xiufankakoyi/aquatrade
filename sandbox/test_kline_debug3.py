"""
调试测试：完整流程调试
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
from server.services.data_initialization_service import DataInitializationService
from server.utils.symbol_utils import normalize_symbol_code

init_service = DataInitializationService()
init_service.ensure_initialized()

symbol_code = "603020"
start_date = "2026-01-11"
end_date = "2026-02-15"

print(f"[测试] 查询 {symbol_code} 从 {start_date} 到 {end_date}")

# 标准化代码
normalized_code = normalize_symbol_code(symbol_code)
print(f"[测试] 标准化后的代码: {normalized_code}")

# 查询数据
history_df = init_service.data_query.get_stock_history(
    normalized_code, start_date, end_date,
    columns=["stock_code", "trade_date", "open", "high", "low", "close", "volume", "adj_factor", "ma5", "ma10", "ma20"]
)

print(f"[测试] 查询结果: {len(history_df)} 行")

# 获取全局最新因子
base_factor = init_service.get_global_latest_factor(normalized_code)
print(f"[测试] 全局最新因子: {base_factor}")

# 计算前复权
history_df['qfq_ratio'] = history_df['adj_factor'] / base_factor
print(f"[测试] qfq_ratio 计算完成")

price_cols = ['open', 'high', 'low', 'close', 'ma5', 'ma10', 'ma20']
for col in price_cols:
    if col in history_df.columns:
        print(f"[测试] 处理列 {col}...")
        history_df[col] = history_df[col] * history_df['qfq_ratio']

print(f"[测试] 前复权计算完成")

# 格式化输出
print(f"[测试] 格式化输出数据...")
records = []
for idx, row in history_df.iterrows():
    print(f"[测试] 处理第 {idx} 行...")
    try:
        # 安全地获取数值，处理 None 和 NaN
        def safe_float(val, decimals=2):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            try:
                return float(f"{val:.{decimals}f}")
            except (TypeError, ValueError) as e:
                print(f"[测试] safe_float 错误: val={val}, type={type(val)}, error={e}")
                return None

        record = {
            "date": row['trade_date'],
            "open": safe_float(row.get('open')),
            "high": safe_float(row.get('high')),
            "low": safe_float(row.get('low')),
            "close": safe_float(row.get('close')),
            "volume": safe_float(row.get('volume'), decimals=0),
            "ma5": safe_float(row.get('ma5')),
            "ma10": safe_float(row.get('ma10')),
            "ma20": safe_float(row.get('ma20'))
        }
        print(f"[测试] 记录: {record}")
        if record['open'] is not None and record['close'] is not None:
            records.append(record)
    except Exception as e:
        print(f"[测试] 处理第 {idx} 行时出错: {e}")
        import traceback
        traceback.print_exc()

print(f"[测试] 返回 {len(records)} 条记录")
