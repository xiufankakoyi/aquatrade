import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 导入Flask应用
from server.app import app

if __name__ == '__main__':
    print("启动Flask开发服务器...")
    print(f"服务器将运行在 http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)