<template>
  <div class="range-slider-container">
    <div v-if="label || true" class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <span v-if="label" class="text-sm font-medium text-slate-200">{{ label }}</span>
        <span v-if="locked" class="text-xs text-slate-500">🔒</span>
      </div>
      <div class="flex items-center gap-2 text-xs font-mono">
        <span class="px-3 py-1.5 rounded-lg bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-semibold shadow-sm">
          {{ formatValue(minValue) }}{{ unit }}
        </span>
        <span class="text-slate-500 font-bold">——</span>
        <span class="px-3 py-1.5 rounded-lg bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-semibold shadow-sm">
          {{ formatValue(maxValue) }}{{ unit }}
        </span>
      </div>
    </div>
    
    <div class="relative" ref="sliderContainer">
      <!-- 背景轨道 -->
      <div 
        ref="sliderTrack"
        class="slider-track"
        :class="{ 'slider-track-locked': locked }"
        :style="{ background: trackBackground }"
        @mousedown="handleTrackClick"
        @touchstart="handleTrackClick"
      >
        <!-- 最小值滑块 -->
        <div
          class="slider-handle"
          :class="{ 'slider-handle-active': dragging === 'min' }"
          :style="{ left: `${minPercent}%` }"
          @mousedown.stop="startDrag('min', $event)"
          @touchstart.stop="startDrag('min', $event)"
        >
          <div class="slider-handle-tooltip">
            {{ formatValue(minValue) }}{{ unit }}
          </div>
        </div>
        
        <!-- 最大值滑块 -->
        <div
          class="slider-handle"
          :class="{ 'slider-handle-active': dragging === 'max' }"
          :style="{ left: `${maxPercent}%` }"
          @mousedown.stop="startDrag('max', $event)"
          @touchstart.stop="startDrag('max', $event)"
        >
          <div class="slider-handle-tooltip">
            {{ formatValue(maxValue) }}{{ unit }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';

interface Props {
  label: string;
  unit?: string;
  absoluteMin: number;
  absoluteMax: number;
  minValue: number;
  maxValue: number;
  step?: number;
  locked?: boolean;
  trackColor?: string;
  activeColor?: string;
  useLogScale?: boolean; // 是否使用对数轴
}

const props = withDefaults(defineProps<Props>(), {
  unit: '',
  step: 0.01,
  locked: false,
  trackColor: 'rgba(148, 163, 184, 0.2)',
  activeColor: 'rgba(99, 102, 241, 0.5)',
  useLogScale: false,
});

const emit = defineEmits<{
  'update:minValue': [value: number];
  'update:maxValue': [value: number];
}>();

const dragging = ref<'min' | 'max' | null>(null);
const sliderTrack = ref<HTMLElement | null>(null);
const sliderContainer = ref<HTMLElement | null>(null);

// 格式化值，根据步长判断是否为整数
const formatValue = (value: number): string => {
  // 如果步长 >= 1，认为是整数参数
  if (props.step && props.step >= 1) {
    return Math.round(value).toString();
  }
  // 如果步长 < 1，显示小数，但最多2位
  if (props.step && props.step < 1) {
    // 如果步长很小（如0.01），显示2位小数
    if (props.step <= 0.01) {
      return value.toFixed(2);
    }
    // 如果步长较大（如0.1），显示1位小数
    return value.toFixed(1);
  }
  // 默认显示2位小数
  return value.toFixed(2);
};

// 对数轴转换函数
const logTransform = (value: number, min: number, max: number): number => {
  if (min <= 0 || max <= 0 || value <= 0) return 0;
  const logMin = Math.log10(min);
  const logMax = Math.log10(max);
  const logValue = Math.log10(value);
  return (logValue - logMin) / (logMax - logMin);
};

const logInverse = (percent: number, min: number, max: number): number => {
  if (min <= 0 || max <= 0) return min;
  const logMin = Math.log10(min);
  const logMax = Math.log10(max);
  const logValue = logMin + percent * (logMax - logMin);
  return Math.pow(10, logValue);
};

const minPercent = computed(() => {
  if (props.useLogScale) {
    return logTransform(props.minValue, props.absoluteMin, props.absoluteMax) * 100;
  }
  const range = props.absoluteMax - props.absoluteMin;
  if (range <= 0) return 0;
  return ((props.minValue - props.absoluteMin) / range) * 100;
});

const maxPercent = computed(() => {
  if (props.useLogScale) {
    return logTransform(props.maxValue, props.absoluteMin, props.absoluteMax) * 100;
  }
  const range = props.absoluteMax - props.absoluteMin;
  if (range <= 0) return 100;
  return ((props.maxValue - props.absoluteMin) / range) * 100;
});

const trackBackground = computed(() => {
  const range = props.absoluteMax - props.absoluteMin;
  if (range <= 0) return props.trackColor;
  return `linear-gradient(to right, 
    ${props.trackColor} 0%, 
    ${props.trackColor} ${minPercent.value}%, 
    ${props.activeColor} ${minPercent.value}%, 
    ${props.activeColor} ${maxPercent.value}%, 
    ${props.trackColor} ${maxPercent.value}%, 
    ${props.trackColor} 100%)`;
});

const getValueFromPosition = (clientX: number): number => {
  if (!sliderTrack.value) return props.minValue;
  
  const rect = sliderTrack.value.getBoundingClientRect();
  const percentage = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  
  let value: number;
  if (props.useLogScale) {
    // 对数轴：先转换到线性空间，再取对数
    value = logInverse(percentage, props.absoluteMin, props.absoluteMax);
  } else {
  const range = props.absoluteMax - props.absoluteMin;
  if (range <= 0) return props.absoluteMin;
    value = props.absoluteMin + percentage * range;
  }
  
  // 对齐到步长（对数轴也需要对齐）
  const stepped = Math.round(value / props.step) * props.step;
  return Math.max(props.absoluteMin, Math.min(props.absoluteMax, stepped));
};

const startDrag = (handle: 'min' | 'max', event: MouseEvent | TouchEvent) => {
  if (props.locked) {
    event.preventDefault();
    event.stopPropagation();
    return;
  }
  
  dragging.value = handle;
  event.preventDefault();
  
  const clientX = 'touches' in event ? event.touches[0].clientX : event.clientX;
  const value = getValueFromPosition(clientX);
  
  if (handle === 'min') {
    const newMin = Math.min(value, props.maxValue - props.step);
    emit('update:minValue', newMin);
  } else {
    const newMax = Math.max(value, props.minValue + props.step);
    emit('update:maxValue', newMax);
  }
};

const handleTrackClick = (event: MouseEvent | TouchEvent) => {
  if (props.locked) {
    event.preventDefault();
    event.stopPropagation();
    return;
  }
  if (dragging.value) return;
  
  const clientX = 'touches' in event ? event.touches[0].clientX : event.clientX;
  const value = getValueFromPosition(clientX);
  
  // 判断点击位置更接近哪个滑块
  const distToMin = Math.abs(value - props.minValue);
  const distToMax = Math.abs(value - props.maxValue);
  
  if (distToMin < distToMax) {
    const newMin = Math.min(value, props.maxValue - props.step);
    emit('update:minValue', newMin);
  } else {
    const newMax = Math.max(value, props.minValue + props.step);
    emit('update:maxValue', newMax);
  }
};

const handleMouseMove = (event: MouseEvent | TouchEvent) => {
  if (!dragging.value) return;
  
  const clientX = 'touches' in event ? event.touches[0].clientX : event.clientX;
  const value = getValueFromPosition(clientX);
  
  if (dragging.value === 'min') {
    const newMin = Math.min(value, props.maxValue - props.step);
    emit('update:minValue', newMin);
  } else {
    const newMax = Math.max(value, props.minValue + props.step);
    emit('update:maxValue', newMax);
  }
};

const handleMouseUp = () => {
  dragging.value = null;
};

onMounted(() => {
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
  document.addEventListener('touchmove', handleMouseMove);
  document.addEventListener('touchend', handleMouseUp);
});

onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
  document.removeEventListener('touchmove', handleMouseMove);
  document.removeEventListener('touchend', handleMouseUp);
});
</script>

