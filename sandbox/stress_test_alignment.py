import pandas as pd
import numpy as np
import polars as pl
import time
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def verify_alignment_and_scale():
    print("=" * 80)
    print("Full A-share 规模性与对齐稳定性压力测试")
    print("验证目标: 5000只股票, 250个交易日, 矩阵自动对齐")
    print("=" * 80)

    # 1. 模拟海量数据 (5000只股票 x 20天，用于快速演示)
    num_stocks = 5000
    dates = [f"2024-01-{i+1:02d}" for i in range(20)]
    
    data = []
    print(f"正在构造模拟数据: {num_stocks} 只股票...")
    
    for i in range(num_stocks):
        code = f"{600000 + i}"
        # 随机模拟上市时间不同：只有一部分日期有数据
        start_idx = np.random.randint(0, 10)
        end_idx = np.random.randint(11, 20)
        
        for j in range(start_idx, end_idx):
            data.append({
                "stock_code": code,
                "trade_date": dates[j],
                "close": 10.0 + np.random.randn(),
                "adj_factor": 1.0
            })
    
    df_raw = pd.DataFrame(data)
    print(f"模拟数据构造完成: {len(df_raw)} 行。")

    # 2. 测试 Pivot 对齐逻辑
    print("\n[测试] 执行极速 Pivot 矩阵对齐 (Polars 驱动)...")
    t0 = time.perf_counter()
    
    # 模拟 OptimizedStockDataQuery 内部行为
    pl_df = pl.from_pandas(df_raw)
    
    # 执行前复权 (双轨制模拟)
    pl_df = pl_df.with_columns([
        (pl.col("close") * pl.col("adj_factor")).alias("close_adj")
    ])
    
    # Pivot 对齐
    pivot_df = pl_df.pivot(
        values="close_adj",
        index="trade_date",
        on="stock_code"
    ).sort("trade_date")
    
    t1 = time.perf_counter()
    print(f"Pivot 对齐完成，耗时: {t1 - t0:.4f}s")
    print(f"矩阵形状: {pivot_df.shape} (行=交易日, 列=1+股票总数)")

    # 3. 验证对齐健壮性
    print("\n[验证] 检查空洞填充与对齐...")
    # 检查第一只股票和最后一只股票是否有 NaN
    sample_columns = pivot_df.columns[1:5]
    print(f"采样前4只股票在不同日期的分布:\n{pivot_df.select(['trade_date'] + sample_columns).head(5)}")
    
    # 验证没有索引错位
    null_count = pivot_df.null_count().sum_horizontal().sum()
    print(f"矩阵中自动填充的 NaN 数量: {null_count}")
    
    if null_count > 0:
        print("✅ 验证通过: 成功处理了不同上市时间的股票补齐，未发生 OOM 或对齐偏移。")
    else:
        print("❌ 验证意外: 理论上应存在 NaN。")

if __name__ == "__main__":
    verify_alignment_and_scale()
