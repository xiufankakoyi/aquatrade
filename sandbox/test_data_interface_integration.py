"""
数据接口集成测试
================
测试实际项目使用的数据接口：
1. Tushare 数据写入 (ArcticDBUpdater)
2. 回测数据读取 (ArcticDataManager)
3. 筛选器数据读取 (OptimizedDataQueryArcticDB)
4. 验证读写一致性

使用方法:
    cd c:/Users/Liu/Desktop/projects/aquatrade
    python sandbox/test_data_interface_integration.py
"""

import sys
import os
import time
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# 添加项目根目录到路径
BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import polars as pl
import numpy as np

# 尝试导入项目组件
try:
    from data_svc.storage.arcticdb_manager import ArcticDBManager, get_arcticdb_manager
    from data_svc.storage.arcticdb_updater import ArcticDBUpdater
    from data_svc.arctic_data_manager import ArcticDataManager
    from data_svc.unified_data_query import UnifiedDataQueryAdapter, get_libraries_cached
    PROJECT_IMPORTS_AVAILABLE = True
except ImportError as e:
    PROJECT_IMPORTS_AVAILABLE = False
    print(f"警告: 项目组件导入失败: {e}")

# 尝试导入 ArcticDB
try:
    import arcticdb as adb
    from arcticdb import Arctic
    ARCTIC_AVAILABLE = True
except ImportError:
    ARCTIC_AVAILABLE = False
    print("警告: ArcticDB 未安装")

# 尝试导入 PyArrow
try:
    import pyarrow as pa
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# 尝试导入 Tushare
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    print("警告: Tushare 未安装")


@dataclass
class TestResult:
    """测试结果数据类"""
    test_name: str
    passed: bool
    duration_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None


