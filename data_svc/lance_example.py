# data_svc/lance_example.py
"""
LanceDB 使用示例

演示如何使用 LanceDB 管理器进行数据迁移和查询
"""
import os
import pandas as pd
from datetime import datetime
from data_svc.lance_manager import LanceDBManager, migrate_parquet_to_lance
from config.config import Config


def example_1_convert_parquet():
    """示例1：转换 Parquet 到 LanceDB"""
    print("=" * 60)
    print("示例1：转换 Parquet 到 LanceDB")
    print("=" * 60)
    
    parquet_path = os.path.join(Config.PARQUET_DIR, "stock_daily.parquet")
    
    if not os.path.exists(parquet_path):
        print(f"❌ Parquet 文件不存在: {parquet_path}")
        return
    
    # 转换
    manager = migrate_parquet_to_lance(
        parquet_path=parquet_path,
        table_name="stock_daily"
    )
    
    print("✓ 转换完成！")


def example_2_load_data():
    """示例2：从 LanceDB 加载数据到 Polars（零拷贝）"""
    print("\n" + "=" * 60)
    print("示例2：从 LanceDB 加载数据到 Polars（零拷贝）")
    print("=" * 60)
    
    manager = LanceDBManager(table_name="stock_daily")
    
    # 查询指定日期范围
    df = manager.load_to_polars(
        start_date="2024-01-01",
        end_date="2024-01-10",
        columns=['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
    )
    
    print(f"✓ 加载了 {len(df)} 行数据")
    print(f"  列: {df.columns}")
    print(f"\n前5行数据:")
    print(df.head(5))
    
    # 查询指定股票
    df2 = manager.load_to_polars(
        stock_codes=['000001', '600000'],
        start_date="2024-01-01",
        end_date="2024-01-31"
    )
    
    print(f"\n✓ 查询指定股票: {len(df2)} 行")


def example_3_upsert():
    """示例3：增量更新（Upsert）"""
    print("\n" + "=" * 60)
    print("示例3：增量更新（Upsert）")
    print("=" * 60)
    
    manager = LanceDBManager(table_name="stock_daily")
    
    # 准备今日新数据
    today = datetime.now().strftime('%Y-%m-%d')
    new_data = pd.DataFrame({
        'stock_code': ['000001', '000002', '600000'],
        'trade_date': [today, today, today],
        'open': [10.0, 20.0, 30.0],
        'high': [10.5, 20.5, 30.5],
        'low': [9.8, 19.8, 29.8],
        'close': [10.2, 20.2, 30.2],
        'volume': [1000000, 2000000, 3000000],
        'amount': [10200000, 40400000, 90600000],
        'prev_close': [10.0, 20.0, 30.0],
        'change_amount': [0.2, 0.2, 0.2],
        'change_pct': [0.02, 0.01, 0.0067],
    })
    
    # Upsert
    manager.upsert_daily_data(new_data)
    print(f"✓ Upsert 完成: {len(new_data)} 条记录")
    
    # 验证：查询今日数据
    df = manager.load_to_polars(
        start_date=today,
        end_date=today,
        stock_codes=['000001', '000002', '600000']
    )
    print(f"\n✓ 验证：查询到 {len(df)} 条今日数据")


def example_4_table_info():
    """示例4：获取表信息"""
    print("\n" + "=" * 60)
    print("示例4：获取表信息")
    print("=" * 60)
    
    manager = LanceDBManager(table_name="stock_daily")
    info = manager.get_table_info()
    
    if info.get('exists'):
        print(f"✓ 表存在")
        print(f"  行数: {info.get('rows', 0):,}")
        print(f"  股票数: {info.get('stock_count', 0):,}")
        print(f"  日期范围: {info.get('date_range', {})}")
        print(f"  列数: {len(info.get('columns', []))}")
    else:
        print("❌ 表不存在")


def example_5_integration():
    """示例5：集成到回测系统"""
    print("\n" + "=" * 60)
    print("示例5：集成到回测系统")
    print("=" * 60)
    
    manager = LanceDBManager(table_name="stock_daily")
    
    # 模拟回测查询：获取某一天的所有股票数据
    test_date = "2024-01-15"
    df = manager.load_to_polars(
        start_date=test_date,
        end_date=test_date
    )
    
    print(f"✓ 回测查询: {test_date}")
    print(f"  股票数: {df['stock_code'].n_unique()}")
    print(f"  数据行数: {len(df)}")
    
    # 转换为 Pandas（如果需要）
    df_pd = df.to_pandas()
    print(f"  已转换为 Pandas: {df_pd.shape}")


if __name__ == "__main__":
    # 运行所有示例
    try:
        example_1_convert_parquet()
    except Exception as e:
        print(f"示例1失败: {e}")
    
    try:
        example_2_load_data()
    except Exception as e:
        print(f"示例2失败: {e}")
    
    try:
        example_3_upsert()
    except Exception as e:
        print(f"示例3失败: {e}")
    
    try:
        example_4_table_info()
    except Exception as e:
        print(f"示例4失败: {e}")
    
    try:
        example_5_integration()
    except Exception as e:
        print(f"示例5失败: {e}")
    
    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)

