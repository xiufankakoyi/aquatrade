<template>
  <div class="main-layout" :class="{ 'workbench-mode': isWorkbenchMode }">
    <Sidebar v-if="!isWorkbenchMode" />
    <div class="main-content-wrapper">
      <TopBar v-if="!isWorkbenchMode" />
      <main class="main-content-area" :class="{ 'fullscreen': isWorkbenchMode }">
        <RouterView v-slot="{ Component, route }">
          <KeepAlive :include="['DashboardOverview']">
            <component :is="Component" :key="route.fullPath" />
          </KeepAlive>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import Sidebar from '../components/layout/Sidebar.vue';
import TopBar from '../components/layout/TopBar.vue';

const route = useRoute();

// 判断是否为工作台模式（全屏，隐藏侧边栏和顶部栏）
const isWorkbenchMode = computed(() => {
  return route.name === 'StrategyEditor';
});
</script>

<style scoped>
.main-layout {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary, #131722);
  color: var(--text-primary, #d1d4dc);
}

.main-layout.workbench-mode {
  height: 100vh;
  overflow: hidden;
}

.main-content-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.main-content-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

.main-content-area.fullscreen {
  overflow: hidden;
  height: 100vh;
}

/* 响应式适配 */
@media (max-width: 991px) {
  .main-layout {
    flex-direction: row;
  }
}

@media (max-width: 767px) {
  .main-layout {
    flex-direction: column;
  }

  .main-content-wrapper {
    width: 100%;
  }
}
</style>
