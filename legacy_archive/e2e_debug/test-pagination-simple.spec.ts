import { test, expect } from '@playwright/test';

test('simple pagination test', async ({ page }) => {
  // 收集API请求
  const apiRequests: number[] = [];
  page.on('request', request => {
    const url = request.url();
    if (url.includes('/api/screener/filter')) {
      const postData = request.postDataJSON();
      apiRequests.push(postData?.page || 1);
      console.log(`API Request - Page: ${postData?.page}, PageSize: ${postData?.page_size}`);
    }
  });
  
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  await page.waitForTimeout(2000);
  
  // 点击"执行筛选"按钮
  const filterButton = await page.locator('button:has-text("执行筛选")').first();
  await filterButton.click();
  await page.waitForTimeout(3000);
  
  console.log('Requests after filter:', apiRequests);
  expect(apiRequests[apiRequests.length - 1]).toBe(1);
  
  // 点击第2页
  const page2Button = await page.locator('.ant-pagination-item-2').first();
  await page2Button.click();
  await page.waitForTimeout(3000);
  
  console.log('Requests after page 2 click:', apiRequests);
  
  // 验证最后一次请求是第2页
  const lastPage = apiRequests[apiRequests.length - 1];
  console.log('Last requested page:', lastPage);
  expect(lastPage).toBe(2);
  
  // 点击第3页
  const page3Button = await page.locator('.ant-pagination-item-3').first();
  await page3Button.click();
  await page.waitForTimeout(3000);
  
  console.log('Requests after page 3 click:', apiRequests);
  expect(apiRequests[apiRequests.length - 1]).toBe(3);
  
  console.log('✅ Pagination is working correctly!');
});
