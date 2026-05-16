"""
Playwright 自动化测试回测功能
"""
import asyncio
import json
import time
from playwright.async_api import async_playwright

async def test_backtest():
    print("=" * 60)
    print("Playwright 自动化回测测试")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 收集 console 日志
        console_logs = []
        def handle_console(msg):
            console_logs.append(f"[{msg.type}] {msg.text}")
            print(f"[Console] {msg.type}: {msg.text[:200]}")
        
        page.on("console", handle_console)
        
        # 收集网络请求
        network_logs = []
        def handle_response(response):
            if 'socket.io' in response.url or 'backtest' in response.url:
                network_logs.append(f"[Response] {response.url}")
        
        page.on("response", handle_response)
        
        try:
            # 1. 打开 Dashboard 页面
            print("\n[1] 打开 Dashboard 页面...")
            await page.goto("http://localhost:5173/dashboard", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 2. 等待策略列表加载
            print("[2] 等待策略列表加载...")
            await asyncio.sleep(2)
            
            # 查找策略选择器
            strategy_selectors = [
                "text=聚宽量比",
                "text=simple_volume",
                "[class*='strategy']",
                "select option",
            ]
            
            strategy_found = False
            for selector in strategy_selectors:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"  找到策略选择器: {selector}, count={count}")
                    strategy_found = True
                    break
            
            if not strategy_found:
                print("  [WARN] 未找到策略选择器，尝试直接点击回测按钮")
            
            # 3. 点击策略选择（如果存在下拉框）
            print("[3] 选择策略...")
            try:
                # 尝试找到策略下拉框
                select_el = page.locator("select").first
                if await select_el.count() > 0:
                    # 获取所有选项
                    options = await select_el.locator("option").all_text_contents()
                    print(f"  可用策略: {options}")
                    # 选择第一个非默认选项
                    for i, opt in enumerate(options):
                        if opt and opt != "选择策略" and opt != "":
                            await select_el.select_option(index=i)
                            print(f"  已选择策略: {opt}")
                            break
            except Exception as e:
                print(f"  [WARN] 策略选择失败: {e}")
            
            # 4. 点击回测按钮
            print("[4] 点击回测按钮...")
            
            # 查找回测按钮
            backtest_btn_selectors = [
                "button:has-text('回测')",
                "button:has-text('开始回测')",
                "button:has-text('运行')",
                "[class*='backtest'] button",
            ]
            
            btn_clicked = False
            for selector in backtest_btn_selectors:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    print(f"  找到回测按钮: {selector}")
                    await btn.click()
                    btn_clicked = True
                    print("  已点击回测按钮")
                    break
            
            if not btn_clicked:
                print("  [ERROR] 未找到回测按钮!")
                await page.screenshot(path="sandbox/backtest_no_btn.png", full_page=True)
                return False
            
            # 5. 等待回测完成（最多等待 120 秒）
            print("[5] 等待回测完成...")
            
            # 等待进度条出现并完成
            for i in range(120):
                await asyncio.sleep(1)
                
                # 检查是否有错误
                error_text = await page.locator("text=错误").count()
                if error_text > 0:
                    print(f"[ERROR] 发现错误提示!")
                    break
                
                # 检查进度
                progress = await page.locator("[class*='progress']").count()
                
                # 检查是否显示数据
                metrics_panel = await page.locator("text=累计收益").count()
                
                if metrics_panel > 0:
                    print(f"[OK] 回测完成，检测到指标面板")
                    break
                
                if i % 10 == 0:
                    print(f"  等待中... {i}s")
            
            await asyncio.sleep(3)
            
            # 6. 验证数据
            print("\n[6] 验证回测数据...")
            
            # 截图
            await page.screenshot(path="sandbox/backtest_screenshot.png", full_page=True)
            print("  截图已保存: sandbox/backtest_screenshot.png")
            
            # 获取指标数值
            metrics = {}
            
            # 尝试获取累计收益
            try:
                total_return_el = page.locator("text=累计收益").locator("..").locator("div").nth(1)
                total_return = await total_return_el.text_content()
                metrics['累计收益'] = total_return
                print(f"  累计收益: {total_return}")
            except Exception as e:
                print(f"  [WARN] 无法获取累计收益: {e}")
            
            # 尝试获取最大回撤
            try:
                max_dd_el = page.locator("text=最大回撤").locator("..").locator("div").nth(1)
                max_dd = await max_dd_el.text_content()
                metrics['最大回撤'] = max_dd
                print(f"  最大回撤: {max_dd}")
            except Exception as e:
                print(f"  [WARN] 无法获取最大回撤: {e}")
            
            # 尝试获取夏普比率
            try:
                sharpe_el = page.locator("text=夏普比率").locator("..").locator("div").nth(1)
                sharpe = await sharpe_el.text_content()
                metrics['夏普比率'] = sharpe
                print(f"  夏普比率: {sharpe}")
            except Exception as e:
                print(f"  [WARN] 无法获取夏普比率: {e}")
            
            # 尝试获取卡尔玛比率
            try:
                calmar_el = page.locator("text=卡尔玛比率").locator("..").locator("div").nth(1)
                calmar = await calmar_el.text_content()
                metrics['卡尔玛比率'] = calmar
                print(f"  卡尔玛比率: {calmar}")
            except Exception as e:
                print(f"  [WARN] 无法获取卡尔玛比率: {e}")
            
            # 尝试获取基准收益
            try:
                benchmark_el = page.locator("text=基准收益").locator("..").locator("div").nth(1)
                benchmark = await benchmark_el.text_content()
                metrics['基准收益'] = benchmark
                print(f"  基准收益: {benchmark}")
            except Exception as e:
                print(f"  [WARN] 无法获取基准收益: {e}")
            
            # 尝试获取交易次数
            try:
                trades_el = page.locator("text=交易次数").locator("..").locator("div").nth(1)
                trades = await trades_el.text_content()
                metrics['交易次数'] = trades
                print(f"  交易次数: {trades}")
            except Exception as e:
                print(f"  [WARN] 无法获取交易次数: {e}")
            
            # 检查收益分布
            monthly_returns = await page.locator("text=收益分布").count()
            print(f"  收益分布模块: {'存在' if monthly_returns > 0 else '不存在'}")
            
            # 检查是否有"暂无数据"
            no_data = await page.locator("text=暂无收益分布数据").count()
            print(f"  暂无数据提示: {'存在' if no_data > 0 else '不存在'}")
            
            # 7. 验证结果
            print("\n[7] 验证结果...")
            
            issues = []
            
            # 检查累计收益是否为 0
            if '累计收益' in metrics:
                if '+0.00%' in metrics['累计收益'] or '-0.00%' in metrics['累计收益']:
                    issues.append("累计收益为 0")
            
            # 检查最大回撤是否为 0
            if '最大回撤' in metrics:
                if '+0.00%' in metrics['最大回撤'] or '-0.00%' in metrics['最大回撤']:
                    issues.append("最大回撤为 0")
            
            # 检查卡尔玛比率是否为 0
            if '卡尔玛比率' in metrics:
                if '0.00' == metrics['卡尔玛比率'].strip():
                    issues.append("卡尔玛比率为 0")
            
            # 检查基准收益是否为 0
            if '基准收益' in metrics:
                if '+0.00%' in metrics['基准收益'] or '-0.00%' in metrics['基准收益']:
                    issues.append("基准收益为 0")
            
            # 检查交易次数是否为 0
            if '交易次数' in metrics:
                if '0' == metrics['交易次数'].strip():
                    issues.append("交易次数为 0")
            
            # 检查收益分布
            if no_data > 0:
                issues.append("收益分布暂无数据")
            
            if issues:
                print(f"\n[FAIL] 发现问题:")
                for issue in issues:
                    print(f"  - {issue}")
            else:
                print(f"\n[OK] 所有数据正常!")
            
            # 输出 console 日志中的关键信息
            print("\n[Console 日志摘要]:")
            for log in console_logs[-20:]:
                if 'stream_complete' in log or 'equityCurve' in log or 'benchmarkCurve' in log or 'metrics' in log.lower():
                    print(f"  {log[:150]}")
            
            print("\n" + "=" * 60)
            print("测试完成")
            print("=" * 60)
            
            return len(issues) == 0
            
        except Exception as e:
            print(f"\n[ERROR] 测试失败: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="sandbox/backtest_error_screenshot.png", full_page=True)
            return False
        
        finally:
            await asyncio.sleep(2)
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(test_backtest())
    exit(0 if result else 1)
