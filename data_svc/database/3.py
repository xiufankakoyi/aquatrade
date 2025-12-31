import os
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import re

# ================= 路径配置 =================
DAILY_FILE = r'D:\aquatrade\parquet_data\stock_daily.parquet'
MIN_CSV_DIR = r'D:\aquatrade\parquet_data\mins'
MAX_CHECK_DATE = '2025-11-04'
# ===========================================

def validate_csv_strict():
    # --- 1. 读取日线基准 ---
    print(f"正在读取基准日线: {DAILY_FILE} ...")
    try:
        df_daily = pd.read_parquet(DAILY_FILE, columns=['code', 'trade_date'])
        df_daily.rename(columns={'trade_date': 'datetime'}, inplace=True)
    except:
        df_daily = pd.read_parquet(DAILY_FILE)
        # 自动找列名
        cols = df_daily.columns
        date_col = next((c for c in cols if 'date' in str(c).lower()), 'date')
        code_col = next((c for c in cols if 'code' in str(c).lower()), 'code')
        df_daily = df_daily[[code_col, date_col]].rename(columns={code_col: 'code', date_col: 'datetime'})

    # 关键修改：提取 6 位数字代码作为 Key
    # 比如 '000001.SZ' -> '000001'
    print("正在构建【纯数字】考勤表...")
    df_daily['pure_code'] = df_daily['code'].astype(str).str.extract(r'(\d{6})')[0]
    df_daily['date_str'] = pd.to_datetime(df_daily['datetime']).dt.strftime('%Y-%m-%d')
    
    # 字典结构：{'000001': {'2023-01-01', ...}, '600000': {...}}
    daily_attendance = df_daily.groupby('pure_code')['date_str'].apply(set).to_dict()
    
    print(f"基准加载完毕，包含 {len(daily_attendance)} 只股票。")
    print(f"基准代码示例: {list(daily_attendance.keys())[:5]}") # 打印前5个看看是不是纯数字

    # --- 2. 准备 CSV 文件 ---
    csv_files = list(Path(MIN_CSV_DIR).rglob('*.csv'))
    if not csv_files:
        print("❌ 未找到 CSV 文件！")
        return

    print(f"找到 {len(csv_files)} 个分时文件。")
    
    # --- 3. 调试：先试着匹配前 5 个，看看能不能对上 ---
    print("\n--- 🔎 正在进行握手测试 ---")
    matched_count = 0
    for i, p in enumerate(csv_files[:10]):
        # 从文件名提取 6 位数字
        match = re.search(r'(\d{6})', p.name)
        file_pure_code = match.group(1) if match else None
        
        status = "❌ 失败"
        if file_pure_code and file_pure_code in daily_attendance:
            status = "✅ 成功"
            matched_count += 1
        print(f"文件: {p.name} -> 提取码: {file_pure_code} -> 匹配状态: {status}")
    
    if matched_count == 0:
        print("⚠️ 警告：前10个文件全部匹配失败！程序将退出，请检查上面的提取码和基准代码是否一致。")
        return
    else:
        print(f"握手成功！开始全量验证... (这次肯定会慢下来，因为真的在读文件了)")
    print("----------------------------\n")

    # --- 4. 全量验证 ---
    missing_records = []
    
    for p in tqdm(csv_files, desc="验证 CSV 数据"):
        # 1. 提取文件名里的数字
        match = re.search(r'(\d{6})', p.name)
        if not match: continue
        pure_code = match.group(1)
        
        # 2. 找考勤表
        target_dates = daily_attendance.get(pure_code)
        if target_dates is None: continue # 日线里没有这只票

        try:
            # 3. 极速读取时间列 (usecols=[0] 假设第一列是时间)
            # 如果你的第一列不是时间，请改为 usecols=['datetime'] 或对应的列名/索引
            try:
                # 优先尝试按名读取
                df_min = pd.read_csv(p, usecols=['datetime'])
            except:
                # 失败则按索引读取第一列
                df_min = pd.read_csv(p, usecols=[0], header=None)
                df_min.columns = ['datetime']

            min_dates = set(pd.to_datetime(df_min['datetime'], errors='coerce').dt.strftime('%Y-%m-%d'))
            
            # 4. 比对 (只看 11-04 之前的)
            valid_targets = {d for d in target_dates if d <= MAX_CHECK_DATE}
            missing = valid_targets - min_dates
            
            if missing:
                missing_records.append({
                    'code': p.stem, # 记录原始文件名方便查找
                    'pure_code': pure_code,
                    'missing_days': len(missing),
                    'first_missing': min(missing),
                    'last_missing': max(missing)
                })
                
        except Exception as e:
            # 文件损坏
            pass

    # --- 5. 结果 ---
    if missing_records:
        report_df = pd.DataFrame(missing_records)
        report_df.sort_values('missing_days', ascending=False, inplace=True)
        report_df.to_csv('Real_Missing_Report.csv', index=False)
        print(f"\n❌ 发现 {len(missing_records)} 个文件有缺失！")
        print("详情请看生成的表格: Real_Missing_Report.csv")
    else:
        print("\n🎉 完美！所有 CSV 确实都完整覆盖了日线。")

if __name__ == '__main__':
    validate_csv_strict()