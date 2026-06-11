import { test, expect } from '@playwright/test';

test('check page state', async ({ page }) => {
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(3000);
  
  // 截图
  await page.screenshot({ path: 'e2e/screenshots/check-page-state.png', fullPage: false });
  
  // 获取页面HTML
  const bodyHtml = await page.locator('body').innerHTML();
  console.log('Body HTML length:', bodyHtml.length);
  
  // 查找执行筛选按钮
  const buttons = await page.locator('button').all();
  console.log('Number of buttons:', buttons.length);
  
  for (let i = 0; i < Math.min(buttons.length, 10); i++) {
    const text = await buttons[i].textContent();
    console.log(`Button ${i}: ${text?.trim()}`);
  }
  
  // 检查是否有加载状态
  const loading = await page.locator('.ant-spin').count();
  console.log('Loading spinners:', loading);
});
