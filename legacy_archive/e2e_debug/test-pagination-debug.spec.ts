import { test, expect } from '@playwright/test';

test('debug pagination', async ({ page }) => {
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(3000);
  
  // 截图
  await page.screenshot({ path: 'e2e/screenshots/debug-pagination.png', fullPage: false });
  
  // 获取分页组件的HTML
  const paginationHtml = await page.locator('.ant-pagination').first().innerHTML();
  console.log('Pagination HTML:', paginationHtml.substring(0, 500));
  
  // 获取所有分页按钮
  const pageButtons = await page.locator('.ant-pagination-item').all();
  console.log('Number of page buttons:', pageButtons.length);
  
  for (let i = 0; i < Math.min(pageButtons.length, 5); i++) {
    const text = await pageButtons[i].textContent();
    const isActive = await pageButtons[i].evaluate(el => el.classList.contains('ant-pagination-item-active'));
    console.log(`Button ${i}: ${text}, active: ${isActive}`);
  }
  
  // 检查是否有数据
  const rows = await page.locator('.ant-table-tbody tr').all();
  console.log('Number of data rows:', rows.length);
  
  if (rows.length > 0) {
    const firstRowText = await rows[0].textContent();
    console.log('First row content:', firstRowText?.substring(0, 100));
  }
});
