"""
测试因子注入机制
验证 _preloaded_factors 是否正确注入到策略中
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List

from core.strategies.vectorized_base import VectorizedStrategyBase


class DebugMACrossStrategy(VectorizedStrategyBase):
    """调试版MA交叉策略"""
    
    def __init__(self, target_stock='000001', **kwargs):
        super().__init__(**kwargs)
        self.target_stock = target_stock
        self.ma5 = None
        self.ma10 = None
        self.required_factors = ['ma5', 'ma10']
    
    def prepare_data(self, preloaded_data: Dict, trading_dates: List[str], stock_codes: List[str]):
        """准备数据 - 调试版"""
        print(f"\n[Strategy.prepare_data] 被调用")
        print(f"   策略ID: {id(self)}")
        print(f"   hasattr factors: {hasattr(self, 'factors')}")
        
        if hasattr(self, 'factors'):
            print(f"   factors类型: {type(self.factors)}")
            print(f"   factors内容: {list(self.factors.keys()) if isinstance(self.factors, dict) else 'N/A'}")
            
            if 'ma5' in self.factors:
                ma5_data = self.factors['ma5']
                print(f"   ma5在factors中: 形状={ma5_data.shape}, dtype={ma5_data.dtype}")
                print(f"   ma5前3个值: {ma5_data[:3, :3] if ma5_data.ndim >= 2 else ma5_data[:3]}")
            else:
                print(f"   ⚠️ ma5不在factors中!")
                
            if 'ma10' in self.factors:
                ma10_data = self.factors['ma10']
                print(f"   ma10在factors中: 形状={ma10_data.shape}")
            else:
                print(f"   ⚠️ ma10不在factors中!")
        else:
            print(f"   ⚠️ 策略没有factors属性!")
        
        # 调用父类的prepare_data
        super().prepare_data(preloaded_data, trading_dates, stock_codes)
        
        print(f"   prepare_data完成后:")
        print(f"   hasattr ma5: {hasattr(self, 'ma5')}, ma5 is None: {self.ma5 is None}")
        print(f"   hasattr ma10: {hasattr(self, 'ma10')}, ma10 is None: {self.ma10 is None}")
        
        if self.ma5 is not None:
            print(f"   self.ma5形状: {self.ma5.shape}")
            print(f"   self.ma5前3个值: {self.ma5[:3, :3]}")
        if self.ma10 is not None:
            print(f"   self.ma10形状: {self.ma10.shape}")
    
    def generate_signals_vectorized(self, price_matrix: np.ndarray, trading_dates: List[str], 
                                   stock_codes: List[str], **kwargs) -> np.ndarray:
        """生成信号 - 调试版"""
        print(f"\n[Strategy.generate_signals_vectorized] 被调用")
        print(f"   策略ID: {id(self)}")
        print(f"   price_matrix形状: {price_matrix.shape}")
        print(f"   trading_dates: {len(trading_dates)} 天 ({trading_dates[0]} ~ {trading_dates[-1]})")
        print(f"   stock_codes: {len(stock_codes)} 只")
        print(f"   target_stock: {self.target_stock}")
        
        T, N, F = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        if self.target_stock not in stock_codes:
            print(f"   ⚠️ 目标股票 {self.target_stock} 不在股票池中")
            return signals
        
        # 准备数据
        print(f"   [Strategy] 调用 prepare_data...")
        self.prepare_data(kwargs.get('preloaded_data', {}), trading_dates, stock_codes)
        
        print(f"   [Strategy] prepare_data 完成")
        print(f"   self.ma5: {self.ma5 is not None}")
        print(f"   self.ma10: {self.ma10 is not None}")
        
        if self.ma5 is None or self.ma10 is None:
            print(f"   ⚠️ MA数据为空，无法生成信号")
            return signals
        
        # 获取目标股票的MA数据
        n_idx = stock_codes.index(self.target_stock)
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        print(f"   n_idx: {n_idx}")
        print(f"   ma5_stock前5个值: {ma5_stock[:5]}")
        print(f"   ma10_stock前5个值: {ma10_stock[:5]}")
        
        # 检查是否有有效数据
        valid_mask = (~np.isnan(ma5_stock)) & (~np.isnan(ma10_stock))
        valid_count = np.sum(valid_mask)
        print(f"   有效数据点数量: {valid_count}/{T}")
        
        if valid_count == 0:
            print(f"   ⚠️ 没有有效的MA数据")
            return signals
        
        # 计算金叉和死叉
        ma5_prev = np.roll(ma5_stock, 1)
        ma10_prev = np.roll(ma10_stock, 1)
        
        golden_cross = (ma5_stock > ma10_stock) & (ma5_prev <= ma10_prev)
        death_cross = (ma5_stock < ma10_stock) & (ma5_prev >= ma10_prev)
        
        golden_cross[0] = False
        death_cross[0] = False
        
        signals[golden_cross, n_idx] = 1
        signals[death_cross, n_idx] = -1
        
        buy_count = np.sum(golden_cross)
        sell_count = np.sum(death_cross)
        print(f"   ✅ 生成信号: 买入={buy_count}, 卖出={sell_count}")
        
        return signals


def test_backtest():
    """测试回测"""
    from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
    
    config = BacktestConfig(
        start_date='2025-01-01',
        end_date='2025-01-31',
        initial_capital=100000,
        stock_pool=['000001'],
        warmup_days=20
    )
    
    strategy = DebugMACrossStrategy(target_stock='000001')
    
    print("=" * 60)
    print("开始回测")
    print("=" * 60)
    
    engine = UnifiedBacktestEngine(config, strategy)
    
    print("\n" + "=" * 60)
    print("检查引擎中的因子数据")
    print("=" * 60)
    
    if hasattr(engine, '_preloaded_factors'):
        print(f"引擎有 _preloaded_factors: {list(engine._preloaded_factors.keys())}")
        for name, matrix in engine._preloaded_factors.items():
            print(f"   {name}: 形状={matrix.shape}, dtype={matrix.dtype}")
            print(f"        前3个值: {matrix[:3, :3]}")
    else:
        print(f"引擎没有 _preloaded_factors!")
    
    result = engine.run()
    
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"总收益率: {result.get('total_return', 0):.2%}")
    print(f"交易次数: {result.get('trade_count', 0)}")
    
    return result


if __name__ == '__main__':
    test_backtest()
