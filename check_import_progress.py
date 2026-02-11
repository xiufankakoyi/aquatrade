"""
QuestDB 导入进度监控脚本
=======================
快速查看当前导入进度

用法:
    python check_import_progress.py
"""

import psycopg2
import time

QUESTDB_HOST = "localhost"
QUESTDB_PG_PORT = 8812

def check_progress():
    try:
        conn = psycopg2.connect(
            host=QUESTDB_HOST,
            port=QUESTDB_PG_PORT,
            user="admin",
            password="quest",
            database="qdb"
        )
        cursor = conn.cursor()
        
        tables = {
            "base_daily": 6841370,
            "factors_momentum": 6841370,
            "factors_valuation": 6841370
        }
        
        print("=" * 60)
        print("📊 QuestDB 导入进度监控")
        print("=" * 60)
        print()
        
        total_imported = 0
        total_target = sum(tables.values())
        
        for table_name, target_count in tables.items():
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            current_count = cursor.fetchone()[0]
            progress = (current_count / target_count * 100) if target_count > 0 else 0
            
            print(f"📋 {table_name}")
            print(f"   当前: {current_count:,} / {target_count:,} 行")
            print(f"   进度: {progress:.1f}%")
            print()
            
            total_imported += current_count
        
        overall_progress = (total_imported / total_target * 100) if total_target > 0 else 0
        print("=" * 60)
        print(f"总体进度: {overall_progress:.1f}% ({total_imported:,} / {total_target:,})")
        print("=" * 60)
        
        cursor.close()
        conn.close()
        
        return overall_progress
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return 0


if __name__ == "__main__":
    while True:
        progress = check_progress()
        
        if progress >= 99.9:
            print("\n✅ 导入完成！")
            break
        
        print("\n等待 30 秒后刷新... (按 Ctrl+C 退出)")
        try:
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n\n已退出监控")
            break
