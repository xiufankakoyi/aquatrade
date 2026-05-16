"""
Playwright 诊断脚本 - 检查前端 Socket.IO 连接和回测流程
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def diagnose():
    print("=" * 80)
    print("Playwright 诊断脚本")
    print("=" * 80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 收集所有 console 日志
        all_logs = []
        def handle_console(msg):
            log_entry = f"[{msg.type}] {msg.text}"
            all_logs.append(log_entry)
            print(f"[Console] {msg.type}: {msg.text[:300]}")
        
        page.on("console", handle_console)
        
        # 收集网络请求
        network_logs = []
        def handle_request(request):
            if 'socket.io' in request.url or 'backtest' in request.url or 'api' in request.url:
                network_logs.append(f"[Request] {request.method} {request.url}")
                print(f"[Network] {request.method} {request.url[:100]}")
        
        page.on("request", handle_request)
        
        try:
            # 1. 打开页面
            print("\n[1] 打开 Dashboard 页面...")
            await page.goto("http://localhost:5173/dashboard", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # 2. 检查 Socket.IO 连接状态
            print("\n[2] 检查 Socket.IO 连接状态...")
            socket_status = await page.evaluate("""
                () => {
                    // 检查全局变量
                    const result = {
                        windowKeys: Object.keys(window).filter(k => k.includes('socket') || k.includes('Socket')),
                        localStorage: {},
                    };
                    
                    // 检查 localStorage
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key.includes('socket') || key.includes('backtest')) {
                            result.localStorage[key] = localStorage.getItem(key);
                        }
                    }
                    
                    return result;
                }
            """)
            print(f"  Socket 相关 window 键: {socket_status['windowKeys']}")
            print(f"  Socket 相关 localStorage: {socket_status['localStorage']}")
            
            # 3. 查找策略选择器和回测按钮
            print("\n[3] 查找 UI 元素...")
            
            # 查找所有按钮
            buttons = await page.locator("button").all()
            print(f"  找到 {len(buttons)} 个按钮")
            for i, btn in enumerate(buttons[:10]):  # 只显示前10个
                try:
                    text = await btn.text_content()
                    if text and ('回测' in text or '运行' in text or '开始' in text):
                        print(f"    按钮 {i}: '{text}'")
                except:
                    pass
            
            # 查找策略选择器
            selects = await page.locator("select").all()
            print(f"  找到 {len(selects)} 个下拉框")
            for i, sel in enumerate(selects):
                try:
                    options = await sel.locator("option").all_text_contents()
                    print(f"    下拉框 {i}: {options[:5]}")  # 只显示前5个选项
                except:
                    pass
            
            # 4. 尝试点击回测按钮
            print("\n[4] 尝试点击回测按钮...")
            
            # 查找包含"回测"文字的按钮
            backtest_btns = page.locator("button:has-text('回测')")
            btn_count = await backtest_btns.count()
            print(f"  找到 {btn_count} 个包含'回测'的按钮")
            
            if btn_count > 0:
                # 点击第一个回测按钮
                await backtest_btns.first.click()
                print("  已点击回测按钮")
                
                # 等待并观察
                print("\n[5] 等待回测响应...")
                for i in range(30):
                    await asyncio.sleep(1)
                    
                    # 检查是否有进度或错误
                    progress = await page.locator("[class*='progress']").count()
                    error = await page.locator("text=错误").count()
                    metrics = await page.locator("text=累计收益").count()
                    
                    if i % 5 == 0:
                        print(f"  {i}s: progress={progress}, error={error}, metrics={metrics}")
                    
                    if metrics > 0:
                        print(f"  [OK] 检测到指标面板!")
                        break
                    
                    if error > 0:
                        print(f"  [ERROR] 检测到错误!")
                        break
                
                # 截图
                await page.screenshot(path="sandbox/diagnose_screenshot.png", full_page=True)
                print("  截图已保存: sandbox/diagnose_screenshot.png")
            else:
                print("  [ERROR] 未找到回测按钮!")
            
            # 6. 输出所有日志
            print("\n[6] 日志摘要...")
            
            # 过滤关键日志
            key_logs = [log for log in all_logs if any(kw in log for kw in [
                'socket', 'Socket', 'connect', 'backtest', 'stream', 'error', 'Error'
            ])]
            
            print("  关键日志:")
            for log in key_logs[-20:]:  # 只显示最后20条
                print(f"    {log[:150]}")
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await asyncio.sleep(2)
            await browser.close()

if __name__ == '__main__':
    asyncio.run(diagnose())
