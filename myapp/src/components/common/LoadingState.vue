<template>
  <div class="common-state" role="status">
    <span class="spinner" aria-hidden="true"></span>
    <strong>{{ title }}</strong>
    <small v-if="description">{{ description }}</small>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ title?: string; description?: string }>(), {
  title: '正在加载',
  description: '',
})
</script>

<style scoped>
.common-state { min-height: 140px; display: grid; place-content: center; gap: 8px; text-align: center; color: #475569; }
.common-state small { color: #94a3b8; }
.spinner { width: 26px; height: 26px; margin: auto; border: 3px solid #dbeafe; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
