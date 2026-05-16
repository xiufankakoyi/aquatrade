"""
检查最近交易日情况
"""
import sys
from pathlib import Path
from datetime import datetime, date

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import tushare as ts
    from config.config import Config
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

def check_recent_dates():
    print("=" * 60)
    print("最近交易日检查")
    print(f"今天日期: {date.today()}")
    print("=" * 60)
    
    if not TUSHARE_AVAILABLE:
        print("tushare 未安装")
        return
    
    token = Config.TUSHARE_TOKEN
    if not token:
        print("TUSHARE_TOKEN 未配置")
        return
    
    ts.set_token(token)
    pro = ts.pro_api()
    
    start = (date.today().replace(day=1)).strftime('%Y%m%d')
    end = date.today().strftime('%Y%m%d')
    
    df_cal = pro.trade_cal(exchange='', start_date=start, end_date=end)
    trade_dates = df_cal[df_cal['is_open'] == 1]['cal_date'].tolist()
    
    print(f"\n本月交易日历 ({start[:6]}):")
    for d in sorted(trade_dates):
        d_date = datetime.strptime(d, '%Y%m%d').date()
        is_today = " (今天)" if d_date == date.today() else ""
        is_future = " (未来)" if d_date > date.today() else ""
        print(f"  {d[:4]}-{d[4:6]}-{d[6:8]}{is_today}{is_future}")
    
    print(f"\n最近5个交易日:")
    past_trades = [d for d in sorted(trade_dates) if datetime.strptime(d, '%Y%m%d').date() <= date.today()]
    for d in past_trades[-5:]:
        print(f"  {d[:4]}-{d[4:6]}-{d[6:8]}")
    
    print(f"\n最新交易日: {past_trades[-1] if past_trades else '无'}")

if __name__ == "__main__":
    check_recent_dates()