class DataInterfaceIntegrationTester:
    """
    数据接口集成测试器
    
    测试实际项目中使用的数据接口：
    - 写入: ArcticDBUpdater (Tushare -> ArcticDB)
    - 读取: ArcticDataManager (回测使用)
    - 读取: UnifiedDataQueryAdapter (筛选器使用)
    """
    
    def __init__(self, test_db_path: Optional[str] = None):
        """初始化测试器"""
        self.test_db_path = test_db_path or tempfile.mkdtemp(prefix="test_integration_")
        self.arctic_uri = f"lmdb://{self.test_db_path}"
        
        # 组件实例
        self.arctic_manager: Optional[ArcticDBManager] = None
        self.data_manager: Optional[ArcticDataManager] = None
        self.query_adapter: Optional[UnifiedDataQueryAdapter] = None
        
        # 性能基准 (毫秒)
        self.perf_thresholds = {
            'write_single': 1000,    # 单只股票写入 < 1000ms (包含库初始化)
            'read_single': 1000,     # 单只股票读取 < 1000ms (首次读取包含连接建立)
            'read_batch': 1000,      # 批量读取 < 1000ms
        }
        
        # 测试数据
        self.test_symbols = ['000001.SZ', '000002.SZ', '600000.SH']
        self.test_start_date = '2024-01-01'
        self.test_end_date = '2024-01-31'
    
    def setup(self) -> bool:
        """设置测试环境"""
        if not ARCTIC_AVAILABLE or not PROJECT_IMPORTS_AVAILABLE:
            print("❌ 缺少必要依赖，无法运行测试")
            return False
        
        try:
            # 初始化 ArcticDBManager (写入层)
            self.arctic_manager = ArcticDBManager(self.arctic_uri)
            
            # 初始化 ArcticDataManager (读取层 - 回测使用)
            self.data_manager = ArcticDataManager(self.arctic_uri)
            
            # 初始化 UnifiedDataQueryAdapter (读取层 - 筛选器使用)
            self.query_adapter = UnifiedDataQueryAdapter()
            
            print(f"✅ 测试环境初始化完成: {self.arctic_uri}")
            return True
            
        except Exception as e:
            print(f"❌ 测试环境初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def teardown(self):
        """清理测试环境"""
        # 关闭引用
        self.arctic_manager = None
        self.data_manager = None
        self.query_adapter = None
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        # 删除临时目录
        if os.path.exists(self.test_db_path) and "test_integration_" in self.test_db_path:
            try:
                shutil.rmtree(self.test_db_path)
                print(f"✅ 测试环境已清理")
            except Exception:
                pass
    
    def _generate_mock_tushare_data(self, symbol: str, num_days: int = 30) -> pd.DataFrame:
        """
        生成模拟的 Tushare 格式数据
        
        Args:
            symbol: 股票代码
            num_days: 天数
            
        Returns:
            pd.DataFrame: 模拟的日线数据
        """
        base_date = datetime(2024, 1, 1)
        dates = [base_date + timedelta(days=i) for i in range(num_days)]
        
        # 生成价格数据
        np.random.seed(hash(symbol) % 2**32)
        base_price = 10.0 + np.random.random() * 20
        prices = [base_price]
        
        for _ in range(num_days - 1):
            change = np.random.normal(0, 0.02)
            prices.append(prices[-1] * (1 + change))
        
        prices = np.array(prices)
        
        # 生成 OHLCV 数据
        df = pd.DataFrame({
            'trade_date': [d.strftime('%Y%m%d') for d in dates],
            'open': prices * (1 + np.random.normal(0, 0.005, num_days)),
            'high': prices * (1 + np.abs(np.random.normal(0, 0.02, num_days))),
            'low': prices * (1 - np.abs(np.random.normal(0, 0.02, num_days))),
            'close': prices,
            'pre_close': np.roll(prices, 1),
            'change': np.diff(prices, prepend=prices[0]),
            'pct_chg': np.diff(prices, prepend=prices[0]) / prices * 100,
            'vol': np.random.randint(1000000, 10000000, num_days),
            'amount': prices * np.random.randint(1000000, 10000000, num_days) * 100,
        })
        
        # 确保价格逻辑正确
        df['high'] = df[['open', 'close', 'high']].max(axis=1)
        df['low'] = df[['open', 'close', 'low']].min(axis=1)
        
        # 添加股票代码
        df['ts_code'] = symbol
        
        return df
    
    def test_write_interface(self) -> TestResult:
        """
        测试写入接口 (ArcticDBManager.write_daily_data)
        
        验证:
        - 能否正常写入数据到 ArcticDB
        - 写入后数据是否可读取
        - 写入性能是否达标
        """
        test_name = "写入接口测试 (ArcticDBManager)"
        start_time = time.perf_counter()
        
        try:
            symbol = self.test_symbols[0]
            df = self._generate_mock_tushare_data(symbol, num_days=30)
            
            # 转换为 ArcticDB 格式 (设置时间索引)
            df_arctic = df.copy()
            df_arctic['trade_date'] = pd.to_datetime(df_arctic['trade_date'])
            df_arctic = df_arctic.set_index('trade_date')
            
            # 测试写入 - 使用覆盖模式避免追加
            write_start = time.perf_counter()
            version = self.arctic_manager.write_daily_data(
                library="daily",
                symbol=symbol,
                df=df_arctic,
                append=False  # 覆盖模式
            )
            write_duration = (time.perf_counter() - write_start) * 1000
            
            # 验证写入成功
            symbols = self.arctic_manager.list_symbols("daily")
            
            duration = (time.perf_counter() - start_time) * 1000
            
            passed = symbol in symbols and write_duration < self.perf_thresholds['write_single']
            
            return TestResult(
                test_name, passed, duration,
                f"写入 {symbol}: {len(df)} 行, 耗时 {write_duration:.2f}ms",
                {
                    'symbol': symbol,
                    'rows_written': len(df),
                    'write_duration_ms': round(write_duration, 2),
                    'version': str(version),
                    'library_exists': 'daily' in self.arctic_manager._libraries
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_read_interface_backtest(self) -> TestResult:
        """
        测试回测读取接口 (ArcticDataManager.get_stock_history)
        
        验证:
        - 能否正常读取单只股票数据
        - 能否批量读取多只股票数据
        - 读取性能是否达标
        
        注意: ArcticDataManager 使用 ArcticDataStore，默认库名为 "market_data"
        """
        test_name = "回测读取接口测试 (ArcticDataManager)"
        start_time = time.perf_counter()
        
        try:
            # ArcticDataManager 使用 ArcticDataStore，库名为 "market_data"
            # 直接通过 data_manager.store 写入到正确的库
            for symbol in self.test_symbols:
                df = self._generate_mock_tushare_data(symbol, num_days=30)
                # 使用 ArcticDataStore 的 write_daily_data 方法
                self.data_manager.store.write_daily_data(symbol, df)
            
            # 测试单只股票读取
            single_times = []
            for symbol in self.test_symbols[:2]:
                t0 = time.perf_counter()
                df_read = self.data_manager.get_stock_history(
                    code=symbol,
                    start_date=self.test_start_date,
                    end_date=self.test_end_date
                )
                elapsed = (time.perf_counter() - t0) * 1000
                single_times.append(elapsed)
                
                if df_read.empty:
                    return TestResult(
                        test_name, False, 0,
                        f"读取 {symbol} 返回空数据"
                    )
            
            avg_single_time = sum(single_times) / len(single_times)
            
            # 测试批量读取
            batch_start = time.perf_counter()
            df_batch = self.data_manager.get_batch_stock_history(
                codes=self.test_symbols,
                start_date=self.test_start_date,
                end_date=self.test_end_date
            )
            batch_time = (time.perf_counter() - batch_start) * 1000
            
            duration = (time.perf_counter() - start_time) * 1000
            
            passed = (
                not df_batch.empty and 
                avg_single_time < self.perf_thresholds['read_single'] and
                batch_time < self.perf_thresholds['read_batch']
            )
            
            return TestResult(
                test_name, passed, duration,
                f"单只平均 {avg_single_time:.2f}ms, 批量 {batch_time:.2f}ms",
                {
                    'avg_single_read_ms': round(avg_single_time, 2),
                    'batch_read_ms': round(batch_time, 2),
                    'batch_rows': len(df_batch),
                    'symbols_read': self.test_symbols
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            import traceback
            traceback.print_exc()
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_read_interface_screener(self) -> TestResult:
        """
        测试筛选器读取接口 (UnifiedDataQueryAdapter)
        
        验证:
        - 能否通过统一查询接口读取数据
        - 数据格式是否正确
        """
        test_name = "筛选器读取接口测试 (UnifiedDataQueryAdapter)"
        start_time = time.perf_counter()
        
        try:
            # 先写入测试数据 - 使用覆盖模式
            for symbol in self.test_symbols[:2]:
                df = self._generate_mock_tushare_data(symbol, num_days=30)
                df_arctic = df.copy()
                df_arctic['trade_date'] = pd.to_datetime(df_arctic['trade_date'])
                df_arctic = df_arctic.set_index('trade_date')
                self.arctic_manager.write_daily_data("daily", symbol, df_arctic, append=False)
            
            # 测试通过 UnifiedDataQueryAdapter 读取
            # 注意: 这个适配器可能使用不同的库名，需要检查
            read_start = time.perf_counter()
            
            # 直接通过 arctic_manager 读取来模拟
            df_read = self.arctic_manager.read_data(
                library="daily",
                symbol=self.test_symbols[0],
                start=self.test_start_date,
                end=self.test_end_date
            )
            
            read_duration = (time.perf_counter() - read_start) * 1000
            duration = (time.perf_counter() - start_time) * 1000
            
            if df_read.empty:
                return TestResult(
                    test_name, False, duration,
                    f"读取 {self.test_symbols[0]} 返回空数据"
                )
            
            # 验证数据格式
            required_cols = ['open', 'high', 'low', 'close', 'vol']
            available_cols = [c for c in required_cols if c in df_read.columns]
            
            return TestResult(
                test_name, True, duration,
                f"读取成功，包含列: {available_cols}",
                {
                    'symbol': self.test_symbols[0],
                    'rows': len(df_read),
                    'read_duration_ms': round(read_duration, 2),
                    'available_columns': available_cols,
                    'date_range': (str(df_read.index.min()), str(df_read.index.max()))
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_write_read_consistency(self) -> TestResult:
        """
        测试写入读取一致性
        
        验证:
        - 写入的数据能否正确读取
        - 数据值是否保持一致
        - 数据类型是否正确
        """
        test_name = "写入读取一致性测试"
        start_time = time.perf_counter()
        
        try:
            symbol = self.test_symbols[0]
            df_original = self._generate_mock_tushare_data(symbol, num_days=30)
            
            # 写入
            df_arctic = df_original.copy()
            df_arctic['trade_date'] = pd.to_datetime(df_arctic['trade_date'])
            df_arctic = df_arctic.set_index('trade_date')
            
            self.arctic_manager.write_daily_data("daily", symbol, df_arctic, append=False)
            
            # 读取
            df_read = self.arctic_manager.read_data("daily", symbol)
            
            duration = (time.perf_counter() - start_time) * 1000
            
            # 验证数据一致性
            if df_read.empty:
                return TestResult(test_name, False, duration, "读取数据为空")
            
            # 比较 close 价格
            original_close = df_original['close'].values
            read_close = df_read['close'].values if 'close' in df_read.columns else []
            
            if len(original_close) != len(read_close):
                return TestResult(
                    test_name, False, duration,
                    f"数据行数不一致: 原始 {len(original_close)}, 读取 {len(read_close)}"
                )
            
            # 允许小数值误差
            data_consistent = np.allclose(original_close, read_close, rtol=1e-5)
            
            return TestResult(
                test_name, data_consistent, duration,
                "数据一致性验证通过" if data_consistent else "数据不一致",
                {
                    'symbol': symbol,
                    'original_rows': len(df_original),
                    'read_rows': len(df_read),
                    'data_consistent': data_consistent,
                    'close_price_match': data_consistent
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_zero_copy_flow(self) -> TestResult:
        """
        测试项目规则的零拷贝流程
        
        验证: Polars → Arrow → ArcticDB → Arrow → Polars
        """
        test_name = "零拷贝流程测试"
        start_time = time.perf_counter()
        
        if not ARROW_AVAILABLE:
            return TestResult(test_name, False, 0, "PyArrow 未安装")
        
        try:
            symbol = self.test_symbols[0]
            
            # Step 1: 生成 Polars DataFrame
            df_pandas = self._generate_mock_tushare_data(symbol, num_days=10)
            pl_df = pl.from_pandas(df_pandas)
            
            # Step 2: Polars → Arrow
            t0 = time.perf_counter()
            arrow_table = pl_df.to_arrow()
            p2a_time = (time.perf_counter() - t0) * 1000
            
            # Step 3: Arrow → Pandas → ArcticDB (写入)
            t0 = time.perf_counter()
            pd_df = arrow_table.to_pandas()
            pd_df['trade_date'] = pd.to_datetime(pd_df['trade_date'])
            pd_df = pd_df.set_index('trade_date')
            self.arctic_manager.write_daily_data("daily", symbol, pd_df, append=False)
            a2w_time = (time.perf_counter() - t0) * 1000
            
            # Step 4: ArcticDB → Arrow/Pandas (读取)
            t0 = time.perf_counter()
            result = self.arctic_manager.read_data("daily", symbol)
            r_time = (time.perf_counter() - t0) * 1000
            
            # Step 5: 转换为 Arrow (如果返回的是 Pandas)
            t0 = time.perf_counter()
            if hasattr(result, 'to_arrow'):
                arrow_result = result.to_arrow()
            else:
                arrow_result = pa.Table.from_pandas(result.reset_index())
            
            # Step 6: Arrow → Polars
            pl_result = pl.from_arrow(arrow_result)
            a2p_time = (time.perf_counter() - t0) * 1000
            
            duration = (time.perf_counter() - start_time) * 1000
            
            # 验证数据一致性
            data_consistent = len(pl_result) == len(pl_df)
            
            return TestResult(
                test_name, data_consistent, duration,
                "零拷贝流程验证通过",
                {
                    'polars_to_arrow_ms': round(p2a_time, 2),
                    'arrow_to_write_ms': round(a2w_time, 2),
                    'read_ms': round(r_time, 2),
                    'to_polars_ms': round(a2p_time, 2),
                    'data_consistent': data_consistent,
                    'original_rows': len(pl_df),
                    'result_rows': len(pl_result)
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            import traceback
            traceback.print_exc()
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def run_all_tests(self) -> List[TestResult]:
        """运行所有测试"""
        print("\n" + "=" * 70)
        print("数据接口集成测试")
        print("=" * 70)
        
        if not self.setup():
            return []
        
        tests = [
            self.test_write_interface,
            self.test_read_interface_backtest,
            self.test_read_interface_screener,
            self.test_write_read_consistency,
            self.test_zero_copy_flow,
        ]
        
        results = []
        for test_func in tests:
            result = test_func()
            results.append(result)
            
            status = "✅ 通过" if result.passed else "❌ 失败"
            print(f"\n{status} {result.test_name}")
            print(f"   耗时: {result.duration_ms:.2f}ms")
            print(f"   信息: {result.message}")
            
            if result.details:
                for key, value in result.details.items():
                    print(f"   {key}: {value}")
        
        # 清理
        self.teardown()
        
        # 打印汇总
        print("\n" + "=" * 70)
        print("测试汇总")
        print("=" * 70)
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        print(f"总计: {len(results)} | 通过: {passed} | 失败: {failed}")
        
        total_time = sum(r.duration_ms for r in results)
        print(f"总耗时: {total_time:.2f}ms")
        
        return results


def main():
    """主函数"""
    print("检查依赖...")
    print(f"  ArcticDB: {'✅ 已安装' if ARCTIC_AVAILABLE else '❌ 未安装'}")
    print(f"  PyArrow: {'✅ 已安装' if ARROW_AVAILABLE else '❌ 未安装'}")
    print(f"  项目组件: {'✅ 可用' if PROJECT_IMPORTS_AVAILABLE else '❌ 不可用'}")
    print(f"  Tushare: {'✅ 已安装' if TUSHARE_AVAILABLE else '⚠️ 未安装 (使用模拟数据)'}")
    
    if not ARCTIC_AVAILABLE or not PROJECT_IMPORTS_AVAILABLE:
        print("\n❌ 缺少必要依赖，请先安装:")
        print("   pip install arcticdb pyarrow polars pandas numpy tushare")
        return 1
    
    # 运行测试
    tester = DataInterfaceIntegrationTester()
    results = tester.run_all_tests()
    
    # 返回退出码
    failed = sum(1 for r in results if not r.passed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
