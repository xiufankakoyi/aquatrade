import asyncio
from playwright.async_api import async_playwright

async def test_dashboard():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        # Load dashboard v2
        await page.goto('file:///c:/Users/Liu/Desktop/projects/aquatrade/sandbox/dashboard-v2.html')
        await page.wait_for_timeout(2000)
        
        # Screenshot full dashboard
        await page.screenshot(path='c:/Users/Liu/Desktop/projects/aquatrade/sandbox/screenshots/v2-full.png', full_page=True)
        print("✓ Full dashboard captured")
        
        # Test config toggle
        await page.click('#btn-config')
        await page.wait_for_timeout(500)
        await page.screenshot(path='c:/Users/Liu/Desktop/projects/aquatrade/sandbox/screenshots/v2-config.png')
        print("✓ Config panel captured")
        
        # Switch back to overview
        await page.click('#btn-overview')
        await page.wait_for_timeout(500)
        
        # Test yearly returns toggle
        await page.click('#ret-yearly')
        await page.wait_for_timeout(500)
        await page.screenshot(path='c:/Users/Liu/Desktop/projects/aquatrade/sandbox/screenshots/v2-yearly.png')
        print("✓ Yearly returns captured")
        
        # Test hover interaction on equity chart
        equity_chart = await page.query_selector('#equity-chart')
        box = await equity_chart.bounding_box()
        await page.mouse.move(box['x'] + box['width'] * 0.5, box['y'] + box['height'] * 0.5)
        await page.wait_for_timeout(300)
        await page.screenshot(path='c:/Users/Liu/Desktop/projects/aquatrade/sandbox/screenshots/v2-hover.png')
        print("✓ Hover interaction captured")
        
        print("\nAll screenshots saved to sandbox/screenshots/")
        await browser.close()

asyncio.run(test_dashboard())
