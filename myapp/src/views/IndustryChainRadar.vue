<template>
  <main class="industry-chain-page">
    <IndustryHeader
      :chain="currentChain"
      :summary="summary"
      :loading="loading"
      :using-fallback="usingFallback"
    />

    <DataSourceStatusBar
      :status="dataSourceStatus"
      :loading="statusLoading"
      :structure-loaded="Boolean(graphData?.nodes?.length)"
      :using-fallback="usingFallback"
    />

    <IndustryToolbar
      v-model:keyword="searchKeyword"
      :chains="chains"
      :current-chain-id="currentChainId"
      :message="searchMessage"
      @select-chain="selectChain"
      @search="runSearch"
    />

    <div class="main-layout">
      <section class="canvas-area">
        <IndustryChainCanvas
          :graph-data="graphData"
          :loading="loading"
          :selected-node-id="selectedNode?.id || ''"
          @select-node="selectNode"
        />
        <IndustryLayerLegend :layers="graphData?.layers || []" />
      </section>

      <IndustryNodePanel
        :node="selectedNode"
        :node-detail="nodeDetail"
        :loading="nodeLoading"
      />
    </div>

    <IndustryStockTable
      :stocks="nodeStocks"
      :message="stockMessage"
      :loading="stockLoading"
      :include-candidates="includeCandidates"
      :verified-only="verifiedOnly"
      :sort-by="sortBy"
      @update:include-candidates="includeCandidates = $event"
      @update:verified-only="verifiedOnly = $event"
      @update:sort-by="sortBy = $event; loadNodeStocks()"
    />

    <p class="boundary">本页仅展示本地维护的产业链结构、证据和市场统计，不构成买入、卖出、仓位、止盈或止损建议。</p>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import type {
  ChainGraphData,
  ChainInfo,
  ChainNode,
  ChainStock,
  DataSourceStatus,
  NodeDetail,
} from '@/api/industryChain';
import {
  getChainGraph,
  getDataSourcesStatus,
  getNodeDetail,
  getNodeStocks,
  listChains,
} from '@/api/industryChain';
import {
  createFallbackNodeDetail,
  FALLBACK_CHAIN,
  FALLBACK_GRAPH,
} from '@/api/industryChainFallback';
import IndustryChainCanvas from '@/components/industry/IndustryChainCanvas.vue';
import IndustryHeader from '@/components/industry/IndustryHeader.vue';
import IndustryLayerLegend from '@/components/industry/IndustryLayerLegend.vue';
import IndustryNodePanel from '@/components/industry/IndustryNodePanel.vue';
import IndustryStockTable from '@/components/industry/IndustryStockTable.vue';
import IndustryToolbar from '@/components/industry/IndustryToolbar.vue';
import DataSourceStatusBar from '@/components/industry/DataSourceStatusBar.vue';

const DEFAULT_CHAIN_ID = 'optical_communication';
const DEFAULT_NODE_IDS = ['optical_module', 'optical_communication'];
const EMPTY_STOCK_MESSAGE = '暂无本地公司证据。请维护 knowledge/stock_concept_mapping.csv 或 knowledge/data_sources/company_evidence.csv 后查看映射。';

const chains = ref<ChainInfo[]>([]);
const currentChainId = ref(DEFAULT_CHAIN_ID);
const currentChain = ref<ChainInfo | null>(FALLBACK_CHAIN);
const graphData = ref<ChainGraphData | null>(null);
const summary = ref<ChainGraphData['summary'] | null>(null);
const selectedNode = ref<ChainNode | null>(null);
const nodeDetail = ref<NodeDetail | null>(null);
const nodeStocks = ref<ChainStock[]>([]);
const stockMessage = ref(EMPTY_STOCK_MESSAGE);
const loading = ref(false);
const nodeLoading = ref(false);
const stockLoading = ref(false);
const searchKeyword = ref('');
const searchMessage = ref('');
const usingFallback = ref(false);

const dataSourceStatus = ref<DataSourceStatus | null>(null);
const statusLoading = ref(false);

const includeCandidates = ref(true);
const verifiedOnly = ref(false);
const sortBy = ref('final_score');

onMounted(async () => {
  await loadChains();
  await selectChain(DEFAULT_CHAIN_ID);
  loadDataSourceStatus();
});

async function loadChains() {
  try {
    const remoteChains = await listChains();
    chains.value = ensureFallbackChain(remoteChains);
  } catch (err) {
    console.error('加载产业链列表失败:', err);
    chains.value = [FALLBACK_CHAIN];
  }
}

function ensureFallbackChain(remoteChains: ChainInfo[]): ChainInfo[] {
  if (!remoteChains.length) return [FALLBACK_CHAIN];
  if (remoteChains.some((item) => item.chain_id === DEFAULT_CHAIN_ID)) return remoteChains;
  return [FALLBACK_CHAIN, ...remoteChains];
}

