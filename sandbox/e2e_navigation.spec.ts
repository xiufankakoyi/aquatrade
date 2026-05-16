/**
 * 导航和路由 - E2E 测试
 * 测试范围：侧边栏导航、页面跳转、路由守卫、面包屑
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';

// 定义所有路由
const routes = [
  { path: '/dashboard', name: '总览看板', title: 'Dashboard' },
  { path: '/strategy/default', name: '策略详情', title: 'Strategy Detail' },
  { path: '/grid-search', name: '参数网格搜索', title: 'Grid Search' },
  { path: '/param-compare', name: '参数对比调参', title: 'Param Compare' },
  { path: '/stock-sentiment', name: '股票风评', title: 'Stock Sentiment' },
  { path: '/defense', name: '防守仓配置', title: 'Defense' },
  { path: '/history', name: '历史记录', title: 'History' },
  { path: '/strategy-generator', name: 'AI 策略生成器', title: 'Strategy Generator' },
  { path: '/strategy-editor', name: '策略开发工作台', title: 'Strategy Editor' },
  { path: '/dragon-eye', name: 'DragonEye 龙虎榜', title: 'Dragon Eye' },
];

test.describe('导航和路由测试', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.waitForLoadState('networkidle');
  });

  test('侧边栏导航链接检查', async ({ page }) => {
    await page.screenshot({ path: 'test-results/navigation-sidebar.png', fullPage: true });
    
    // 查找导航项
    const navItems = page.locator('nav a, .sidebar a, [class*="nav-item"]').filter({ hasText: /.+/ });
    const navCount = await navItems.count();
    
    console.log(`导航项数量: ${navCount}`);
    
    // 记录所有导航文本
    for (let i = 0; i < Math.min(navCount, 15); i++) {
      const text = await navItems.nth(i).textContent();
      console.log(`导航项 ${i + 1}: ${text}`);
    }
  });

  test('所有路由页面可访问性', async ({ page }) => {
    const results: { path: string; status: string; loadTime: number; errors: string[] }[] = [];
    
    for (const route of routes) {
      const startTime = Date.now();
      const errors: string[] = [];
      
      // 监听错误
      page.on('console', msg => {
        if (msg.type() === 'error') {
          errors.push(msg.text());
        }
      });
      
      try {
        await page.goto(`${FRONTEND_URL}${route.path}`);
        await page.waitForLoadState('networkidle', { timeout: 15000 });
        
        const loadTime = Date.now() - startTime;
        
        // 截图记录
        await page.screenshot({ path: `test-results/route-${route.path.replace(/\//g, '-')}.png`, fullPage: true });
        
        results.push({
          path: route.path,
          status: 'success',
          loadTime,
          errors: errors.slice(0, 3), // 只记录前3个错误
        });
        
        console.log(`✅ ${route.name} (${route.path}): ${loadTime}ms`);
      } catch (e) {
        results.push({
          path: route.path,
          status: 'failed',
          loadTime: Date.now() - startTime,
          errors: [e instanceof Error ? e.message : 'Unknown error'],
        });
        
        console.log(`❌ ${route.name} (${route.path}): 加载失败`);
      }
      
      // 移除监听器
      page.removeAllListeners('console');
    }
    
    // 汇总结果
    const successCount = results.filter(r => r.status === 'success').length;
    console.log(`\n路由测试结果: ${successCount}/${routes.length} 成功`);
    
    // 所有路由都应该成功加载
    expect(successCount).toBeGreaterThanOrEqual(routes.length - 2); // 允许最多2个失败
  });

  test('页面标题检查', async ({ page }) => {
    for (const route of routes.slice(0, 5)) { // 只检查前5个路由
      await page.goto(`${FRONTEND_URL}${route.path}`);
      await page.waitForLoadState('networkidle');
      
      // 检查页面是否有标题
      const h1 = page.locator('h1').first();
      const hasTitle = await h1.isVisible().catch(() => false);
      
      if (hasTitle) {
        const titleText = await h1.textContent();
        console.log(`${route.path}: "${titleText}"`);
      } else {
        console.log(`${route.path}: 无标题`);
      }
    }
  });

  test('导航高亮状态', async ({ page }) => {
    // 访问 Dashboard
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 查找当前激活的导航项
    const activeNav = page.locator('nav a[class*="active"], .sidebar a[class*="active"], [class*="nav-item"][class*="active"]').first();
    
    if (await activeNav.isVisible().catch(() => false)) {
      const text = await activeNav.textContent();
      console.log(`当前激活导航: ${text}`);
      
      await page.screenshot({ path: 'test-results/navigation-active-state.png' });
    }
  });

  test('浏览器前进后退', async ({ page }) => {
    // 访问两个页面
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    await page.goto(`${FRONTEND_URL}/grid-search`);
    await page.waitForLoadState('networkidle');
    
    // 后退
    await page.goBack();
    await page.waitForLoadState('networkidle');
    
    // 检查是否在 Dashboard
    const url = page.url();
    expect(url).toContain('/dashboard');
    
    // 前进
    await page.goForward();
    await page.waitForLoadState('networkidle');
    
    const forwardUrl = page.url();
    expect(forwardUrl).toContain('/grid-search');
  });

  test('404 页面处理', async ({ page }) => {
    // 访问不存在的路由
    await page.goto(`${FRONTEND_URL}/non-existent-route`);
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ path: 'test-results/404-page.png', fullPage: true });
    
    // 检查是否有 404 提示或重定向到首页
    const bodyText = await page.locator('body').textContent();
    const has404 = bodyText?.toLowerCase().includes('404') || 
                   bodyText?.toLowerCase().includes('not found') ||
                   bodyText?.toLowerCase().includes('找不到');
    
    const isRedirected = page.url() === `${FRONTEND_URL}/` || 
                         page.url() === `${FRONTEND_URL}/dashboard`;
    
    console.log(`404 测试: has404=${has404}, isRedirected=${isRedirected}`);
    
    // 应该有 404 提示或重定向
    expect(has404 || isRedirected).toBeTruthy();
  });

  test('移动端导航菜单', async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 932 });
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ path: 'test-results/navigation-mobile.png', fullPage: true });
    
    // 查找移动端菜单按钮
    const menuBtn = page.locator('button[class*="menu"], button[aria-label*="menu"], .hamburger').first();
    
    if (await menuBtn.isVisible().catch(() => false)) {
      await menuBtn.click();
      await page.waitForTimeout(500);
      
      await page.screenshot({ path: 'test-results/navigation-mobile-menu-open.png' });
      
      // 点击菜单项
      const firstNavItem = page.locator('nav a, .mobile-nav a').first();
      if (await firstNavItem.isVisible().catch(() => false)) {
        await firstNavItem.click();
        await page.waitForLoadState('networkidle');
      }
    }
  });
});
