"""
调试数据读取问题
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

from core.dragon_eye.manager import DragonEyeManager

manager = DragonEyeManager()

print("读取市场情绪数据...")
df = manager.get_market_sentiment("2026-01-01", "2026-02-20")

print(f"数据形状: {df.shape}")
print(f"列名: {df.columns}")
print(f"前5行:")
print(df.head())

if 'trade_date' in df.columns:
    print(f"\ntrade_date 列: {df['trade_date'].to_list()}")
else:
    print("\ntrade_date 列不存在!")
    # 检查索引
    if hasattr(df, 'index'):
        print(f"索引: {df.index}")
