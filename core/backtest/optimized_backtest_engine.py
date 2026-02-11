# backtest/optimized_backtest_engine.py
"""
优化的回测引擎 - Polars + CuPy + Numba 架构

架构说明：
1. 数据加载：使用 Polars 加载 Parquet，立即转换为 NumPy 数组
2. 指标计算：在 GPU (CuPy) 上计算技术指标，然后移回 CPU
3. 执行循环：使用 Numba JIT 编译的快速循环函数
4. 策略接口：保持与现有策略接口兼容

性能优化：
- GPU 加速的指标计算
- Numba JIT 编译的执行循环
- 向量化的数据处理

注意：此类现在继承自 FlexibleBacktestEngine，以获得完整的回测功能。
"""

import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import Dict, Any, Generator, Tuple, List, Optional
from threading import Event
import time
import os
from pathlib import Path
import hashlib
import json
from functools import lru_cache

# 导入 FlexibleBacktestEngine 以实现继承
from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine

# 可选依赖导入
try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False
    cp = None

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

try:
    import numba
    from numba import jit, types, int64
    from numba.typed import List
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    numba = None
    jit = lambda *args, **kwargs: lambda f: f
    int64 = None
    List = None


def _make_json_serializable(obj: Any, max_depth: int = 10, _current_depth: int = 0) -> Any:
    """
    递归将对象转换为 JSON 可序列化的类型。
    
    处理以下类型：
    - 基本类型：int, float, str, bool, None（直接返回）
    - 列表/元组：递归处理每个元素
    - 字典：递归处理每个值
    - numpy 数组：调用 tolist()
    - pandas 对象：DataFrame/Series 转为 dict，Timestamp 转为 ISO 字符串
    - datetime/date 对象：转为 ISO 字符串
    - set/frozenset：转为排序后的列表
    - 具有 __dict__ 的对象：递归处理属性
    - 未知类型：尝试 str()，失败返回 None
    
    参数:
        obj: 要序列化的对象
        max_depth: 最大递归深度（防止无限递归）
        _current_depth: 当前递归深度（内部使用）
    
    返回:
        JSON 可序列化的对象
    """
    # 防止无限递归
    if _current_depth > max_depth:
        return None
    
    # [Modified] 任务D：JSON兼容性加固 - 添加isinf检查
    # 基本类型直接返回，但需处理无穷大值
    if obj is None or isinstance(obj, bool):
        return obj
    elif isinstance(obj, (int, float)):
        # 处理无穷大值：isinf -> None
        import math
        if isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj)):
            return None
        elif hasattr(obj, 'item'):  # numpy 标量
            try:
                val = obj.item()
                if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                    return None
            except:
                pass
        return obj
    elif isinstance(obj, str):
        return obj
    
    # 处理 numpy 类型
    if hasattr(obj, 'tolist'):
        try:
            return obj.tolist()
        except (AttributeError, ValueError):
            pass
    elif isinstance(obj, np.generic):
        # numpy 标量类型
        try:
            return float(obj) if isinstance(obj, (np.floating, np.integer)) else str(obj)
        except (ValueError, TypeError):
            return None
    
    # 处理 pandas DataFrame 和 Series
    if isinstance(obj, pd.DataFrame):
        return _make_json_serializable(obj.to_dict('records'), max_depth, _current_depth)
    if isinstance(obj, pd.Series):
        return _make_json_serializable(obj.to_dict(), max_depth, _current_depth)
    
    # 处理 pandas 特定类型
    if isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
        try:
            return obj.isoformat()
        except (AttributeError, ValueError):
            return str(obj)
    if isinstance(obj, (pd.Period, pd.Interval)):
        return str(obj)
    
    # 处理 datetime/date 对象
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # 处理列表和元组
    if isinstance(obj, (list, tuple)):
        result = []
        for item in obj:
            try:
                result.append(_make_json_serializable(item, max_depth, _current_depth + 1))
            except Exception:
                result.append(str(item))
        return result if isinstance(obj, list) else tuple(result)
    
    # 处理字典
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            try:
                # 确保 key 也是可序列化的
                key = _make_json_serializable(k, max_depth, _current_depth + 1) if not isinstance(k, (str, int, float, bool)) else k
                if key is not None:
                    result[key] = _make_json_serializable(v, max_depth, _current_depth + 1)
            except Exception:
                pass
        return result
    
    # 处理 set/frozenset
    if isinstance(obj, (set, frozenset)):
        try:
            sorted_items = sorted(_make_json_serializable(list(obj), max_depth, _current_depth + 1))
            return sorted_items
        except (TypeError, ValueError):
            return list(obj)
    
    # 处理具有 __dict__ 的对象
    if hasattr(obj, '__dict__'):
        try:
            result = {}
            for k, v in obj.__dict__.items():
                # 跳过私有属性和不可序列化的属性
                if k.startswith('_'):
                    continue
                try:
                    result[k] = _make_json_serializable(v, max_depth, _current_depth + 1)
                except Exception:
                    pass
            return result
        except Exception:
            pass
    
    # 最后尝试 str()
    try:
        return str(obj)
    except Exception:
        return None


class OptimizedBacktestEngine(FlexibleBacktestEngine):
    """
    优化的回测引擎 - 继承自 FlexibleBacktestEngine
    
    此类保持向后兼容性，实际功能由 FlexibleBacktestEngine 提供。
    FlexibleBacktestEngine 已包含：
    - 多种时间粒度支持（日线、分钟线、tick）
    - datetime 对象统一处理
    - 流式数据加载
    - LRU 缓存优化
    - 向量化计算
    """
    
    def __init__(
        self,
        data_query,
        initial_capital: float = 1_000_000,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
        time_granularity: str = 'daily'
    ):
        """
        初始化优化的回测引擎
        
        参数：
            data_query: 数据查询对象
            initial_capital: 初始资金（默认100万）
            commission_rate: 手续费率（默认0.03%）
            min_commission: 最小手续费（默认5元）
            time_granularity: 时间粒度 ('daily', 'minute', 'tick')
        """
        super().__init__(
            data_query=data_query,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            min_commission=min_commission,
            time_granularity=time_granularity
        )
        
        # 保留原有初始化日志以保持兼容性
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.info(f"✅ OptimizedBacktestEngine 初始化完成 (资金: {initial_capital:,.0f}, 粒度: {time_granularity})")
