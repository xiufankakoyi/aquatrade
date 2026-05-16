<template>
  <div class="layer-legend">
    <div class="legend-title">层级</div>
    <div class="legend-items">
      <div v-for="layer in layers" :key="layer.id" class="legend-item">
        <span class="legend-dot" :style="{ background: getLayerColor(layer.id) }"></span>
        <span class="legend-name">{{ layer.name }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChainLayer } from '@/api/industryChain';

interface Props {
  layers: ChainLayer[];
}

defineProps<Props>();

const layerColors: Record<string, string> = {
  upstream: '#FF6B6B',
  component: '#4ECDC4',
  product: '#45B7D1',
  application: '#96CEB4',
};

function getLayerColor(layerId: string): string {
  return layerColors[layerId] || '#94a3b8';
}
</script>

<style scoped>
.layer-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #1e293b;
  border-radius: 6px;
  background: #0f172a;
}

.legend-title {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.legend-items {
  display: flex;
  gap: 16px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-name {
  font-size: 12px;
  color: #94a3b8;
}
</style>
