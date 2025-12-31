import os
import sys
import pandas as pd
import numpy as np
import time

# 确保可以找到项目内模块（如 database.optimized_data_query）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ==========================================
# 1. 导入你的项目环境
# ==========================================
# 请在这里导入你的 DataQuery 类初始化方法
# 例如: from data.data_query import DataQuery
#       from utils.config import Config
#       data_query = DataQuery() 
# 为了演示，这里假设你已经初始化了一个 data_query 对象

def get_real_data_query():
    """
    【已改】在这里初始化并返回你真实项目中的 DataQuery 实例。
    请根据实际项目修改 import 路径，确保返回可用的 DataQuery 对象。
    """
    from database.optimized_data_query import OptimizedStockDataQuery
    return OptimizedStockDataQuery()

# ==========================================
# 2. 核心校验逻辑
# ==========================================

def verify_database_integrity(check_date='2024-10-19', sample_size=10):
    """
    :param check_date: 校验日期（最好选一个最近的交易日）
    :param sample_size: 随机抽查的股票数量
    """
    print(f"[*] 正在初始化数据接口...")
    try:
        dq = get_real_data_query()
    except ImportError as e:
        print(f"[错误] 无法导入 DataQuery，请修改 get_real_data_query 函数中的 import 路径。\n详细错误: {e}")
        return

    print(f"[*] 正在获取 {check_date} 的全市场股票池（包含预计算的 volume_ratio）...")
    
    # 获取当日股票池（包含 volume 和 volume_ratio 列）
    # 假设你的 get_stock_pool 返回 DataFrame
    pool = dq.get_stock_pool(check_date) 
    
    if pool is None or pool.empty:
        print("[错误] 股票池为空，请检查日期是否为交易日，或数据库连接是否正常。")
        return

    # 检查必要列
    required_cols = ['stock_code', 'volume', 'volume_ratio']
    for col in required_cols:
        if col not in pool.columns:
            print(f"[错误] 股票池数据缺少必要列: {col}。当前列: {pool.columns.tolist()}")
            return

    # 过滤掉停牌（没成交量的）和刚上市没数据的
    valid_pool = pool[pool['volume'] > 0].copy()
    
    # 随机抽样
    if len(valid_pool) > sample_size:
        samples = valid_pool.sample(sample_size)
    else:
        samples = valid_pool

    print(f"[*] 开始对 {len(samples)} 只股票进行【硬核对账】...\n")
    print(f"{'股票代码':<12} | {'数据库量比':<10} | {'手动计算量比':<12} | {'误差':<10} | {'结果':<6}")
    print("-" * 70)

    error_count = 0
    
    for _, row in samples.iterrows():
        code = row['stock_code']
        db_ratio = row['volume_ratio']
        db_vol = row['volume'] # 当日成交量

        # ==============================================================================
        # 【关键步骤】获取历史数据
        # 你需要根据你的 data_query API 修改下面这行代码
        # 目标：获取包括 check_date 在内的过去 6 个交易日的日线数据
        # ==============================================================================
        try:
            # 使用 OptimizedStockDataQuery 的 get_stock_history 方法
            # 获取包括 check_date 在内的过去 6 个交易日的数据
            from datetime import timedelta
            check_date_dt = pd.to_datetime(check_date)
            start_date = (check_date_dt - timedelta(days=10)).strftime('%Y-%m-%d')  # 多取几天确保有6个交易日
            
            history_df = dq.get_stock_history(
                stock_code=code,
                start_date=start_date,
                end_date=check_date,
                columns=['volume', 'trade_date']
            )
            
            # 提取成交量数组，按日期排序，取最后6条
            if history_df.empty:
                vols = []
            else:
                history_df = history_df.sort_values('trade_date')
                vols = history_df['volume'].tail(6).values

        except Exception as e:
            print(f"{code:<12} | 获取历史数据失败: {e}")
            continue

        # --- 验证逻辑 ---
        # 1. 数据长度检查
        if len(vols) < 6:
            print(f"{code:<12} | {'N/A':<10} | {'数据不足6天':<12} | {'-':<10} | [跳过]")
            continue
            
        # 2. 验证当日成交量是否一致（先看volume本身对不对）
        # 历史数据的最后一个应该是 check_date 当天
        vol_today_hist = vols[-1]
        if not np.isclose(db_vol, vol_today_hist, rtol=0.001):
            print(f"{code:<12} | [数据源冲突] 股票池volume({db_vol}) != 历史K线volume({vol_today_hist})")
            error_count += 1
            continue

        # 3. 计算量比
        # 公式：当日 / 过去5日均值
        vol_past_5d = vols[:-1]
        avg_5d = vol_past_5d.mean()
        
        if avg_5d == 0:
            calc_ratio = 0.0
        else:
            calc_ratio = vol_today_hist / avg_5d

        # 4. 比对
        diff = abs(db_ratio - calc_ratio)
        is_match = diff < 0.01  # 允许 0.01 的浮点误差

        status = "✅通过" if is_match else "❌失败"
        if not is_match: error_count += 1
        
        print(f"{code:<12} | {db_ratio:<10.4f} | {calc_ratio:<12.4f} | {diff:<10.6f} | {status}")

    print("-" * 70)
    if error_count == 0:
        print(f"\n[完美] 抽样的 {len(samples)} 只股票数据完全一致！可以直接使用数据库字段。")
    else:
        print(f"\n[警告] 发现 {error_count} 个数据不一致！请检查：")
        print("1. 数据库的 volume_ratio 计算公式是否为 (今日量 / 前5日均量)？")
        print("2. 数据库是否发生了除权除息（复权）导致历史 K 线和快照不一致？")
        print("3. 数据源的更新时间是否同步？")

if __name__ == "__main__":
    # 请修改日期为你数据库里有数据的某一天
    verify_database_integrity(check_date='2024-12-19')