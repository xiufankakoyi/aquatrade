import { test, expect } from '@playwright/test';

test('check table horizontal scroll - final', async ({ page }) => {
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(3000);
  
  // 获取 ant-col-16 容器
  const colContainer = await page.locator('.ant-col-16').first();
  const colBox = await colContainer.boundingBox();
  console.log('Col-16 container:', colBox);
  
  // 获取 table-card
  const tableCard = await page.locator('.table-card').first();
  const cardBox = await tableCard.boundingBox();
  console.log('Table card:', cardBox);
  
  // 获取 ant-table-wrapper
  const tableWrapper = await page.locator('.table-card .ant-table-wrapper').first();
  const wrapperBox = await tableWrapper.boundingBox();
  console.log('Table wrapper:', wrapperBox);
  
  // 检查 ant-col-16 的 scrollWidth vs clientWidth
  const colScrollInfo = await colContainer.evaluate(el => {
    return {
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      offsetWidth: el.offsetWidth
    };
  });
  console.log('Col-16 scroll info:', colScrollInfo);
  console.log('Should scroll:', colScrollInfo.scrollWidth > colScrollInfo.clientWidth);
  
  // 截图
  await page.screenshot({ path: 'e2e/screenshots/final-check.png', fullPage: false });
  
  // 尝试滚动 ant-col-16
  await colContainer.evaluate(el => {
    el.scrollLeft = 500;
  });
  
  await page.waitForTimeout(500);
  
  const scrollLeft = await colContainer.evaluate(el => el.scrollLeft);
  console.log('Scroll left after scroll:', scrollLeft);
  
  // 截图滚动后
  await page.screenshot({ path: 'e2e/screenshots/after-scroll-final.png', fullPage: false });
});
