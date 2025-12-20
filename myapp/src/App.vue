<!--
  App.vue - 项目入口
  保留作为项目入口，使用路由视图支持 Dashboard 和 StrategyDetail 页面
  原有的完整功能已迁移到 DashboardPage 和 StrategyDetailPage
-->
<template>
  <RouterView />
  <!-- CHANGED: 添加回测加载动画 -->
  <BacktestLoading />
</template>

<script setup lang="ts">
import BacktestLoading from './components/BacktestLoading.vue';
</script>

<style scoped>
/* 全局样式在 main.ts 中导入 */
</style>
