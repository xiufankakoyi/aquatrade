<template>
  <aside
    class="sidebar"
    :class="{ 'collapsed': isCollapsed, 'dragging': isDragging }"
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

    <!-- Edit Mode Toggle -->
    <button
      v-if="!isCollapsed"
      @click="toggleEditMode"
      class="edit-mode-btn"
      :class="{ 'active': isEditMode }"
      :title="isEditMode ? '完成排序' : '调整顺序'"
    >
      <i class="fas" :class="isEditMode ? 'fa-check' : 'fa-grip-lines'"></i>
    </button>

    <!-- Navigation -->
    <nav class="nav-container">
      <!-- 导航菜单 -->
      <div class="nav-items">
        <div
          v-for="(item, index) in navItems"
          :key="item.to"
          class="nav-item-wrapper"
          :class="{
            'dragging': draggedItem?.to === item.to,
            'drag-over': dragOverItem?.to === item.to,
            'edit-mode': isEditMode
          }"
          :draggable="isEditMode"
          @dragstart="handleDragStart($event, item, index)"
          @dragend="handleDragEnd"
          @dragover.prevent="handleDragOver($event, item)"
          @drop="handleDrop($event, item, index)"
        >
          <!-- Drag Handle (only in edit mode) -->
          <div v-if="isEditMode" class="drag-handle">
            <i class="fas fa-grip-vertical"></i>
          </div>

          <router-link
            :to="item.to"
            class="nav-item"
            :class="{ 'active': item.isActive, 'collapsed': isCollapsed }"
            @click="handleNavClick"
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
import { ref, computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useDashboardStore } from '../../store/dashboardStore';

const route = useRoute();
const dashboardStore = useDashboardStore();

const isCollapsed = ref(true);
const isEditMode = ref(false);
const isDragging = ref(false);

// 拖拽状态
const draggedItem = ref<NavItem | null>(null);
const dragOverItem = ref<NavItem | null>(null);
const draggedFromIndex = ref<number>(-1);

// 导航项顺序（从 localStorage 读取或默认）
const defaultOrder = [
  '/dashboard',
  '/strategy',
  '/param-optimization',
  '/stock-sentiment',
  '/strategy-center',
  '/dragon-eye',
  '/kline-game',
  '/stock-screener',
  '/similarity',
  '/industry-chain',
  '/portfolio',
  '/history',
];

const navOrder = ref<string[]>(loadOrder('sidebar_nav_order', defaultOrder));

interface NavItem {
  to: string;
  icon: string;
  label: string;
  isActive: boolean;
}

// 从 localStorage 加载顺序
function loadOrder(key: string, defaultOrder: string[]): string[] {
  try {
    const saved = localStorage.getItem(key);
    if (saved) {
      const parsed = JSON.parse(saved);
      // 验证保存的顺序包含所有默认项
      const hasAllItems = defaultOrder.every(item => parsed.includes(item));
      const noExtraItems = parsed.every((item: string) => defaultOrder.includes(item));
      if (hasAllItems && noExtraItems) {
        return parsed;
      }
    }
  } catch {
    // 解析失败，使用默认顺序
  }
  return defaultOrder;
}

// 保存顺序到 localStorage
function saveOrder(key: string, order: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(order));
  } catch (e) {
    console.error('保存侧边栏顺序失败:', e);
  }
}

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value;
  // 收起时退出编辑模式
  if (isCollapsed.value) {
    isEditMode.value = false;
  }
};

const toggleEditMode = () => {
  isEditMode.value = !isEditMode.value;
};

const handleNavClick = () => {
  // 点击导航项时退出编辑模式
  if (isEditMode.value) {
    isEditMode.value = false;
  }
};

const isActive = (path: string) => {
  if (path === '/dashboard') return route.path === '/dashboard';
  if (path.startsWith('/strategy')) return route.path.startsWith('/strategy');
  return route.path === path;
};

