import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
q = OptimizedStockDataQuery()
print("表结构:", q.conn.execute('DESCRIBE benchmark_data').fetchall())
print("---")
print("指数代码:", q.conn.execute("SELECT DISTINCT code FROM benchmark_data").fetchall())
q.close()
