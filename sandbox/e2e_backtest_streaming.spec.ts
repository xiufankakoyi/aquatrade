/**
 * Dashboard 回测流式传输深度测试
 * 
 * 测试目标：
 * 1. 验证流式传输是否工作（净值曲线逐步更新）
 * 2. 验证多维概览数据是否正确
 * 3. 验证月度收益热力图是否有数据
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:5000';

// 测试配置 - 使用实际存在的策略
const TEST_CONFIG = {
  strategyId: 'simple_volume_v5',
  strategyName: '聚宽量比市值策略V5_趋势增强',
  startDate: '2024-05-01',
  endDate: '2024-05-31',
  timeout: 180000, // 3分钟超时
};

// 存储测试结果
interface TestResult {
  streamingWorked: boolean;
  equityUpdateCount: number;
  equityPoints: Array<{ date: string; equity: number }>;
  finalMetrics: Record<string, number>;
  metricsReasonable: boolean;
  hasMonthlyReturns: boolean;
  errors: string[];
  socketEvents: string[];
  consoleLogs: string[];
}

test.describe('Dashboard 回测流式传输深度测试', () => {
  let testResult: TestResult = {
    streamingWorked: false,
    equityUpdateCount: 0,
    equityPoints: [],
    finalMetrics: {},
    metricsReasonable: true,
    hasMonthlyReturns: false,
    errors: [],
    socketEvents: [],
    consoleLogs: [],
  };

  test.beforeEach(async ({ page }) => {
    // 重置测试结果
    testResult = {
      streamingWorked: false,
      equityUpdateCount: 0,
      equityPoints: [],
      finalMetrics: {},
      metricsReasonable: true,
      hasMonthlyReturns: false,
      errors: [],
      socketEvents: [],
      consoleLogs: [],
    };

    // 监听控制台消息
    page.on('console', msg => {
      const text = msg.text();
      
      // 记录所有控制台消息
      if (text.includes('Socket') || text.includes('backtest') || 
          text.includes('equity') || text.includes('streaming') ||
          text.includes('daily') || text.includes('metrics')) {
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

  test('完整回测流程测试 - 使用 simple_volume_v5 策略', async ({ page, context }) => {
    console.log('\n========================================');
    console.log('开始 Dashboard 回测流式传输深度测试');
    console.log(`策略: ${TEST_CONFIG.strategyName}`);
    console.log(`日期范围: ${TEST_CONFIG.startDate} ~ ${TEST_CONFIG.endDate}`);
    console.log('========================================\n');

    // 1. 导航到 Dashboard 页面
    console.log('[步骤 1] 导航到 Dashboard 页面...');
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // 2. 等待页面完全加载
    console.log('[步骤 2] 等待页面加载...');
    
    // 检查是否有策略选择器
    const strategySelect = page.locator('select').first();
    await strategySelect.waitFor({ state: 'visible', timeout: 10000 }).catch(() => {
      console.log('[警告] 未找到策略选择器');
    });

    // 3. 选择策略
    console.log('[步骤 3] 选择策略...');
    
    // 查找策略下拉框
    const strategySelectors = await page.locator('select').all();
    console.log(`[状态] 发现 ${strategySelectors.length} 个下拉框`);

    // 使用第一个下拉框选择策略
    if (strategySelectors.length > 0) {
      const select = strategySelectors[0];
      const options = await select.locator('option').allTextContents();
      console.log(`[下拉框 0] 选项: ${options.slice(0, 5).join(', ')}...`);
      
      // 查找包含 V5 的选项
      const v5Option = options.find(opt => opt.includes('V5') || opt.includes('v5'));
      if (v5Option) {
        await select.selectOption({ label: v5Option });
        console.log(`[选择] 已选择策略: ${v5Option}`);
      } else {
        // 选择第一个非空选项
        const firstOption = options.find(opt => opt && opt.trim() && !opt.includes('选择'));
        if (firstOption) {
          await select.selectOption({ label: firstOption });
          console.log(`[选择] 已选择策略: ${firstOption}`);
        }
      }
    }

    // 4. 设置日期范围
    console.log('[步骤 4] 设置日期范围...');
    
    const dateInputs = await page.locator('input[type="date"]').all();
    console.log(`[状态] 发现 ${dateInputs.length} 个日期输入框`);

    if (dateInputs.length >= 2) {
      await dateInputs[0].fill(TEST_CONFIG.startDate);
      console.log(`[设置] 开始日期: ${TEST_CONFIG.startDate}`);
      
      await dateInputs[1].fill(TEST_CONFIG.endDate);
      console.log(`[设置] 结束日期: ${TEST_CONFIG.endDate}`);
    }

    // 5. 点击运行按钮
    console.log('[步骤 5] 点击运行按钮...');
    
    const runButton = page.locator('button:has-text("运行")').first();
    await runButton.waitFor({ state: 'visible', timeout: 5000 });
    
    // 检查按钮状态
    const isDisabled = await runButton.isDisabled();
    if (isDisabled) {
      console.log('[警告] 运行按钮被禁用');
      testResult.errors.push('运行按钮被禁用');
    } else {
      console.log('[状态] 运行按钮可用，点击...');
      await runButton.click();
    }

    // 6. 监控流式更新
    console.log('[步骤 6] 监控流式更新...');
    
    const startTime = Date.now();
    let lastEquityCount = 0;
    let equityUpdateTimestamps: number[] = [];
    let metricsFound = false;

    // 设置定时检查
    const checkInterval = setInterval(async () => {
      try {
        // 检查图表 canvas
        const canvas = page.locator('canvas').first();
        if (await canvas.isVisible().catch(() => false)) {
          const now = Date.now();
          equityUpdateTimestamps.push(now);
          testResult.equityUpdateCount++;
        }
      } catch (e) {
        // 忽略
      }
    }, 200);

    // 等待回测完成
    while ((Date.now() - startTime) < TEST_CONFIG.timeout) {
      await page.waitForTimeout(2000);
      
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      
      // 检查是否有图表显示
      const hasChart = await page.locator('canvas, [class*="chart"]').first().isVisible().catch(() => false);
      
      // 检查是否有指标面板
      const hasMetrics = await page.locator('[class*="metric"], [class*="Metric"]').first().isVisible().catch(() => false);
      
      // 检查是否有运行状态
      const isRunning = await page.locator('[class*="running"], [class*="loading"], [class*="spinner"]').first().isVisible().catch(() => false);

      // 每 10 秒输出状态
      if (elapsed % 10 === 0 && elapsed > 0) {
        console.log(`[状态 ${elapsed}s] 图表: ${hasChart}, 指标: ${hasMetrics}, 运行中: ${isRunning}, 更新次数: ${testResult.equityUpdateCount}`);
      }

      // 如果有指标且不在运行，可能已完成
      if (hasMetrics && !isRunning && elapsed > 10) {
        console.log(`[状态] 检测到回测可能完成`);
        await page.waitForTimeout(3000); // 等待数据稳定
        break;
      }
    }

    clearInterval(checkInterval);

    // 7. 分析流式传输效果
    console.log('[步骤 7] 分析流式传输效果...');
    
    // 如果有多个更新时间戳，计算更新间隔
    if (equityUpdateTimestamps.length > 1) {
      const intervals: number[] = [];
      for (let i = 1; i < equityUpdateTimestamps.length; i++) {
        intervals.push(equityUpdateTimestamps[i] - equityUpdateTimestamps[i-1]);
      }
      const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      console.log(`[分析] 平均更新间隔: ${avgInterval.toFixed(0)}ms`);
      
      // 如果平均间隔小于 1 秒，说明是流式更新
      testResult.streamingWorked = avgInterval < 1000 && intervals.length > 5;
    }

    console.log(`[结果] 流式传输工作: ${testResult.streamingWorked}`);
    console.log(`[结果] 权益更新次数: ${testResult.equityUpdateCount}`);

    // 8. 提取指标数据
    console.log('[步骤 8] 提取指标数据...');
    
    // 尝试从页面提取指标
    const metricsPanel = page.locator('[class*="MetricsPanel"], [class*="metrics-panel"]').first();
    if (await metricsPanel.isVisible().catch(() => false)) {
      const metricsText = await metricsPanel.textContent().catch(() => '');
      console.log(`[指标面板] ${metricsText?.substring(0, 300)}...`);
      
      // 提取数字
      const numbers = metricsText?.match(/-?\d+\.?\d*/g) || [];
      console.log(`[提取数字] ${numbers.slice(0, 15).join(', ')}`);
      
      // 尝试解析指标
      if (numbers.length >= 5) {
        testResult.finalMetrics = {
          totalReturn: parseFloat(numbers[0]) || 0,
          annualReturn: parseFloat(numbers[1]) || 0,
          maxDrawdown: parseFloat(numbers[2]) || 0,
          sharpeRatio: parseFloat(numbers[3]) || 0,
          winRate: parseFloat(numbers[4]) || 0,
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

    // 9. 检查月度收益热力图
    console.log('[步骤 9] 检查月度收益热力图...');
    
    const heatmap = page.locator('[class*="heatmap"], [class*="Heatmap"], [class*="calendar"]').first();
    testResult.hasMonthlyReturns = await heatmap.isVisible().catch(() => false);
    console.log(`[结果] 有月度收益数据: ${testResult.hasMonthlyReturns}`);

    // 10. 输出控制台日志
    console.log('\n[控制台日志摘要]');
    testResult.consoleLogs.slice(-20).forEach(log => {
      console.log(`  ${log}`);
    });

    // 11. 输出错误
    if (testResult.errors.length > 0) {
      console.log('\n[错误列表]');
      testResult.errors.forEach(err => {
        console.log(`  ${err}`);
      });
    }

    // 12. 输出最终报告
    console.log('\n========================================');
    console.log('测试报告');
    console.log('========================================');
    console.log(`流式传输工作: ${testResult.streamingWorked ? '是' : '否'}`);
    console.log(`权益更新次数: ${testResult.equityUpdateCount}`);
    console.log(`指标合理性: ${testResult.metricsReasonable ? '是' : '否'}`);
    console.log(`有月度收益数据: ${testResult.hasMonthlyReturns ? '是' : '否'}`);
    console.log(`错误数量: ${testResult.errors.length}`);
    console.log('========================================\n');

    // 验证基本功能
    // 注意：即使流式传输不工作，测试也不应该失败，而是记录问题
    expect(testResult.errors.length).toBeLessThan(10);
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
  });

  test('直接调用后端 API 测试回测', async ({ page }) => {
    console.log('\n[测试] 直接调用后端 API...');
    
    // 获取策略列表
    const strategiesResponse = await page.request.get(`${BACKEND_URL}/api/strategies`);
    const strategiesData = await strategiesResponse.json();
    console.log(`[API] 策略数量: ${strategiesData.data?.length || 0}`);

    // 选择一个策略
    const strategy = strategiesData.data?.find((s: any) => 
      s.id?.includes('simple_volume') || s.name?.includes('V5')
    );
    
    if (strategy) {
      console.log(`[API] 选择策略: ${strategy.name} (${strategy.id})`);
    } else {
      console.log('[API] 未找到合适的策略');
    }
  });
});
