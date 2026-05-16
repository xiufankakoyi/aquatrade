"""
Playwright 测试：删除平安银行持仓
"""
from playwright.sync_api import sync_playwright
import time

def delete_pingan_positions():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("1. 打开持仓页面...")
        page.goto("http://localhost:5173/portfolio")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # 查找所有平安银行的行
        print("2. 查找平安银行持仓...")
        
        while True:
            # 查找包含"平安银行"的行
            rows = page.locator("tr:has-text('平安银行')")
            count = rows.count()
            
            if count == 0:
                print("没有找到平安银行持仓，删除完成！")
                break
            
            print(f"找到 {count} 条平安银行持仓")
            
            # 点击第一行的删除按钮
            first_row = rows.first
            delete_btn = first_row.locator("button:has(i.fa-trash)")
            
            if delete_btn.count() > 0:
                print("点击删除按钮...")
                
                # 监听对话框并确认
                page.on("dialog", lambda dialog: dialog.accept())
                
                delete_btn.click()
                time.sleep(1)
                
                # 等待页面刷新
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                
                print("删除成功，继续检查...")
            else:
                print("未找到删除按钮")
                break
        
        print("\n3. 验证最终结果...")
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        final_rows = page.locator("tr:has-text('平安银行')")
        if final_rows.count() == 0:
            print("✅ 所有平安银行持仓已删除！")
        else:
            print(f"⚠️ 还有 {final_rows.count()} 条平安银行持仓")
        
        browser.close()

if __name__ == "__main__":
    delete_pingan_positions()
