import { test, expect } from '@playwright/test';

test('verify pagination works correctly', async ({ page }) => {
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(3000);
  
  // 截图初始状态（第1页）
  await page.screenshot({ path: 'e2e/screenshots/pagination-page1.png', fullPage: false });
  
  // 获取第1页的第一行数据
  const firstRowPage1 = await page.locator('.ant-table-tbody tr:first-child td:nth-child(2)').textContent();
  console.log('First row stock code on page 1:', firstRowPage1);
  
  // 点击第2页
  const page2Button = await page.locator('.ant-pagination-item-2').first();
  await page2Button.click();
  
  // 等待数据加载
  await page.waitForTimeout(2000);
  
  // 截图第2页
  await page.screenshot({ path: 'e2e/screenshots/pagination-page2.png', fullPage: false });
  
  // 获取第2页的第一行数据
  const firstRowPage2 = await page.locator('.ant-table-tbody tr:first-child td:nth-child(2)').textContent();
  console.log('First row stock code on page 2:', firstRowPage2);
  
  // 验证数据是否不同
  const isDifferent = firstRowPage1 !== firstRowPage2;
  console.log('Data changed after pagination:', isDifferent);
  
  // 验证当前页码是否高亮
  const page2Active = await page.locator('.ant-pagination-item-2.ant-pagination-item-active').count();
  console.log('Page 2 is active:', page2Active > 0);
  
  // 点击下一页按钮
  const nextButton = await page.locator('.ant-pagination-next').first();
  await nextButton.click();
  
  // 等待数据加载
  await page.waitForTimeout(2000);
  
  // 截图第3页
  await page.screenshot({ path: 'e2e/screenshots/pagination-page3.png', fullPage: false });
  
  // 获取第3页的第一行数据
  const firstRowPage3 = await page.locator('.ant-table-tbody tr:first-child td:nth-child(2)').textContent();
  console.log('First row stock code on page 3:', firstRowPage3);
  
  // 验证第3页数据与第2页不同
  const isDifferent3 = firstRowPage2 !== firstRowPage3;
  console.log('Data changed from page 2 to 3:', isDifferent3);
  
  // 断言验证
  expect(isDifferent, 'Page 2 data should be different from Page 1').toBe(true);
  expect(isDifferent3, 'Page 3 data should be different from Page 2').toBe(true);
});
