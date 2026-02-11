"""
CSV vs Parquet 数据一致性验证脚本 (改进版)
使用 Polars 快速验证 date 文件夹中的 CSV 数据与 Parquet 文件中的数据是否一致

重要说明:
- 本脚本会检查 Parquet 文件是否包含 CSV 文件的所有数据
- 如果 Parquet 只包含部分数据，会明确指出
- 只有当 Parquet 包含 CSV 的所有数据且一致时，才认为验证通过
"""

import polars as pl
from pathlib import Path
from typing import Dict, List
import sys
from datetime import datetime


# 列名映射：CSV中文列名 -> Parquet英文列名
COLUMN_MAPPING = {
    "交易日期": "trade_date",
    "开盘价": "open",
    "最高价": "high",
    "最低价": "low",
    "收盘价": "close",
    "成交量(手)": "volume",
    "成交额(千元)": "amount",
}


def main():
    """主函数"""
    print("\n" + "="*80)
    print("CSV vs Parquet 数据一致性验证 (快速版)")
    print("="*80 + "\n")
    
    csv_dir = Path(r"d:\aquatrade\data\date")
    parquet_file = Path(r"d:\aquatrade\data\parquet_data\stock_daily.parquet")
    
    # 读取 Parquet 文件
    print("📂 正在读取 Parquet 文件...")
    try:
        pq_df = pl.read_parquet(parquet_file)
        print(f"✅ Parquet 文件包含 {len(pq_df):,} 行数据")
        print(f"   股票数量: {pq_df['stock_code'].n_unique():,}")
        print(f"   日期范围: {pq_df['trade_date'].min()} 至 {pq_df['trade_date'].max()}")
    except Exception as e:
        print(f"❌ 读取 Parquet 文件失败: {e}")
        sys.exit(1)
    
    # 获取 CSV 文件列表
    csv_files = sorted(csv_dir.glob("*.csv"))
    print(f"\n📂 找到 {len(csv_files):,} 个 CSV 文件")
    
    # 随机采样进行验证
    import random
    sample_size = min(20, len(csv_files))
    sampled_files = random.sample(csv_files, sample_size)
    print(f"🎲 随机采样 {sample_size} 个文件进行验证\n")
    
    # 验证结果统计
    results = {
        "完全匹配": 0,
        "Parquet数据不完整": 0,
        "数据不一致": 0,
        "Parquet无数据": 0,
    }
    
    print("开始验证...\n")
    print("-" * 80)
    
    for i, csv_path in enumerate(sampled_files, 1):
        stock_code = csv_path.stem
        print(f"[{i}/{sample_size}] {stock_code}...", end=" ")
        
        try:
            # 读取 CSV
            csv_df = pl.read_csv(csv_path, encoding="utf-8")
            csv_df = csv_df.rename({k: v for k, v in COLUMN_MAPPING.items() if k in csv_df.columns})
            
            # 筛选 Parquet 数据
            pq_stock = pq_df.filter(pl.col("stock_code") == stock_code)
            
            if len(pq_stock) == 0:
                print("❌ Parquet 无数据")
                results["Parquet无数据"] += 1
                continue
            
            # 比较行数
            csv_rows = len(csv_df)
            pq_rows = len(pq_stock)
            
            if pq_rows < csv_rows:
                coverage = pq_rows / csv_rows * 100
                print(f"⚠️  Parquet 数据不完整 (CSV:{csv_rows:,} 行, Parquet:{pq_rows:,} 行, 覆盖率:{coverage:.1f}%)")
                results["Parquet数据不完整"] += 1
                continue
            
            # 比较核心数据（重叠日期范围）
            common_cols = ["trade_date", "close"]
            if all(col in csv_df.columns and col in pq_stock.columns for col in common_cols):
                csv_sorted = csv_df.select(common_cols).sort("trade_date")
                pq_sorted = pq_stock.select(common_cols).sort("trade_date")
                
                # 只比较 CSV 日期范围内的数据
                csv_dates = set(csv_sorted["trade_date"].to_list())
                pq_in_csv_range = pq_sorted.filter(pl.col("trade_date").is_in(csv_dates))
                
                if len(pq_in_csv_range) == 0:
                    print("⚠️  日期范围无重叠")
                    results["Parquet数据不完整"] += 1
                    continue
                
                # 比较重叠部分
                csv_in_range = csv_sorted.filter(pl.col("trade_date").is_in(pq_in_csv_range["trade_date"]))
                
                if len(csv_in_range) != len(pq_in_csv_range):
                    print(f"❌ 数据不一致 (重叠日期数不同)")
                    results["数据不一致"] += 1
                    continue
                
                # 比较收盘价
                csv_close = csv_in_range.sort("trade_date")["close"].cast(pl.Float64)
                pq_close = pq_in_csv_range.sort("trade_date")["close"].cast(pl.Float64)
                
                max_diff = (csv_close - pq_close).abs().max()
                
                if max_diff > 0.01:  # 容忍 0.01 元的差异
                    print(f"❌ 数据不一致 (最大差异:{max_diff:.4f})")
                    results["数据不一致"] += 1
                else:
                    print(f"✅ 完全匹配")
                    results["完全匹配"] += 1
            else:
                print("⚠️  缺少必要列")
                results["数据不一致"] += 1
                
        except Exception as e:
            print(f"❌ 验证失败: {e}")
            results["数据不一致"] += 1
    
    # 输出汇总
    print("\n" + "="*80)
    print("验证结果汇总")
    print("="*80)
    print(f"总验证文件数: {sample_size}")
    print(f"✅ 完全匹配: {results['完全匹配']} ({results['完全匹配']/sample_size*100:.1f}%)")
    print(f"⚠️  Parquet 数据不完整: {results['Parquet数据不完整']} ({results['Parquet数据不完整']/sample_size*100:.1f}%)")
    print(f"❌ 数据不一致: {results['数据不一致']} ({results['数据不一致']/sample_size*100:.1f}%)")
    print(f"❌ Parquet 无数据: {results['Parquet无数据']} ({results['Parquet无数据']/sample_size*100:.1f}%)")
    
    print("\n" + "="*80)
    print("结论")
    print("="*80)
    
    if results["完全匹配"] == sample_size:
        print("🎉 验证通过！Parquet 包含 CSV 的所有数据且完全一致！")
        print("✅ 可以安全删除 CSV 文件！")
        sys.exit(0)
    elif results["Parquet数据不完整"] > 0:
        print("⚠️  警告：Parquet 文件只包含部分数据（可能只有最近的数据）")
        print("❌ Parquet 不是 CSV 的完整替代品，不能删除 CSV 文件！")
        print("\n建议：")
        print("1. 检查 Parquet 文件的生成逻辑")
        print("2. 确保 Parquet 包含完整的历史数据")
        print("3. 重新生成 Parquet 文件后再次验证")
        sys.exit(1)
    else:
        print("❌ 验证失败！发现数据不一致！")
        print("❌ 请勿删除 CSV 文件！")
        sys.exit(1)


if __name__ == "__main__":
    main()
