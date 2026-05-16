const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  // 监听控制台日志
  page.on('console', msg => {
    console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
  });
  
  await page.goto('http://localhost:5173/strategy/strategy_001');
  
  // 等待页面加载
  await page.waitForTimeout(3000);
  
  // 截图查看当前状态
  await page.screenshot({ path: 'toolbar_test_1.png' });
  
  // 查找工具栏
  const toolbar = await page.$('.chart-toolbar');
  console.log('Toolbar found:', !!toolbar);
  
  if (toolbar) {
    // 查找趋势线工具按钮
    const trendLineBtn = await page.$('.has-submenu:has(.fa-chart-line)');
    console.log('TrendLine button found:', !!trendLineBtn);
    
    if (trendLineBtn) {
      // 悬停显示子菜单
      await trendLineBtn.hover();
      await page.waitForTimeout(500);
      
      // 截图
      await page.screenshot({ path: 'toolbar_test_2.png' });
      
      // 查找子菜单中的趋势线选项
      const submenuItem = await page.$('.submenu-item:has(.fa-slash)');
      console.log('Submenu item found:', !!submenuItem);
      
      if (submenuItem) {
        // 点击子菜单项
        await submenuItem.click();
        console.log('Clicked on submenu item');
        await page.waitForTimeout(1000);
        
        // 截图
        await page.screenshot({ path: 'toolbar_test_3.png' });
      }
    }
  }
  
  // 等待一段时间查看控制台输出
  await page.waitForTimeout(3000);
  
  await browser.close();
})();
