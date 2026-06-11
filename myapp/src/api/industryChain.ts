import service from './index';

export interface ChainInfo {
  chain_id: string;
  name: string;
  aliases: string[];
  description: string;
  node_count: number;
  source?: string;
  is_fallback?: boolean;
}

export interface ChainNode {
  id: string;
  name: string;
  type: string;
  layer: string;
  layer_name: string;
  order: number;
  aliases?: string[];
  keywords?: string[];
  description?: string;
  x: number;
  y: number;
  fixed: boolean;
  importance: number;
  hot_score: number;
  hot_score_source?: string;
  market_strength: string;
  stock_count: number;
  candidate_count: number;
  verified_stock_count: number;
  candidate_stock_count: number;
  limit_up_count: number;
  avg_return_1d: number;
  avg_pct_chg: number;
  avg_return_5d: number;
  total_amount: number;
  main_net_inflow?: number;
  updated_at?: string;
  provider_summary?: string;
  symbolSize: number | [number, number];
  itemStyle: Record<string, any>;
  label: Record<string, any>;
  is_fallback?: boolean;
  demo_highlight?: boolean;
}

export interface ChainEdge {
  source: string;
  target: string;
  relation: string;
  label: Record<string, any>;
  lineStyle: Record<string, any>;
  description: string;
}

export interface ChainLayer {
  id: string;
  name: string;
  order: number;
}

export interface ChainSummary {
  chain_id: string;
  chain_name: string;
  hot_score: number;
  market_strength: string;
  top_node: string;
  top_node_name: string;
  limit_up_count: number;
  turnover_change: number;
  node_count: number;
  stock_count: number;
  updated_at?: string;
}

export interface ChainGraphData {
  nodes: ChainNode[];
  edges: ChainEdge[];
  layers: ChainLayer[];
  summary: ChainSummary;
  source?: string;
  is_fallback?: boolean;
}

export interface NodeDetail {
  node: {
    id: string;
    name: string;
    type: string;
    layer: string;
    layer_name: string;
    order: number;
    aliases: string[];
    keywords: string[];
    description: string;
    importance: number;
  };
  upstream: { id: string; name: string; type: string }[];
  downstream: { id: string; name: string; type: string }[];
  metrics: Record<string, any>;
  stock_count: number;
  stocks: ChainStock[];
}

export interface ChainStock {
  chain_id: string;
  node_id: string;
  symbol: string;
  stock_name: string;
  chain_position: string;
  source: string;
  data_source: string;
  source_concept_name: string;
  matched_board_name: string;
  matched_keyword: string;
  candidate_source: string;
  provider: string;
  is_verified: boolean;
  is_candidate: boolean;
  is_manual_override: boolean;
  flag_label: string;
  relevance_score: number;
  purity_score: number;
  evidence_score: number;
  market_confirm_score: number;
  final_score: number;
  system_relevance_score: number;
  source_confidence: number;
  auto_relevance_score: number;
  evidence_type: string;
  evidence_text: string;
  evidence_source: string;
  updated_at: string;
  pct_chg: number | null;
  return_5d: number | null;
  amount: number | null;
  amount_change_ratio: number | null;
  turnover_rate?: number | null;
  volume_ratio?: number | null;
  limit_status: string | null;
  is_limit_up: boolean;
  consecutive_limit_count: number;
  limit_up_reason: string;
  main_net_inflow: number | null;
  market_provider?: string;
  fund_flow_provider?: string;
  pattern_signal: string | null;
}

export interface NodeStocksResponse {
  rows: ChainStock[];
  verified_stocks: ChainStock[];
  candidate_stocks: ChainStock[];
  evidence_summary: {
    evidence_count: number;
    verified_count: number;
    evidence_types: string[];
    latest_update: string | null;
  };
  market_metrics: Record<string, any>;
  message?: string;
}

export interface DataSourceStatus {
  providers: Record<string, Record<string, any>>;
  last_sync: string | null;
  parquet_files: Record<string, boolean>;
  parquet_row_counts?: Record<string, number>;
  recent_source_log?: Record<string, any>[];
  auto_update_scheduler?: Record<string, any>;
  empty_hint?: string;
}

export interface IndustryChainDebug {
  project_root: string;
  knowledge_path: string;
  industry_chain_files: string[];
  loaded_chains: string[];
  optical_communication_exists: boolean;
  node_count: number;
  edge_count: number;
  stock_mapping_count: number;
}

export interface SearchResult {
  chains: { chain_id: string; name: string; aliases: string[]; description: string }[];
  nodes: {
    chain_id: string;
    chain_name: string;
    node_id: string;
    node_name: string;
    type: string;
    layer: string;
    layer_name: string;
    aliases: string[];
    keywords: string[];
    description: string;
  }[];
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
  research_boundary?: string;
}

export async function listChains(): Promise<ChainInfo[]> {
  const response = await service.get<ApiResponse<ChainInfo[]>>('/api/industry-chain/chains');
  return response.data.data;
}

export async function getChainGraph(chainId: string, tradeDate?: string): Promise<ChainGraphData> {
  const params: Record<string, string> = { chain_id: chainId };
  if (tradeDate) params.trade_date = tradeDate;
  const response = await service.get<ApiResponse<ChainGraphData>>('/api/industry-chain/graph', { params });
  return response.data.data;
}

export async function getNodeDetail(chainId: string, nodeId: string): Promise<NodeDetail> {
  const response = await service.get<ApiResponse<NodeDetail>>(`/api/industry-chain/node/${encodeURIComponent(nodeId)}`, {
    params: { chain_id: chainId },
  });
  return response.data.data;
}

export async function getNodeStocks(
  chainId: string,
  nodeId: string,
  options?: {
    include_candidates?: boolean;
    verified_only?: boolean;
    sort_by?: string;
  }
): Promise<NodeStocksResponse> {
  const params: Record<string, string> = { chain_id: chainId };
  if (options?.include_candidates !== undefined) params.include_candidates = String(options.include_candidates);
  if (options?.verified_only !== undefined) params.verified_only = String(options.verified_only);
  if (options?.sort_by) params.sort_by = options.sort_by;
  const response = await service.get<ApiResponse<NodeStocksResponse>>(
    `/api/industry-chain/node/${encodeURIComponent(nodeId)}/stocks`,
    { params }
  );
  return response.data.data;
}

export async function searchIndustryChain(q: string): Promise<SearchResult> {
  const response = await service.get<ApiResponse<SearchResult>>('/api/industry-chain/search', { params: { q } });
  return response.data.data;
}

export async function getDataSourcesStatus(): Promise<DataSourceStatus> {
  const response = await service.get<ApiResponse<DataSourceStatus>>('/api/industry-chain/data-sources/status');
  return response.data.data;
}

export async function getIndustryChainDebug(): Promise<IndustryChainDebug> {
  const response = await service.get<ApiResponse<IndustryChainDebug>>('/api/industry-chain/debug');
  return response.data.data;
}

export async function triggerSync(chainId?: string, tradeDate?: string): Promise<Record<string, any>> {
  const params: Record<string, string> = {};
  if (chainId) params.chain_id = chainId;
  if (tradeDate) params.trade_date = tradeDate;
  const response = await service.post<ApiResponse<Record<string, any>>>('/api/industry-chain/sync', null, { params });
  return response.data.data;
}
