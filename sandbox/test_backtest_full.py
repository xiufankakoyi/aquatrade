"""
Playwright 完整回测测试 - 选择 simple_volume_v3 策略并验证结果
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def test_backtest():
    print("=" * 80)
    print("Playwright 完整回测测试")
    print("=" * 80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 收集 console 日志
        console_logs = []
        def handle_console(msg):
            log_entry = f"[{msg.type}] {msg.text}"
            console_logs.append(log_entry)
            # 只打印关键日志
            if any(kw in msg.text for kw in ['stream_complete', 'totalReturn', 'trades', 'error', 'Error']):
                print(f"[Console] {msg.type}: {msg.text[:200]}")
        
        page.on("console", handle_console)
        
        try:
            # 1. 打开页面
            print("\n[1] 打开 Dashboard 页面...")
            await page.goto("http://localhost:5173/dashboard", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 2. 选择策略
            print("[2] 选择策略...")
            select_el = page.locator("select").first
            if await select_el.count() > 0:
                # 获取所有选项
                options = await select_el.locator("option").all_text_contents()
                print(f"  可用策略: {options}")
                
                # 查找 simple_volume_v3 或聚宽量比策略
                target_idx = None
                for i, opt in enumerate(options):
                    if 'simple_volume' in opt.lower() or '聚宽量比' in opt:
                        target_idx = i
                        print(f"  找到目标策略: {opt} (index={i})")
                        break
                
                if target_idx is not None:
                    await select_el.select_option(index=target_idx)
                    print(f"  已选择策略: {options[target_idx]}")
                else:
                    print("  [WARN] 未找到目标策略，使用默认策略")
            
            # 3. 点击回测按钮
            print("\n[3] 点击回测按钮...")
            backtest_btn = page.locator("button:has-text('回测')").first
            if await backtest_btn.count() > 0:
                await backtest_btn.click()
                print("  已点击回测按钮")
            else:
                print("  [ERROR] 未找到回测按钮!")
                return
            
            # 4. 等待回测完成
            print("\n[4] 等待回测完成...")
            
            stream_complete_received = False
            final_data = {}
            
            for i in range(120):
                await asyncio.sleep(1)
                
                # 检查 console 日志中是否有 stream_complete
                for log in console_logs[-10:]:  # 只检查最近10条
                    if 'stream_complete' in log and 'totalReturn' in log:
                        stream_complete_received = True
                        # 尝试解析数据
                        try:
                            # 从日志中提取 JSON 数据
                            import re
                            match = re.search(r'\{.*totalReturn.*\}', log)
                            if match:
                                final_data = json.loads(match.group())
                        except:
                            pass
                
                # 检查 UI 状态
                metrics_panel = await page.locator("text=累计收益").count()
                
                if i % 10 == 0:
                    print(f"  {i}s: metrics_panel={metrics_panel}, stream_complete={stream_complete_received}")
                
                if stream_complete_received:
                    print(f"  [OK] 收到 stream_complete 事件!")
                    break
            
            # 5. 截图
            await page.screenshot(path="sandbox/backtest_final.png", full_page=True)
            print("\n[5] 截图已保存: sandbox/backtest_final.png")
            
            # 6. 获取指标数值
            print("\n[6] 获取指标数值...")
            
            # 尝试从页面获取指标
            metrics = {}
            
            try:
                # 使用更通用的选择器
                page_text = await page.content()
                
                # 从 console 日志中提取 stream_complete 数据
                for log in console_logs:
                    if 'stream_complete' in log and 'finalEquity' in log:
                        print(f"  找到 stream_complete 日志:")
                        print(f"    {log[:500]}")
            except Exception as e:
                print(f"  [WARN] 获取指标失败: {e}")
            
            # 7. 输出结果
            print("\n" + "=" * 80)
            print("测试结果")
            print("=" * 80)
            
            # 从 console 日志中提取关键数据
            print("\n关键日志:")
            for log in console_logs:
                if any(kw in log for kw in ['stream_complete', 'finalEquity', 'totalReturn', 'trades', 'equityCurve']):
                    print(f"  {log[:200]}")
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await asyncio.sleep(2)
            await browser.close()

if __name__ == '__main__':
    asyncio.run(test_backtest())
