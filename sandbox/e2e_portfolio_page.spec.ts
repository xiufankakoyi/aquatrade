import { test, expect } from '@playwright/test';

test('portfolio page debug', async ({ page }) => {
  // 监听控制台消息
  page.on('console', msg => {
    if (msg.text().includes('portfolio') || msg.text().includes('position') || msg.text().includes('API')) {
      console.log(`[Browser ${msg.type()}] ${msg.text()}`);
    }
  });
  
  // 访问持仓页面
  await page.goto('http://localhost:5173/portfolio');
  
  // 等待页面加载
  await page.waitForTimeout(5000);
  
  // 直接检查 DOM
  const tableRows = await page.locator('table tbody tr').allTextContents();
  console.log('Table rows:', tableRows);
  
  // 检查是否有持仓数据
  const hasData = await page.locator('table tbody tr td').first().textContent();
  console.log('First cell content:', hasData);
});
