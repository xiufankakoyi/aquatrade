import os
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import re
import gc
import warnings
import numpy as np

warnings.filterwarnings('ignore')

# ================= 配置区域 =================
REPORT_FILE = 'Real_Missing_Report.csv'
SOURCE_DIR = r'D:\aquatrade\data\mins\falt'
TARGET_DIR = r'D:\aquatrade\parquet_data\mins'
BATCH_SIZE = 50  # 增大批次大小，减少IO频率
OVERWRITE_EXISTING = False 
# ===========================================

def find_code_column(df):
    """
    【优化版】智能列定位
    能够识别 '000001' 和 '000001.XSHE' 两种格式。
    优化：减少字符串操作，提高检测速度
    """
    # 优先检查常见位置（第8列或第14列）
    for col_idx in [7, 13]:
        if col_idx in df.columns:
            try:
                sample = df[col_idx].dropna().head(10).astype(str)
                if not sample.empty:
                    matches = sample.str.contains(r'^\d{6}', regex=True, na=False)
                    if matches.sum() >= 5:  # 至少5个匹配
                        return col_idx
            except:
                continue
    
    # 从最后一列往前找（最多检查后5列）
    cols_to_check = list(reversed(df.columns))[:5]
    for col in cols_to_check:
        try:
            # 只检查前10行，减少计算量
            sample = df[col].dropna().head(10).astype(str)
            if sample.empty: continue
            
            matches = sample.str.contains(r'^\d{6}', regex=True, na=False)
            if matches.sum() >= 5:  # 至少5个匹配
                return col
        except:
            continue
    return None

def read_csv_smart(file_path, usecols=None):
    """
    优化版：支持指定列读取，避免读取不必要的数据
    """
    df = pd.DataFrame()
    
    # --- 阶段 1: 读取 (含引擎自动降级) ---
    try:
        # 如果指定了列，只读取需要的列，大幅提升性能
        read_params = {
            'filepath_or_buffer': file_path,
            'engine': 'c',
            'header': None,
            'low_memory': True,  # 改为True，让pandas自动优化
            'on_bad_lines': 'skip'
        }
        
        if usecols is not None:
            # 只读取需要的列
            read_params['usecols'] = usecols
            read_params['dtype'] = {col: str for col in usecols}
        else:
            # 先读取少量行来检测列结构
            read_params['nrows'] = 100
            read_params['dtype'] = str
        
        df = pd.read_csv(**read_params)
        
        if df.empty: return df
        
        # 如果没有指定列，需要检测代码列
        if usecols is None:
            code_col = find_code_column(df)
            if code_col is None:
                if 7 in df.columns: code_col = 7
                elif 13 in df.columns: code_col = 13
                else: return pd.DataFrame()
            
            # 重新读取，只读取需要的列
            target_cols = [0, 1, 2, 3, 4, 5, 6, code_col]
            return read_csv_smart(file_path, usecols=target_cols)
        
        # 如果已经指定了列，直接处理
        df.columns = ['datetime', 'open', 'close', 'high', 'low', 'volume', 'amount', 'code']
        
        # 行清洗：剔除表头行
        df = df[df['code'].str.contains(r'\d+', na=False, regex=True)]
        
        return df
        
    except Exception:
        try:
            # 降级到python引擎
            read_params = {
                'filepath_or_buffer': file_path,
                'engine': 'python',
                'header': None,
                'on_bad_lines': 'skip'
            }
            
            if usecols is not None:
                read_params['usecols'] = usecols
                read_params['dtype'] = {col: str for col in usecols}
            else:
                read_params['nrows'] = 100
                read_params['dtype'] = str
            
            df = pd.read_csv(**read_params)
            
            if df.empty: return df
            
            if usecols is None:
                code_col = find_code_column(df)
                if code_col is None:
                    if 7 in df.columns: code_col = 7
                    elif 13 in df.columns: code_col = 13
                    else: return pd.DataFrame()
                target_cols = [0, 1, 2, 3, 4, 5, 6, code_col]
                return read_csv_smart(file_path, usecols=target_cols)
            
            df.columns = ['datetime', 'open', 'close', 'high', 'low', 'volume', 'amount', 'code']
            df = df[df['code'].str.contains(r'\d+', na=False, regex=True)]
            return df
            
        except Exception:
            return pd.DataFrame()

def get_target_map(report_file, target_dir):
    print("Step 1: Analyzing repair targets...")
    try:
        df_report = pd.read_csv(report_file)
        if 'pure_code' in df_report.columns:
            watch_codes = set(df_report['pure_code'].astype(str).str.zfill(6))
        else:
            watch_codes = set(df_report['code'].astype(str).str.extract(r'(\d{6})')[0])
    except:
        watch_codes = None
    target_files = list(Path(target_dir).rglob('*.csv'))
    code_path_map = {}
    for p in target_files:
        match = re.search(r'(\d{6})', p.name)
        if match:
            code = match.group(1)
            if watch_codes is None or code in watch_codes:
                code_path_map[code] = str(p)
    return code_path_map

