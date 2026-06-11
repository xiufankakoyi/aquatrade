import { test, expect } from '@playwright/test';

test('verify pagination with data', async ({ page }) => {
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
  await page.screenshot({ path: 'e2e/screenshots/pagination-full-page1.png', fullPage: false });
  
  // 检查数据是否加载
  const totalText = await page.locator('.ant-pagination-total-text').first().textContent();
  console.log('Total records:', totalText);
  
  // 获取第1页的第一行股票代码
  const firstRowPage1 = await page.locator('.ant-table-tbody tr:first-child td:nth-child(2)').textContent();
  console.log('First row stock code on page 1:', firstRowPage1?.trim());
  
  // 获取分页按钮数量
  const pageButtons = await page.locator('.ant-pagination-item').all();
  console.log('Number of page buttons:', pageButtons.length);
  
  if (pageButtons.length < 2) {
    console.log('Not enough pages to test pagination');
    return;
  }
  
  // 点击第2页
  await pageButtons[1].click();
  
  // 等待数据加载
  await page.waitForTimeout(2000);
  
  // 截图第2页
  await page.screenshot({ path: 'e2e/screenshots/pagination-full-page2.png', fullPage: false });
  
  // 获取第2页的第一行股票代码
  const firstRowPage2 = await page.locator('.ant-table-tbody tr:first-child td:nth-child(2)').textContent();
  console.log('First row stock code on page 2:', firstRowPage2?.trim());
  
  // 验证数据是否不同
  const isDifferent = firstRowPage1?.trim() !== firstRowPage2?.trim();
  console.log('Data changed after pagination:', isDifferent);
  
  // 验证第2页是否高亮
  const isPage2Active = await pageButtons[1].evaluate(el => el.classList.contains('ant-pagination-item-active'));
  console.log('Page 2 is active:', isPage2Active);
  
  // 断言
  expect(isDifferent, 'Page 2 data should be different from Page 1').toBe(true);
  expect(isPage2Active, 'Page 2 should be active').toBe(true);
});
