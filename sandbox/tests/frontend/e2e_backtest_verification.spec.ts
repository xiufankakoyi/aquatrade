/**
 * Dashboard 回测功能完整验证测试
 * 
 * 测试目标：
 * 1. 验证页面加载和策略选择
 * 2. 验证日期范围设置
 * 3. 验证回测运行和流式传输
 * 4. 验证多维概览面板数据正确性
 * 5. 验证月度收益热力图数据
 * 
 * 重点验证：
 * - 累计收益是否显示正确数值（不应该是 -436%）
 * - 流式传输是否工作（净值曲线逐步更新）
 * - 最终指标是否正确显示
 * - 月度收益热力图是否有数据
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:5000';

// 测试配置
const TEST_CONFIG = {
  // 使用实际存在的策略名称
  strategies: ['聚宽量比市值策略V5_趋势增强', '聚宽量比市值策略', 'simple_momentum'],
  startDate: '2024-05-01',
  endDate: '2024-05-31',
  timeout: 120000, // 2分钟超时
};

// 测试结果接口
interface BacktestTestResult {
  strategyName: string;
  strategyId: string;
  streamingWorked: boolean;
  equityUpdateCount: number;
  finalMetrics: {
    totalReturn: number;
    annualReturn: number;
    maxDrawdown: number;
    sharpeRatio: number;
    winRate: number;
    profitFactor: number;
    totalTrades: number;
    benchmarkReturn: number;
  } | null;
  metricsReasonable: boolean;
  hasMonthlyReturns: boolean;
  monthlyReturnsCount: number;
  errors: string[];
  consoleLogs: string[];
  socketEvents: string[];
  executionTime: number;
  screenshots: string[];
  backtestStarted: boolean;
  backtestCompleted: boolean;
}

/**
 * 检查后端服务是否可用
 */
