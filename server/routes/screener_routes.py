#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股票量化筛选器 API 路由
提供指标列表获取和股票筛选功能
"""
from flask import Blueprint, request, jsonify
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
import math
import json
import os

import polars as pl
import pandas as pd
import numpy as np

from config.config import Config

screener_bp = Blueprint('screener', __name__, url_prefix='/api/screener')

_lancedb_reader = None
_dates_cache = {'dates': None, 'latest': None, 'updated_at': 0}
_DATES_CACHE_TTL = 3600

def get_lancedb():
    """获取 LanceDB Reader 实例"""
    global _lancedb_reader
    if _lancedb_reader is None:
        from data_svc.storage.lancedb_reader import get_lancedb_reader
        _lancedb_reader = get_lancedb_reader()
    return _lancedb_reader

def get_lancedb_manager():
    """获取 LanceDB Manager 实例"""
    from data_svc.storage.lancedb_manager import get_lancedb_manager
    return get_lancedb_manager()


def get_stock_daily_df() -> Optional[pl.DataFrame]:
    """从 LanceDB 获取股票日线数据，返回 Polars DataFrame"""
    try:
        reader = get_lancedb()
        df = reader.read_all()
        return df if not df.is_empty() else None
    except Exception as e:
        print(f"[Screener] Error reading stock_daily from LanceDB: {e}")
        import traceback
        traceback.print_exc()
        return None


import time as _time

def get_all_trade_dates() -> List[str]:
    """获取所有交易日列表 - 使用 DuckDB 优化 + 内存缓存"""
    global _dates_cache
    
    now = _time.time()
    if _dates_cache['dates'] is not None and (now - _dates_cache['updated_at']) < _DATES_CACHE_TTL:
        return _dates_cache['dates']
    
    try:
        import lancedb
        import duckdb
        
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data', 'lancedb'
        )
        
        if not os.path.exists(db_path):
            return _dates_cache['dates'] or []
            
        db = lancedb.connect(db_path)
        result = db.list_tables()
        tables = result.tables if hasattr(result, 'tables') else list(result)
        
        if 'daily_ohlcv' not in tables:
            return _dates_cache['dates'] or []
        
        tbl = db.open_table('daily_ohlcv')
        lance_ds = tbl.to_lance()
        
        conn = duckdb.connect(database=':memory:')
        scanner = lance_ds.scanner(columns=['trade_date', 'volume'])
        arrow_table = scanner.to_table()
        conn.register("dailies", arrow_table)
        
        dates_result = conn.execute("""
            SELECT DISTINCT trade_date 
            FROM dailies 
            ORDER BY trade_date DESC
        """).fetchall()
        
        latest_result = conn.execute("""
            SELECT trade_date 
            FROM dailies 
            WHERE volume IS NOT NULL
            ORDER BY trade_date DESC 
            LIMIT 1
        """).fetchone()
        
        conn.close()
        
        dates = [str(row[0])[:10] for row in dates_result]
        latest = str(latest_result[0])[:10] if latest_result else None
        
        _dates_cache = {
            'dates': dates,
            'latest': latest,
            'updated_at': now
        }
        
        return dates

    except Exception as e:
        print(f"[Screener] get_all_trade_dates 错误: {e}")
        import traceback
        traceback.print_exc()
        return _dates_cache['dates'] or []


def normalize_date_for_filter(target_date: str, df: pl.DataFrame) -> Optional[str]:
    """将日期格式转换为与数据匹配的格式
    
    Args:
        target_date: 输入日期，如 '2025-11-20'
        df: DataFrame，用于检查日期列格式
        
    Returns:
        转换后的日期字符串，用于过滤
    """
    if not target_date:
        return None
    
    # 检查数据中的日期列
    if 'trade_date_basic' in df.columns:
        # trade_date_basic 格式是 '20260227' (YYYYMMDD)
        # 将 '2025-11-20' 转换为 '20251120'
        return target_date.replace('-', '').replace('/', '')
    elif 'trade_date' in df.columns:
        # trade_date 是 datetime 类型，保持原格式
        return target_date
    
    return target_date


def get_all_stocks_daily_df(
    target_date: Optional[str] = None,
    fields: Optional[List[str]] = None,
) -> Optional[pl.DataFrame]:
    """获取所有股票的日线数据（默认从 LanceDB 读取）
    
    Args:
        target_date: 如果指定，只返回该日期的数据
        
    Returns:
        包含所有股票数据的 Polars DataFrame
    """
    try:
        reader = get_lancedb()
        requested_fields = [
            "stock_code", "ts_code", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "prev_close", "change_pct", "turnover_rate", "volume_ratio",
            "total_mv", "float_mv", "pe", "pe_ttm", "pb", "ps", "ps_ttm",
        ]
        for field in fields or []:
            if field and field not in requested_fields:
                requested_fields.append(field)
        df = reader.read(None, target_date, target_date, fields=requested_fields)
        if df is not None and not df.is_empty():
            print(f"[Screener] Loaded {len(df)} rows from LanceDB")
            return df

        if not Config.parquet_fallback_enabled():
            print("[Screener] No LanceDB data and Parquet fallback is disabled")
            return None
        
        parquet_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data', 'parquet_data', 'stock_daily.parquet'
        )
        
        if os.path.exists(parquet_path):
            print(f"[Screener] Loading from Parquet: {parquet_path}")
            
            if target_date:
                df = pl.scan_parquet(parquet_path).filter(pl.col('trade_date') == target_date).collect()
                print(f"[Screener] Loaded {len(df)} rows for {target_date}")
            else:
                df = pl.read_parquet(parquet_path)
                print(f"[Screener] Loaded {len(df)} rows from Parquet")
            return df
        
        from data_svc.unified_data_manager import get_unified_manager
        
        manager = get_unified_manager()
        
        if manager._cache_loaded and 'stock_daily' in manager._memory_cache:
            for cache_key, df in manager._memory_cache['stock_daily'].items():
                if not df.is_empty():
                    if target_date and 'trade_date' in df.columns:
                        df = df.filter(pl.col('trade_date') == target_date)
                    print(f"[Screener] Using cached data: {len(df)} rows")
                    return df
        
        return None
        
    except Exception as e:
        print(f"[Screener] Error getting all stocks data: {e}")
        import traceback
        traceback.print_exc()
        return None


def clean_nan_values(obj):
    """
    递归清理对象中的 NaN 值，将其转换为 None
    """
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def get_factor_data_for_date(target_date: str) -> Optional[pl.DataFrame]:
    """
    获取指定日期的所有股票因子数据
    
    默认从 LanceDB factors 表读取；仅显式启用后才回退到 Parquet。
    
    Args:
        target_date: 目标日期，格式 'YYYY-MM-DD'
        
    Returns:
        包含因子数据的 Polars DataFrame
    """
    try:
        reader = get_lancedb()
        df = reader.read_table("factors", None, target_date, target_date, fields=None)
        if df is not None and not df.is_empty():
            if 'stock_code' in df.columns:
                df = df.with_columns(
                    pl.col('stock_code').str.split('.').list.get(0).alias('stock_code')
                )
            print(f"[Screener] Loaded factor data from LanceDB for {len(df)} stocks on {target_date}")
            return df

        if not Config.parquet_fallback_enabled():
            print(f"[Screener] No LanceDB factor data for {target_date}; Parquet fallback is disabled")
            return None

        from datetime import datetime
        
        parquet_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data', 'parquet_data', 'factors_momentum_hot.parquet'
        )
        
        if not os.path.exists(parquet_path):
            print(f"[Screener] Factor parquet not found: {parquet_path}")
            return None
        
        lazy_df = pl.scan_parquet(parquet_path)
        
        actual_dtype = lazy_df.collect_schema()['trade_date']
        
        if actual_dtype == pl.String:
            df = lazy_df.filter(pl.col('trade_date') == target_date).collect()
        elif actual_dtype == pl.Date:
            target_dt = datetime.strptime(target_date, '%Y-%m-%d').date()
            df = lazy_df.filter(pl.col('trade_date') == target_dt).collect()
        else:
            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
            df = lazy_df.filter(pl.col('trade_date') == target_dt).collect()
        
        if df.is_empty():
            print(f"[Screener] No factor data for {target_date}")
            return None
        
        if 'stock_code' in df.columns:
            df = df.with_columns(
                pl.col('stock_code').str.split('.').list.get(0).alias('stock_code')
            )
        
        print(f"[Screener] Loaded factor data for {len(df)} stocks on {target_date}")
        
        return df
        
    except Exception as e:
        print(f"[Screener] Error getting factor data: {e}")
        import traceback
        traceback.print_exc()
        return None


def merge_factor_data(stock_df: pl.DataFrame, target_date: str) -> pl.DataFrame:
    """
    合并股票日线数据和因子数据
    
    Args:
        stock_df: 股票日线数据
        target_date: 目标日期
        
    Returns:
        合并后的 DataFrame
    """
    try:
        factor_df = get_factor_data_for_date(target_date)
        
        if factor_df is None or factor_df.is_empty():
            print("[Screener] No factor data to merge")
            return stock_df
        
        exclude_cols = {'stock_code', 'trade_date', 'date'}
        factor_cols = [c for c in factor_df.columns if c not in exclude_cols]
        
        print(f"[Screener] Merging {len(factor_cols)} factor columns for {len(factor_df)} stocks")
        
        factor_select = factor_df.select(['stock_code'] + factor_cols)
        
        for col in ['ma5', 'ma10', 'ma20']:
            if col in stock_df.columns:
                stock_df = stock_df.drop(col)
        
        merged = stock_df.join(factor_select, on='stock_code', how='left')
        
        return merged
        
    except Exception as e:
        print(f"[Screener] Error merging factor data: {e}")
        import traceback
        traceback.print_exc()
        return stock_df


INDICATOR_CATEGORIES = {
    'basic': {
        'name': '基础信息',
        'indicators': [
            {'field': 'stock_code', 'name': '股票代码', 'type': 'text'},
            {'field': 'stock_name', 'name': '股票名称', 'type': 'text'},
            {'field': 'trade_date', 'name': '交易日期', 'type': 'date'},
        ]
    },
    'price_volume': {
        'name': '价格与成交量',
        'indicators': [
            {'field': 'close', 'name': '收盘价', 'type': 'number', 'unit': '元'},
            {'field': 'open', 'name': '开盘价', 'type': 'number', 'unit': '元'},
            {'field': 'high', 'name': '最高价', 'type': 'number', 'unit': '元'},
            {'field': 'low', 'name': '最低价', 'type': 'number', 'unit': '元'},
            {'field': 'change_pct', 'name': '涨跌幅', 'type': 'number', 'unit': '%'},
            {'field': 'volume', 'name': '成交量', 'type': 'number', 'unit': '手'},
            {'field': 'amount', 'name': '成交额', 'type': 'number', 'unit': '元'},
            {'field': 'turnover_rate', 'name': '换手率', 'type': 'number', 'unit': '%'},
            {'field': 'volume_ratio', 'name': '量比', 'type': 'number'},
        ]
    },
    'moving_average': {
        'name': '均线类',
        'indicators': [
            {'field': 'ma5', 'name': 'MA5', 'type': 'number', 'unit': '元'},
            {'field': 'ma10', 'name': 'MA10', 'type': 'number', 'unit': '元'},
            {'field': 'ma20', 'name': 'MA20', 'type': 'number', 'unit': '元'},
            {'field': 'ma3_avg_price', 'name': 'MA3均价', 'type': 'number', 'unit': '元'},
            {'field': 'ma5_avg_price', 'name': 'MA5均价', 'type': 'number', 'unit': '元'},
            {'field': 'ma10_avg_price', 'name': 'MA10均价', 'type': 'number', 'unit': '元'},
            {'field': 'volume_ma5', 'name': '5日均量', 'type': 'number', 'unit': '手'},
        ]
    },
    'valuation': {
        'name': '估值与市值',
        'indicators': [
            {'field': 'pe', 'name': '市盈率PE', 'type': 'number'},
            {'field': 'pe_ttm', 'name': '市盈率TTM', 'type': 'number'},
            {'field': 'pb', 'name': '市净率PB', 'type': 'number'},
            {'field': 'ps', 'name': '市销率PS', 'type': 'number'},
            {'field': 'ps_ttm', 'name': '市销率TTM', 'type': 'number'},
            {'field': 'total_mv', 'name': '总市值', 'type': 'number', 'unit': '万元'},
            {'field': 'float_mv', 'name': '流通市值', 'type': 'number', 'unit': '万元'},
        ]
    },
    'momentum': {
        'name': '动量类',
        'indicators': [
            {'field': 'rsi_6', 'name': 'RSI(6)', 'type': 'number'},
            {'field': 'rsi_12', 'name': 'RSI(12)', 'type': 'number'},
            {'field': 'rsi_24', 'name': 'RSI(24)', 'type': 'number'},
            {'field': 'macd_dif', 'name': 'MACD DIF', 'type': 'number'},
            {'field': 'macd_dea', 'name': 'MACD DEA', 'type': 'number'},
            {'field': 'macd_bar', 'name': 'MACD 柱状线', 'type': 'number'},
            {'field': 'kdj_k', 'name': 'KDJ K', 'type': 'number'},
            {'field': 'kdj_d', 'name': 'KDJ D', 'type': 'number'},
            {'field': 'kdj_j', 'name': 'KDJ J', 'type': 'number'},
            {'field': 'wr_14', 'name': 'W%R(14)', 'type': 'number'},
            {'field': 'cci_14', 'name': 'CCI(14)', 'type': 'number'},
        ]
    },
    'trend': {
        'name': '趋势类',
        'indicators': [
            {'field': 'boll_upper', 'name': '布林带上轨', 'type': 'number', 'unit': '元'},
            {'field': 'boll_mid', 'name': '布林带中轨', 'type': 'number', 'unit': '元'},
            {'field': 'boll_lower', 'name': '布林带下轨', 'type': 'number', 'unit': '元'},
            {'field': 'bb_width_20', 'name': '布林带宽度', 'type': 'number', 'unit': '%'},
            {'field': 'ema12', 'name': 'EMA12', 'type': 'number', 'unit': '元'},
            {'field': 'ema26', 'name': 'EMA26', 'type': 'number', 'unit': '元'},
            {'field': 'ema50', 'name': 'EMA50', 'type': 'number', 'unit': '元'},
            {'field': 'ema200', 'name': 'EMA200', 'type': 'number', 'unit': '元'},
            {'field': 'dmi_pdi', 'name': 'DMI +DI', 'type': 'number'},
            {'field': 'dmi_mdi', 'name': 'DMI -DI', 'type': 'number'},
            {'field': 'dmi_adx', 'name': 'DMI ADX', 'type': 'number'},
            {'field': 'trix_12', 'name': 'TRIX(12)', 'type': 'number'},
        ]
    },
    'volume_energy': {
        'name': '能量/成交量类',
        'indicators': [
            {'field': 'obv', 'name': 'OBV', 'type': 'number'},
            {'field': 'vwap_20', 'name': 'VWAP(20)', 'type': 'number', 'unit': '元'},
            {'field': 'vr_26', 'name': 'VR(26)', 'type': 'number'},
            {'field': 'bias_6', 'name': 'BIAS(6)', 'type': 'number', 'unit': '%'},
            {'field': 'bias_12', 'name': 'BIAS(12)', 'type': 'number', 'unit': '%'},
            {'field': 'bias_24', 'name': 'BIAS(24)', 'type': 'number', 'unit': '%'},
            {'field': 'mfi_14', 'name': 'MFI(14)', 'type': 'number'},
            {'field': 'volume_std_20d', 'name': '成交量标准差(20)', 'type': 'number'},
        ]
    },
    'volatility': {
        'name': '波动率类',
        'indicators': [
            {'field': 'hv_20d', 'name': '历史波动率(20)', 'type': 'number', 'unit': '%'},
            {'field': 'hv_60d', 'name': '历史波动率(60)', 'type': 'number', 'unit': '%'},
            {'field': 'atr_14', 'name': 'ATR(14)', 'type': 'number', 'unit': '元'},
            {'field': 'atr_ratio_14_50', 'name': 'ATR比例(14/50)', 'type': 'number'},
        ]
    },
    'statistical': {
        'name': '统计衍生指标',
        'indicators': [
            {'field': 'ret_5d', 'name': '5日收益率', 'type': 'number', 'unit': '%'},
            {'field': 'ret_20d', 'name': '20日收益率', 'type': 'number', 'unit': '%'},
            {'field': 'ret_60d', 'name': '60日收益率', 'type': 'number', 'unit': '%'},
            {'field': 'volatility_20d', 'name': '20日波动率', 'type': 'number'},
            {'field': 'max_drawdown_20d', 'name': '最大回撤(20)', 'type': 'number', 'unit': '%'},
            {'field': 'max_drawdown_60d', 'name': '最大回撤(60)', 'type': 'number', 'unit': '%'},
            {'field': 'max_drawdown_250d', 'name': '最大回撤(250)', 'type': 'number', 'unit': '%'},
            {'field': 'sharpe_20d', 'name': '夏普比率(20)', 'type': 'number'},
            {'field': 'sortino_250d', 'name': 'Sortino比率(250)', 'type': 'number'},
            {'field': 'calmar_250d', 'name': 'Calmar比率(250)', 'type': 'number'},
            {'field': 'var_95_250d', 'name': 'VaR 95%(250)', 'type': 'number', 'unit': '%'},
            {'field': 'ma_bull_alignment', 'name': '均线多头排列', 'type': 'boolean'},
            {'field': 'golden_cross', 'name': '金叉标记', 'type': 'boolean'},
            {'field': 'death_cross', 'name': '死叉标记', 'type': 'boolean'},
            {'field': 'macd_golden_cross', 'name': 'MACD金叉', 'type': 'boolean'},
            {'field': 'macd_death_cross', 'name': 'MACD死叉', 'type': 'boolean'},
        ]
    },
    'market_risk': {
        'name': '市场基准相关',
        'indicators': [
            {'field': 'beta_60d', 'name': 'Beta(60)', 'type': 'number'},
            {'field': 'beta_120d', 'name': 'Beta(120)', 'type': 'number'},
            {'field': 'beta_250d', 'name': 'Beta(250)', 'type': 'number'},
            {'field': 'alpha_60d', 'name': 'Alpha(60)', 'type': 'number', 'unit': '%'},
            {'field': 'alpha_120d', 'name': 'Alpha(120)', 'type': 'number', 'unit': '%'},
            {'field': 'alpha_250d', 'name': 'Alpha(250)', 'type': 'number', 'unit': '%'},
            {'field': 'corr_60d', 'name': '相关系数(60)', 'type': 'number'},
            {'field': 'corr_120d', 'name': '相关系数(120)', 'type': 'number'},
            {'field': 'corr_250d', 'name': '相关系数(250)', 'type': 'number'},
            {'field': 'excess_ret_20d', 'name': '超额收益(20)', 'type': 'number', 'unit': '%'},
            {'field': 'ir_250d', 'name': '信息比率(250)', 'type': 'number'},
        ]
    }
}

OPERATORS = {
    'number': [
        {'value': '>', 'label': '大于', 'input': 'single'},
        {'value': '<', 'label': '小于', 'input': 'single'},
        {'value': '=', 'label': '等于', 'input': 'single'},
        {'value': '>=', 'label': '大于等于', 'input': 'single'},
        {'value': '<=', 'label': '小于等于', 'input': 'single'},
        {'value': 'between', 'label': '介于', 'input': 'range'},
        {'value': 'top', 'label': '前N%', 'input': 'percent'},
        {'value': 'bottom', 'label': '后N%', 'input': 'percent'},
    ],
    'text': [
        {'value': 'contains', 'label': '包含', 'input': 'single'},
        {'value': '=', 'label': '等于', 'input': 'single'},
        {'value': 'starts_with', 'label': '开头于', 'input': 'single'},
    ],
    'boolean': [
        {'value': '=', 'label': '等于', 'input': 'boolean'},
    ],
    'date': [
        {'value': '=', 'label': '等于', 'input': 'single'},
        {'value': '>=', 'label': '大于等于', 'input': 'single'},
        {'value': '<=', 'label': '小于等于', 'input': 'single'},
        {'value': 'between', 'label': '介于', 'input': 'range'},
    ]
}

def get_latest_trade_date() -> str:
    """获取最新有实际数据的交易日 - 使用缓存"""
    global _dates_cache
    
    if _dates_cache['latest'] is not None:
        return _dates_cache['latest']
    
    dates = get_all_trade_dates()
    if dates:
        return dates[0]
    
    return datetime.now().strftime('%Y-%m-%d')


def apply_filter_conditions(df: pl.LazyFrame, conditions: List[Dict], logic: str = 'AND') -> pl.LazyFrame:
    """
    应用筛选条件到 LazyFrame
    """
    if not conditions:
        return df

    filters = []
    for cond in conditions:
        field = cond.get('field')
        operator = cond.get('operator')
        value = cond.get('value')
        value2 = cond.get('value2')

        if not field or not operator:
            continue

        col = pl.col(field)

        if operator == '>':
            filters.append(col > float(value))
        elif operator == '<':
            filters.append(col < float(value))
        elif operator == '=':
            filters.append(col == float(value))
        elif operator == '>=':
            filters.append(col >= float(value))
        elif operator == '<=':
            filters.append(col <= float(value))
        elif operator == 'between':
            filters.append((col >= float(value)) & (col <= float(value2)))
        elif operator == 'contains':
            filters.append(col.str.contains(str(value)))
        elif operator == 'starts_with':
            filters.append(col.str.starts_with(str(value)))

    if not filters:
        return df

    if logic == 'OR':
        combined = filters[0]
        for f in filters[1:]:
            combined = combined | f
    else:
        combined = filters[0]
        for f in filters[1:]:
            combined = combined & f

    return df.filter(combined)


def apply_filter_conditions_pl(df: pl.DataFrame, conditions: List[Dict], logic: str = 'AND') -> pl.DataFrame:
    """
    应用筛选条件到 Polars DataFrame
    
    与 apply_filter_conditions 相同，但适用于 Eager DataFrame
    """
    if not conditions:
        return df

    filters = []
    for cond in conditions:
        field = cond.get('field')
        operator = cond.get('operator') or cond.get('op')
        value = cond.get('value')
        value2 = cond.get('value2')

        if not field or not operator:
            continue

        col = pl.col(field)

        try:
            if operator == '>':
                filters.append(col > float(value))
            elif operator == '<':
                filters.append(col < float(value))
            elif operator == '=':
                filters.append(col == float(value))
            elif operator == '>=':
                filters.append(col >= float(value))
            elif operator == '<=':
                filters.append(col <= float(value))
            elif operator == 'between':
                filters.append((col >= float(value)) & (col <= float(value2)))
            elif operator == 'contains':
                filters.append(col.str.contains(str(value)))
            elif operator == 'starts_with':
                filters.append(col.str.starts_with(str(value)))
        except (ValueError, TypeError):
            continue

    if not filters:
        return df

    if logic == 'OR':
        combined = filters[0]
        for f in filters[1:]:
            combined = combined | f
    else:
        combined = filters[0]
        for f in filters[1:]:
            combined = combined & f

    return df.filter(combined)


@screener_bp.route('/indicators', methods=['GET'])
def get_indicators():
    """获取所有可用指标列表"""
    return jsonify({
        'success': True,
        'data': {
            'categories': INDICATOR_CATEGORIES,
            'operators': OPERATORS
        }
    })


def compute_technical_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算技术指标因子
    
    Args:
        df: 包含历史数据的 DataFrame，必须有 stock_code, trade_date, close, high, low, volume 列
        
    Returns:
        添加了因子列的 DataFrame
    """
    if df.empty:
        return df
    
    # 按股票代码分组计算
    result_dfs = []
    
    for stock_code, group in df.groupby('stock_code'):
        group = group.sort_values('trade_date')
        
        # RSI 计算
        close_prices = group['close'].values
        deltas = np.diff(close_prices)
        
        # RSI(6)
        if len(deltas) >= 6:
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains[-6:])
            avg_loss = np.mean(losses[-6:])
            if avg_loss == 0:
                group['rsi_6'] = 100.0
            else:
                rs = avg_gain / avg_loss
                group['rsi_6'] = 100 - (100 / (1 + rs))
        else:
            group['rsi_6'] = np.nan
            
        # RSI(12)
        if len(deltas) >= 12:
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains[-12:])
            avg_loss = np.mean(losses[-12:])
            if avg_loss == 0:
                group['rsi_12'] = 100.0
            else:
                rs = avg_gain / avg_loss
                group['rsi_12'] = 100 - (100 / (1 + rs))
        else:
            group['rsi_12'] = np.nan
            
        # RSI(24)
        if len(deltas) >= 24:
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains[-24:])
            avg_loss = np.mean(losses[-24:])
            if avg_loss == 0:
                group['rsi_24'] = 100.0
            else:
                rs = avg_gain / avg_loss
                group['rsi_24'] = 100 - (100 / (1 + rs))
        else:
            group['rsi_24'] = np.nan
        
        # MACD 计算
        if len(close_prices) >= 26:
            exp1 = group['close'].ewm(span=12, adjust=False).mean()
            exp2 = group['close'].ewm(span=26, adjust=False).mean()
            macd_dif = exp1 - exp2
            macd_dea = macd_dif.ewm(span=9, adjust=False).mean()
            macd_bar = 2 * (macd_dif - macd_dea)
            
            group['macd_dif'] = macd_dif
            group['macd_dea'] = macd_dea
            group['macd_bar'] = macd_bar
            
            # MACD 金叉/死叉
            group['macd_golden_cross'] = (macd_dif > macd_dea) & (macd_dif.shift(1) <= macd_dea.shift(1))
            group['macd_death_cross'] = (macd_dif < macd_dea) & (macd_dif.shift(1) >= macd_dea.shift(1))
        else:
            group['macd_dif'] = np.nan
            group['macd_dea'] = np.nan
            group['macd_bar'] = np.nan
            group['macd_golden_cross'] = False
            group['macd_death_cross'] = False
        
        # KDJ 计算
        if len(group) >= 9:
            low_list = group['low'].rolling(window=9, min_periods=9).min()
            high_list = group['high'].rolling(window=9, min_periods=9).max()
            rsv = (group['close'] - low_list) / (high_list - low_list) * 100
            
            # K值
            k = rsv.ewm(com=2, adjust=False).mean()
            # D值
            d = k.ewm(com=2, adjust=False).mean()
            # J值
            j = 3 * k - 2 * d
            
            group['kdj_k'] = k
            group['kdj_d'] = d
            group['kdj_j'] = j
        else:
            group['kdj_k'] = np.nan
            group['kdj_d'] = np.nan
            group['kdj_j'] = np.nan
        
        # 布林带计算
        if len(close_prices) >= 20:
            ma20 = group['close'].rolling(window=20).mean()
            std20 = group['close'].rolling(window=20).std()
            group['boll_mid'] = ma20
            group['boll_upper'] = ma20 + 2 * std20
            group['boll_lower'] = ma20 - 2 * std20
            group['bb_width_20'] = (group['boll_upper'] - group['boll_lower']) / ma20 * 100
        else:
            group['boll_mid'] = np.nan
            group['boll_upper'] = np.nan
            group['boll_lower'] = np.nan
            group['bb_width_20'] = np.nan
        
        # 均线多头排列
        if len(close_prices) >= 20:
            ma5 = group['close'].rolling(window=5).mean()
            ma10 = group['close'].rolling(window=10).mean()
            ma20 = group['close'].rolling(window=20).mean()
            group['ma_bullish_arrangement'] = (ma5 > ma10) & (ma10 > ma20)
        else:
            group['ma_bullish_arrangement'] = False
        
        # 5日、20日、60日收益
        if len(close_prices) >= 6:
            group['return_5d'] = (close_prices[-1] - close_prices[-6]) / close_prices[-6] * 100
        else:
            group['return_5d'] = np.nan
            
        if len(close_prices) >= 21:
            group['return_20d'] = (close_prices[-1] - close_prices[-21]) / close_prices[-21] * 100
        else:
            group['return_20d'] = np.nan
            
        if len(close_prices) >= 61:
            group['return_60d'] = (close_prices[-1] - close_prices[-61]) / close_prices[-61] * 100
        else:
            group['return_60d'] = np.nan
        
        # 20日波动率
        if len(close_prices) >= 21:
            returns = np.diff(close_prices[-21:]) / close_prices[-22:-1]
            group['volatility_20d'] = np.std(returns) * np.sqrt(252) * 100
        else:
            group['volatility_20d'] = np.nan
        
        # 20日最大回撤
        if len(close_prices) >= 21:
            recent_prices = close_prices[-21:]
            peak = np.maximum.accumulate(recent_prices)
            drawdown = (recent_prices - peak) / peak
            group['max_drawdown_20d'] = drawdown[-1] * 100
        else:
            group['max_drawdown_20d'] = np.nan
        
        result_dfs.append(group)
    
    return pd.concat(result_dfs, ignore_index=True)


