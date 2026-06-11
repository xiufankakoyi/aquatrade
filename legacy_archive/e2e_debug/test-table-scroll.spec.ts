import { test, expect } from '@playwright/test';

test('check table horizontal scroll', async ({ page }) => {
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(3000);
  
  // 截图查看整体布局
  await page.screenshot({ path: 'e2e/screenshots/full-page.png', fullPage: false });
  
  // 获取表格容器信息
  const tableWrapper = await page.locator('.table-card .ant-table-wrapper').first();
  const table = await page.locator('.table-card .ant-table').first();
  const tableContainer = await page.locator('.table-card .ant-table-container').first();
  
  // 获取尺寸信息
  const wrapperBox = await tableWrapper.boundingBox();
  const tableBox = await table.boundingBox();
  const containerBox = await tableContainer.boundingBox();
  
  console.log('Table Wrapper:', wrapperBox);
  console.log('Table:', tableBox);
  console.log('Table Container:', containerBox);
  
  // 获取表格内容宽度
  const scrollWidth = await table.evaluate(el => el.scrollWidth);
  const clientWidth = await table.evaluate(el => el.clientWidth);
  
  console.log('Table scrollWidth:', scrollWidth);
  console.log('Table clientWidth:', clientWidth);
  console.log('Should scroll:', scrollWidth > clientWidth);
  
  // 获取所有列
  const headers = await page.locator('.ant-table-thead th').all();
  console.log('Total columns:', headers.length);
  
  for (let i = 0; i < Math.min(headers.length, 5); i++) {
    const text = await headers[i].textContent();
    const box = await headers[i].boundingBox();
    console.log(`Column ${i}: ${text} - width: ${box?.width}`);
  }
  
  // 检查是否有横向滚动条
  const hasScroll = await tableWrapper.evaluate(el => {
    return el.scrollWidth > el.clientWidth;
  });
  console.log('Wrapper has horizontal scroll:', hasScroll);
  
  // 尝试滚动
  await tableWrapper.evaluate(el => {
    el.scrollLeft = 500;
  });
  
  await page.waitForTimeout(500);
  
  // 截图查看滚动后的效果
  await page.screenshot({ path: 'e2e/screenshots/after-scroll.png', fullPage: false });
  
  // 获取滚动后的位置
  const scrollLeft = await tableWrapper.evaluate(el => el.scrollLeft);
  console.log('Scroll left after scroll:', scrollLeft);
});
