"""
测试数据流全流程: Tushare API → Polars DataFrame → Arrow Table → ArcticDB

项目规则数据流:
Tushare API → Polars DataFrame → Arrow Table → ArcticDB._nvs.write()
                                                   ↓
                                  内部自动持久化为 Parquet 文件
                                                   ↓
ArcticDB 读取 → Arrow 格式 → Polars DataFrame → 内存字典缓存
                                                   ↓
                                      回测引擎（零拷贝查询）
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

# 设置日志级别
logger.remove()
logger.add(sys.stderr, level="INFO")


def test_step_1_tushare_api():
    """
    【环节 1】测试 Tushare API 获取数据
    
    验证:
    - 能成功连接到 Tushare API
    - 能获取日线数据
    - 返回的是 pandas DataFrame
    """
    logger.info("\n" + "=" * 70)
    logger.info("【环节 1】Tushare API 获取数据")
    logger.info("=" * 70)
    
    try:
        import tushare as ts
        from config.config import Config
        
        # 设置 token
        ts.set_token(Config.TUSHARE_TOKEN)
        pro = ts.pro_api()
        
        # 获取最近一个交易日的数据
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        logger.info(f"获取日期: {yesterday}")
        
        # 获取日线数据
        df_daily = pro.daily(trade_date=yesterday)
        
        if df_daily is None or df_daily.empty:
            logger.error("❌ Tushare API 返回空数据")
            return None
        
        logger.info(f"✅ Tushare API 成功返回数据")
        logger.info(f"   类型: {type(df_daily)}")
        logger.info(f"   行数: {len(df_daily)}")
        logger.info(f"   列数: {len(df_daily.columns)}")
        logger.info(f"   列名: {list(df_daily.columns)[:10]}...")
        
        return df_daily
        
    except Exception as e:
        logger.error(f"❌ Tushare API 测试失败: {e}")
        return None


def test_step_2_pandas_to_polars(df_pandas: pd.DataFrame):
    """
    【环节 2】测试 Pandas DataFrame → Polars DataFrame 转换
    
    验证:
    - 能成功将 pandas DataFrame 转换为 Polars DataFrame
    - 数据完整性保持
    """
    logger.info("\n" + "=" * 70)
    logger.info("【环节 2】Pandas DataFrame → Polars DataFrame 转换")
    logger.info("=" * 70)
    
    try:
        # 添加时间戳列
        df_pandas = df_pandas.copy()
        df_pandas['trade_date'] = pd.to_datetime(df_pandas['trade_date'], format='%Y%m%d')
        
        # Pandas → Polars
        df_polars = pl.from_pandas(df_pandas)
        
        logger.info(f"✅ Pandas → Polars 转换成功")
        logger.info(f"   Pandas 类型: {type(df_pandas)}")
        logger.info(f"   Polars 类型: {type(df_polars)}")
        logger.info(f"   行数: {len(df_polars)}")
        logger.info(f"   列数: {len(df_polars.columns)}")
        logger.info(f"   列名: {df_polars.columns[:10]}...")
        
        # 验证数据完整性
        assert len(df_polars) == len(df_pandas), "行数不匹配"
        assert len(df_polars.columns) == len(df_pandas.columns), "列数不匹配"
        
        logger.info("✅ 数据完整性验证通过")
        
        return df_polars
        
    except Exception as e:
        logger.error(f"❌ Polars 转换测试失败: {e}")
        return None


def test_step_3_polars_to_arrow(df_polars: pl.DataFrame):
    """
    【环节 3】测试 Polars DataFrame → Arrow Table 转换
    
    验证:
    - 能成功将 Polars DataFrame 转换为 Arrow Table
    - Arrow Table 格式正确
    """
    logger.info("\n" + "=" * 70)
    logger.info("【环节 3】Polars DataFrame → Arrow Table 转换")
    logger.info("=" * 70)
    
    try:
        # Polars → Arrow
        arrow_table = df_polars.to_arrow()
        
        logger.info(f"✅ Polars → Arrow 转换成功")
        logger.info(f"   Polars 类型: {type(df_polars)}")
        logger.info(f"   Arrow 类型: {type(arrow_table)}")
        logger.info(f"   Arrow 行数: {arrow_table.num_rows}")
        logger.info(f"   Arrow 列数: {arrow_table.num_columns}")
        logger.info(f"   Arrow 列名: {[arrow_table.schema[i].name for i in range(min(5, arrow_table.num_columns))]}...")
        
        # 验证 Arrow Table 格式
        assert isinstance(arrow_table, pa.Table), "不是 Arrow Table 类型"
        assert arrow_table.num_rows == len(df_polars), "行数不匹配"
        assert arrow_table.num_columns == len(df_polars.columns), "列数不匹配"
        
        logger.info("✅ Arrow Table 格式验证通过")
        
        return arrow_table
        
    except Exception as e:
        logger.error(f"❌ Arrow 转换测试失败: {e}")
        return None


def test_step_4_arrow_to_arcticdb(arrow_table: pa.Table, test_symbol: str = "TEST0001"):
    """
    【环节 4】测试 Arrow Table → ArcticDB 写入
    
    验证:
    - 能成功将 Arrow Table 写入 ArcticDB
    - 能从 ArcticDB 读取数据
    - 数据完整性保持
    """
    logger.info("\n" + "=" * 70)
    logger.info("【环节 4】Arrow Table → ArcticDB 写入")
    logger.info("=" * 70)
    
    try:
        from data_svc.storage import get_arcticdb_manager
        
        # 获取 ArcticDB 管理器
        manager = get_arcticdb_manager()
        
        # Arrow Table → Pandas DataFrame (ArcticDB 需要 pandas)
        df_pandas = arrow_table.to_pandas()
        
        # 设置时间索引
        if 'trade_date' in df_pandas.columns:
            df_pandas.set_index('trade_date', inplace=True)
        
        logger.info(f"准备写入 ArcticDB:")
        logger.info(f"   Symbol: {test_symbol}")
        logger.info(f"   行数: {len(df_pandas)}")
        logger.info(f"   列数: {len(df_pandas.columns)}")
        
        # 写入 ArcticDB
        version = manager.write_daily_data(
            library="test",
            symbol=test_symbol,
            df=df_pandas,
            metadata={
                "test": True,
                "source": "pipeline_test"
            },
            append=False
        )
        
        logger.info(f"✅ ArcticDB 写入成功")
        logger.info(f"   版本: {version}")
        
        # 验证读取
        df_read = manager.read_data("test", test_symbol)
        
        logger.info(f"✅ ArcticDB 读取验证成功")
        logger.info(f"   读取行数: {len(df_read)}")
        logger.info(f"   读取列数: {len(df_read.columns)}")
        
        assert len(df_read) == len(df_pandas), "读取行数不匹配"
        
        logger.info("✅ 数据完整性验证通过")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ArcticDB 写入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_step_5_arcticdb_to_polars(test_symbol: str = "TEST0001"):
    """
    【环节 5】测试 ArcticDB → Polars DataFrame 读取
    
    验证:
    - 能从 ArcticDB 读取数据
    - 能转换为 Polars DataFrame
    - 数据完整性保持
    """
    logger.info("\n" + "=" * 70)
    logger.info("【环节 5】ArcticDB → Polars DataFrame 读取")
    logger.info("=" * 70)
    
    try:
        from data_svc.storage import get_arcticdb_manager
        
        # 获取 ArcticDB 管理器
        manager = get_arcticdb_manager()
        
        # 从 ArcticDB 读取
        df_pandas = manager.read_data("test", test_symbol)
        
        if df_pandas.empty:
            logger.error("❌ 从 ArcticDB 读取的数据为空")
            return None
        
        logger.info(f"从 ArcticDB 读取数据:")
        logger.info(f"   类型: {type(df_pandas)}")
        logger.info(f"   行数: {len(df_pandas)}")
        
        # Pandas → Polars
        df_polars = pl.from_pandas(df_pandas)
        
        logger.info(f"✅ Pandas → Polars 转换成功")
        logger.info(f"   Polars 类型: {type(df_polars)}")
        logger.info(f"   Polars 行数: {len(df_polars)}")
        logger.info(f"   Polars 列数: {len(df_polars.columns)}")
        
        # 显示样本数据
        logger.info(f"样本数据:")
        logger.info(f"{df_polars.head(3)}")
        
        return df_polars
        
    except Exception as e:
        logger.error(f"❌ ArcticDB 读取测试失败: {e}")
        return None


def cleanup_test_data(test_symbol: str = "TEST0001"):
    """清理测试数据"""
    logger.info("\n" + "=" * 70)
    logger.info("清理测试数据")
    logger.info("=" * 70)
    
    try:
        from data_svc.storage import get_arcticdb_manager
        manager = get_arcticdb_manager()
        
        lib = manager._get_or_create_library("test")
        try:
            lib.delete(test_symbol)
            logger.info(f"✅ 已删除测试 symbol: {test_symbol}")
        except Exception as e:
            logger.warning(f"删除测试数据失败: {e}")
            
    except Exception as e:
        logger.warning(f"清理测试数据失败: {e}")


def run_full_pipeline_test():
    """运行全流程测试"""
    logger.info("\n" + "=" * 70)
    logger.info("开始全流程数据流测试")
    logger.info("数据流: Tushare API → Polars DataFrame → Arrow Table → ArcticDB")
    logger.info("=" * 70)
    
    test_symbol = "TEST0001"
    results = {}
    
    # 环节 1: Tushare API
    df_pandas = test_step_1_tushare_api()
    results['tushare'] = df_pandas is not None
    
    if df_pandas is None:
        logger.error("❌ 环节 1 失败，终止测试")
        return results
    
    # 环节 2: Pandas → Polars
    df_polars = test_step_2_pandas_to_polars(df_pandas)
    results['polars'] = df_polars is not None
    
    if df_polars is None:
        logger.error("❌ 环节 2 失败，终止测试")
        return results
    
    # 环节 3: Polars → Arrow
    arrow_table = test_step_3_polars_to_arrow(df_polars)
    results['arrow'] = arrow_table is not None
    
    if arrow_table is None:
        logger.error("❌ 环节 3 失败，终止测试")
        return results
    
    # 环节 4: Arrow → ArcticDB
    write_success = test_step_4_arrow_to_arcticdb(arrow_table, test_symbol)
    results['arcticdb_write'] = write_success
    
    if not write_success:
        logger.error("❌ 环节 4 失败，终止测试")
        return results
    
    # 环节 5: ArcticDB → Polars
    df_polars_read = test_step_5_arcticdb_to_polars(test_symbol)
    results['arcticdb_read'] = df_polars_read is not None
    
    # 清理测试数据
    cleanup_test_data(test_symbol)
    
    # 打印测试总结
    logger.info("\n" + "=" * 70)
    logger.info("测试总结")
    logger.info("=" * 70)
    
    all_passed = all(results.values())
    
    for step, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"{step}: {status}")
    
    if all_passed:
        logger.info("\n🎉 所有测试通过！数据流完整。")
    else:
        logger.info("\n⚠️ 部分测试失败，请检查日志。")
    
    return results


if __name__ == "__main__":
    run_full_pipeline_test()
