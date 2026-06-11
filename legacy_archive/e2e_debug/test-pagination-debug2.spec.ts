import { test, expect } from '@playwright/test';

test('debug pagination with logs', async ({ page }) => {
  // 监听控制台日志
  page.on('console', msg => {
    console.log(`[${msg.type()}] ${msg.text()}`);
  });
  
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(2000);
  
  // 点击"执行筛选"按钮获取数据
  const filterButton = await page.locator('button:has-text("执行筛选")').first();
  await filterButton.click();
  
  // 等待数据加载
  await page.waitForTimeout(3000);
  
  // 截图初始状态
  await page.screenshot({ path: 'e2e/screenshots/debug2-page1.png', fullPage: false });
  
  // 获取第1页的第一行数据（用dataIndex来获取股票代码）
  const firstRowPage1 = await page.locator('.ant-table-tbody tr:first-child td[data-column-key="stock_code"]').textContent();
  console.log('First row stock code on page 1:', firstRowPage1?.trim() || 'EMPTY');
  
  // 获取当前页码
  const activePage1 = await page.locator('.ant-pagination-item-active').textContent();
  console.log('Active page before click:', activePage1);
  
  // 点击第2页
  const page2Button = await page.locator('.ant-pagination-item-2').first();
  await page2Button.click();
  
  // 等待更长时间
  await page.waitForTimeout(3000);
  
  // 截图第2页
  await page.screenshot({ path: 'e2e/screenshots/debug2-page2.png', fullPage: false });
  
  // 获取当前页码
  const activePage2 = await page.locator('.ant-pagination-item-active').textContent();
  console.log('Active page after click:', activePage2);
  
  // 获取第2页的第一行数据
  const firstRowPage2 = await page.locator('.ant-table-tbody tr:first-child td[data-column-key="stock_code"]').textContent();
  console.log('First row stock code on page 2:', firstRowPage2?.trim() || 'EMPTY');
  
  // 检查表格行数
  const rows = await page.locator('.ant-table-tbody tr').all();
  console.log('Number of rows:', rows.length);
});
