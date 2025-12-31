import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import duckdb


def _get_db_path() -> str:
    """
    获取 DuckDB 文件路径。

    默认放在项目根目录下的 data/trading.duckdb。
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "trading.duckdb")


_DB_PATH = _get_db_path()
_CONN: Optional[duckdb.DuckDBPyConnection] = None


def _get_conn() -> duckdb.DuckDBPyConnection:
    """懒加载获取全局 DuckDB 连接，并确保表已创建。"""
    global _CONN
    if _CONN is None:
        _CONN = duckdb.connect(_DB_PATH)
        _init_schema(_CONN)
    return _CONN


def _init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """初始化 strategy_profiles 表结构。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS strategy_profiles (
            id BIGINT PRIMARY KEY,
            strategy_name VARCHAR NOT NULL,
            profile_name VARCHAR NOT NULL,
            description VARCHAR,
            params JSON NOT NULL,
            source VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def _next_profile_id(conn: duckdb.DuckDBPyConnection) -> int:
    """
    生成下一个自增 id。

    这里不用 DuckDB 的 IDENTITY 语法，是为了兼容较旧版本，
    直接基于当前表内最大 id + 1 生成，足够覆盖本项目的使用场景。
    """
    row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM strategy_profiles").fetchone()
    return int(row[0])


def create_profile(
    strategy_name: str,
    profile_name: str,
    description: Optional[str],
    params_dict: Dict[str, Any],
    source: str = "optimization",
) -> Dict[str, Any]:
    """
    创建一个新的参数预设（Profile）。
    """
    conn = _get_conn()
    new_id = _next_profile_id(conn)
    created_at = datetime.utcnow()
    params_json = json.dumps(params_dict, ensure_ascii=False)

    result = conn.execute(
        """
        INSERT INTO strategy_profiles (id, strategy_name, profile_name, description, params, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id, strategy_name, profile_name, description, params, source, created_at
        """,
        [new_id, strategy_name, profile_name, description, params_json, source, created_at],
    ).fetchone()

    return {
        "id": result[0],
        "strategy_name": result[1],
        "profile_name": result[2],
        "description": result[3],
        "params": json.loads(result[4]) if result[4] is not None else {},
        "source": result[5],
        "created_at": result[6].isoformat() if isinstance(result[6], datetime) else str(result[6]),
    }


def list_profiles(strategy_name: str) -> List[Dict[str, Any]]:
    """
    列出某个策略下的所有预设，按创建时间倒序。
    """
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT id, strategy_name, profile_name, description, params, source, created_at
        FROM strategy_profiles
        WHERE strategy_name = ?
        ORDER BY created_at DESC, id DESC
        """,
        [strategy_name],
    ).fetchall()

    profiles: List[Dict[str, Any]] = []
    for row in rows:
        profiles.append(
            {
                "id": row[0],
                "strategy_name": row[1],
                "profile_name": row[2],
                "description": row[3],
                "params": json.loads(row[4]) if row[4] is not None else {},
                "source": row[5],
                "created_at": row[6].isoformat() if isinstance(row[6], datetime) else str(row[6]),
            }
        )
    return profiles


def get_profile(profile_id: int) -> Optional[Dict[str, Any]]:
    """
    获取单个预设详情。
    """
    conn = _get_conn()
    row = conn.execute(
        """
        SELECT id, strategy_name, profile_name, description, params, source, created_at
        FROM strategy_profiles
        WHERE id = ?
        """,
        [profile_id],
    ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "strategy_name": row[1],
        "profile_name": row[2],
        "description": row[3],
        "params": json.loads(row[4]) if row[4] is not None else {},
        "source": row[5],
        "created_at": row[6].isoformat() if isinstance(row[6], datetime) else str(row[6]),
    }


