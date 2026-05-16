"""
使用 Flask 开发服务器测试
"""
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from server.app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
