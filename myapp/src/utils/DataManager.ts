/**
 * DataManager - 智能数据缓存层
 *
 * 核心功能：
 * 1. IndexedDB 本地缓存 - 存储K线数据，避免重复请求
 * 2. TTL (Time To Live) - 数据过期机制，1分钟内不重复请求服务器
 * 3. 智能区间合并 - 只请求缓存中缺失的数据段
 * 4. 强制刷新 - 支持手动清除缓存重新拉取
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

/** 缓存数据项 */
interface CacheItem {
  symbol: string
  timeframe: string
  data: KlineDataPoint[]
  timestamp: number
  ttl: number
}

/** 数据请求参数 */
export interface DataRequestParams {
  symbol: string
  timeframe: string
  startDate: string
  endDate: string
  forceRefresh?: boolean
}

/** IndexedDB 配置 */
const DB_NAME = 'AquaTradeKlineDB'
const DB_VERSION = 1
const STORE_NAME = 'kline_cache'

/** 默认 TTL: 1分钟 (毫秒) */
const DEFAULT_TTL = 60 * 1000

class DataManager {
  private db: IDBDatabase | null = null
  private memoryCache: Map<string, CacheItem> = new Map()
  private initPromise: Promise<void> | null = null

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
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'key' })
          store.createIndex('symbol', 'symbol', { unique: false })
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
   * 从 IndexedDB 读取缓存
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

        // 检查是否过期
        if (Date.now() - result.timestamp > result.ttl) {
          // 过期数据，删除
          this.deleteFromDB(key)
          return resolve(null)
        }

        resolve({
          symbol: result.symbol,
          timeframe: result.timeframe,
          data: result.data,
          timestamp: result.timestamp,
          ttl: result.ttl
        })
      }
    })
  }

  /**
   * 写入缓存到 IndexedDB
   */
  private async writeToDB(key: string, item: CacheItem): Promise<void> {
    if (!this.db) await this.init()
    if (!this.db) return

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.put({
        key,
        symbol: item.symbol,
        timeframe: item.timeframe,
        data: item.data,
        timestamp: item.timestamp,
        ttl: item.ttl
      })

      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }

  /**
   * 从 IndexedDB 删除缓存
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
   * 获取缓存数据（公开方法，供组件先读取缓存）
   */
  async getCache(
    symbol: string,
    timeframe: string
  ): Promise<CacheItem | null> {
    const key = this.getCacheKey(symbol, timeframe)

    // 优先从内存缓存读取
    const memoryItem = this.memoryCache.get(key)
    if (memoryItem && Date.now() - memoryItem.timestamp <= memoryItem.ttl) {
      return memoryItem
    }

    // 从 IndexedDB 读取
    const dbItem = await this.readFromDB(key)
    if (dbItem) {
      // 同步到内存缓存
      this.memoryCache.set(key, dbItem)
      return dbItem
    }

    return null
  }

  /**
   * 设置缓存数据 - 异步写入IndexedDB不阻塞主流程
   */
  private setCache(
    symbol: string,
    timeframe: string,
    data: KlineDataPoint[],
    ttl: number = DEFAULT_TTL
  ): void {
    const key = this.getCacheKey(symbol, timeframe)
    const item: CacheItem = {
      symbol,
      timeframe,
      data,
      timestamp: Date.now(),
      ttl
    }

    // 写入内存缓存（同步，立即生效）
    this.memoryCache.set(key, item)

    // 异步写入 IndexedDB，不阻塞主流程
    this.writeToDB(key, item).catch(err => {
      console.warn('[DataManager] 写入缓存失败:', err)
    })
  }

  /**
   * 合并两段K线数据（按日期排序去重）
   */
  private mergeKlineData(
    existing: KlineDataPoint[],
    newData: KlineDataPoint[]
  ): KlineDataPoint[] {
    const merged = new Map<string, KlineDataPoint>()

    // 添加现有数据
    existing.forEach((item) => {
      merged.set(item.date, item)
    })

    // 添加新数据（会覆盖旧数据）
    newData.forEach((item) => {
      merged.set(item.date, item)
    })

    // 按日期排序
    return Array.from(merged.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }

  /**
   * 计算需要请求的日期区间
   * @returns 需要请求的区间数组，空数组表示缓存已覆盖
   */
  private calculateMissingRanges(
    cacheStart: string,
    cacheEnd: string,
    reqStart: string,
    reqEnd: string
  ): Array<{ start: string; end: string }> {
    const ranges: Array<{ start: string; end: string }> = []

    const cacheStartTime = new Date(cacheStart).getTime()
    const cacheEndTime = new Date(cacheEnd).getTime()
    const reqStartTime = new Date(reqStart).getTime()
    const reqEndTime = new Date(reqEnd).getTime()

    // 请求开始早于缓存开始，需要请求前面部分
    if (reqStartTime < cacheStartTime) {
      ranges.push({
        start: reqStart,
        end: new Date(cacheStartTime - 86400000).toISOString().split('T')[0]
      })
    }

    // 请求结束晚于缓存结束，需要请求后面部分
    if (reqEndTime > cacheEndTime) {
      ranges.push({
        start: new Date(cacheEndTime + 86400000).toISOString().split('T')[0],
        end: reqEnd
      })
    }

    return ranges
  }

  /**
   * 请求服务器数据
   */
  private async fetchFromServer(
    symbol: string,
    timeframe: string,
    startDate: string,
    endDate: string
  ): Promise<KlineDataPoint[]> {
    try {
      const response = await apiService.getKlineData(symbol, startDate, endDate)

      // API 返回的是 { data: KlineData[], perf? } 对象
      const data = response?.data || []

      if (Array.isArray(data)) {
        return data.map((item: any) => ({
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
      console.error('[DataManager] 请求服务器数据失败:', error)
      throw error
    }
  }

  /**
   * 直接从服务器获取K线数据（用于流式加载，不走缓存）
   */
  async fetchFromServerPublic(
    symbol: string,
    timeframe: string,
    startDate: string,
    endDate: string
  ): Promise<KlineDataPoint[]> {
    return this.fetchFromServer(symbol, timeframe, startDate, endDate)
  }

  /**
   * 获取K线数据（智能缓存入口）- 分段并行加载
   */
  async getKlineData(params: DataRequestParams): Promise<KlineDataPoint[]> {
    const { symbol, timeframe, startDate, endDate, forceRefresh = false } = params

    await this.init()

    // 强制刷新：清除缓存并重新请求
    if (forceRefresh) {
      await this.clearCache(symbol, timeframe)
      const data = await this.fetchSegmented(symbol, timeframe, startDate, endDate)
      this.setCache(symbol, timeframe, data)
      return data
    }

    // 尝试读取缓存
    const cache = await this.getCache(symbol, timeframe)

    if (!cache || cache.data.length === 0) {
      // 无缓存，分段加载
      const data = await this.fetchSegmented(symbol, timeframe, startDate, endDate)
      this.setCache(symbol, timeframe, data)
      return data
    }

    // 有缓存，检查区间覆盖
    const cacheStart = cache.data[0].date
    const cacheEnd = cache.data[cache.data.length - 1].date

    const reqStartTime = new Date(startDate).getTime()
    const reqEndTime = new Date(endDate).getTime()
    const cacheStartTime = new Date(cacheStart).getTime()
    const cacheEndTime = new Date(cacheEnd).getTime()

    // 请求区间完全在缓存内，直接返回
    if (reqStartTime >= cacheStartTime && reqEndTime <= cacheEndTime) {
      return cache.data.filter((item) => {
        const itemTime = new Date(item.date).getTime()
        return itemTime >= reqStartTime && itemTime <= reqEndTime
      })
    }

    // 需要补充数据 - 分段并行加载缺失部分
    let mergedData = [...cache.data]

    // 需要补充前面
    if (reqStartTime < cacheStartTime) {
      const frontData = await this.fetchSegmented(symbol, timeframe, startDate, cacheStart)
      mergedData = this.mergeKlineData(frontData, mergedData)
    }

    // 需要补充后面
    if (reqEndTime > cacheEndTime) {
      const backData = await this.fetchSegmented(symbol, timeframe, cacheEnd, endDate)
      mergedData = this.mergeKlineData(mergedData, backData)
    }

    // 更新缓存（异步，不阻塞）
    this.setCache(symbol, timeframe, mergedData)

    // 返回请求区间内的数据
    return mergedData.filter((item) => {
      const itemTime = new Date(item.date).getTime()
      return itemTime >= reqStartTime && itemTime <= reqEndTime
    })
  }

  /**
   * 分段加载数据 - 串行加载避免并发过多，支持流式返回
   */
  private async fetchSegmented(
    symbol: string,
    timeframe: string,
    startDate: string,
    endDate: string,
    onProgress?: (loaded: number, total: number, data: KlineDataPoint[]) => void
  ): Promise<KlineDataPoint[]> {
    const SEGMENT_DAYS = 60 // 增加到60天，减少请求次数
    const start = new Date(startDate)
    const end = new Date(endDate)
    const totalDays = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)

    // 如果范围较小，直接请求
    if (totalDays <= SEGMENT_DAYS) {
      const data = await this.fetchFromServer(symbol, timeframe, startDate, endDate)
      onProgress?.(1, 1, data)
      return data
    }

    // 分割为多个小段
    const segments: Array<{ start: string; end: string }> = []
    let currentStart = new Date(start)

    while (currentStart < end) {
      const segmentEnd = new Date(currentStart)
      segmentEnd.setDate(segmentEnd.getDate() + SEGMENT_DAYS)

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

    console.log(`[DataManager] 分段加载: ${segments.length} 段, 总计 ${Math.floor(totalDays)} 天`)

    // 串行加载，先加载最近的数据让用户快速看到
    let merged: KlineDataPoint[] = []
    for (let i = segments.length - 1; i >= 0; i--) {
      const seg = segments[i]
      try {
        const data = await this.fetchFromServer(symbol, timeframe, seg.start, seg.end)
        merged = this.mergeKlineData(merged, data)
        onProgress?.(segments.length - i, segments.length, merged)
      } catch (err) {
        console.error(`[DataManager] 加载段 ${i + 1}/${segments.length} 失败:`, err)
        // 继续加载其他段
      }
    }

    return merged
  }

  /**
   * 清除指定品种的缓存
   */
  async clearCache(symbol?: string, timeframe?: string): Promise<void> {
    if (!this.db) await this.init()
    if (!this.db) return

    if (symbol && timeframe) {
      // 清除特定品种
      const key = this.getCacheKey(symbol, timeframe)
      this.memoryCache.delete(key)
      await this.deleteFromDB(key)
    } else if (symbol) {
      // 清除该品种所有时间周期
      const keysToDelete: string[] = []
      this.memoryCache.forEach((_, key) => {
        if (key.startsWith(`${symbol}_`)) {
          keysToDelete.push(key)
        }
      })
      keysToDelete.forEach((key) => this.memoryCache.delete(key))

      // 从 IndexedDB 删除
      const transaction = this.db.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.openCursor()

      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest).result
        if (cursor) {
          const key = cursor.value.key as string
          if (key.startsWith(`${symbol}_`)) {
            cursor.delete()
          }
          cursor.continue()
        }
      }
    } else {
      // 清除所有缓存
      this.memoryCache.clear()

      const transaction = this.db.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      store.clear()
    }
  }

  /**
   * 获取缓存统计信息
   */
  async getCacheStats(): Promise<{
    memoryCount: number
    dbCount: number
    totalSize: number
  }> {
    if (!this.db) await this.init()

    const memoryCount = this.memoryCache.size

    let dbCount = 0
    let totalSize = 0

    if (this.db) {
      const transaction = this.db.transaction([STORE_NAME], 'readonly')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.openCursor()

      await new Promise<void>((resolve) => {
        request.onsuccess = (event) => {
          const cursor = (event.target as IDBRequest).result
          if (cursor) {
            dbCount++
            totalSize += JSON.stringify(cursor.value).length
            cursor.continue()
          } else {
            resolve()
          }
        }
        request.onerror = () => resolve()
      })
    }

    return { memoryCount, dbCount, totalSize }
  }
}

// 导出单例
export const dataManager = new DataManager()
export default dataManager
