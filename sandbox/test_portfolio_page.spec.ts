import { test, expect } from '@playwright/test';

test('portfolio page should show positions', async ({ page }) => {
  // 访问持仓页面
  await page.goto('http://localhost:5173/portfolio');
  
  // 等待页面加载
  await page.waitForTimeout(3000);
  
  // 检查是否有持仓数据
  const tableBody = page.locator('table tbody');
  const rows = await tableBody.locator('tr').count();
  
  console.log(`Found ${rows} rows in table`);
  
  // 截图
  await page.screenshot({ path: 'portfolio-test.png', fullPage: true });
  
  // 打印页面内容
  const content = await page.content();
  console.log('Page contains "暂无持仓":', content.includes('暂无持仓'));
  console.log('Page contains "平安银行":', content.includes('平安银行'));
});