async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/strategies`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
    return response.ok;
  } catch {
    return false;
  }
}

test.describe('Dashboard 回测功能完整验证', () => {
  let testResult: BacktestTestResult;

  test.beforeEach(async ({ page }) => {
    // 初始化测试结果
    testResult = {
      strategyName: '',
      strategyId: '',
      streamingWorked: false,
      equityUpdateCount: 0,
      finalMetrics: null,
      metricsReasonable: false,
      hasMonthlyReturns: false,
      monthlyReturnsCount: 0,
      errors: [],
      consoleLogs: [],
      socketEvents: [],
      executionTime: 0,
      screenshots: [],
      backtestStarted: false,
      backtestCompleted: false
    };

    // 监听控制台消息
    page.on('console', msg => {
      const text = msg.text();
      
      // 记录关键日志
      if (text.includes('Socket') || text.includes('backtest') || 
          text.includes('equity') || text.includes('streaming') ||
          text.includes('daily') || text.includes('metrics') ||
          text.includes('MsgPack') || text.includes('策略') ||
          text.includes('Dashboard') || text.includes('backtestStore') ||
          text.includes('运行') || text.includes('progress')) {
        testResult.consoleLogs.push(`[${msg.type()}] ${text}`);
      }
      
      // 记录错误
      if (msg.type() === 'error') {
        if (!text.includes('favicon') && !text.includes('source map')) {
          testResult.errors.push(`[Console Error] ${text}`);
        }
      }
    });

    // 监听页面错误
    page.on('pageerror', error => {
      testResult.errors.push(`[Page Error] ${error.message}`);
    });

    // 监听网络请求
    page.on('request', request => {
      if (request.url().includes('socket.io') || request.url().includes('backtest')) {
        testResult.socketEvents.push(`[Request] ${request.method()} ${request.url()}`);
      }
    });

    page.on('response', response => {
      if (response.status() >= 400 && !response.url().includes('favicon')) {
        testResult.errors.push(`[HTTP ${response.status()}] ${response.url()}`);
      }
    });
  });

  test('前置检查：后端服务可用性', async () => {
    const isHealthy = await checkBackendHealth();
    console.log(`[前置检查] 后端服务状态: ${isHealthy ? '正常' : '不可用'}`);
    expect(isHealthy).toBe(true);
  });

  test('完整回测流程验证', async ({ page }) => {
    const startTime = Date.now();

    console.log('\n========================================');
    console.log('Dashboard 回测功能完整验证测试');
    console.log(`日期范围: ${TEST_CONFIG.startDate} ~ ${TEST_CONFIG.endDate}`);
    console.log('========================================\n');

    // ========================================
    // 步骤 1: 导航到 Dashboard 页面
    // ========================================
    console.log('[步骤 1] 导航到 Dashboard 页面...');
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 截图：初始页面
    const screenshot1 = 'sandbox/reports/dashboard_01_initial.png';
    await page.screenshot({ path: screenshot1, fullPage: false });
    testResult.screenshots.push(screenshot1);
    console.log(`[截图] ${screenshot1}`);

    // ========================================
    // 步骤 2: 选择策略
    // ========================================
    console.log('[步骤 2] 选择策略...');
    
    // 查找策略选择器（combobox）
    const strategySelector = page.locator('combobox, select').first();
    await strategySelector.waitFor({ state: 'visible', timeout: 10000 });
    
    // 获取所有选项
    const options = await strategySelector.locator('option').allTextContents();
    console.log(`[状态] 策略选项: ${options.slice(0, 5).join(', ')}...`);
    
    // 查找目标策略
    let targetStrategy = '';
    for (const strategyName of TEST_CONFIG.strategies) {
      const found = options.find(opt => opt.includes(strategyName) || opt.includes(strategyName.split('_')[0]));
      if (found) {
        targetStrategy = found;
        break;
      }
    }
    
    if (!targetStrategy && options.length > 0) {
      // 选择第一个非空选项
      targetStrategy = options.find(opt => opt && opt.trim()) || options[0];
    }
    
    if (targetStrategy) {
      await strategySelector.selectOption({ label: targetStrategy });
      testResult.strategyName = targetStrategy;
      console.log(`[选择] 已选择策略: ${targetStrategy}`);
    } else {
      console.log('[错误] 未找到可选择的策略');
      testResult.errors.push('未找到可选择的策略');
    }

    // ========================================
    // 步骤 3: 设置日期范围
    // ========================================
    console.log('[步骤 3] 设置日期范围...');
    
    const dateInputs = await page.locator('input[type="date"], textbox[type="date"]').all();
    console.log(`[状态] 发现 ${dateInputs.length} 个日期输入框`);

    if (dateInputs.length >= 2) {
      // 设置开始日期
      await dateInputs[0].fill(TEST_CONFIG.startDate);
      console.log(`[设置] 开始日期: ${TEST_CONFIG.startDate}`);
      
      // 设置结束日期
      await dateInputs[1].fill(TEST_CONFIG.endDate);
      console.log(`[设置] 结束日期: ${TEST_CONFIG.endDate}`);
    } else {
      // 尝试其他选择器
      const startDateInput = page.locator('input').filter({ hasText: '' }).nth(0);
      const endDateInput = page.locator('input').filter({ hasText: '' }).nth(1);
      
      try {
        await startDateInput.fill(TEST_CONFIG.startDate);
        await endDateInput.fill(TEST_CONFIG.endDate);
        console.log(`[设置] 通过备选选择器设置日期`);
      } catch (e) {
        console.log('[警告] 无法设置日期');
      }
    }

    // 截图：配置完成
    const screenshot2 = 'sandbox/reports/dashboard_02_configured.png';
    await page.screenshot({ path: screenshot2, fullPage: false });
    testResult.screenshots.push(screenshot2);

    // ========================================
    // 步骤 4: 点击回测按钮
    // ========================================
    console.log('[步骤 4] 点击回测按钮...');
    
    // 查找回测按钮 - 使用多种选择器
    const backButtonSelectors = [
      'button:has-text("回测")',
      'button:has-text("运行")',
      'button:has-text("运行回测")',
      'button >> text="回测"',
    ];
    
    let backButtonClicked = false;
    for (const selector of backButtonSelectors) {
      const backButton = page.locator(selector).first();
      if (await backButton.isVisible().catch(() => false)) {
        const isDisabled = await backButton.isDisabled().catch(() => true);
        if (!isDisabled) {
          await backButton.click();
          backButtonClicked = true;
          testResult.backtestStarted = true;
          console.log(`[操作] 已点击回测按钮 (选择器: ${selector})`);
          break;
        } else {
          console.log(`[警告] 回测按钮被禁用 (选择器: ${selector})`);
          const title = await backButton.getAttribute('title').catch(() => '');
          if (title) {
            console.log(`[原因] ${title}`);
            testResult.errors.push(`回测按钮禁用: ${title}`);
          }
        }
      }
    }
    
    if (!backButtonClicked) {
      console.log('[警告] 未找到可点击的回测按钮');
      testResult.errors.push('未找到可点击的回测按钮');
    }

    // ========================================
    // 步骤 5: 监控回测进度和流式更新
    // ========================================
    console.log('[步骤 5] 监控回测进度和流式更新...');
    
    let equityUpdateTimestamps: number[] = [];
    let lastMetricsText = '';
    let progressDetected = false;

    // 等待回测开始
    await page.waitForTimeout(2000);

    // 监控回测状态
    const maxWaitTime = TEST_CONFIG.timeout;
    const checkStartTime = Date.now();
    let checkCount = 0;

    while ((Date.now() - checkStartTime) < maxWaitTime) {
      checkCount++;
      await page.waitForTimeout(1000);
      
      const elapsed = Math.floor((Date.now() - checkStartTime) / 1000);
      
      // 检查是否有进度指示
      const progressIndicator = await page.locator('[class*="progress"], [class*="spinner"], [class*="loading"]').first()
        .isVisible().catch(() => false);
      
      // 检查是否有图表显示
      const hasChart = await page.locator('canvas').first()
        .isVisible().catch(() => false);
      
      // 检查指标面板
      const metricsPanel = page.locator('[class*="metrics"], [class*="Metrics"]').first();
      const hasMetrics = await metricsPanel.isVisible().catch(() => false);
      
      // 获取指标文本
      if (hasMetrics) {
        const currentMetricsText = await metricsPanel.textContent().catch(() => '');
        if (currentMetricsText !== lastMetricsText && !currentMetricsText.includes('--')) {
          lastMetricsText = currentMetricsText;
          console.log(`[指标更新] ${currentMetricsText.substring(0, 100)}...`);
        }
      }
      
      // 记录 canvas 更新
      if (hasChart) {
        equityUpdateTimestamps.push(Date.now());
        testResult.equityUpdateCount++;
      }
      
      // 检测进度
      if (progressIndicator && !progressDetected) {
        progressDetected = true;
        console.log(`[进度] 检测到回测运行中 (${elapsed}s)`);
      }
      
      // 每 15 秒输出状态
      if (elapsed % 15 === 0 && elapsed > 0 && checkCount % 15 === 0) {
        console.log(`[状态 ${elapsed}s] 图表: ${hasChart}, 指标: ${hasMetrics}, 进度: ${progressIndicator}, 更新次数: ${testResult.equityUpdateCount}`);
      }
      
      // 如果有指标数据且没有进度指示，可能已完成
      if (hasMetrics && !progressIndicator && hasChart && elapsed > 10) {
        // 检查指标是否有效（不是 --）
        const metricsText = await metricsPanel.textContent().catch(() => '');
        if (!metricsText.includes('--') && metricsText.length > 50) {
          console.log(`[状态] 检测到回测完成 (${elapsed}s)`);
          testResult.backtestCompleted = true;
          await page.waitForTimeout(2000); // 等待数据稳定
          break;
        }
      }
    }

    // ========================================
    // 步骤 6: 分析流式传输效果
    // ========================================
    console.log('[步骤 6] 分析流式传输效果...');
    
    if (equityUpdateTimestamps.length > 1) {
      const intervals: number[] = [];
      for (let i = 1; i < equityUpdateTimestamps.length; i++) {
        intervals.push(equityUpdateTimestamps[i] - equityUpdateTimestamps[i-1]);
      }
      const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      console.log(`[分析] 平均更新间隔: ${avgInterval.toFixed(0)}ms`);
      
      // 如果平均间隔小于 2 秒且有多次更新，说明是流式更新
      testResult.streamingWorked = avgInterval < 2000 && intervals.length > 5;
    }

    console.log(`[结果] 流式传输工作: ${testResult.streamingWorked}`);
    console.log(`[结果] 权益更新次数: ${testResult.equityUpdateCount}`);

    // ========================================
    // 步骤 7: 提取指标数据
    // ========================================
    console.log('[步骤 7] 提取指标数据...');
    
    // 尝试从多个位置提取指标
    const metricsSelectors = [
      '[class*="metrics-panel"]',
      '[class*="MetricsPanel"]',
      '[class*="metrics"]',
      '.metrics-panel'
    ];
    
    for (const selector of metricsSelectors) {
      const metricsPanel = page.locator(selector).first();
      if (await metricsPanel.isVisible().catch(() => false)) {
        const metricsText = await metricsPanel.textContent().catch(() => '');
        
        if (metricsText && !metricsText.includes('--')) {
          console.log(`[指标面板] 找到有效数据`);
          
          // 提取关键指标
          const totalReturnMatch = metricsText.match(/累计收益[：:\s]*([+-]?\d+\.?\d*)%?/i);
          const annualReturnMatch = metricsText.match(/年化收益[：:\s]*([+-]?\d+\.?\d*)%?/i);
          const maxDrawdownMatch = metricsText.match(/最大回撤[：:\s]*([+-]?\d+\.?\d*)%?/i);
          const sharpeMatch = metricsText.match(/夏普比率[：:\s]*([+-]?\d+\.?\d*)/i);
          const winRateMatch = metricsText.match(/胜率[：:\s]*([+-]?\d+\.?\d*)%?/i);
          const profitFactorMatch = metricsText.match(/盈亏比[：:\s]*([+-]?\d+\.?\d*)/i);
          const tradesMatch = metricsText.match(/总交易次数[：:\s]*(\d+)/i);
          const benchmarkMatch = metricsText.match(/基准收益[：:\s]*([+-]?\d+\.?\d*)%?/i);

          if (totalReturnMatch || maxDrawdownMatch || sharpeMatch) {
            testResult.finalMetrics = {
              totalReturn: totalReturnMatch ? parseFloat(totalReturnMatch[1]) : 0,
              annualReturn: annualReturnMatch ? parseFloat(annualReturnMatch[1]) : 0,
              maxDrawdown: maxDrawdownMatch ? parseFloat(maxDrawdownMatch[1]) : 0,
              sharpeRatio: sharpeMatch ? parseFloat(sharpeMatch[1]) : 0,
              winRate: winRateMatch ? parseFloat(winRateMatch[1]) : 0,
              profitFactor: profitFactorMatch ? parseFloat(profitFactorMatch[1]) : 0,
              totalTrades: tradesMatch ? parseInt(tradesMatch[1]) : 0,
              benchmarkReturn: benchmarkMatch ? parseFloat(benchmarkMatch[1]) : 0
            };
            break;
          }
        }
      }
    }

    // 验证指标合理性
    if (testResult.finalMetrics) {
      const { totalReturn, maxDrawdown, sharpeRatio } = testResult.finalMetrics;
      
      // 累计收益应该在合理范围内（-100% 到 500%）
      // 注意：-436% 是不合理的，说明数据有问题
      const isTotalReturnReasonable = totalReturn > -100 && totalReturn < 500;
      // 最大回撤通常显示为负数（表示亏损），范围 -100% ~ 0%
      const isMaxDrawdownReasonable = maxDrawdown >= -100 && maxDrawdown <= 0;
      const isSharpeReasonable = sharpeRatio > -5 && sharpeRatio < 10;
      
      testResult.metricsReasonable = isTotalReturnReasonable && isMaxDrawdownReasonable && isSharpeReasonable;
      
      console.log(`[指标验证] 合理性: ${testResult.metricsReasonable}`);
      console.log(`[指标] 累计收益: ${totalReturn}% (${isTotalReturnReasonable ? '合理' : '异常 - 可能是 -436% 问题'})`);
      console.log(`[指标] 最大回撤: ${maxDrawdown}% (${isMaxDrawdownReasonable ? '合理' : '异常'})`);
      console.log(`[指标] 夏普比率: ${sharpeRatio} (${isSharpeReasonable ? '合理' : '异常'})`);
      
      // 特别检查 -436% 问题
      if (totalReturn <= -100) {
        console.log(`[警告] 累计收益 ${totalReturn}% 超出合理范围，存在 -436% 问题！`);
        testResult.errors.push(`累计收益异常: ${totalReturn}% (存在 -436% 问题)`);
      }
    } else {
      console.log('[警告] 未获取到有效指标数据');
    }

    // ========================================
    // 步骤 8: 检查月度收益热力图
    // ========================================
    console.log('[步骤 8] 检查月度收益热力图...');
    
    const heatmapSelectors = [
      '[class*="heatmap"]',
      '[class*="Heatmap"]',
      '[class*="VerticalHeatmap"]',
      '[class*="calendar"]'
    ];
    
    for (const selector of heatmapSelectors) {
      const heatmap = page.locator(selector).first();
      if (await heatmap.isVisible().catch(() => false)) {
        testResult.hasMonthlyReturns = true;
        
        // 尝试获取月度收益数据
        const heatmapText = await heatmap.textContent().catch(() => '');
        const monthMatches = heatmapText?.match(/\d{4}-\d{2}/g) || [];
        testResult.monthlyReturnsCount = monthMatches.length;
        console.log(`[热力图] 发现 ${testResult.monthlyReturnsCount} 个月份的数据`);
        break;
      }
    }
    
    console.log(`[结果] 有月度收益数据: ${testResult.hasMonthlyReturns}`);

    // 截图：最终结果
    const screenshot3 = 'sandbox/reports/dashboard_03_final.png';
    await page.screenshot({ path: screenshot3, fullPage: true });
    testResult.screenshots.push(screenshot3);

    // ========================================
    // 步骤 9: 输出控制台日志摘要
    // ========================================
    console.log('\n[控制台日志摘要]');
    testResult.consoleLogs.slice(-20).forEach(log => {
      console.log(`  ${log}`);
    });

    // ========================================
    // 步骤 10: 输出错误
    // ========================================
    if (testResult.errors.length > 0) {
      console.log('\n[错误列表]');
      testResult.errors.forEach(err => {
        console.log(`  ${err}`);
      });
    }

    // 计算执行时间
    testResult.executionTime = Date.now() - startTime;

    // ========================================
    // 步骤 11: 输出最终报告
    // ========================================
    console.log('\n========================================');
    console.log('测试报告');
    console.log('========================================');
    console.log(`策略名称: ${testResult.strategyName}`);
    console.log(`执行时间: ${(testResult.executionTime / 1000).toFixed(1)}s`);
    console.log(`回测启动: ${testResult.backtestStarted ? '是' : '否'}`);
    console.log(`回测完成: ${testResult.backtestCompleted ? '是' : '否'}`);
    console.log(`流式传输工作: ${testResult.streamingWorked ? '是' : '否'}`);
    console.log(`权益更新次数: ${testResult.equityUpdateCount}`);
    console.log(`指标合理性: ${testResult.metricsReasonable ? '是' : '否'}`);
    if (testResult.finalMetrics) {
      console.log(`  - 累计收益: ${testResult.finalMetrics.totalReturn}%`);
      console.log(`  - 年化收益: ${testResult.finalMetrics.annualReturn}%`);
      console.log(`  - 最大回撤: ${testResult.finalMetrics.maxDrawdown}%`);
      console.log(`  - 夏普比率: ${testResult.finalMetrics.sharpeRatio}`);
      console.log(`  - 胜率: ${testResult.finalMetrics.winRate}%`);
      console.log(`  - 盈亏比: ${testResult.finalMetrics.profitFactor}`);
      console.log(`  - 总交易次数: ${testResult.finalMetrics.totalTrades}`);
      console.log(`  - 基准收益: ${testResult.finalMetrics.benchmarkReturn}%`);
    }
    console.log(`有月度收益数据: ${testResult.hasMonthlyReturns ? '是' : '否'}`);
    console.log(`月度收益数量: ${testResult.monthlyReturnsCount}`);
    console.log(`错误数量: ${testResult.errors.length}`);
    console.log('========================================\n');

    // ========================================
    // 验证断言
    // ========================================
    
    // 验证回测启动
    expect(testResult.backtestStarted).toBe(true);
    
    // 验证没有严重错误
    expect(testResult.errors.length).toBeLessThan(10);
    
    // 验证指标合理性（如果获取到了指标）
    if (testResult.finalMetrics) {
      // 累计收益不应该小于 -100%（即不应该出现 -436% 这种异常值）
      expect(testResult.finalMetrics.totalReturn).toBeGreaterThan(-100);
      expect(testResult.finalMetrics.totalReturn).toBeLessThan(500);
      
      // 最大回撤通常显示为负数（表示亏损），范围 -100% ~ 0%
      expect(testResult.finalMetrics.maxDrawdown).toBeGreaterThanOrEqual(-100);
      expect(testResult.finalMetrics.maxDrawdown).toBeLessThanOrEqual(0);
      
      // 夏普比率应该在合理范围内
      expect(testResult.finalMetrics.sharpeRatio).toBeGreaterThan(-5);
      expect(testResult.finalMetrics.sharpeRatio).toBeLessThan(10);
    }
  });

  test('验证页面元素完整性', async ({ page }) => {
    console.log('\n[测试] 验证页面元素完整性...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 检查关键元素
    const elements = {
      '策略选择器': 'combobox, select',
      '日期输入框': 'input[type="date"]',
      '回测按钮': 'button:has-text("回测")',
      '图表区域': 'canvas',
    };

    const results: Record<string, boolean> = {};
    
    for (const [name, selector] of Object.entries(elements)) {
      const isVisible = await page.locator(selector).first().isVisible().catch(() => false);
      results[name] = isVisible;
      console.log(`[元素检查] ${name}: ${isVisible ? 'OK' : 'MISSING'}`);
    }

    // 输出汇总
    console.log('\n[元素完整性汇总]');
    for (const [name, isVisible] of Object.entries(results)) {
      console.log(`  ${name}: ${isVisible ? 'OK' : 'MISSING'}`);
    }
    
    // 验证关键元素存在
    expect(results['策略选择器']).toBe(true);
    expect(results['回测按钮']).toBe(true);
  });
});
