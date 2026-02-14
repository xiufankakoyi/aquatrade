<template>
  <div class="app-container">
    <SplashScreen 
      v-if="showSplash" 
      @ready="onSplashReady" 
      @error="onSplashError"
    />
    
    <Transition name="fade-slow" mode="out-in">
      <DashboardSkeleton v-if="showSkeleton && !showSplash" />
      <div v-else-if="!showSplash" class="main-content">
        <RouterView />
      </div>
    </Transition>
    
    <BacktestLoading />
    <ErrorReporter />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SplashScreen from './components/SplashScreen.vue'
import DashboardSkeleton from './components/DashboardSkeleton.vue'
import BacktestLoading from './components/BacktestLoading.vue'
import ErrorReporter from './components/ErrorReporter.vue'

const showSplash = ref(true)
const showSkeleton = ref(false)
const SKELETON_DURATION = 800

const onSplashReady = () => {
  showSkeleton.value = true
  showSplash.value = false
  
  setTimeout(() => {
    showSkeleton.value = false
  }, SKELETON_DURATION)
}

const onSplashError = (code: string, message: string) => {
  console.error('Startup error:', code, message)
}

onMounted(() => {
  const skipSplash = localStorage.getItem('aquatrade_skip_splash') === 'true'
  if (skipSplash) {
    showSplash.value = false
  }
})
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  background: #0F172A;
}

.main-content {
  min-height: 100vh;
}

.fade-slow-enter-active,
.fade-slow-leave-active {
  transition: opacity 0.4s ease;
}

.fade-slow-enter-from,
.fade-slow-leave-to {
  opacity: 0;
}
</style>
