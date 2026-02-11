"""
数据拆分与迁移脚本
==================
将 stock_daily_with_indicators.parquet 拆分为：
1. 冷数据 (Parquet): 2020年之前的历史数据
2. 热数据 (QuestDB): 2020年至今的数据，按因子簇拆分

用法:
    python scripts/migrate_to_questdb.py
"""

import polars as pl
import os
from datetime import datetime
from pathlib import Path

# ============== 配置 ==============
SOURCE_FILE = r"d:\aquatrade\data\parquet_data\stock_daily_with_indicators.parquet"
OUTPUT_DIR = r"d:\aquatrade\data\parquet_data"
HOT_DATA_CUTOFF = "2020-01-01"  # 热数据起始日期
# ==================================


def split_data():
    """
    步骤 1: 将数据按时间拆分为冷热两部分
    """
    print("=" * 60)
    print("📊 数据拆分与迁移工具")
    print("=" * 60)
    
    if not os.path.exists(SOURCE_FILE):
        print(f"❌ 源文件不存在: {SOURCE_FILE}")
        return None, None
    
    print(f"📁 读取源文件: {SOURCE_FILE}")
    df = pl.read_parquet(SOURCE_FILE)
    print(f"   总行数: {len(df):,}")
    
    # 确保 trade_date 是字符串格式用于比较
    if df["trade_date"].dtype != pl.Utf8:
        df = df.with_columns(pl.col("trade_date").cast(pl.Utf8))
    
    # 拆分冷热数据
    print(f"\n🔀 按 {HOT_DATA_CUTOFF} 拆分冷热数据...")
    
    cold_df = df.filter(pl.col("trade_date") < HOT_DATA_CUTOFF)
    hot_df = df.filter(pl.col("trade_date") >= HOT_DATA_CUTOFF)
    
    print(f"   冷数据 (< {HOT_DATA_CUTOFF}): {len(cold_df):,} 行")
    print(f"   热数据 (>= {HOT_DATA_CUTOFF}): {len(hot_df):,} 行")
    
    return cold_df, hot_df


def export_cold_parquet(cold_df: pl.DataFrame):
    """
    步骤 2: 导出冷数据到 Parquet 文件
    """
    if cold_df is None or len(cold_df) == 0:
        print("⚠️ 无冷数据需要导出")
        return
    
    print("\n💾 导出冷数据到 Parquet...")
    
    # 基础行情冷数据
    base_cols = ["stock_code", "trade_date", "open", "high", "low", "close", 
                 "volume", "amount", "adj_factor", "prev_close"]
    base_cold = cold_df.select([c for c in base_cols if c in cold_df.columns])
    base_path = os.path.join(OUTPUT_DIR, "base_daily_archive.parquet")
    base_cold.write_parquet(base_path)
    print(f"   ✅ {base_path}")
    
    # 动量因子冷数据
    momentum_cols = ["stock_code", "trade_date", "rsi_14", "kdj_k", "kdj_d", "kdj_j",
                     "macd_dif", "macd_dea", "macd_histogram", "atr_14",
                     "ma5", "ma10", "ma20", "ma60", "ma120", "ma250",
                     "boll_upper", "boll_mid", "boll_lower", "bias_5", "bias_10", "bias_20"]
    momentum_cold = cold_df.select([c for c in momentum_cols if c in cold_df.columns])
    momentum_path = os.path.join(OUTPUT_DIR, "factors_momentum_archive.parquet")
    momentum_cold.write_parquet(momentum_path)
    print(f"   ✅ {momentum_path}")
    
    # 估值因子冷数据
    valuation_cols = ["stock_code", "trade_date", "pe", "pe_ttm", "pb", "ps", "ps_ttm",
                      "total_mv", "float_mv", "turnover_rate", "turnover_free", 
                      "volume_ratio", "dividend_yield"]
    valuation_cold = cold_df.select([c for c in valuation_cols if c in cold_df.columns])
    valuation_path = os.path.join(OUTPUT_DIR, "factors_valuation_archive.parquet")
    valuation_cold.write_parquet(valuation_path)
    print(f"   ✅ {valuation_path}")