// 所有导航项
const allNavItems = computed<NavItem[]>(() => [
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
    to: '/param-optimization',
    icon: 'fa-sliders-h',
    label: '参数优化',
    isActive: isActive('/param-optimization'),
  },
  {
    to: '/stock-sentiment',
    icon: 'fa-comments',
    label: '股票风评',
    isActive: isActive('/stock-sentiment'),
  },
  {
    to: '/strategy-center',
    icon: 'fa-code',
    label: '策略中心',
    isActive: isActive('/strategy-center'),
  },
  {
    to: '/dragon-eye',
    icon: 'fa-dragon',
    label: '龙虎榜',
    isActive: isActive('/dragon-eye'),
  },
  {
    to: '/kline-game',
    icon: 'fa-gamepad',
    label: '盘感训练',
    isActive: isActive('/kline-game'),
  },
  {
    to: '/stock-screener',
    icon: 'fa-filter',
    label: '股票筛选器',
    isActive: isActive('/stock-screener'),
  },
  {
    to: '/similarity',
    icon: 'fa-shapes',
    label: '形态研究',
    isActive: isActive('/similarity'),
  },
  {
    to: '/industry-chain',
    icon: 'fa-network-wired',
    label: '产业链雷达',
    isActive: isActive('/industry-chain'),
  },
  {
    to: '/portfolio',
    icon: 'fa-wallet',
    label: '实盘持仓',
    isActive: isActive('/portfolio'),
  },
  {
    to: '/history',
    icon: 'fa-clock',
    label: '历史记录',
    isActive: isActive('/history'),
  },
]);

// 根据顺序排序的导航项
const navItems = computed(() => {
  const items = allNavItems.value;
  return items.sort((a, b) => {
    const indexA = navOrder.value.findIndex(path => {
      if (path === '/strategy') return a.to.startsWith('/strategy');
      return a.to === path;
    });
    const indexB = navOrder.value.findIndex(path => {
      if (path === '/strategy') return b.to.startsWith('/strategy');
      return b.to === path;
    });
    return indexA - indexB;
  });
});

// 拖拽处理
const handleDragStart = (e: DragEvent, item: NavItem, index: number) => {
  if (!isEditMode.value) return;

  draggedItem.value = item;
  draggedFromIndex.value = index;
  isDragging.value = true;

  // 设置拖拽效果
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', item.to);
  }
};

const handleDragEnd = () => {
  draggedItem.value = null;
  dragOverItem.value = null;
  draggedFromIndex.value = -1;
  isDragging.value = false;
};

const handleDragOver = (e: DragEvent, item: NavItem) => {
  if (!isEditMode.value || !draggedItem.value) return;

  e.preventDefault();

  // 不显示拖拽到自己上面
  if (draggedItem.value.to === item.to) {
    dragOverItem.value = null;
    return;
  }

  dragOverItem.value = item;

  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'move';
  }
};

const handleDrop = (e: DragEvent, targetItem: NavItem, _targetIndex: number) => {
  e.preventDefault();

  if (!isEditMode.value || !draggedItem.value) return;

  // 获取当前顺序数组
  const currentOrder = [...navOrder.value];

  // 找到拖拽项和目标项的路径
  const draggedPath = draggedItem.value.to.startsWith('/strategy')
    ? '/strategy'
    : draggedItem.value.to;
  const targetPath = targetItem.to.startsWith('/strategy') ? '/strategy' : targetItem.to;

  // 找到索引
  const fromIndex = currentOrder.indexOf(draggedPath);
  const toIndex = currentOrder.indexOf(targetPath);

  if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) return;

  // 重新排序
  currentOrder.splice(fromIndex, 1);
  currentOrder.splice(toIndex, 0, draggedPath);

  // 更新顺序
  navOrder.value = currentOrder;
  saveOrder('sidebar_nav_order', currentOrder);

  // 清理拖拽状态
  dragOverItem.value = null;
};

