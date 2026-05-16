"""
验证 read_as_dict 新接口与老接口数据一致性

测试目标：
1. 数据格式一致
2. 数据值一致
3. 可以完全替代老接口
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import lancedb
import polars as pl
import numpy as np
from datetime import datetime, timedelta


def load_data_original(start_date: str, end_date: str):
    """原始方法：Python 循环（老接口）- 注意：老接口加载全部数据，不按日期过滤"""
    db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
    
    st_info_table = db.open_table("stock_info")
    st_info_df = pl.from_arrow(st_info_table.to_arrow())
    
    st_stocks = set(st_info_df.filter(pl.col('is_st') == 1)['stock_code'].to_list())
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    min_list_date = (end_dt - timedelta(days=60)).strftime('%Y%m%d')
    new_stocks = set(st_info_df.filter(pl.col('list_date') > min_list_date)['stock_code'].to_list())
    
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    daily_data = {}
    for row in daily_df.iter_rows(named=True):
        sc = row['stock_code']
        if sc in st_stocks or sc in new_stocks:
            continue
        if sc not in daily_data:
            daily_data[sc] = {'dates': [], 'close': [], 'open': [], 'high': [], 'low': [], 'volume': []}
        daily_data[sc]['dates'].append(str(row['trade_date']))
        daily_data[sc]['close'].append(row['close'])
        daily_data[sc]['open'].append(row.get('open', row['close']))
        daily_data[sc]['high'].append(row.get('high', row['close']))
        daily_data[sc]['low'].append(row.get('low', row['close']))
        daily_data[sc]['volume'].append(row['volume'])
    for sc in daily_data:
        idx = np.argsort(np.array(daily_data[sc]['dates']))
        for k in daily_data[sc]:
            arr = np.array(daily_data[sc][k])[idx]
            daily_data[sc][k] = arr.astype(np.float64) if k != 'dates' else arr
    return daily_data


def load_data_original_with_date_filter(start_date: str, end_date: str):
    """原始方法 + 日期过滤（修复版）"""
    db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
    
    st_info_table = db.open_table("stock_info")
    st_info_df = pl.from_arrow(st_info_table.to_arrow())
    
    st_stocks = set(st_info_df.filter(pl.col('is_st') == 1)['stock_code'].to_list())
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    min_list_date = (end_dt - timedelta(days=60)).strftime('%Y%m%d')
    new_stocks = set(st_info_df.filter(pl.col('list_date') > min_list_date)['stock_code'].to_list())
    
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    daily_data = {}
    for row in daily_df.iter_rows(named=True):
        sc = row['stock_code']
        if sc in st_stocks or sc in new_stocks:
            continue
        
        trade_date = str(row['trade_date'])[:10]
        if trade_date < start_date or trade_date > end_date:
            continue
        
        if sc not in daily_data:
            daily_data[sc] = {'dates': [], 'close': [], 'open': [], 'high': [], 'low': [], 'volume': []}
        daily_data[sc]['dates'].append(trade_date)
        daily_data[sc]['close'].append(row['close'])
        daily_data[sc]['open'].append(row.get('open', row['close']))
        daily_data[sc]['high'].append(row.get('high', row['close']))
        daily_data[sc]['low'].append(row.get('low', row['close']))
        daily_data[sc]['volume'].append(row['volume'])
    for sc in daily_data:
        idx = np.argsort(np.array(daily_data[sc]['dates']))
        for k in daily_data[sc]:
            arr = np.array(daily_data[sc][k])[idx]
            daily_data[sc][k] = arr.astype(np.float64) if k != 'dates' else arr
    return daily_data


def load_data_optimized(start_date: str, end_date: str):
    """优化方法：向量化操作（新接口）"""
    from data_svc.storage.lancedb_reader import get_lancedb_reader
    
    db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
    
    st_info_table = db.open_table("stock_info")
    st_info_df = pl.from_arrow(st_info_table.to_arrow())
    
    st_stocks = set(st_info_df.filter(pl.col('is_st') == 1)['stock_code'].to_list())
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    min_list_date = (end_dt - timedelta(days=60)).strftime('%Y%m%d')
    new_stocks = set(st_info_df.filter(pl.col('list_date') > min_list_date)['stock_code'].to_list())
    
    filter_stocks = st_stocks | new_stocks
    
    reader = get_lancedb_reader()
    fields = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
    
    daily_data = reader.read_as_dict(
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        filter_stocks=filter_stocks,
    )
    
    for sc in daily_data:
        daily_data[sc]['dates'] = daily_data[sc].pop('trade_date')
    
    return daily_data


def compare_data(data_old, data_new):
    """对比两个数据集是否一致"""
    print("=" * 60)
    print("数据一致性验证")
    print("=" * 60)
    
    # 1. 股票数量
    old_stocks = set(data_old.keys())
    new_stocks = set(data_new.keys())
    
    print(f"\n[1] 股票数量")
    print(f"    老接口: {len(old_stocks)}")
    print(f"    新接口: {len(new_stocks)}")
    
    missing_in_new = old_stocks - new_stocks
    extra_in_new = new_stocks - old_stocks
    
    if missing_in_new:
        print(f"    ⚠️ 新接口缺失: {len(missing_in_new)} 只")
        print(f"       样例: {list(missing_in_new)[:5]}")
    if extra_in_new:
        print(f"    ⚠️ 新接口多余: {len(extra_in_new)} 只")
        print(f"       样例: {list(extra_in_new)[:5]}")
    
    if not missing_in_new and not extra_in_new:
        print(f"    ✓ 股票列表一致")
    
    # 2. 字段一致性
    common_stocks = old_stocks & new_stocks
    sample_stock = list(common_stocks)[0] if common_stocks else None
    
    if sample_stock:
        print(f"\n[2] 字段对比 (样例: {sample_stock})")
        old_fields = set(data_old[sample_stock].keys())
        new_fields = set(data_new[sample_stock].keys())
        print(f"    老接口字段: {sorted(old_fields)}")
        print(f"    新接口字段: {sorted(new_fields)}")
        
        if old_fields == new_fields:
            print(f"    ✓ 字段一致")
        else:
            print(f"    ⚠️ 字段不一致")
    
    # 3. 数据值对比
    if sample_stock and common_stocks:
        print(f"\n[3] 数据值对比 (样例: {sample_stock})")
        old_sample = data_old[sample_stock]
        new_sample = data_new[sample_stock]
        
        for field in ['dates', 'close', 'open', 'high', 'low', 'volume']:
            if field not in old_sample or field not in new_sample:
                print(f"    ⚠️ {field}: 字段缺失")
                continue
            
            old_arr = old_sample[field]
            new_arr = new_sample[field]
            
            if field == 'dates':
                old_dates = [str(d) for d in old_arr]
                new_dates = [str(d)[:10] for d in new_arr]
                
                if old_dates == new_dates:
                    print(f"    ✓ {field}: 一致 ({len(old_dates)} 条)")
                else:
                    print(f"    ⚠️ {field}: 不一致")
                    print(f"       老接口前3: {old_dates[:3]}")
                    print(f"       新接口前3: {new_dates[:3]}")
            else:
                if len(old_arr) != len(new_arr):
                    print(f"    ⚠️ {field}: 长度不一致 ({len(old_arr)} vs {len(new_arr)})")
                    continue
                
                if np.allclose(old_arr, new_arr, equal_nan=True, rtol=1e-5):
                    print(f"    ✓ {field}: 一致 (均值: {np.nanmean(old_arr):.4f})")
                else:
                    diff = np.abs(old_arr - new_arr)
                    max_diff = np.nanmax(diff)
                    print(f"    ⚠️ {field}: 不一致 (最大差异: {max_diff:.6f})")
    
    # 4. 多股票抽样验证
    print(f"\n[4] 多股票抽样验证 (10只)")
    test_stocks = list(common_stocks)[:10]
    all_match = True
    
    for stock in test_stocks:
        old_data = data_old[stock]
        new_data = data_new[stock]
        
        dates_match = len(old_data['dates']) == len(new_data['dates'])
        close_match = np.allclose(old_data['close'], new_data['close'], equal_nan=True, rtol=1e-5)
        
        if dates_match and close_match:
            print(f"    ✓ {stock}: 一致")
        else:
            print(f"    ⚠️ {stock}: 不一致 (dates={dates_match}, close={close_match})")
            all_match = False
    
    # 5. 总结
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)
    
    if all_match and not missing_in_new and not extra_in_new:
        print("✓ 新接口可以完全替代老接口")
        return True
    else:
        print("⚠️ 新接口与老接口存在差异，需要进一步检查")
        return False


def main():
    start_date = "2026-01-01"
    end_date = "2026-03-13"
    
    print(f"日期范围: {start_date} ~ {end_date}")
    print()
    
    print("[1] 加载老接口数据（带日期过滤）...")
    t0 = time.perf_counter()
    data_old = load_data_original_with_date_filter(start_date, end_date)
    time_old = time.perf_counter() - t0
    print(f"    耗时: {time_old:.1f}s")
    
    print("\n[2] 加载新接口数据...")
    t0 = time.perf_counter()
    data_new = load_data_optimized(start_date, end_date)
    time_new = time.perf_counter() - t0
    print(f"    耗时: {time_new:.1f}s")
    
    print(f"\n加速比: {time_old/time_new:.1f}x")
    
    # 对比数据
    can_replace = compare_data(data_old, data_new)
    
    return can_replace


if __name__ == "__main__":
    main()
