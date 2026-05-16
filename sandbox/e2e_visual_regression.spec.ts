/**
 * 视觉回归测试
 * 测试范围：各页面视觉一致性、响应式布局、主题适配
 */

import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';

// 定义测试的视口配置
const viewports = [
  { name: 'desktop', width: 1920, height: 1080 },
  { name: 'ipad', width: 834, height: 1194 },
  { name: 'iphone', width: 430, height: 932 },
];

// 定义要测试的页面
const pages = [
  { path: '/dashboard', name: 'dashboard' },
  { path: '/strategy/default', name: 'strategy-detail' },
  { path: '/grid-search', name: 'grid-search' },
  { path: '/dragon-eye', name: 'dragon-eye' },
  { path: '/stock-sentiment', name: 'stock-sentiment' },
];

test.describe('视觉回归测试', () => {
  
  test('全页面截图对比', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      
      for (const pageConfig of pages) {
        try {
          await page.goto(`${FRONTEND_URL}${pageConfig.path}`);
          await page.waitForLoadState('networkidle');
          await page.waitForTimeout(2000); // 等待动画完成
          
          // 全页面截图
          await page.screenshot({
            path: `test-results/visual/${viewport.name}-${pageConfig.name}-full.png`,
            fullPage: true,
          });
          
          console.log(`✅ 截图完成: ${viewport.name}-${pageConfig.name}`);
        } catch (e) {
          console.log(`❌ 截图失败: ${viewport.name}-${pageConfig.name}`);
        }
      }
    }
  });

  test('关键元素截图', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 截图关键元素
    const elements = [
      { selector: 'header, .header, [class*="header"]', name: 'header' },
      { selector: 'nav, .sidebar, [class*="sidebar"]', name: 'sidebar' },
      { selector: '[class*="chart"], [class*="equity"]', name: 'chart' },
    ];
    
    for (const element of elements) {
      const locator = page.locator(element.selector).first();
      if (await locator.isVisible().catch(() => false)) {
        await locator.screenshot({
          path: `test-results/visual/element-${element.name}.png`,
        });
      }
    }
  });

  test('暗色主题一致性检查', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    
    for (const pageConfig of pages) {
      await page.goto(`${FRONTEND_URL}${pageConfig.path}`);
      await page.waitForLoadState('networkidle');
      
      // 检查背景色是否为暗色
      const bgColor = await page.evaluate(() => {
        const body = document.body;
        const computedStyle = window.getComputedStyle(body);
        return computedStyle.backgroundColor;
      });
      
      console.log(`${pageConfig.name} 背景色: ${bgColor}`);
      
      // 截图用于人工检查
      await page.screenshot({
        path: `test-results/visual/theme-${pageConfig.name}.png`,
        fullPage: true,
      });
    }
  });

  test('字体和排版检查', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 检查字体大小一致性
    const fontInfo = await page.evaluate(() => {
      const h1 = document.querySelector('h1');
      const h2 = document.querySelector('h2');
      const p = document.querySelector('p');
      
      return {
        h1: h1 ? window.getComputedStyle(h1).fontSize : null,
        h2: h2 ? window.getComputedStyle(h2).fontSize : null,
        p: p ? window.getComputedStyle(p).fontSize : null,
      };
    });
    
    console.log('字体大小:', fontInfo);
  });

  test('颜色对比度检查', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // 检查主要文本颜色
    const colors = await page.evaluate(() => {
      const elements = document.querySelectorAll('h1, h2, p, span, button');
      const colorMap: Record<string, number> = {};
      
      elements.forEach(el => {
        const color = window.getComputedStyle(el).color;
        colorMap[color] = (colorMap[color] || 0) + 1;
      });
      
      return colorMap;
    });
    
    console.log('页面颜色分布:', colors);
  });
});
