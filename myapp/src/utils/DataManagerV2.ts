/**
 * DataManagerV2 - 高性能K线数据管理器
 *
 * 核心优化：
 * 1. 三段式预加载 - 中心窗口 + 左侧缓冲 + 右侧空白
 * 2. 虚拟渲染 - 只渲染视口内数据
 * 3. 异步预取 - 后台加载不阻塞UI
 * 4. 平滑缩放 - 插值拉伸过渡
 */

import { apiService } from '../services/api'

/** K线数据点 */
export interface KlineDataPoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

/** 数据加载配置 */
export interface LoadConfig {
  /** 中心窗口大小（可见区域） */
  centerWindow: number
  /** 左侧缓冲大小（预加载） */
  leftBuffer: number
  /** 右侧缓冲大小 */
  rightBuffer: number
}

/** 默认配置 */
const DEFAULT_CONFIG: LoadConfig = {
  centerWindow: 20,
  leftBuffer: 100,
  rightBuffer: 0
}

/** 数据段 */
export interface DataSegment {
  /** 中心窗口数据 */
  center: KlineDataPoint[]
  /** 左侧缓冲数据 */
  leftBuffer: KlineDataPoint[]
  /** 右侧缓冲数据 */
  rightBuffer: KlineDataPoint[]
  /** 完整数据（用于缩放） */
  full: KlineDataPoint[]
  /** 是否有更多历史数据 */
  hasMoreHistory: boolean
  /** 是否有更多未来数据 */
  hasMoreFuture: boolean
}

/** 缓存项 */
interface CacheItem {
  key: string
  data: KlineDataPoint[]
  startDate: string
  endDate: string
  timestamp: number
  hasMoreHistory: boolean
  hasMoreFuture: boolean
}

/** IndexedDB 配置 */
const DB_NAME = 'AquaTradeKlineDB'
const DB_VERSION = 2
const STORE_NAME = 'kline_cache_v2'

/** 默认 TTL: 5分钟 */
const DEFAULT_TTL = 5 * 60 * 1000

class DataManagerV2 {
  private db: IDBDatabase | null = null
  private memoryCache: Map<string, CacheItem> = new Map()
  private initPromise: Promise<void> | null = null
  private config: LoadConfig = DEFAULT_CONFIG

  /** 预取队列 */
  private prefetchQueue: Set<string> = new Set()
  private isPrefetching = false

  /**
   * 初始化 IndexedDB
   */
  async init(): Promise<void> {
    if (this.initPromise) return this.initPromise
    this.initPromise = this.doInit()
    return this.initPromise
  }

