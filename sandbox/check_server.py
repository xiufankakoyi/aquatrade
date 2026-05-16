
"""
检查后端服务器是否运行
"""
import sys
import requests
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    resp = requests.get('http://localhost:5000/api/db/last_date', timeout=5)
    print(f"✅ 后端服务器正在运行! 状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    sys.exit(0)
except requests.exceptions.ConnectionError:
    print("❌ 后端服务器未运行，请先启动后端")
    print("启动命令: python run.py")
    sys.exit(1)
except Exception as e:
    print(f"❌ 检查失败: {e}")
    sys.exit(1)

