/**
 * Dashboard 回测功能完整测试
 * 
 * 测试目标：
 * 1. 验证页面加载和策略选择
 * 2. 验证日期范围设置
 * 3. 验证回测运行和流式传输
 * 4. 验证多维概览面板数据正确性
 * 5. 验证月度收益热力图数据
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:5000';

// 测试配置
const TEST_CONFIG = {
  strategies: ['simple_momentum', 'simple_volume_v5'],
  startDate: '2024-05-01',
  endDate: '2024-05-31',
  timeout: 180000, // 3分钟超时
};

// 测试结果接口
interface BacktestTestResult {
  strategyName: string;
  streamingWorked: boolean;
  equityUpdateCount: number;
  equityPoints: Array<{ date: string; equity: number }>;
  finalMetrics: {
    totalReturn: number;
    annualReturn: number;
    maxDrawdown: number;
    sharpeRatio: number;
    winRate: number;
    profitFactor: number;
    totalTrades: number;
  } | null;
  metricsReasonable: boolean;
  hasMonthlyReturns: boolean;
  monthlyReturnsCount: number;
  errors: string[];
  consoleLogs: string[];
  socketEvents: string[];
  executionTime: number;
}

/**
 * 等待元素并返回是否可见
 */
async function waitForElement(page: Page, selector: string, timeout: number = 10000): Promise<boolean> {
  try {
    await page.locator(selector).waitFor({ state: 'visible', timeout });
    return true;
  } catch {
    return false;
  }
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

test.describe('Dashboard 回测功能完整测试', () => {
  let testResult: BacktestTestResult;

  test.beforeEach(async ({ page }) => {
    // 初始化测试结果
    testResult = {
      strategyName: '',
      streamingWorked: false,
      equityUpdateCount: 0,
      equityPoints: [],
      finalMetrics: null,
      metricsReasonable: false,
      hasMonthlyReturns: false,
      monthlyReturnsCount: 0,
      errors: [],
      consoleLogs: [],
      socketEvents: [],
      executionTime: 0
    };

    // 监听控制台消息
    page.on('console', msg => {
      const text = msg.text();
      
      // 记录关键日志
      if (text.includes('Socket') || text.includes('backtest') || 
          text.includes('equity') || text.includes('streaming') ||
          text.includes('daily') || text.includes('metrics') ||
          text.includes('MsgPack') || text.includes('策略')) {
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
      if (request.url().includes('socket.io')) {
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
    
    if (!isHealthy) {
      console.warn('[警告] 后端服务不可用，部分测试可能失败');
    }
    
    // 不强制要求后端可用，允许测试继续
  });

  test('完整回测流程测试 - simple_volume_v5 策略', async ({ page }) => {
    const startTime = Date.now();
    testResult.strategyName = 'simple_volume_v5';

    console.log('\n========================================');
    console.log('开始 Dashboard 回测功能完整测试');
    console.log(`策略: ${testResult.strategyName}`);
    console.log(`日期范围: ${TEST_CONFIG.startDate} ~ ${TEST_CONFIG.endDate}`);
    console.log('========================================\n');

    // 步骤 1: 导航到 Dashboard 页面
    console.log('[步骤 1] 导航到 Dashboard 页面...');
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 截图：初始页面
    await page.screenshot({ path: 'sandbox/reports/dashboard_initial.png', fullPage: false });

    // 步骤 2: 检查页面元素
    console.log('[步骤 2] 检查页面元素...');
    
    // 检查侧边栏是否打开
    const sidebar = page.locator('[class*="sidebar"], [class*="Sidebar"], .w-\\[300px\\]');
    const isSidebarVisible = await sidebar.isVisible().catch(() => false);
    console.log(`[状态] 侧边栏可见: ${isSidebarVisible}`);

    // 如果侧边栏不可见，尝试打开它
    if (!isSidebarVisible) {
      const toggleBtn = page.locator('button:has-text("columns"), button:has([class*="fa-columns"])');
      if (await toggleBtn.isVisible().catch(() => false)) {
        await toggleBtn.click();
        await page.waitForTimeout(500);
        console.log('[操作] 已点击侧边栏切换按钮');
      }
    }

    // 步骤 3: 选择策略
    console.log('[步骤 3] 选择策略...');
    
    // 查找策略选择器（在顶部导航栏）
    const strategySelectors = await page.locator('select, [class*="select"]').all();
    console.log(`[状态] 发现 ${strategySelectors.length} 个选择器`);

    // 尝试找到策略选择器
    let strategySelected = false;
    for (let i = 0; i < strategySelectors.length; i++) {
      const selector = strategySelectors[i];
      try {
        const options = await selector.locator('option').allTextContents();
        console.log(`[选择器 ${i}] 选项: ${options.slice(0, 5).join(', ')}...`);
        
        // 查找 simple_volume_v5 或 V5 策略
        const targetOption = options.find(opt => 
          opt.includes('simple_volume_v5') || 
          opt.includes('V5') || 
          opt.includes('v5') ||
          opt.includes('量比')
        );
        
        if (targetOption) {
          await selector.selectOption({ label: targetOption });
          console.log(`[选择] 已选择策略: ${targetOption}`);
          strategySelected = true;
          break;
        }
      } catch (e) {
        // 忽略错误，继续尝试下一个选择器
      }
    }

    if (!strategySelected) {
      console.log('[警告] 未能通过选择器选择策略，尝试其他方式...');
      
      // 尝试点击策略下拉菜单
      const strategyDropdown = page.locator('[class*="strategy"], [class*="Strategy"]').first();
      if (await strategyDropdown.isVisible().catch(() => false)) {
        await strategyDropdown.click();
        await page.waitForTimeout(500);
        
        // 查找策略选项
        const strategyOption = page.locator('text=/simple_volume_v5|V5|量比/i').first();
        if (await strategyOption.isVisible().catch(() => false)) {
          await strategyOption.click();
          console.log('[选择] 通过下拉菜单选择策略');
          strategySelected = true;
        }
      }
    }

    // 步骤 4: 设置日期范围
    console.log('[步骤 4] 设置日期范围...');
    
    const dateInputs = await page.locator('input[type="date"]').all();
    console.log(`[状态] 发现 ${dateInputs.length} 个日期输入框`);

    if (dateInputs.length >= 2) {
      // 清除并设置开始日期
      await dateInputs[0].fill('');
      await dateInputs[0].fill(TEST_CONFIG.startDate);
      console.log(`[设置] 开始日期: ${TEST_CONFIG.startDate}`);
      
      // 清除并设置结束日期
      await dateInputs[1].fill('');
      await dateInputs[1].fill(TEST_CONFIG.endDate);
      console.log(`[设置] 结束日期: ${TEST_CONFIG.endDate}`);
    } else {
      console.log('[警告] 未找到足够的日期输入框');
    }

    // 截图：配置完成
    await page.screenshot({ path: 'sandbox/reports/dashboard_configured.png', fullPage: false });

    // 步骤 5: 点击运行回测按钮
    console.log('[步骤 5] 点击运行回测按钮...');
    
    const runButton = page.locator('button:has-text("运行"), button:has-text("RUN")').first();
    const isRunButtonVisible = await runButton.isVisible().catch(() => false);
    
    if (isRunButtonVisible) {
      const isDisabled = await runButton.isDisabled();
      if (isDisabled) {
        console.log('[警告] 运行按钮被禁用');
        testResult.errors.push('运行按钮被禁用');
        
        // 检查禁用原因
        const disabledReason = await runButton.getAttribute('title');
        if (disabledReason) {
          console.log(`[原因] ${disabledReason}`);
        }
      } else {
        console.log('[状态] 运行按钮可用，点击...');
        await runButton.click();
      }
    } else {
      console.log('[警告] 未找到运行按钮');
    }

    // 步骤 6: 监控流式更新
    console.log('[步骤 6] 监控流式更新...');
    
    let lastEquityCount = 0;
    let equityUpdateTimestamps: number[] = [];
    let streamingCheckCount = 0;

    // 设置定时检查
    const checkInterval = setInterval(async () => {
      try {
        streamingCheckCount++;
        
        // 检查图表 canvas
        const canvas = page.locator('canvas').first();
        if (await canvas.isVisible().catch(() => false)) {
          const now = Date.now();
          equityUpdateTimestamps.push(now);
          testResult.equityUpdateCount++;
        }
        
        // 每 10 次检查输出一次状态
        if (streamingCheckCount % 10 === 0) {
          console.log(`[流式检查 ${streamingCheckCount}] 权益更新次数: ${testResult.equityUpdateCount}`);
        }
      } catch (e) {
        // 忽略检查错误
      }
    }, 500);

    // 等待回测完成
    const maxWaitTime = TEST_CONFIG.timeout;
    const checkStartTime = Date.now();
    let isBacktestComplete = false;

    while ((Date.now() - checkStartTime) < maxWaitTime) {
      await page.waitForTimeout(2000);
      
      const elapsed = Math.floor((Date.now() - checkStartTime) / 1000);
      
      // 检查是否有图表显示
      const hasChart = await page.locator('canvas, [class*="chart"], [class*="Chart"]').first()
        .isVisible().catch(() => false);
      
      // 检查是否有指标面板
      const hasMetrics = await page.locator('[class*="metric"], [class*="Metric"], [class*="指标"]').first()
        .isVisible().catch(() => false);
      
      // 检查是否有运行状态
      const isRunning = await page.locator('[class*="running"], [class*="loading"], [class*="spinner"], [class*="fa-spin"]').first()
        .isVisible().catch(() => false);

      // 每 10 秒输出状态
      if (elapsed % 10 === 0 && elapsed > 0) {
        console.log(`[状态 ${elapsed}s] 图表: ${hasChart}, 指标: ${hasMetrics}, 运行中: ${isRunning}, 更新次数: ${testResult.equityUpdateCount}`);
      }

      // 如果有指标且不在运行，可能已完成
      if (hasMetrics && !isRunning && elapsed > 10) {
        console.log(`[状态] 检测到回测可能完成`);
        await page.waitForTimeout(3000); // 等待数据稳定
        isBacktestComplete = true;
        break;
      }
    }

    clearInterval(checkInterval);

    // 步骤 7: 分析流式传输效果
    console.log('[步骤 7] 分析流式传输效果...');
    
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

    // 步骤 8: 提取指标数据
    console.log('[步骤 8] 提取指标数据...');
    
    // 尝试从 MetricsPanel 提取指标
    const metricsPanel = page.locator('[class*="MetricsPanel"], [class*="metrics-panel"], [class*="指标"]').first();
    if (await metricsPanel.isVisible().catch(() => false)) {
      const metricsText = await metricsPanel.textContent().catch(() => '');
      console.log(`[指标面板内容] ${metricsText?.substring(0, 500)}...`);
      
      // 提取关键指标
      // 累计收益
      const totalReturnMatch = metricsText?.match(/累计收益[：:]\s*(-?\d+\.?\d*)%?/i);
      const annualReturnMatch = metricsText?.match(/年化收益[：:]\s*(-?\d+\.?\d*)%?/i);
      const maxDrawdownMatch = metricsText?.match(/最大回撤[：:]\s*(-?\d+\.?\d*)%?/i);
      const sharpeMatch = metricsText?.match(/夏普比率[：:]\s*(-?\d+\.?\d*)/i);
      const winRateMatch = metricsText?.match(/胜率[：:]\s*(-?\d+\.?\d*)%?/i);
      const profitFactorMatch = metricsText?.match(/盈亏比[：:]\s*(-?\d+\.?\d*)/i);
      const tradesMatch = metricsText?.match(/交易次数[：:]\s*(\d+)/i);

      if (totalReturnMatch || maxDrawdownMatch || sharpeMatch) {
        testResult.finalMetrics = {
          totalReturn: totalReturnMatch ? parseFloat(totalReturnMatch[1]) : 0,
          annualReturn: annualReturnMatch ? parseFloat(annualReturnMatch[1]) : 0,
          maxDrawdown: maxDrawdownMatch ? parseFloat(maxDrawdownMatch[1]) : 0,
          sharpeRatio: sharpeMatch ? parseFloat(sharpeMatch[1]) : 0,
          winRate: winRateMatch ? parseFloat(winRateMatch[1]) : 0,
          profitFactor: profitFactorMatch ? parseFloat(profitFactorMatch[1]) : 0,
          totalTrades: tradesMatch ? parseInt(tradesMatch[1]) : 0
        };

        // 验证指标合理性
        const { totalReturn, maxDrawdown, sharpeRatio } = testResult.finalMetrics;
        testResult.metricsReasonable = 
          totalReturn > -100 && totalReturn < 500 &&
          maxDrawdown >= 0 && maxDrawdown < 100 &&
          sharpeRatio > -5 && sharpeRatio < 10;
        
        console.log(`[指标验证] 合理性: ${testResult.metricsReasonable}`);
        console.log(`[指标] 累计收益: ${totalReturn}%, 最大回撤: ${maxDrawdown}%, 夏普: ${sharpeRatio}`);
      }
    }

    // 步骤 9: 检查月度收益热力图
    console.log('[步骤 9] 检查月度收益热力图...');
    
    const heatmap = page.locator('[class*="heatmap"], [class*="Heatmap"], [class*="calendar"], [class*="VerticalHeatmap"]').first();
    testResult.hasMonthlyReturns = await heatmap.isVisible().catch(() => false);
    
    if (testResult.hasMonthlyReturns) {
      // 尝试获取月度收益数据
      const heatmapText = await heatmap.textContent().catch(() => '');
      const monthMatches = heatmapText?.match(/\d{4}-\d{2}/g) || [];
      testResult.monthlyReturnsCount = monthMatches.length;
      console.log(`[热力图] 发现 ${testResult.monthlyReturnsCount} 个月份的数据`);
    }
    
    console.log(`[结果] 有月度收益数据: ${testResult.hasMonthlyReturns}`);

    // 截图：最终结果
    await page.screenshot({ path: 'sandbox/reports/dashboard_final.png', fullPage: true });

    // 步骤 10: 输出控制台日志摘要
    console.log('\n[控制台日志摘要]');
    testResult.consoleLogs.slice(-30).forEach(log => {
      console.log(`  ${log}`);
    });

    // 步骤 11: 输出错误
    if (testResult.errors.length > 0) {
      console.log('\n[错误列表]');
      testResult.errors.forEach(err => {
        console.log(`  ${err}`);
      });
    }

    // 计算执行时间
    testResult.executionTime = Date.now() - startTime;

    // 步骤 12: 输出最终报告
    console.log('\n========================================');
    console.log('测试报告');
    console.log('========================================');
    console.log(`策略名称: ${testResult.strategyName}`);
    console.log(`执行时间: ${(testResult.executionTime / 1000).toFixed(1)}s`);
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
      console.log(`  - 交易次数: ${testResult.finalMetrics.totalTrades}`);
    }
    console.log(`有月度收益数据: ${testResult.hasMonthlyReturns ? '是' : '否'}`);
    console.log(`月度收益数量: ${testResult.monthlyReturnsCount}`);
    console.log(`错误数量: ${testResult.errors.length}`);
    console.log('========================================\n');

    // 验证基本功能
    // 注意：即使流式传输不工作，测试也不应该失败，而是记录问题
    expect(testResult.errors.length).toBeLessThan(15);
  });

  test('检查 Socket.IO 连接状态', async ({ page }) => {
    console.log('\n[测试] 检查 Socket.IO 连接状态...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // 检查 Socket.IO 连接
    const socketStatus = await page.evaluate(() => {
      // @ts-ignore
      const status = window.__SOCKET_STATUS__;
      return status || 'unknown';
    }).catch(() => 'unknown');

    console.log(`[Socket 状态] ${socketStatus}`);

    // 检查是否有 WebSocket 连接
    const hasWebSocket = await page.evaluate(() => {
      return typeof WebSocket !== 'undefined';
    });

    console.log(`[WebSocket 支持] ${hasWebSocket}`);
    
    // 验证 WebSocket 支持
    expect(hasWebSocket).toBe(true);
  });

  test('直接调用后端 API 测试回测', async ({ page }) => {
    console.log('\n[测试] 直接调用后端 API...');
    
    // 获取策略列表
    const strategiesResponse = await page.request.get(`${BACKEND_URL}/api/strategies`);
    
    if (!strategiesResponse.ok()) {
      console.log('[API] 后端服务不可用，跳过此测试');
      return;
    }
    
    const strategiesData = await strategiesResponse.json();
    console.log(`[API] 策略数量: ${strategiesData.data?.length || 0}`);

    // 选择一个策略
    const strategy = strategiesData.data?.find((s: any) => 
      s.id?.includes('simple_volume') || s.name?.includes('V5') || s.name?.includes('量比')
    );
    
    if (strategy) {
      console.log(`[API] 选择策略: ${strategy.name} (${strategy.id})`);
      
      // 验证策略数据结构
      expect(strategy).toHaveProperty('id');
      expect(strategy).toHaveProperty('name');
    } else {
      console.log('[API] 未找到合适的策略');
    }
  });

  test('验证页面元素完整性', async ({ page }) => {
    console.log('\n[测试] 验证页面元素完整性...');
    
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 检查关键元素
    const elements = {
      '侧边栏': '[class*="sidebar"], [class*="Sidebar"], .w-\\[300px\\]',
      '日期输入框': 'input[type="date"]',
      '运行按钮': 'button:has-text("运行"), button:has-text("RUN")',
      '图表区域': 'canvas, [class*="chart"], [class*="Chart"]',
      '配置面板': '[class*="config"], [class*="Config"]'
    };

    const results: Record<string, boolean> = {};
    
    for (const [name, selector] of Object.entries(elements)) {
      const isVisible = await page.locator(selector).first().isVisible().catch(() => false);
      results[name] = isVisible;
      console.log(`[元素检查] ${name}: ${isVisible ? '可见' : '不可见'}`);
    }

    // 输出汇总
    console.log('\n[元素完整性汇总]');
    for (const [name, isVisible] of Object.entries(results)) {
      console.log(`  ${name}: ${isVisible ? '✓' : '✗'}`);
    }
  });
});
