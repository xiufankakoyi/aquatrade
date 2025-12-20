<template>
  <div class="main-layout flex h-screen bg-[#0b0e14] text-slate-100">
    <Sidebar />
    <div class="flex flex-col flex-1 overflow-hidden">
      <TopBar />
      <main class="flex-1 overflow-y-auto">
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
import Sidebar from '../components/layout/Sidebar.vue';
import TopBar from '../components/layout/TopBar.vue';
</script>

