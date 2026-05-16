"""
直接检查 TradeRecord 创建
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class TradeRecord:
    """交易记录"""
    date: str
    code: str
    action: str
    shares: int
    price: float
    amount: float
    commission: float
    tax: float = 0.0
    profit_loss: float = 0.0
    roi: float = 0.0
    entry_price: float = 0.0
    entry_date: str = ""
    holding_days: int = 0
    indicators: Dict[str, Any] = field(default_factory=dict)

# 创建一个卖出交易记录
trade = TradeRecord(
    date='2025-06-05',
    code='002005',
    action='sell',
    shares=55500,
    price=1.80,
    amount=99770.13,
    commission=29.97,
    tax=99.90,
    profit_loss=-159.84,
    roi=-0.16,
    entry_price=1.80,
    entry_date='2025-06-04',
    holding_days=1
)

print(f"TradeRecord 创建后:")
print(f"  amount: {trade.amount}")
print(f"  __dict__: {trade.__dict__}")

# 模拟 _trade_to_dict
def _trade_to_dict(trade: TradeRecord) -> Dict[str, Any]:
    stock_code = str(trade.code).zfill(6) if trade.code.isdigit() else trade.code
    return {
        "id": f"{trade.date}_{stock_code}_{trade.action}",
        "date": trade.date,
        "symbol": stock_code,
        "symbolCode": stock_code,
        "code": stock_code,
        "action": trade.action,
        "price": trade.price,
        "quantity": trade.shares,
        "shares": trade.shares,
        "commission": trade.commission,
        "cost": trade.amount if trade.action == 'buy' else 0,
        "revenue": trade.amount if trade.action == 'sell' else 0,
        "profitLoss": trade.profit_loss,
        "profit_loss": trade.profit_loss,
        "roi": trade.roi,
        "entry_price": trade.entry_price,
        "holdingDays": trade.holding_days
    }

result = _trade_to_dict(trade)
print(f"\n_trade_to_dict 结果:")
print(f"  cost: {result['cost']}")
print(f"  revenue: {result['revenue']}")
