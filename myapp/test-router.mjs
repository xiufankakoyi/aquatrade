import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 监听控制台消息
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

  try {
    // 1. 先访问 strategy-editor
    console.log('1. 访问 strategy-editor...');
    await page.goto('http://localhost:5173/strategy-editor', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    console.log('当前URL:', page.url());

    // 2. 点击 dragon-eye 导航
    console.log('\n2. 点击 dragon-eye 导航...');
    const dragonEyeLink = await page.locator('a[href="/dragon-eye"]').first();
    console.log('找到 dragon-eye 链接:', await dragonEyeLink.isVisible());
    await dragonEyeLink.click();
    
    // 等待导航完成
    await page.waitForURL('**/dragon-eye', { timeout: 5000 });
    await page.waitForTimeout(2000);
    console.log('点击后URL:', page.url());

    // 3. 检查页面内容
    const bodyText = await page.locator('body').textContent();
    console.log('\n3. 页面内容包含 "DragonEye":', bodyText.includes('DragonEye'));
    console.log('页面内容包含 "龙虎榜":', bodyText.includes('龙虎榜'));
    console.log('页面内容包含 "策略开发":', bodyText.includes('策略开发'));
    console.log('页面内容包含 "回测参数":', bodyText.includes('回测参数'));

    // 4. 截图查看
    await page.screenshot({ path: 'test-result.png' });
    console.log('\n4. 已保存截图到 test-result.png');

  } catch (error) {
    console.error('测试失败:', error);
  }

  await browser.close();
})();
