<template>
  <aside
    class="sidebar"
    :class="{ 'collapsed': isCollapsed }"
  >
    <!-- Logo -->
    <div class="sidebar-header">
      <div v-if="isCollapsed" class="logo-collapsed">
        <i class="fas fa-water logo-icon"></i>
      </div>
      <div v-else class="logo-expanded">
        <span class="logo-text">AquaTrade</span>
        <span class="logo-subtitle">Quant</span>
      </div>
    </div>

    <!-- Toggle Button -->
    <button
      @click="toggleCollapse"
      class="toggle-btn"
      :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'"
    >
      <i class="fas" :class="isCollapsed ? 'fa-chevron-right' : 'fa-chevron-left'"></i>
    </button>

    <!-- Navigation -->
    <nav class="nav-container">
      <!-- 核心功能 -->
      <div class="nav-section">
        <p v-if="!isCollapsed" class="section-title">核心</p>
        <div class="nav-items">
          <router-link
            v-for="item in coreItems"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            :class="{ 'active': item.isActive, 'collapsed': isCollapsed }"
          >
            <!-- Icon -->
            <i
              class="nav-icon fas"
              :class="item.icon"
            ></i>

            <!-- Label (expanded only) -->
            <span v-if="!isCollapsed" class="nav-label">
              {{ item.label }}
            </span>

            <!-- Tooltip (collapsed + hover only) -->
            <div
              v-if="isCollapsed"
              class="nav-tooltip"
            >
              {{ item.label }}
              <div class="tooltip-arrow"></div>
            </div>

            <!-- Active indicator (collapsed) -->
            <div
              v-if="isCollapsed && item.isActive"
              class="active-indicator"
            ></div>
          </router-link>
        </div>
      </div>

      <!-- 资产管理 -->
      <div class="nav-section">
        <p v-if="!isCollapsed" class="section-title">资产</p>
        <div class="nav-items">
          <router-link
            v-for="item in assetItems"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            :class="{ 'active': item.isActive, 'collapsed': isCollapsed }"
          >
            <!-- Icon -->
            <i
              class="nav-icon fas"
              :class="item.icon"
            ></i>

            <!-- Label (expanded only) -->
            <span v-if="!isCollapsed" class="nav-label">
              {{ item.label }}
            </span>

            <!-- Tooltip (collapsed + hover only) -->
            <div
              v-if="isCollapsed"
              class="nav-tooltip"
            >
              {{ item.label }}
              <div class="tooltip-arrow"></div>
            </div>

            <!-- Active indicator (collapsed) -->
            <div
              v-if="isCollapsed && item.isActive"
              class="active-indicator"
            ></div>
          </router-link>
        </div>
      </div>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import { useDashboardStore } from '../../store/dashboardStore';

const route = useRoute();
const dashboardStore = useDashboardStore();

const isCollapsed = ref(true);

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value;
};

const isActive = (path: string) => {
  if (path === '/dashboard') return route.path === '/dashboard';
  if (path.startsWith('/strategy')) return route.path.startsWith('/strategy');
  return route.path === path;
};

const coreItems = computed(() => [
  {
    to: '/dashboard',
    icon: 'fa-th-large',
    label: '总览看板',
    isActive: isActive('/dashboard'),
  },
  {
    to: `/strategy/${dashboardStore.selectedStrategyId || 'apex_convergence_v1'}`,
    icon: 'fa-chart-line',
    label: '策略详情',
    isActive: isActive('/strategy'),
  },
  {
    to: '/grid-search',
    icon: 'fa-th',
    label: '网格搜索',
    isActive: isActive('/grid-search'),
  },
  {
    to: '/param-compare',
    icon: 'fa-balance-scale',
    label: '参数对比',
    isActive: isActive('/param-compare'),
  },
  {
    to: '/stock-sentiment',
    icon: 'fa-comments',
    label: '股票风评',
    isActive: isActive('/stock-sentiment'),
  },
  {
    to: '/strategy-generator',
    icon: 'fa-robot',
    label: 'AI 策略',
    isActive: isActive('/strategy-generator'),
  },
  {
    to: '/strategy-editor',
    icon: 'fa-code',
    label: '策略开发',
    isActive: isActive('/strategy-editor'),
  },
  {
    to: '/dragon-eye',
    icon: 'fa-dragon',
    label: '龙虎榜',
    isActive: isActive('/dragon-eye'),
  },
]);

const assetItems = computed(() => [
  {
    to: '/defense',
    icon: 'fa-shield-alt',
    label: '防守仓',
    isActive: isActive('/defense'),
  },
  {
    to: '/history',
    icon: 'fa-clock',
    label: '历史记录',
    isActive: isActive('/history'),
  },
]);
</script>

