"""检查并插入 2026-02-10 的数据"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import requests

print("=" * 60)
print("检查 2026-02-10 数据")
print("=" * 60)

# 1. 检查数据是否存在
resp = requests.get(
    "http://localhost:5000/api/db/missing_dates",
    params={"start_date": "2026-02-10", "end_date": "2026-02-10"},
    timeout=5
)
data = resp.json()
missing = data.get("missing_dates", [])

if "20260210" in missing:
    print("2026-02-10: 缺失，需要插入")
    
    # 2. 插入数据
    print("\n正在插入数据...")
    import pandas as pd
    from datetime import datetime
    from config.config import Config
    from config.logger import get_logger
    
    logger = get_logger(__name__)
    
    try:
        import tushare as ts
        ts.set_token(Config.TUSHARE_TOKEN)
        pro = ts.pro_api()
        
        # 获取日线数据
        df_daily = pro.daily(trade_date="20260210")
        if df_daily is None or df_daily.empty:
            print("2026-02-10 没有数据（可能不是交易日）")
        else:
            print(f"获取到 {len(df_daily)} 条数据")
            
            # 插入到 QuestDB
            from questdb.ingress import Sender
            
            df_daily["stock_code"] = df_daily["ts_code"].str.split(".", expand=True)[0]
            
            records = 0
            with Sender("tcp", "localhost", 9009) as sender:
                for _, row in df_daily.iterrows():
                    ts_dt = pd.to_datetime("20260210", format="%Y%m%d").to_pydatetime()
                    
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
                params={"start_date": "2026-02-10", "end_date": "2026-02-10"},
                timeout=5
            )
            data = resp.json()
            missing = data.get("missing_dates", [])
            
            if "20260210" not in missing:
                print("\n2026-02-10: 已存在")
            else:
                print("\n2026-02-10: 仍然缺失")
                
    except Exception as e:
        print(f"插入失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print("2026-02-10: 已存在")

print("=" * 60)
