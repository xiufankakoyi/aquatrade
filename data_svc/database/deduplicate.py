"""
去重脚本：用于清理使用追加模式写入后的重复数据
在fast.py运行完成后，运行此脚本进行去重
"""
import pandas as pd
import os
from pathlib import Path
from tqdm import tqdm
import gc

TARGET_DIR = r'D:\aquatrade\parquet_data\mins'
CHUNK_SIZE = 10000  # 每次处理10000行，避免内存爆炸

def deduplicate_file(file_path):
    """使用chunked方式去重大文件"""
    try:
        file_size = os.path.getsize(file_path)
        
        # 如果文件很小，直接读取去重
        if file_size < 10 * 1024 * 1024:  # 10MB
            try:
                df = pd.read_csv(file_path)
                if df.empty:
                    return
                
                if 'datetime' in df.columns:
                    df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                    df = df.dropna(subset=['datetime'])
                    df = df.drop_duplicates(subset=['datetime'], keep='first')
                    df = df.sort_values('datetime')
                    df.to_csv(file_path, index=False)
            except:
                pass
            return
        
        # 大文件使用chunked方式
        temp_file = str(file_path) + '.tmp'
        seen_dates = set()
        header_written = False
        
        try:
            # 读取并去重
            chunk_iter = pd.read_csv(file_path, chunksize=CHUNK_SIZE)
            
            for chunk in chunk_iter:
                if chunk.empty:
                    continue
                
                if 'datetime' in chunk.columns:
                    chunk['datetime'] = pd.to_datetime(chunk['datetime'], errors='coerce')
                    chunk = chunk.dropna(subset=['datetime'])
                    
                    # 去重：只保留第一次出现的datetime
                    mask = ~chunk['datetime'].isin(seen_dates)
                    chunk_filtered = chunk[mask]
                    
                    if not chunk_filtered.empty:
                        # 更新seen_dates
                        seen_dates.update(chunk_filtered['datetime'].tolist())
                        
                        # 写入临时文件
                        chunk_filtered.to_csv(temp_file, mode='a', header=not header_written, index=False)
                        header_written = True
                
                del chunk, chunk_filtered
                gc.collect()
            
            # 替换原文件
            if os.path.exists(temp_file):
                os.replace(temp_file, file_path)
                
        except Exception as e:
            # 如果出错，删除临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise e
            
    except Exception as e:
        print(f"❌ Error processing {Path(file_path).name}: {e}")

def main():
    target_files = list(Path(TARGET_DIR).rglob('*.csv'))
    print(f"Found {len(target_files)} files to deduplicate")
    
    pbar = tqdm(target_files, desc="Deduplicating")
    for file_path in pbar:
        pbar.set_description(f"Processing {Path(file_path).name}")
        deduplicate_file(str(file_path))
        gc.collect()
    
    print("✅ Deduplication Complete!")

if __name__ == '__main__':
    main()

