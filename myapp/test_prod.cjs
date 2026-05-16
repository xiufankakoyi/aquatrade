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
  
  // 检查子菜单项的 HTML
  const result = await page.evaluate(() => {
    const submenuItem = document.querySelector('.submenu-item:has(.fa-slash)');
    console.log('Submenu item HTML:', submenuItem?.outerHTML);
    return { found: !!submenuItem, html: submenuItem?.outerHTML };
  });
  
  console.log('Result:', result);
  
  // 等待一段时间
  await page.waitForTimeout(3000);
  
  await browser.close();
})();