def flush_buffer(buffer_dict, code_path_map):
    if not buffer_dict: return
    
    for code, df_list in buffer_dict.items():
        if code not in code_path_map: continue
        target_path = code_path_map[code]
        
        try:
            # 合并批次数据
            if not df_list:
                continue
            patch_data = pd.concat(df_list, ignore_index=True)
            
            if patch_data.empty:
                continue
            
            # 预处理patch_data
            if 'datetime' in patch_data.columns:
                patch_data['datetime'] = pd.to_datetime(patch_data['datetime'], errors='coerce')
                patch_data = patch_data.dropna(subset=['datetime'])
            
            if patch_data.empty:
                continue
            
            # 检查目标文件是否存在及大小
            file_exists = os.path.exists(target_path)
            file_size = os.path.getsize(target_path) if file_exists else 0
            
            # 如果文件很大（>50MB），使用追加模式而不是读取全部
            if file_exists and file_size > 50 * 1024 * 1024:
                # 大文件策略：直接追加，后续统一去重
                patch_data.to_csv(target_path, mode='a', header=False, index=False)
            else:
                # 小文件策略：读取、合并、去重、写入
                if file_exists:
                    original_data = read_csv_smart(target_path)
                    
                    if not original_data.empty:
                        if 'datetime' in original_data.columns:
                            original_data['datetime'] = pd.to_datetime(original_data['datetime'], errors='coerce')
                            original_data = original_data.dropna(subset=['datetime'])
                        
                        if OVERWRITE_EXISTING:
                            combined = pd.concat([original_data, patch_data], ignore_index=True)
                            keep_strategy = 'last'
                        else:
                            combined = pd.concat([original_data, patch_data], ignore_index=True)
                            keep_strategy = 'first'
                    else:
                        combined = patch_data
                        keep_strategy = 'last'
                else:
                    combined = patch_data
                    keep_strategy = 'last'
                
                # 去重和排序
                if 'datetime' in combined.columns and not combined.empty:
                    combined = combined.drop_duplicates(subset=['datetime'], keep=keep_strategy)
                    combined = combined.sort_values('datetime')
                
                combined.to_csv(target_path, index=False)
            
        except Exception as e:
            print(f"❌ Write Error {code}: {e}")
            import traceback
            traceback.print_exc()

def run_corrected_patch():
    target_map = get_target_map(REPORT_FILE, TARGET_DIR)
    if not target_map:
        print("❌ No target files found!")
        return

    source_files = list(Path(SOURCE_DIR).rglob('*.csv'))
    print(f"Step 2: Starting Repair (Source: {len(source_files)} files)")
    print(f"Target codes: {len(target_map)}")
    print("Mode: Adaptive Regex (Matches '000001' and '000001.XSHE')")
    print(f"Batch size: {BATCH_SIZE}")
    
    buffer = {}
    processed_count = 0
    skipped_count = 0
    
    pbar = tqdm(source_files, desc="Processing", unit="file")
    
    for i, src_file in enumerate(pbar):
        try:
            # 读取
            df = read_csv_smart(str(src_file))
            if df.empty:
                skipped_count += 1
                continue

            # 提取 6 位纯数字代码用于分发
            # 优化：先过滤再提取，减少字符串操作
            df = df[df['code'].notna()]
            if df.empty:
                skipped_count += 1
                continue
            
            # 使用向量化操作提取代码
            df['pure_code'] = df['code'].str.extract(r'(\d{6})', expand=False)
            df_filtered = df[df['pure_code'].notna() & df['pure_code'].isin(target_map.keys())]
            
            if df_filtered.empty:
                skipped_count += 1
                continue
            
            # 分组处理
            grouped = df_filtered.groupby('pure_code', sort=False)
            for code, group_df in grouped:
                save_df = group_df.drop(columns=['pure_code'], errors='ignore')
                if code not in buffer:
                    buffer[code] = []
                buffer[code].append(save_df)
            
            processed_count += 1
            
            # 定期刷新缓冲区
            if (i + 1) % BATCH_SIZE == 0:
                pbar.set_description(f"Flushing batch ({processed_count} processed, {skipped_count} skipped)...")
                flush_buffer(buffer, target_map)
                buffer = {}
                gc.collect()
                pbar.set_description(f"Processing ({processed_count} processed)")
                
        except Exception as e:
            skipped_count += 1
            pbar.write(f"⚠️  Error processing {src_file.name}: {e}")
            continue

    # 最终刷新
    if buffer:
        print("\nFinal Flush...")
        flush_buffer(buffer, target_map)
    
    print(f"\n✅ Repair Complete!")
    print(f"   Processed: {processed_count} files")
    print(f"   Skipped: {skipped_count} files")

if __name__ == '__main__':
    run_corrected_patch()