def export_hot_parquet(hot_df: pl.DataFrame):
    """
    步骤 3: 导出热数据到独立 Parquet 文件 (用于后续导入 QuestDB)
    """
    if hot_df is None or len(hot_df) == 0:
        print("⚠️ 无热数据需要导出")
        return
    
    print("\n💾 导出热数据到 Parquet (临时文件，用于 QuestDB 导入)...")
    
    # 基础行情
    base_cols = ["stock_code", "trade_date", "open", "high", "low", "close", 
                 "volume", "amount", "adj_factor", "prev_close"]
    base_hot = hot_df.select([c for c in base_cols if c in hot_df.columns])
    base_path = os.path.join(OUTPUT_DIR, "base_daily_hot.parquet")
    base_hot.write_parquet(base_path)
    print(f"   ✅ {base_path} ({len(base_hot):,} 行)")
    
    # 动量因子
    momentum_cols = ["stock_code", "trade_date", "rsi_14", "kdj_k", "kdj_d", "kdj_j",
                     "macd_dif", "macd_dea", "macd_histogram", "atr_14",
                     "ma5", "ma10", "ma20", "ma60", "ma120", "ma250",
                     "boll_upper", "boll_mid", "boll_lower", "bias_5", "bias_10", "bias_20"]
    momentum_hot = hot_df.select([c for c in momentum_cols if c in hot_df.columns])
    momentum_path = os.path.join(OUTPUT_DIR, "factors_momentum_hot.parquet")
    momentum_hot.write_parquet(momentum_path)
    print(f"   ✅ {momentum_path} ({len(momentum_hot):,} 行)")
    
    # 估值因子
    valuation_cols = ["stock_code", "trade_date", "pe", "pe_ttm", "pb", "ps", "ps_ttm",
                      "total_mv", "float_mv", "turnover_rate", "turnover_free", 
                      "volume_ratio", "dividend_yield"]
    valuation_hot = hot_df.select([c for c in valuation_cols if c in hot_df.columns])
    valuation_path = os.path.join(OUTPUT_DIR, "factors_valuation_hot.parquet")
    valuation_hot.write_parquet(valuation_path)
    print(f"   ✅ {valuation_path} ({len(valuation_hot):,} 行)")


def import_to_questdb(hot_df: pl.DataFrame):
    """
    步骤 4: 将热数据导入 QuestDB
    """
    print("\n🚀 导入热数据到 QuestDB...")
    
    try:
        from data_svc.database.questdb_manager import get_questdb_manager
        
        qdb = get_questdb_manager()
        
        # 检查 QuestDB 是否可用
        if not qdb.health_check():
            print("⚠️ QuestDB 服务不可用，跳过导入。")
            print("   请先启动 QuestDB: docker run -p 9000:9000 -p 9009:9009 questdb/questdb")
            return False
        
        # 创建表结构
        print("   创建表结构...")
        qdb.create_tables()
        
        # 分批导入数据
        batch_size = 100000
        total_rows = len(hot_df)
        
        print(f"   导入基础行情数据 ({total_rows:,} 行)...")
        for i in range(0, total_rows, batch_size):
            batch = hot_df.slice(i, batch_size)
            qdb.insert_base_daily(batch)
            progress = min(100, (i + batch_size) * 100 // total_rows)
            print(f"      进度: {progress}%", end="\r")
        print()
        
        print(f"   导入动量因子数据...")
        for i in range(0, total_rows, batch_size):
            batch = hot_df.slice(i, batch_size)
            qdb.insert_factors_momentum(batch)
            progress = min(100, (i + batch_size) * 100 // total_rows)
            print(f"      进度: {progress}%", end="\r")
        print()
        
        print(f"   导入估值因子数据...")
        for i in range(0, total_rows, batch_size):
            batch = hot_df.slice(i, batch_size)
            qdb.insert_factors_valuation(batch)
            progress = min(100, (i + batch_size) * 100 // total_rows)
            print(f"      进度: {progress}%", end="\r")
        print()
        
        qdb.close()
        return True
        
    except Exception as e:
        print(f"❌ QuestDB 导入失败: {e}")
        return False


def main():
    start_time = datetime.now()
    
    # 步骤 1: 拆分数据
    cold_df, hot_df = split_data()
    
    if cold_df is None and hot_df is None:
        return
    
    # 步骤 2: 导出冷数据
    export_cold_parquet(cold_df)
    
    # 步骤 3: 导出热数据 Parquet
    export_hot_parquet(hot_df)
    
    # 步骤 4: 尝试导入 QuestDB (可选)
    questdb_success = import_to_questdb(hot_df)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print(f"✅ 迁移完成! 耗时: {elapsed:.2f} 秒")
    print("=" * 60)
    print("\n📁 生成的文件:")
    print(f"   冷数据 (Parquet):")
    print(f"      - base_daily_archive.parquet")
    print(f"      - factors_momentum_archive.parquet")
    print(f"      - factors_valuation_archive.parquet")
    print(f"   热数据 (Parquet):")
    print(f"      - base_daily_hot.parquet")
    print(f"      - factors_momentum_hot.parquet")
    print(f"      - factors_valuation_hot.parquet")
    
    if questdb_success:
        print(f"   QuestDB 表:")
        print(f"      - base_daily")
        print(f"      - factors_momentum")
        print(f"      - factors_valuation")
    else:
        print("\n💡 提示: 如需导入 QuestDB，请先启动服务后手动运行:")
        print("   python scripts/import_parquet_to_questdb.py")


if __name__ == "__main__":
    main()
