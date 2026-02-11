
import os
import sys

# Ensure project root is in path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from config.logger import get_logger
from data_svc.lance_manager import LanceDBManager

logger = get_logger(__name__)

def optimize_all_tables():
    logger.info("Starting LanceDB optimization...")
    
    tables = ["stock_limit_status", "stock_daily", "benchmark_data", "stock_info"]
    
    for table_name in tables:
        try:
            logger.info(f"Optimizing table: {table_name}")
            manager = LanceDBManager(table_name=table_name)
            manager.optimize_table()
            logger.info(f"✓ Optimized {table_name}")
        except Exception as e:
            logger.error(f"Failed to optimize {table_name}: {e}")
            
    logger.info("Optimization complete.")

if __name__ == "__main__":
    optimize_all_tables()
