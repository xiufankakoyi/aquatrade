import service from './index';

export interface PatternTemplate {
  pattern_id: string;
  pattern_name: string;
  description: string;
  default_params: Record<string, number | string | boolean>;
  required_events: string[];
}

export interface EventSequenceItem {
  date: string;
  close?: number | null;
  change_pct?: number | null;
  events: string[];
}

export interface PatternMatch {
  pattern_id: string;
  pattern_name: string;
  symbol: string;
  stock_name?: string | null;
  match_date: string;
  event_sequence: EventSequenceItem[];
  match_score: number;
  hit_reasons: string[];
  risk_flags: string[];
  concept_tags: string[];
  future_return_1d?: number | null;
  future_return_3d?: number | null;
  future_return_5d?: number | null;
  future_return_10d?: number | null;
  max_gain_5d?: number | null;
  max_drawdown_5d?: number | null;
  success_label?: boolean | null;
  failure_reason?: string | null;
}

export interface PatternReport {
  pattern_id: string;
  pattern_name: string;
  start_date: string;
  end_date: string;
  params: Record<string, number | string | boolean>;
  summary: {
    total_matches: number;
    success_cases: number;
    failure_cases: number;
    current_candidates: number;
    success_rate: number | null;
  };
  results: PatternMatch[];
  success_samples: PatternMatch[];
  failure_samples: PatternMatch[];
  current_candidates: PatternMatch[];
  research_boundary: string;
}

export interface PatternEventRow {
  stock_code: string;
  stock_name?: string | null;
  trade_date: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  change_pct?: number | null;
  volume?: number | null;
  amount?: number | null;
  ma5?: number | null;
  ma10?: number | null;
  [key: string]: unknown;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
  message?: string;
}

export async function getPatternTemplates(): Promise<PatternTemplate[]> {
  const response = await service.get<ApiResponse<PatternTemplate[]>>('/api/patterns/templates');
  return response.data.data;
}

export async function searchPatterns(payload: {
  pattern_id: string;
  start_date: string;
  end_date: string;
  symbols?: string[];
  params?: Record<string, number | string | boolean>;
  limit?: number;
  auto_generate?: boolean;
}): Promise<PatternReport> {
  const response = await service.post<ApiResponse<PatternReport>>('/api/patterns/search', payload);
  return response.data.data;
}

export async function getSymbolEvents(symbol: string, startDate: string, endDate: string): Promise<PatternEventRow[]> {
  const response = await service.get<ApiResponse<PatternEventRow[]>>(`/api/patterns/symbol/${encodeURIComponent(symbol)}/events`, {
    params: { start_date: startDate, end_date: endDate, limit: 1000 },
  });
  return response.data.data;
}
