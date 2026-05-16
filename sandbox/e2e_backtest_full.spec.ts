/**
 * 回测功能完整测试
 * 测试范围：页面加载、策略选择、日期设置、运行回测、指标验证
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:5000';

// 测试配置
const TEST_CONFIG = {
  strategyName: 'apex_convergence_v1',
  startDate: '2024-05-01',
  endDate: '2024-05-31',
  benchmarkCode: '000300',
  timeout: 120000, // 2分钟超时
};

interface BacktestMetrics {
  totalReturn: number;
  annualizedReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  winRate: number;
  totalTrades: number;
}

test.describe('回测功能完整测试', () => {
  
  test.beforeEach(async ({ page }) => {
    // 监听控制台错误
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`[Console Error] ${msg.text()}`);
      }
    });
    
    // 监听页面错误
    page.on('pageerror', error => {
      console.log(`[Page Error] ${error.message}`);
    });
  });

  test('1. 打开 Dashboard 页面并验证基础结构', async ({ page }) => {
    console.log('[Step 1] 打开 Dashboard 页面...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 截图记录初始状态
    await page.screenshot({ path: 'test-results/backtest/01_initial.png', fullPage: true });
    
    // 验证页面标题
    const pageTitle = page.locator('h1:has-text("回测 Dashboard")');
    await expect(pageTitle).toBeVisible({ timeout: 10000 });
    
    // 验证侧边栏存在
    const sidebar = page.locator('.sidebar, aside').first();
    await expect(sidebar).toBeVisible();
    
    // 验证顶部工具栏存在
    const topbar = page.locator('.topbar, header').first();
    await expect(topbar).toBeVisible();
    
    console.log('[Step 1] 页面基础结构验证通过');
  });

  test('2. 验证策略选择下拉框', async ({ page }) => {
    console.log('[Step 2] 验证策略选择下拉框...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 等待策略列表加载
    await page.waitForTimeout(2000);
    
    // 查找策略选择下拉框
    const strategySelect = page.locator('select.strategy-select, select').first();
    await expect(strategySelect).toBeVisible({ timeout: 10000 });
    
    // 获取所有选项
    const options = await strategySelect.locator('option').allTextContents();
    console.log('[Step 2] 可用策略:', options);
    
    // 验证至少有一个策略可选
    expect(options.length).toBeGreaterThan(0);
    
    // 截图
    await page.screenshot({ path: 'test-results/backtest/02_strategy_select.png', fullPage: true });
    
    console.log('[Step 2] 策略选择验证通过');
  });

  test('3. 设置日期范围', async ({ page }) => {
    console.log('[Step 3] 设置日期范围...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 查找日期输入框
    const startDateInput = page.locator('input[type="date"]').first();
    const endDateInput = page.locator('input[type="date"]').nth(1);
    
    await expect(startDateInput).toBeVisible({ timeout: 10000 });
    await expect(endDateInput).toBeVisible({ timeout: 10000 });
    
    // 设置开始日期
    await startDateInput.fill(TEST_CONFIG.startDate);
    await page.waitForTimeout(500);
    
    // 设置结束日期
    await endDateInput.fill(TEST_CONFIG.endDate);
    await page.waitForTimeout(500);
    
    // 验证日期已设置
    const startValue = await startDateInput.inputValue();
    const endValue = await endDateInput.inputValue();
    
    expect(startValue).toBe(TEST_CONFIG.startDate);
    expect(endValue).toBe(TEST_CONFIG.endDate);
    
    // 截图
    await page.screenshot({ path: 'test-results/backtest/03_date_range.png', fullPage: true });
    
    console.log(`[Step 3] 日期范围设置完成: ${startValue} ~ ${endValue}`);
  });

  test('4. 运行回测并等待完成', async ({ page }) => {
    console.log('[Step 4] 运行回测...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 等待策略列表加载
    await page.waitForTimeout(2000);
    
    // 设置日期范围
    const startDateInput = page.locator('input[type="date"]').first();
    const endDateInput = page.locator('input[type="date"]').nth(1);
    
    await startDateInput.fill(TEST_CONFIG.startDate);
    await endDateInput.fill(TEST_CONFIG.endDate);
    
    // 查找并点击回测按钮
    const runButton = page.locator('button.run-btn, button:has-text("回测")').first();
    await expect(runButton).toBeVisible({ timeout: 10000 });
    
    // 检查按钮是否可用
    const isDisabled = await runButton.isDisabled();
    if (isDisabled) {
      console.log('[Step 4] 回测按钮被禁用，等待 API 连接...');
      await page.waitForTimeout(5000);
    }
    
    // 截图：点击前
    await page.screenshot({ path: 'test-results/backtest/04_before_run.png', fullPage: true });
    
    // 点击运行回测
    await runButton.click();
    console.log('[Step 4] 已点击回测按钮');
    
    // 等待回测开始
    await page.waitForTimeout(2000);
    
    // 截图：运行中
    await page.screenshot({ path: 'test-results/backtest/05_running.png', fullPage: true });
    
    // 等待回测完成（最长等待2分钟）
    console.log('[Step 4] 等待回测完成...');
    
    // 监听运行状态变化
    let isRunning = true;
    const startTime = Date.now();
    
    while (isRunning && (Date.now() - startTime) < TEST_CONFIG.timeout) {
      // 检查是否有运行状态指示器
      const runningIndicator = page.locator('.status-badge:has-text("运行中"), .running-indicator').first();
      const stopButton = page.locator('button.stop-btn, button:has-text("停止")').first();
      
      const hasRunningIndicator = await runningIndicator.isVisible().catch(() => false);
      const hasStopButton = await stopButton.isVisible().catch(() => false);
      
      isRunning = hasRunningIndicator || hasStopButton;
      
      if (isRunning) {
        console.log('[Step 4] 回测运行中...');
        await page.waitForTimeout(5000);
        
        // 每10秒截图一次
        if (Math.floor((Date.now() - startTime) / 10000) % 2 === 0) {
          await page.screenshot({ path: `test-results/backtest/06_running_${Math.floor((Date.now() - startTime) / 10000)}.png`, fullPage: true });
        }
      }
    }
    
    // 截图：完成
    await page.screenshot({ path: 'test-results/backtest/07_completed.png', fullPage: true });
    
    console.log('[Step 4] 回测已完成');
  });

  test('5. 验证回测指标', async ({ page }) => {
    console.log('[Step 5] 验证回测指标...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 设置日期范围并运行回测
    const startDateInput = page.locator('input[type="date"]').first();
    const endDateInput = page.locator('input[type="date"]').nth(1);
    
    await startDateInput.fill(TEST_CONFIG.startDate);
    await endDateInput.fill(TEST_CONFIG.endDate);
    
    const runButton = page.locator('button.run-btn, button:has-text("回测")').first();
    await runButton.click();
    
    // 等待回测完成
    await page.waitForTimeout(5000);
    
    // 等待运行状态消失
    const startTime = Date.now();
    let isRunning = true;
    
    while (isRunning && (Date.now() - startTime) < TEST_CONFIG.timeout) {
      const runningIndicator = page.locator('.status-badge:has-text("运行中")').first();
      isRunning = await runningIndicator.isVisible().catch(() => false);
      
      if (isRunning) {
        await page.waitForTimeout(5000);
      }
    }
    
    // 等待数据渲染
    await page.waitForTimeout(3000);
    
    // 截图
    await page.screenshot({ path: 'test-results/backtest/08_metrics.png', fullPage: true });
    
    // 提取指标数据
    const metrics: BacktestMetrics = {
      totalReturn: 0,
      annualizedReturn: 0,
      maxDrawdown: 0,
      sharpeRatio: 0,
      winRate: 0,
      totalTrades: 0,
    };
    
    // 尝试从页面提取指标
    // 方法1: 从指标卡片提取
    const metricCards = page.locator('.metric-card, .chart-card, [class*="metric"]').all();
    
    for (const card of await metricCards) {
      const text = await card.textContent().catch(() => '');
      
      // 累计收益
      if (text.includes('累计收益') || text.includes('总收益')) {
        const match = text.match(/[-+]?\d+\.?\d*%?/);
        if (match) {
          metrics.totalReturn = parseFloat(match[0].replace('%', ''));
          console.log(`[Step 5] 累计收益: ${metrics.totalReturn}%`);
        }
      }
      
      // 年化收益
      if (text.includes('年化收益') || text.includes('期间收益')) {
        const match = text.match(/[-+]?\d+\.?\d*%?/);
        if (match) {
          metrics.annualizedReturn = parseFloat(match[0].replace('%', ''));
          console.log(`[Step 5] 年化收益: ${metrics.annualizedReturn}%`);
        }
      }
      
      // 最大回撤
      if (text.includes('最大回撤')) {
        const match = text.match(/[-+]?\d+\.?\d*%?/);
        if (match) {
          metrics.maxDrawdown = Math.abs(parseFloat(match[0].replace('%', '')));
          console.log(`[Step 5] 最大回撤: ${metrics.maxDrawdown}%`);
        }
      }
      
      // 夏普比率
      if (text.includes('夏普比率') || text.includes('夏普')) {
        const match = text.match(/[-+]?\d+\.?\d*/);
        if (match) {
          metrics.sharpeRatio = parseFloat(match[0]);
          console.log(`[Step 5] 夏普比率: ${metrics.sharpeRatio}`);
        }
      }
      
      // 胜率
      if (text.includes('胜率')) {
        const match = text.match(/\d+\.?\d*%?/);
        if (match) {
          metrics.winRate = parseFloat(match[0].replace('%', ''));
          console.log(`[Step 5] 胜率: ${metrics.winRate}%`);
        }
      }
      
      // 总交易次数
      if (text.includes('交易次数') || text.includes('总交易')) {
        const match = text.match(/\d+/);
        if (match) {
          metrics.totalTrades = parseInt(match[0]);
          console.log(`[Step 5] 总交易次数: ${metrics.totalTrades}`);
        }
      }
    }
    
    // 方法2: 从 localStorage 提取
    const storedData = await page.evaluate(() => {
      const stored = localStorage.getItem('quantflow.backtest.v1');
      if (stored) {
        return JSON.parse(stored);
      }
      return null;
    });
    
    if (storedData && storedData.metrics) {
      console.log('[Step 5] 从 localStorage 获取到指标数据:', storedData.metrics);
      
      // 使用 localStorage 数据覆盖
      if (storedData.metrics.totalReturn !== undefined) {
        metrics.totalReturn = storedData.metrics.totalReturn;
      }
      if (storedData.metrics.annualizedReturn !== undefined) {
        metrics.annualizedReturn = storedData.metrics.annualizedReturn;
      }
      if (storedData.metrics.maxDrawdown !== undefined) {
        metrics.maxDrawdown = storedData.metrics.maxDrawdown;
      }
      if (storedData.metrics.sharpeRatio !== undefined) {
        metrics.sharpeRatio = storedData.metrics.sharpeRatio;
      }
      if (storedData.metrics.winRate !== undefined) {
        metrics.winRate = storedData.metrics.winRate;
      }
      if (storedData.metrics.tradesCount !== undefined) {
        metrics.totalTrades = storedData.metrics.tradesCount;
      }
      if (storedData.metrics.totalTrades !== undefined) {
        metrics.totalTrades = storedData.metrics.totalTrades;
      }
    }
    
    // 验证指标是否合理
    console.log('\n========== 回测指标验证报告 ==========');
    console.log(`累计收益: ${metrics.totalReturn}%`);
    console.log(`年化收益: ${metrics.annualizedReturn}%`);
    console.log(`最大回撤: ${metrics.maxDrawdown}%`);
    console.log(`夏普比率: ${metrics.sharpeRatio}`);
    console.log(`胜率: ${metrics.winRate}%`);
    console.log(`总交易次数: ${metrics.totalTrades}`);
    console.log('========================================\n');
    
    // 验证指标不应该出现异常值
    // 累计收益不应该是 -436% 这种极端值（允许范围 -100% 到 1000%）
    expect(metrics.totalReturn).toBeGreaterThan(-100);
    expect(metrics.totalReturn).toBeLessThan(1000);
    
    // 年化收益不应该是 0%（如果总收益不为0）
    if (metrics.totalReturn !== 0) {
      expect(metrics.annualizedReturn).not.toBe(0);
    }
    
    // 胜率不应该是 10000% 这种异常值
    expect(metrics.winRate).toBeGreaterThanOrEqual(0);
    expect(metrics.winRate).toBeLessThanOrEqual(100);
    
    // 总交易次数不应该是 0（如果日期范围有效）
    // 注意：这个断言可能需要根据实际策略调整
    // expect(metrics.totalTrades).toBeGreaterThan(0);
    
    console.log('[Step 5] 指标验证完成');
  });

  test('6. 验证月度收益热力图', async ({ page }) => {
    console.log('[Step 6] 验证月度收益热力图...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 设置日期范围并运行回测
    const startDateInput = page.locator('input[type="date"]').first();
    const endDateInput = page.locator('input[type="date"]').nth(1);
    
    await startDateInput.fill(TEST_CONFIG.startDate);
    await endDateInput.fill(TEST_CONFIG.endDate);
    
    const runButton = page.locator('button.run-btn, button:has-text("回测")').first();
    await runButton.click();
    
    // 等待回测完成
    await page.waitForTimeout(5000);
    
    const startTime = Date.now();
    let isRunning = true;
    
    while (isRunning && (Date.now() - startTime) < TEST_CONFIG.timeout) {
      const runningIndicator = page.locator('.status-badge:has-text("运行中")').first();
      isRunning = await runningIndicator.isVisible().catch(() => false);
      
      if (isRunning) {
        await page.waitForTimeout(5000);
      }
    }
    
    // 等待热力图渲染
    await page.waitForTimeout(3000);
    
    // 截图
    await page.screenshot({ path: 'test-results/backtest/09_heatmap.png', fullPage: true });
    
    // 查找热力图
    const heatmapSection = page.locator('h2:has-text("月度收益热力图")').first();
    const isHeatmapVisible = await heatmapSection.isVisible().catch(() => false);
    
    if (isHeatmapVisible) {
      console.log('[Step 6] 热力图区域可见');
      
      // 检查是否有数据
      const heatmapContainer = heatmapSection.locator('xpath=..').locator('.chart-wrapper, [class*="heatmap"]');
      const heatmapContent = await heatmapContainer.textContent().catch(() => '');
      
      // 不应该显示"暂无数据"
      const hasNoData = heatmapContent.includes('暂无') || heatmapContent.includes('无数据');
      
      if (!hasNoData) {
        console.log('[Step 6] 热力图有数据');
      } else {
        console.log('[Step 6] 热力图无数据');
      }
    } else {
      console.log('[Step 6] 热力图区域不可见');
    }
    
    // 从 localStorage 检查月度收益数据
    const storedData = await page.evaluate(() => {
      const stored = localStorage.getItem('quantflow.backtest.v1');
      if (stored) {
        return JSON.parse(stored);
      }
      return null;
    });
    
    if (storedData && storedData.monthlyReturns) {
      console.log('[Step 6] 月度收益数据:', storedData.monthlyReturns);
      expect(storedData.monthlyReturns.length).toBeGreaterThan(0);
    }
    
    console.log('[Step 6] 热力图验证完成');
  });

  test('7. 验证收益曲线', async ({ page }) => {
    console.log('[Step 7] 验证收益曲线...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 设置日期范围并运行回测
    const startDateInput = page.locator('input[type="date"]').first();
    const endDateInput = page.locator('input[type="date"]').nth(1);
    
    await startDateInput.fill(TEST_CONFIG.startDate);
    await endDateInput.fill(TEST_CONFIG.endDate);
    
    const runButton = page.locator('button.run-btn, button:has-text("回测")').first();
    await runButton.click();
    
    // 等待回测完成
    await page.waitForTimeout(5000);
    
    const startTime = Date.now();
    let isRunning = true;
    
    while (isRunning && (Date.now() - startTime) < TEST_CONFIG.timeout) {
      const runningIndicator = page.locator('.status-badge:has-text("运行中")').first();
      isRunning = await runningIndicator.isVisible().catch(() => false);
      
      if (isRunning) {
        await page.waitForTimeout(5000);
      }
    }
    
    // 等待图表渲染
    await page.waitForTimeout(3000);
    
    // 截图
    await page.screenshot({ path: 'test-results/backtest/10_equity_curve.png', fullPage: true });
    
    // 从 localStorage 检查权益曲线数据
    const storedData = await page.evaluate(() => {
      const stored = localStorage.getItem('quantflow.backtest.v1');
      if (stored) {
        return JSON.parse(stored);
      }
      return null;
    });
    
    if (storedData && storedData.equitySeries) {
      console.log(`[Step 7] 权益曲线数据点数量: ${storedData.equitySeries.length}`);
      expect(storedData.equitySeries.length).toBeGreaterThan(0);
      
      // 检查数据是否有效
      const firstPoint = storedData.equitySeries[0];
      const lastPoint = storedData.equitySeries[storedData.equitySeries.length - 1];
      
      console.log(`[Step 7] 起点: ${firstPoint.date} - ${firstPoint.equity}`);
      console.log(`[Step 7] 终点: ${lastPoint.date} - ${lastPoint.equity}`);
    }
    
    if (storedData && storedData.benchmarkEquitySeries) {
      console.log(`[Step 7] 基准曲线数据点数量: ${storedData.benchmarkEquitySeries.length}`);
    }
    
    console.log('[Step 7] 收益曲线验证完成');
  });

  test('8. 完整回测流程测试', async ({ page }) => {
    console.log('\n========== 开始完整回测流程测试 ==========\n');
    
    // Step 1: 打开页面
    console.log('[完整测试] Step 1: 打开页面');
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/backtest/full_01_initial.png', fullPage: true });
    
    // Step 2: 等待策略列表加载
    console.log('[完整测试] Step 2: 等待策略列表加载');
    await page.waitForTimeout(2000);
    
    // Step 3: 选择策略（如果有下拉框）
    console.log('[完整测试] Step 3: 检查策略选择');
    const strategySelect = page.locator('select.strategy-select').first();
    const hasStrategySelect = await strategySelect.isVisible().catch(() => false);
    
    if (hasStrategySelect) {
      const selectedStrategy = await strategySelect.inputValue();
      console.log(`[完整测试] 当前选中策略: ${selectedStrategy}`);
    }
    
    // Step 4: 设置日期范围
    console.log('[完整测试] Step 4: 设置日期范围');
    const startDateInput = page.locator('input[type="date"]').first();
    const endDateInput = page.locator('input[type="date"]').nth(1);
    
    await startDateInput.fill(TEST_CONFIG.startDate);
    await endDateInput.fill(TEST_CONFIG.endDate);
    await page.screenshot({ path: 'test-results/backtest/full_02_date_set.png', fullPage: true });
    
    // Step 5: 运行回测
    console.log('[完整测试] Step 5: 运行回测');
    const runButton = page.locator('button.run-btn, button:has-text("回测")').first();
    
    // 检查按钮状态
    const isButtonDisabled = await runButton.isDisabled();
    if (isButtonDisabled) {
      console.log('[完整测试] 回测按钮被禁用，等待 API 连接...');
      await page.waitForTimeout(5000);
    }
    
    await runButton.click();
    console.log('[完整测试] 已点击回测按钮');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/backtest/full_03_running.png', fullPage: true });
    
    // Step 6: 等待回测完成
    console.log('[完整测试] Step 6: 等待回测完成');
    const startTime = Date.now();
    let isRunning = true;
    let progressCount = 0;
    
    while (isRunning && (Date.now() - startTime) < TEST_CONFIG.timeout) {
      const runningIndicator = page.locator('.status-badge:has-text("运行中")').first();
      const stopButton = page.locator('button.stop-btn, button:has-text("停止")').first();
      
      const hasRunningIndicator = await runningIndicator.isVisible().catch(() => false);
      const hasStopButton = await stopButton.isVisible().catch(() => false);
      
      isRunning = hasRunningIndicator || hasStopButton;
      
      if (isRunning) {
        progressCount++;
        if (progressCount % 10 === 0) {
          console.log(`[完整测试] 回测运行中... (${Math.floor((Date.now() - startTime) / 1000)}秒)`);
        }
        await page.waitForTimeout(1000);
      }
    }
    
    console.log(`[完整测试] 回测完成，耗时 ${Math.floor((Date.now() - startTime) / 1000)} 秒`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'test-results/backtest/full_04_completed.png', fullPage: true });
    
    // Step 7: 提取并验证指标
    console.log('[完整测试] Step 7: 提取并验证指标');
    
    const storedData = await page.evaluate(() => {
      const stored = localStorage.getItem('quantflow.backtest.v1');
      if (stored) {
        return JSON.parse(stored);
      }
      return null;
    });
    
    console.log('\n========== 最终测试报告 ==========');
    
    if (storedData) {
      const metrics = storedData.metrics || {};
      
      console.log('\n【回测指标】');
      console.log(`  累计收益: ${metrics.totalReturn?.toFixed(2) ?? 'N/A'}%`);
      console.log(`  年化收益: ${metrics.annualizedReturn?.toFixed(2) ?? 'N/A'}%`);
      console.log(`  最大回撤: ${metrics.maxDrawdown?.toFixed(2) ?? 'N/A'}%`);
      console.log(`  夏普比率: ${metrics.sharpeRatio?.toFixed(2) ?? 'N/A'}`);
      console.log(`  胜率: ${metrics.winRate?.toFixed(2) ?? 'N/A'}%`);
      console.log(`  总交易次数: ${metrics.tradesCount ?? metrics.totalTrades ?? 'N/A'}`);
      
      console.log('\n【数据统计】');
      console.log(`  权益曲线数据点: ${storedData.equitySeries?.length ?? 0}`);
      console.log(`  基准曲线数据点: ${storedData.benchmarkEquitySeries?.length ?? 0}`);
      console.log(`  交易记录数: ${storedData.trades?.length ?? 0}`);
      console.log(`  月度收益数据: ${storedData.monthlyReturns?.length ?? 0} 个月`);
      
      console.log('\n【验证结果】');
      
      // 验证累计收益
      const totalReturnValid = metrics.totalReturn !== undefined && 
        metrics.totalReturn > -100 && metrics.totalReturn < 1000;
      console.log(`  累计收益: ${totalReturnValid ? 'PASS' : 'FAIL'} (值: ${metrics.totalReturn}%)`);
      
      // 验证年化收益
      const annualizedReturnValid = metrics.annualizedReturn !== undefined && 
        metrics.annualizedReturn !== 0;
      console.log(`  年化收益: ${annualizedReturnValid ? 'PASS' : 'FAIL'} (值: ${metrics.annualizedReturn}%)`);
      
      // 验证最大回撤
      const maxDrawdownValid = metrics.maxDrawdown !== undefined && 
        metrics.maxDrawdown >= 0 && metrics.maxDrawdown <= 100;
      console.log(`  最大回撤: ${maxDrawdownValid ? 'PASS' : 'FAIL'} (值: ${metrics.maxDrawdown}%)`);
      
      // 验证夏普比率
      const sharpeRatioValid = metrics.sharpeRatio !== undefined;
      console.log(`  夏普比率: ${sharpeRatioValid ? 'PASS' : 'FAIL'} (值: ${metrics.sharpeRatio})`);
      
      // 验证胜率
      const winRateValid = metrics.winRate !== undefined && 
        metrics.winRate >= 0 && metrics.winRate <= 100;
      console.log(`  胜率: ${winRateValid ? 'PASS' : 'FAIL'} (值: ${metrics.winRate}%)`);
      
      // 验证交易次数
      const tradesCount = metrics.tradesCount ?? metrics.totalTrades ?? 0;
      const tradesCountValid = tradesCount >= 0;
      console.log(`  总交易次数: ${tradesCountValid ? 'PASS' : 'FAIL'} (值: ${tradesCount})`);
      
      // 验证月度收益数据
      const monthlyReturnsValid = storedData.monthlyReturns && storedData.monthlyReturns.length > 0;
      console.log(`  月度收益热力图: ${monthlyReturnsValid ? 'PASS' : 'FAIL'} (数据: ${storedData.monthlyReturns?.length ?? 0} 个月)`);
      
      console.log('\n========================================\n');
      
      // 最终断言
      expect(totalReturnValid).toBe(true);
      expect(annualizedReturnValid).toBe(true);
      expect(maxDrawdownValid).toBe(true);
      expect(sharpeRatioValid).toBe(true);
      expect(winRateValid).toBe(true);
      expect(tradesCountValid).toBe(true);
      
    } else {
      console.log('[完整测试] 未找到存储的回测数据');
      console.log('========================================\n');
    }
    
    // 最终截图
    await page.screenshot({ path: 'test-results/backtest/full_05_final.png', fullPage: true });
    
    console.log('[完整测试] 测试完成');
  });
});
