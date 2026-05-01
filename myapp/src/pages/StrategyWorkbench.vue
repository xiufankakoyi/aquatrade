<template>
  <StrategyWorkbenchLayout />
</template>

<script setup lang="ts">
import { onBeforeUnmount } from 'vue';
import StrategyWorkbenchLayout from '../components/strategy-workbench/StrategyWorkbenchLayout.vue';

defineOptions({
  name: 'StrategyWorkbench'
});

// 确保组件卸载时清理所有资源
onBeforeUnmount(() => {
  console.log('[StrategyWorkbench] 组件即将卸载');
});
</script>
