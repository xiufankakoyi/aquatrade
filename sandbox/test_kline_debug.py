"""
测试脚本：检查 K 线图数据加载问题
使用 Playwright 访问前端页面并检查控制台日志
"""

import asyncio
import json
from playwright.async_api import async_playwright

async def test_kline_chart():
    """测试 K 线图数据加载"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # 监听控制台日志
        console_logs = []
        def handle_console(msg):
            log_entry = {
                'type': msg.type,
                'text': msg.text
            }
            console_logs.append(log_entry)
            # 打印 K 线相关的日志
            if 'kline' in msg.text.lower() or 'socket' in msg.text.lower() or 'mock' in msg.text.lower():
                print(f"[浏览器控制台] [{msg.type}] {msg.text}")

        page.on("console", handle_console)

        try:
            # 访问前端页面
            print("[测试] 访问 http://localhost:5173/strategy/simple_volume_v3")
            await page.goto('http://localhost:5173/strategy/simple_volume_v3', wait_until='networkidle')

            # 等待页面加载
            await asyncio.sleep(5)

            # 检查页面是否有 K 线图
            kline_chart = await page.query_selector('[data-testid="kline-chart"]')
            if kline_chart:
                print("[测试] 找到 K 线图组件")
            else:
                print("[测试] 未找到 K 线图组件")

            # 检查页面内容
            page_content = await page.content()
            if 'kline' in page_content.lower():
                print("[测试] 页面内容包含 'kline'")

            # 等待一段时间，让 K 线数据加载
            print("[测试] 等待 10 秒，让 K 线数据加载...")
            await asyncio.sleep(10)

            # 检查控制台日志
            print("\n[测试] 所有控制台日志:")
            for log in console_logs:
                print(f"  [{log['type']}] {log['text'][:200]}")  # 只打印前200个字符

            # 关闭浏览器
            await browser.close()
            print("\n[测试] 测试完成")

        except Exception as e:
            print(f"[测试] 错误: {e}")
            import traceback
            traceback.print_exc()
            await browser.close()

if __name__ == '__main__':
    asyncio.run(test_kline_chart())
