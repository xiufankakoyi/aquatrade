import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 监听控制台消息
  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('daily_equity') || text.includes('equity') || text.includes('addEquity')) {
      console.log('PAGE LOG:', text);
    }
  });

  try {
    // 访问策略页面
    console.log('1. 访问策略页面...');
    await page.goto('http://localhost:5173/strategy/jq_volume_v1pro', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    // 点击运行回测按钮
    console.log('\n2. 点击运行回测...');
    const runButton = await page.locator('button:has-text("运行")').first();
    await runButton.click();

    // 等待并观察流式更新
    console.log('\n3. 观察流式更新（等待10秒）...');
    for (let i = 0; i < 10; i++) {
      await page.waitForTimeout(1000);
      const equityText = await page.locator('.equity-curve-container').textContent().catch(() => '');
      console.log(`  ${i+1}s: 图表内容长度 = ${equityText.length}`);
    }

  } catch (error) {
    console.error('测试失败:', error);
  }

  await browser.close();
})();
