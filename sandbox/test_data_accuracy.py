"""
数据准确性全面测试

测试内容：
1. 复权价格准确性
2. 市值单位正确性
3. 停牌数据标记
4. 涨跌停标记
5. 因子计算准确性
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def test_price_accuracy():
    """测试价格数据准确性"""
    print("\n" + "=" * 70)
    print("1. 价格数据准确性测试")
    print("=" * 70)
    
    loader = get_polars_loader_v5()
    matrix_data = loader.load_period_to_matrix(
        "2023-01-01", "2023-01-31",
        required_fields=['open', 'high', 'low', 'close', 'volume']
    )
    
    if matrix_data is None:
        print("❌ 数据加载失败")
        return False
    
    matrices = matrix_data['matrices']
    T, N = matrix_data['T'], matrix_data['N']
    
    print(f"\n数据维度: {T} 天 x {N} 只股票")
    
    # 测试1: 价格逻辑检查
    open_p = matrices['open']
    high_p = matrices['high']
    low_p = matrices['low']
    close_p = matrices['close']
    
    # 检查 high >= low
    valid_hl = (high_p >= low_p) | np.isnan(high_p) | np.isnan(low_p)
    hl_violations = (~valid_hl).sum()
    print(f"\n价格逻辑检查:")
    print(f"  high >= low 违规: {hl_violations} 处")
    
    # 检查 high >= open, close
    valid_high = (high_p >= open_p) | np.isnan(high_p) | np.isnan(open_p)
    valid_high2 = (high_p >= close_p) | np.isnan(high_p) | np.isnan(close_p)
    high_violations = (~valid_high).sum() + (~valid_high2).sum()
    print(f"  high >= open/close 违规: {high_violations} 处")
    
    # 检查 low <= open, close
    valid_low = (low_p <= open_p) | np.isnan(low_p) | np.isnan(open_p)
    valid_low2 = (low_p <= close_p) | np.isnan(low_p) | np.isnan(close_p)
    low_violations = (~valid_low).sum() + (~valid_low2).sum()
    print(f"  low <= open/close 违规: {low_violations} 处")
    
    # 测试2: 成交量检查
    volume = matrices['volume']
    negative_volume = (volume < 0).sum()
    print(f"\n成交量检查:")
    print(f"  负成交量: {negative_volume} 处")
    
    # 测试3: 价格范围检查
    extreme_prices = ((close_p > 10000) | (close_p < 0.1)) & ~np.isnan(close_p)
    extreme_count = extreme_prices.sum()
    print(f"\n价格范围检查:")
    print(f"  极端价格 (>10000 或 <0.1): {extreme_count} 处")
    
    if hl_violations == 0 and high_violations == 0 and low_violations == 0 and negative_volume == 0:
        print("\n✅ 价格数据基本正确")
        return True
    else:
        print("\n⚠️ 价格数据存在问题")
        return False


def test_market_cap_unit():
    """测试市值单位"""
    print("\n" + "=" * 70)
    print("2. 市值单位测试")
    print("=" * 70)
    
    query = OptimizedStockDataQuery()
    
    # 获取某天的股票池
    pool = query.get_stock_pool("2023-06-01", use_cache=False)
    
    if pool is None or pool.empty:
        print("❌ 股票池数据为空")
        return False
    
    print(f"\n股票池样本 ({len(pool)} 只股票):")
    
    # 检查市值列
    if 'total_mv' in pool.columns:
        mv = pool['total_mv']
        print(f"\n市值统计 (total_mv):")
        print(f"  最小值: {mv.min():,.0f}")
        print(f"  最大值: {mv.max():,.0f}")
        print(f"  中位数: {mv.median():,.0f}")
        print(f"  平均值: {mv.mean():,.0f}")
        
        # 判断单位
        # 如果市值是"万"为单位，茅台应该是 20000 万左右
        # 如果市值是"元"为单位，茅台应该是 2 万亿左右
        
        # 找茅台
        moutai = pool[pool['stock_code'].astype(str).str.contains('600519')]
        if not moutai.empty:
            moutai_mv = moutai['total_mv'].iloc[0]
            print(f"\n  茅台(600519)市值: {moutai_mv:,.0f}")
            
            if moutai_mv > 1e8:  # 大于1亿
                print(f"  ⚠️ 市值单位可能是'元'，茅台市值 {moutai_mv/1e8:.0f} 亿")
            elif moutai_mv > 1e4:  # 大于1万
                print(f"  ✅ 市值单位可能是'万'，茅台市值 {moutai_mv/1e4:.0f} 万亿")
            else:
                print(f"  ⚠️ 市值单位不明")
        
        # 检查是否有异常小的市值
        very_small = (mv < 1000).sum()
        very_large = (mv > 1e9).sum()
        print(f"\n  异常小市值(<1000): {very_small} 只")
        print(f"  异常大市值(>10亿): {very_large} 只")
        
        return True
    else:
        print("❌ 股票池缺少 total_mv 列")
        return False


def test_suspended_stocks():
    """测试停牌数据"""
    print("\n" + "=" * 70)
    print("3. 停牌数据测试")
    print("=" * 70)
    
    query = OptimizedStockDataQuery()
    
    # 获取一段时间的数据
    start_date = "2023-01-01"
    end_date = "2023-01-31"
    
    # 获取某只股票的日数据
    history = query.get_batch_stock_history(
        stock_codes=['000001'],  # 平安银行
        start_date=start_date,
        end_date=end_date,
        columns=['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'is_suspended']
    )
    
    if history.empty:
        print("❌ 历史数据为空")
        return False
    
    print(f"\n平安银行(000001) {len(history)} 天数据:")
    print(history.head(10))
    
    # 检查停牌标记
    if 'is_suspended' in history.columns:
        suspended = history[history['is_suspended'] == 1]
        print(f"\n停牌天数: {len(suspended)}")
        if len(suspended) > 0:
            print("停牌日期:")
            print(suspended[['trade_date', 'open', 'close', 'volume', 'is_suspended']])
    else:
        print("⚠️ 数据中没有 is_suspended 列")
    
    return True


def test_limit_up_down():
    """测试涨跌停标记"""
    print("\n" + "=" * 70)
    print("4. 涨跌停标记测试")
    print("=" * 70)
    
    query = OptimizedStockDataQuery()
    
    # 获取某天的股票池
    pool = query.get_stock_pool("2023-06-01", use_cache=False)
    
    if pool is None or pool.empty:
        print("❌ 股票池数据为空")
        return False
    
    print(f"\n股票池字段: {list(pool.columns)}")
    
    # 检查涨跌停标记
    if 'is_limit_up' in pool.columns:
        limit_up = pool[pool['is_limit_up'] == 1]
        print(f"\n涨停股票: {len(limit_up)} 只")
        if len(limit_up) > 0:
            print(limit_up[['stock_code', 'close', 'is_limit_up']].head())
    else:
        print("⚠️ 没有 is_limit_up 列")
    
    if 'is_limit_down' in pool.columns:
        limit_down = pool[pool['is_limit_down'] == 1]
        print(f"\n跌停股票: {len(limit_down)} 只")
        if len(limit_down) > 0:
            print(limit_down[['stock_code', 'close', 'is_limit_down']].head())
    else:
        print("⚠️ 没有 is_limit_down 列")
    
    return True


def test_factor_accuracy():
    """测试因子计算准确性"""
    print("\n" + "=" * 70)
    print("5. 因子准确性测试")
    print("=" * 70)
    
    query = OptimizedStockDataQuery()
    
    # 获取股票池（包含因子）
    pool = query.get_stock_pool("2023-06-01", use_cache=False)
    
    if pool is None or pool.empty:
        print("❌ 股票池数据为空")
        return False
    
    print(f"\n股票池字段: {list(pool.columns)}")
    
    # 测试 MA5 计算
    if 'ma5' in pool.columns and 'close' in pool.columns:
        print("\nMA5 因子检查:")
        
        # 获取某只股票的历史数据重新计算 MA5
        test_code = pool['stock_code'].iloc[0]
        print(f"测试股票: {test_code}")
        
        history = query.get_batch_stock_history(
            stock_codes=[test_code],
            start_date="2023-05-20",
            end_date="2023-06-01",
            columns=['stock_code', 'trade_date', 'close']
        )
        
        if len(history) >= 5:
            history = history.sort_values('trade_date')
            manual_ma5 = history['close'].iloc[-5:].mean()
            
            # 从股票池获取 MA5
            pool_ma5 = pool[pool['stock_code'] == test_code]['ma5'].iloc[0]
            
            print(f"  手动计算 MA5: {manual_ma5:.4f}")
            print(f"  股票池 MA5: {pool_ma5:.4f}")
            print(f"  差异: {abs(manual_ma5 - pool_ma5):.4f}")
            
            if abs(manual_ma5 - pool_ma5) < 0.01:
                print("  ✅ MA5 计算正确")
            else:
                print("  ⚠️ MA5 计算有差异")
    else:
        print("⚠️ 股票池缺少 ma5 或 close 列")
    
    # 测试涨跌幅计算
    if 'close' in pool.columns and 'prev_close' in pool.columns:
        print("\n涨跌幅检查:")
        pool['calc_return'] = (pool['close'] - pool['prev_close']) / pool['prev_close']
        
        # 检查是否有异常涨跌幅
        extreme_up = pool[pool['calc_return'] > 0.21]  # 超过21%
        extreme_down = pool[pool['calc_return'] < -0.21]  # 低于-21%
        
        print(f"  异常大涨(>21%): {len(extreme_up)} 只")
        print(f"  异常大跌(<-21%): {len(extreme_down)} 只")
        
        if len(extreme_up) > 0:
            print("  大涨样本:")
            print(extreme_up[['stock_code', 'close', 'prev_close', 'calc_return']].head())
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("数据准确性全面测试")
    print("=" * 70)
    
    results = []
    
    results.append(("价格数据", test_price_accuracy()))
    results.append(("市值单位", test_market_cap_unit()))
    results.append(("停牌数据", test_suspended_stocks()))
    results.append(("涨跌停标记", test_limit_up_down()))
    results.append(("因子准确性", test_factor_accuracy()))
    
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有测试通过")
    else:
        print("⚠️ 部分测试未通过")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
