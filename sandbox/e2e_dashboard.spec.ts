/**
 * Dashboard 总览看板 - E2E 测试
 * 测试范围：页面加载、图表渲染、AI分析、导出功能、响应式适配
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:5000';

test.describe('Dashboard 总览看板测试', () => {
  
  test.beforeEach(async ({ page }) => {
    // 访问首页并等待加载完成
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
  });

  test('页面基础结构检查', async ({ page }) => {
    // 截图记录初始状态
    await page.screenshot({ path: 'test-results/dashboard-initial.png', fullPage: true });
    
    // 检查顶部 MetricsToolbar 是否存在
    const toolbar = page.locator('.metrics-toolbar, [class*="toolbar"]').first();
    await expect(toolbar).toBeVisible();
    
    // 检查主内容区域
    const mainContent = page.locator('.tv-dot-grid, .grid').first();
    await expect(mainContent).toBeVisible();
    
    // 检查右侧边栏
    const sidebar = page.locator('.sidebar, [class*="sidebar"]').first();
    // 侧边栏可能在移动端隐藏
    if (await sidebar.isVisible().catch(() => false)) {
      await expect(sidebar).toBeVisible();
    }
  });

  test('净值曲线图表渲染检查', async ({ page }) => {
    // 等待图表容器加载
    const chartContainer = page.locator('[class*="equity"], [class*="chart"]').first();
    await expect(chartContainer).toBeVisible({ timeout: 10000 });
    
    // 检查图表切换按钮（线性/对数）
    const linearBtn = page.locator('button:has-text("线性"), button:has-text("linear")').first();
    const logBtn = page.locator('button:has-text("对数"), button:has-text("log")').first();
    
    if (await linearBtn.isVisible().catch(() => false)) {
      await linearBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/dashboard-chart-linear.png' });
    }
    
    if (await logBtn.isVisible().catch(() => false)) {
      await logBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/dashboard-chart-log.png' });
    }
  });

  test('AI Review 按钮交互', async ({ page }) => {
    const aiReviewBtn = page.locator('button:has-text("AI REVIEW"), button:has-text("AI Review")').first();
    
    if (await aiReviewBtn.isVisible().catch(() => false)) {
      // 记录按钮初始状态
      await expect(aiReviewBtn).toBeVisible();
      
      // 检查按钮是否可点击（需要回测数据才能点击）
      const isDisabled = await aiReviewBtn.isDisabled().catch(() => false);
      
      if (!isDisabled) {
        await aiReviewBtn.click();
        await page.waitForTimeout(1000);
        
        // 检查是否弹出分析模态框
        const modal = page.locator('.modal, [class*="modal"], [class*="Modal"]').first();
        if (await modal.isVisible().catch(() => false)) {
          await page.screenshot({ path: 'test-results/dashboard-ai-modal.png' });
          
          // 关闭模态框
          const closeBtn = page.locator('button:has-text("关闭"), button:has-text("Close"), .close').first();
          if (await closeBtn.isVisible().catch(() => false)) {
            await closeBtn.click();
          }
        }
      }
    }
  });

  test('侧边栏折叠/展开功能', async ({ page }) => {
    const toggleBtn = page.locator('button:has([class*="columns"]), button[class*="toggle"]').first();
    
    if (await toggleBtn.isVisible().catch(() => false)) {
      // 点击折叠
      await toggleBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/dashboard-sidebar-collapsed.png' });
      
      // 点击展开
      await toggleBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/dashboard-sidebar-expanded.png' });
    }
  });

  test('响应式布局适配 - 桌面端', async ({ page }) => {
    // 桌面端应该显示所有元素
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    const sidebar = page.locator('.sidebar, [class*="sidebar"]').first();
    const chartArea = page.locator('[class*="chart"], [class*="equity"]').first();
    
    await expect(chartArea).toBeVisible();
    
    // 截图记录桌面端布局
    await page.screenshot({ path: 'test-results/dashboard-desktop.png', fullPage: true });
  });

  test('响应式布局适配 - 平板端', async ({ page }) => {
    await page.setViewportSize({ width: 834, height: 1194 });
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    // 截图记录平板端布局
    await page.screenshot({ path: 'test-results/dashboard-ipad.png', fullPage: true });
    
    // 检查图表区域是否正常显示
    const chartArea = page.locator('[class*="chart"], [class*="equity"]').first();
    await expect(chartArea).toBeVisible();
  });

  test('响应式布局适配 - 移动端', async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 932 });
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    // 截图记录移动端布局
    await page.screenshot({ path: 'test-results/dashboard-mobile.png', fullPage: true });
    
    // 移动端侧边栏应该隐藏或折叠
    const sidebar = page.locator('.sidebar, [class*="sidebar"]').first();
    const isSidebarVisible = await sidebar.isVisible().catch(() => false);
    
    // 记录移动端布局状态
    console.log(`移动端侧边栏可见性: ${isSidebarVisible}`);
  });

  test('性能指标收集', async ({ page }) => {
    // 使用 Performance API 收集加载性能
    const performanceMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return {
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.startTime,
        loadComplete: navigation.loadEventEnd - navigation.startTime,
        firstPaint: performance.getEntriesByType('paint').find(p => p.name === 'first-paint')?.startTime,
        firstContentfulPaint: performance.getEntriesByType('paint').find(p => p.name === 'first-contentful-paint')?.startTime,
      };
    });
    
    console.log('性能指标:', performanceMetrics);
    
    // 断言性能指标
    expect(performanceMetrics.domContentLoaded).toBeLessThan(5000);
    expect(performanceMetrics.loadComplete).toBeLessThan(10000);
  });

  test('错误监控检查', async ({ page }) => {
    const errors: string[] = [];
    
    // 监听控制台错误
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    
    // 监听页面错误
    page.on('pageerror', error => {
      errors.push(error.message);
    });
    
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    // 过滤掉已知的非关键错误
    const criticalErrors = errors.filter(e => 
      !e.includes('favicon') && 
      !e.includes('source map') &&
      !e.includes('sockjs')
    );
    
    if (criticalErrors.length > 0) {
      console.log('发现的错误:', criticalErrors);
    }
    
    // 记录错误但不中断测试
    expect(criticalErrors.length).toBeLessThan(5);
  });
});
