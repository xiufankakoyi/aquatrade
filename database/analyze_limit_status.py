"""
分析股票涨跌停、开板和停牌状态
读取stock_daily.parquet，计算三列指标并写入新的parquet文件
"""
import os
import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm
import pyarrow.parquet as pq

# ================= 配置区域 =================
PARQUET_DIR = r'D:\aquatrade\parquet_data'
INPUT_FILE = os.path.join(PARQUET_DIR, 'stock_daily.parquet')
INFO_FILE = os.path.join(PARQUET_DIR, 'stock_info.parquet')
OUTPUT_FILE = os.path.join(PARQUET_DIR, 'stock_limit_status.parquet')
CHUNK_SIZE = 100000  # 分块读取，避免内存溢出
# ===========================================


def get_stock_type_info(info_file: str) -> pd.DataFrame:
    """
    读取stock_info.parquet获取股票类型信息
    如果文件不存在或缺少字段，根据代码推断
    """
    if os.path.exists(info_file):
        try:
            df_info = pd.read_parquet(info_file)
            # 确保有必要的列
            if 'stock_code' not in df_info.columns:
                return pd.DataFrame()
            
            # 如果缺少is_st/is_kc/is_cy字段，根据代码推断
            if 'is_st' not in df_info.columns:
                df_info['is_st'] = 0
            if 'is_kc' not in df_info.columns:
                df_info['is_kc'] = df_info['stock_code'].astype(str).str.startswith(('688', '689')).astype(int)
            if 'is_cy' not in df_info.columns:
                df_info['is_cy'] = df_info['stock_code'].astype(str).str.startswith(('300', '301')).astype(int)
            
            return df_info[['stock_code', 'is_st', 'is_kc', 'is_cy']]
        except Exception as e:
            print(f"⚠️ 读取stock_info失败: {e}，将根据代码推断")
    
    return pd.DataFrame()


def calculate_limit_pct(stock_code: pd.Series, stock_info: pd.DataFrame = None) -> pd.Series:
    """
    根据股票代码和类型计算涨跌停比例
    
    规则：
    - ST股票：5%
    - 创业板(300/301开头)、科创板(688/689开头)：20%
    - 其他：10%
    """
    stock_code_str = stock_code.astype(str)
    
    # 默认10%
    limit_pct = pd.Series(0.10, index=stock_code.index)
    
    # 如果有stock_info信息，使用它（向量化操作）
    if stock_info is not None and not stock_info.empty:
        # 创建映射Series，用于快速查找
        stock_info_indexed = stock_info.set_index('stock_code')
        
        # 合并数据
        merged = pd.DataFrame({'stock_code': stock_code_str})
        merged = merged.merge(
            stock_info_indexed[['is_st', 'is_kc', 'is_cy']],
            left_on='stock_code',
            right_index=True,
            how='left'
        )
        
        # 填充缺失值为0
        merged['is_st'] = merged['is_st'].fillna(0).astype(int)
        merged['is_kc'] = merged['is_kc'].fillna(0).astype(int)
        merged['is_cy'] = merged['is_cy'].fillna(0).astype(int)
        
        # ST股票：5%
        limit_pct[merged['is_st'] == 1] = 0.05
        # 创业板或科创板：20%
        limit_pct[(merged['is_kc'] == 1) | (merged['is_cy'] == 1)] = 0.20
    else:
        # 根据代码推断
        # ST股票：无法从代码判断，保持10%
        # 创业板：300或301开头
        is_cy = stock_code_str.str.startswith(('300', '301'))
        # 科创板：688或689开头
        is_kc = stock_code_str.str.startswith(('688', '689'))
        
        limit_pct[is_cy | is_kc] = 0.20
        # ST股票无法从代码判断，保持10%（实际应该从stock_info获取）
    
    return limit_pct


