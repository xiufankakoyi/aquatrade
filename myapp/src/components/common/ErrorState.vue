<template>
  <div class="common-state" role="alert">
    <strong>{{ title }}</strong>
    <small>{{ message }}</small>
    <button v-if="retryable" type="button" @click="$emit('retry')">重试</button>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ title?: string; message: string; retryable?: boolean }>(), {
  title: '加载失败',
  retryable: true,
})
defineEmits<{ retry: [] }>()
</script>

<style scoped>
.common-state { min-height: 140px; display: grid; place-content: center; gap: 8px; text-align: center; color: #991b1b; background: #fff7f7; border: 1px solid #fecaca; border-radius: 12px; }
.common-state small { color: #b91c1c; }
button { margin: 4px auto 0; padding: 7px 16px; border: 0; border-radius: 8px; color: white; background: #dc2626; cursor: pointer; }
</style>
