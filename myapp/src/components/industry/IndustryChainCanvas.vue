<template>
  <div class="chain-canvas">
    <div ref="chartRef" class="chart-container"></div>
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner">
        <i class="fas fa-spinner fa-spin"></i>
        <span>加载图谱...</span>
      </div>
    </div>
    <div v-if="!loading && isEmpty" class="empty-state">
      <i class="fas fa-project-diagram"></i>
      <p>暂无产业链结构数据</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue';
import * as echarts from 'echarts';
import type { ChainEdge, ChainGraphData, ChainNode } from '@/api/industryChain';

interface Props {
  graphData: ChainGraphData | null;
  loading: boolean;
  selectedNodeId: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'selectNode', node: ChainNode): void;
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const isEmpty = computed(() => !props.graphData || props.graphData.nodes.length === 0);

const layerColors: Record<string, string> = {
  upstream: '#3dd6a3',
  component: '#4cc9f0',
  product: '#f5b84b',
  application: '#a78bfa',
};

onMounted(() => {
  if (!chartRef.value) return;
  chartInstance = echarts.init(chartRef.value, 'dark');
  chartInstance.on('click', (params: any) => {
    if (params.dataType === 'node' && params.data && !params.data.silent) {
      emit('selectNode', params.data.rawNode as ChainNode);
    }
  });
  window.addEventListener('resize', handleResize);
  renderChart();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
  chartInstance = null;
});

watch(
  () => [props.graphData, props.selectedNodeId],
  () => {
    nextTick(() => renderChart());
  },
  { deep: true }
);

function handleResize() {
  chartInstance?.resize();
}

function renderChart() {
  if (!chartInstance || !props.graphData) return;

  const { nodes, edges, layers } = props.graphData;
  if (!nodes.length) {
    chartInstance.clear();
    return;
  }

  const sortedLayers = [...layers].sort((a, b) => a.order - b.order);
  const layerOrderMap = Object.fromEntries(sortedLayers.map((layer, index) => [layer.id, index]));
  const layoutNodes = buildLayoutNodes(nodes, sortedLayers);
  const nodeById = new Map(layoutNodes.map((node) => [node.id, node]));

  const chartNodes = layoutNodes.map((node) => {
    const color = layerColors[node.layer] || '#94a3b8';
    const isSelected = node.id === props.selectedNodeId;
    const isDemo = Boolean(node.demo_highlight || node.hot_score_source === '示例热度');
    return {
      id: node.id,
      name: node.name,
      rawNode: node,
      x: node.x,
      y: node.y,
      fixed: true,
      symbol: 'roundRect',
      symbolSize: [148, 52],
      value: node.hot_score || node.importance || 1,
      itemStyle: {
        color: isDemo ? brighten(color) : 'rgba(15, 23, 42, 0.98)',
        borderColor: isSelected ? '#f8fafc' : color,
        borderWidth: isSelected ? 3 : 1.5,
        shadowBlur: isSelected || isDemo ? 18 : 8,
        shadowColor: isDemo ? color : 'rgba(15, 23, 42, 0.5)',
      },
      label: {
        show: true,
        position: 'inside',
        color: '#f8fafc',
        fontSize: 13,
        fontWeight: 650,
        lineHeight: 17,
        formatter: () => node.hot_score_source === '示例热度' ? `${node.name}\n示例热度` : node.name,
      },
    };
  });

  const chartEdges = normalizeEdges(edges, nodeById, layerOrderMap);

  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    animationDurationUpdate: 240,
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.96)',
      borderColor: '#334155',
      borderWidth: 1,
      textStyle: {
        color: '#e2e8f0',
        fontSize: 12,
      },
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const d = params.data.rawNode as ChainNode;
          const hotScore = d.hot_score_source === '示例热度'
            ? `${Number(d.hot_score || 0).toFixed(2)}（示例热度）`
            : d.hot_score > 0
              ? Number(d.hot_score).toFixed(2)
              : '暂无';
          const stockCount = d.stock_count || 0;
          return `
            <div style="padding:8px;max-width:260px;">
              <div style="font-weight:700;font-size:14px;margin-bottom:5px;color:#f8fafc;">${escapeHtml(d.name)}</div>
              <div style="color:#94a3b8;font-size:12px;margin-bottom:4px;">${escapeHtml(d.layer_name || d.layer)} / ${escapeHtml(d.type || '节点')}</div>
              <div style="color:#cbd5e1;font-size:12px;line-height:1.45;">${escapeHtml(d.description || '暂无描述')}</div>
              <div style="margin-top:6px;color:#94a3b8;font-size:11px;">热度：${hotScore}</div>
              <div style="color:#94a3b8;font-size:11px;">相关股票数量：${stockCount}</div>
            </div>
          `;
        }
        if (params.dataType === 'edge') {
          const d = params.data;
          return `
            <div style="padding:8px;max-width:240px;">
              <div style="font-weight:700;color:#f8fafc;margin-bottom:4px;">${escapeHtml(d.labelText || d.relation || '关联')}</div>
              <div style="color:#94a3b8;font-size:12px;line-height:1.45;">${escapeHtml(d.description || '')}</div>
            </div>
          `;
        }
        return '';
      },
    },
    graphic: buildLayerTitles(sortedLayers),
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        left: 28,
        right: 28,
        top: 54,
        bottom: 28,
        data: chartNodes,
        links: chartEdges,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 10],
        lineStyle: {
          color: '#64748b',
          width: 1.6,
          opacity: 0.78,
          curveness: 0.08,
        },
        edgeLabel: {
          show: false,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: {
            width: 3,
            opacity: 1,
          },
        },
      } as any,
    ],
  };

  chartInstance.setOption(option, true);
  chartInstance.resize();
}

