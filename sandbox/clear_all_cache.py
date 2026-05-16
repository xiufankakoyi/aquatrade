"""
清除所有缓存
"""
import shutil
from pathlib import Path

# 清除因子矩阵缓存
cache_dir = Path("data/factor_matrix_cache")
if cache_dir.exists():
    for f in cache_dir.glob("*"):
        f.unlink()
    print("因子矩阵缓存已清除")

# 清除矩阵缓存
matrix_cache_dir = Path("data/matrix_cache")
if matrix_cache_dir.exists():
    shutil.rmtree(matrix_cache_dir, ignore_errors=True)
    print("矩阵缓存已清除")

print("所有缓存已清除")
