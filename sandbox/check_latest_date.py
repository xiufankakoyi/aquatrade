"""
检查 get_latest_trade_date 返回的日期
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from server.routes.screener_routes import get_latest_trade_date, get_all_trade_dates


def check_latest_date():
    """检查最新日期"""
    print("=" * 70)
    print("检查最新交易日")
    print("=" * 70)
    
    latest = get_latest_trade_date()
    print(f"\n最新交易日: {latest}")
    
    dates = get_all_trade_dates()
    print(f"\n交易日数量: {len(dates)}")
    print(f"前 10 个交易日: {dates[:10]}")


if __name__ == '__main__':
    check_latest_date()
