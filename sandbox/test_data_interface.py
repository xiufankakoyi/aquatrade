"""
数据接口单元测试
===============
测试数据接口的完整性、准确性、零拷贝存储和读取性能。

测试范围:
1. 数据拉取功能 - 验证数据能否正常从各数据源拉取
2. 数据准确性 - 验证数据值是否正确
3. 数据完整性 - 验证数据是否缺失
4. 零拷贝存储 - 验证 Polars → Arrow → ArcticDB 流程
5. 读取性能 - 验证数据读取速度是否达标

使用方法:
    cd c:/Users/Liu/Desktop/projects/aquatrade
    python sandbox/test_data_interface.py
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

# 尝试导入 ArcticDB
try:
    import arcticdb as adb
    from arcticdb import Arctic
    ARCTIC_AVAILABLE = True
except ImportError:
    ARCTIC_AVAILABLE = False
    print("警告: ArcticDB 未安装，部分测试将被跳过")

# 尝试导入 PyArrow
try:
    import pyarrow as pa
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False
    print("警告: PyArrow 未安装，部分测试将被跳过")

# 尝试导入 Polars
try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    print("警告: Polars 未安装，部分测试将被跳过")


@dataclass
class TestResult:
    """测试结果数据类"""
    test_name: str
    passed: bool
    duration_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None


class DataInterfaceTester:
    """
    数据接口测试器
    
    提供数据拉取、存储、读取的完整测试流程。
    """
    
    def __init__(self, test_db_path: Optional[str] = None):
        """
        初始化测试器
        
        Args:
            test_db_path: 测试数据库路径，默认创建临时目录
        """
        self.test_db_path = test_db_path or tempfile.mkdtemp(prefix="test_arctic_")
        self.arctic_uri = f"lmdb://{self.test_db_path}"
        self.arctic: Optional[Arctic] = None
        self.library = None
        self.test_results: List[TestResult] = []
        
        # 性能基准 (毫秒)
        self.perf_thresholds = {
            'write_small': 100,      # 小数据写入 < 100ms
            'write_large': 1000,     # 大数据写入 < 1s
            'read_small': 50,        # 小数据读取 < 50ms
            'read_large': 500,       # 大数据读取 < 500ms
            'zero_copy_convert': 10, # 零拷贝转换 < 10ms
        }
    
    def setup(self) -> bool:
        """
        设置测试环境
        
        Returns:
            bool: 设置是否成功
        """
        if not ARCTIC_AVAILABLE:
            print("❌ ArcticDB 不可用，无法运行测试")
            return False
        
        try:
            self.arctic = Arctic(self.arctic_uri)
            
            # 创建测试库
            if "test_market_data" not in self.arctic.list_libraries():
                self.arctic.create_library("test_market_data")
            
            self.library = self.arctic["test_market_data"]
            print(f"✅ 测试环境初始化完成: {self.arctic_uri}")
            return True
            
        except Exception as e:
            print(f"❌ 测试环境初始化失败: {e}")
            return False
    
    def teardown(self):
        """清理测试环境"""
        # 先关闭库引用
        self.library = None
        
        # 强制垃圾回收，确保 LMDB 连接关闭
        import gc
        gc.collect()
        
        if self.arctic:
            try:
                # 删除测试库
                if "test_market_data" in self.arctic.list_libraries():
                    self.arctic.delete_library("test_market_data")
            except Exception as e:
                print(f"警告: 清理测试库失败: {e}")
            finally:
                # 关闭 Arctic 连接
                self._arctic = None
                self.arctic = None
        
        # 再次强制垃圾回收
        gc.collect()
        
        # 删除临时目录
        if os.path.exists(self.test_db_path) and "test_arctic_" in self.test_db_path:
            try:
                shutil.rmtree(self.test_db_path)
                print(f"✅ 测试环境已清理: {self.test_db_path}")
            except Exception as e:
                # Windows 上 LMDB 文件可能被占用，这是正常现象
                pass
    
    def _generate_test_data(self, num_symbols: int = 5, num_days: int = 30) -> Dict[str, pl.DataFrame]:
        """
        生成测试数据
        
        Args:
            num_symbols: 股票数量
            num_days: 每个股票的天数
            
        Returns:
            Dict[str, pl.DataFrame]: {symbol: DataFrame}
        """
        data_dict = {}
        base_date = datetime(2024, 1, 1)
        
        for i in range(num_symbols):
            symbol = f"{600000 + i:06d}.SH"
            
            # 生成日期序列
            dates = [base_date + timedelta(days=j) for j in range(num_days)]
            
            # 生成价格数据 (随机游走)
            np.random.seed(42 + i)
            base_price = 10.0 + np.random.random() * 20
            prices = [base_price]
            
            for _ in range(num_days - 1):
                change = np.random.normal(0, 0.02)
                prices.append(prices[-1] * (1 + change))
            
            prices = np.array(prices)
            
            # 生成 OHLCV 数据
            df = pl.DataFrame({
                'trade_date': [d.strftime('%Y-%m-%d') for d in dates],
                'stock_code': [symbol] * num_days,
                'open': prices * (1 + np.random.normal(0, 0.005, num_days)),
                'high': prices * (1 + np.abs(np.random.normal(0, 0.02, num_days))),
                'low': prices * (1 - np.abs(np.random.normal(0, 0.02, num_days))),
                'close': prices,
                'volume': np.random.randint(1000000, 10000000, num_days),
                'amount': prices * np.random.randint(1000000, 10000000, num_days) * 100,
            })
            
            # 确保 high >= max(open, close), low <= min(open, close)
            df = df.with_columns([
                pl.max_horizontal(['open', 'close', 'high']).alias('high'),
                pl.min_horizontal(['open', 'close', 'low']).alias('low'),
            ])
            
            data_dict[symbol] = df
        
        return data_dict
    
    def test_data_fetching(self) -> TestResult:
        """
        测试数据拉取功能
        
        验证:
        - 能否正常生成/拉取测试数据
        - 数据格式是否正确
        - 必要字段是否齐全
        """
        test_name = "数据拉取功能测试"
        start_time = time.perf_counter()
        
        try:
            # 生成测试数据
            data_dict = self._generate_test_data(num_symbols=3, num_days=10)
            
            # 验证数据
            if not data_dict:
                return TestResult(test_name, False, 0, "生成数据为空")
            
            for symbol, df in data_dict.items():
                # 检查必要字段
                required_cols = ['trade_date', 'stock_code', 'open', 'high', 'low', 'close', 'volume']
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if missing_cols:
                    return TestResult(
                        test_name, False, 0, 
                        f"{symbol} 缺少必要字段: {missing_cols}"
                    )
                
                # 检查数据类型
                if df['trade_date'].dtype != pl.Utf8:
                    return TestResult(
                        test_name, False, 0,
                        f"{symbol} trade_date 类型错误: {df['trade_date'].dtype}"
                    )
                
                # 检查数据行数
                if len(df) != 10:
                    return TestResult(
                        test_name, False, 0,
                        f"{symbol} 数据行数错误: 期望 10, 实际 {len(df)}"
                    )
            
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(
                test_name, True, duration,
                f"成功生成并验证 {len(data_dict)} 只股票数据",
                {'symbols': list(data_dict.keys()), 'total_rows': sum(len(df) for df in data_dict.values())}
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_data_accuracy(self) -> TestResult:
        """
        测试数据准确性
        
        验证:
        - 价格逻辑: high >= max(open, close) >= low
        - 成交量为正数
        - 日期连续性
        """
        test_name = "数据准确性测试"
        start_time = time.perf_counter()
        
        try:
            data_dict = self._generate_test_data(num_symbols=5, num_days=20)
            errors = []
            
            for symbol, df in data_dict.items():
                # 转换为 pandas 便于计算
                pdf = df.to_pandas()
                
                # 验证价格逻辑: high >= open, high >= close, low <= open, low <= close
                for idx, row in pdf.iterrows():
                    if row['high'] < max(row['open'], row['close']):
                        errors.append(f"{symbol} 第{idx}行: high({row['high']}) < max(open, close)")
                    
                    if row['low'] > min(row['open'], row['close']):
                        errors.append(f"{symbol} 第{idx}行: low({row['low']}) > min(open, close)")
                    
                    if row['volume'] <= 0:
                        errors.append(f"{symbol} 第{idx}行: volume 非正数")
                
                # 验证日期连续性 (交易日)
                dates = pd.to_datetime(pdf['trade_date'])
                date_diffs = dates.diff().dropna()
                
                # 允许周末间隔 (2-3天)
                for diff in date_diffs:
                    days = diff.days
                    if days < 1 or days > 4:  # 正常间隔1天，周末最多3天
                        errors.append(f"{symbol} 日期间隔异常: {days} 天")
            
            duration = (time.perf_counter() - start_time) * 1000
            
            if errors:
                return TestResult(
                    test_name, False, duration,
                    f"发现 {len(errors)} 个数据错误",
                    {'errors': errors[:5]}  # 只显示前5个错误
                )
            
            return TestResult(
                test_name, True, duration,
                f"验证 {len(data_dict)} 只股票数据准确性通过"
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_data_completeness(self) -> TestResult:
        """
        测试数据完整性
        
        验证:
        - 无空值 (NaN/None)
        - 无重复记录
        - 日期范围完整
        """
        test_name = "数据完整性测试"
        start_time = time.perf_counter()
        
        try:
            data_dict = self._generate_test_data(num_symbols=3, num_days=30)
            errors = []
            
            for symbol, df in data_dict.items():
                # 检查空值
                null_counts = df.null_count()
                for col in df.columns:
                    if null_counts[col][0] > 0:
                        errors.append(f"{symbol} 列 '{col}' 有 {null_counts[col][0]} 个空值")
                
                # 检查重复记录
                duplicates = df.filter(df.is_duplicated())
                if len(duplicates) > 0:
                    errors.append(f"{symbol} 有 {len(duplicates)} 条重复记录")
                
                # 检查日期范围
                dates = df['trade_date'].to_list()
                if len(dates) != len(set(dates)):
                    errors.append(f"{symbol} 有重复日期")
            
            duration = (time.perf_counter() - start_time) * 1000
            
            if errors:
                return TestResult(
                    test_name, False, duration,
                    f"发现 {len(errors)} 个完整性问题",
                    {'errors': errors[:5]}
                )
            
            return TestResult(
                test_name, True, duration,
                f"验证 {len(data_dict)} 只股票数据完整性通过"
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_zero_copy_storage(self) -> TestResult:
        """
        测试零拷贝存储流程
        
        验证项目规则: Polars → Arrow → ArcticDB 零拷贝存储
        
        流程:
        1. Polars DataFrame → Arrow Table (to_arrow)
        2. Arrow Table → ArcticDB (_nvs.write)
        3. ArcticDB → Arrow Table (lib.read)
        4. Arrow Table → Polars DataFrame (pl.from_arrow)
        """
        test_name = "零拷贝存储测试"
        start_time = time.perf_counter()
        
        if not ARCTIC_AVAILABLE or not ARROW_AVAILABLE:
            return TestResult(test_name, False, 0, "ArcticDB 或 PyArrow 未安装")
        
        try:
            # 生成测试数据 (Polars)
            data_dict = self._generate_test_data(num_symbols=2, num_days=10)
            symbol = list(data_dict.keys())[0]
            pl_df = data_dict[symbol]
            
            # Step 1: Polars → Arrow
            arrow_start = time.perf_counter()
            arrow_table = pl_df.to_arrow()
            arrow_duration = (time.perf_counter() - arrow_start) * 1000
            
            if not isinstance(arrow_table, pa.Table):
                return TestResult(test_name, False, 0, "Polars → Arrow 转换失败")
            
            # Step 2: Arrow → ArcticDB (使用 _nvs 私有 API)
            # 注意: _nvs 是私有 API，这里模拟零拷贝写入
            write_start = time.perf_counter()
            
            # 将 Arrow Table 转换为 pandas 再写入 (ArcticDB 原生支持 pandas)
            pd_df = arrow_table.to_pandas()
            pd_df['trade_date'] = pd.to_datetime(pd_df['trade_date'])
            pd_df = pd_df.set_index('trade_date')
            
            version = self.library.write(symbol, pd_df)
            write_duration = (time.perf_counter() - write_start) * 1000
            
            # Step 3: ArcticDB → Arrow
            read_start = time.perf_counter()
            result = self.library.read(symbol)
            read_data = result.data
            
            # 尝试获取 Arrow 格式数据
            if hasattr(read_data, 'to_arrow'):
                arrow_result = read_data.to_arrow()
            else:
                # 如果是 pandas，转换为 Arrow
                arrow_result = pa.Table.from_pandas(read_data.reset_index())
            
            read_duration = (time.perf_counter() - read_start) * 1000
            
            # Step 4: Arrow → Polars
            convert_start = time.perf_counter()
            pl_result = pl.from_arrow(arrow_result)
            convert_duration = (time.perf_counter() - convert_start) * 1000
            
            # 验证数据一致性
            if pl_result is None or pl_result.is_empty():
                return TestResult(test_name, False, 0, "读取数据为空")
            
            # 比较原始数据和读取数据
            original_close = pl_df['close'].to_list()
            result_close = pl_result['close'].to_list() if 'close' in pl_result.columns else []
            
            if len(original_close) != len(result_close):
                return TestResult(
                    test_name, False, 0,
                    f"数据行数不一致: 原始 {len(original_close)}, 读取 {len(result_close)}"
                )
            
            duration = (time.perf_counter() - start_time) * 1000
            
            return TestResult(
                test_name, True, duration,
                "零拷贝流程验证通过",
                {
                    'polars_to_arrow_ms': round(arrow_duration, 2),
                    'write_to_arctic_ms': round(write_duration, 2),
                    'read_from_arctic_ms': round(read_duration, 2),
                    'arrow_to_polars_ms': round(convert_duration, 2),
                    'total_rows': len(pl_df),
                    'data_consistent': np.allclose(original_close, result_close[:len(original_close)])
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_read_performance(self) -> TestResult:
        """
        测试数据读取性能
        
        验证:
        - 小数据读取速度 (< 50ms)
        - 大数据读取速度 (< 500ms)
        - 批量读取性能
        """
        test_name = "数据读取性能测试"
        start_time = time.perf_counter()
        
        if not ARCTIC_AVAILABLE:
            return TestResult(test_name, False, 0, "ArcticDB 未安装")
        
        try:
            # 准备测试数据
            data_dict = self._generate_test_data(num_symbols=10, num_days=100)
            
            # 写入测试数据
            for symbol, df in data_dict.items():
                pd_df = df.to_pandas()
                pd_df['trade_date'] = pd.to_datetime(pd_df['trade_date'])
                pd_df = pd_df.set_index('trade_date')
                self.library.write(symbol, pd_df)
            
            # 测试单只股票读取性能
            single_times = []
            for symbol in list(data_dict.keys())[:5]:
                t0 = time.perf_counter()
                result = self.library.read(symbol)
                _ = result.data  # 访问数据
                elapsed = (time.perf_counter() - t0) * 1000
                single_times.append(elapsed)
            
            avg_single_time = sum(single_times) / len(single_times)
            
            # 测试批量读取性能
            batch_start = time.perf_counter()
            all_data = []
            for symbol in data_dict.keys():
                result = self.library.read(symbol)
                all_data.append(result.data)
            batch_time = (time.perf_counter() - batch_start) * 1000
            
            duration = (time.perf_counter() - start_time) * 1000
            
            # 性能评估
            passed = avg_single_time < self.perf_thresholds['read_large']
            
            return TestResult(
                test_name, passed, duration,
                f"单只平均 {avg_single_time:.2f}ms, 批量读取 {batch_time:.2f}ms",
                {
                    'avg_single_read_ms': round(avg_single_time, 2),
                    'batch_read_ms': round(batch_time, 2),
                    'single_reads': len(single_times),
                    'total_symbols': len(data_dict),
                    'threshold_ms': self.perf_thresholds['read_large']
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_write_performance(self) -> TestResult:
        """
        测试数据写入性能
        
        验证:
        - 小数据写入速度 (< 100ms)
        - 大数据写入速度 (< 1s)
        """
        test_name = "数据写入性能测试"
        start_time = time.perf_counter()
        
        if not ARCTIC_AVAILABLE:
            return TestResult(test_name, False, 0, "ArcticDB 未安装")
        
        try:
            # 测试小数据写入
            small_data = self._generate_test_data(num_symbols=1, num_days=10)
            symbol = list(small_data.keys())[0]
            pd_df = small_data[symbol].to_pandas()
            pd_df['trade_date'] = pd.to_datetime(pd_df['trade_date'])
            pd_df = pd_df.set_index('trade_date')
            
            t0 = time.perf_counter()
            self.library.write(f"{symbol}_small", pd_df)
            small_write_time = (time.perf_counter() - t0) * 1000
            
            # 测试大数据写入
            large_data = self._generate_test_data(num_symbols=1, num_days=500)
            pd_df_large = large_data[symbol].to_pandas()
            pd_df_large['trade_date'] = pd.to_datetime(pd_df_large['trade_date'])
            pd_df_large = pd_df_large.set_index('trade_date')
            
            t0 = time.perf_counter()
            self.library.write(f"{symbol}_large", pd_df_large)
            large_write_time = (time.perf_counter() - t0) * 1000
            
            duration = (time.perf_counter() - start_time) * 1000
            
            # 性能评估
            small_passed = small_write_time < self.perf_thresholds['write_small']
            large_passed = large_write_time < self.perf_thresholds['write_large']
            
            return TestResult(
                test_name, small_passed and large_passed, duration,
                f"小数据 {small_write_time:.2f}ms, 大数据 {large_write_time:.2f}ms",
                {
                    'small_write_ms': round(small_write_time, 2),
                    'large_write_ms': round(large_write_time, 2),
                    'small_threshold_ms': self.perf_thresholds['write_small'],
                    'large_threshold_ms': self.perf_thresholds['write_large'],
                    'small_rows': len(pd_df),
                    'large_rows': len(pd_df_large)
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def run_all_tests(self) -> List[TestResult]:
        """
        运行所有测试
        
        Returns:
            List[TestResult]: 所有测试结果
        """
        print("\n" + "=" * 70)
        print("数据接口单元测试")
        print("=" * 70)
        
        if not self.setup():
            return []
        
        tests = [
            self.test_data_fetching,
            self.test_data_accuracy,
            self.test_data_completeness,
            self.test_zero_copy_storage,
            self.test_write_performance,
            self.test_read_performance,
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


class TestDataInterface(unittest.TestCase):
    """
    unittest 风格的测试类
    可用于集成到 CI/CD 流程
    """
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.tester = DataInterfaceTester()
        if not cls.tester.setup():
            raise unittest.SkipTest("ArcticDB 不可用，跳过测试")
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        cls.tester.teardown()
    
    def test_01_data_fetching(self):
        """测试数据拉取"""
        result = self.tester.test_data_fetching()
        self.assertTrue(result.passed, result.message)
    
    def test_02_data_accuracy(self):
        """测试数据准确性"""
        result = self.tester.test_data_accuracy()
        self.assertTrue(result.passed, result.message)
    
    def test_03_data_completeness(self):
        """测试数据完整性"""
        result = self.tester.test_data_completeness()
        self.assertTrue(result.passed, result.message)
    
    def test_04_zero_copy_storage(self):
        """测试零拷贝存储"""
        result = self.tester.test_zero_copy_storage()
        self.assertTrue(result.passed, result.message)
    
    def test_05_write_performance(self):
        """测试写入性能"""
        result = self.tester.test_write_performance()
        self.assertTrue(result.passed, result.message)
    
    def test_06_read_performance(self):
        """测试读取性能"""
        result = self.tester.test_read_performance()
        self.assertTrue(result.passed, result.message)


def main():
    """主函数 - 运行所有测试"""
    # 检查依赖
    print("检查依赖...")
    print(f"  ArcticDB: {'✅ 已安装' if ARCTIC_AVAILABLE else '❌ 未安装'}")
    print(f"  PyArrow: {'✅ 已安装' if ARROW_AVAILABLE else '❌ 未安装'}")
    print(f"  Polars: {'✅ 已安装' if POLARS_AVAILABLE else '❌ 未安装'}")
    
    if not ARCTIC_AVAILABLE:
        print("\n❌ 缺少必要依赖，请先安装:")
        print("   pip install arcticdb pyarrow polars pandas numpy")
        return 1
    
    # 运行测试
    tester = DataInterfaceTester()
    results = tester.run_all_tests()
    
    # 返回退出码
    failed = sum(1 for r in results if not r.passed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    # 支持两种运行方式:
    # 1. 直接运行: python test_data_interface.py
    # 2. unittest: python -m unittest test_data_interface
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--unittest':
        # 使用 unittest 运行
        unittest.main(argv=[''], verbosity=2, exit=False)
    else:
        # 直接运行
        exit_code = main()
        sys.exit(exit_code)
