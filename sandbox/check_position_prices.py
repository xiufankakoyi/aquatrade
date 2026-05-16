"""
检查持仓数据中的ETF价格
"""
import sys
sys.path.insert(0, '.')

from core.portfolio.position_manager import PositionManager
from core.portfolio.signal_engine import SignalEngine

def check_positions():
    print("检查持仓数据...")
    
    manager = PositionManager()
    positions = manager.get_all_positions(active_only=True)
    
    print(f"\n当前持仓数量: {len(positions)}")
    
    # 找出ETF持仓
    etf_positions = [p for p in positions if 'ETF' in p.stock_name or 'etf' in p.stock_name.lower()]
    
    if etf_positions:
        print("\nETF持仓:")
        for p in etf_positions:
            print(f"  {p.stock_code} - {p.stock_name}")
    
    # 获取最新价格
    stock_codes = [p.stock_code for p in positions]
    signal_engine = SignalEngine()
    latest_prices = signal_engine.get_latest_prices(stock_codes)
    
    print("\n所有持仓价格:")
    for p in positions:
        price = latest_prices.get(p.stock_code, 'N/A')
        print(f"  {p.stock_code} ({p.stock_name}): 买入价={p.buy_price}, 现价={price}")
    
    # 检查中概互联
    print("\n检查中概互联ETF...")
    for p in positions:
        if '中概' in p.stock_name or '互联' in p.stock_name:
            price = latest_prices.get(p.stock_code, 'N/A')
            print(f"  代码: {p.stock_code}")
            print(f"  名称: {p.stock_name}")
            print(f"  买入价: {p.buy_price}")
            print(f"  现价: {price}")

if __name__ == "__main__":
    check_positions()
