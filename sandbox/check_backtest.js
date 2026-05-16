const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  console.log('打开页面: http://localhost:5173/dashboard');
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded', timeout: 60000 });
  
  console.log('页面已加载，等待渲染...');
  await page.waitForTimeout(3000);
  
  // 截图查看当前状态
  await page.screenshot({ path: 'sandbox/check_initial.png', fullPage: true });
  console.log('已保存初始状态截图: sandbox/check_initial.png');
  
  // 检查 API 连接状态
  const apiStatus = await page.locator('.bg-green-500, .bg-red-500').first();
  const apiText = await page.locator('text=/API.*连接/').first();
  if (apiText) {
    const text = await apiText.textContent();
    console.log('API 状态:', text);
  }
  
  // 检查策略选择
  const strategySelect = await page.locator('select').first();
  const strategyValue = await strategySelect.inputValue().catch(() => '未选择');
  console.log('当前策略:', strategyValue);
  
  // 检查日期范围
  const dateInputs = await page.locator('input[type="date"]').all();
  for (let i = 0; i < dateInputs.length; i++) {
    const value = await dateInputs[i].inputValue();
    console.log(`日期输入 ${i}:`, value);
  }
  
  // 检查运行回测按钮状态
  const runButton = page.locator('button:has-text("运行回测")');
  const isDisabled = await runButton.isDisabled().catch(() => true);
  console.log('运行回测按钮是否禁用:', isDisabled);
  
  // 检查是否有错误信息
  const errorElements = await page.locator('.text-red-600, .text-red-400, [class*="error"]').all();
  if (errorElements.length > 0) {
    console.log('发现错误信息:');
    for (const el of errorElements) {
      const text = await el.textContent();
      console.log(' -', text);
    }
  }
  
  // 检查页面是否有数据
  const hasData = await page.locator('.tv-pane, .equity-curve, canvas').count();
  console.log('页面数据元素数量:', hasData);
  
  // 尝试点击运行回测并观察
  console.log('\n尝试点击运行回测...');
  await runButton.click();
  
  // 等待几秒观察变化
  console.log('等待回测响应...');
  await page.waitForTimeout(5000);
  
  // 再次截图
  await page.screenshot({ path: 'sandbox/check_after_click.png', fullPage: true });
  console.log('已保存点击后截图: sandbox/check_after_click.png');
  
  // 检查是否有加载状态
  const loadingElements = await page.locator('.animate-spin, .loading, [class*="loading"]').all();
  console.log('加载状态元素数量:', loadingElements.length);
  
  // 检查控制台日志
  const logs = [];
  page.on('console', msg => {
    logs.push(`${msg.type()}: ${msg.text()}`);
  });
  
  await page.waitForTimeout(2000);
  
  console.log('\n控制台日志:');
  logs.forEach(log => console.log(log));
  
  // 检查网络请求
  console.log('\n检查网络请求...');
  
  await browser.close();
  console.log('\n诊断完成');
})();
