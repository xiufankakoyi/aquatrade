import sys
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')

from data_svc.ingestion.dragon_eye_adapter import DragonEyeAdapter
import polars as pl

adapter = DragonEyeAdapter()

latest_date = adapter._resolve_latest_date()
if not latest_date:
    print('No trading data found in data_lake')
    sys.exit(1)

print(f'Latest trading date: {latest_date}')

df_limit_up, df_sector, df_sentiment = adapter.build_dataframes(latest_date)

print(f'df_limit_up: {df_limit_up.shape if not df_limit_up.is_empty() else "EMPTY"}')
print(f'df_sector: {df_sector.shape if not df_sector.is_empty() else "EMPTY"}')
print(f'df_sentiment: {df_sentiment.shape if not df_sentiment.is_empty() else "EMPTY"}')

df = df_limit_up if not df_limit_up.is_empty() else df_sector
if not df.is_empty():
    sort_col = 'continue_num' if 'continue_num' in df.columns else 'continue_num'
    top = df.sort(sort_col, descending=True).head(10)
    print(f'\nTop Limit-Up Stocks:')
    header = f"{'Code':<10} {'Name':<14} {'Continue':<10} {'Turnover%':<12} {'MktCap(yi)':<12} {'Tags'}"
    print(header)
    print('-' * 80)
    for row in top.iter_rows(named=True):
        code = str(row.get('stock_code', ''))
        name = str(row.get('stock_name', ''))
        cnt = row.get('continue_num', 0)
        tr = f"{row.get('turnover_rate', 0):.2f}%"
        mc = f"{row.get('market_cap_yi', 0):.1f}"
        tags = row.get('leader_tag', '') or row.get('theme', '')
        ban_str = f'{cnt} ban'
        print(f'{code:<10} {name:<14} {ban_str:<10} {tr:<12} {mc:<12} {tags}')
