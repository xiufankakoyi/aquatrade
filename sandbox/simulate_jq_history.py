"""
模拟聚宽的history函数

聚宽代码：
hist = history(20, '1d', 'close', security_list=stock_list, skip_paused=True)
ma5 = hist.iloc[-5:].mean()      # 最近5天均值
ma10 = hist.iloc[-10:].mean()    # 最近10天均值
ma5_prev = hist.iloc[-6:-1].mean()
ma10_prev = hist.iloc[-11:-1].mean()

关键：history(20, ...) 返回20天的数据，但在开盘时运行，所以返回的是昨天及之前的数据
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
import polars as pl
from pathlib import Path

def simulate_jq_history():
    print("模拟聚宽的history函数...")
    
    loader = get_polars_loader_v5()
    matrix_data = loader.load_period_to_matrix(
        "2022-11-01",  # 更早开始，确保有足够数据
        "2023-01-10",
        required_fields=['open', 'close'],
        use_adj_price=False
    )
    
    if matrix_data is None:
        print("❌ 加载失败")
        return
    
    matrices = matrix_data['matrices']
    dates = matrix_data['trading_dates']
    codes = matrix_data['stock_codes']
    
    print(f"\n日期范围: {dates[0]} 到 {dates[-1]}")
    
    # 找到2023-01-03的索引
    target_idx = None
    for i, d in enumerate(dates):
        if d == '2023-01-03':
            target_idx = i
            break
    
    print(f"2023-01-03 索引: {target_idx}")
    
    # 模拟聚宽在2023-01-03开盘时运行
    # history(20, ...) 返回的是T-1到T-20的数据
    # 因为在开盘时运行，当天(T)的数据还没有
    
    # 聚宽的history返回的是最近的20个交易日
    # 在2023-01-03开盘时，返回的是2022-12-05到2022-12-30的数据（假设没有停牌）
    
    # 检查000060的数据
    idx_000060 = None
    for i, code in enumerate(codes):
        if str(code) == '000060':
            idx_000060 = i
            break
    
    if idx_000060 is None:
        print("❌ 找不到000060")
        return
    
    close_col = matrices['close'][:, idx_000060]
    
    print(f"\n000060 收盘价历史（从target_idx往前20天）:")
    
    # 聚宽在开盘时运行，所以history返回的是target_idx-1往前20天
    hist_start = target_idx - 20
    hist_end = target_idx
    
    print(f"  history范围: dates[{hist_start}:{hist_end}] = {dates[hist_start]} 到 {dates[hist_end-1]}")
    
    for i in range(hist_start, hist_end):
        print(f"    {dates[i]}: close={close_col[i]:.2f}")
    
    # 计算MA
    hist_data = close_col[hist_start:hist_end]
    
    # 聚宽的MA计算
    # ma5 = hist.iloc[-5:].mean() = hist_data[-5:]
    ma5 = np.mean(hist_data[-5:])
    ma10 = np.mean(hist_data[-10:])
    ma5_prev = np.mean(hist_data[-6:-1])
    ma10_prev = np.mean(hist_data[-11:-1])
    
    print(f"\n聚宽MA计算:")
    print(f"  hist_data[-5:] = {hist_data[-5:]}")
    print(f"  MA5 = {ma5:.4f}")
    print(f"  MA10 = {ma10:.4f}")
    print(f"  MA5_prev = {ma5_prev:.4f}")
    print(f"  MA10_prev = {ma10_prev:.4f}")
    
    # 金叉判断
    cross = ma5_prev <= ma10_prev and ma5 > ma10
    print(f"\n金叉判断: MA5_prev <= MA10_prev ({ma5_prev:.4f} <= {ma10_prev:.4f}) = {ma5_prev <= ma10_prev}")
    print(f"          MA5 > MA10 ({ma5:.4f} > {ma10:.4f}) = {ma5 > ma10}")
    print(f"          金叉 = {cross}")

if __name__ == "__main__":
    simulate_jq_history()
