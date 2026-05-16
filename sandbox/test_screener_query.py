"""
测试前端筛选器查询
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import time
from server.routes.screener_data_service import ScreenerDataService


def test_screener_query():
    """测试筛选器查询"""
    print("=" * 70)
    print("测试筛选器查询")
    print("=" * 70)
    
    service = ScreenerDataService()
    
    # 测试最新日期 2026-02-27
    start_time = time.time()
    df = service.get_data(
        date='2026-02-27',
        fields=['ma5', 'ma10', 'ma20', 'ma60', 'close', 'total_mv'],
        conditions=[]
    )
    elapsed = time.time() - start_time
    
    if df is not None and not df.is_empty():
        print(f"\n✅ 查询成功: {len(df)} 行, 耗时: {elapsed:.2f}s")
        print(f"   列: {list(df.columns)}")
        
        # 检查 MA 列
        ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
        for col in ma_cols:
            if col in df.columns:
                null_count = df[col].null_count()
                print(f"   {col}: null={null_count}/{len(df)}")
        
        # 显示样本
        print(f"\n   样本数据:")
        sample = df.head(3)
        for row in sample.iter_rows(named=True):
            stock_code = row.get('stock_code', 'N/A')
            ma5 = row.get('ma5')
            ma10 = row.get('ma10')
            ma20 = row.get('ma20')
            print(f"   {stock_code}: ma5={ma5:.2f if ma5 else 'N/A'}, ma10={ma10:.2f if ma10 else 'N/A'}, ma20={ma20:.2f if ma20 else 'N/A'}")
    else:
        print("❌ 查询失败")


if __name__ == '__main__':
    test_screener_query()
