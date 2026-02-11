import os
import sys
import importlib
import traceback

# Add project root to path
sys.path.insert(0, os.getcwd())

from core.strategies.strategy_factory import StrategyFactory

print("="*60)
print("诊断: 策略加载检查")
print("="*60)

# 1. Try to use the Factory normally
try:
    factory = StrategyFactory()
    strategies = factory.list_strategies()
    print(f"Factory 成功加载了 {len(strategies)} 个策略:")
    for s in strategies:
        print(f"  [OK] {s['id']} ({s['name']}) -> {s['class_name']}")
except Exception as e:
    print(f"Factory 初始化失败: {e}")
    traceback.print_exc()

print("\n" + "="*60)
print("诊断: 逐个文件导入检查")
print("="*60)

# 2. Manually check each file in core/strategies
strategies_dir = os.path.join("core", "strategies")
if not os.path.exists(strategies_dir):
    print(f"目录不存在: {strategies_dir}")
    sys.exit(1)

for filename in os.listdir(strategies_dir):
    if filename.endswith(".py") and not filename.startswith("_"):
        module_name = f"core.strategies.{filename[:-3]}"
        print(f"正在检查: {filename} ({module_name})... ", end="")
        try:
            importlib.import_module(module_name)
            print("导入成功 ✅")
        except Exception as e:
            print(f"导入失败 ❌")
            print(f"  错误信息: {e}")
            # print(traceback.format_exc())
