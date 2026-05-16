const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // 监听控制台日志
  page.on('console', msg => {
    console.log(`[浏览器控制台] ${msg.type()}: ${msg.text()}`);
  });
  
  // 监听网络请求
  page.on('request', request => {
    if (request.url().includes('socket.io') || request.url().includes('localhost:5000')) {
      console.log(`[网络请求] ${request.method()} ${request.url()}`);
    }
  });
  
  page.on('response', async response => {
    if (response.url().includes('socket.io') || response.url().includes('localhost:5000')) {
      console.log(`[网络响应] ${response.status()} ${response.url()}`);
    }
  });
  
  console.log('打开页面: http://localhost:5173/dashboard');
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded', timeout: 60000 });
  
  console.log('等待页面渲染...');
  await page.waitForTimeout(3000);
  
  // 截图初始状态
  await page.screenshot({ path: 'sandbox/frontend_initial.png', fullPage: true });
  console.log('已保存初始状态截图');
  
  // 检查初始状态
  console.log('\n=== 初始状态检查 ===');
  const initialEquityCurve = await page.locator('.equity-curve, [class*="equity"], canvas').count();
  console.log('权益曲线元素数量:', initialEquityCurve);
  
  // 点击运行回测
  console.log('\n点击运行回测按钮...');
  const runButton = page.locator('button:has-text("运行回测")');
  await runButton.click();
  
  console.log('等待回测完成（最多60秒）...');
  
  // 等待回测完成
  let completed = false;
  let attempts = 0;
  const maxAttempts = 60;
  
  while (!completed && attempts < maxAttempts) {
    await page.waitForTimeout(1000);
    attempts++;
    
    // 检查是否有权益曲线数据
    const equityElements = await page.locator('.equity-curve, [class*="equity"], canvas, [class*="chart"]').count();
    
    // 检查 localStorage 中是否有回测数据
    const hasBacktestData = await page.evaluate(() => {
      const data = localStorage.getItem('backtest-store');
      if (data) {
        const parsed = JSON.parse(data);
        return {
          hasEquitySeries: parsed.equitySeries && parsed.equitySeries.length > 0,
          equityCount: parsed.equitySeries?.length || 0,
          hasTrades: parsed.trades && parsed.trades.length > 0,
          tradeCount: parsed.trades?.length || 0,
          isRunning: parsed.running,
          progress: parsed.progress
        };
      }
      return null;
    });
    
    if (hasBacktestData && hasBacktestData.hasEquitySeries) {
      console.log(`\n✅ 回测数据已保存到 localStorage!`);
      console.log(`   权益数据点: ${hasBacktestData.equityCount}`);
      console.log(`   交易记录: ${hasBacktestData.tradeCount}`);
      console.log(`   运行状态: ${hasBacktestData.isRunning}`);
      console.log(`   进度: ${hasBacktestData.progress}%`);
      completed = true;
    }
    
    if (attempts % 10 === 0) {
      console.log(`  等待中... (${attempts}秒)`);
    }
  }
  
  // 等待几秒让图表渲染
  await page.waitForTimeout(3000);
  
  // 截图最终状态
  await page.screenshot({ path: 'sandbox/frontend_final.png', fullPage: true });
  console.log('\n已保存最终状态截图');
  
  // 详细检查页面内容
  console.log('\n=== 最终页面状态 ===');
  
  // 检查各种图表元素
  const canvasCount = await page.locator('canvas').count();
  const tvPaneCount = await page.locator('.tv-pane').count();
  const equityCurveCount = await page.locator('.equity-curve, [class*="equity"]').count();
  
  console.log('Canvas 元素数量:', canvasCount);
  console.log('TradingView Pane 数量:', tvPaneCount);
  console.log('权益曲线容器数量:', equityCurveCount);
  
  // 检查指标显示
  const metricsText = await page.locator('text=/收益率|总收益|年化|夏普/').count();
  console.log('指标文本元素数量:', metricsText);
  
  // 检查是否有数据表格
  const tableCount = await page.locator('table').count();
  console.log('表格数量:', tableCount);
  
  // 获取页面文本内容
  const pageText = await page.locator('body').textContent();
  const hasReturnData = pageText.includes('收益率') || pageText.includes('总收益') || pageText.includes('%');
  console.log('页面是否包含收益数据:', hasReturnData);
  
  console.log('\n=== 测试完成 ===');
  console.log('截图已保存:');
  console.log('  - sandbox/frontend_initial.png');
  console.log('  - sandbox/frontend_final.png');
  
  await browser.close();
})();
