const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // 监听所有网络请求
  const requests = [];
  const responses = [];
  
  page.on('request', request => {
    const url = request.url();
    if (url.includes('localhost:5000') || url.includes('socket.io') || url.includes('backtest')) {
      requests.push({
        method: request.method(),
        url: url,
        postData: request.postData()
      });
      console.log(`[请求] ${request.method()} ${url}`);
    }
  });
  
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('localhost:5000') || url.includes('socket.io') || url.includes('backtest')) {
      const status = response.status();
      let body = '';
      try {
        body = await response.text().catch(() => '');
      } catch (e) {}
      responses.push({
        status: status,
        url: url,
        body: body.substring(0, 500)
      });
      console.log(`[响应] ${status} ${url}`);
      if (status >= 400) {
        console.log('  错误响应:', body.substring(0, 200));
      }
    }
  });
  
  // 监听控制台错误
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('[控制台错误]', msg.text());
    }
  });
  
  page.on('pageerror', error => {
    console.log('[页面错误]', error.message);
  });
  
  console.log('打开页面...');
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  
  console.log('\n=== 检查后端 API 连接 ===');
  
  // 直接测试后端 API
  const apiCheck = await page.evaluate(async () => {
    try {
      const response = await fetch('http://localhost:5000/api/strategies');
      return { status: response.status, ok: response.ok };
    } catch (e) {
      return { error: e.message };
    }
  });
  console.log('API 策略列表检查:', apiCheck);
  
  console.log('\n=== 点击运行回测 ===');
  const runButton = page.locator('button:has-text("运行回测")');
  await runButton.click();
  
  console.log('等待 10 秒观察网络活动...');
  await page.waitForTimeout(10000);
  
  console.log('\n=== 网络请求摘要 ===');
  console.log('总请求数:', requests.length);
  console.log('总响应数:', responses.length);
  
  // 检查失败请求
  const failedResponses = responses.filter(r => r.status >= 400);
  if (failedResponses.length > 0) {
    console.log('\n失败的请求:');
    failedResponses.forEach(r => {
      console.log(`  ${r.status} ${r.url}`);
    });
  }
  
  // 检查 socket.io 连接
  const socketRequests = requests.filter(r => r.url.includes('socket.io'));
  console.log('\nSocket.IO 请求数:', socketRequests.length);
  
  // 截图当前状态
  await page.screenshot({ path: 'sandbox/check_network.png', fullPage: true });
  console.log('\n已保存截图: sandbox/check_network.png');
  
  await browser.close();
})();
