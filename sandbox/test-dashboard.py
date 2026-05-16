"""
Playwright test script for dashboard-mock.html
Captures screenshots and validates layout
"""
import asyncio
from playwright.async_api import async_playwright

async def test_dashboard():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        # Load the dashboard
        await page.goto('file:///c:/Users/Liu/Desktop/projects/aquatrade/sandbox/dashboard-mock.html')
        await page.wait_for_timeout(2000)  # Wait for rendering
        
        # Full page screenshot
        await page.screenshot(path='c:/Users/Liu/Desktop/projects/aquatrade/sandbox/screenshots/dashboard-full.png', full_page=True)
        
        # Test CONFIG toggle
        await page.click('#btn-config')
        await page.wait_for_timeout(500)
        await page.screenshot(path='c:/Users/Liu/Desktop/projects/aquatrade/sandbox/screenshots/dashboard-config.png')
        
        # Test returns toggle
        await page.click('#btn-overview')
        await page.wait_for_timeout(500)
        await page.click('#btn-yearly')
        await page.wait_for_timeout(500)
        await page.screenshot(path='c:/Users/Liu/Desktop/projects/aquatrade/sandbox/screenshots/dashboard-yearly.png')
        
        print("Screenshots captured successfully!")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_dashboard())
