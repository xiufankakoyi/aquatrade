"""
检查数据库数据完整性 V2 - 检查所有数据源
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def check_parquet_files():
    """检查所有 parquet 文件"""
    print("=" * 70)
    print("检查 Parquet 数据文件")
    print("=" * 70)
    
    parquet_dir = Path("data/parquet_data")
    if not parquet_dir.exists():
        print(f"❌ 目录不存在: {parquet_dir}")
        return
    
    # 核心数据文件
    core_files = [
        "stock_daily.parquet",
        "stock_daily_with_indicators.parquet", 
        "base_daily_hot.parquet",
        "base_daily_archive.parquet"
    ]
    
    results = []
    
    for filename in core_files:
        filepath = parquet_dir / filename
        if not filepath.exists():
            print(f"\n❌ {filename}: 文件不存在")
            continue
        
        try:
            df = pd.read_parquet(filepath)
            
            # 查找日期列
            date_col = None
            for col in ['trade_date', 'date', 'datetime', 'trade_date_basic']:
                if col in df.columns:
                    date_col = col
                    break
            
            if date_col:
                # 转换日期格式
                if df[date_col].dtype == 'object':
                    try:
                        df[date_col] = pd.to_datetime(df[date_col])
                    except:
                        pass
                
                latest = df[date_col].max()
                earliest = df[date_col].min()
                count = len(df)
                
                # 获取唯一日期数
                unique_dates = df[date_col].nunique()
                
                print(f"\n📊 {filename}:")
                print(f"   记录数: {count:,}")
                print(f"   唯一日期: {unique_dates}")
                print(f"   最早: {earliest}")
                print(f"   最新: {latest}")
                
                results.append({
                    'file': filename,
                    'latest': str(latest),
                    'earliest': str(earliest),
                    'count': count
                })
            else:
                print(f"\n⚠️ {filename}: 未找到日期列")
                print(f"   可用列: {list(df.columns)}")
                
        except Exception as e:
            print(f"\n❌ {filename}: 读取失败 - {e}")
    
    return results


def check_arcticdb_detailed():
    """详细检查 ArcticDB"""
    print("\n" + "=" * 70)
    print("检查 ArcticDB 数据")
    print("=" * 70)
    
    try:
        from data_svc.storage.arcticdb_manager import ArcticDBManager
        
        arctic = ArcticDBManager()
        
        # 检查 daily 库
        try:
            lib = arctic._connect().get_library("daily")
            symbols = lib.list_symbols()
            print(f"\n📁 daily 库:")
            print(f"   股票数量: {len(symbols):,}")
            
            if symbols:
                # 检查不同股票的最新日期
                sample_dates = {}
                for symbol in symbols[:20]:  # 检查前20只
                    try:
                        data = lib.read(symbol)
                        if data and hasattr(data, 'data') and len(data.data) > 0:
                            df = data.data
                            # 查找日期列
                            date_col = None
                            for col in ['trade_date', 'date', 'index']:
                                if col in df.columns:
                                    date_col = col
                                    break
                            
                            if date_col and date_col in df.columns:
                                last_date = df[date_col].iloc[-1]
                            else:
                                last_date = df.index[-1] if hasattr(df, 'index') else None
                            
                            if last_date is not None:
                                date_str = str(last_date)[:10]
                                if date_str not in sample_dates:
                                    sample_dates[date_str] = 0
                                sample_dates[date_str] += 1
                    except:
                        pass
                
                if sample_dates:
                    print(f"\n   样本股票最新日期分布:")
                    for date, count in sorted(sample_dates.items(), reverse=True)[:5]:
                        print(f"      {date}: {count} 只股票")
                    
                    # 返回最新的日期
                    latest_date = max(sample_dates.keys())
                    return latest_date
                    
        except Exception as e:
            print(f"   读取失败: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"   检查失败: {e}")
    
    return None


def check_polars_loader():
    """使用 PolarsLoader 检查"""
    print("\n" + "=" * 70)
    print("使用 PolarsLoader 检查")
    print("=" * 70)
    
    try:
        from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
        
        loader = get_polars_loader_v5()
        
        # 获取交易日历
        dates = loader.get_trading_dates("2020-01-01", "2026-02-16")
        print(f"\n📅 交易日历范围: {dates[0]} ~ {dates[-1]}")
        print(f"   总交易日数: {len(dates)}")
        
        # 尝试加载最近的数据
        try:
            data = loader.load_period_to_matrix("2024-01-01", "2024-12-31", ['close'])
            if data:
                print(f"\n✅ 2024年数据加载成功:")
                print(f"   矩阵形状: {data['T']} x {data['N']}")
                print(f"   日期范围: {data['trading_dates'][0]} ~ {data['trading_dates'][-1]}")
        except Exception as e:
            print(f"\n❌ 2024年数据加载失败: {e}")
        
        # 尝试加载2025年数据
        try:
            data = loader.load_period_to_matrix("2025-01-01", "2025-12-31", ['close'])
            if data:
                print(f"\n✅ 2025年数据加载成功:")
                print(f"   矩阵形状: {data['T']} x {data['N']}")
                print(f"   日期范围: {data['trading_dates'][0]} ~ {data['trading_dates'][-1]}")
        except Exception as e:
            print(f"\n❌ 2025年数据加载失败: {e}")
            
    except Exception as e:
        print(f"   检查失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("数据库数据完整性检查 V2")
    print("=" * 70)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查 Parquet
    parquet_results = check_parquet_files()
    
    # 检查 ArcticDB
    arctic_latest = check_arcticdb_detailed()
    
    # 使用 PolarsLoader 检查
    check_polars_loader()
    
    # 汇总
    print("\n" + "=" * 70)
    print("数据汇总")
    print("=" * 70)
    
    if parquet_results:
        print("\n📊 Parquet 文件:")
        for r in parquet_results:
            print(f"   {r['file']}: {r['earliest']} ~ {r['latest']}")
    
    if arctic_latest:
        print(f"\n📁 ArcticDB: 最新 {arctic_latest}")
    
    print("\n" + "=" * 70)
    print("检查完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
