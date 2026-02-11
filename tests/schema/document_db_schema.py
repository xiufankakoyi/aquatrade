import os
import sqlite3
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from config.config import Config
    from data_svc.lance_manager import LanceDBManager
    import pandas as pd
    try:
        import duckdb
    except ImportError:
        duckdb = None
    try:
        import pyarrow.parquet as pq
    except ImportError:
        pq = None
except ImportError as e:
    print(f"导入失败: {e}")
    sys.exit(1)

def document_sqlite(db_path):
    """文档化 SQLite 数据库结构"""
    print(f"正在读取 SQLite: {db_path}")
    if not os.path.exists(db_path):
        return f"> [!WARNING]\n> SQLite 数据库未找到: `{db_path}`\n"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cursor.fetchall()]
        
        md = "### 1. SQLite 核心业务数据库\n\n"
        md += f"- **路径**: `{os.path.relpath(db_path, Config.BASE_DIR)}`\n"
        md += "- **说明**: 存储策略、回测结果、交易明细等核心业务数据。\n\n"
        
        for table in tables:
            md += f"#### 表: `{table}`\n"
            md += "| 字段名 | 类型 | 必填 | 主键 | 默认值 |\n"
            md += "| --- | --- | --- | --- | --- |\n"
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            for col in columns:
                not_null = "✅" if col[3] else "❌"
                is_pk = "🔑" if col[5] else ""
                default_val = col[4] if col[4] is not None else "NULL"
                md += f"| {col[1]} | {col[2]} | {not_null} | {is_pk} | {default_val} |\n"
            md += "\n"
        
        conn.close()
        return md
    except Exception as e:
        return f"SQLite 文档化失败: {e}\n"

def document_duckdb_parquet():
    """文档化 DuckDB 视图与 Parquet 源文件结构 (查全)"""
    print(f"正在分析 Parquet 数据目录: {Config.PARQUET_DIR}")
    if not os.path.exists(Config.PARQUET_DIR):
        return f"> [!WARNING]\n> Parquet 目录未找到: `{Config.PARQUET_DIR}`\n"
    
    md = "### 2. Parquet & DuckDB 行情存储 (查全)\n\n"
    md += f"- **目录**: `{os.path.relpath(Config.PARQUET_DIR, Config.BASE_DIR)}`\n"
    md += "- **架构**: 使用 DuckDB 作为计算引擎，直接查询 Parquet 文件生成的虚拟视图。\n\n"
    
    parquet_files = [f for f in os.listdir(Config.PARQUET_DIR) if f.endswith('.parquet')]
    
    if not parquet_files:
        md += "> [!NOTE]\n> 该目录下暂无 Parquet 文件。\n"
        return md
    
    for filename in sorted(parquet_files):
        path = os.path.join(Config.PARQUET_DIR, filename)
        md += f"#### 文件/视图: `{filename}`\n"
        md += "| 字段名 | Arrow 类型 |\n"
        md += "| --- | --- |\n"
        try:
            if pq:
                schema = pq.read_schema(path)
                for name, type_ in zip(schema.names, schema.types):
                    md += f"| {name} | {type_} |\n"
            else:
                # Fallback to pandas
                df_sample = pd.read_parquet(path).head(0)
                for col in df_sample.columns:
                    md += f"| {col} | {df_sample[col].dtype} |\n"
        except Exception as e:
            md += f"| ERROR | 读取解析失败: {e} |\n"
        md += "\n"
    
    return md

def document_lancedb():
    """文档化 LanceDB 向量数据库结构"""
    print("正在读取 LanceDB...")
    try:
        manager = LanceDBManager(table_name="stock_daily")
        db = manager.db
        # 使用更现代的 list_tables 方法
        try:
            res = db.list_tables()
            # 处理 ListTablesResponse 对象或普通列表
            if hasattr(res, 'tables'):
                tables = res.tables
            else:
                tables = res
        except AttributeError:
            tables = db.table_names()
            
        md = "### 3. LanceDB 向量数据库 (未来扩展)\n\n"
        md += f"- **路径**: `{os.path.relpath(manager.lance_dir, Config.BASE_DIR)}`\n"
        md += "- **说明**: 用于极速行情检索与向量量化实验。\n\n"
        
        if not tables:
            md += "> [!NOTE]\n> LanceDB 目前尚未创建物理表，系统优先使用 Parquet 后端。\n"
            return md

        for table_name in tables:
            # 兼容处理表对象或字符串
            if hasattr(table_name, 'name'):
                table_name = table_name.name
            elif isinstance(table_name, tuple):
                table_name = table_name[0]
            
            md += f"#### 表: `{table_name}`\n"
            md += "| 字段名 | Arrow 类型 |\n"
            md += "| --- | --- |\n"
            table = db.open_table(table_name)
            schema = table.schema
            for field in schema:
                md += f"| {field.name} | {field.type} |\n"
            md += "\n"
        return md
    except Exception as e:
        return f"> [!NOTE]\n> LanceDB 文档化跳过: {e}\n"

def update_readme(content):
    """更新项目根目录的 README.md"""
    readme_path = os.path.join(Config.BASE_DIR, "README.md")
    print(f"正在更新 README: {readme_path}")
    
    if not os.path.exists(readme_path):
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# Aquatrade 项目指南\n\n")
    
    with open(readme_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    start_marker = "<!-- DB_SCHEMA_START -->"
    end_marker = "<!-- DB_SCHEMA_END -->"
    
    new_lines = []
    in_schema = False
    found_marker = False
    
    for line in lines:
        if start_marker in line:
            new_lines.append(line)
            new_lines.append("\n" + content + "\n")
            in_schema = True
            found_marker = True
        elif end_marker in line:
            new_lines.append(line)
            in_schema = False
        elif not in_schema:
            new_lines.append(line)
            
    if not found_marker:
        new_lines.append("\n## 📊 数据库开发指南 (Auto-generated)\n\n")
        new_lines.append("该部分由 `tests/schema/document_db_schema.py` 自动生成，请勿手动修改。\n\n")
        new_lines.append(start_marker + "\n")
        new_lines.append(content + "\n")
        new_lines.append(end_marker + "\n")
        
    with open(readme_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    print("开始执行全量数据库文档化 (查全)...")
    sqlite_md = document_sqlite(Config.DB_PATH)
    parquet_md = document_duckdb_parquet()
    lancedb_md = document_lancedb()
    
    full_md = "## 存储架构概览\n\n本项目当前处于 **码数合一** 后的优化阶段，采用了多级存储方案：\n"
    full_md += "1. **SQLite**: 负责 CRUD 业务数据（订单、结果、配置）。\n"
    full_md += "2. **Parquet/DuckDB**: 负责大规模回测行情数据的高速读取（当前主方案，查全必看）。\n"
    full_md += "3. **LanceDB**: 负责向量化行情与极速缓存（逐步迁移中）。\n\n---\n\n"
    
    full_md += sqlite_md + "\n---\n\n" + parquet_md + "\n---\n\n" + lancedb_md
    
    update_readme(full_md)
    print("✅ 全量文档生成成功！")
