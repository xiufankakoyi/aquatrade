"""
清除缓存
"""
import shutil
from pathlib import Path

cache_dir = Path("data/factor_matrix_cache")
if cache_dir.exists():
    for f in cache_dir.glob("*"):
        f.unlink()
    print("缓存已清除")
else:
    print("缓存目录不存在")
