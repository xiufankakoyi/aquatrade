"""
检查缺失交易日数据
====================
对比 Tushare 交易日历和本地 Parquet 数据，找出缺失的日期
"""
import os
import sys
import datetime
import pandas as pd
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import Config

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None


def check_missing_dates():
    """检查缺失的交易日数据"""
    print("=" * 60)
    print("检查缺失交易日数据")
    print("=" * 60)
    
    if not TUSHARE_AVAILABLE:
        print("错误: tushare 未安装")
        return
    
    token = Config.TUSHARE_TOKEN
    if not token:
        print("错误: TUSHARE_TOKEN 未配置")
        return
    
    ts.set_token(token)
    pro = ts.pro_api()
    
    # 读取本地数据
    parquet_path = os.path.join(Config.PARQUET_DIR, "stock_daily.parquet")
    if not os.path.exists(parquet_path):
        print(f"错误: Parquet 文件不存在: {parquet_path}")
        return
    
    print(f"\n[1] 读取本地数据...")
    df_local = pl.scan_parquet(parquet_path)
    local_dates = df_local.select(pl.col("trade_date")).collect().to_series().to_list()
    local_dates_set = set(d.strftime('%Y%m%d') if hasattr(d, 'strftime') else str(d).replace('-', '') for d in local_dates)
    print(f"    本地数据日期数: {len(local_dates_set)}")
    print(f"    最早日期: {min(local_dates_set)}")
    print(f"    最晚日期: {max(local_dates_set)}")
    
    # 获取 Tushare 交易日历
    print(f"\n[2] 获取 Tushare 交易日历...")
    start_date = min(local_dates_set)
    end_date = datetime.date.today().strftime('%Y%m%d')
    
    try:
        df_cal = pro.trade_cal(exchange='', start_date=start_date, end_date=end_date)
        trade_dates = set(df_cal[df_cal['is_open'] == 1]['cal_date'].tolist())
        print(f"    Tushare 交易日数: {len(trade_dates)}")
        print(f"    范围: {min(trade_dates)} ~ {max(trade_dates)}")
    except Exception as e:
        print(f"    获取交易日历失败: {e}")
        return
    
    # 找出缺失的日期
    print(f"\n[3] 对比数据...")
    missing_dates = sorted(trade_dates - local_dates_set)
    extra_dates = sorted(local_dates_set - trade_dates)
    
    if missing_dates:
        print(f"\n    ⚠️ 缺失 {len(missing_dates)} 个交易日:")
        for i, date in enumerate(missing_dates[:20]):
            # 获取该日期的股票数量（用于判断是部分缺失还是全部缺失）
            try:
                df_daily = pro.daily(trade_date=date)
                expected_count = len(df_daily) if df_daily is not None else 0
                print(f"        {date}: 期望 {expected_count} 条数据")
            except:
                print(f"        {date}: 无法获取预期数量")
        
        if len(missing_dates) > 20:
            print(f"        ... 还有 {len(missing_dates) - 20} 个日期")
        
        # 显示缺失日期分布
        print(f"\n    缺失日期分布:")
        by_year = {}
        for d in missing_dates:
            year = d[:4]
            by_year[year] = by_year.get(year, 0) + 1
        for year in sorted(by_year.keys()):
            print(f"        {year}年: {by_year[year]} 天")
    else:
        print(f"\n    ✅ 无缺失日期！")
    
    if extra_dates:
        print(f"\n    ⚠️ 本地有多余 {len(extra_dates)} 个日期（可能已退市/非交易日）:")
        for date in extra_dates[:10]:
            print(f"        {date}")
        if len(extra_dates) > 10:
            print(f"        ... 还有 {len(extra_dates) - 10} 个日期")
    
    # 统计信息
    print(f"\n[4] 统计信息:")
    print(f"    Tushare 交易日: {len(trade_dates)} 天")
    print(f"    本地数据日期: {len(local_dates_set)} 天")
    print(f"    缺失: {len(missing_dates)} 天")
    print(f"    多余: {len(extra_dates)} 天")
    print(f"    覆盖率: {len(local_dates_set & trade_dates)}/{len(trade_dates)} ({len(local_dates_set & trade_dates)/len(trade_dates)*100:.1f}%)")
    
    # 检查最近30天
    print(f"\n[5] 最近30天检查:")
    today = datetime.date.today()
    recent_missing = []
    for i in range(30):
        check_date = (today - datetime.timedelta(days=i)).strftime('%Y%m%d')
        if check_date in trade_dates and check_date not in local_dates_set:
            recent_missing.append(check_date)
    
    if recent_missing:
        print(f"    ⚠️ 最近30天缺失 {len(recent_missing)} 天:")
        for d in sorted(recent_missing):
            print(f"        {d}")
    else:
        print(f"    ✅ 最近30天数据完整！")
    
    print(f"\n" + "=" * 60)
    
    return missing_dates


if __name__ == "__main__":
    check_missing_dates()
