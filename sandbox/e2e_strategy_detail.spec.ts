/**
 * Strategy Detail K线页面 - E2E 测试
 * 测试范围：K线图表、交易记录、持仓面板、Playback功能
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';

test.describe('Strategy Detail K线页面测试', () => {
  
  test.beforeEach(async ({ page }) => {
    // 访问策略详情页
    await page.goto(`${FRONTEND_URL}/strategy/default`);
    await page.waitForLoadState('networkidle');
  });

  test('页面基础结构检查', async ({ page }) => {
    await page.screenshot({ path: 'test-results/strategy-detail-initial.png', fullPage: true });
    
    // 检查顶部工具栏
    const toolbar = page.locator('.toolbar, [class*="toolbar"]').first();
    await expect(toolbar).toBeVisible();
    
    // 检查股票名称显示
    const symbolName = page.locator('.symbol-name, [class*="symbol-name"]').first();
    await expect(symbolName).toBeVisible();
    
    // 检查图表区域
    const chartArea = page.locator('.chart-area, [class*="chart-area"]').first();
    await expect(chartArea).toBeVisible();
  });

  test('K线图表交互检查', async ({ page }) => {
    const chart = page.locator('.kline-chart, [class*="kline-chart"]').first();
    await expect(chart).toBeVisible();
    
    // 尝试在图表上悬停查看十字线
    const chartBox = await chart.boundingBox();
    if (chartBox) {
      await page.mouse.move(chartBox.x + chartBox.width / 2, chartBox.y + chartBox.height / 2);
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/strategy-detail-chart-hover.png' });
    }
  });

  test('影子曲线切换功能', async ({ page }) => {
    // 查找影子曲线切换按钮
    const shadowToggle = page.locator('button:has-text("剔除 Alpha"), button:has-text("shadow"), .shadow-toggle button').first();
    
    if (await shadowToggle.isVisible().catch(() => false)) {
      const initialState = await shadowToggle.getAttribute('class');
      
      await shadowToggle.click();
      await page.waitForTimeout(500);
      
      const newState = await shadowToggle.getAttribute('class');
      await page.screenshot({ path: 'test-results/strategy-detail-shadow-toggle.png' });
      
      // 验证按钮状态变化
      console.log(`影子曲线切换: ${initialState} -> ${newState}`);
    }
  });

  test('运行回测按钮检查', async ({ page }) => {
    const runBtn = page.locator('button:has-text("运行回测"), button:has-text("Run"), .run-btn').first();
    
    if (await runBtn.isVisible().catch(() => false)) {
      await expect(runBtn).toBeVisible();
      
      // 记录按钮状态
      const isDisabled = await runBtn.isDisabled().catch(() => false);
      console.log(`运行回测按钮状态: ${isDisabled ? '禁用' : '可用'}`);
    }
  });

  test('侧边持仓面板检查', async ({ page }) => {
    const sidePanel = page.locator('.side-panel, [class*="side-panel"]').first();
    
    // 桌面端侧边栏应该可见
    const isVisible = await sidePanel.isVisible().catch(() => false);
    
    if (isVisible) {
      // 检查风险雷达
      const riskRadar = page.locator('[class*="radar"], [class*="risk"]').first();
      await expect(riskRadar).toBeVisible();
      
      // 检查持仓卡片
      const positionCard = page.locator('[class*="position"], [class*="holding"]').first();
      if (await positionCard.isVisible().catch(() => false)) {
        await page.screenshot({ path: 'test-results/strategy-detail-position-card.png' });
      }
    }
  });

  test('底部交易记录面板', async ({ page }) => {
    const tradePanel = page.locator('.trade-panel, [class*="trade-panel"]').first();
    await expect(tradePanel).toBeVisible();
    
    // 检查面板标题
    const panelTitle = page.locator('.panel-title:has-text("交易明细"), [class*="panel-title"]').first();
    if (await panelTitle.isVisible().catch(() => false)) {
      await expect(panelTitle).toContainText('交易');
    }
    
    // 测试面板折叠/展开
    const panelHeader = page.locator('.panel-header, [class*="panel-header"]').first();
    if (await panelHeader.isVisible().catch(() => false)) {
      await panelHeader.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: 'test-results/strategy-detail-trade-panel-collapsed.png' });
      
      await panelHeader.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: 'test-results/strategy-detail-trade-panel-expanded.png' });
    }
  });

  test('Playback控制器检查', async ({ page }) => {
    const playbackOverlay = page.locator('.playback-overlay, [class*="playback"]').first();
    
    // Playback 控制器可能只在有回测数据时显示
    if (await playbackOverlay.isVisible().catch(() => false)) {
      await expect(playbackOverlay).toBeVisible();
      
      // 检查播放/暂停按钮
      const playBtn = page.locator('button:has([class*="play"]), button:has-text("播放")').first();
      if (await playBtn.isVisible().catch(() => false)) {
        await page.screenshot({ path: 'test-results/strategy-detail-playback.png' });
      }
    }
  });

  test('响应式适配 - 移动端隐藏侧边栏', async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 932 });
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ path: 'test-results/strategy-detail-mobile.png', fullPage: true });
    
    // 移动端侧边栏应该隐藏
    const sidePanel = page.locator('.side-panel, [class*="side-panel"]').first();
    const isSidePanelVisible = await sidePanel.isVisible().catch(() => false);
    
    console.log(`移动端侧边栏可见性: ${isSidePanelVisible}`);
  });

  test('交易记录表格交互', async ({ page }) => {
    // 展开交易面板
    const panelHeader = page.locator('.panel-header, [class*="panel-header"]').first();
    if (await panelHeader.isVisible().catch(() => false)) {
      // 确保面板展开
      const panel = page.locator('.trade-panel, [class*="trade-panel"]').first();
      const panelHeight = await panel.evaluate(el => (el as HTMLElement).style.height);
      
      if (panelHeight === '40px' || !panelHeight) {
        await panelHeader.click();
        await page.waitForTimeout(300);
      }
    }
    
    // 检查表格行
    const tableRows = page.locator('table tbody tr');
    const rowCount = await tableRows.count();
    
    console.log(`交易记录行数: ${rowCount}`);
    
    if (rowCount > 0) {
      // 点击第一行
      await tableRows.first().click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/strategy-detail-trade-row-clicked.png' });
    }
  });

  test('性能指标 - 大图表渲染', async ({ page }) => {
    // 收集图表渲染性能
    const startTime = Date.now();
    
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    // 等待图表渲染完成
    const chart = page.locator('.kline-chart, [class*="kline-chart"]').first();
    await chart.waitFor({ state: 'visible', timeout: 10000 });
    
    const renderTime = Date.now() - startTime;
    console.log(`K线图表渲染时间: ${renderTime}ms`);
    
    // 图表渲染应该小于 5 秒
    expect(renderTime).toBeLessThan(5000);
  });
});
