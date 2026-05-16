"""检查缺失日期并测试补数据功能"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import requests
from datetime import datetime, timedelta

print("=" * 60)
print("检查缺失日期")
print("=" * 60)

# 1. 检查最近 10 天的缺失日期
end_date = datetime.now()
start_date = end_date - timedelta(days=10)

resp = requests.get(
    "http://localhost:5000/api/db/missing_dates",
    params={
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    },
    timeout=5
)
data = resp.json()
missing = data.get("missing_dates", [])

print(f"检查范围: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
print(f"缺失日期: {missing if missing else '无'}")

# 2. 如果有缺失日期，尝试补一个
if missing:
    target_date = missing[0]
    print(f"\n尝试补数据: {target_date}")
    
    # 转换格式
    target_date_fmt = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"
    
    # 从 Tushare 获取数据
    import pandas as pd
    from config.config import Config
    
    try:
        import tushare as ts
        ts.set_token(Config.TUSHARE_TOKEN)
        pro = ts.pro_api()
        
        df_daily = pro.daily(trade_date=target_date)
        if df_daily is None or df_daily.empty:
            print(f"{target_date} 没有数据（可能不是交易日）")
        else:
            print(f"获取到 {len(df_daily)} 条数据")
            
            # 插入到 QuestDB
            from questdb.ingress import Sender
            
            df_daily["stock_code"] = df_daily["ts_code"].str.split(".", expand=True)[0]
            
            records = 0
            with Sender("tcp", "localhost", 9009) as sender:
                for _, row in df_daily.iterrows():
                    ts_dt = pd.to_datetime(target_date, format="%Y%m%d").to_pydatetime()
                    
                    columns = {
                        "open": float(row.get("open", 0) or 0),
                        "high": float(row.get("high", 0) or 0),
                        "low": float(row.get("low", 0) or 0),
                        "close": float(row.get("close", 0) or 0),
                        "volume": float(row.get("vol", 0) or 0),
                        "amount": float(row.get("amount", 0) or 0),
                        "adj_factor": float(row.get("adj_factor", 1) or 1),
                        "prev_close": float(row.get("pre_close", 0) or 0),
                    }
                    
                    sender.row(
                        "base_daily",
                        symbols={"stock_code": row["stock_code"]},
                        columns=columns,
                        at=ts_dt
                    )
                    records += 1
                
                sender.flush()
            
            print(f"成功插入 {records} 条记录")
            
            # 3. 再次验证
            resp = requests.get(
                "http://localhost:5000/api/db/missing_dates",
                params={
                    "start_date": target_date_fmt,
                    "end_date": target_date_fmt
                },
                timeout=5
            )
            data = resp.json()
            missing_after = data.get("missing_dates", [])
            
            if target_date not in missing_after:
                print(f"\n✅ {target_date} 数据已存在")
            else:
                print(f"\n❌ {target_date} 仍然缺失")
                
    except Exception as e:
        print(f"插入失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n没有缺失日期，数据完整！")

# 4. 检查最终状态
print("\n" + "=" * 60)
print("最终状态检查")
print("=" * 60)

resp = requests.get("http://localhost:5000/api/db/last_date", timeout=5)
data = resp.json()
print(f"最后日期: {data.get('last_date')}")

print("=" * 60)
