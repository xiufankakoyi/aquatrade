#!/usr/bin/env python3
"""
检查所有 Parquet 文件的列结构，并查找 benchmark 数据位置
"""
import os
import sys
from pathlib import Path
import pandas as pd
try:
    import pyarrow.parquet as pq
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False
    print("警告: pyarrow 未安装，将使用 pandas 读取（可能较慢）")

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config.config import Config
import sqlite3


def check_sqlite_tables(db_path: str) -> dict:
    """检查 SQLite 数据库中的表结构"""
    result = {
        'db_path': db_path,
        'exists': False,
        'tables': [],
        'benchmark_info': None
    }
    
    if not os.path.exists(db_path):
        result['error'] = "数据库文件不存在"
        return result
    
    result['exists'] = True
    result['size_mb'] = round(os.path.getsize(db_path) / (1024 * 1024), 2)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        result['tables'] = tables
        
        # 检查 benchmark_data 表
        if 'benchmark_data' in tables:
            cursor.execute("PRAGMA table_info(benchmark_data)")
            columns = [{'name': row[1], 'type': row[2]} for row in cursor.fetchall()]
            
            # 获取数据行数
            cursor.execute("SELECT COUNT(*) FROM benchmark_data")
            row_count = cursor.fetchone()[0]
            
            # 获取样本数据
            cursor.execute("SELECT * FROM benchmark_data LIMIT 3")
            sample_rows = cursor.fetchall()
            column_names = [col['name'] for col in columns]
            sample_data = [dict(zip(column_names, row)) for row in sample_rows]
            
            # 获取基准代码列表
            cursor.execute("SELECT DISTINCT code FROM benchmark_data")
            codes = [row[0] for row in cursor.fetchall()]
            
            result['benchmark_info'] = {
                'columns': columns,
                'row_count': row_count,
                'sample_data': sample_data,
                'codes': codes
            }
        
        conn.close()
    except Exception as e:
        result['error'] = str(e)
        import traceback
        result['traceback'] = traceback.format_exc()
    
    return result


def get_parquet_files(parquet_dir: Path) -> list[Path]:
    """获取所有 parquet 文件"""
    parquet_files = []
    if parquet_dir.exists():
        for file in parquet_dir.glob("*.parquet"):
            parquet_files.append(file)
    return sorted(parquet_files)


def inspect_parquet_file(file_path: Path) -> dict:
    """检查单个 parquet 文件的结构"""
    result = {
        'file': str(file_path.name),
        'path': str(file_path),
        'exists': file_path.exists(),
        'size_mb': 0,
        'columns': [],
        'num_rows': 0,
        'sample_data': None,
        'error': None
    }
    
    if not file_path.exists():
        result['error'] = "文件不存在"
        return result
    
    try:
        # 获取文件大小
        result['size_mb'] = round(file_path.stat().st_size / (1024 * 1024), 2)
        
        if PYARROW_AVAILABLE:
            # 使用 pyarrow 快速读取元数据（不加载全部数据）
            parquet_file = pq.ParquetFile(file_path)
            schema = parquet_file.schema
            result['columns'] = [field.name for field in schema]
            result['num_rows'] = parquet_file.metadata.num_rows
            
            # 读取前几行作为样本
            try:
                sample = parquet_file.read_row_groups([0], columns=result['columns'][:10]).to_pandas()
                if len(sample) > 0:
                    result['sample_data'] = sample.head(3).to_dict('records')
            except Exception as e:
                result['error'] = f"读取样本数据失败: {e}"
        else:
            # 使用 pandas 读取（较慢，但兼容性好）
            df = pd.read_parquet(file_path, nrows=100)  # 只读前100行
            result['columns'] = list(df.columns)
            result['num_rows'] = len(df)
            if len(df) > 0:
                result['sample_data'] = df.head(3).to_dict('records')
                
    except Exception as e:
        result['error'] = str(e)
        import traceback
        result['traceback'] = traceback.format_exc()
    
    return result


def find_benchmark_columns(results: list[dict]) -> dict:
    """查找包含 benchmark 相关列的文件"""
    benchmark_keywords = ['benchmark', 'index', '000300', '000001', '399001', '399006']
    benchmark_files = []
    
    for result in results:
        if result.get('error'):
            continue
        
        columns = result.get('columns', [])
        matching_columns = []
        
        for col in columns:
            col_lower = col.lower()
            for keyword in benchmark_keywords:
                if keyword in col_lower:
                    matching_columns.append(col)
                    break
        
        if matching_columns:
            benchmark_files.append({
                'file': result['file'],
                'columns': matching_columns,
                'all_columns': columns
            })
    
    return benchmark_files


