/**
 * 路由配置
 * 定义应用的主要路由：Dashboard 和策略详情页
 */
import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    children: [
      {
        path: '',
        redirect: '/dashboard'
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../pages/DashboardOverview.vue'),
        meta: {
          title: '总览看板',
          keepAlive: true
        }
      },
      {
        path: 'strategy/:id?',
        name: 'StrategyDetail',
        component: () => import('../pages/StrategyDetailKline.vue'),
        meta: {
          title: '策略详情 & K线'
        },
        props: true
      },
      {
        path: 'grid-search',
        name: 'GridSearch',
        component: () => import('../pages/GridSearchPage.vue'),
        meta: {
          title: '参数网格搜索'
        }
      },
      {
        path: 'param-compare',
        name: 'ParamCompare',
        component: () => import('../pages/ParamComparePage.vue'),
        meta: {
          title: '参数对比调参'
        }
      },
      {
        path: 'stock-sentiment',
        name: 'StockSentiment',
        component: () => import('../pages/StockSentimentPage.vue'),
        meta: {
          title: '股票风评'
        }
      },
      {
        path: 'defense',
        name: 'Defense',
        component: () => import('../pages/DefenseConfigPage.vue'),
        meta: {
          title: '防守仓配置'
        }
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('../pages/HistoryRecordsPage.vue'),
        meta: {
          title: '历史记录'
        }
      },
      {
        path: 'strategy-generator',
        name: 'StrategyGenerator',
        component: () => import('../pages/StrategyGeneratorPage.vue'),
        meta: {
          title: 'AI 策略生成器'
        }
      },
      {
        path: 'strategy-editor',
        name: 'StrategyEditor',
        component: () => import('../pages/StrategyWorkbench.vue'),
        meta: {
          title: '策略开发工作台'
        }
      },
      {
        path: 'dragon-eye',
        name: 'DragonEye',
        component: () => import('../pages/DragonEyePage.vue'),
        meta: {
          title: 'DragonEye 龙虎榜'
        }
      }
    ]
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;

