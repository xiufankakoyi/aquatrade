import sys
import os
import inspect

sys.path.insert(0, os.getcwd())

from core.strategies.strategy_framework import StrategyBase
import core.strategies.trend_follow_strategy as trend_module

print(f"StrategyBase id: {id(StrategyBase)}")
print(f"StrategyBase module: {StrategyBase.__module__}")

print(f"Trend module name: {trend_module.__name__}")

for name, obj in inspect.getmembers(trend_module, inspect.isclass):
    print(f"\nChecking class: {name}")
    print(f"  Module: {getattr(obj, '__module__', None)}")
    print(f"  Is subclass of StrategyBase? {issubclass(obj, StrategyBase)}")
    print(f"  Is StrategyBase? {obj is StrategyBase}")
    
    # Imitate factory logic
    is_defined_in_module = getattr(obj, '__module__', None) == trend_module.__name__
    print(f"  Defined in module? {is_defined_in_module}")
    
    if is_defined_in_module and issubclass(obj, StrategyBase) and obj is not StrategyBase:
        print("  ✅ Factory SHOULD register this!")
    else:
        print("  ❌ Factory will SKIP this.")
