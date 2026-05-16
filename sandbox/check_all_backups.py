"""检查所有备份数据"""
from pathlib import Path
import polars as pl

backup_dir = Path('C:/Users/Liu/Desktop/projects/aquatrade/data/backup')

print('=' * 70)
print('备份数据检查')
print('=' * 70)

backup_files = list(backup_dir.glob('*.parquet'))
print(f'\n找到 {len(backup_files)} 个备份文件:\n')

results = []
for f in sorted(backup_files):
    try:
        df = pl.read_parquet(f)
        size_mb = f.stat().st_size / (1024 * 1024)
        
        info = {
            'file': f.name,
            'size_mb': size_mb,
            'rows': len(df),
            'cols': len(df.columns),
        }
        
        if 'trade_date' in df.columns:
            info['date_min'] = str(df['trade_date'].min())
            info['date_max'] = str(df['trade_date'].max())
        
        if 'ts_code' in df.columns:
            info['stocks'] = df['ts_code'].n_unique()
        
        results.append(info)
        print(f"{f.name}:")
        print(f"  大小: {size_mb:.1f} MB, 行数: {len(df):,}, 列数: {len(df.columns)}")
        if 'trade_date' in df.columns:
            print(f"  日期: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
        if 'ts_code' in df.columns:
            print(f"  股票数: {df['ts_code'].n_unique()}")
        print()
    except Exception as e:
        print(f"{f.name}: 读取失败 - {e}\n")

print('=' * 70)
print('总结')
print('=' * 70)
for r in results:
    print(f"  {r['file']}: {r['rows']:,} 行")
