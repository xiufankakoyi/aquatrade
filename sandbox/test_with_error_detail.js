const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // 存储所有事件
  const allEvents = [];
  
  page.on('console', msg => {
    const text = msg.text();
    allEvents.push({ type: 'console', level: msg.type(), text, time: Date.now() });
    
    // 打印关键事件
    if (text.includes('backtest_') || text.includes('error') || text.includes('Error') || text.includes('daily_update')) {
      console.log(`[${msg.type()}] ${text.substring(0, 150)}`);
    }
  });
  
  console.log('打开页面...');
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  
  console.log('\n点击运行回测...');
  await page.locator('button:has-text("运行回测")').click();
  
  // 等待一段时间收集事件
  console.log('等待回测事件...');
  await page.waitForTimeout(15000);
  
  // 检查收到的所有事件类型
  console.log('\n=== 收到的事件摘要 ===');
  const backtestEvents = allEvents.filter(e => 
    e.text.includes('backtest_') || 
    e.text.includes('daily_') || 
    e.text.includes('metrics') ||
    e.text.includes('stream_') ||
    e.text.includes('risk_')
  );
  
  const eventTypes = {};
  backtestEvents.forEach(e => {
    const match = e.text.match(/on_(\w+)/);
    if (match) {
      const type = match[1];
      eventTypes[type] = (eventTypes[type] || 0) + 1;
    }
  });
  
  console.log('事件统计:', eventTypes);
  
  // 查找错误详情
  const errorEvents = allEvents.filter(e => 
    e.text.includes('backtest_error') || 
    (e.text.includes('error') && e.level === 'error')
  );
  
  if (errorEvents.length > 0) {
    console.log('\n=== 错误事件详情 ===');
    errorEvents.forEach(e => {
      console.log(`[${e.level}] ${e.text.substring(0, 300)}`);
    });
  }
  
  // 检查 localStorage
  const storeData = await page.evaluate(() => {
    const data = localStorage.getItem('backtest-store');
    if (data) {
      const parsed = JSON.parse(data);
      return {
        hasEquitySeries: !!parsed.equitySeries && parsed.equitySeries.length > 0,
        equityCount: parsed.equitySeries?.length || 0,
        hasMetrics: !!parsed.metrics,
        running: parsed.running,
        error: parsed.error
      };
    }
    return null;
  });
  
  console.log('\n=== localStorage 状态 ===');
  console.log(storeData || '无数据');
  
  // 截图
  await page.screenshot({ path: 'sandbox/error_detail.png', fullPage: true });
  console.log('\n截图已保存: sandbox/error_detail.png');
  
  await browser.close();
})();
