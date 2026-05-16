"""
Playwright 测试前端删除
"""
from playwright.sync_api import sync_playwright
import time

def test_delete():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.on("console", lambda msg: print(f"[控制台] {msg.text}") if '删除' in msg.text or 'error' in msg.text.lower() else None)
        
        print("打开持仓页面...")
        page.goto("http://localhost:5173/portfolio")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # 查找删除按钮
        delete_buttons = page.locator("button[title='删除']")
        count = delete_buttons.count()
        print(f"找到 {count} 个删除按钮")
        
        if count > 0:
            print("点击删除按钮...")
            
            def handle_dialog(dialog):
                print(f"[对话框] {dialog.message}")
                dialog.accept()
            
            page.on("dialog", handle_dialog)
            
            delete_buttons.first.click()
            time.sleep(3)
            
            # 检查结果
            success_msg = page.locator("text=删除成功")
            error_msg = page.locator("text=删除失败")
            
            if success_msg.count() > 0:
                print("✅ 删除成功！")
            elif error_msg.count() > 0:
                print("❌ 删除失败")
            else:
                print("⚠️ 未看到结果提示")
        else:
            print("没有找到删除按钮，可能没有持仓数据")
        
        time.sleep(2)
        browser.close()

if __name__ == "__main__":
    test_delete()
