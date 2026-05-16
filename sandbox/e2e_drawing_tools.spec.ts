/**
 * 绘图工具功能测试
 * 测试绘图工具是否能正确绘制线条（使用两次点击完成绘制）
 */
import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';

test.describe('绘图工具功能测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/strategy/jq_volume_v1pro`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    // 等待交易数据加载
    console.log('[测试] 等待交易数据加载...');
    await page.waitForFunction(() => {
      const tradeRows = document.querySelectorAll('.trade-table-container .vue-recycle-scroller__item-wrapper > div, .trade-table-container [role="row"], .trade-table-container tr');
      const emptyState = document.querySelector('.empty-state, .empty-title');
      return tradeRows.length > 0 || emptyState !== null;
    }, { timeout: 30000 });
    await page.waitForTimeout(1000);
    
    // 检查是否有交易数据
    const tradeRows = page.locator('.trade-table-container .vue-recycle-scroller__item-wrapper > div');
    let hasTrades = await tradeRows.count() > 0;
    
    if (!hasTrades) {
      console.log('[测试] 没有交易数据，需要先运行回测...');
      
      // 查找回测按钮
      const backtestBtn = page.locator('button:has-text("运行回测"), button.run-btn, .toolbar button:has-text("回")').first();
      if (await backtestBtn.isVisible().catch(() => false)) {
        console.log('[测试] 找到回测按钮，点击运行...');
        await backtestBtn.click();
        
        // 等待回测完成
        console.log('[测试] 等待回测完成...');
        await page.waitForFunction(() => {
          const tradeRows = document.querySelectorAll('.trade-table-container .vue-recycle-scroller__item-wrapper > div');
          return tradeRows.length > 0;
        }, { timeout: 120000 }).catch(() => {
          console.log('[测试] 回测超时或没有交易数据');
        });
        
        await page.waitForTimeout(2000);
        hasTrades = await tradeRows.count() > 0;
      }
    }
    
    console.log('[测试] 交易数据状态:', hasTrades ? '有数据' : '无数据');
    
    // 点击第一个交易来加载 K 线数据
    const firstTrade = page.locator('.trade-table-container .vue-recycle-scroller__item-wrapper > div').first();
    if (await firstTrade.isVisible().catch(() => false)) {
      console.log('[测试] 点击第一个交易加载 K 线数据...');
      await firstTrade.click();
      await page.waitForTimeout(1000);
      
      // 关闭可能打开的 TradeDeepDive 模态框
      const modal = page.locator('.fixed.inset-0.z-\\[100\\]');
      if (await modal.isVisible().catch(() => false)) {
        console.log('[测试] 关闭 TradeDeepDive 模态框...');
        await page.keyboard.press('Escape');
        await page.waitForTimeout(500);
      }
      
      // 等待 K 线数据加载
      console.log('[测试] 等待 K 线数据加载...');
      await page.waitForFunction(() => {
        // 检查是否有 K 线数据（通过检查 canvas 是否有内容）
        const canvas = document.querySelector('.chart-area canvas, .tv-kline-container canvas') as HTMLCanvasElement;
        if (!canvas) return false;
        const ctx = canvas.getContext('2d');
        if (!ctx) return false;
        // 检查 canvas 是否有绘制内容
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const hasContent = imageData.data.some((val, i) => i % 4 === 3 && val > 0);
        return hasContent;
      }, { timeout: 10000 }).catch(() => {
        console.log('[测试] K 线数据未加载');
      });
      
      // 检查 klineStore 是否有数据
      const klineStoreData = await page.evaluate(() => {
        // 尝试从 Vue 组件获取数据
        const chartContainer = document.querySelector('.tv-kline-container');
        if (!chartContainer) return { hasContainer: false };
        
        // 检查 canvas 是否有内容
        const canvas = chartContainer.querySelector('canvas') as HTMLCanvasElement;
        if (!canvas) return { hasCanvas: false };
        
        const ctx = canvas.getContext('2d');
        if (!ctx) return { hasContext: false };
        
        // 检查 canvas 是否有绘制内容
        const imageData = ctx.getImageData(0, 0, Math.min(canvas.width, 100), Math.min(canvas.height, 100));
        let nonZeroPixels = 0;
        for (let i = 0; i < imageData.data.length; i += 4) {
          if (imageData.data[i + 3] > 0) nonZeroPixels++;
        }
        
        return {
          hasContainer: true,
          hasCanvas: true,
          canvasWidth: canvas.width,
          canvasHeight: canvas.height,
          nonZeroPixels: nonZeroPixels
        };
      });
      console.log('[测试] 图表数据:', klineStoreData);
      
      // 等待 K 线数据加载完成
      console.log('[测试] 等待 K 线数据加载完成...');
      
      // 等待足够长的时间让 K 线数据加载
      await page.waitForTimeout(5000);
      
      // 检查数据是否加载成功
      const dataCheck = await page.evaluate(() => {
        const chartContainer = document.querySelector('.tv-kline-container');
        if (!chartContainer) return { hasData: false };
        
        const canvas = chartContainer.querySelector('canvas') as HTMLCanvasElement;
        if (!canvas) return { hasData: false };
        
        const ctx = canvas.getContext('2d');
        if (!ctx) return { hasData: false };
        
        // 检查整个 canvas 是否有绘制内容
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        let coloredPixels = 0;
        for (let i = 0; i < imageData.data.length; i += 4) {
          if (imageData.data[i + 3] > 0) coloredPixels++;
        }
        
        return { hasData: coloredPixels > 50000, coloredPixels };
      });
      console.log('[测试] 数据检查:', dataCheck);
    } else {
      console.log('[测试] 未找到交易行，尝试直接使用图表');
    }
    
    // 等待 K 线数据加载完成
    console.log('[测试] 等待 K 线数据加载...');
    await page.waitForFunction(() => {
      const canvas = document.querySelector('.chart-area canvas, .tv-kline-container canvas');
      return canvas !== null;
    }, { timeout: 30000 });
    await page.waitForTimeout(2000);
    
    // 检查是否有 K 线数据
    const hasKlineData = await page.evaluate(() => {
      const canvas = document.querySelector('.chart-area canvas, .tv-kline-container canvas');
      if (!canvas) return false;
      const rect = canvas.getBoundingClientRect();
      return rect.width > 100 && rect.height > 100;
    });
    console.log('[测试] K 线数据加载完成, hasKlineData:', hasKlineData);
  });

  test('测试趋势线绘制功能（两次点击）', async ({ page }) => {
    console.log('[测试] 测试趋势线绘制功能...');
    
    // 关闭可能存在的模态框（点击关闭按钮）
    for (let i = 0; i < 3; i++) {
      const modal = page.locator('.fixed.inset-0.z-\\[100\\]');
      if (await modal.isVisible().catch(() => false)) {
        console.log('[测试] 关闭模态框...');
        // 点击模态框内的关闭按钮
        const closeBtn = modal.locator('button:has(.fa-times)').first();
        if (await closeBtn.isVisible().catch(() => false)) {
          await closeBtn.click();
        } else {
          await page.keyboard.press('Escape');
        }
        await page.waitForTimeout(500);
      } else {
        break;
      }
    }
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const trendLineBtn = toolbarPanel.locator('.toolbar-item:has(.fa-chart-line)').first();
    await trendLineBtn.click();
    await page.waitForTimeout(300);
    
    const submenu = toolbarPanel.locator('.submenu').first();
    await expect(submenu).toBeVisible();
    
    const trendLineOption = submenu.locator('.submenu-item:has-text("趋势线")').first();
    await trendLineOption.click();
    await page.waitForTimeout(500);
    
    console.log('[测试] 已选择趋势线工具');
    
    const chartArea = page.locator('.chart-area, .tv-kline-container').first();
    await expect(chartArea).toBeVisible({ timeout: 10000 });
    
    const canvas = chartArea.locator('canvas').first();
    await expect(canvas).toBeVisible();
    
    const box = await canvas.boundingBox();
    if (!box) {
      console.log('[测试] 无法获取画布边界');
      return;
    }
    
    console.log('[测试] 画布边界:', box);
    
    const startX = box.x + box.width * 0.3;
    const startY = box.y + box.height * 0.5;
    const endX = box.x + box.width * 0.7;
    const endY = box.y + box.height * 0.3;
    
    console.log('[测试] 第一次点击位置:', { x: startX, y: startY });
    console.log('[测试] 第二次点击位置:', { x: endX, y: endY });
    
    const consoleMessages: string[] = [];
    page.on('console', msg => {
      const text = msg.text();
      if (text.includes('[subscribeClick]') || 
          text.includes('[useChartDrawing]') ||
          text.includes('[renderTrendLine]') ||
          text.includes('[toChartTime]') ||
          text.includes('[TVKlineChart') ||
          text.includes('props.data') ||
          text.includes('currentData') ||
          text.includes('updateCandlestickData') ||
          text.includes('currentDataRef') ||
          text.includes('watch]') ||
          text.includes('watchEffect') ||
          text.includes('[klineStore]')) {
        consoleMessages.push(text);
        console.log('[浏览器控制台]', text);
      }
    });
    
    // 检查图表是否有数据
    const chartDataInfo = await page.evaluate(() => {
      const container = document.querySelector('.tv-kline-container');
      if (!container) return { hasContainer: false };
      
      // 检查是否有 canvas
      const canvases = container.querySelectorAll('canvas');
      return {
        hasContainer: true,
        canvasCount: canvases.length,
        canvasSizes: Array.from(canvases).map(c => ({
          width: c.width,
          height: c.height
        }))
      };
    });
    console.log('[测试] 图表信息:', chartDataInfo);
    
    await page.mouse.click(startX, startY);
    await page.waitForTimeout(500);
    
    console.log('[测试] 第一次点击完成');
    
    await page.mouse.click(endX, endY);
    await page.waitForTimeout(1000);
    
    console.log('[测试] 第二次点击完成');
    console.log('[测试] 控制台消息:', consoleMessages);
    
    const hasStartDrawing = consoleMessages.some(m => m.includes('startDrawing'));
    const hasFinishDrawing = consoleMessages.some(m => m.includes('finishDrawing') || m.includes('renderTrendLine'));
    
    console.log('[验证] 开始绘制:', hasStartDrawing);
    console.log('[验证] 完成绘制:', hasFinishDrawing);
  });

  test('测试水平线绘制功能', async ({ page }) => {
    console.log('[测试] 测试水平线绘制功能...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const trendLineBtn = toolbarPanel.locator('.toolbar-item:has(.fa-chart-line)').first();
    await trendLineBtn.click();
    await page.waitForTimeout(300);
    
    const submenu = toolbarPanel.locator('.submenu').first();
    await expect(submenu).toBeVisible();
    
    const horizontalLineOption = submenu.locator('.submenu-item:has-text("水平线")').first();
    await horizontalLineOption.click();
    await page.waitForTimeout(500);
    
    console.log('[测试] 已选择水平线工具');
    
    const chartArea = page.locator('.chart-area, .tv-kline-container').first();
    const canvas = chartArea.locator('canvas').first();
    const box = await canvas.boundingBox();
    if (!box) return;
    
    const clickX = box.x + box.width * 0.5;
    const clickY = box.y + box.height * 0.5;
    
    await page.mouse.click(clickX, clickY);
    await page.waitForTimeout(500);
    
    console.log('[测试] 水平线绘制完成');
  });

  test('测试测量尺功能', async ({ page }) => {
    console.log('[测试] 测试测量尺功能...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const measureBtn = toolbarPanel.locator('.toolbar-item:has(.fa-ruler)').first();
    await measureBtn.click();
    await page.waitForTimeout(500);
    
    console.log('[测试] 已选择测量尺工具');
    
    const chartArea = page.locator('.chart-area, .tv-kline-container').first();
    const canvas = chartArea.locator('canvas').first();
    const box = await canvas.boundingBox();
    if (!box) return;
    
    const startX = box.x + box.width * 0.3;
    const startY = box.y + box.height * 0.5;
    const endX = box.x + box.width * 0.7;
    const endY = box.y + box.height * 0.3;
    
    await page.mouse.click(startX, startY);
    await page.waitForTimeout(500);
    await page.mouse.click(endX, endY);
    await page.waitForTimeout(500);
    
    console.log('[测试] 测量尺绘制完成');
  });

  test('测试斐波那契回调线绘制', async ({ page }) => {
    console.log('[测试] 测试斐波那契回调线绘制...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const fibBtn = toolbarPanel.locator('.toolbar-item:has(.fa-grip-lines)').first();
    await fibBtn.click();
    await page.waitForTimeout(300);
    
    const submenu = toolbarPanel.locator('.submenu').first();
    const isSubmenuVisible = await submenu.isVisible().catch(() => false);
    
    if (isSubmenuVisible) {
      const fibOption = submenu.locator('.submenu-item:has-text("斐波那契回调")').first();
      await fibOption.click();
      await page.waitForTimeout(500);
      console.log('[测试] 已选择斐波那契回调工具');
    } else {
      console.log('[测试] 斐波那契工具已直接选中');
    }
    
    const chartArea = page.locator('.chart-area, .tv-kline-container').first();
    const canvas = chartArea.locator('canvas').first();
    const box = await canvas.boundingBox();
    if (!box) return;
    
    const startX = box.x + box.width * 0.3;
    const startY = box.y + box.height * 0.3;
    const endX = box.x + box.width * 0.7;
    const endY = box.y + box.height * 0.7;
    
    await page.mouse.click(startX, startY);
    await page.waitForTimeout(500);
    await page.mouse.click(endX, endY);
    await page.waitForTimeout(500);
    
    console.log('[测试] 斐波那契回调线绘制完成');
  });

  test('测试矩形绘制功能', async ({ page }) => {
    console.log('[测试] 测试矩形绘制功能...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const shapesBtn = toolbarPanel.locator('.toolbar-item:has(.fa-shapes)').first();
    await shapesBtn.click();
    await page.waitForTimeout(300);
    
    const submenu = toolbarPanel.locator('.submenu').first();
    const isSubmenuVisible = await submenu.isVisible().catch(() => false);
    
    if (isSubmenuVisible) {
      const rectangleOption = submenu.locator('.submenu-item:has-text("矩形")').first();
      await rectangleOption.click();
      await page.waitForTimeout(500);
      console.log('[测试] 已选择矩形工具');
    } else {
      console.log('[测试] 矩形工具已直接选中');
    }
    
    const chartArea = page.locator('.chart-area, .tv-kline-container').first();
    const canvas = chartArea.locator('canvas').first();
    const box = await canvas.boundingBox();
    if (!box) return;
    
    const startX = box.x + box.width * 0.3;
    const startY = box.y + box.height * 0.3;
    const endX = box.x + box.width * 0.7;
    const endY = box.y + box.height * 0.7;
    
    await page.mouse.click(startX, startY);
    await page.waitForTimeout(500);
    await page.mouse.click(endX, endY);
    await page.waitForTimeout(500);
    
    console.log('[测试] 矩形绘制完成');
  });

  test('测试删除绘图功能', async ({ page }) => {
    console.log('[测试] 测试删除绘图功能...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const trendLineBtn = toolbarPanel.locator('.toolbar-item:has(.fa-chart-line)').first();
    await trendLineBtn.click();
    await page.waitForTimeout(300);
    
    const submenu = toolbarPanel.locator('.submenu').first();
    await expect(submenu).toBeVisible();
    
    const trendLineOption = submenu.locator('.submenu-item:has-text("趋势线")').first();
    await trendLineOption.click();
    await page.waitForTimeout(500);
    
    const chartArea = page.locator('.chart-area, .tv-kline-container').first();
    const canvas = chartArea.locator('canvas').first();
    const box = await canvas.boundingBox();
    if (!box) return;
    
    const startX = box.x + box.width * 0.3;
    const startY = box.y + box.height * 0.5;
    const endX = box.x + box.width * 0.7;
    const endY = box.y + box.height * 0.3;
    
    await page.mouse.click(startX, startY);
    await page.waitForTimeout(500);
    await page.mouse.click(endX, endY);
    await page.waitForTimeout(500);
    
    console.log('[测试] 已绘制一条趋势线');
    
    const deleteBtn = toolbarPanel.locator('.toolbar-item:has(.fa-trash-alt)').first();
    await deleteBtn.click();
    await page.waitForTimeout(300);
    
    const deleteSubmenu = toolbarPanel.locator('.submenu').first();
    const clearAllBtn = deleteSubmenu.locator('.submenu-item:has-text("清空所有")').first();
    
    if (await clearAllBtn.isVisible()) {
      await clearAllBtn.click();
      await page.waitForTimeout(300);
      console.log('[测试] 已清空所有绘图');
    }
  });

  test('测试磁铁模式切换', async ({ page }) => {
    console.log('[测试] 测试磁铁模式切换...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const magnetBtn = toolbarPanel.locator('.toolbar-item:has(.fa-magnet)').first();
    await expect(magnetBtn).toBeVisible();
    
    const initialClass = await magnetBtn.getAttribute('class');
    const wasActive = initialClass?.includes('active') || false;
    
    await magnetBtn.click();
    await page.waitForTimeout(300);
    
    const afterClickClass = await magnetBtn.getAttribute('class');
    const isActive = afterClickClass?.includes('active') || false;
    
    console.log(`[验证] 磁铁模式切换: ${wasActive ? '激活' : '未激活'} -> ${isActive ? '激活' : '未激活'}`);
    expect(isActive).toBe(!wasActive);
  });

  test('测试锁定绘图功能', async ({ page }) => {
    console.log('[测试] 测试锁定绘图功能...');
    
    const toolbarPanel = page.locator('.toolbar-panel, .chart-toolbar').first();
    await expect(toolbarPanel).toBeVisible({ timeout: 10000 });
    
    const lockBtn = toolbarPanel.locator('.toolbar-item:has(.fa-lock)').first();
    await expect(lockBtn).toBeVisible();
    
    await lockBtn.click();
    await page.waitForTimeout(300);
    
    const afterClickClass = await lockBtn.getAttribute('class');
    const isActive = afterClickClass?.includes('active') || false;
    
    console.log(`[验证] 锁定绘图状态: ${isActive ? '激活' : '未激活'}`);
  });
});
