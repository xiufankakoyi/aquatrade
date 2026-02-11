# scripts/generate_schema_doc.py
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def generate():
    """扫描数据库并生成专业的 Markdown 架构文档"""
    db = OptimizedStockDataQuery()
    tables = ["stock_daily", "stock_info", "benchmark_data", "stock_limit_status"]
    output_path = PROJECT_ROOT / "docs" / "SCHEMA.md"
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Aquatrade Database Schema\n\n")
        f.write("此文档由 `scripts/generate_schema_doc.py` 自动生成，用于记录当前数据库的所有字段，方便策略开发。\n\n")
        
        for table in tables:
            f.write(f"## 数据表: `{table}`\n")
            columns = db._get_table_columns(table)
            if not columns:
                f.write("> [!WARNING]\n> 该表在当前后端（LanceDB/DuckDB）中为空或未找到。\n\n")
                continue
            
            f.write("| 序号 | 字段名 (Column Name) | 备注 (Notes) |\n")
            f.write("| :--- | :--- | :--- |\n")
            for idx, col in enumerate(sorted(list(columns)), 1):
                # 为一些核心字段添加简单备注
                note = ""
                if col == 'total_mv': note = "总市值 (策略核心过滤字段)"
                elif col == 'volume_ratio': note = "量比 (策略核心过滤字段)"
                elif col == 'trade_date': note = "交易日期 (格式: YYYY-MM-DD)"
                elif col == 'adj_factor': note = "复权因子"
                
                f.write(f"| {idx} | `{col}` | {note} |\n")
            f.write("\n")
            
    print(f"✅ 架构文档已生成: {output_path}")

if __name__ == "__main__":
    generate()
