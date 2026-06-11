import { test, expect } from '@playwright/test';

test('final pagination verification', async ({ page }) => {
  // 收集API请求
  const apiRequests: { url: string; postData: any }[] = [];
  page.on('request', request => {
    const url = request.url();
    if (url.includes('/api/screener/filter')) {
      const postData = request.postDataJSON();
      apiRequests.push({ url, postData });
      console.log('API Request page:', postData?.page);
    }
  });
  
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  await page.waitForTimeout(2000);
  
  // 点击"执行筛选"按钮
  const filterButton = await page.locator('button:has-text("执行筛选")').first();
  await filterButton.click();
  await page.waitForTimeout(3000);
  
  // 获取第1页的第一个股票代码
  const firstStockPage1 = await page.locator('.ant-table-tbody tr:first-child td:nth-child(2) a').textContent();
  console.log('First stock on page 1:', firstStockPage1?.trim());
  
  // 清空请求记录
  apiRequests.length = 0;
  
  // 点击第2页
  const page2Button = await page.locator('.ant-pagination-item-2').first();
  await page2Button.click();
  await page.waitForTimeout(3000);
  
  // 获取第2页的第一个股票代码
  const firstStockPage2 = await page.locator('.ant-table-tbody tr:first-child td:nth-child(2) a').textContent();
  console.log('First stock on page 2:', firstStockPage2?.trim());
  
  // 验证请求中的page参数
  console.log('API request page param:', apiRequests[0]?.postData?.page);
  
  // 验证
  expect(apiRequests.length).toBeGreaterThan(0);
  expect(apiRequests[0]?.postData?.page).toBe(2);
  
  // 股票代码应该不同（如果数据正常的话）
  if (firstStockPage1 && firstStockPage2) {
    const isDifferent = firstStockPage1.trim() !== firstStockPage2.trim();
    console.log('Stock codes are different:', isDifferent);
    expect(isDifferent, 'Stock codes should be different on different pages').toBe(true);
  }
});
