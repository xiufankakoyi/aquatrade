<template>
  <main class="concept-page">
    <header class="page-header">
      <div>
        <h1>概念研究库</h1>
        <p>展示本地维护的概念定义、产业链和证据，不自动判断公司业务正宗性。</p>
      </div>
    </header>

    <ConceptSearchBox v-model="keyword" :loading="loading" @search="runSearch" />

    <section class="layout">
      <aside class="concept-list">
        <button
          v-for="concept in concepts"
          :key="concept.concept_id"
          type="button"
          :class="{ active: selectedConcept?.concept_id === concept.concept_id }"
          @click="selectConcept(concept)"
        >
          <span>{{ concept.concept_name }}</span>
          <small>{{ concept.aliases.slice(0, 2).join(' / ') }}</small>
        </button>
        <div v-if="concepts.length === 0" class="empty">暂无匹配概念</div>
      </aside>

      <div class="main-stack">
        <ConceptChainGraph :concept="selectedConcept" />
        <div v-if="stocks.length > 0" class="toolbar">
          <button type="button" @click="openPatternForConcept">查看全部相关股票形态</button>
        </div>
        <div class="split">
          <ConceptStockTable :stocks="stocks" @select="selectedStock = $event" @open-pattern="openPattern" />
          <EvidencePanel :stock="selectedStock" />
        </div>
        <p class="boundary">本页仅展示本地证据与市场统计，不构成买入、卖出或仓位建议。</p>
        <p v-if="message" class="message">{{ message }}</p>
        <p v-if="error" class="error">{{ error }}</p>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import type { ConceptInfo, ConceptStock } from '@/api/concept';
import { getConceptStocks, listConcepts, searchConcepts } from '@/api/concept';
import ConceptSearchBox from '@/components/concept/ConceptSearchBox.vue';
import ConceptChainGraph from '@/components/concept/ConceptChainGraph.vue';
import ConceptStockTable from '@/components/concept/ConceptStockTable.vue';
import EvidencePanel from '@/components/concept/EvidencePanel.vue';

const router = useRouter();
const keyword = ref('磷化铟');
const concepts = ref<ConceptInfo[]>([]);
const selectedConcept = ref<ConceptInfo | null>(null);
const stocks = ref<ConceptStock[]>([]);
const selectedStock = ref<ConceptStock | null>(null);
const loading = ref(false);
const error = ref('');
const message = ref('');

onMounted(async () => {
  loading.value = true;
  try {
    concepts.value = await listConcepts();
    const defaultConcept = concepts.value.find((item) => item.concept_name === '磷化铟') || concepts.value[0] || null;
    if (defaultConcept) await selectConcept(defaultConcept);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载概念库失败';
  } finally {
    loading.value = false;
  }
});

async function runSearch(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    concepts.value = await searchConcepts(keyword.value);
    const first = concepts.value[0] || null;
    if (first) {
      await selectConcept(first);
    } else {
      selectedConcept.value = null;
      stocks.value = [];
      selectedStock.value = null;
      message.value = '暂无匹配概念';
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '搜索概念失败';
  } finally {
    loading.value = false;
  }
}

async function selectConcept(concept: ConceptInfo): Promise<void> {
  selectedConcept.value = concept;
  selectedStock.value = null;
  message.value = '';
  try {
    const response = await getConceptStocks(concept.concept_id);
    stocks.value = response.rows;
    message.value = response.message || '';
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载概念映射失败';
  }
}

function openPattern(stock: ConceptStock): void {
  router.push({
    path: '/similarity',
    query: {
      module: 'radar',
      symbols: stock.symbol,
      concept: selectedConcept.value?.concept_name || '',
    },
  });
}

function openPatternForConcept(): void {
  router.push({
    path: '/similarity',
    query: {
      module: 'radar',
      symbols: stocks.value.map((stock) => stock.symbol).join(','),
      concept: selectedConcept.value?.concept_name || '',
    },
  });
}
</script>

<style scoped>
.concept-page {
  min-height: 100vh;
  padding: 24px;
  background: #020617;
  color: #e2e8f0;
}

.page-header {
  margin-bottom: 16px;
}

h1 {
  margin: 0 0 6px;
  color: #f8fafc;
  font-size: 24px;
}

.page-header p,
.boundary {
  margin: 0;
  color: #94a3b8;
  font-size: 13px;
}

.layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 14px;
  margin-top: 14px;
}

.concept-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 500px;
  padding: 12px;
  border: 1px solid #243244;
  border-radius: 8px;
  background: #0b1120;
}

.concept-list button {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border: 1px solid #1f2937;
  border-radius: 6px;
  background: #111827;
  color: #e2e8f0;
  text-align: left;
  cursor: pointer;
}

.concept-list button.active {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
}

.concept-list small {
  color: #64748b;
}

.main-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 14px;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
}

.toolbar button {
  height: 34px;
  padding: 0 12px;
  border: 1px solid #16a34a;
  border-radius: 6px;
  background: rgba(22, 163, 74, 0.12);
  color: #86efac;
  cursor: pointer;
}

.empty,
.message {
  color: #64748b;
}

.error {
  padding: 10px 12px;
  border: 1px solid rgba(239, 68, 68, 0.35);
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
}

@media (max-width: 1120px) {
  .layout,
  .split {
    grid-template-columns: 1fr;
  }

  .concept-list {
    min-height: 0;
  }
}
</style>
