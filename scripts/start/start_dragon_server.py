#!/usr/bin/env python
"""DragonEye 服务启动脚本（调试用）"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

from server.app import app

# 打印所有路由
print("=" * 60)
print("Registered Routes:")
print("=" * 60)
for rule in app.url_map.iter_rules():
    methods = ','.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
    print(f"  {rule.rule:40s} [{methods}]")

# 过滤 dragon 路由
dragon_routes = [r for r in app.url_map.iter_rules() if 'dragon' in str(r)]
print(f"\nDragon routes count: {len(dragon_routes)}")
for rule in dragon_routes:
    print(f"  {rule}")

PORT = 5001

print("\n" + "=" * 60)
print(f"Starting server on http://0.0.0.0:{PORT}")
print("=" * 60)

# 启动服务
app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
