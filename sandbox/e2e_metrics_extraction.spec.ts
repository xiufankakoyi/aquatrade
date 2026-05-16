/**
 * Dashboard 回测指标提取测试 - 最终版
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';

test.describe('Dashboard 回测指标提取', () => {
  
  test('提取并验证回测指标', async ({ page }) => {
    console.log('\n========================================');
    console.log('Dashboard 回测指标提取测试');
    console.log('========================================\n');

    // 监听控制台
    page.on('console', msg => {
      const text = msg.text();
      if (text.includes('backtest') || text.includes('equity') || text.includes('metrics') || text.includes('Socket')) {
        console.log(`[Console] ${text}`);
      }
    });

    // 1. 导航到 Dashboard
    console.log('[步骤 1] 导航到 Dashboard...');
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // 2. 选择策略
    console.log('[步骤 2] 选择策略...');
    const strategySelect = page.locator('select').first();
    await strategySelect.waitFor({ state: 'visible', timeout: 10000 });
    const options = await strategySelect.locator('option').allTextContents();
    
    const v5Option = options.find(opt => opt.includes('V5'));
    if (v5Option) {
      await strategySelect.selectOption({ label: v5Option });
      console.log(`[选择] ${v5Option}`);
    }

    // 3. 设置日期
    console.log('[步骤 3] 设置日期...');
    const dateInputs = await page.locator('input[type="date"]').all();
    console.log(`[状态] 发现 ${dateInputs.length} 个日期输入框`);
    
    if (dateInputs.length >= 2) {
      await dateInputs[0].fill('2024-05-01');
      await dateInputs[1].fill('2024-05-31');
      console.log('[设置] 日期范围: 2024-05-01 ~ 2024-05-31');
    }

    // 4. 运行回测 - 使用多种方式查找按钮
    console.log('[步骤 4] 运行回测...');
    
    // 等待一下确保页面稳定
    await page.waitForTimeout(1000);
    
    // 尝试多种选择器
    const runButtonSelectors = [
      'button:has-text("运行")',
      'button:has-text("运行回测")',
      'button:has-text("RUN")',
      'button.run-btn',
      'button.primary',
    ];
    
    let runButton = null;
    for (const selector of runButtonSelectors) {
      const btn = page.locator(selector).first();
      if (await btn.isVisible().catch(() => false)) {
        const isDisabled = await btn.isDisabled().catch(() => true);
        if (!isDisabled) {
          runButton = btn;
          console.log(`[找到] 运行按钮: ${selector}`);
          break;
        }
      }
    }
    
    if (!runButton) {
      // 列出所有可见按钮
      console.log('[调试] 列出所有可见按钮:');
      const allButtons = await page.locator('button:visible').all();
      for (let i = 0; i < allButtons.length; i++) {
        const text = await allButtons[i].textContent().catch(() => '');
        const isDisabled = await allButtons[i].isDisabled().catch(() => true);
        console.log(`  按钮 ${i}: "${text?.trim()}" (禁用: ${isDisabled})`);
      }
      
      // 尝试找到包含"运行"的按钮
      for (let i = 0; i < allButtons.length; i++) {
        const text = await allButtons[i].textContent().catch(() => '');
        if (text?.includes('运行')) {
          runButton = allButtons[i];
          console.log(`[选择] 按钮 ${i}: "${text?.trim()}"`);
          break;
        }
      }
    }
    
    if (runButton) {
      await runButton.click();
      console.log('[操作] 点击运行按钮');
    } else {
      console.log('[错误] 未找到运行按钮');
      throw new Error('未找到运行按钮');
    }

    // 5. 等待回测完成
    console.log('[步骤 5] 等待回测完成...');
    const startTime = Date.now();
    const timeout = 180000;
    let equityUpdateCount = 0;

    while ((Date.now() - startTime) < timeout) {
      await page.waitForTimeout(2000);
      
      // 检查 canvas
      const canvas = page.locator('canvas').first();
      const hasCanvas = await canvas.isVisible().catch(() => false);
      if (hasCanvas) {
        equityUpdateCount++;
      }
      
      // 检查是否有"概览"按钮（说明有回测数据）
      const overviewBtn = page.locator('button:has-text("概览")').first();
      const hasOverviewBtn = await overviewBtn.isVisible().catch(() => false);
      
      // 检查运行状态
      const isRunning = await page.locator('[class*="running"], [class*="spinner"], [class*="loading"]').first().isVisible().catch(() => false);
      
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      if (elapsed % 10 === 0) {
        console.log(`[等待 ${elapsed}s] Canvas: ${hasCanvas}, 概览按钮: ${hasOverviewBtn}, 运行中: ${isRunning}, 更新次数: ${equityUpdateCount}`);
      }

      // 如果有概览按钮且不在运行，说明回测完成
      if (hasOverviewBtn && !isRunning && elapsed > 5) {
        console.log('[状态] 检测到回测完成');
        await page.waitForTimeout(3000);
        break;
      }
    }

    console.log(`[统计] 总更新次数: ${equityUpdateCount}`);

    // 6. 确保在概览面板
    console.log('[步骤 6] 切换到概览面板...');
    const overviewBtn = page.locator('button:has-text("概览")').first();
    if (await overviewBtn.isVisible().catch(() => false)) {
      // 检查是否已经是概览面板
      const btnClass = await overviewBtn.getAttribute('class').catch(() => '');
      if (!btnClass?.includes('bg-[#2962ff]')) {
        await overviewBtn.click();
        await page.waitForTimeout(1000);
        console.log('[操作] 点击概览按钮');
      } else {
        console.log('[状态] 已经在概览面板');
      }
    } else {
      console.log('[警告] 未找到概览按钮');
    }

    // 7. 提取指标数据
    console.log('\n[步骤 7] 提取指标数据...');
    
    // 等待数据渲染
    await page.waitForTimeout(2000);

    // 尝试多种选择器
    const selectors = [
      '.core-metric-item',
      '.metrics-panel .core-metric-item',
      '[class*="metrics-panel"] .core-metric-item',
      '.metric-item',
    ];

    for (const selector of selectors) {
      const count = await page.locator(selector).count();
      console.log(`[选择器] ${selector}: ${count} 个元素`);
    }

    // 提取核心指标
    const coreMetrics = page.locator('.core-metric-item');
    const coreMetricsCount = await coreMetrics.count();
    console.log(`[核心指标数量] ${coreMetricsCount}`);
    
    const extractedMetrics: Record<string, string> = {};
    
    for (let i = 0; i < coreMetricsCount; i++) {
      const item = coreMetrics.nth(i);
      const label = await item.locator('.core-metric-label').textContent().catch(() => '');
      const value = await item.locator('.core-metric-value').textContent().catch(() => '');
      
      if (label && value) {
        extractedMetrics[label.trim()] = value.trim();
        console.log(`[核心指标] ${label.trim()}: ${value.trim()}`);
      }
    }

    // 提取次要指标
    const metricItems = page.locator('.metric-item');
    const metricItemsCount = await metricItems.count();
    console.log(`\n[次要指标数量] ${metricItemsCount}`);
    
    for (let i = 0; i < metricItemsCount; i++) {
      const item = metricItems.nth(i);
      const label = await item.locator('.metric-label').textContent().catch(() => '');
      const value = await item.locator('.metric-value').textContent().catch(() => '');
      
      if (label && value) {
        extractedMetrics[label.trim()] = value.trim();
        console.log(`[次要指标] ${label.trim()}: ${value.trim()}`);
      }
    }

    // 如果没有提取到指标，尝试从整个面板提取
    if (Object.keys(extractedMetrics).length === 0) {
      console.log('\n[备选] 尝试从整个面板提取...');
      
      const metricsPanel = page.locator('[class*="metrics-panel"], .metrics-panel').first();
      if (await metricsPanel.isVisible().catch(() => false)) {
        const panelText = await metricsPanel.textContent().catch(() => '');
        console.log(`[面板内容] ${panelText?.substring(0, 500)}...`);
        
        // 尝试解析所有带冒号的指标
        const matches = panelText?.matchAll(/([^\n:]+)[：:]\s*(-?\d+\.?\d*%?)/g) || [];
        for (const match of matches) {
          const label = match[1].trim();
          const value = match[2].trim();
          if (label && value && label.length < 20) {
            extractedMetrics[label] = value;
            console.log(`[解析指标] ${label}: ${value}`);
          }
        }
      }
    }

    // 8. 检查热力图
    console.log('\n[步骤 8] 检查月度收益热力图...');
    
    const heatmap = page.locator('[class*="heatmap"], [class*="Heatmap"], [class*="calendar"]').first();
    const hasHeatmap = await heatmap.isVisible().catch(() => false);
    console.log(`[热力图可见] ${hasHeatmap}`);

    // 9. 输出所有提取的指标
    console.log('\n========================================');
    console.log('提取的指标');
    console.log('========================================');
    Object.entries(extractedMetrics).forEach(([key, value]) => {
      console.log(`  ${key}: ${value}`);
    });
    console.log('========================================\n');

    // 10. 验证指标合理性
    if (Object.keys(extractedMetrics).length > 0) {
      // 解析累计收益
      if (extractedMetrics['累计收益']) {
        const totalReturnStr = extractedMetrics['累计收益'].replace('%', '').replace('+', '');
        const totalReturn = parseFloat(totalReturnStr);
        console.log(`[验证] 累计收益: ${totalReturn}%`);
        
        expect(totalReturn).toBeGreaterThan(-100);
        expect(totalReturn).toBeLessThan(500);
        console.log(`[验证] 累计收益合理性: 通过`);
      }

      // 解析最大回撤
      if (extractedMetrics['最大回撤']) {
        const maxDrawdownStr = extractedMetrics['最大回撤'].replace('%', '').replace('-', '');
        const maxDrawdown = parseFloat(maxDrawdownStr);
        console.log(`[验证] 最大回撤: ${maxDrawdown}%`);
        
        expect(maxDrawdown).toBeGreaterThanOrEqual(0);
        expect(maxDrawdown).toBeLessThan(100);
        console.log(`[验证] 最大回撤合理性: 通过`);
      }

      // 解析夏普比率
      if (extractedMetrics['夏普比率']) {
        const sharpe = parseFloat(extractedMetrics['夏普比率']);
        console.log(`[验证] 夏普比率: ${sharpe}`);
        
        expect(sharpe).toBeGreaterThan(-5);
        expect(sharpe).toBeLessThan(10);
        console.log(`[验证] 夏普比率合理性: 通过`);
      }
    }

    // 最终断言
    expect(Object.keys(extractedMetrics).length).toBeGreaterThan(0);
  });
});
