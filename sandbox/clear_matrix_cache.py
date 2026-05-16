"""清除矩阵缓存"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

from core.backtest.matrix_cache_manager import get_matrix_cache_manager

cache_manager = get_matrix_cache_manager()
stats = cache_manager.get_cache_stats()
print(f"清除前缓存统计: {stats}")

cache_manager.clear_cache()

stats = cache_manager.get_cache_stats()
print(f"清除后缓存统计: {stats}")
print("矩阵缓存已清除")
