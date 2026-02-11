<template>
  <button
    @click="toggleTheme"
    class="theme-switcher flex items-center justify-center p-2 rounded-full bg-gray-200 dark:bg-gray-800 transition-colors duration-200"
    aria-label="切换主题"
  >
    <svg
      v-if="isDarkTheme"
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="text-yellow-500"
    >
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
    <svg
      v-else
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="text-blue-500"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  </button>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';

const isDarkTheme = ref(true);

function toggleTheme() {
  isDarkTheme.value = !isDarkTheme.value;
  document.documentElement.setAttribute('data-theme', isDarkTheme.value ? 'dark' : 'light');
  localStorage.setItem('theme', isDarkTheme.value ? 'dark' : 'light');
}

onMounted(() => {
  // 从 localStorage 恢复主题设置
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) {
    isDarkTheme.value = savedTheme === 'dark';
  } else {
    // 自动检测系统主题
    isDarkTheme.value = window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  document.documentElement.setAttribute('data-theme', isDarkTheme.value ? 'dark' : 'light');
});
</script>

<style scoped>
.theme-switcher {
  cursor: pointer;
  transition: all 0.2s ease;
}

.theme-switcher:hover {
  transform: scale(1.1);
}
</style>