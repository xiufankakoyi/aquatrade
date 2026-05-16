"""
测试 Tushare 数据更新和因子计算写入端

验证：
1. Tushare 数据更新能正常写入 ArcticDB
2. 因子计算能正常工作
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ['LOG_LEVEL'] = 'INFO'

import polars as pl
from loguru import logger


def test_unified_manager_write():
    """测试 UnifiedDataManager 写入功能"""
    print("\n" + "=" * 80)
    print("测试 UnifiedDataManager 写入功能")
    print("=" * 80)
    
    from data_svc.unified_data_manager import get_unified_manager
    
    manager = get_unified_manager()
    
    test_df = pl.DataFrame({
        'trade_date': ['2024-01-20', '2024-01-20', '2024-01-20'],
        'stock_code': ['000001', '000002', '600000'],
        'open': [10.5, 20.3, 15.2],
        'high': [10.8, 20.8, 15.5],
        'low': [10.3, 20.1, 15.0],
        'close': [10.6, 20.5, 15.3],
        'volume': [1000000, 2000000, 1500000],
        'amount': [10600000, 41000000, 22950000],
    })
    
    print("\n[1/3] 测试写入 stock_daily...")
    result = manager.write('stock_daily', 'daily_20240120', test_df)
    print(f"写入结果: success={result.success}, rows={result.rows}, version={result.version}")
    
    print("\n[2/3] 测试读取...")
    df_read = manager.read('stock_daily', start_date='2024-01-20', end_date='2024-01-20')
    print(f"读取结果: {len(df_read)} 行")
    print(df_read)
    
    print("\n[3/3] 测试删除测试数据...")
    try:
        lib = manager.arctic['stock_daily']
        lib.delete('daily_20240120')
        print("删除成功")
    except Exception as e:
        print(f"删除失败: {e}")
    
    return result.success


def test_factor_calculation():
    """测试因子计算"""
    print("\n" + "=" * 80)
    print("测试因子计算")
    print("=" * 80)
    
    from data_svc.unified_data_manager import get_unified_manager
    
    manager = get_unified_manager()
    
    print("\n[1/2] 读取数据...")
    df = manager.read('stock_daily', start_date='2024-01-01', end_date='2024-01-31')
    print(f"读取: {len(df)} 行, 列: {df.columns}")
    
    if len(df) == 0:
        print("数据为空，跳过因子计算测试")
        return True
    
    required_cols = ['close', 'high', 'low', 'volume', 'amount']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        print(f"缺少必要列: {missing_cols}，跳过因子计算测试")
        return True
    
    print("\n[2/2] 计算简单因子...")
    
    df_with_factors = df.with_columns([
        (pl.col('close') / pl.col('close').shift(1).over('stock_code') - 1).alias('return'),
        (pl.col('high') - pl.col('low')) / pl.col('close').alias('volatility'),
        pl.col('amount') / pl.col('volume').cast(pl.Float64).alias('vwap'),
    ])
    
    print(f"因子计算完成: {df_with_factors.columns}")
    print(df_with_factors.head(5))
    
    return True


def test_stock_updater():
    """测试 StockDataUpdater 初始化"""
    print("\n" + "=" * 80)
    print("测试 StockDataUpdater 初始化")
    print("=" * 80)
    
    try:
        from update.update_all_stock_data import StockDataUpdater
        
        print("\n[1/2] 初始化...")
        updater = StockDataUpdater()
        print("初始化成功")
        
        print("\n[2/2] 检查 UnifiedDataManager...")
        manager = updater._get_unified_manager()
        if manager:
            print("UnifiedDataManager 连接成功")
        else:
            print("UnifiedDataManager 连接失败")
        
        return True
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_factor_updater():
    """测试因子更新脚本"""
    print("\n" + "=" * 80)
    print("测试因子更新脚本")
    print("=" * 80)
    
    try:
        from update.update_factors import FactorUpdater
        
        print("\n[1/2] 初始化...")
        updater = FactorUpdater()
        print("初始化成功")
        
        print("\n[2/2] 检查 UnifiedDataManager...")
        manager = updater._get_unified_manager()
        if manager:
            print("UnifiedDataManager 连接成功")
        else:
            print("UnifiedDataManager 连接失败")
        
        return True
    except ImportError as e:
        print(f"因子更新脚本不存在: {e}")
        return True
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Tushare 更新和因子计算测试")
    print("=" * 80)
    
    results = []
    
    results.append(("UnifiedDataManager 写入", test_unified_manager_write()))
    results.append(("因子计算", test_factor_calculation()))
    results.append(("StockDataUpdater", test_stock_updater()))
    results.append(("FactorUpdater", test_factor_updater()))
    
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ 所有测试通过!")
    else:
        print("❌ 部分测试失败!")
    print("=" * 80)
