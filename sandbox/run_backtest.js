const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  console.log('打开页面: http://localhost:5173/dashboard');
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded', timeout: 60000 });
  
  console.log('页面已加载，等待页面渲染...');
  await page.waitForTimeout(5000);
  
  const runButton = page.locator('button:has-text("运行回测")');
  
  try {
    await runButton.waitFor({ state: 'visible', timeout: 10000 });
    console.log('找到"运行回测"按钮，点击...');
    await runButton.click();
    console.log('已点击"运行回测"按钮');
    
    await page.waitForTimeout(3000);
    console.log('回测已启动');
  } catch (e) {
    console.log('未找到"运行回测"按钮，尝试其他选择器...');
    
    const altButton = page.locator('button').filter({ hasText: '运行回测' });
    if (await altButton.count() > 0) {
      await altButton.first().click();
      console.log('已点击"运行回测"按钮 (备用选择器)');
    } else {
      console.log('仍未找到按钮，页面截图保存到 sandbox/screenshot.png');
      await page.screenshot({ path: 'sandbox/screenshot.png' });
    }
  }
  
  await browser.close();
})();
