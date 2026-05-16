/**
 * Grid Search 参数优化页面 - E2E 测试
 * 测试范围：参数选择、算法配置、优化执行、结果展示
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';

test.describe('Grid Search 参数优化页面测试', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/grid-search`);
    await page.waitForLoadState('networkidle');
  });

  test('页面基础结构检查', async ({ page }) => {
    await page.screenshot({ path: 'test-results/grid-search-initial.png', fullPage: true });
    
    // 检查页面标题
    const title = page.locator('h1:has-text("参数智能优化"), h1:has-text("Grid Search")').first();
    await expect(title).toBeVisible();
    
    // 检查基础设置区域
    const basicSettings = page.locator('h2:has-text("基础设置")').first();
    await expect(basicSettings).toBeVisible();
    
    // 检查策略选择下拉框
    const strategySelect = page.locator('select').first();
    await expect(strategySelect).toBeVisible();
  });

  test('策略选择功能', async ({ page }) => {
    const strategySelect = page.locator('select').first();
    
    // 获取可用选项
    const options = await strategySelect.locator('option').allTextContents();
    console.log(`可用策略数量: ${options.length}`);
    
    if (options.length > 1) {
      // 选择第一个非空选项
      await strategySelect.selectOption({ index: 1 });
      await page.waitForTimeout(1000);
      
      await page.screenshot({ path: 'test-results/grid-search-strategy-selected.png' });
    }
  });

  test('算法选择功能', async ({ page }) => {
    // 查找算法选择下拉框
    const algoSelect = page.locator('select:has-option("遗传算法"), select:has-option("GA")').first();
    
    if (await algoSelect.isVisible().catch(() => false)) {
      const algorithms = ['遗传算法', '粒子群优化', 'CMA-ES', '模拟退火', '网格搜索', '贝叶斯优化'];
      
      for (const algo of algorithms) {
        const option = algoSelect.locator(`option:has-text("${algo}")`);
        const exists = await option.count() > 0;
        console.log(`算法 "${algo}" 可用: ${exists}`);
      }
      
      // 选择不同算法
      await algoSelect.selectOption({ label: '粒子群优化' });
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/grid-search-algo-changed.png' });
    }
  });

  test('日期范围设置', async ({ page }) => {
    // 查找日期输入框
    const dateInputs = page.locator('input[type="date"]');
    const dateCount = await dateInputs.count();
    
    console.log(`日期输入框数量: ${dateCount}`);
    
    if (dateCount >= 2) {
      const startDate = dateInputs.nth(0);
      const endDate = dateInputs.nth(1);
      
      // 设置日期范围
      await startDate.fill('2024-01-01');
      await endDate.fill('2024-06-30');
      
      await page.screenshot({ path: 'test-results/grid-search-dates-set.png' });
    }
  });

  test('参数选择功能', async ({ page }) => {
    // 等待参数列表加载
    await page.waitForTimeout(2000);
    
    // 查找参数复选框
    const paramCheckboxes = page.locator('input[type="checkbox"]').filter({ has: page.locator('..') });
    const checkboxCount = await paramCheckboxes.count();
    
    console.log(`参数复选框数量: ${checkboxCount}`);
    
    if (checkboxCount > 0) {
      // 选择第一个参数
      await paramCheckboxes.first().check();
      await page.waitForTimeout(500);
      
      await page.screenshot({ path: 'test-results/grid-search-param-selected.png' });
    }
  });

  test('优化模式选择', async ({ page }) => {
    const modeSelect = page.locator('select:has-option("稳健优化模式"), select:has-option("robust")').first();
    
    if (await modeSelect.isVisible().catch(() => false)) {
      await modeSelect.selectOption({ label: '稳健优化模式（训练+验证）【推荐】' });
      await page.waitForTimeout(500);
      
      await page.screenshot({ path: 'test-results/grid-search-mode-selected.png' });
    }
  });

  test('开始优化按钮状态检查', async ({ page }) => {
    const startBtn = page.locator('button:has-text("开始优化"), button:has-text("Start")').first();
    
    await expect(startBtn).toBeVisible();
    
    // 检查按钮初始状态（应该禁用，因为没有选择参数）
    const isDisabled = await startBtn.isDisabled().catch(() => false);
    console.log(`开始优化按钮初始状态: ${isDisabled ? '禁用' : '可用'}`);
    
    // 截图记录按钮状态
    await page.screenshot({ path: 'test-results/grid-search-start-btn.png' });
  });

  test('高级设置展开/折叠', async ({ page }) => {
    // 查找高级设置区域
    const advancedSection = page.locator('details, [class*="advanced"]').first();
    
    if (await advancedSection.isVisible().catch(() => false)) {
      // 点击展开
      await advancedSection.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/grid-search-advanced-expanded.png' });
      
      // 再次点击折叠
      await advancedSection.click();
      await page.waitForTimeout(500);
    }
  });

  test('响应式适配 - 移动端', async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 932 });
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ path: 'test-results/grid-search-mobile.png', fullPage: true });
    
    // 检查布局是否正常
    const title = page.locator('h1').first();
    await expect(title).toBeVisible();
  });

  test('性能 - 大量参数渲染', async ({ page }) => {
    // 先选择策略以加载参数
    const strategySelect = page.locator('select').first();
    const options = await strategySelect.locator('option').count();
    
    if (options > 1) {
      await strategySelect.selectOption({ index: 1 });
      await page.waitForTimeout(3000);
      
      // 记录参数加载时间
      const startTime = Date.now();
      
      // 查找所有参数项
      const paramItems = page.locator('[class*="param"]').filter({ has: page.locator('input[type="checkbox"]') });
      const paramCount = await paramItems.count();
      
      const loadTime = Date.now() - startTime;
      console.log(`参数数量: ${paramCount}, 加载时间: ${loadTime}ms`);
      
      // 参数加载应该小于 3 秒
      expect(loadTime).toBeLessThan(3000);
    }
  });
});