async function loadDataSourceStatus() {
  statusLoading.value = true;
  try {
    dataSourceStatus.value = await getDataSourcesStatus();
  } catch (err) {
    console.error('加载数据源状态失败:', err);
    dataSourceStatus.value = null;
  } finally {
    statusLoading.value = false;
  }
}

async function selectChain(chainId: string) {
  currentChainId.value = chainId || DEFAULT_CHAIN_ID;
  currentChain.value = chains.value.find((c) => c.chain_id === currentChainId.value) || (currentChainId.value === DEFAULT_CHAIN_ID ? FALLBACK_CHAIN : null);
  selectedNode.value = null;
  nodeDetail.value = null;
  nodeStocks.value = [];
  nodeLoading.value = false;
  stockLoading.value = false;
  stockMessage.value = EMPTY_STOCK_MESSAGE;
  searchMessage.value = '';
  usingFallback.value = false;

  loading.value = true;
  try {
    const data = await getChainGraph(currentChainId.value);
    if (!data?.nodes?.length) {
      throw new Error('empty graph');
    }
    applyGraph(data, false);
  } catch (err) {
    console.error('加载产业链图谱失败:', err);
    if (currentChainId.value === DEFAULT_CHAIN_ID) {
      currentChain.value = FALLBACK_CHAIN;
      applyGraph(FALLBACK_GRAPH, true);
    } else {
      graphData.value = null;
      summary.value = null;
    }
  } finally {
    loading.value = false;
  }
}

function applyGraph(data: ChainGraphData, fallback: boolean) {
  graphData.value = data;
  summary.value = data.summary;
  usingFallback.value = fallback;

  const defaultNode =
    DEFAULT_NODE_IDS.map((id) => data.nodes.find((node) => node.id === id)).find(Boolean) ||
    data.nodes[0] ||
    null;
  if (defaultNode) {
    selectNode(defaultNode);
  }
}

async function selectNode(node: ChainNode) {
  selectedNode.value = node;
  nodeDetail.value = null;
  nodeStocks.value = [];
  stockMessage.value = EMPTY_STOCK_MESSAGE;

  if (!currentChainId.value || !node.id || !graphData.value) return;

  if (usingFallback.value) {
    nodeDetail.value = createFallbackNodeDetail(graphData.value, node);
    nodeLoading.value = false;
    stockLoading.value = false;
    return;
  }

  nodeLoading.value = true;
  try {
    nodeDetail.value = await getNodeDetail(currentChainId.value, node.id);
  } catch (err) {
    console.error('加载节点详情失败:', err);
    nodeDetail.value = createFallbackNodeDetail(graphData.value, node);
  } finally {
    nodeLoading.value = false;
  }

  await loadNodeStocks();
}

async function loadNodeStocks() {
  if (!currentChainId.value || !selectedNode.value?.id) return;
  if (usingFallback.value) {
    nodeStocks.value = [];
    stockMessage.value = EMPTY_STOCK_MESSAGE;
    return;
  }

  stockLoading.value = true;
  try {
    const result = await getNodeStocks(currentChainId.value, selectedNode.value.id, {
      include_candidates: includeCandidates.value,
      verified_only: verifiedOnly.value,
      sort_by: sortBy.value,
    });
    nodeStocks.value = result.rows || [];
    stockMessage.value = nodeStocks.value.length ? '' : (result.message || EMPTY_STOCK_MESSAGE);
  } catch (err) {
    console.error('加载相关公司失败:', err);
    nodeStocks.value = [];
    stockMessage.value = EMPTY_STOCK_MESSAGE;
  } finally {
    stockLoading.value = false;
  }
}

watch([includeCandidates, verifiedOnly], () => {
  loadNodeStocks();
});

function runSearch() {
  const keyword = searchKeyword.value.trim();
  if (!keyword || !graphData.value) return;

  const normalized = keyword.toLowerCase();
  const found = graphData.value.nodes.find((node) => {
    const haystack = [
      node.name,
      node.id,
      ...(node.aliases || []),
      ...(node.keywords || []),
      node.description || '',
    ].join(' ').toLowerCase();
    return haystack.includes(normalized);
  });

  if (found) {
    searchMessage.value = '';
    selectNode(found);
    return;
  }

  searchMessage.value = '未在当前产业链中找到相关节点';
}
</script>

<style scoped>
.industry-chain-page {
  min-height: 100vh;
  padding: 24px;
  background: #05070d;
  color: #e2e8f0;
}

.main-layout {
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(320px, 3fr);
  gap: 16px;
  margin-top: 16px;
  align-items: stretch;
}

.canvas-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 640px;
}

.boundary {
  margin-top: 16px;
  text-align: center;
  color: #64748b;
  font-size: 12px;
}

@media (max-width: 1200px) {
  .main-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .industry-chain-page {
    padding: 16px;
  }
}
</style>
