"""
回测引擎集成测试
================
使用真实组件测试回测引擎：
1. UnifiedBacktestEngine - 真实回测引擎
2. Parquet 数据源（避免 ArcticDB 预加载问题）
3. SimpleVolumeStrategyV3 / TrendFollowStrategyV3 - 真实策略
4. 数值稳定性验证

使用方法:
    cd c:/Users/Liu/Desktop/projects/aquatrade
    python sandbox/test_backtest_integration.py
"""

import sys
import os

os.environ['DB_BACKEND'] = 'parquet'

import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import numpy as np

print("=" * 70)
print("回测引擎集成测试 (Parquet 数据源)")
print("=" * 70)

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

try:
    from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3, SimpleVolumeConfig
    STRATEGY_AVAILABLE = True
    print("   ✅ SimpleVolumeStrategyV3 可用")
except ImportError as e:
    STRATEGY_AVAILABLE = False
    print(f"   ⚠️ SimpleVolumeStrategyV3 不可用: {e}")

try:
    from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
    TREND_STRATEGY_AVAILABLE = True
    print("   ✅ TrendFollowStrategyV3 可用")
except ImportError as e:
    TREND_STRATEGY_AVAILABLE = False
    print(f"   ⚠️ TrendFollowStrategyV3 不可用: {e}")


@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    duration_ms: float
    message: str
    details: Optional[Dict] = None


