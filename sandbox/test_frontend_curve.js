const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  console.log('打开页面: http://localhost:5173/dashboard');
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded', timeout: 60000 });
  
  console.log('等待页面渲染...');
  await page.waitForTimeout(3000);
  
  // 截图初始状态
  await page.screenshot({ path: 'sandbox/frontend_initial.png', fullPage: true });
  console.log('已保存初始状态截图');
  
  // 点击运行回测
  console.log('点击运行回测按钮...');
  const runButton = page.locator('button:has-text("运行回测")');
  await runButton.click();
  
  console.log('等待回测完成（最多60秒）...');
  
  // 等待回测完成或错误
  let completed = false;
  let attempts = 0;
  const maxAttempts = 60;
  
  while (!completed && attempts < maxAttempts) {
    await page.waitForTimeout(1000);
    attempts++;
    
    // 检查是否有收益曲线
    const hasChart = await page.locator('canvas, .tv-pane, .equity-curve, [class*="chart"]').count() > 0;
    
    // 检查是否有错误
    const hasError = await page.locator('.text-red-600, .text-red-400, [class*="error"]').count() > 0;
    
    if (hasChart) {
      console.log(`✅ 发现图表元素！(${attempts}秒)`);
      completed = true;
    } else if (hasError) {
      const errorText = await page.locator('.text-red-600, .text-red-400, [class*="error"]').first().textContent();
      console.log(`❌ 发现错误: ${errorText}`);
      completed = true;
    }
    
    if (attempts % 10 === 0) {
      console.log(`  等待中... (${attempts}秒)`);
    }
  }
  
  // 截图最终状态
  await page.screenshot({ path: 'sandbox/frontend_final.png', fullPage: true });
  console.log('已保存最终状态截图');
  
  // 检查页面内容
  console.log('\n=== 页面状态检查 ===');
  
  // 检查权益曲线数据
  const pageContent = await page.content();
  const hasEquityData = pageContent.includes('equity') || pageContent.includes('收益') || pageContent.includes('权益');
  console.log('是否有权益相关数据:', hasEquityData);
  
  // 检查图表
  const chartCount = await page.locator('canvas').count();
  console.log('Canvas 图表数量:', chartCount);
  
  // 检查权益曲线容器
  const equityContainers = await page.locator('[class*="equity"], [class*="curve"]').count();
  console.log('权益曲线容器数量:', equityContainers);
  
  // 检查指标显示
  const metricsCount = await page.locator('[class*="metric"], [class*="指标"]').count();
  console.log('指标元素数量:', metricsCount);
  
  console.log('\n=== 测试完成 ===');
  console.log('截图已保存:');
  console.log('  - sandbox/frontend_initial.png');
  console.log('  - sandbox/frontend_final.png');
  
  await browser.close();
})();
