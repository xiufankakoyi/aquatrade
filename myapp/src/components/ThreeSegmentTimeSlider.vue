<template>
  <div class="three-segment-time-slider">
    <div class="mb-4">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm text-slate-300">时间区间分配</span>
        <div class="flex items-center gap-4 text-xs text-slate-400">
          <div class="flex items-center gap-1">
            <div class="w-3 h-3 rounded bg-blue-500/60"></div>
            <span>训练</span>
            <span class="font-mono text-blue-300">{{ trainPercent.toFixed(2) }}%</span>
          </div>
          <div class="flex items-center gap-1">
            <div class="w-3 h-3 rounded bg-yellow-500/60"></div>
            <span>验证</span>
            <span class="font-mono text-yellow-300">{{ valPercent.toFixed(2) }}%</span>
          </div>
          <div class="flex items-center gap-1">
            <div class="w-3 h-3 rounded bg-green-500/60"></div>
            <span>测试</span>
            <span class="font-mono text-green-300">{{ testPercent.toFixed(2) }}%</span>
          </div>
        </div>
      </div>
      <div class="text-xs text-slate-500 mb-3">
        <span>训练: {{ formatDate(trainStartDate) }} ~ {{ formatDate(trainEndDate) }}</span>
        <span class="mx-2">|</span>
        <span>验证: {{ formatDate(valStartDate) }} ~ {{ formatDate(valEndDate) }}</span>
        <span class="mx-2">|</span>
        <span>测试: {{ formatDate(testStartDate) }} ~ {{ formatDate(testEndDate) }}</span>
      </div>
    </div>
    
    <div class="relative" ref="sliderContainer">
      <!-- 背景轨道 -->
      <div 
        ref="sliderTrack"
        class="slider-track h-8 rounded-lg"
        :style="{ background: trackBackground }"
      >
        <!-- 训练区间 -->
        <div 
          class="absolute top-0 bottom-0 bg-blue-500/60 rounded-l-lg"
          :style="{ left: '0%', width: `${trainPercent}%` }"
        >
          <div class="absolute inset-0 flex items-center justify-center text-xs font-semibold text-white">
            训练
          </div>
        </div>
        
        <!-- 验证区间 -->
        <div 
          class="absolute top-0 bottom-0 bg-yellow-500/60"
          :style="{ left: `${trainPercent}%`, width: `${valPercent}%` }"
        >
          <div class="absolute inset-0 flex items-center justify-center text-xs font-semibold text-white">
            验证
          </div>
        </div>
        
        <!-- 测试区间 -->
        <div 
          class="absolute top-0 bottom-0 bg-green-500/60 rounded-r-lg"
          :style="{ left: `${trainPercent + valPercent}%`, width: `${Math.min(testPercent, 100 - trainPercent - valPercent)}%` }"
        >
          <div class="absolute inset-0 flex items-center justify-center text-xs font-semibold text-white">
            测试
          </div>
        </div>
        
        <!-- 分割节点1：训练/验证 -->
        <div
          class="absolute top-0 bottom-0 w-1 bg-white cursor-col-resize z-10 hover:w-2 transition-all"
          :style="{ left: `${trainPercent}%`, transform: 'translateX(-50%)' }"
          @mousedown.stop="startDrag('trainVal', $event)"
          @touchstart.stop="startDrag('trainVal', $event)"
        >
          <div class="absolute top-full mt-1 left-1/2 transform -translate-x-1/2 text-[10px] text-slate-400 whitespace-nowrap">
            {{ formatDate(trainEndDate) }}
          </div>
        </div>
        
        <!-- 分割节点2：验证/测试 -->
        <div
          class="absolute top-0 bottom-0 w-1 bg-white cursor-col-resize z-10 hover:w-2 transition-all"
          :style="{ left: `${trainPercent + valPercent}%`, transform: 'translateX(-50%)' }"
          @mousedown.stop="startDrag('valTest', $event)"
          @touchstart.stop="startDrag('valTest', $event)"
        >
          <div class="absolute top-full mt-1 left-1/2 transform -translate-x-1/2 text-[10px] text-slate-400 whitespace-nowrap">
            {{ formatDate(valEndDate) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';

interface Props {
  startDate: string;
  endDate: string;
  trainStartDate: string;
  trainEndDate: string;
  valStartDate: string;
  valEndDate: string;
  testStartDate: string;
  testEndDate: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'update:trainStartDate': [value: string];
  'update:trainEndDate': [value: string];
  'update:valStartDate': [value: string];
  'update:valEndDate': [value: string];
  'update:testStartDate': [value: string];
  'update:testEndDate': [value: string];
}>();

const sliderContainer = ref<HTMLElement | null>(null);
const sliderTrack = ref<HTMLElement | null>(null);
const dragging = ref<'trainVal' | 'valTest' | null>(null);

// 计算百分比
const totalDays = computed(() => {
  const start = new Date(props.startDate + 'T00:00:00').getTime();
  const end = new Date(props.endDate + 'T00:00:00').getTime();
  return Math.max(1, Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1);
});

const trainDays = computed(() => {
  const start = new Date(props.trainStartDate + 'T00:00:00').getTime();
  const end = new Date(props.trainEndDate + 'T00:00:00').getTime();
  return Math.max(0, Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1);
});

const valDays = computed(() => {
  const start = new Date(props.valStartDate + 'T00:00:00').getTime();
  const end = new Date(props.valEndDate + 'T00:00:00').getTime();
  return Math.max(0, Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1);
});

const testDays = computed(() => {
  const start = new Date(props.testStartDate + 'T00:00:00').getTime();
  const end = new Date(props.testEndDate + 'T00:00:00').getTime();
  return Math.max(0, Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1);
});

const trainPercent = computed(() => {
  if (totalDays.value <= 0) return 33.33;
  const percent = (trainDays.value / totalDays.value) * 100;
  // 确保不超过100%，并保留两位小数
  return Math.min(100, Math.max(0, Number(percent.toFixed(2))));
});

const valPercent = computed(() => {
  if (totalDays.value <= 0) return 33.33;
  const percent = (valDays.value / totalDays.value) * 100;
  // 确保不超过100%，并保留两位小数
  return Math.min(100, Math.max(0, Number(percent.toFixed(2))));
});

const testPercent = computed(() => {
  if (totalDays.value <= 0) return 33.33;
  const percent = (testDays.value / totalDays.value) * 100;
  // 确保不超过100%，并保留两位小数
  return Math.min(100, Math.max(0, Number(percent.toFixed(2))));
});

const trackBackground = computed(() => {
  return `linear-gradient(to right, 
    rgba(59, 130, 246, 0.2) 0%, 
    rgba(59, 130, 246, 0.2) ${trainPercent.value}%, 
    rgba(234, 179, 8, 0.2) ${trainPercent.value}%, 
    rgba(234, 179, 8, 0.2) ${trainPercent.value + valPercent.value}%, 
    rgba(34, 197, 94, 0.2) ${trainPercent.value + valPercent.value}%, 
    rgba(34, 197, 94, 0.2) 100%)`;
});

// 格式化日期
function formatDate(dateStr: string): string {
  if (!dateStr) return '--';
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

// 根据百分比计算日期
function getDateFromPercent(percent: number): string {
  const start = new Date(props.startDate + 'T00:00:00').getTime();
  const days = Math.floor((percent / 100) * totalDays.value);
  const targetDate = new Date(start + days * 24 * 60 * 60 * 1000);
  const year = targetDate.getFullYear();
  const month = String(targetDate.getMonth() + 1).padStart(2, '0');
  const day = String(targetDate.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// 根据日期计算百分比
function getPercentFromDate(dateStr: string): number {
  const start = new Date(props.startDate + 'T00:00:00').getTime();
  const target = new Date(dateStr + 'T00:00:00').getTime();
  const days = Math.ceil((target - start) / (1000 * 60 * 60 * 24));
  return Math.max(0, Math.min(100, (days / totalDays.value) * 100));
}

const startDrag = (handle: 'trainVal' | 'valTest', event: MouseEvent | TouchEvent) => {
  dragging.value = handle;
  event.preventDefault();
  event.stopPropagation();
};

const handleMouseMove = (event: MouseEvent | TouchEvent) => {
  if (!dragging.value || !sliderTrack.value) return;
  
  const clientX = 'touches' in event ? event.touches[0].clientX : event.clientX;
  const rect = sliderTrack.value.getBoundingClientRect();
  const percentage = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
  
  if (dragging.value === 'trainVal') {
    // 限制：训练区间至少10%，验证区间至少10%
    const newTrainPercent = Math.max(10, Math.min(percentage, 80));
    const newValPercent = Math.max(10, Math.min(100 - newTrainPercent - testPercent.value, 80));
    const newTestPercent = 100 - newTrainPercent - newValPercent;
    
    const trainEnd = getDateFromPercent(newTrainPercent);
    const valStart = trainEnd;
    const valEnd = getDateFromPercent(newTrainPercent + newValPercent);
    const testStart = valEnd;
    
    // 确保trainStartDate始终等于startDate
    emit('update:trainStartDate', props.startDate);
    emit('update:trainEndDate', trainEnd);
    emit('update:valStartDate', valStart);
    emit('update:valEndDate', valEnd);
    emit('update:testStartDate', testStart);
    emit('update:testEndDate', props.endDate);
  } else if (dragging.value === 'valTest') {
    // 限制：验证区间至少10%，测试区间至少10%
    const newValPercent = Math.max(10, Math.min(percentage - trainPercent.value, 80));
    const newTestPercent = Math.max(10, 100 - trainPercent.value - newValPercent);
    const adjustedValPercent = 100 - trainPercent.value - newTestPercent;
    
    const valEnd = getDateFromPercent(trainPercent.value + adjustedValPercent);
    const testStart = valEnd;
    
    emit('update:valEndDate', valEnd);
    emit('update:testStartDate', testStart);
    emit('update:testEndDate', props.endDate);
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
.three-segment-time-slider {
  width: 100%;
}

.slider-track {
  position: relative;
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.3);
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
}
</style>


