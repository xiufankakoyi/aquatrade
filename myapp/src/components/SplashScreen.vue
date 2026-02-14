<template>
  <Transition name="splash-fade">
    <div v-if="visible" class="splash-screen">
      <div class="splash-background">
        <div class="wave-container">
          <div class="wave wave1"></div>
          <div class="wave wave2"></div>
          <div class="wave wave3"></div>
        </div>
      </div>
      
      <div class="splash-content">
        <div class="logo-section">
          <div class="logo-wrapper">
            <div class="logo-glow"></div>
            <div class="logo-icon">
              <svg class="w-16 h-16 text-white" viewBox="0 0 24 24" fill="none">
                <path d="M12 2C12 2 8 6 8 10C8 14 12 18 12 18C12 18 16 14 16 10C16 6 12 2 12 2Z" fill="currentColor" opacity="0.9"/>
                <path d="M6 8C6 8 3 11 3 14C3 17 6 20 6 20C6 20 9 17 9 14C9 11 6 8 6 8Z" fill="currentColor" opacity="0.6"/>
                <path d="M18 8C18 8 15 11 15 14C15 17 18 20 18 20C18 20 21 17 21 14C21 11 18 8 18 8Z" fill="currentColor" opacity="0.6"/>
              </svg>
            </div>
          </div>
          
          <h1 class="logo-text">AquaTrade</h1>
          <p class="logo-subtitle">Quantitative Platform</p>
        </div>
        
        <div class="progress-section">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${status.progress}%` }"></div>
            <div class="progress-glow" :style="{ width: `${status.progress}%` }"></div>
          </div>
          <div class="progress-info">
            <span class="progress-percent">{{ status.progress }}%</span>
            <span class="progress-message">{{ status.message }}</span>
          </div>
        </div>
        
        <div class="logs-section">
          <div class="logs-container" ref="logsContainer">
            <div 
              v-for="(log, index) in displayLogs" 
              :key="index"
              class="log-entry"
              :class="`log-${log.level.toLowerCase()}`"
            >
              <span class="log-time">{{ log.timestamp }}</span>
              <span class="log-level">[{{ log.level }}]</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </div>
        
        <div v-if="hasError" class="error-section">
          <div class="error-content">
            <div class="error-icon">⚠️</div>
            <div class="error-info">
              <p class="error-code">{{ status.error_code }}</p>
              <p class="error-message">{{ status.error_message }}</p>
            </div>
          </div>
          <div class="error-actions">
            <button @click="retryStartup" class="btn-retry">
              <i class="fas fa-redo"></i> 重试
            </button>
            <button @click="openLogs" class="btn-logs">
              <i class="fas fa-file-alt"></i> 查看日志
            </button>
          </div>
        </div>
        
        <div v-if="isTimeout" class="timeout-section">
          <p class="timeout-message">启动超时，请检查后端服务</p>
          <button @click="retryStartup" class="btn-retry">
            <i class="fas fa-redo"></i> 重试
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'

interface LogEntry {
  timestamp: string
  level: string
  message: string
}

interface StartupStatus {
  phase: string
  step: string
  message: string
  progress: number
  ready: boolean
  error_code: string | null
  error_message: string | null
  logs: LogEntry[]
}

const emit = defineEmits<{
  (e: 'ready'): void
  (e: 'error', code: string, message: string): void
}>()

const visible = ref(true)
const status = ref<StartupStatus>({
  phase: 'idle',
  step: 'initializing',
  message: '正在唤醒 AquaTrade...',
  progress: 0,
  ready: false,
  error_code: null,
  error_message: null,
  logs: []
})

const logsContainer = ref<HTMLElement | null>(null)
const eventSource = ref<EventSource | null>(null)
const timeoutTimer = ref<number | null>(null)
const startTime = ref(Date.now())
const TIMEOUT_MS = 60000

const displayLogs = computed(() => {
  return status.value.logs.slice(-15)
})

const hasError = computed(() => {
  return status.value.error_code !== null
})

const isTimeout = computed(() => {
  return !status.value.ready && !hasError.value && Date.now() - startTime.value > TIMEOUT_MS
})

const scrollToBottom = async () => {
  await nextTick()
  if (logsContainer.value) {
    logsContainer.value.scrollTop = logsContainer.value.scrollHeight
  }
}

const connectSSE = () => {
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:5000'
  
  eventSource.value = new EventSource(`${apiBase}/api/startup-logs`)
  
  eventSource.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      if (data.event === 'close') {
        eventSource.value?.close()
        return
      }
      
      status.value = data
      scrollToBottom()
      
      if (data.ready) {
        onReady()
      }
    } catch (e) {
      console.error('Failed to parse SSE data:', e)
    }
  }
  
  eventSource.value.onerror = () => {
    eventSource.value?.close()
    status.value.message = '正在等待后端服务响应...'
    status.value.phase = 'waiting'
    setTimeout(() => {
      connectSSE()
    }, 1000)
  }
}

const pollStatus = async () => {
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:5000'
  
  try {
    const response = await fetch(`${apiBase}/api/startup-status`)
    const data = await response.json()
    status.value = data
    
    if (data.ready) {
      onReady()
    } else if (!hasError.value) {
      setTimeout(pollStatus, 500)
    }
  } catch (e) {
    status.value.message = '正在等待后端服务响应...'
    status.value.phase = 'waiting'
    if (!hasError.value) {
      setTimeout(pollStatus, 1000)
    }
  }
}

const beginStartup = async () => {
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:5000'
  
  try {
    const response = await fetch(`${apiBase}/api/startup-begin`, { method: 'POST' })
    if (response.ok) {
      connectSSE()
    } else {
      pollStatus()
    }
  } catch (e) {
    status.value.message = '正在等待后端服务响应...'
    status.value.phase = 'waiting'
    setTimeout(beginStartup, 1000)
  }
}

const onReady = () => {
  if (timeoutTimer.value) {
    clearTimeout(timeoutTimer.value)
  }
  
  setTimeout(() => {
    visible.value = false
    emit('ready')
  }, 500)
}

const retryStartup = () => {
  status.value = {
    phase: 'idle',
    step: 'initializing',
    message: '正在唤醒 AquaTrade...',
    progress: 0,
    ready: false,
    error_code: null,
    error_message: null,
    logs: []
  }
  startTime.value = Date.now()
  beginStartup()
  connectSSE()
}

const openLogs = () => {
  console.log('Opening logs...')
}

const checkTimeout = () => {
  if (!status.value.ready && !hasError.value && Date.now() - startTime.value > TIMEOUT_MS) {
    status.value.error_code = 'ERR_TIMEOUT'
    status.value.error_message = '启动超时，请检查后端服务是否正常运行'
    emit('error', 'ERR_TIMEOUT', status.value.error_message)
  }
}

watch(displayLogs, scrollToBottom)

onMounted(() => {
  startTime.value = Date.now()
  timeoutTimer.value = window.setInterval(checkTimeout, 5000)
  status.value.message = '正在连接后端服务...'
  beginStartup()
})

onUnmounted(() => {
  eventSource.value?.close()
  if (timeoutTimer.value) {
    clearInterval(timeoutTimer.value)
  }
})
</script>

<style scoped>
.splash-screen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: linear-gradient(135deg, #0B1120 0%, #0F172A 50%, #1E293B 100%);
  z-index: 9999;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
}

.splash-background {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.wave-container {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 40%;
}

.wave {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 200%;
  height: 100%;
  background: linear-gradient(180deg, transparent 60%, rgba(6, 182, 212, 0.03) 100%);
  border-radius: 50% 50% 0 0;
  transform-origin: bottom;
}

.wave1 {
  animation: wave 8s ease-in-out infinite;
  opacity: 0.5;
}

.wave2 {
  animation: wave 10s ease-in-out infinite 0.5s;
  opacity: 0.3;
}

.wave3 {
  animation: wave 12s ease-in-out infinite 1s;
  opacity: 0.2;
}

@keyframes wave {
  0%, 100% {
    transform: translateX(0) translateY(0);
  }
  50% {
    transform: translateX(-25%) translateY(-10px);
  }
}

.splash-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2rem;
  max-width: 600px;
  width: 100%;
}

.logo-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 3rem;
}

.logo-wrapper {
  position: relative;
  margin-bottom: 1.5rem;
}

.logo-glow {
  position: absolute;
  inset: -20px;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.3) 0%, transparent 70%);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 0.5;
    transform: scale(1);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.1);
  }
}

.logo-icon {
  position: relative;
  width: 80px;
  height: 80px;
  background: linear-gradient(135deg, #06B6D4 0%, #0891B2 50%, #0E7490 100%);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 20px 40px rgba(6, 182, 212, 0.3);
}

.logo-text {
  font-size: 2.5rem;
  font-weight: 700;
  background: linear-gradient(135deg, #67E8F9 0%, #22D3EE 50%, #06B6D4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.02em;
  margin: 0;
}

.logo-subtitle {
  font-size: 0.875rem;
  color: #64748B;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin-top: 0.25rem;
}

.progress-section {
  width: 100%;
  max-width: 400px;
  margin-bottom: 2rem;
}

.progress-bar {
  position: relative;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, #06B6D4 0%, #22D3EE 100%);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-glow {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.4) 50%, transparent 100%);
  border-radius: 3px;
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(400%);
  }
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.75rem;
}

.progress-percent {
  font-size: 0.875rem;
  font-weight: 600;
  color: #22D3EE;
  font-variant-numeric: tabular-nums;
}

.progress-message {
  font-size: 0.875rem;
  color: #94A3B8;
}

.logs-section {
  width: 100%;
  max-width: 500px;
  margin-bottom: 1.5rem;
}

.logs-container {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 1rem;
  height: 200px;
  overflow-y: auto;
  font-family: 'Fira Code', 'SF Mono', monospace;
  font-size: 0.75rem;
  line-height: 1.6;
}

.logs-container::-webkit-scrollbar {
  width: 4px;
}

.logs-container::-webkit-scrollbar-track {
  background: transparent;
}

.logs-container::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.log-entry {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  white-space: nowrap;
}

.log-time {
  color: #475569;
}

.log-level {
  min-width: 50px;
}

.log-info .log-level {
  color: #22D3EE;
}

.log-warn .log-level {
  color: #FBBF24;
}

.log-error .log-level {
  color: #EF4444;
}

.log-message {
  color: #CBD5E1;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.error-section {
  width: 100%;
  max-width: 500px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 12px;
  padding: 1.5rem;
}

.error-content {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.error-icon {
  font-size: 1.5rem;
}

.error-info {
  flex: 1;
}

.error-code {
  font-size: 0.875rem;
  font-weight: 600;
  color: #FCA5A5;
  margin: 0 0 0.25rem 0;
  font-family: 'Fira Code', monospace;
}

.error-message {
  font-size: 0.875rem;
  color: #FECACA;
  margin: 0;
}

.error-actions {
  display: flex;
  gap: 0.75rem;
}

.btn-retry, .btn-logs {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border: none;
}

.btn-retry {
  background: #EF4444;
  color: white;
}

.btn-retry:hover {
  background: #DC2626;
}

.btn-logs {
  background: rgba(255, 255, 255, 0.1);
  color: #CBD5E1;
}

.btn-logs:hover {
  background: rgba(255, 255, 255, 0.15);
}

.timeout-section {
  text-align: center;
}

.timeout-message {
  color: #FBBF24;
  margin-bottom: 1rem;
}

.splash-fade-enter-active,
.splash-fade-leave-active {
  transition: opacity 0.5s ease;
}

.splash-fade-enter-from,
.splash-fade-leave-to {
  opacity: 0;
}
</style>
