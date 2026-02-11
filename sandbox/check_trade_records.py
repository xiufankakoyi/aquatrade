"""
验证回测交易记录生成和数据库持久化
"""
import sqlite3
from config.config import Config

def check_trade_records():
    print("=" * 60)
    print("检查回测交易记录")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(Config.DB_PATH)
        cursor = conn.cursor()
        
        # 1. 检查最近的回测记录
        print("\n[1] 最近的回测记录:")
        cursor.execute("""
            SELECT id, strategy_name, start_date, end_date, 
                   final_capital, total_return, trade_count, 
                   created_at
            FROM backtest_results
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        if not results:
            print("   ❌ 没有找到任何回测记录")
            return
        
        for row in results:
            backtest_id, strategy, start, end, final, ret, trades, created = row
            print(f"\n   回测ID: {backtest_id}")
            print(f"   策略: {strategy}")
            print(f"   日期: {start} ~ {end}")
            print(f"   最终资金: {final:,.2f}")
            print(f"   总收益率: {ret:.2f}%")
            print(f"   交易次数: {trades}")
            print(f"   创建时间: {created}")
        
        # 2. 检查最新回测的交易记录
        latest_id = results[0][0]
        print(f"\n[2] 回测ID {latest_id} 的交易记录:")
        
        cursor.execute("""
            SELECT stock_code, action, date, price, shares, 
                   amount, profit_loss
            FROM trade_records
            WHERE backtest_id = ?
            ORDER BY date, id
        """, (latest_id,))
        
        trades = cursor.fetchall()
        if not trades:
            print(f"   ⚠️ 回测ID {latest_id} 没有交易记录")
            print("   可能原因:")
            print("   1. 策略没有生成任何信号")
            print("   2. 所有信号都因涨跌停/停牌被过滤")
            print("   3. 资金不足无法买入")
        else:
            print(f"   ✅ 找到 {len(trades)} 条交易记录\n")
            
            buy_count = sum(1 for t in trades if t[1] == 'buy')
            sell_count = sum(1 for t in trades if t[1] == 'sell')
            
            print(f"   买入: {buy_count} 笔")
            print(f"   卖出: {sell_count} 笔")
            
            # 显示前5笔交易
            print(f"\n   前5笔交易:")
            for i, trade in enumerate(trades[:5], 1):
                code, action, date, price, shares, amount, pnl = trade
                action_cn = "买入" if action == 'buy' else "卖出"
                print(f"   {i}. [{date}] {action_cn} {code}: {shares}股 @ ¥{price:.2f}")
                if action == 'sell' and pnl != 0:
                    print(f"      盈亏: ¥{pnl:,.2f}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_trade_records()