def calculate_limit_status(df: pd.DataFrame, stock_info: pd.DataFrame = None) -> pd.DataFrame:
    """
    计算涨跌停、开板和停牌状态
    不使用limit_up/limit_down字段，而是根据prev_close和涨跌停规则计算
    
    参数:
        df: 包含股票日线数据的DataFrame，需要包含以下列：
            - stock_code: 股票代码
            - trade_date: 交易日期
            - close: 收盘价
            - high: 最高价
            - low: 最低价
            - prev_close: 前收盘价
            - volume: 成交量
        stock_info: 股票信息DataFrame，包含is_st, is_kc, is_cy字段
    
    返回:
        包含四列新数据的DataFrame:
            - is_limit_up: 是否涨停 (1=涨停, 0=非涨停)
            - is_limit_down: 是否跌停 (1=跌停, 0=非跌停)
            - is_opened: 是否开过板 (1=开过板, 0=未开板或非涨跌停)
            - is_suspended: 是否停牌 (1=停牌, 0=正常交易)
    """
    result = pd.DataFrame()
    result['stock_code'] = df['stock_code']
    result['trade_date'] = df['trade_date']
    
    # 确保数值列为float类型，处理缺失值
    close = pd.to_numeric(df['close'], errors='coerce')
    high = pd.to_numeric(df['high'], errors='coerce')
    low = pd.to_numeric(df['low'], errors='coerce')
    prev_close = pd.to_numeric(df['prev_close'], errors='coerce')
    volume = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
    
    # 计算涨跌停比例
    limit_pct = calculate_limit_pct(df['stock_code'], stock_info)
    
    # 计算理论涨跌停价（基于前收盘价）
    # 涨停价 = prev_close * (1 + limit_pct)，四舍五入到分
    limit_up_price = (prev_close * (1 + limit_pct)).round(2)
    # 跌停价 = prev_close * (1 - limit_pct)，四舍五入到分
    limit_down_price = (prev_close * (1 - limit_pct)).round(2)
    
    # 处理缺失值：如果prev_close为0或NaN，无法判断涨跌停
    valid_prev_close = (prev_close > 0) & prev_close.notna()
    
    # 1. 判断是否涨停
    # 涨停：收盘价 >= 涨停价（考虑浮点数精度问题，使用接近判断）
    # 使用0.999的容差，因为四舍五入可能导致微小差异
    is_limit_up = valid_prev_close & (close >= limit_up_price * 0.999)
    result['is_limit_up'] = is_limit_up.astype(int)
    
    # 2. 判断是否跌停
    # 跌停：收盘价 <= 跌停价（考虑浮点数精度问题）
    is_limit_down = valid_prev_close & (close > 0) & (close <= limit_down_price * 1.001)
    result['is_limit_down'] = is_limit_down.astype(int)
    
    # 3. 判断是否开过板
    # 开板定义：对于涨停/跌停的股票，判断盘中是否曾经开过板
    # 
    # 涨停开板：收盘涨停，但最低价 < 涨停价
    #   说明：如果封板后一直未开板，最低价应该等于涨停价；如果最低价 < 涨停价，说明盘中曾经开过板
    # 
    # 跌停开板：收盘跌停，但最高价 > 跌停价
    #   说明：如果封板后一直未开板，最高价应该等于跌停价；如果最高价 > 跌停价，说明盘中曾经开过板
    
    is_opened = pd.Series(0, index=df.index, dtype=int)
    
    # 涨停开板：收盘涨停但最低价低于涨停价（说明盘中曾经开过板）
    limit_up_opened = is_limit_up & (low < limit_up_price * 0.999)
    
    # 跌停开板：收盘跌停但最高价高于跌停价（说明盘中曾经开过板）
    limit_down_opened = is_limit_down & (high > limit_down_price * 1.001)
    
    is_opened = (limit_up_opened | limit_down_opened).astype(int)
    result['is_opened'] = is_opened
    
    # 4. 判断是否停牌
    # 停牌：成交量 <= 0
    is_suspended = (volume <= 0).astype(int)
    result['is_suspended'] = is_suspended
    
    return result


def process_parquet_file():
    """
    读取stock_daily.parquet，计算指标并写入新文件
    """
    print(f"正在读取: {INPUT_FILE}")
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误：文件不存在 {INPUT_FILE}")
        return
    
    # 检查文件大小，决定是否分块处理
    file_size = os.path.getsize(INPUT_FILE) / (1024 * 1024)  # MB
    print(f"文件大小: {file_size:.2f} MB")
    
    all_results = []
    
    try:
        # 先读取一小部分检查列名（使用pyarrow读取第一个row group）
        parquet_file = pq.ParquetFile(INPUT_FILE)
        if parquet_file.num_row_groups > 0:
            sample = parquet_file.read_row_group(0).to_pandas()
        else:
            # 如果文件为空，尝试读取整个文件
            sample = pd.read_parquet(INPUT_FILE)
        
        print(f"数据列: {list(sample.columns)}")
        
        # 检查必需的列是否存在
        required_cols = ['stock_code', 'trade_date', 'close', 'high', 'low', 
                        'prev_close', 'volume']
        missing_cols = [col for col in required_cols if col not in sample.columns]
        
        if missing_cols:
            print(f"❌ 错误：缺少必需的列: {missing_cols}")
            print(f"可用列: {list(sample.columns)}")
            return
        
        # 读取股票信息（用于判断ST、创业板、科创板）
        print("正在读取股票信息...")
        stock_info = get_stock_type_info(INFO_FILE)
        if not stock_info.empty:
            print(f"已加载 {len(stock_info)} 只股票的类型信息")
        else:
            print("⚠️ 未找到股票信息文件，将根据代码推断（ST股票可能无法准确判断）")
        
        # 如果文件较大，分块读取
        if file_size > 500:  # 大于500MB分块处理
            print(f"文件较大，使用分块处理...")
            
            # 使用pyarrow的ParquetFile进行分块读取（重用之前创建的对象）
            num_row_groups = parquet_file.num_row_groups
            
            for i in tqdm(range(num_row_groups), desc="处理分块"):
                df_chunk = parquet_file.read_row_group(i).to_pandas()
                result_chunk = calculate_limit_status(df_chunk, stock_info)
                all_results.append(result_chunk)
        else:
            # 文件较小，一次性读取
            print("一次性读取全部数据...")
            df = pd.read_parquet(INPUT_FILE)
            print(f"数据行数: {len(df):,}")
            
            result = calculate_limit_status(df, stock_info)
            all_results.append(result)
        
        # 合并所有结果
        print("合并结果...")
        final_result = pd.concat(all_results, ignore_index=True)
        
        # 统计信息
        print("\n=== 统计信息 ===")
        print(f"总记录数: {len(final_result):,}")
        print(f"涨停记录数: {final_result['is_limit_up'].sum():,}")
        print(f"跌停记录数: {final_result['is_limit_down'].sum():,}")
        print(f"开板记录数: {final_result['is_opened'].sum():,}")
        print(f"停牌记录数: {final_result['is_suspended'].sum():,}")
        
        # 保存到parquet文件
        print(f"\n正在保存到: {OUTPUT_FILE}")
        final_result.to_parquet(OUTPUT_FILE, index=False, engine='pyarrow')
        
        print(f"✅ 完成！已保存 {len(final_result):,} 条记录到 {OUTPUT_FILE}")
        
        # 显示前几行示例
        print("\n=== 数据示例 ===")
        print(final_result.head(10))
        
    except Exception as e:
        print(f"❌ 处理过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    process_parquet_file()

