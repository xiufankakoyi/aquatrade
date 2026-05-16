"""检查策略名称映射"""
import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.strategies.strategy_factory import get_factory

f = get_factory()
strategies = f.list_strategies()

print("趋势相关策略:")
print("-" * 60)
for s in strategies:
    if '趋势' in s['name'] or 'trend' in s['id'].lower() or 'wave' in s['id'].lower():
        print(f"ID: {s['id']:25} | 名称: {s['name']}")