// 监听路由变化，退出编辑模式
watch(() => route.path, () => {
  if (isEditMode.value) {
    isEditMode.value = false;
  }
});
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
  --sidebar-width: clamp(3rem, 14vw, 14rem);
  overflow: visible;
  z-index: 100;
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.4);
}

.sidebar.collapsed {
  width: clamp(2.75rem, 3rem, 3.5rem);
  --sidebar-width: clamp(2.75rem, 3rem, 3.5rem);
}

.sidebar.dragging {
  user-select: none;
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

/* Edit Mode Button */
.edit-mode-btn {
  position: absolute;
  right: -0.75rem;
  top: clamp(4.5rem, 14vh, 5rem);
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

.edit-mode-btn:hover {
  background: var(--border-hover, #2a2a2a);
  color: #a3a3a3;
}

.edit-mode-btn.active {
  background: var(--accent-primary, #2962FF);
  border-color: var(--accent-primary, #2962FF);
  color: #fff;
}

.edit-mode-btn i {
  font-size: clamp(0.5rem, 0.6vw, 0.625rem);
}

/* Navigation */
.nav-container {
  flex: 1;
  padding: clamp(0.375rem, 1vh, 0.5rem) 0;
  overflow-y: auto;
  overflow-x: visible;
}

.nav-items {
  display: flex;
  flex-direction: column;
  gap: clamp(0.125rem, 0.3vh, 0.25rem);
  padding: 0 clamp(0.25rem, 0.5vw, 0.375rem);
}

/* Nav Item Wrapper */
.nav-item-wrapper {
  display: flex;
  align-items: center;
  border-radius: 0.375rem;
  transition: all 0.2s ease;
}

.nav-item-wrapper.edit-mode {
  background: var(--bg-secondary, #1f1f1f);
  border: 1px dashed var(--border-card, #2a2a2a);
}

.nav-item-wrapper.dragging {
  opacity: 0.5;
}

.nav-item-wrapper.drag-over {
  background: rgba(41, 98, 255, 0.1);
  border: 1px dashed var(--accent-primary, #2962FF);
}

/* Drag Handle */
.drag-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 clamp(0.25rem, 0.5vw, 0.375rem);
  color: #525252;
  cursor: grab;
  flex-shrink: 0;
}

.drag-handle:active {
  cursor: grabbing;
}

.drag-handle i {
  font-size: clamp(0.625rem, 0.75vw, 0.75rem);
}

/* Nav Item */
.nav-item {
  display: flex;
  align-items: center;
  flex: 1;
  border-radius: 0.375rem;
  transition: all 0.2s ease;
  text-decoration: none;
  color: #737373;
  position: relative;
  padding: clamp(0.375rem, 1vh, 0.5rem) clamp(0.5rem, 1vw, 0.625rem);
}

.nav-item-wrapper.edit-mode .nav-item {
  padding-left: clamp(0.25rem, 0.5vw, 0.375rem);
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
  left: calc(100% + 0.5rem);
  top: 50%;
  transform: translateY(-50%);
  padding: clamp(0.25rem, 0.5vw, 0.375rem) clamp(0.5rem, 0.8vw, 0.625rem);
  background: var(--bg-secondary, #1f1f1f);
  color: #d4d4d4;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  font-weight: 500;
  border-radius: 0.375rem;
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.2s ease, visibility 0.2s ease;
  z-index: 9999;
  border: 1px solid var(--border-card, #2a2a2a);
  pointer-events: none;
}

.nav-item:hover .nav-tooltip {
  opacity: 1;
  visibility: visible;
}

.tooltip-arrow {
  position: absolute;
  left: -4px;
  top: 50%;
  transform: translateY(-50%);
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

  .nav-label {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: clamp(0.5rem, 1.5vh, 0.625rem) clamp(0.25rem, 0.5vw, 0.375rem);
  }

  .toggle-btn,
  .edit-mode-btn {
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

  .nav-label {
    display: block;
  }
}
</style>
