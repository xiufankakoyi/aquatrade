<template>
  <div class="space-y-6">
    <div class="grid grid-cols-2 gap-6">
      <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
        <h2 class="text-xl font-semibold text-white mb-2">防守仓位配置</h2>
        <p class="text-sm text-slate-400 mb-4">动态调整模型: Risk Parity V2</p>
        <DefensePie :data="defenseData" />
      </div>

      <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
        <h2 class="text-xl font-semibold text-white mb-4">风控触发规则</h2>
        <div class="space-y-3">
          <div
            v-for="rule in riskRules"
            :key="rule.id"
            class="bg-slate-800/50 rounded-lg p-4 border border-slate-700"
          >
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-sm font-semibold text-white">{{ rule.title }}</h3>
              <span
                class="px-2 py-1 text-xs rounded-full font-medium"
                :class="rule.active ? 'bg-green-500/20 text-green-400' : 'bg-slate-700 text-slate-400'"
              >
                {{ rule.active ? 'Active' : 'Paused' }}
              </span>
            </div>
            <p class="text-sm text-slate-400">{{ rule.description }}</p>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
      <h2 class="text-xl font-semibold text-white mb-4">压力测试模拟</h2>
      <div class="flex space-x-4">
        <button
          class="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
        >
          2008 金融危机
        </button>
        <button
          class="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
        >
          2020 疫情熔断
        </button>
      </div>
    </div>

    <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
      <PortfolioDefense
        :trades="defenseTrades"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useStrategyStore } from '../store/strategyStore';
import { useDefenseStore } from '../store/defenseStore';
import DefensePie from '../components/charts/DefensePie.vue';
import PortfolioDefense from '../components/PortfolioDefense.vue';

const strategyStore = useStrategyStore();
const defenseStore = useDefenseStore();

const defenseData = computed(() => {
  return defenseStore.positions.map(pos => ({
    name: pos.symbolName,
    value: pos.allocation,
    color: pos.category === 'bank' ? '#8b5cf6' : 
           pos.category === 'insurance' ? '#10b981' :
           pos.category === 'bond' ? '#f59e0b' : '#6366f1'
  }));
});

const riskRules = computed(() => {
  return defenseStore.rules.map(rule => ({
    id: rule.id,
    title: rule.name,
    description: rule.description,
    active: rule.enabled
  }));
});

const defenseTrades = computed(() => {
  return strategyStore.currentBacktestResult?.trades || [];
});
</script>

