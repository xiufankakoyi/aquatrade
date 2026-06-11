import { test, expect } from '@playwright/test';

test('debug table scroll issue', async ({ page }) => {
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(3000);
  
  // 截图初始状态
  await page.screenshot({ path: 'e2e/screenshots/1-initial.png', fullPage: false });
  
  // 获取关键元素
  const elements = await page.evaluate(() => {
    const results: any = {};
    
    // 检查 ant-col-16
    const col16 = document.querySelector('.ant-col-16');
    if (col16) {
      results.col16 = {
        scrollWidth: col16.scrollWidth,
        clientWidth: col16.clientWidth,
        offsetWidth: col16.offsetWidth,
        scrollLeft: col16.scrollLeft,
        computedStyle: {
          overflowX: window.getComputedStyle(col16).overflowX,
          maxWidth: window.getComputedStyle(col16).maxWidth,
          width: window.getComputedStyle(col16).width
        }
      };
    }
    
    // 检查 table-card
    const tableCard = document.querySelector('.table-card');
    if (tableCard) {
      results.tableCard = {
        scrollWidth: tableCard.scrollWidth,
        clientWidth: tableCard.clientWidth,
        offsetWidth: tableCard.offsetWidth,
        computedStyle: {
          overflowX: window.getComputedStyle(tableCard).overflowX,
          width: window.getComputedStyle(tableCard).width
        }
      };
    }
    
    // 检查 ant-table-wrapper
    const wrapper = document.querySelector('.table-card .ant-table-wrapper');
    if (wrapper) {
      results.wrapper = {
        scrollWidth: wrapper.scrollWidth,
        clientWidth: wrapper.clientWidth,
        offsetWidth: wrapper.offsetWidth,
        computedStyle: {
          overflowX: window.getComputedStyle(wrapper).overflowX,
          width: window.getComputedStyle(wrapper).width
        }
      };
    }
    
    // 检查 ant-table
    const table = document.querySelector('.dark-table .ant-table');
    if (table) {
      results.table = {
        scrollWidth: table.scrollWidth,
        clientWidth: table.clientWidth,
        offsetWidth: table.offsetWidth,
        computedStyle: {
          width: window.getComputedStyle(table).width,
          tableLayout: window.getComputedStyle(table).tableLayout
        }
      };
    }
    
    return results;
  });
  
  console.log('Elements analysis:', JSON.stringify(elements, null, 2));
  
  // 尝试在 ant-col-16 上滚动
  const col16 = await page.locator('.ant-col-16').first();
  await col16.evaluate(el => el.scrollLeft = 1000);
  await page.waitForTimeout(500);
  
  const scrollLeftAfter = await col16.evaluate(el => el.scrollLeft);
  console.log('Scroll left after manual scroll:', scrollLeftAfter);
  
  // 截图滚动后
  await page.screenshot({ path: 'e2e/screenshots/2-after-scroll.png', fullPage: false });
  
  // 检查是否有滚动条可见
  const hasScrollbar = await col16.evaluate(el => {
    return el.scrollWidth > el.clientWidth;
  });
  console.log('Has horizontal scrollbar:', hasScrollbar);
});
