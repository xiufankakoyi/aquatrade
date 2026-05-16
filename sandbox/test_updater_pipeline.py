"""
测试回测更新 API 的数据流合规性
验证: Tushare API → Polars DataFrame → Arrow Table → ArcticDB

项目规则:
Tushare API → Polars DataFrame → Arrow Table → ArcticDB._nvs.write()
                                                   ↓
                                  内部自动持久化为 Parquet 文件
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import polars as pl
import pyarrow as pa
from loguru import logger
from datetime import datetime, timedelta

# 设置日志
logger.remove()
logger.add(sys.stderr, level="INFO")


def test_arcticdb_updater_pipeline():
    """
    测试 ArcticDBUpdater 的数据流合规性
    
    验证 _write_with_pipeline 方法是否正确实现了:
    pandas → Polars → Arrow → ArcticDB
    """
    logger.info("\n" + "=" * 70)
    logger.info("测试 ArcticDBUpdater 数据流合规性")
    logger.info("=" * 70)
    
    try:
        from data_svc.storage import ArcticDBUpdater, get_arcticdb_manager
        
        # 创建更新器
        updater = ArcticDBUpdater()
        
        # 获取测试数据
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        logger.info(f"获取测试数据: {yesterday}")
        
        df_pandas = updater.fetch_daily_data(yesterday)
        
        if df_pandas is None or df_pandas.empty:
            logger.error("❌ 无法获取测试数据")
            return False
        
        logger.info(f"✅ 获取到测试数据: {len(df_pandas)} 行")
        
        # 获取第一只股票的数据进行测试
        test_symbol = df_pandas['ts_code'].iloc[0]
        df_test = df_pandas[df_pandas['ts_code'] == test_symbol].copy()
        
        logger.info(f"测试股票: {test_symbol}, {len(df_test)} 行")
        
        # 使用 _write_with_pipeline 写入
        success = updater._write_with_pipeline(
            library="test_updater",
            symbol=test_symbol,
            df_pandas=df_test,
            metadata={"test": True, "date": yesterday}
        )
        
        if not success:
            logger.error("❌ _write_with_pipeline 写入失败")
            return False
        
        logger.info("✅ _write_with_pipeline 写入成功")
        
        # 验证读取
        manager = get_arcticdb_manager()
        df_read = manager.read_data("test_updater", test_symbol)
        
        if df_read.empty:
            logger.error("❌ 读取验证失败: 数据为空")
            return False
        
        logger.info(f"✅ 读取验证成功: {len(df_read)} 行")
        
        # 清理测试数据
        try:
            lib = manager._get_or_create_library("test_updater")
            lib.delete(test_symbol)
            logger.info("✅ 测试数据已清理")
        except Exception as e:
            logger.warning(f"清理测试数据失败: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pipeline_steps():
    """
    详细测试每个转换环节
    """
    logger.info("\n" + "=" * 70)
    logger.info("详细测试数据流各环节")
    logger.info("=" * 70)
    
    try:
        from data_svc.storage import ArcticDBUpdater
        
        updater = ArcticDBUpdater()
        
        # 获取测试数据
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        df_pandas = updater.fetch_daily_data(yesterday)
        
        if df_pandas is None or df_pandas.empty:
            logger.error("❌ 无法获取测试数据")
            return False
        
        # 取第一只股票
        test_symbol = df_pandas['ts_code'].iloc[0]
        df_test = df_pandas[df_pandas['ts_code'] == test_symbol].copy()
        
        logger.info(f"\n原始数据 (pandas):")
        logger.info(f"   类型: {type(df_test)}")
        logger.info(f"   形状: {df_test.shape}")
        logger.info(f"   索引: {type(df_test.index)}")
        logger.info(f"   列: {list(df_test.columns)[:5]}...")
        
        # Step 1: pandas → Polars
        # 需要将索引转为列，否则 Polars 会丢失索引信息
        df_reset = df_test.reset_index()
        df_polars = pl.from_pandas(df_reset)
        logger.info(f"\nStep 1: pandas → Polars")
        logger.info(f"   类型: {type(df_polars)}")
        logger.info(f"   形状: ({len(df_polars)}, {len(df_polars.columns)})")
        
        assert isinstance(df_polars, pl.DataFrame), "不是 Polars DataFrame"
        assert len(df_polars) == len(df_test), "行数不匹配"
        logger.info("   ✅ 验证通过")
        
        # Step 2: Polars → Arrow
        arrow_table = df_polars.to_arrow()
        logger.info(f"\nStep 2: Polars → Arrow")
        logger.info(f"   类型: {type(arrow_table)}")
        logger.info(f"   行数: {arrow_table.num_rows}")
        logger.info(f"   列数: {arrow_table.num_columns}")
        
        assert isinstance(arrow_table, pa.Table), "不是 Arrow Table"
        assert arrow_table.num_rows == len(df_polars), "行数不匹配"
        logger.info("   ✅ 验证通过")
        
        # Step 3: Arrow → pandas (ArcticDB 需要)
        df_for_arctic = arrow_table.to_pandas()
        logger.info(f"\nStep 3: Arrow → pandas (ArcticDB 输入)")
        logger.info(f"   类型: {type(df_for_arctic)}")
        logger.info(f"   形状: {df_for_arctic.shape}")
        logger.info(f"   列: {list(df_for_arctic.columns)[:5]}...")
        
        assert isinstance(df_for_arctic, pd.DataFrame), "不是 pandas DataFrame"
        assert len(df_for_arctic) == arrow_table.num_rows, "行数不匹配"
        logger.info("   ✅ 验证通过")
        
        # Step 4: 确保索引是 datetime
        logger.info(f"\nStep 4: 设置 DatetimeIndex")
        logger.info(f"   可用列: {list(df_for_arctic.columns)[:10]}...")
        
        # 检查是否有 trade_date 列（原始数据）或 index 列（重置索引后）
        if 'trade_date' in df_for_arctic.columns:
            df_for_arctic['trade_date'] = pd.to_datetime(df_for_arctic['trade_date'])
            df_for_arctic.set_index('trade_date', inplace=True)
            logger.info("   使用 'trade_date' 列作为索引")
        elif 'index' in df_for_arctic.columns:
            df_for_arctic['index'] = pd.to_datetime(df_for_arctic['index'])
            df_for_arctic.set_index('index', inplace=True)
            df_for_arctic.index.name = 'trade_date'
            logger.info("   使用 'index' 列作为索引")
        else:
            # 如果没有日期列，创建一个
            logger.warning("   未找到日期列，创建默认日期索引")
            df_for_arctic.index = pd.DatetimeIndex([pd.Timestamp.now()])
            df_for_arctic.index.name = 'trade_date'
        
        logger.info(f"   索引类型: {type(df_for_arctic.index)}")
        logger.info("   ✅ 索引设置完成")
        
        # Step 5: 写入 ArcticDB
        from data_svc.storage import get_arcticdb_manager
        manager = get_arcticdb_manager()
        
        version = manager.write_daily_data(
            library="test_steps",
            symbol=test_symbol,
            df=df_for_arctic,
            metadata={"test": True},
            append=False
        )
        
        logger.info(f"\nStep 5: 写入 ArcticDB")
        logger.info(f"   版本: {version}")
        logger.info("   ✅ 写入成功")
        
        # Step 6: 验证读取
        df_read = manager.read_data("test_steps", test_symbol)
        logger.info(f"\nStep 6: 验证读取")
        logger.info(f"   读取行数: {len(df_read)}")
        logger.info(f"   读取列数: {len(df_read.columns)}")
        
        assert len(df_read) == len(df_test), "读取行数不匹配"
        logger.info("   ✅ 验证通过")
        
        # 清理
        try:
            lib = manager._get_or_create_library("test_steps")
            lib.delete(test_symbol)
            logger.info("\n✅ 测试数据已清理")
        except Exception as e:
            logger.warning(f"清理失败: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_sync_flow():
    """
    测试完整的同步流程
    """
    logger.info("\n" + "=" * 70)
    logger.info("测试完整同步流程")
    logger.info("=" * 70)
    
    try:
        from data_svc.storage import ArcticDBUpdater
        
        # 创建更新器
        updater = ArcticDBUpdater()
        
        # 同步最近一个交易日
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        logger.info(f"同步日期: {yesterday}")
        
        # 使用 sync_single_date 测试
        success = updater.sync_single_date(yesterday, library="test_sync")
        
        if not success:
            logger.error("❌ 同步失败")
            return False
        
        logger.info("✅ 同步成功")
        
        # 验证数据
        from data_svc.storage import get_arcticdb_manager
        manager = get_arcticdb_manager()
        
        symbols = manager.list_symbols("test_sync")
        logger.info(f"✅ 验证: 共 {len(symbols)} 只股票的同步数据")
        
        if len(symbols) > 0:
            # 读取第一只股票验证
            df_read = manager.read_data("test_sync", symbols[0])
            logger.info(f"✅ 样本数据: {symbols[0]} 有 {len(df_read)} 行")
        
        # 清理
        try:
            import shutil
            arctic_path = Path(manager._uri.replace("lmdb://", ""))
            test_lib_path = arctic_path / "test_sync"
            if test_lib_path.exists():
                shutil.rmtree(test_lib_path)
                logger.info("✅ 测试库已清理")
        except Exception as e:
            logger.warning(f"清理失败: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "=" * 70)
    logger.info("ArcticDBUpdater 数据流合规性测试套件")
    logger.info("=" * 70)
    
    results = {}
    
    # 测试 1: Pipeline 方法
    results['pipeline_method'] = test_arcticdb_updater_pipeline()
    
    # 测试 2: 详细环节测试
    results['detailed_steps'] = test_pipeline_steps()
    
    # 测试 3: 完整同步流程
    results['full_sync'] = test_full_sync_flow()
    
    # 打印总结
    logger.info("\n" + "=" * 70)
    logger.info("测试总结")
    logger.info("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n🎉 所有测试通过！ArcticDBUpdater 符合项目规则数据流。")
        logger.info("数据流: Tushare API → Polars DataFrame → Arrow Table → ArcticDB")
    else:
        logger.info("\n⚠️ 部分测试失败，请检查日志。")
    
    return results


if __name__ == "__main__":
    run_all_tests()
