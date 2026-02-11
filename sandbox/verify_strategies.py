import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(r'd:\aquatrade')
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.strategies.strategy_factory import get_factory

def test_strategy_discovery():
    factory = get_factory()
    # Force a discovery scan
    factory._discover_strategies(force_reload=True)
    
    strategies = factory.list_strategies()
    print("Available Strategies:")
    for s in strategies:
        print(f"- ID: {s['id']}, Name: {s['name']}, Class: {s['class_name']}")
    
    target_id = "jq_volume_v1pro"
    found = any(s['id'] == target_id for s in strategies)
    
    if found:
        print(f"\nSUCCESS: Strategy '{target_id}' found!")
    else:
        print(f"\nFAILURE: Strategy '{target_id}' NOT found.")

if __name__ == "__main__":
    test_strategy_discovery()
