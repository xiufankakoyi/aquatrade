import { test, expect } from '@playwright/test';

test('check console errors', async ({ page }) => {
  // 收集控制台错误
  const consoleErrors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  
  // 收集页面错误
  const pageErrors: string[] = [];
  page.on('pageerror', error => {
    pageErrors.push(error.message);
  });
  
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(3000);
  
  // 截图
  await page.screenshot({ path: 'e2e/screenshots/console-errors.png', fullPage: false });
  
  // 输出错误
  console.log('Console errors:', consoleErrors);
  console.log('Page errors:', pageErrors);
  
  // 获取页面文本内容
  const bodyText = await page.locator('body').textContent();
  console.log('Body text:', bodyText?.substring(0, 200));
});
