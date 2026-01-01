"""
股票代码规范化工具函数
"""
import re
from typing import Optional


def normalize_symbol_code(symbol_code: Optional[str]) -> str:
    """
    规范化股票代码为6位数字格式
    
    Args:
        symbol_code: 原始股票代码（可能包含sz/sh前缀）
    
    Returns:
        6位数字股票代码
    """
    if not symbol_code:
        return ''
    code = str(symbol_code).strip().upper()
    match = re.search(r'(\d{6})', code)
    return match.group(1) if match else code


def normalize_symbol_key(raw_symbol: str, stock_code: str) -> str:
    """
    规范化股票代码为标准格式（sz/sh + 6位数字）
    
    Args:
        raw_symbol: 原始股票代码（可能包含sz/sh前缀）
        stock_code: 股票代码（6位数字）
    
    Returns:
        标准格式的股票代码（如 sz000001, sh600000）
    """
    symbol_key = raw_symbol
    if not symbol_key and stock_code:
        code_6 = stock_code[-6:] if len(stock_code) >= 6 else stock_code.zfill(6)
        if code_6.startswith('0'):
            symbol_key = f"sz{code_6}"
        elif code_6.startswith('6'):
            symbol_key = f"sh{code_6}"
        else:
            symbol_key = code_6
    return symbol_key

