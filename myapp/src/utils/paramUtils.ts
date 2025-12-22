import { PARAM_DISPLAY, CUSTOM_PARAM_CONFIG } from '@/config/strategyConfig';

const normalizeParamKey = (key: string) => key?.trim().toLowerCase();

export const getParamDisplayConfig = (key: string) => {
  if (!key) return undefined;
  return PARAM_DISPLAY[normalizeParamKey(key)];
};

// 通用默认范围生成器（当后端不返回 min/max 时使用）
export const getDefaultRange = (param: any): { min: number; max: number } => {
  // 1. 优先使用配置表中的值
  const config = CUSTOM_PARAM_CONFIG[param.key];
  if (config && config.overrideMin !== undefined && config.overrideMax !== undefined) {
    return {
      min: config.overrideMin,
      max: config.overrideMax
    };
  }
  
  // 2. 根据参数类型和名称推断通用超大范围
  const paramType = param.type || 'float';
  const key = param.key?.toLowerCase() || '';
  
  if (paramType === 'int') {
    if (key.includes('days') || key.includes('ma')) {
      return { min: 1, max: 1000 };
    } else if (key.includes('candidates') || key.includes('stocks')) {
      return { min: 1, max: 1000 };
    } else if (key.includes('cap')) {
      return { min: 0, max: 50000000 };
    } else {
      return { min: 1, max: 10000 };
    }
  } else {
    if (key.includes('ratio') || key.includes('position')) {
      return { min: 0, max: 10 };
    } else if (key.includes('threshold')) {
      return { min: 0, max: 100 };
    } else if (key.includes('cap')) {
      return { min: 0, max: 50000000 };
    } else {
      return { min: 0, max: 1000 };
    }
  }
};

export const getParamUnit = (key: string): string => {
  return getParamDisplayConfig(key)?.unit ?? '';
};

export const toUiValue = (key: string, backendValue: number | undefined | null): number | null => {
  if (backendValue === undefined || backendValue === null) return null;
  const cfg = getParamDisplayConfig(key);
  if (!cfg?.scale) return backendValue;
  const result = backendValue / cfg.scale;
  if (result === 0) return 0;
  return result < 0.01 && result > 0 ? 0.01 : result;
};

export const toBackendValue = (key: string, uiValue: number | undefined | null): number | null => {
  if (uiValue === undefined || uiValue === null) return null;
  const cfg = getParamDisplayConfig(key);
  if (!cfg?.scale) return uiValue;
  return uiValue * cfg.scale;
};

export const formatParamDisplayValue = (key: string, value: any, digits = 2): string => {
  const numericValue = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(numericValue)) return String(value ?? '');
  const cfg = getParamDisplayConfig(key);
  const displayValue = cfg?.scale ? numericValue / cfg.scale : numericValue;
  return displayValue.toFixed(digits);
};

export const getParamLabel = (param: any): string => {
  const base = String(param?.label || param?.key || '');
  const cfg = getParamDisplayConfig(param?.key);
  if (!cfg?.unit) return base;
  if (base.includes('万元')) return base.replace('万元', '亿元');
  if (base.includes('万')) return base.replace('万', cfg.unit);
  return `${base}(${cfg.unit})`;
};


















