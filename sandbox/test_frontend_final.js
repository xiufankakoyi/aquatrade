const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // 收集所有事件和错误
  const events = [];
  const errors = [];
  
  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('backtest_error') || text.includes('error') || text.includes('Error')) {
      errors.push(text);
    }
    events.push({ type: 'console', level: msg.type(), text });
  });
  
  console.log('打开页面: http://localhost:5173/dashboard');
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  
  // 点击运行回测
  console.log('点击运行回测...');
  await page.locator('button:has-text("运行回测")').click();
  
  // 等待回测完成（最多30秒）
  console.log('等待回测完成...');
  await page.waitForTimeout(20000);
  
  // 检查 localStorage 数据
  const backtestData = await page.evaluate(() => {
    const data = localStorage.getItem('backtest-store');
    return data ? JSON.parse(data) : null;
  });
  
  console.log('\n=== 回测数据状态 ===');
  if (backtestData) {
    console.log('权益序列长度:', backtestData.equitySeries?.length || 0);
    console.log('交易记录数:', backtestData.trades?.length || 0);
    console.log('指标数据:', backtestData.metrics ? '有' : '无');
    console.log('运行状态:', backtestData.running);
    console.log('进度:', backtestData.progress);
    
    if (backtestData.equitySeries && backtestData.equitySeries.length > 0) {
      console.log('\n✅ 回测成功！权益曲线数据已生成');
      console.log('第一个数据点:', backtestData.equitySeries[0]);
      console.log('最后一个数据点:', backtestData.equitySeries[backtestData.equitySeries.length - 1]);
    }
  } else {
    console.log('localStorage 中没有回测数据');
  }
  
  // 截图
  await page.screenshot({ path: 'sandbox/final_result.png', fullPage: true });
  
  // 检查页面上的图表
  const chartVisible = await page.locator('canvas').first().isVisible().catch(() => false);
  console.log('\n图表是否可见:', chartVisible);
  
  if (errors.length > 0) {
    console.log('\n=== 错误日志 ===');
    errors.forEach(e => console.log(' -', e.substring(0, 200)));
  }
  
  console.log('\n截图已保存: sandbox/final_result.png');
  
  await browser.close();
})();
