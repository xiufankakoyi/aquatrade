import sys
import os

# 获取当前脚本所在目录的父目录（即项目根目录）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"项目根目录: {project_root}")

# 添加项目根目录到Python路径
sys.path.insert(0, project_root)
print(f"Python路径: {sys.path}")

# 现在尝试导入
from server.app import app

if __name__ == '__main__':
    print("启动Flask开发服务器...")
    app.run(debug=True, host='0.0.0.0', port=5000)