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
  
  // 在浏览器控制台执行测试代码
  const result = await page.evaluate(() => {
    // 查找子菜单项
    const submenuItem = document.querySelector('.submenu-item:has(.fa-slash)');
    console.log('Submenu item found:', !!submenuItem);
    
    if (submenuItem) {
      console.log('Submenu item HTML:', submenuItem.outerHTML);
      console.log('Submenu item click handler:', submenuItem.onclick);
      
      // 检查是否有 Vue 事件绑定
      const vueEvents = submenuItem.__vueParentComponent?.ctx;
      console.log('Vue context:', vueEvents);
      
      // 手动触发点击
      submenuItem.click();
      console.log('Manually clicked submenu item');
    }
    
    return { found: !!submenuItem };
  });
  
  console.log('Evaluation result:', result);
  
  // 等待一段时间
  await page.waitForTimeout(3000);
  
  await browser.close();
})();