def print_report(results: list[dict], benchmark_files: list[dict], db_info: dict = None):
    """打印详细报告"""
    print("=" * 80)
    print("Parquet 文件结构检查报告")
    print("=" * 80)
    print()
    
    # 1. 文件概览
    print("[文件概览]")
    print("-" * 80)
    for result in results:
        status = "[OK]" if result['exists'] and not result.get('error') else "[FAIL]"
        size_info = f"{result['size_mb']} MB" if result['size_mb'] > 0 else "N/A"
        rows_info = f"{result['num_rows']:,} 行" if result['num_rows'] > 0 else "N/A"
        print(f"{status} {result['file']:40s} | {size_info:10s} | {rows_info:15s}")
        if result.get('error'):
            print(f"   错误: {result['error']}")
    print()
    
    # 2. 每个文件的详细列信息
    print("=" * 80)
    print("[详细列信息]")
    print("=" * 80)
    for result in results:
        if result.get('error'):
            continue
        
        print(f"\n[文件] {result['file']}")
        print(f"   路径: {result['path']}")
        print(f"   大小: {result['size_mb']} MB")
        print(f"   行数: {result['num_rows']:,}")
        print(f"   列数: {len(result['columns'])}")
        print(f"   列名:")
        for i, col in enumerate(result['columns'], 1):
            print(f"      {i:2d}. {col}")
        
        # 显示样本数据
        if result.get('sample_data'):
            print(f"   样本数据（前3行）:")
            for idx, row in enumerate(result['sample_data'], 1):
                print(f"      行 {idx}: {row}")
        print()
    
    # 3. Benchmark 数据位置
    print("=" * 80)
    print("[Benchmark 数据查找结果]")
    print("=" * 80)
    
    found_in_parquet = False
    if benchmark_files:
        found_in_parquet = True
        for bf in benchmark_files:
            print(f"\n[找到] 在 Parquet 文件 '{bf['file']}' 中找到 benchmark 相关列:")
            for col in bf['columns']:
                print(f"   - {col}")
            print(f"\n   该文件的所有列:")
            for i, col in enumerate(bf['all_columns'], 1):
                marker = " [*]" if col in bf['columns'] else ""
                print(f"      {i:2d}. {col}{marker}")
    
    # 检查 SQLite 数据库
    if db_info:
        print(f"\n[SQLite 数据库] {db_info['db_path']}")
        if db_info.get('exists'):
            print(f"   存在: 是")
            print(f"   大小: {db_info.get('size_mb', 0)} MB")
            print(f"   表列表: {', '.join(db_info.get('tables', []))}")
            
            if db_info.get('benchmark_info'):
                bm_info = db_info['benchmark_info']
                print(f"\n   [找到] benchmark_data 表存在！")
                print(f"   行数: {bm_info['row_count']:,}")
                print(f"   列结构:")
                for col in bm_info['columns']:
                    print(f"      - {col['name']}: {col['type']}")
                print(f"   基准代码列表: {', '.join(bm_info['codes'])}")
                print(f"   样本数据（前3行）:")
                for idx, row in enumerate(bm_info['sample_data'], 1):
                    print(f"      行 {idx}: {row}")
            else:
                print(f"\n   [未找到] benchmark_data 表不存在")
        else:
            print(f"   存在: 否")
            if db_info.get('error'):
                print(f"   错误: {db_info['error']}")
    
    if not found_in_parquet and not (db_info and db_info.get('benchmark_info')):
        print("\n[未找到] 未找到 benchmark 数据")
        print("\n   搜索关键词: benchmark, index, 000300, 000001, 399001, 399006")
        print("\n   建议检查:")
        print("   1. benchmark 数据是否在 SQLite 数据库中（需要创建 benchmark_data 表）")
        print("   2. benchmark 数据是否需要从外部数据源导入")
        print("   3. benchmark 数据是否需要单独生成 Parquet 文件")
    print()
    
    # 4. 列名统计
    print("=" * 80)
    print("[列名统计（所有文件）]")
    print("=" * 80)
    all_columns = {}
    for result in results:
        if result.get('error'):
            continue
        for col in result.get('columns', []):
            if col not in all_columns:
                all_columns[col] = []
            all_columns[col].append(result['file'])
    
    # 按出现频率排序
    sorted_columns = sorted(all_columns.items(), key=lambda x: len(x[1]), reverse=True)
    print(f"\n总共发现 {len(sorted_columns)} 个不同的列名:")
    for col, files in sorted_columns[:50]:  # 只显示前50个
        print(f"   {col:30s} -> 出现在 {len(files)} 个文件中: {', '.join(files)}")
    if len(sorted_columns) > 50:
        print(f"   ... 还有 {len(sorted_columns) - 50} 个列名未显示")
    print()


def main():
    """主函数"""
    parquet_dir = Path(Config.PARQUET_DIR)
    
    print(f"正在检查 Parquet 文件目录: {parquet_dir}")
    print(f"目录存在: {parquet_dir.exists()}")
    print()
    
    if not parquet_dir.exists():
        print(f"❌ 错误: Parquet 目录不存在: {parquet_dir}")
        print(f"   请检查 config/config.py 中的 PARQUET_DIR 配置")
        return
    
    # 获取所有 parquet 文件
    parquet_files = get_parquet_files(parquet_dir)
    
    if not parquet_files:
        print(f"❌ 未找到任何 .parquet 文件")
        return
    
    print(f"找到 {len(parquet_files)} 个 Parquet 文件:")
    for f in parquet_files:
        print(f"   - {f.name}")
    print()
    
    # 检查每个文件
    print("正在检查文件结构...")
    results = []
    for file_path in parquet_files:
        print(f"   检查: {file_path.name}...")
        result = inspect_parquet_file(file_path)
        results.append(result)
    
    print()
    
    # 查找 benchmark 数据
    benchmark_files = find_benchmark_columns(results)
    
    # 检查 SQLite 数据库
    print("\n正在检查 SQLite 数据库...")
    db_info = check_sqlite_tables(Config.DB_PATH)
    
    # 打印报告
    print_report(results, benchmark_files, db_info)
    
    # 保存报告到文件
    report_file = _project_root / "parquet_schema_report.txt"
    import io
    from contextlib import redirect_stdout
    
    with open(report_file, 'w', encoding='utf-8') as f:
        with redirect_stdout(f):
            print_report(results, benchmark_files, db_info)
    
    print(f"[完成] 报告已保存到: {report_file}")


if __name__ == '__main__':
    main()

