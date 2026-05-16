"""
对比中证1000和上证指数的收益曲线
使用ArcticDB加载指数数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def load_index_data_from_arcticdb(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """从ArcticDB加载指数数据"""
    from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
    
    arctic = get_arctic_instance_for_library('index_daily')
    lib = arctic['index_daily']
    
    if symbol not in lib.list_symbols():
        print(f"未找到 {symbol}")
        return None
    
    item = lib.read(symbol, date_range=(pd.Timestamp(start_date), pd.Timestamp(end_date)))
    df = item.data
    
    if df.empty:
        return None
    
    df = df.sort_index()
    df = df.reset_index()
    df = df.rename(columns={'index': 'trade_date'})
    
    return df[['trade_date', 'close']]


def main():
    print("=" * 70)
    print("中证1000 vs 上证指数 收益对比")
    print("=" * 70)
    
    start_date = "2015-01-01"
    end_date = "2025-12-31"
    
    print(f"\n时间范围: {start_date} - {end_date}")
    
    print("\n加载上证指数数据...")
    sh_df = load_index_data_from_arcticdb('000001.SH', start_date, end_date)
    
    print("加载中证1000数据...")
    zz_df = load_index_data_from_arcticdb('000852.SH', start_date, end_date)
    
    if sh_df is not None:
        print(f"  上证指数: {len(sh_df)} 条")
    if zz_df is not None:
        print(f"  中证1000: {len(zz_df)} 条")
    
    if sh_df is None or zz_df is None:
        print("\n数据不完整，无法对比")
        return
    
    merged = pd.merge(sh_df, zz_df, on='trade_date', how='inner', suffixes=('_sh', '_zz'))
    merged = merged.rename(columns={'close_sh': '000001.SH', 'close_zz': '000852.SH'})
    print(f"\n合并后数据: {len(merged)} 条")
    
    merged['sh_return'] = merged['000001.SH'] / merged['000001.SH'].iloc[0] * 100
    merged['zz_return'] = merged['000852.SH'] / merged['000852.SH'].iloc[0] * 100
    
    sh_total = (merged['000001.SH'].iloc[-1] / merged['000001.SH'].iloc[0] - 1) * 100
    zz_total = (merged['000852.SH'].iloc[-1] / merged['000852.SH'].iloc[0] - 1) * 100
    
    print(f"\n总收益:")
    print(f"  上证指数: {sh_total:.1f}%")
    print(f"  中证1000: {zz_total:.1f}%")
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    ax1 = axes[0]
    ax1.plot(merged['trade_date'], merged['sh_return'], label='上证指数', color='#E74C3C', linewidth=1.5)
    ax1.plot(merged['trade_date'], merged['zz_return'], label='中证1000', color='#2E86AB', linewidth=1.5)
    ax1.set_title('累计收益对比 (基准=100)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('净值', fontsize=11)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=100, color='gray', linestyle='--', linewidth=0.5)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    textstr = f'上证指数总收益: {sh_total:.1f}%\n中证1000总收益: {zz_total:.1f}%'
    props = dict(boxstyle='round', facecolor='white', alpha=0.8)
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes, fontsize=10,
             verticalalignment='top', bbox=props)
    
    ax2 = axes[1]
    merged['year'] = merged['trade_date'].dt.year
    yearly_returns = []
    for year in sorted(merged['year'].unique()):
        year_data = merged[merged['year'] == year]
        sh_year_return = (year_data['000001.SH'].iloc[-1] / year_data['000001.SH'].iloc[0] - 1) * 100
        zz_year_return = (year_data['000852.SH'].iloc[-1] / year_data['000852.SH'].iloc[0] - 1) * 100
        yearly_returns.append({
            'year': year,
            'sh_return': sh_year_return,
            'zz_return': zz_year_return,
        })
    
    yearly_df = pd.DataFrame(yearly_returns)
    
    x = np.arange(len(yearly_df))
    width = 0.35
    
    ax2.bar(x - width/2, yearly_df['sh_return'], width, label='上证指数', color='#E74C3C', alpha=0.7)
    ax2.bar(x + width/2, yearly_df['zz_return'], width, label='中证1000', color='#2E86AB', alpha=0.7)
    
    ax2.set_title('年度收益对比', fontsize=14, fontweight='bold')
    ax2.set_xlabel('年份', fontsize=11)
    ax2.set_ylabel('年度收益 (%)', fontsize=11)
    ax2.set_xticks(x)
    ax2.set_xticklabels(yearly_df['year'].astype(int))
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    plt.tight_layout()
    
    output_path = "C:/Users/Liu/Desktop/projects/aquatrade/sandbox/index_comparison.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n图表已保存: {output_path}")
    
    plt.close()
    
    print("\n" + "=" * 70)
    print("各年度收益对比")
    print("=" * 70)
    print(f"\n{'年份':^6} {'上证指数':^12} {'中证1000':^12} {'差异':^10}")
    print("-" * 45)
    for _, row in yearly_df.iterrows():
        diff = row['zz_return'] - row['sh_return']
        print(f"{int(row['year']):^6} {row['sh_return']:>12.1f}% {row['zz_return']:>12.1f}% {diff:>+10.1f}%")


if __name__ == "__main__":
    main()
