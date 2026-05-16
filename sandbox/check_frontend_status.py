"""
检查前端页面状态
"""
import requests

print("=" * 80)
print("检查前端页面状态")
print("=" * 80)

# 检查前端页面是否可以访问
print("\n[1] 检查前端页面...")
try:
    resp = requests.get('http://localhost:5173', timeout=5)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        print("   ✅ 前端页面正常")
    else:
        print(f"   ❌ 前端页面异常: {resp.status_code}")
except Exception as e:
    print(f"   ❌ 无法访问前端: {e}")

# 检查前端是否能正确代理 API
print("\n[2] 检查前端 API 代理...")
try:
    resp = requests.get('http://localhost:5173/api/db/last_date', timeout=5)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"   ✅ API 代理正常: {resp.json()}")
    else:
        print(f"   ❌ API 代理异常: {resp.status_code}")
except Exception as e:
    print(f"   ❌ API 代理错误: {e}")

print("\n" + "=" * 80)
print("诊断建议:")
print("=" * 80)
print("""
如果以上检查都正常，但前端还是不能更新，请检查:

1. 浏览器控制台错误:
   - 按 F12 打开开发者工具
   - 切换到 Console 标签
   - 查看是否有红色错误信息

2. 网络请求:
   - 在开发者工具中切换到 Network 标签
   - 点击更新按钮
   - 查看是否有 /api/db/update 请求
   - 查看请求状态码和响应

3. Socket.IO 连接:
   - 在 Console 中搜索 "Socket.IO"
   - 查看连接状态和事件接收情况

4. 如果以上都正常，尝试:
   - 清除浏览器缓存 (Ctrl+Shift+R 强制刷新)
   - 重启前端开发服务器
   - 检查 DataUpdateModal 组件是否正确显示
""")
