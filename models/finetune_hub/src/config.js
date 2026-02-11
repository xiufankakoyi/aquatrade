// API 配置
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001'

export const API_ENDPOINTS = {
  health: `${API_BASE_URL}/api/health`,
  trainStart: `${API_BASE_URL}/api/train/start`,
  trainStatus: `${API_BASE_URL}/api/train/status`,
  predict: `${API_BASE_URL}/api/predict`,
  validateData: `${API_BASE_URL}/api/data/validate`,
  cleanData: `${API_BASE_URL}/api/data/clean`,
}