class BacktestEngineIntegrationTester:
    """回测引擎集成测试"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.data_query: Optional[OptimizedStockDataQuery] = None
        self.engine: Optional[UnifiedBacktestEngine] = None
        
    def setup(self) -> bool:
        """初始化测试环境"""
        print("\n[1] 初始化测试环境...")
        
        try:
            self.data_query = OptimizedStockDataQuery()
            print("   ✅ 数据查询初始化成功")
            
            config = BacktestConfig(
                initial_capital=1_000_000,
                commission_rate=0.0003,
                min_commission=5.0,
            )
            
            self.engine = UnifiedBacktestEngine(
                data_query=self.data_query,
                config=config
            )
            print("   ✅ 回测引擎初始化成功")
            
            return True
            
        except Exception as e:
            print(f"   ❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_data_query(self) -> TestResult:
        """测试数据查询"""
        test_name = "数据查询测试 (Parquet)"
        start_time = time.perf_counter()
        
        try:
            codes = ['000001.SZ', '000002.SZ', '600000.SH']
            
            for code in codes:
                df = self.data_query.get_stock_history(
                    code=code,
                    start_date='2024-01-01',
                    end_date='2024-01-31'
                )
                
                if df is None or df.empty:
                    return TestResult(test_name, False, 0, f"股票 {code} 数据为空")
                
                required_cols = ['open', 'high', 'low', 'close', 'vol']
                missing = [c for c in required_cols if c not in df.columns]
                if missing:
                    return TestResult(test_name, False, 0, f"缺少列: {missing}")
            
            duration = (time.perf_counter() - start_time) * 1000
            
            return TestResult(
                test_name, True, duration,
                f"成功查询 {len(codes)} 只股票数据",
                {'codes': codes, 'query_time_ms': duration}
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"查询异常: {str(e)}")
    
    def test_engine_initialization(self) -> TestResult:
        """测试引擎初始化"""
        test_name = "引擎初始化测试"
        start_time = time.perf_counter()
        
        try:
            assert self.engine is not None
            assert self.engine.config is not None
            assert self.engine.config.initial_capital == 1_000_000
            
            duration = (time.perf_counter() - start_time) * 1000
            
            return TestResult(
                test_name, True, duration,
                "引擎初始化验证通过",
                {'initial_capital': self.engine.config.initial_capital}
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_strategy_creation(self) -> TestResult:
        """测试策略创建"""
        test_name = "策略创建测试"
        start_time = time.perf_counter()
        
        try:
            if not STRATEGY_AVAILABLE:
                return TestResult(test_name, False, 0, "策略不可用")
            
            config = SimpleVolumeConfig()
            strategy = SimpleVolumeStrategyV3(config=config)
            
            assert strategy is not None
            assert hasattr(strategy, 'generate_signals')
            
            duration = (time.perf_counter() - start_time) * 1000
            
            return TestResult(
                test_name, True, duration,
                "策略创建验证通过",
                {'strategy': type(strategy).__name__}
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_backtest_short_period(self) -> TestResult:
        """测试短期回测（10天）"""
        test_name = "短期回测测试 (10天)"
        start_time = time.perf_counter()
        
        try:
            if not STRATEGY_AVAILABLE or not self.engine:
                return TestResult(test_name, False, 0, "组件不可用")
            
            config = SimpleVolumeConfig()
            strategy = SimpleVolumeStrategyV3(config=config)
            
            start_date = '2024-01-01'
            end_date = '2024-01-10'
            
            events = {'final_metrics': None, 'stream_complete': None}
            
            for event in self.engine.run_backtest_streaming(
                start_date=start_date,
                end_date=end_date,
                strategy=strategy
            ):
                event_type = event.get('type')
                data = event.get('data', {})
                
                if event_type in events:
                    events[event_type] = data
            
            duration = (time.perf_counter() - start_time) * 1000
            
            if events['final_metrics'] is None:
                return TestResult(test_name, False, duration, "未收到 final_metrics")
            
            metrics = events['final_metrics']
            
            return TestResult(
                test_name, True, duration,
                f"回测完成: 总收益 {metrics.get('totalReturn', 0):.2f}%",
                {
                    'total_return': metrics.get('totalReturn', 0),
                    'max_drawdown': metrics.get('maxDrawdown', 0),
                    'trade_count': metrics.get('tradeCount', 0),
                    'win_rate': metrics.get('winRate', 0)
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            import traceback
            traceback.print_exc()
            return TestResult(test_name, False, duration, f"回测异常: {str(e)}")
    
    def test_backtest_medium_period(self) -> TestResult:
        """测试中期回测（30天）"""
        test_name = "中期回测测试 (30天)"
        start_time = time.perf_counter()
        
        try:
            if not STRATEGY_AVAILABLE or not self.engine:
                return TestResult(test_name, False, 0, "组件不可用")
            
            config = SimpleVolumeConfig()
            strategy = SimpleVolumeStrategyV3(config=config)
            
            start_date = '2024-01-01'
            end_date = '2024-01-31'
            
            events = {'final_metrics': None}
            
            for event in self.engine.run_backtest_streaming(
                start_date=start_date,
                end_date=end_date,
                strategy=strategy
            ):
                if event.get('type') == 'final_metrics':
                    events['final_metrics'] = event.get('data', {})
            
            duration = (time.perf_counter() - start_time) * 1000
            
            if events['final_metrics'] is None:
                return TestResult(test_name, False, duration, "未收到 final_metrics")
            
            metrics = events['final_metrics']
            
            return TestResult(
                test_name, True, duration,
                f"回测完成: 总收益 {metrics.get('totalReturn', 0):.2f}%",
                {
                    'total_return': metrics.get('totalReturn', 0),
                    'trade_count': metrics.get('tradeCount', 0)
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"回测异常: {str(e)}")
    
    def test_numerical_stability(self) -> TestResult:
        """测试数值稳定性（相同参数两次回测结果一致）"""
        test_name = "数值稳定性测试"
        start_time = time.perf_counter()
        
        try:
            if not STRATEGY_AVAILABLE or not self.engine:
                return TestResult(test_name, False, 0, "组件不可用")
            
            config = SimpleVolumeConfig()
            
            start_date = '2024-01-01'
            end_date = '2024-01-10'
            
            results = []
            
            for i in range(2):
                strategy = SimpleVolumeStrategyV3(config=config)
                for event in self.engine.run_backtest_streaming(
                    start_date=start_date,
                    end_date=end_date,
                    strategy=strategy
                ):
                    if event.get('type') == 'final_metrics':
                        results.append(event.get('data', {}))
                        break
            
            if len(results) < 2:
                return TestResult(test_name, False, 0, "结果数量不足")
            
            r1, r2 = results[0], results[1]
            
            diff_return = abs(r1.get('totalReturn', 0) - r2.get('totalReturn', 0))
            diff_equity = abs(r1.get('finalEquity', 0) - r2.get('finalEquity', 0))
            diff_trades = abs(r1.get('tradeCount', 0) - r2.get('tradeCount', 0))
            
            stable = diff_return < 0.001 and diff_equity < 0.01 and diff_trades == 0
            
            duration = (time.perf_counter() - start_time) * 1000
            
            return TestResult(
                test_name, stable, duration,
                "数值稳定" if stable else f"数值不稳定",
                {
                    'diff_return': diff_return,
                    'diff_equity': diff_equity,
                    'diff_trades': diff_trades
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def test_equity_curve(self) -> TestResult:
        """测试权益曲线正确性"""
        test_name = "权益曲线测试"
        start_time = time.perf_counter()
        
        try:
            if not STRATEGY_AVAILABLE or not self.engine:
                return TestResult(test_name, False, 0, "组件不可用")
            
            config = SimpleVolumeConfig()
            strategy = SimpleVolumeStrategyV3(config=config)
            
            start_date = '2024-01-01'
            end_date = '2024-02-29'
            
            equity_points = []
            
            for event in self.engine.run_backtest_streaming(
                start_date=start_date,
                end_date=end_date,
                strategy=strategy
            ):
                if event.get('type') == 'daily_equity_engine':
                    equity_points.append(event.get('data', {}).get('equity', 0))
            
            if not equity_points:
                return TestResult(test_name, False, 0, "无权益数据")
            
            initial_capital = self.engine.config.initial_capital
            min_equity = min(equity_points)
            
            valid = equity_points[0] == initial_capital and min_equity > 0
            
            duration = (time.perf_counter() - start_time) * 1000
            
            return TestResult(
                test_name, valid, duration,
                f"权益验证通过" if valid else f"权益异常",
                {
                    'initial': initial_capital,
                    'min': min_equity,
                    'final': equity_points[-1]
                }
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return TestResult(test_name, False, duration, f"测试异常: {str(e)}")
    
    def run_all_tests(self) -> List[TestResult]:
        """运行所有测试"""
        if not self.setup():
            return [TestResult("初始化", False, 0, "测试环境初始化失败")]
        
        tests = [
            ("数据查询", self.test_data_query),
            ("引擎初始化", self.test_engine_initialization),
            ("策略创建", self.test_strategy_creation),
            ("短期回测", self.test_backtest_short_period),
            ("中期回测", self.test_backtest_medium_period),
            ("数值稳定性", self.test_numerical_stability),
            ("权益曲线", self.test_equity_curve),
        ]
        
        results = []
        
        print("\n[2] 运行测试...")
        print("-" * 70)
        
        for name, test_func in tests:
            result = test_func()
            results.append(result)
            
            status = "✅" if result.passed else "❌"
            print(f"   {status} {result.name}: {result.message} ({result.duration_ms/1000:.1f}s)")
            
            if result.details:
                for k, v in result.details.items():
                    print(f"      {k}: {v}")
        
        print("-" * 70)
        
        return results


def main():
    """主函数"""
    tester = BacktestEngineIntegrationTester()
    results = tester.run_all_tests()
    
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    total_time = sum(r.duration_ms for r in results)
    
    print(f"总计: {len(results)} | 通过: {passed} | 失败: {failed}")
    print(f"总耗时: {total_time/1000:.1f}s")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
