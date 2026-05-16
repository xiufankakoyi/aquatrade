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
  
  // 悬停到趋势线工具按钮
  const trendLineBtn = await page.$('.has-submenu:has(.fa-chart-line)');
  await trendLineBtn.hover();
  await page.waitForTimeout(500);
  
  // 查找并点击子菜单项
  const submenuItem = await page.$('.submenu-item:has(.fa-slash)');
  console.log('Clicking submenu item...');
  
  // 添加一个标记来确认点击是否工作
  await page.evaluate(() => {
    window.clickTest = false;
    const item = document.querySelector('.submenu-item:has(.fa-slash)');
    if (item) {
      item.addEventListener('click', () => {
        console.log('Native click handler triggered!');
        window.clickTest = true;
      });
    }
  });
  
  await submenuItem.click();
  await page.waitForTimeout(1000);
  
  // 检查点击是否触发
  const clickTestResult = await page.evaluate(() => window.clickTest);
  console.log('Click test result:', clickTestResult);
  
  // 等待一段时间
  await page.waitForTimeout(3000);
  
  await browser.close();
})();