@screener_bp.route('/filter', methods=['POST'])
def filter_stocks():
    """
    股票筛选接口 - 优化版本
    
    使用优化后的 ScreenerDataService：
    1. 批量读取 - Polars Lazy API
    2. 限制日期范围 - 只读取指定日期
    3. 只读指定列 - 根据筛选条件动态确定
    4. 内存缓存 - 避免重复读取
    5. 纯 Polars - 避免 Pandas 转换开销
    """
    try:
        from server.routes.screener_data_service import get_screener_service
        import time
        
        start_time = time.perf_counter()
        
        data = request.get_json() or {}
        date = data.get('date') or get_latest_trade_date()
        conditions = data.get('conditions') or data.get('filters', [])
        logic = data.get('logic', 'AND')
        order_by = data.get('order_by', [])
        page = int(data.get('page', 1))
        page_size = int(data.get('page_size', 20))
        fields = data.get('fields', [])
        
        print(f"[Screener] ========== 开始筛选 ==========")
        print(f"[Screener] 请求参数: date={date}, conditions={len(conditions)}, fields={len(fields)}, logic={logic}")
        print(f"[Screener] fields={fields[:10] if fields else 'all'}")
        print(f"[Screener] conditions={conditions}")
        
        # 获取优化数据服务
        service = get_screener_service()
        
        # 获取数据（自动缓存）
        df = service.get_data(date=date, fields=fields, conditions=conditions)
        
        if df is None or df.is_empty():
            print(f"[Screener] ERROR: 无法获取股票数据或该日期无数据: {date}")
            return jsonify({
                'success': False,
                'error': f'无法获取股票数据或该日期无数据: {date}'
            }), 404
        
        print(f"[Screener] ========== 数据加载结果 ==========")
        print(f"[Screener] 数据加载完成: shape={df.shape}, columns={len(df.columns)}")
        print(f"[Screener] 列名: {list(df.columns)[:15]}...")
        
        # 检查关键字段
        print(f"[Screener] ========== 关键字段检查 ==========")
        if 'stock_name' in df.columns:
            null_count = df['stock_name'].null_count()
            non_null_count = len(df) - null_count
            print(f"[Screener] stock_name: 成功 {non_null_count}/{len(df)}, 空值 {null_count}/{len(df)}")
        else:
            print(f"[Screener] WARNING: stock_name 列不存在")
        
        # 检查因子字段
        factor_cols = ['corr_60d', 'beta_60d', 'alpha_60d']
        for col in factor_cols:
            if col in df.columns:
                null_count = df[col].null_count()
                non_null_count = len(df) - null_count
                print(f"[Screener] {col}: 成功 {non_null_count}/{len(df)}, 空值 {null_count}/{len(df)}")
            else:
                print(f"[Screener] WARNING: {col} 列不存在")
        
        # 应用筛选条件
        df_filtered = service.apply_filter_optimized(df, conditions, logic)
        
        print(f"[Screener] ========== 筛选结果 ==========")
        print(f"[Screener] 筛选后: {len(df_filtered)} 行 (原始 {len(df)} 行)")
        
        # 获取总数
        total = df_filtered.height
        
        # 排序
        if order_by:
            for ob in reversed(order_by):
                field = ob.get('field')
                direction = ob.get('direction', 'asc').lower()
                if field and field in df_filtered.columns:
                    # 使用 nulls_last=True 确保 null 值排在最后
                    df_filtered = df_filtered.sort(field, descending=(direction == 'desc'), nulls_last=True)
        else:
            if 'total_mv' in df_filtered.columns:
                df_filtered = df_filtered.sort('total_mv', descending=True, nulls_last=True)
        
        # 分页
        offset = (page - 1) * page_size
        df_paged = df_filtered.slice(offset, page_size)
        
        # 选择字段
        if fields:
            select_fields = [f for f in fields if f in df_paged.columns]
        else:
            exclude_fields = {'_id', 'id', 'created_at', 'updated_at'}
            select_fields = [f for f in df_paged.columns if f not in exclude_fields]
        
        df_paged = df_paged.select(select_fields)
        
        # 转换为字典（使用 Polars 直接转换，避免 Pandas）
        records = df_paged.to_dicts()
        records = clean_nan_values(records)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"[Screener] ========== 查询完成: total={total}, 耗时={elapsed:.2f}ms ==========")
        
        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size,
                'date': date,
                'records': records
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@screener_bp.route('/dates', methods=['GET'])
def get_trade_dates():
    """获取可用交易日列表"""
    print("[Screener] GET /api/screener/dates called")
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        print(f"[Screener] start_date={start_date}, end_date={end_date}")

        dates = get_all_trade_dates()
        print(f"[Screener] get_all_trade_dates returned {len(dates)} dates")
        
        if not dates:
            print("[Screener] Falling back to get_stock_daily_df")
            pdf = get_stock_daily_df()
            if pdf is not None and not pdf.is_empty() and 'trade_date' in pdf.columns:
                dates = pdf.select('trade_date').unique().to_series().to_list()
                dates = sorted([str(d) for d in dates], reverse=True)
                print(f"[Screener] Fallback returned {len(dates)} dates")
        
        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]
        
        latest = get_latest_trade_date() if dates else ''
        print(f"[Screener] Returning {len(dates)} dates, latest={latest}")

        return jsonify({
            'success': True,
            'data': {
                'dates': dates,
                'latest': latest
            }
        })

    except Exception as e:
        print(f"[Screener] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@screener_bp.route('/stock/<stock_code>', methods=['GET'])
def get_stock_history(stock_code: str):
    """获取单只股票的历史数据"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))

        df = get_stock_daily_df()
        if df is None or df.is_empty():
            return jsonify({'success': False, 'error': '无法连接数据库'}), 500

        candidates = [stock_code, f"{stock_code}.SZ", f"{stock_code}.SH", f"{stock_code}.BJ"]
        code_cols = [c for c in ("stock_code", "ts_code", "code", "symbol") if c in df.columns]
        if not code_cols:
            return jsonify({'success': False, 'error': '数据缺少股票代码字段'}), 500

        mask = None
        for col in code_cols:
            col_mask = pl.col(col).cast(pl.Utf8).is_in(candidates)
            mask = col_mask if mask is None else (mask | col_mask)
        df = df.filter(mask)

        if df.is_empty():
            return jsonify({'success': False, 'error': f'股票 {stock_code} 不存在'}), 404
        
        # 日期过滤
        date_col = 'trade_date' if 'trade_date' in df.columns else 'trade_date_basic'
        
        if start_date:
            if date_col == 'trade_date_basic':
                start_date_fmt = start_date.replace('-', '')
                df = df.filter(pl.col(date_col) >= start_date_fmt)
            else:
                df = df.filter(pl.col(date_col) >= start_date)
        
        if end_date:
            if date_col == 'trade_date_basic':
                end_date_fmt = end_date.replace('-', '')
                df = df.filter(pl.col(date_col) <= end_date_fmt)
            else:
                df = df.filter(pl.col(date_col) <= end_date)
        
        # 排序并限制数量
        df = df.sort(date_col, descending=True).head(limit)
        
        records = df.to_dicts()
        records = clean_nan_values(records)

        return jsonify({
            'success': True,
            'data': records
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@screener_bp.route('/rank', methods=['POST'])
def rank_stocks():
    """股票排名接口"""
    try:
        data = request.get_json() or {}

        date = data.get('date') or get_latest_trade_date()
        field = data.get('field', 'total_mv')
        direction = data.get('direction', 'desc')
        page = int(data.get('page', 1))
        page_size = int(data.get('page_size', 20))

        # 从当前数据后端获取数据
        df = get_all_stocks_daily_df(target_date=date, fields=[field])
        
        if df is None or df.is_empty():
            return jsonify({'success': False, 'error': f'该日期无数据: {date}'}), 404

        total = df.height

        # 排序
        if field in df.columns:
            df = df.sort(field, descending=(direction == 'desc'))
        
        # 分页
        offset = (page - 1) * page_size
        df = df.slice(offset, page_size)

        records = df.to_dicts()
        records = clean_nan_values(records)

        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size,
                'date': date,
                'field': field,
                'direction': direction,
                'records': records
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@screener_bp.route('/stats', methods=['GET'])
def get_field_stats():
    """获取字段统计信息"""
    try:
        date = request.args.get('date') or get_latest_trade_date()
        field = request.args.get('field', 'close')

        # 从当前数据后端获取数据
        df = get_all_stocks_daily_df(target_date=date, fields=[field])
        
        if df is None or df.is_empty():
            return jsonify({'success': False, 'error': f'该日期无数据: {date}'}), 404
        
        if field not in df.columns:
            return jsonify({'success': False, 'error': f'字段不存在: {field}'}), 400

        stats = df.select([
            pl.col(field).min().alias('min'),
            pl.col(field).max().alias('max'),
            pl.col(field).mean().alias('mean'),
            pl.col(field).median().alias('median'),
            pl.col(field).std().alias('std'),
            pl.col(field).quantile(0.25).alias('q25'),
            pl.col(field).quantile(0.75).alias('q75'),
        ])

        result = {
            'min': stats['min'].item(),
            'max': stats['max'].item(),
            'mean': stats['mean'].item(),
            'median': stats['median'].item(),
            'std': stats['std'].item(),
            'q25': stats['q25'].item(),
            'q75': stats['q75'].item(),
        }

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
