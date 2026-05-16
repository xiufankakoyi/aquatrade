"""
Playwright 测试：模拟前端删除操作
"""
from playwright.sync_api import sync_playwright
import time

def test_delete():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # 监听控制台日志
        page.on("console", lambda msg: print(f"[浏览器控制台] {msg.type}: {msg.text}"))
        
        # 监听网络请求
        def on_request(request):
            if 'positions' in request.url:
                print(f"[请求] {request.method} {request.url}")
        
        def on_response(response):
            if 'positions' in response.url:
                print(f"[响应] {response.status} {response.url}")
        
        page.on("request", on_request)
        page.on("response", on_response)
        
        print("1. 打开持仓页面...")
        page.goto("http://localhost:5173/portfolio")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # 查找删除按钮
        print("\n2. 查找删除按钮...")
        delete_buttons = page.locator("button[title='删除']")
        count = delete_buttons.count()
        print(f"找到 {count} 个删除按钮")
        
        if count > 0:
            print("\n3. 点击第一个删除按钮...")
            
            # 监听对话框
            def handle_dialog(dialog):
                print(f"[对话框] {dialog.message}")
                dialog.accept()
            
            page.on("dialog", handle_dialog)
            
            delete_buttons.first.click()
            time.sleep(3)
            
            print("\n4. 检查结果...")
            # 检查是否有成功提示
            success_msg = page.locator("text=删除成功")
            if success_msg.count() > 0:
                print("✅ 删除成功！")
            else:
                error_msg = page.locator("text=删除失败")
                if error_msg.count() > 0:
                    print("❌ 删除失败")
                else:
                    print("⚠️ 未看到结果提示")
        
        time.sleep(2)
        browser.close()

if __name__ == "__main__":
    test_delete()