function buildLayoutNodes(nodes: ChainNode[], layers: { id: string; order: number }[]): ChainNode[] {
  const horizontalGap = 330;
  const verticalGap = 78;
  const layerStartX = 90;
  const layerOrderMap = Object.fromEntries(layers.map((layer, index) => [layer.id, index]));
  const grouped = new Map<string, ChainNode[]>();

  for (const node of nodes) {
    const group = grouped.get(node.layer) || [];
    group.push(node);
    grouped.set(node.layer, group);
  }

  for (const group of grouped.values()) {
    group.sort((a, b) => (a.order || 0) - (b.order || 0));
  }

  return nodes.map((node) => {
    const group = grouped.get(node.layer) || [];
    const index = Math.max(group.findIndex((item) => item.id === node.id), 0);
    const layerIndex = layerOrderMap[node.layer] ?? 0;
    const yOffset = Math.max(0, (10 - group.length) * verticalGap * 0.18);
    return {
      ...node,
      x: layerStartX + layerIndex * horizontalGap,
      y: 70 + yOffset + index * verticalGap,
      fixed: true,
    };
  });
}

function normalizeEdges(
  edges: ChainEdge[],
  nodeById: Map<string, ChainNode>,
  layerOrderMap: Record<string, number>
) {
  return edges
    .filter((edge) => nodeById.has(edge.source) && nodeById.has(edge.target))
    .map((edge) => {
      const sourceNode = nodeById.get(edge.source)!;
      const targetNode = nodeById.get(edge.target)!;
      const sourceLayerOrder = layerOrderMap[sourceNode.layer] ?? 0;
      const targetLayerOrder = layerOrderMap[targetNode.layer] ?? 0;
      const shouldReverse = sourceLayerOrder > targetLayerOrder;
      const labelText = typeof edge.label?.formatter === 'string' ? edge.label.formatter : edge.relation;
      return {
        source: shouldReverse ? edge.target : edge.source,
        target: shouldReverse ? edge.source : edge.target,
        relation: edge.relation,
        labelText,
        description: edge.description,
        lineStyle: {
          color: shouldReverse ? '#475569' : '#64748b',
          width: 1.6,
          curveness: sourceLayerOrder === targetLayerOrder ? 0.16 : 0.08,
        },
      };
    });
}

function buildLayerTitles(layers: { id: string; name: string }[]) {
  const lefts = ['8%', '33%', '58%', '82%'];
  return layers.map((layer, index) => ({
    type: 'group',
    left: lefts[index] || `${8 + index * 24}%`,
    top: 12,
    children: [
      {
        type: 'rect',
        shape: { width: 118, height: 28, r: 6 },
        style: {
          fill: 'rgba(15, 23, 42, 0.96)',
          stroke: layerColors[layer.id] || '#94a3b8',
          lineWidth: 1,
        },
      },
      {
        type: 'text',
        left: 12,
        top: 7,
        style: {
          text: layer.name,
          fill: '#e2e8f0',
          font: '12px sans-serif',
          fontWeight: 700,
        },
      },
    ],
  }));
}

function brighten(color: string): string {
  const palette: Record<string, string> = {
    '#3dd6a3': '#0f766e',
    '#4cc9f0': '#0369a1',
    '#f5b84b': '#b45309',
    '#a78bfa': '#6d28d9',
  };
  return palette[color] || color;
}

function escapeHtml(value: string): string {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
</script>

<style scoped>
.chain-canvas {
  position: relative;
  flex: 1;
  min-height: 590px;
  border: 1px solid rgba(71, 85, 105, 0.45);
  border-radius: 8px;
  background:
    linear-gradient(rgba(148, 163, 184, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.045) 1px, transparent 1px),
    #0b1120;
  background-size: 28px 28px;
  overflow: hidden;
}

.chart-container {
  width: 100%;
  height: 100%;
  min-height: 590px;
}

.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(2, 6, 23, 0.82);
}

.loading-spinner {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 14px;
}

.empty-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #64748b;
  font-size: 14px;
}
</style>
