"""检查当前配置"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import Config
from config.setting import Setting

print("=" * 60)
print("配置检查")
print("=" * 60)
print(f"\nSetting.DB_BACKEND: {Setting.DB_BACKEND}")
print(f"Config.DB_BACKEND: {Config.DB_BACKEND}")
print(f"is_arcticdb_backend(): {Config.is_arcticdb_backend()}")
print(f"\nARCTICDB_PATH: {Config.ARCTICDB_PATH}")
print(f"ARCTICDB_LIBRARIES: {Config.ARCTICDB_LIBRARIES}")
print(f"\n数据接口: {Config.get_data_interface()}")
