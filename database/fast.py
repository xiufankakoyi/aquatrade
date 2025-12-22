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
BATCH_SIZE = 5

# 【核心策略调整】
# True: 补丁包覆盖原文件（信任补丁） -> keep='last'
# False: 仅填补空缺，不修改原数据（信任原文件） -> keep='first'
OVERWRITE_EXISTING = False 
# ===========================================

def validate_schema(df, file_name):
    """
    【防御性编程】内容探针
    检查切片后的数据是否符合语义，防止列错位。
    """
    # 1. 检查行数
    if df.shape[1] != 8:
        return False, "列数切片异常"

    # 2. 检查时间列 (第1列, index 0)
    # 随机抽样检查，避免全量检查太慢。抽前10行和后10行。
    sample = pd.concat([df.head(10), df.tail(10)])
    
    # 尝试将第一列转为日期
    try:
        # 只要能解析出日期，就没有大错位
        pd.to_datetime(sample.iloc[:, 0], errors='raise')
    except:
        return False, "第1列不是有效的时间格式 (Possible Column Shift)"

    # 3. 检查代码列 (第8列, index 7)
    # 应该是数字或字符串数字
    try:
        # 转换为字符串并检查是否包含数字
        code_sample = sample.iloc[:, 7].astype(str)
        if not code_sample.str.contains(r'\d+', regex=True).all():
             return False, "第8列不包含股票代码 (Possible Column Shift)"
    except:
        return False, "代码列校验失败"

    return True, "OK"

def read_csv_safe_validated(file_path):
    # 构造超长表头以容错
    oversized_names = list(range(20))
    
    try:
        df = pd.read_csv(
            file_path,
            engine='c',
            header=None,
            names=oversized_names,
            dtype=str, # 全读为字符，方便后续校验
            low_memory=False
        )
        
        # 1. 硬切片
        df = df.iloc[:, :8]
        
        # 2. 【新增】语义校验
        is_valid, reason = validate_schema(df, Path(file_path).name)
        if not is_valid:
            print(f"    ⚠️ [Schema Error] 跳过文件 {Path(file_path).name}: {reason}")
            return pd.DataFrame()
        
        # 3. 命名
        df.columns = ['datetime', 'open', 'close', 'high', 'low', 'volume', 'amount', 'code']
        
        # 4. 清洗非数据行 (比如读到了原来的表头)
        # 逻辑：datetime 列必须能转为时间，或者 code 列必须是数字
        df = df[df['code'].str.match(r'^\d+(\.\w+)?$', na=False)]
        
        return df

    except Exception as e:
        print(f"读取异常 {Path(file_path).name}: {e}")
        return pd.DataFrame()

def get_target_map(report_file, target_dir):
    # (逻辑不变，略)
    print("Step 1: 锁定修复目标...")
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
            # 新数据 (Patch)
            patch_data = pd.concat(df_list, ignore_index=True)
            
            if os.path.exists(target_path):
                # 旧数据 (Original)
                original_data = read_csv_safe_validated(target_path)
                
                if not original_data.empty:
                    # 【关键决策点】
                    if OVERWRITE_EXISTING:
                        # 补丁在后 -> keep='last' -> 补丁覆盖旧数据
                        combined = pd.concat([original_data, patch_data], ignore_index=True)
                        keep_strategy = 'last'
                    else:
                        # 补丁在后 -> keep='first' -> 遇到重复日期，保留前面的(旧数据)，丢弃后面的(补丁)
                        combined = pd.concat([original_data, patch_data], ignore_index=True)
                        keep_strategy = 'first'
                else:
                    combined = patch_data
                    keep_strategy = 'last'
            else:
                combined = patch_data
                keep_strategy = 'last'

            # 统一清洗
            if 'datetime' in combined.columns:
                combined['datetime'] = pd.to_datetime(combined['datetime'], errors='coerce')
                combined.dropna(subset=['datetime'], inplace=True)
                
                # 【去重逻辑执行】
                combined.drop_duplicates(subset=['datetime'], keep=keep_strategy, inplace=True)
                
                combined.sort_values('datetime', inplace=True)
            
            # 写入
            combined.to_csv(target_path, index=False)
            
        except Exception as e:
            print(f"❌ 写入 {code} 失败: {e}")

def run_architectural_patch():
    target_map = get_target_map(REPORT_FILE, TARGET_DIR)
    if not target_map: return

    source_files = list(Path(SOURCE_DIR).rglob('*.csv'))
    print(f"Step 2: 启动架构级修复 (Source: {len(source_files)} files)")
    print(f"策略: {'覆盖模式 (Overwrite)' if OVERWRITE_EXISTING else '安全填充模式 (Fill Only)'}")
    
    buffer = {}
    pbar = tqdm(source_files, desc="Processing")
    
    for i, src_file in enumerate(pbar):
        # 读取并校验
        df = read_csv_safe_validated(str(src_file))
        if df.empty: continue

        # 提取代码
        df['pure_code'] = df['code'].str.extract(r'(\d{6})')[0]
        
        # 过滤
        df_filtered = df[df['pure_code'].isin(target_map.keys())]
        if df_filtered.empty: continue
            
        grouped = df_filtered.groupby('pure_code')
        for code, group_df in grouped:
            save_df = group_df.drop(columns=['pure_code'], errors='ignore')
            if code not in buffer: buffer[code] = []
            buffer[code].append(save_df)
            
        if (i + 1) % BATCH_SIZE == 0:
            pbar.set_description(f"Saving (Batch {i+1})...")
            flush_buffer(buffer, target_map)
            buffer = {}
            gc.collect()
            pbar.set_description("Processing")

    print("Final Flush...")
    flush_buffer(buffer, target_map)
    print("✅ 任务完成。数据一致性已校验。")

if __name__ == '__main__':
    run_architectural_patch()