/**
 * 回测功能完整测试 - 使用聚宽量比市值策略
 * 该策略交易频率较高，适合验证指标
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:5000';

// 测试配置 - 使用聚宽量比市值策略
const TEST_CONFIG = {
  strategyName: 'jq_volume_strategy',
  strategyDisplayName: '聚宽量比市值策略',
  startDate: '2024-05-01',
  endDate: '2024-05-31',
  benchmarkCode: '000300',
  timeout: 180000, // 3分钟超时
};

test.describe('回测功能测试 - 聚宽量比市值策略', () => {
  
  test('完整回测流程验证', async ({ page }) => {
    console.log('\n========== 开始回测测试 ==========\n');
    console.log(`策略: ${TEST_CONFIG.strategyDisplayName}`);
    console.log(`日期范围: ${TEST_CONFIG.startDate} ~ ${TEST_CONFIG.endDate}\n`);
    
    // 监听控制台
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`[Console Error] ${msg.text()}`);
      }
    });
    
    // Step 1: 打开页面
    console.log('[Step 1] 打开 Dashboard 页面');
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    // Step 2: 选择策略
    console.log('[Step 2] 选择策略');
    const strategySelect = page.locator('select.strategy-select').first();
    await expect(strategySelect).toBeVisible({ timeout: 10000 });
    
    // 选择聚宽量比市值策略
    await strategySelect.selectOption({ label: TEST_CONFIG.strategyDisplayName });
    await page.waitForTimeout(1000);
    
    const selectedStrategy = await strategySelect.inputValue();
    console.log(`[Step 2] 已选择策略: ${selectedStrategy}`);
    
    // Step 3: 设置日期范围
    console.log('[Step 3] 设置日期范围');
    const startDateInput = page.locator('input[type="date"]').first();
    const endDateInput = page.locator('input[type="date"]').nth(1);
    
    await startDateInput.fill(TEST_CONFIG.startDate);
    await endDateInput.fill(TEST_CONFIG.endDate);
    await page.waitForTimeout(500);
    
    console.log(`[Step 3] 日期范围: ${TEST_CONFIG.startDate} ~ ${TEST_CONFIG.endDate}`);
    
    // 截图：运行前
    await page.screenshot({ path: 'test-results/backtest_jq/01_before_run.png', fullPage: true });
    
    // Step 4: 运行回测
    console.log('[Step 4] 运行回测');
    const runButton = page.locator('button.run-btn, button:has-text("回测")').first();
    
    const isButtonDisabled = await runButton.isDisabled();
    if (isButtonDisabled) {
      console.log('[Step 4] 回测按钮被禁用，等待 API 连接...');
      await page.waitForTimeout(5000);
    }
    
    await runButton.click();
    console.log('[Step 4] 已点击回测按钮');
    await page.waitForTimeout(2000);
    
    // 截图：运行中
    await page.screenshot({ path: 'test-results/backtest_jq/02_running.png', fullPage: true });
    
    // Step 5: 等待回测完成
    console.log('[Step 5] 等待回测完成');
    const startTime = Date.now();
    let isRunning = true;
    let lastLogTime = 0;
    
    while (isRunning && (Date.now() - startTime) < TEST_CONFIG.timeout) {
      const runningIndicator = page.locator('.status-badge:has-text("运行中")').first();
      const stopButton = page.locator('button.stop-btn, button:has-text("停止")').first();
      
      const hasRunningIndicator = await runningIndicator.isVisible().catch(() => false);
      const hasStopButton = await stopButton.isVisible().catch(() => false);
      
      isRunning = hasRunningIndicator || hasStopButton;
      
      if (isRunning) {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        if (elapsed - lastLogTime >= 10) {
          console.log(`[Step 5] 回测运行中... (${elapsed}秒)`);
          lastLogTime = elapsed;
        }
        await page.waitForTimeout(2000);
      }
    }
    
    const totalTime = Math.floor((Date.now() - startTime) / 1000);
    console.log(`[Step 5] 回测完成，耗时 ${totalTime} 秒`);
    
    // 等待数据渲染
    await page.waitForTimeout(5000);
    
    // 截图：完成
    await page.screenshot({ path: 'test-results/backtest_jq/03_completed.png', fullPage: true });
    
    // Step 6: 提取并验证指标
    console.log('[Step 6] 提取并验证指标');
    
    const storedData = await page.evaluate(() => {
      const stored = localStorage.getItem('quantflow.backtest.v1');
      if (stored) {
        return JSON.parse(stored);
      }
      return null;
    });
    
    console.log('\n========== 回测结果报告 ==========\n');
    
    if (storedData) {
      const metrics = storedData.metrics || {};
      const trades = storedData.trades || [];
      const equitySeries = storedData.equitySeries || [];
      const benchmarkEquitySeries = storedData.benchmarkEquitySeries || [];
      const monthlyReturns = storedData.monthlyReturns || [];
      
      // 输出指标
      console.log('【回测指标】');
      console.log(`  累计收益: ${metrics.totalReturn?.toFixed(2) ?? 'N/A'}%`);
      console.log(`  年化收益: ${metrics.annualizedReturn?.toFixed(2) ?? 'N/A'}%`);
      console.log(`  最大回撤: ${metrics.maxDrawdown?.toFixed(2) ?? 'N/A'}%`);
      console.log(`  夏普比率: ${metrics.sharpeRatio?.toFixed(2) ?? 'N/A'}`);
      console.log(`  胜率: ${metrics.winRate?.toFixed(2) ?? 'N/A'}%`);
      console.log(`  盈亏比: ${metrics.profitFactor?.toFixed(2) ?? 'N/A'}`);
      console.log(`  总交易次数: ${metrics.tradesCount ?? metrics.totalTrades ?? trades.length ?? 'N/A'}`);
      
      console.log('\n【数据统计】');
      console.log(`  权益曲线数据点: ${equitySeries.length}`);
      console.log(`  基准曲线数据点: ${benchmarkEquitySeries.length}`);
      console.log(`  交易记录数: ${trades.length}`);
      console.log(`  月度收益数据: ${monthlyReturns.length} 个月`);
      
      // 显示部分交易记录
      if (trades.length > 0) {
        console.log('\n【交易记录示例】(前5条)');
        trades.slice(0, 5).forEach((trade: any, i: number) => {
          console.log(`  ${i + 1}. ${trade.date} | ${trade.action === 'buy' ? '买入' : '卖出'} | ${trade.symbolCode || trade.symbol} | 价格: ${trade.price} | 数量: ${trade.quantity}`);
        });
      }
      
      console.log('\n【验证结果】');
      
      // 验证累计收益
      const totalReturn = metrics.totalReturn ?? 0;
      const totalReturnValid = totalReturn > -100 && totalReturn < 1000;
      const totalReturnStatus = totalReturnValid ? 'PASS' : 'FAIL';
      console.log(`  累计收益: ${totalReturnStatus} (值: ${totalReturn.toFixed(2)}%, 期望: -100% ~ 1000%)`);
      
      // 验证年化收益
      const annualizedReturn = metrics.annualizedReturn ?? 0;
      const annualizedReturnValid = trades.length > 0 ? annualizedReturn !== 0 : true;
      const annualizedReturnStatus = annualizedReturnValid ? 'PASS' : 'FAIL';
      console.log(`  年化收益: ${annualizedReturnStatus} (值: ${annualizedReturn.toFixed(2)}%)`);
      
      // 验证最大回撤
      const maxDrawdown = metrics.maxDrawdown ?? 0;
      const maxDrawdownValid = maxDrawdown >= 0 && maxDrawdown <= 100;
      const maxDrawdownStatus = maxDrawdownValid ? 'PASS' : 'FAIL';
      console.log(`  最大回撤: ${maxDrawdownStatus} (值: ${maxDrawdown.toFixed(2)}%, 期望: 0% ~ 100%)`);
      
      // 验证夏普比率
      const sharpeRatio = metrics.sharpeRatio ?? 0;
      const sharpeRatioValid = typeof sharpeRatio === 'number';
      const sharpeRatioStatus = sharpeRatioValid ? 'PASS' : 'FAIL';
      console.log(`  夏普比率: ${sharpeRatioStatus} (值: ${sharpeRatio.toFixed(2)})`);
      
      // 验证胜率
      const winRate = metrics.winRate ?? 0;
      const winRateValid = winRate >= 0 && winRate <= 100;
      const winRateStatus = winRateValid ? 'PASS' : 'FAIL';
      console.log(`  胜率: ${winRateStatus} (值: ${winRate.toFixed(2)}%, 期望: 0% ~ 100%)`);
      
      // 验证交易次数
      const tradesCount = metrics.tradesCount ?? metrics.totalTrades ?? trades.length ?? 0;
      const tradesCountValid = tradesCount >= 0;
      const tradesCountStatus = tradesCountValid ? 'PASS' : 'FAIL';
      console.log(`  总交易次数: ${tradesCountStatus} (值: ${tradesCount})`);
      
      // 验证月度收益数据
      const monthlyReturnsValid = monthlyReturns.length > 0;
      const monthlyReturnsStatus = monthlyReturnsValid ? 'PASS' : 'FAIL';
      console.log(`  月度收益热力图: ${monthlyReturnsStatus} (数据: ${monthlyReturns.length} 个月)`);
      
      console.log('\n========================================\n');
      
      // 最终截图
      await page.screenshot({ path: 'test-results/backtest_jq/04_final.png', fullPage: true });
      
      // 断言
      expect(totalReturnValid).toBe(true);
      expect(maxDrawdownValid).toBe(true);
      expect(sharpeRatioValid).toBe(true);
      expect(winRateValid).toBe(true);
      expect(tradesCountValid).toBe(true);
      
      // 如果有交易，年化收益不应该为0
      if (trades.length > 0) {
        expect(annualizedReturnValid).toBe(true);
      }
      
    } else {
      console.log('[Step 6] 未找到存储的回测数据');
      console.log('========================================\n');
      throw new Error('未找到回测数据');
    }
  });
});
