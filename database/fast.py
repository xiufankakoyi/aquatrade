import os
import pandas as pd
from pathlib import Path
import warnings

# 忽略一些pandas的警告
warnings.filterwarnings('ignore')

# ================= 配置区域 =================
# 你的原始数据根目录
SOURCE_DIR = r'D:\aquatrade\data\mins'
# 输出目录
OUTPUT_DIR = r'D:\aquatrade\parquet_data'
# ===========================================

def clean_and_convert():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # 获取所有CSV文件路径
    all_files = [str(p) for p in Path(SOURCE_DIR).rglob('*.csv')]
    total_files = len(all_files)
    
    print(f"扫描到 {total_files} 个CSV文件，开始处理...")
    
    # 这里的策略是：
    # 因为数据量大，我们不能一次读完。
    # 我们先定义标准列名。
    # 注意：根据你的截图，有些文件有header，有些可能没有，这里需要根据实际情况微调
    # 假设截图3是标准格式，第一列是时间
    
    # 用一个字典暂存数据： { '000001.XSHE': [df1, df2, ...], '000002.XSHE': [...] }
    # 内存不够时可以考虑基于数据库的方案，这里演示基于文件的方案
    
    # 由于分钟线数据量巨大，为了防止内存爆炸，建议按年份或者按文件批次处理
    # 这里演示最通用的单文件处理逻辑：
    
    # 1. 既然文件是按时间切片的，我们需要把它们都读出来，
    #    然后按 code (股票代码) group by，再追加写入对应的文件。
    
    for i, file_path in enumerate(all_files):
        try:
            # 读取CSV
            # 根据截图，第一列是时间，index_col=False 防止把第一列当索引
            df = pd.read_csv(file_path, index_col=False)
            
            # --- 格式对齐 (根据你的截图3进行调整) ---
            # 你的截图显示列名可能是：[Unnamed: 0, open, close, high, low, volume, money, code]
            # 实际上 Unnamed: 0 是时间
            
            # 标准化列名
            rename_dict = {
                df.columns[0]: 'datetime', # 假设第一列是时间
                'money': 'amount',         # 习惯上金额叫 amount
                'vol': 'volume'
            }
            df.rename(columns=rename_dict, inplace=True)
            
            # 确保包含必要的列
            required_cols = ['datetime', 'code', 'open', 'high', 'low', 'close', 'volume', 'amount']
            # 如果某些列不存在（比如你的截图里有 header），需要做防御性编程
            # 简单清洗
            df = df[df['code'].notna()] # 去掉代码为空的行
            
            # --- 关键步骤：按代码拆分并追加保存 ---
            grouped = df.groupby('code')
            
            for code, group_df in grouped:
                # 清洗代码文件名 (防止文件名非法字符)
                safe_code = str(code).replace('/', '_').strip()
                save_path = os.path.join(OUTPUT_DIR, f"{safe_code}.parquet")
                
                # 转换时间格式，确保是 datetime 类型
                group_df['datetime'] = pd.to_datetime(group_df['datetime'])
                group_df.sort_values('datetime', inplace=True)
                
                # 追加模式写入 Parquet (Fastparquet引擎支持 append)
                # 或者：如果不熟悉追加，可以先存成临时的小 CSV，最后再合并。
                # 鉴于Parquet追加比较复杂，这里用一种更稳妥的“分桶”策略：
                # 直接追加到一个CSV，最后统一转Parquet。
                
                csv_save_path = os.path.join(OUTPUT_DIR, f"{safe_code}_temp.csv")
                
                # 如果文件不存在，写入header，否则不写入
                header = not os.path.exists(csv_save_path)
                group_df.to_csv(csv_save_path, mode='a', index=False, header=header)
                
        except Exception as e:
            print(f"处理文件 {file_path} 出错: {e}")
            
        if (i + 1) % 10 == 0:
            print(f"已处理 {i + 1}/{total_files} 个文件...")

    print("第一阶段：数据拆分完成。开始第二阶段：转换为 Parquet 并去重排序...")
    
    # 第二阶段：把临时 CSV 转为最终的高效 Parquet
    temp_csvs = [str(p) for p in Path(OUTPUT_DIR).glob('*_temp.csv')]
    for temp_file in temp_csvs:
        df = pd.read_csv(temp_file)
        
        # 全局去重（防止买的数据有重叠日期）
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.drop_duplicates(subset=['datetime'], keep='last', inplace=True)
        df.sort_values('datetime', inplace=True)
        
        # 保存为最终文件
        final_name = temp_file.replace('_temp.csv', '.parquet')
        df.to_parquet(final_name, engine='pyarrow', compression='snappy')
        
        # 删除临时csv
        os.remove(temp_file)
        print(f"生成: {final_name}")

    print("全部完成！")

if __name__ == '__main__':
    clean_and_convert()