<style scoped>
.range-slider-container {
  width: 100%;
}

.slider-track {
  position: relative;
  width: 100%;
  height: 10px;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
}

.slider-track:hover:not(.slider-track-locked) {
  height: 12px;
}

.slider-track-locked {
  cursor: not-allowed;
  opacity: 0.6;
}

.slider-handle {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 22px;
  height: 22px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border: 3px solid rgba(255, 255, 255, 0.95);
  border-radius: 50%;
  cursor: grab;
  transition: all 0.2s ease;
  z-index: 2;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4), 0 0 0 2px rgba(99, 102, 241, 0.1);
}

.slider-track-locked .slider-handle {
  cursor: not-allowed;
  opacity: 0.5;
  background: linear-gradient(135deg, #475569 0%, #64748b 100%);
}

.slider-handle:hover {
  transform: translate(-50%, -50%) scale(1.2);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.6);
}

.slider-handle-active {
  transform: translate(-50%, -50%) scale(1.3);
  cursor: grabbing;
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.8);
}

.slider-handle-tooltip {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-bottom: 10px;
  padding: 6px 10px;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.98) 0%, rgba(30, 41, 59, 0.98) 100%);
  border: 1px solid rgba(99, 102, 241, 0.6);
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
  color: #e2e8f0;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.slider-handle:hover .slider-handle-tooltip,
.slider-handle-active .slider-handle-tooltip {
  opacity: 1;
}

.slider-handle-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: rgba(99, 102, 241, 0.6);
  filter: drop-shadow(0 2px 2px rgba(0, 0, 0, 0.2));
}
</style>