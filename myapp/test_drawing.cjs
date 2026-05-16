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
  
  // 1. 点击趋势线工具
  const trendLineBtn = await page.$('.has-submenu:has(.fa-chart-line)');
  await trendLineBtn.hover();
  await page.waitForTimeout(500);
  
  const submenuItem = await page.$('.submenu-item:has(.fa-slash)');
  await submenuItem.click();
  console.log('1. 已选择趋势线工具');
  await page.waitForTimeout(1000);
  
  // 2. 在图表上绘制一条线
  const chart = await page.$('.chart-container');
  const box = await chart.boundingBox();
  
  console.log('2. 图表位置:', box);
  
  // 从左上到右下画一条线
  const startX = box.x + box.width * 0.3;
  const startY = box.y + box.height * 0.3;
  const endX = box.x + box.width * 0.7;
  const endY = box.y + box.height * 0.7;
  
  console.log(`3. 开始绘制: (${startX}, ${startY}) -> (${endX}, ${endY})`);
  
  await page.mouse.move(startX, startY);
  await page.waitForTimeout(200);
  await page.mouse.down();
  await page.waitForTimeout(200);
  await page.mouse.move(endX, endY);
  await page.waitForTimeout(200);
  await page.mouse.up();
  await page.waitForTimeout(200);
  
  console.log('4. 绘制完成');
  
  // 截图查看结果
  await page.screenshot({ path: 'drawing_test.png' });
  
  // 等待一段时间查看控制台输出
  await page.waitForTimeout(3000);
  
  await browser.close();
})();
