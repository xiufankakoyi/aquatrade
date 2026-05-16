"""
Playwright 流式回测测试 - 检查基准曲线
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def test_streaming_backtest():
    print("=" * 80)
    print("Playwright 流式回测测试 - 检查基准曲线")
    print("=" * 80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        console_logs = []
        def handle_console(msg):
            log_entry = f"[{msg.type}] {msg.text}"
            console_logs.append(log_entry)
            if any(kw in msg.text for kw in ['stream_complete', 'benchmarkCurve', 'benchmarkReturn', 'daily_equity', 'DEBUG']):
                print(f"[Console] {msg.text[:300]}")
        
        page.on("console", handle_console)
        
        try:
            print("\n[1] 打开 Dashboard 页面...")
            await page.goto("http://localhost:5173/dashboard", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            print("[2] 选择策略...")
            select_el = page.locator("select").first
            if await select_el.count() > 0:
                options = await select_el.locator("option").all_text_contents()
                print(f"  可用策略: {options}")
                for i, opt in enumerate(options):
                    if '聚宽量比' in opt:
                        await select_el.select_option(index=i)
                        print(f"  已选择策略: {opt}")
                        break
            
            print("\n[3] 点击回测按钮...")
            backtest_btn = page.locator("button:has-text('回测')").first
            if await backtest_btn.count() > 0:
                await backtest_btn.click()
                print("  已点击回测按钮")
            
            print("\n[4] 等待回测完成...")
            
            for i in range(60):
                await asyncio.sleep(1)
                
                stream_complete_received = False
                for log in console_logs:
                    if 'stream_complete' in log and 'totalReturn' in log:
                        stream_complete_received = True
                
                if i % 10 == 0:
                    print(f"  {i}s: stream_complete={stream_complete_received}")
                
                if stream_complete_received:
                    print(f"  [OK] 收到 stream_complete 事件!")
                    break
            
            await asyncio.sleep(2)
            
            print("\n[5] 分析日志...")
            
            # 提取 benchmarkCurve 数据
            for log in console_logs:
                if 'benchmarkCurve' in log:
                    print(f"\n  找到 benchmarkCurve 日志:")
                    print(f"    {log[:500]}")
            
            # 提取 daily_equity 数据
            print("\n  daily_equity 示例:")
            daily_count = 0
            for log in console_logs:
                if 'daily_equity' in log and 'benchmarkReturn' in log and daily_count < 5:
                    print(f"    {log[:200]}")
                    daily_count += 1
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await asyncio.sleep(2)
            await browser.close()

if __name__ == '__main__':
    asyncio.run(test_streaming_backtest())
