"""
导入指数数据到 ArcticDB

从 data/marketdata/ 目录读取 CSV 文件，导入到对应的 ArcticDB 库
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import polars as pl
from datetime import datetime
from loguru import logger
from typing import Dict, List

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library


INDEX_MAPPING = {
    '沪深300.csv': {
        'library': 'hs300_daily',
        'symbol': 'hs300',
        'code': '000300.SH',
        'name': '沪深300'
    },
    '上证50.csv': {
        'library': 'sz50_daily',
        'symbol': 'sz50',
        'code': '000016.SH',
        'name': '上证50'
    },
    '中证500.csv': {
        'library': 'zz500_daily',
        'symbol': 'zz500',
        'code': '000905.SH',
        'name': '中证500'
    },
    '创业板指数数据.csv': {
        'library': 'cyb_index_daily',
        'symbol': 'cyb_index',
        'code': '399006.SZ',
        'name': '创业板指'
    },
    '上证指数数据.csv': {
        'library': 'sh_index_daily',
        'symbol': 'sh_index',
        'code': '000001.SH',
        'name': '上证指数'
    },
    '深证成指数据.csv': {
        'library': 'sz_index_daily',
        'symbol': 'sz_index',
        'code': '399001.SZ',
        'name': '深证成指'
    },
}


def read_index_csv(file_path: Path) -> pd.DataFrame:
    """读取指数 CSV 文件"""
    df = pd.read_csv(file_path, encoding='utf-8')
    
    column_mapping = {
        '交易日期': 'trade_date',
        '开盘价': 'open',
        '最高价': 'high',
        '最低价': 'low',
        '收盘价': 'close',
        '前收盘价': 'pre_close',
        '涨跌额': 'change',
        '涨跌幅(%)': 'pct_chg',
        '成交量(手)': 'volume',
        '成交额(万元)': 'amount',
        '股票代码': 'ts_code',
    }
    
    df = df.rename(columns=column_mapping)
    
    if 'trade_date' in df.columns:
        if df['trade_date'].dtype == 'object':
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        elif df['trade_date'].dtype == 'int64':
            df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str), format='%Y%m%d')
    
    df = df.sort_values('trade_date')
    
    if 'trade_date' in df.columns:
        df = df.set_index('trade_date')
    
    return df


def import_index_data(file_path: Path, config: Dict) -> Dict:
    """导入单个指数数据"""
    result = {
        'file': file_path.name,
        'library': config['library'],
        'status': 'OK',
        'rows': 0,
        'date_range': ''
    }
    
    try:
        logger.info(f"读取文件: {file_path}")
        df = read_index_csv(file_path)
        
        if df.empty:
            result['status'] = 'EMPTY'
            return result
        
        result['rows'] = len(df)
        result['date_range'] = f"{df.index.min()} ~ {df.index.max()}"
        
        logger.info(f"  行数: {len(df)}")
        logger.info(f"  日期范围: {result['date_range']}")
        
        arctic = get_arctic_instance_for_library(config['library'])
        
        libraries = arctic.list_libraries()
        if config['library'] not in libraries:
            arctic.create_library(config['library'])
            logger.info(f"  创建库: {config['library']}")
        
        lib = arctic[config['library']]
        
        # 使用 Arrow Table 直接写入，避免 UTF-8 解码问题
        try:
            # 先尝试普通写入
            lib.write(config['symbol'], df)
            logger.info(f"  写入成功: {config['symbol']}")
        except UnicodeDecodeError:
            # 如果遇到编码问题，使用 _nvs 直接写入
            logger.info(f"  使用 _nvs 直接写入...")
            import pyarrow as pa
            table = pa.Table.from_pandas(df)
            lib._nvs.write(config['symbol'], table)
            logger.info(f"  写入成功 (_nvs): {config['symbol']}")
        
    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = str(e)
        logger.error(f"  导入失败: {e}")
    
    return result


def verify_import(library: str, symbol: str) -> Dict:
    """验证导入的数据"""
    try:
        arctic = get_arctic_instance_for_library(library)
        lib = arctic[library]
        
        data = lib.read(symbol)
        df = data.data
        
        if hasattr(df, 'to_pandas'):
            df = df.to_pandas()
        
        return {
            'library': library,
            'symbol': symbol,
            'rows': len(df),
            'columns': list(df.columns),
            'date_range': f"{df.index.min()} ~ {df.index.max()}",
            'status': 'OK'
        }
    except Exception as e:
        return {
            'library': library,
            'symbol': symbol,
            'status': 'ERROR',
            'error': str(e)
        }


def main():
    logger.info("=" * 70)
    logger.info("导入指数数据到 ArcticDB")
    logger.info("=" * 70)
    
    marketdata_dir = Path('data/marketdata')
    
    if not marketdata_dir.exists():
        logger.error(f"目录不存在: {marketdata_dir}")
        return
    
    results = []
    
    for csv_file, config in INDEX_MAPPING.items():
        file_path = marketdata_dir / csv_file
        
        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            results.append({
                'file': csv_file,
                'status': 'NOT_FOUND'
            })
            continue
        
        logger.info(f"\n处理: {csv_file}")
        result = import_index_data(file_path, config)
        results.append(result)
    
    logger.info("\n" + "=" * 70)
    logger.info("验证导入结果")
    logger.info("=" * 70)
    
    for csv_file, config in INDEX_MAPPING.items():
        file_path = marketdata_dir / csv_file
        if file_path.exists():
            verify_result = verify_import(config['library'], config['symbol'])
            status_icon = '✅' if verify_result['status'] == 'OK' else '❌'
            logger.info(f"{status_icon} {config['name']}: {verify_result.get('rows', 0)} 行")
    
    logger.info("\n" + "=" * 70)
    logger.info("导入汇总")
    logger.info("=" * 70)
    
    for r in results:
        status_icon = {
            'OK': '✅',
            'ERROR': '❌',
            'EMPTY': '📭',
            'NOT_FOUND': '❓'
        }.get(r['status'], '❓')
        
        logger.info(f"{status_icon} {r.get('file', r.get('library'))}: {r.get('rows', 0)} 行")
    
    logger.info("\n导入完成!")


if __name__ == '__main__':
    main()
