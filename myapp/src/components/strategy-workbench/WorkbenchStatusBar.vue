<template>
  <div class="workbench-status-bar">
    <div class="status-left">
      <div class="status-item">
        <span
          class="status-dot"
          :class="apiStatus"
        ></span>
        <span class="status-text">
          {{ apiStatus === 'connected' ? '已连接' : '未连接' }}
        </span>
      </div>
      
      <div class="status-divider"></div>
      
      <div class="status-item">
        <i class="fas fa-clock"></i>
        <span class="status-text">{{ lastUpdate || '--' }}</span>
      </div>
    </div>

    <div class="status-center">
      <div v-if="currentDate" class="current-date">
        <i class="fas fa-calendar-alt"></i>
        <span>当前回测日期: {{ currentDate }}</span>
      </div>
    </div>

    <div class="status-right">
      <div v-if="progress > 0" class="progress-indicator">
        <div class="mini-progress-bar">
          <div
            class="mini-progress-fill"
            :style="{ width: progress * 100 + '%' }"
          ></div>
        </div>
        <span class="progress-text">{{ Math.round(progress * 100) }}%</span>
      </div>
      
      <div class="status-item">
        <span class="status-text">AquaTrade v1.0</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// ============================================
// Props
// ============================================
interface Props {
  apiStatus: 'connected' | 'disconnected';
  lastUpdate: string;
  currentDate?: string;
  progress?: number;
}

withDefaults(defineProps<Props>(), {
  progress: 0,
});
</script>

<style scoped>
.workbench-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 24px;
  padding: 0 12px;
  background-color: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

.status-left,
.status-center,
.status-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-dot.connected {
  background-color: var(--color-up);
}

.status-dot.disconnected {
  background-color: var(--color-down);
}

.status-text {
  font-size: 10px;
  color: var(--text-muted);
}

.status-divider {
  width: 1px;
  height: 12px;
  background-color: var(--border-color);
}

.current-date {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  background-color: var(--bg-tertiary);
  border-radius: 3px;
  font-size: 10px;
  color: var(--text-secondary);
}

.current-date i {
  font-size: 9px;
  color: var(--accent-primary);
}

.progress-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mini-progress-bar {
  width: 60px;
  height: 3px;
  background-color: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  background-color: var(--accent-primary);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 9px;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

/* 响应式 */
@media (max-width: 767px) {
  .status-center {
    display: none;
  }
}
</style>
