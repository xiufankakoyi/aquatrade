import { test, expect } from '@playwright/test';

test('check network requests on pagination', async ({ page }) => {
  // 收集API请求
  const apiRequests: string[] = [];
  page.on('request', request => {
    const url = request.url();
    if (url.includes('/api/screener/filter')) {
      apiRequests.push(url);
      console.log('API Request:', url);
    }
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
  
  console.log('API requests after filter:', apiRequests.length);
  
  // 清空请求记录
  apiRequests.length = 0;
  
  // 点击第2页
  const page2Button = await page.locator('.ant-pagination-item-2').first();
  await page2Button.click();
  
  // 等待一段时间
  await page.waitForTimeout(2000);
  
  console.log('API requests after page 2 click:', apiRequests.length);
  
  // 检查是否有新的API请求
  if (apiRequests.length > 0) {
    console.log('New API requests:');
    apiRequests.forEach(url => console.log('  -', url));
  } else {
    console.log('No new API requests after pagination!');
  }
  
  // 验证应该有新的API请求
  expect(apiRequests.length, 'Pagination should trigger new API request').toBeGreaterThan(0);
});
