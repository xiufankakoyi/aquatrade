"""
验证因子数据查询
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import time
from server.routes.screener_routes import get_factor_data_for_date


def test_factor_query():
    """测试因子数据查询"""
    print("=" * 70)
    print("验证因子数据查询")
    print("=" * 70)
    
    start_time = time.time()
    factor_df = get_factor_data_for_date('2025-11-07')
    elapsed = time.time() - start_time
    
    if factor_df is not None and not factor_df.is_empty():
        print(f"\n✅ 加载成功: {len(factor_df)} 行, 耗时: {elapsed:.2f}s")
        print(f"   列: {list(factor_df.columns)}")
        
        # 检查 MA 列
        ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
        for col in ma_cols:
            if col in factor_df.columns:
                null_count = factor_df[col].null_count()
                non_null = len(factor_df) - null_count
                print(f"   {col}: null={null_count}/{len(factor_df)}, 有效={non_null}")
        
        # 显示样本数据
        print(f"\n   样本数据:")
        sample = factor_df.head(3)
        for row in sample.iter_rows(named=True):
            print(f"   {row.get('stock_code')}: ma5={row.get('ma5'):.2f if row.get('ma5') else 'N/A'}, ma10={row.get('ma10'):.2f if row.get('ma10') else 'N/A'}")
    else:
        print("❌ 加载失败")


if __name__ == '__main__':
    test_factor_query()
