<template>
  <div class="common-state">
    <strong>{{ title }}</strong>
    <small>{{ description }}</small>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ title?: string; description?: string }>(), {
  title: '暂无数据',
  description: '暂无本地证据',
})
</script>

<style scoped>
.common-state { min-height: 140px; display: grid; place-content: center; gap: 8px; text-align: center; color: #475569; }
.common-state small { color: #94a3b8; }
</style>