<style scoped>
.sidebar {
  background: var(--bg-primary, #0a0a0a);
  border-right: 1px solid var(--border-color, #1a1a1a);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  position: relative;
  width: clamp(3rem, 14vw, 14rem);
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: clamp(2.75rem, 3rem, 3.5rem);
}

/* Header */
.sidebar-header {
  height: clamp(2.5rem, 8vh, 2.75rem);
  border-bottom: 1px solid var(--border-color, #1a1a1a);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-collapsed {
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-icon {
  color: var(--accent-primary, #2962FF);
  font-size: clamp(1rem, 1.2vw, 1.25rem);
}

.logo-expanded {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.logo-text {
  font-size: clamp(0.875rem, 1vw, 1rem);
  font-weight: 600;
  color: #e5e7eb;
  letter-spacing: -0.025em;
}

.logo-subtitle {
  font-size: clamp(0.5rem, 0.6vw, 0.5625rem);
  color: #525252;
  font-weight: 500;
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

/* Toggle Button */
.toggle-btn {
  position: absolute;
  right: -0.75rem;
  top: clamp(3rem, 10vh, 3.5rem);
  width: clamp(1.25rem, 1.5vw, 1.5rem);
  height: clamp(1.25rem, 1.5vw, 1.5rem);
  background: var(--bg-secondary, #1f1f1f);
  border: 1px solid var(--border-card, #2a2a2a);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #737373;
  cursor: pointer;
  transition: all 0.2s ease;
  z-index: 10;
  padding: 0;
}

.toggle-btn:hover {
  background: var(--border-hover, #2a2a2a);
  color: #a3a3a3;
}

.toggle-btn i {
  font-size: clamp(0.5rem, 0.6vw, 0.625rem);
}

/* Navigation */
.nav-container {
  flex: 1;
  padding: clamp(0.375rem, 1vh, 0.5rem) 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-section {
  margin-bottom: clamp(0.5rem, 1.5vh, 0.75rem);
}

.section-title {
  padding: 0 clamp(0.5rem, 1vw, 0.75rem);
  font-size: clamp(0.5625rem, 0.65vw, 0.625rem);
  font-weight: 500;
  color: #525252;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: clamp(0.25rem, 0.5vh, 0.375rem);
}

.nav-items {
  display: flex;
  flex-direction: column;
  gap: clamp(0.125rem, 0.3vh, 0.25rem);
  padding: 0 clamp(0.25rem, 0.5vw, 0.375rem);
}

.nav-item {
  display: flex;
  align-items: center;
  border-radius: 0.375rem;
  transition: all 0.2s ease;
  text-decoration: none;
  color: #737373;
  position: relative;
  padding: clamp(0.375rem, 1vh, 0.5rem) clamp(0.5rem, 1vw, 0.625rem);
}

.nav-item:hover {
  background: var(--bg-tertiary, #141414);
  color: #d4d4d4;
}

.nav-item.active {
  background: var(--bg-secondary, #1f1f1f);
  color: var(--accent-primary, #2962FF);
}

.nav-item.collapsed {
  justify-content: center;
  padding: clamp(0.5rem, 1.5vh, 0.625rem) clamp(0.25rem, 0.5vw, 0.375rem);
}

.nav-icon {
  font-size: clamp(0.75rem, 0.9vw, 0.875rem);
  transition: transform 0.2s ease;
  width: clamp(1rem, 1.2vw, 1.25rem);
  text-align: center;
  flex-shrink: 0;
}

.nav-item:hover .nav-icon {
  transform: scale(1.1);
}

.nav-item.active .nav-icon {
  color: var(--accent-primary, #2962FF);
}

.nav-label {
  margin-left: clamp(0.5rem, 0.8vw, 0.625rem);
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Tooltip */
.nav-tooltip {
  position: absolute;
  left: 100%;
  margin-left: 0.5rem;
  padding: clamp(0.25rem, 0.5vw, 0.375rem) clamp(0.5rem, 0.8vw, 0.625rem);
  background: var(--bg-secondary, #1f1f1f);
  color: #d4d4d4;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  font-weight: 500;
  border-radius: 0.375rem;
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s ease;
  z-index: 50;
  border: 1px solid var(--border-card, #2a2a2a);
}

.nav-item:hover .nav-tooltip {
  opacity: 1;
  visibility: visible;
}

.tooltip-arrow {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translate(-100%, -50%);
  width: 0;
  height: 0;
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  border-right: 4px solid var(--bg-secondary, #1f1f1f);
}

/* Active indicator */
.active-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: clamp(1rem, 1.5vh, 1.25rem);
  background: var(--accent-primary, #2962FF);
  border-radius: 0 2px 2px 0;
}

/* 响应式适配 */
@media (max-width: 991px) {
  .sidebar {
    width: clamp(2.5rem, 3rem, 3.5rem);
  }

  .nav-label,
  .section-title {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: clamp(0.5rem, 1.5vh, 0.625rem) clamp(0.25rem, 0.5vw, 0.375rem);
  }

  .toggle-btn {
    display: none;
  }
}

@media (max-width: 767px) {
  .sidebar {
    width: 0;
    position: fixed;
    z-index: 50;
    overflow-x: hidden;
  }

  .sidebar.open {
    width: 200px;
  }

  .nav-label,
  .section-title {
    display: block;
  }
}
</style>
