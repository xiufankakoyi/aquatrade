"""数据更新闭环的 shim 入口（已弃用）。

历史原因：早期同时存在两个 update 脚本：
- ``scripts/update/update_market_data_incremental.py``（parquet 主源）
- ``tools/update_market_data_incremental.py``（LanceDB 主源）

为避免用户困惑，已把两条流水线合并到
``scripts/update/update_market_data_incremental.py``，并支持 ``--target`` 选择
写入目标。本文件保留仅作为向后兼容的转发器，打印弃用提示后把命令原样转发到
统一入口。

新写法：
    python scripts/update/update_market_data_incremental.py            # 默认 lancedb
    python scripts/update/update_market_data_incremental.py --target lancedb
    python scripts/update/update_market_data_incremental.py --target parquet
    python scripts/update/update_market_data_incremental.py --target all
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("tools.update_market_data_incremental.shim")


def main() -> int:
    """转发到统一入口，并提示用户改用新位置。"""

    logger.warning(
        "[DEPRECATED] tools/update_market_data_incremental.py 已合并，"
        "请改用 scripts/update/update_market_data_incremental.py；"
        "本 shim 仅做转发，所有参数原样透传。"
    )

    from scripts.update.update_market_data_incremental import main as canonical_main

    return canonical_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
