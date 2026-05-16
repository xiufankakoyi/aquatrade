"""
测试自动列推断功能

验证：
1. AST 分析能正确提取 self.xxx 属性访问
2. 推断结果与手动声明一致
3. 缓存机制正常工作
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.utils.column_inference import ColumnInference, KNOWN_FACTOR_COLUMNS
from core.strategies.vectorized_base import VectorizedStrategyBase
import numpy as np


class TestStrategy1(VectorizedStrategyBase):
    """测试策略1：使用 close, volume, total_mv"""
    
    def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data):
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        # 使用 self.close, self.volume, self.total_mv
        signals = np.zeros_like(self.close)
        
        # 简单逻辑：成交量放大时买入
        volume_ma = np.mean(self.volume, axis=0)
        for i in range(len(trading_dates)):
            for j in range(len(stock_codes)):
                if self.volume[i, j] > volume_ma[j] * 1.5:
                    signals[i, j] = 1
        
        return signals


class TestStrategy2(VectorizedStrategyBase):
    """测试策略2：使用 ma5, ma10, ma20"""
    
    def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data):
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        # 使用 self.ma5, self.ma10, self.ma20
        signals = np.zeros_like(self.close)
        
        # MA 金叉策略
        for i in range(1, len(trading_dates)):
            for j in range(len(stock_codes)):
                if self.ma5[i-1, j] < self.ma10[i-1, j] and self.ma5[i, j] > self.ma10[i, j]:
                    signals[i, j] = 1
        
        return signals


class TestStrategy3(VectorizedStrategyBase):
    """测试策略3：手动声明 required_factors"""
    
    required_factors = ['rsi_14', 'macd_dif']
    
    def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data):
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        # 使用 self.factors['rsi_14'], self.factors['macd_dif']
        signals = np.zeros_like(self.close)
        
        return signals


class TestStrategy4(VectorizedStrategyBase):
    """测试策略4：混合使用 AST 推断 + 手动声明"""
    
    required_factors = ['kdj_k']
    
    def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data):
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        # AST 推断：self.close, self.volume
        # 手动声明：kdj_k
        signals = np.zeros_like(self.close)
        
        # 使用 close, volume
        _ = self.close
        _ = self.volume
        
        return signals


def test_column_inference():
    print("=" * 60)
    print("自动列推断测试")
    print("=" * 60)
    
    print("\n已知因子列（部分）:")
    print(f"  {sorted(list(KNOWN_FACTOR_COLUMNS)[:20])}...")
    print(f"  共 {len(KNOWN_FACTOR_COLUMNS)} 个")
    
    print("\n" + "-" * 60)
    print("测试1：纯 AST 推断（close, volume, total_mv）")
    print("-" * 60)
    strategy1 = TestStrategy1()
    columns1 = ColumnInference.infer(strategy1)
    print(f"推断结果: {sorted(columns1)}")
    
    expected1 = {'stock_code', 'trade_date', 'close', 'volume', 'total_mv'}
    print(f"期望包含: {sorted(expected1)}")
    print(f"测试结果: {'✓ 通过' if expected1.issubset(columns1) else '✗ 失败'}")
    
    print("\n" + "-" * 60)
    print("测试2：纯 AST 推断（ma5, ma10, ma20）")
    print("-" * 60)
    strategy2 = TestStrategy2()
    columns2 = ColumnInference.infer(strategy2)
    print(f"推断结果: {sorted(columns2)}")
    
    expected2 = {'stock_code', 'trade_date', 'close', 'ma5', 'ma10', 'ma20'}
    print(f"期望包含: {sorted(expected2)}")
    print(f"测试结果: {'✓ 通过' if expected2.issubset(columns2) else '✗ 失败'}")
    
    print("\n" + "-" * 60)
    print("测试3：手动声明 required_factors")
    print("-" * 60)
    strategy3 = TestStrategy3()
    columns3 = ColumnInference.infer(strategy3)
    print(f"推断结果: {sorted(columns3)}")
    
    expected3 = {'stock_code', 'trade_date', 'rsi_14', 'macd_dif'}
    print(f"期望包含: {sorted(expected3)}")
    print(f"测试结果: {'✓ 通过' if expected3.issubset(columns3) else '✗ 失败'}")
    
    print("\n" + "-" * 60)
    print("测试4：混合模式（AST + 手动声明）")
    print("-" * 60)
    strategy4 = TestStrategy4()
    columns4 = ColumnInference.infer(strategy4)
    print(f"推断结果: {sorted(columns4)}")
    
    expected4 = {'stock_code', 'trade_date', 'close', 'volume', 'kdj_k'}
    print(f"期望包含: {sorted(expected4)}")
    print(f"测试结果: {'✓ 通过' if expected4.issubset(columns4) else '✗ 失败'}")
    
    print("\n" + "-" * 60)
    print("测试5：缓存机制")
    print("-" * 60)
    ColumnInference.clear_cache()
    
    import time
    t0 = time.perf_counter()
    columns5a = ColumnInference.infer(strategy1)
    time1 = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    columns5b = ColumnInference.infer(strategy1)
    time2 = time.perf_counter() - t0
    
    print(f"首次推断: {time1*1000:.2f}ms")
    print(f"缓存命中: {time2*1000:.2f}ms")
    print(f"加速比: {time1/time2:.1f}x")
    print(f"测试结果: {'✓ 通过' if time2 < time1 else '✗ 失败'}")
    
    print("\n" + "-" * 60)
    print("测试6：get_required_columns 方法")
    print("-" * 60)
    columns6 = TestStrategy1.get_required_columns()
    print(f"有序列: {columns6}")
    
    print(f"测试结果: {'✓ 通过' if 'stock_code' in columns6 and 'trade_date' in columns6 else '✗ 失败'}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_column_inference()
