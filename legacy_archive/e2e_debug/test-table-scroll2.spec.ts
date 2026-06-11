import { test, expect } from '@playwright/test';

test('check table horizontal scroll - detailed', async ({ page }) => {
  // 访问页面
  await page.goto('http://localhost:5173/stock-screener');
  
  // 等待页面加载完成
  await page.waitForTimeout(3000);
  
  // 获取表格的 scroll.x 属性值
  const scrollXValue = await page.evaluate(() => {
    // 查找 a-table 组件实例
    const tableEl = document.querySelector('.dark-table');
    if (tableEl) {
      // 获取 Vue 组件实例
      const vueInstance = (tableEl as any).__vueParentComponent;
      console.log('Vue instance:', vueInstance);
      return vueInstance?.props?.scroll;
    }
    return null;
  });
  
  console.log('Scroll config:', scrollXValue);
  
  // 获取表格实际宽度
  const tableEl = await page.locator('.dark-table .ant-table').first();
  const tableWidth = await tableEl.evaluate(el => {
    return {
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      offsetWidth: el.offsetWidth,
      style: el.style.cssText
    };
  });
  console.log('Table width info:', tableWidth);
  
  // 获取表格内容
  const content = await tableEl.evaluate(el => el.innerHTML);
  console.log('Table HTML length:', content.length);
  
  // 截图
  await page.screenshot({ path: 'e2e/screenshots/table-debug.png', fullPage: false });
});
