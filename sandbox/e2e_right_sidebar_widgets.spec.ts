/**
 * 右边栏小组件功能测试
 * 测试 ChartToolbar 组件的所有功能是否正常工作
 */
import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';

test.describe('右边栏小组件功能测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/strategy/jq_volume_v1pro`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
  });

  test('1. 验证右边栏工具栏存在', async ({ page }) => {
    console.log('[测试] 验证右边栏工具栏存在...');
    
    const chartToolbar = page.locator('.chart-toolbar, .toolbar-panel').first();
    await expect(chartToolbar).toBeVisible({ timeout: 10000 });
    
    console.log('[验证] 右边栏工具栏可见');
  });

  test('2. 测试基础绘图工具', async ({ page }) => {
    console.log('[测试] 测试基础绘图工具...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const crosshairBtn = toolbarPanel.locator('.toolbar-item:has(.fa-crosshairs)').first();
    await expect(crosshairBtn).toBeVisible();
    console.log('[验证] 十字准星按钮可见');
    
    await crosshairBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 十字准星工具可点击');
    
    const trendLineBtn = toolbarPanel.locator('.toolbar-item:has(.fa-chart-line)').first();
    await expect(trendLineBtn).toBeVisible();
    console.log('[验证] 趋势线按钮可见');
    
    await trendLineBtn.click();
    await page.waitForTimeout(300);
    
    const submenu = toolbarPanel.locator('.submenu').first();
    const isSubmenuVisible = await submenu.isVisible().catch(() => false);
    console.log(`[验证] 趋势线子菜单: ${isSubmenuVisible ? '可见' : '不可见'}`);
  });

  test('3. 测试斐波那契工具', async ({ page }) => {
    console.log('[测试] 测试斐波那契工具...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const fibBtn = toolbarPanel.locator('.toolbar-item:has(.fa-grip-lines)').first();
    await expect(fibBtn).toBeVisible();
    console.log('[验证] 斐波那契按钮可见');
    
    await fibBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 斐波那契工具可点击');
  });

  test('4. 测试几何图形工具', async ({ page }) => {
    console.log('[测试] 测试几何图形工具...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const shapesBtn = toolbarPanel.locator('.toolbar-item:has(.fa-shapes)').first();
    await expect(shapesBtn).toBeVisible();
    console.log('[验证] 几何图形按钮可见');
    
    await shapesBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 几何图形工具可点击');
  });

  test('5. 测试文字注释工具', async ({ page }) => {
    console.log('[测试] 测试文字注释工具...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const textBtn = toolbarPanel.locator('.toolbar-item:has(.fa-font)').first();
    await expect(textBtn).toBeVisible();
    console.log('[验证] 文字注释按钮可见');
    
    await textBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 文字注释工具可点击');
  });

  test('6. 测试技术形态工具', async ({ page }) => {
    console.log('[测试] 测试技术形态工具...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const patternBtn = toolbarPanel.locator('.toolbar-item:has(.fa-wave-square)').first();
    await expect(patternBtn).toBeVisible();
    console.log('[验证] 技术形态按钮可见');
    
    await patternBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 技术形态工具可点击');
  });

  test('7. 测试仓位工具', async ({ page }) => {
    console.log('[测试] 测试仓位工具...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const positionBtn = toolbarPanel.locator('.toolbar-item:has(.fa-balance-scale)').first();
    await expect(positionBtn).toBeVisible();
    console.log('[验证] 仓位工具按钮可见');
    
    await positionBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 仓位工具可点击');
  });

  test('8. 测试测量尺工具', async ({ page }) => {
    console.log('[测试] 测试测量尺工具...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const measureBtn = toolbarPanel.locator('.toolbar-item:has(.fa-ruler)').first();
    await expect(measureBtn).toBeVisible();
    console.log('[验证] 测量尺按钮可见');
    
    await measureBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 测量尺工具可点击');
  });

  test('9. 测试放大功能', async ({ page }) => {
    console.log('[测试] 测试放大功能...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const zoomInBtn = toolbarPanel.locator('.toolbar-item:has(.fa-search-plus)').first();
    await expect(zoomInBtn).toBeVisible();
    console.log('[验证] 放大按钮可见');
    
    await zoomInBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 放大功能可点击');
  });

  test('10. 测试磁铁模式', async ({ page }) => {
    console.log('[测试] 测试磁铁模式...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const magnetBtn = toolbarPanel.locator('.toolbar-item:has(.fa-magnet)').first();
    await expect(magnetBtn).toBeVisible();
    console.log('[验证] 磁铁模式按钮可见');
    
    const initialClass = await magnetBtn.getAttribute('class');
    const wasActive = initialClass?.includes('active') || false;
    
    await magnetBtn.click();
    await page.waitForTimeout(300);
    
    const afterClickClass = await magnetBtn.getAttribute('class');
    const isActive = afterClickClass?.includes('active') || false;
    
    console.log(`[验证] 磁铁模式切换: ${wasActive ? '激活' : '未激活'} -> ${isActive ? '激活' : '未激活'}`);
    expect(isActive).toBe(!wasActive);
  });

  test('11. 测试连续绘图模式', async ({ page }) => {
    console.log('[测试] 测试连续绘图模式...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const pencilBtn = toolbarPanel.locator('.toolbar-item:has(.fa-pencil-alt)').first();
    await expect(pencilBtn).toBeVisible();
    console.log('[验证] 连续绘图按钮可见');
    
    await pencilBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 连续绘图模式可切换');
  });

  test('12. 测试锁定绘图功能', async ({ page }) => {
    console.log('[测试] 测试锁定绘图功能...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const lockBtn = toolbarPanel.locator('.toolbar-item:has(.fa-lock)').first();
    await expect(lockBtn).toBeVisible();
    console.log('[验证] 锁定绘图按钮可见');
    
    await lockBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 锁定绘图功能可切换');
  });

  test('13. 测试隐藏绘图功能', async ({ page }) => {
    console.log('[测试] 测试隐藏绘图功能...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const hideBtn = toolbarPanel.locator('.toolbar-item:has(.fa-eye-slash)').first();
    await expect(hideBtn).toBeVisible();
    console.log('[验证] 隐藏绘图按钮可见');
    
    await hideBtn.click();
    await page.waitForTimeout(300);
    console.log('[验证] 隐藏绘图功能可切换');
  });

  test('14. 测试删除功能菜单', async ({ page }) => {
    console.log('[测试] 测试删除功能菜单...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const deleteBtn = toolbarPanel.locator('.toolbar-item:has(.fa-trash-alt)').first();
    await expect(deleteBtn).toBeVisible();
    console.log('[验证] 删除按钮可见');
    
    await deleteBtn.click();
    await page.waitForTimeout(300);
    
    const submenu = toolbarPanel.locator('.submenu').first();
    const isSubmenuVisible = await submenu.isVisible().catch(() => false);
    console.log(`[验证] 删除子菜单: ${isSubmenuVisible ? '可见' : '不可见'}`);
    
    if (isSubmenuVisible) {
      const deleteSelectedBtn = submenu.locator('.submenu-item:has-text("删除选中")');
      const clearAllBtn = submenu.locator('.submenu-item:has-text("清空所有")');
      
      const hasDeleteSelected = await deleteSelectedBtn.isVisible().catch(() => false);
      const hasClearAll = await clearAllBtn.isVisible().catch(() => false);
      
      console.log(`[验证] 删除选中选项: ${hasDeleteSelected ? '存在' : '不存在'}`);
      console.log(`[验证] 清空所有选项: ${hasClearAll ? '存在' : '不存在'}`);
    }
  });

  test('15. 测试工具提示显示', async ({ page }) => {
    console.log('[测试] 测试工具提示显示...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const crosshairBtn = toolbarPanel.locator('.toolbar-item:has(.fa-crosshairs)').first();
    await crosshairBtn.hover();
    await page.waitForTimeout(500);
    
    const tooltip = toolbarPanel.locator('.tooltip').first();
    const tooltipText = await tooltip.textContent().catch(() => '');
    
    console.log(`[验证] 工具提示文本: "${tooltipText}"`);
    expect(tooltipText.length).toBeGreaterThan(0);
  });

  test('16. 测试子菜单导航', async ({ page }) => {
    console.log('[测试] 测试子菜单导航...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const trendLineBtn = toolbarPanel.locator('.toolbar-item:has(.fa-chart-line)').first();
    await trendLineBtn.click();
    await page.waitForTimeout(300);
    
    const submenu = toolbarPanel.locator('.submenu').first();
    const isSubmenuVisible = await submenu.isVisible().catch(() => false);
    
    if (isSubmenuVisible) {
      const submenuItems = submenu.locator('.submenu-item');
      const count = await submenuItems.count();
      console.log(`[验证] 趋势线子菜单包含 ${count} 个选项`);
      
      for (let i = 0; i < Math.min(count, 5); i++) {
        const item = submenuItems.nth(i);
        const text = await item.textContent().catch(() => '');
        console.log(`[验证] 子菜单选项 ${i + 1}: "${text}"`);
      }
    }
  });

  test('17. 测试工具激活状态', async ({ page }) => {
    console.log('[测试] 测试工具激活状态...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const crosshairBtn = toolbarPanel.locator('.toolbar-item:has(.fa-crosshairs)').first();
    await crosshairBtn.click();
    await page.waitForTimeout(300);
    
    const classAttr = await crosshairBtn.getAttribute('class');
    const isActive = classAttr?.includes('active') || false;
    console.log(`[验证] 十字准星工具激活状态: ${isActive ? '激活' : '未激活'}`);
    expect(isActive).toBe(true);
  });

  test('18. 测试工具栏滚动', async ({ page }) => {
    console.log('[测试] 测试工具栏滚动...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const toolbarItems = toolbarPanel.locator('.toolbar-item');
    const itemCount = await toolbarItems.count();
    console.log(`[验证] 工具栏包含 ${itemCount} 个工具项`);
    
    expect(itemCount).toBeGreaterThan(10);
  });
});

test.describe('右边栏工具与K线图交互测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/strategy/jq_volume_v1pro`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
  });

  test('工具切换后图表响应', async ({ page }) => {
    console.log('[测试] 工具切换后图表响应...');
    
    const chartArea = page.locator('.chart-area, .kline-chart').first();
    await expect(chartArea).toBeVisible({ timeout: 10000 });
    console.log('[验证] K线图区域可见');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const measureBtn = toolbarPanel.locator('.toolbar-item:has(.fa-ruler)').first();
    await measureBtn.click();
    await page.waitForTimeout(500);
    
    const canvas = chartArea.locator('canvas').first();
    const canvasVisible = await canvas.isVisible().catch(() => false);
    console.log(`[验证] 图表画布可见: ${canvasVisible}`);
  });
});
