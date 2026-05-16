const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // 收集所有日志
  const logs = [];
  page.on('console', msg => {
    const text = `[${msg.type()}] ${msg.text()}`;
    logs.push(text);
    console.log(text);
  });
  
  page.on('pageerror', error => {
    const text = `[PAGE ERROR] ${error.message}`;
    logs.push(text);
    console.log(text);
  });
  
  // 监听网络请求
  page.on('request', request => {
    const url = request.url();
    if (url.includes('socket.io') || url.includes('localhost:5000')) {
      console.log(`[REQUEST] ${request.method()} ${url}`);
    }
  });
  
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('socket.io') || url.includes('localhost:5000')) {
      console.log(`[RESPONSE] ${response.status()} ${url}`);
    }
  });
  
  console.log('=== 打开页面 ===');
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  
  // 截图初始状态
  await page.screenshot({ path: 'sandbox/debug_initial.png', fullPage: true });
  
  console.log('\n=== 检查页面状态 ===');
  
  // 检查策略选择
  const strategySelect = await page.locator('select').first();
  const strategyOptions = await strategySelect.locator('option').all();
  console.log('可用策略:');
  for (const opt of strategyOptions) {
    const value = await opt.getAttribute('value');
    const text = await opt.textContent();
    console.log(`  - ${value}: ${text}`);
  }
  
  // 获取当前选中的策略
  const selectedStrategy = await strategySelect.inputValue();
  console.log('当前选中策略:', selectedStrategy);
  
  // 检查日期
  const dateInputs = await page.locator('input[type="date"]').all();
  for (let i = 0; i < dateInputs.length; i++) {
    const value = await dateInputs[i].inputValue();
    const label = i === 0 ? '开始日期' : '结束日期';
    console.log(`${label}:`, value);
  }
  
  // 检查 API 状态
  const apiStatus = await page.locator('text=/API.*连接/').first().textContent().catch(() => '未知');
  console.log('API 状态:', apiStatus);
  
  console.log('\n=== 检查后端 API ===');
  
  // 测试后端 API
  const strategiesCheck = await page.evaluate(async () => {
    try {
      const response = await fetch('http://localhost:5000/api/strategies');
      const data = await response.json();
      return { ok: response.ok, status: response.status, data };
    } catch (e) {
      return { error: e.message };
    }
  });
  console.log('策略列表 API:', JSON.stringify(strategiesCheck, null, 2));
  
  console.log('\n=== 点击运行回测 ===');
  
  // 点击前清空日志
  logs.length = 0;
  
  const runButton = page.locator('button:has-text("运行回测")');
  await runButton.click();
  
  console.log('等待 15 秒观察回测过程...');
  await page.waitForTimeout(15000);
  
  // 截图回测后状态
  await page.screenshot({ path: 'sandbox/debug_after_run.png', fullPage: true });
  
  console.log('\n=== 检查回测结果 ===');
  
  // 检查是否有数据
  const hasEquityData = await page.evaluate(() => {
    // 检查 localStorage
    const backtestData = localStorage.getItem('backtest-store');
    if (backtestData) {
      const data = JSON.parse(backtestData);
      return {
        hasEquitySeries: data.equitySeries && data.equitySeries.length > 0,
        equityCount: data.equitySeries?.length || 0,
        hasTrades: data.trades && data.trades.length > 0,
        tradeCount: data.trades?.length || 0,
        hasMetrics: !!data.metrics,
        isRunning: data.running,
        progress: data.progress
      };
    }
    return null;
  });
  
  console.log('回测数据状态:', JSON.stringify(hasEquityData, null, 2));
  
  // 检查页面上的图表
  const chartElements = await page.locator('canvas, .tv-pane, .equity-curve').count();
  console.log('图表元素数量:', chartElements);
  
  // 检查是否有错误提示
  const errorMessages = await page.locator('.text-red-600, .text-red-400, [class*="error"]').all();
  if (errorMessages.length > 0) {
    console.log('\n页面错误信息:');
    for (const el of errorMessages) {
      const text = await el.textContent();
      console.log(' -', text);
    }
  }
  
  console.log('\n=== 日志摘要 ===');
  const socketLogs = logs.filter(l => l.includes('Socket') || l.includes('socket'));
  if (socketLogs.length > 0) {
    console.log('Socket.IO 相关日志:');
    socketLogs.forEach(l => console.log(' ', l));
  }
  
  const backtestLogs = logs.filter(l => l.includes('回测') || l.includes('backtest') || l.includes('stream'));
  if (backtestLogs.length > 0) {
    console.log('回测相关日志:');
    backtestLogs.forEach(l => console.log(' ', l));
  }
  
  console.log('\n=== 诊断完成 ===');
  console.log('截图已保存:');
  console.log('  - sandbox/debug_initial.png');
  console.log('  - sandbox/debug_after_run.png');
  
  await browser.close();
})();
