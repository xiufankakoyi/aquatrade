from pathlib import Path
text_path = Path('myapp/src/pages/GridSearchPage.vue')
text = text_path.read_text(encoding='utf-8')
start = text.index('// 参数展示和单位配置')
script_end = text.index('</script>', start)
new_block = '''// 参数展示和单位配置（前端专用，不影响后端）
interface ParamDisplayConfig {
  unit?: string;      // 显示用单位，例如 "亿"
  scale?: number;     // 前端 -> 后端 的倍数
}

// 目前只对市值做"前端<->后端"的转换
const PARAM_DISPLAY: Record<string, ParamDisplayConfig> = {
  market_cap_min: {
    unit: '亿',
    scale: 10000,     // 前端：亿，后端：万
  },
  market_cap_max: {
    unit: '亿',
    scale: 10000,
  },
};

const normalizeParamKey = (key: string) => key?.trim().toLowerCase();
const getParamDisplayConfig = (key: string) => {
  if (!key) return undefined;
  return PARAM_DISPLAY[normalizeParamKey(key)];
};

function getParamUnit(key: string): string {
  return getParamDisplayConfig(key)?.unit ?? '';
}

function toUiValue(key: string, backendValue: number | undefined | null): number | null {
  if (backendValue === undefined || backendValue === null) return null;
  const cfg = getParamDisplayConfig(key);
  if (!cfg?.scale) return backendValue;
  return backendValue / cfg.scale;
}

function toBackendValue(key: string, uiValue: number | undefined | null): number | null {
  if (uiValue === undefined || uiValue === null) return null;
  const cfg = getParamDisplayConfig(key);
  if (!cfg?.scale) return uiValue;
  return uiValue * cfg.scale;
}

function formatParamDisplayValue(key: string, value: any): string | number {
  const numericValue = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(numericValue)) return value;
  const cfg = getParamDisplayConfig(key);
  const displayValue = cfg?.scale ? numericValue / cfg.scale : numericValue;
  return displayValue.toFixed(2);
}
'''
prefix = text[:start]
suffix = text[script_end:]
text_path.write_text(prefix + new_block + suffix, encoding='utf-8')
