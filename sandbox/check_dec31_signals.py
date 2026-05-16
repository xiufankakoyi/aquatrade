"""
检查2024-12-31的数据，看有多少只股票满足买入条件
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
import pandas as pd
import numpy as np

query = OptimizedStockDataQuery()

print("=" * 60)
print("检查2024-12-31的数据（用于生成2025-01-02的信号）")
print("=" * 60)

# 直接查询2024-12-31的数据
try:
    from data_svc.unified_data_manager import get_unified_manager
    manager = get_unified_manager()
    
    df = manager.read('stock_daily', start_date='2024-12-31', end_date='2024-12-31')
    if df is not None and not df.is_empty():
        print(f"\n2024-12-31有 {len(df)} 条数据，{df['stock_code'].n_unique()} 只股票")
        
        # 转换为pandas便于分析
        df_pd = df.to_pandas()
        
        # 检查均线数据
        print("\n均线数据有效性:")
        print(f"  MA5有效: {df_pd['ma5'].notna().sum()}/{len(df_pd)}")
        print(f"  MA10有效: {df_pd['ma10'].notna().sum()}/{len(df_pd)}")
        print(f"  MA20有效: {df_pd['ma20'].notna().sum()}/{len(df_pd)}")
        
        # 检查均线多头排列
        bullish = df_pd[
            (df_pd['ma5'] > df_pd['ma10']) & 
            (df_pd['ma10'] > df_pd['ma20']) &
            (df_pd['ma5'] > 0)
        ]
        print(f"\n均线多头排列: {len(bullish)} 只股票")
        
        if len(bullish) > 0:
            print("\n前10只均线多头排列的股票:")
            print(bullish[['stock_code', 'close', 'ma5', 'ma10', 'ma20']].head(10).to_string())
            
            # 检查其他条件
            print("\n进一步筛选:")
            
            # 价格在MA20之上
            above_ma20 = bullish[bullish['close'] > bullish['ma20']]
            print(f"  价格在MA20之上: {len(above_ma20)}")
            
            # 乖离率不太高（< 5%）
            bullish['bias'] = (bullish['close'] / bullish['ma5'] - 1)
            normal_bias = bullish[bullish['bias'] < 0.05]
            print(f"  乖离率<5%: {len(normal_bias)}")
            
            # 成交量比
            if 'volume_ratio' in bullish.columns:
                vol_ok = bullish[bullish['volume_ratio'] >= 0.8]
                print(f"  成交量比>=0.8: {len(vol_ok)}")
            
            # 综合条件
            final = bullish[
                (bullish['close'] > bullish['ma20']) &
                (bullish['bias'] < 0.05)
            ]
            print(f"\n  综合条件（均线多头+价格在MA20之上+乖离率<5%）: {len(final)}")
            
            if len(final) > 0:
                print("\n满足综合条件的股票:")
                print(final[['stock_code', 'close', 'ma5', 'ma10', 'ma20', 'bias']].head(10).to_string())
        else:
            print("\n2024-12-31没有均线多头排列的股票")
            print("这意味着2025-01-02不会有买入信号")
    else:
        print("2024-12-31没有数据")
except Exception as e:
    print(f"查询失败: {e}")
    import traceback
    traceback.print_exc()
