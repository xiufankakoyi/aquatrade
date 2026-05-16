"""
Playwright: 删除所有测试股票
"""
from playwright.sync_api import sync_playwright
import time

def delete_all_test_stocks():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.on("console", lambda msg: print(f"[控制台] {msg.text}") if '删除' in msg.text else None)
        
        print("打开持仓页面...")
        page.goto("http://localhost:5173/portfolio")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        deleted_count = 0
        
        while True:
            # 查找包含"测试股票"的行
            rows = page.locator("tr:has-text('测试股票')")
            count = rows.count()
            
            if count == 0:
                print("没有找到测试股票，删除完成！")
                break
            
            print(f"找到 {count} 条测试股票")
            
            # 点击第一个删除按钮
            delete_btn = rows.first.locator("button[title='删除']")
            
            def handle_dialog(dialog):
                dialog.accept()
            
            page.on("dialog", handle_dialog)
            
            delete_btn.click()
            time.sleep(1)
            
            deleted_count += 1
            print(f"已删除 {deleted_count} 条")
            
            page.wait_for_load_state("networkidle")
            time.sleep(1)
        
        print(f"\n总共删除了 {deleted_count} 条测试股票")
        time.sleep(1)
        browser.close()

if __name__ == "__main__":
    delete_all_test_stocks()