  private async doInit(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION)

      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        this.db = request.result
        resolve()
      }

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        // 删除旧版本存储
        if (db.objectStoreNames.contains('kline_cache')) {
          db.deleteObjectStore('kline_cache')
        }
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'key' })
          store.createIndex('timestamp', 'timestamp', { unique: false })
        }
      }
    })
  }

  /**
   * 生成缓存键
   */
  private getCacheKey(symbol: string, timeframe: string): string {
    return `${symbol}_${timeframe}`
  }

  /**
   * 从 IndexedDB 读取
   */
  private async readFromDB(key: string): Promise<CacheItem | null> {
    if (!this.db) await this.init()
    if (!this.db) return null

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readonly')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.get(key)

      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        const result = request.result
        if (!result) return resolve(null)

        if (Date.now() - result.timestamp > DEFAULT_TTL) {
          this.deleteFromDB(key)
          return resolve(null)
        }

        resolve(result)
      }
    })
  }

  /**
   * 写入 IndexedDB
   */
  private async writeToDB(item: CacheItem): Promise<void> {
    if (!this.db) await this.init()
    if (!this.db) return

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.put(item)

      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }

  /**
   * 删除缓存
   */
  private async deleteFromDB(key: string): Promise<void> {
    if (!this.db) return
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.delete(key)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }

  /**
   * 获取缓存
   */
  private async getCache(symbol: string, timeframe: string): Promise<CacheItem | null> {
    const key = this.getCacheKey(symbol, timeframe)
    const memoryItem = this.memoryCache.get(key)
    if (memoryItem && Date.now() - memoryItem.timestamp <= DEFAULT_TTL) {
      return memoryItem
    }
    const dbItem = await this.readFromDB(key)
    if (dbItem) {
      this.memoryCache.set(key, dbItem)
      return dbItem
    }
    return null
  }

  /**
   * 设置缓存
   */
  private async setCache(
    symbol: string,
    timeframe: string,
    data: KlineDataPoint[],
    startDate: string,
    endDate: string,
    hasMoreHistory: boolean,
    hasMoreFuture: boolean
  ): Promise<void> {
    const key = this.getCacheKey(symbol, timeframe)
    const item: CacheItem = {
      key,
      data,
      startDate,
      endDate,
      timestamp: Date.now(),
      hasMoreHistory,
      hasMoreFuture
    }
    this.memoryCache.set(key, item)
    await this.writeToDB(item)
  }

  /**
   * 计算日期偏移
   */
  private addDays(dateStr: string, days: number): string {
    const date = new Date(dateStr)
    date.setDate(date.getDate() + days)
    return date.toISOString().split('T')[0]
  }

  /**
   * 三段式数据加载 - 分段并行加载优化
   * @param symbol 股票代码
   * @param timeframe 时间周期
   * @param centerDate 中心日期（当前显示区域中心）
   * @param config 加载配置
   */
  async loadSegmentedData(
    symbol: string,
    timeframe: string,
    centerDate: string,
    config: Partial<LoadConfig> = {}
  ): Promise<DataSegment> {
    const cfg = { ...this.config, ...config }
    await this.init()

    // 计算需要的日期范围
    const centerHalf = Math.floor(cfg.centerWindow / 2)
    const totalLeft = centerHalf + cfg.leftBuffer
    const totalRight = centerHalf + cfg.rightBuffer

    const targetStartDate = this.addDays(centerDate, -totalLeft)
    const targetEndDate = this.addDays(centerDate, totalRight)

    // 尝试读取缓存
    const cache = await this.getCache(symbol, timeframe)
    let fullData: KlineDataPoint[] = []
    let hasMoreHistory = true
    let hasMoreFuture = false

    if (cache && cache.data.length > 0) {
      // 检查缓存覆盖情况
      const cacheStart = new Date(cache.startDate).getTime()
      const cacheEnd = new Date(cache.endDate).getTime()
      const targetStart = new Date(targetStartDate).getTime()
      const targetEnd = new Date(targetEndDate).getTime()

      // 已有数据范围
      fullData = [...cache.data]
      hasMoreHistory = cache.hasMoreHistory
      hasMoreFuture = cache.hasMoreFuture

      // 计算需要补充的段（每段最多30天，避免超时）
      const missingSegments = this.calculateMissingSegments(
        cache.startDate,
        cache.endDate,
        targetStartDate,
        targetEndDate,
        30 // 每段最大30天
      )

      if (missingSegments.length > 0) {
        // 并行加载所有缺失段
        const segmentPromises = missingSegments.map(seg =>
          this.fetchFromServer(symbol, timeframe, seg.start, seg.end)
        )
        const segmentResults = await Promise.all(segmentPromises)

        // 合并所有段
        segmentResults.forEach(segmentData => {
          fullData = this.mergeData(fullData, segmentData)
        })

        // 更新缓存
        const newStart = missingSegments[0].start < cache.startDate
          ? missingSegments[0].start
          : cache.startDate
        const newEnd = missingSegments[missingSegments.length - 1].end > cache.endDate
          ? missingSegments[missingSegments.length - 1].end
          : cache.endDate

        await this.setCache(symbol, timeframe, fullData, newStart, newEnd, hasMoreHistory, hasMoreFuture)
      }
    } else {
      // 无缓存，分段并行加载
      const segments = this.splitDateRange(targetStartDate, targetEndDate, 30)
      const segmentPromises = segments.map(seg =>
        this.fetchFromServer(symbol, timeframe, seg.start, seg.end)
      )
      const segmentResults = await Promise.all(segmentPromises)

      // 合并所有段
      segmentResults.forEach(segmentData => {
        fullData = this.mergeData(fullData, segmentData)
      })

      await this.setCache(symbol, timeframe, fullData, targetStartDate, targetEndDate, hasMoreHistory, hasMoreFuture)
    }

    // 分割数据段
    return this.splitSegments(fullData, centerDate, cfg, hasMoreHistory, hasMoreFuture)
  }

  /**
   * 将日期范围分割为多个小段
   */
  private splitDateRange(
    startDate: string,
    endDate: string,
    maxDaysPerSegment: number
  ): Array<{ start: string; end: string }> {
    const segments: Array<{ start: string; end: string }> = []
    const start = new Date(startDate)
    const end = new Date(endDate)
    const totalDays = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)

    if (totalDays <= maxDaysPerSegment) {
      return [{ start: startDate, end: endDate }]
    }

    let currentStart = new Date(start)
    while (currentStart < end) {
      const segmentEnd = new Date(currentStart)
      segmentEnd.setDate(segmentEnd.getDate() + maxDaysPerSegment)

      if (segmentEnd > end) {
        segments.push({
          start: currentStart.toISOString().split('T')[0],
          end: endDate
        })
        break
      } else {
        segments.push({
          start: currentStart.toISOString().split('T')[0],
          end: segmentEnd.toISOString().split('T')[0]
        })
        currentStart = new Date(segmentEnd)
        currentStart.setDate(currentStart.getDate() + 1)
      }
    }

    return segments
  }

  /**
   * 计算需要补充的数据段
   */
  private calculateMissingSegments(
    cacheStart: string,
    cacheEnd: string,
    targetStart: string,
    targetEnd: string,
    maxDaysPerSegment: number
  ): Array<{ start: string; end: string }> {
    const segments: Array<{ start: string; end: string }> = []

    const cacheStartTime = new Date(cacheStart).getTime()
    const cacheEndTime = new Date(cacheEnd).getTime()
    const targetStartTime = new Date(targetStart).getTime()
    const targetEndTime = new Date(targetEnd).getTime()

    // 需要补充前面部分
    if (targetStartTime < cacheStartTime) {
      segments.push(...this.splitDateRange(targetStart, cacheStart, maxDaysPerSegment))
    }

    // 需要补充后面部分
    if (targetEndTime > cacheEndTime) {
      segments.push(...this.splitDateRange(cacheEnd, targetEnd, maxDaysPerSegment))
    }

    return segments
  }

  /**
   * 分割数据为三段
   */
  private splitSegments(
    data: KlineDataPoint[],
    centerDate: string,
    config: LoadConfig,
    hasMoreHistory: boolean,
    hasMoreFuture: boolean
  ): DataSegment {
    const centerTime = new Date(centerDate).getTime()
    const centerHalf = Math.floor(config.centerWindow / 2)

    // 找到中心日期在数据中的索引
    let centerIndex = data.findIndex(item => item.date === centerDate)
    if (centerIndex === -1) {
      // 找最接近的
      centerIndex = data.reduce((closest, item, index) => {
        const diff = Math.abs(new Date(item.date).getTime() - centerTime)
        const closestDiff = Math.abs(new Date(data[closest].date).getTime() - centerTime)
        return diff < closestDiff ? index : closest
      }, 0)
    }

    // 计算各段索引
    const centerStart = Math.max(0, centerIndex - centerHalf)
    const centerEnd = Math.min(data.length, centerIndex + centerHalf + 1)
    const leftStart = Math.max(0, centerStart - config.leftBuffer)

    return {
      center: data.slice(centerStart, centerEnd),
      leftBuffer: data.slice(leftStart, centerStart),
      rightBuffer: data.slice(centerEnd, centerEnd + config.rightBuffer),
      full: data,
      hasMoreHistory: hasMoreHistory && leftStart > 0,
      hasMoreFuture: hasMoreFuture && centerEnd < data.length
    }
  }

  /**
   * 加载更多历史数据
   */
  async loadMoreHistory(
    symbol: string,
    timeframe: string,
    currentStartDate: string,
    count: number = 100
  ): Promise<KlineDataPoint[]> {
    const endDate = this.addDays(currentStartDate, -1)
    const startDate = this.addDays(endDate, -count)

    const newData = await this.fetchFromServer(symbol, timeframe, startDate, endDate)

    // 更新缓存
    const cache = await this.getCache(symbol, timeframe)
    if (cache) {
      const merged = this.mergeData(newData, cache.data)
      await this.setCache(symbol, timeframe, merged, startDate, cache.endDate, newData.length >= count, cache.hasMoreFuture)
    }

    return newData
  }

  /**
   * 后台预取数据
   */
  async prefetchData(symbol: string, timeframe: string, centerDate: string): Promise<void> {
    const key = `${symbol}_${timeframe}_${centerDate}`
    if (this.prefetchQueue.has(key)) return

    this.prefetchQueue.add(key)

    if (this.isPrefetching) return
    this.isPrefetching = true

    try {
      await this.loadSegmentedData(symbol, timeframe, centerDate, {
        centerWindow: 20,
        leftBuffer: 200,  // 预取更多历史数据
        rightBuffer: 0
      })
    } finally {
      this.isPrefetching = false
      this.prefetchQueue.delete(key)
    }
  }

  /**
   * 从服务器获取数据
   */
  private async fetchFromServer(
    symbol: string,
    timeframe: string,
    startDate: string,
    endDate: string
  ): Promise<KlineDataPoint[]> {
    try {
      const response = await apiService.getKlineData(symbol, startDate, endDate)
      if (response && Array.isArray(response)) {
        return response.map((item: any) => ({
          date: item.date,
          open: item.open,
          high: item.high,
          low: item.low,
          close: item.close,
          volume: item.volume || 0
        }))
      }
      return []
    } catch (error) {
      console.error('[DataManagerV2] 请求失败:', error)
      throw error
    }
  }

  /**
   * 合并数据（去重排序）
   */
  private mergeData(existing: KlineDataPoint[], newData: KlineDataPoint[]): KlineDataPoint[] {
    const merged = new Map<string, KlineDataPoint>()
    existing.forEach(item => merged.set(item.date, item))
    newData.forEach(item => merged.set(item.date, item))
    return Array.from(merged.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }

  /**
   * 清除缓存
   */
  async clearCache(symbol?: string, timeframe?: string): Promise<void> {
    if (!this.db) await this.init()
    if (!this.db) return

    if (symbol && timeframe) {
      const key = this.getCacheKey(symbol, timeframe)
      this.memoryCache.delete(key)
      await this.deleteFromDB(key)
    } else {
      // 清除所有
      this.memoryCache.clear()
      const transaction = this.db.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      await store.clear()
    }
  }
}

export const dataManagerV2 = new DataManagerV2()
