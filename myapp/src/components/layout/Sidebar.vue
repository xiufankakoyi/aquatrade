<template>
  <aside class="w-64 bg-[#151925] border-r border-slate-800 flex flex-col">
    <div class="p-6 border-b border-slate-800">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-xl">Q</span>
        </div>
        <span class="text-xl font-semibold text-white">QuantFlow</span>
      </div>
    </div>
    
    <nav class="flex-1 py-4 overflow-y-auto">
      <div class="px-4 mb-6">
        <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">核心功能</p>
        <div class="space-y-1">
          <router-link
            to="/dashboard"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/dashboard' ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-th-large w-5"></i>
            <span>总览看板</span>
          </router-link>
          <router-link
            :to="`/strategy/${dashboardStore.selectedStrategyId || ''}`"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path.startsWith('/strategy') ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-chart-line w-5"></i>
            <span>策略详情 & K线</span>
          </router-link>
          <router-link
            to="/grid-search"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/grid-search' ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-th w-5"></i>
            <span>参数网格搜索</span>
          </router-link>
          <router-link
            to="/param-compare"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/param-compare' ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-balance-scale w-5"></i>
            <span>参数对比调参</span>
          </router-link>
          <router-link
            to="/stock-sentiment"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/stock-sentiment' ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-comments w-5"></i>
            <span>股票风评</span>
          </router-link>
          <router-link
            to="/strategy-generator"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/strategy-generator' ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-robot w-5"></i>
            <span>AI 策略生成器</span>
          </router-link>
          <router-link
            to="/dragon-eye"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/dragon-eye' ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-dragon w-5"></i>
            <span>DragonEye 龙虎榜</span>
          </router-link>
        </div>
      </div>
      
      <div class="px-4">
        <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">资产管理</p>
        <div class="space-y-1">
          <router-link
            to="/defense"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/defense' ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-shield-alt w-5"></i>
            <span>防守仓配置</span>
          </router-link>
          <router-link
            to="/history"
            class="flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/history' ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-300 hover:bg-slate-800'"
          >
            <i class="fas fa-clock w-5"></i>
            <span>历史记录</span>
          </router-link>
        </div>
      </div>
    </nav>
    
    <div class="p-4 border-t border-slate-800">
      <div class="flex items-center space-x-3 px-2 py-3">
        <div class="w-10 h-10 bg-slate-700 rounded-full flex items-center justify-center">
          <i class="fas fa-user text-slate-300"></i>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-white truncate">Alex Quant</p>
          <p class="text-xs text-slate-400 truncate">高级算法研究员</p>
        </div>
        <button class="p-2 text-slate-400 hover:text-white transition-colors">
          <i class="fas fa-cog"></i>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useDashboardStore } from '../../store/dashboardStore';

const dashboardStore = useDashboardStore();
</script>

