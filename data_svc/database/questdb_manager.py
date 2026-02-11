"""
QuestDB 数据管理器
==================
提供与 QuestDB 的连接和数据操作接口。

使用方式:
    from data_svc.database.questdb_manager import QuestDBManager
    
    qdb = QuestDBManager()
    qdb.insert_daily_data(df)
    result = qdb.query("SELECT * FROM base_daily WHERE code = '000001.SZ'")
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import polars as pl

# QuestDB 配置
QUESTDB_HOST = os.getenv("QUESTDB_HOST", "localhost")
QUESTDB_HTTP_PORT = int(os.getenv("QUESTDB_HTTP_PORT", "9000"))
QUESTDB_ILP_PORT = int(os.getenv("QUESTDB_ILP_PORT", "9009"))
QUESTDB_PG_PORT = int(os.getenv("QUESTDB_PG_PORT", "8812"))


class QuestDBManager:
    """
    QuestDB 数据管理器
    
    支持三种连接方式：
    1. ILP (InfluxDB Line Protocol) - 高速批量写入
    2. HTTP REST API - 查询和DDL
    3. PostgreSQL Wire Protocol - 兼容 SQL 客户端
    """
    
    def __init__(self, host: str = QUESTDB_HOST):
        self.host = host
        self.http_port = QUESTDB_HTTP_PORT
        self.ilp_port = QUESTDB_ILP_PORT
        self.pg_port = QUESTDB_PG_PORT
        self._sender = None
        
    def _get_sender(self):
        """获取 ILP Sender (用于高速写入)"""
        if self._sender is None:
            from questdb.ingress import Sender, IngressError
            self._sender = Sender(host=self.host, port=self.ilp_port)
        return self._sender
    
    def close(self):
        """关闭连接"""
        if self._sender:
            self._sender.close()
            self._sender = None
    
    # ==================== DDL 操作 ====================
    
    def create_tables(self):
        """创建所有因子表结构"""
        import requests
        
        ddl_statements = [
            # 基础行情表 (使用实际发现的列名以保持一致)
            """
            CREATE TABLE IF NOT EXISTS base_daily (
                timestamp TIMESTAMP,
                stock_code SYMBOL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume LONG,
                amount DOUBLE,
                adj_factor DOUBLE,
                prev_close DOUBLE
            ) TIMESTAMP(timestamp) PARTITION BY MONTH;
            """,
            
            # 动量因子表
            """
            CREATE TABLE IF NOT EXISTS factors_momentum (
                timestamp TIMESTAMP,
                stock_code SYMBOL,
                rsi_14 DOUBLE,
                kdj_k DOUBLE,
                kdj_d DOUBLE,
                kdj_j DOUBLE,
                macd_dif DOUBLE,
                macd_dea DOUBLE,
                macd_histogram DOUBLE,
                atr_14 DOUBLE,
                ma5 DOUBLE,
                ma10 DOUBLE,
                ma20 DOUBLE,
                ma60 DOUBLE,
                ma120 DOUBLE,
                ma250 DOUBLE,
                boll_upper DOUBLE,
                boll_mid DOUBLE,
                boll_lower DOUBLE,
                bias_5 DOUBLE,
                bias_10 DOUBLE,
                bias_20 DOUBLE
            ) TIMESTAMP(timestamp) PARTITION BY MONTH;
            """,
            
            # 估值因子表
            """
            CREATE TABLE IF NOT EXISTS factors_valuation (
                trade_date TIMESTAMP,
                stock_code SYMBOL,
                pe DOUBLE,
                pe_ttm DOUBLE,
                pb DOUBLE,
                ps DOUBLE,
                ps_ttm DOUBLE,
                total_mv DOUBLE,
                float_mv DOUBLE,
                turnover_rate DOUBLE,
                turnover_free DOUBLE,
                volume_ratio DOUBLE,
                dividend_yield DOUBLE
            ) TIMESTAMP(trade_date) PARTITION BY MONTH;
            """,
            
            # 实验因子表
            """
            CREATE TABLE IF NOT EXISTS factors_experimental (
                timestamp TIMESTAMP,
                stock_code SYMBOL,
                is_limit_up BOOLEAN,
                is_limit_down BOOLEAN,
                is_opened BOOLEAN,
                is_suspended BOOLEAN,
                guba_sentiment DOUBLE,
                guba_heat DOUBLE
            ) TIMESTAMP(timestamp) PARTITION BY MONTH;
            """,
            
            # 创建统一视图 (兼容代码中的旧表名或标准表名)
            "CREATE VIEW IF NOT EXISTS stock_daily AS SELECT timestamp AS trade_date, stock_code, open, high, low, close, volume, amount, adj_factor, prev_close FROM base_daily",
            "CREATE VIEW IF NOT EXISTS benchmark_data AS SELECT timestamp AS trade_date, stock_code, close, open, high, low, volume, amount FROM base_daily WHERE stock_code = '000300.SH'"
        ]
        
        results = []
        for ddl in ddl_statements:
            try:
                resp = requests.get(
                    f"http://{self.host}:{self.http_port}/exec",
                    params={"query": ddl.strip()}
                )
                results.append({"success": resp.status_code == 200, "response": resp.text})
            except Exception as e:
                results.append({"success": False, "error": str(e)})
        
        return results
    
    # ==================== 数据写入 ====================
    
    def insert_base_daily(self, df: pl.DataFrame):
        """
        批量插入基础行情数据 (使用 ILP 高速协议)
        
        Args:
            df: Polars DataFrame，必须包含 trade_date, stock_code 等列
        """
        from questdb.ingress import Sender
        
        with Sender(self.host, self.ilp_port) as sender:
            for row in df.iter_rows(named=True):
                # 解析日期
                ts = self._parse_timestamp(row.get("trade_date") or row.get("ts"))
                
                sender.row(
                    "base_daily",
                    symbols={"code": row.get("stock_code") or row.get("code")},
                    columns={
                        "open": float(row.get("open", 0) or 0),
                        "high": float(row.get("high", 0) or 0),
                        "low": float(row.get("low", 0) or 0),
                        "close": float(row.get("close", 0) or 0),
                        "volume": int(row.get("volume", 0) or 0),
                        "amount": float(row.get("amount", 0) or 0),
                        "adj_factor": float(row.get("adj_factor", 1) or 1),
                        "prev_close": float(row.get("prev_close", 0) or 0),
                    },
                    at=ts
                )
            sender.flush()
    
    def insert_factors_momentum(self, df: pl.DataFrame):
        """批量插入动量因子数据"""
        from questdb.ingress import Sender
        
        momentum_cols = [
            "rsi_14", "kdj_k", "kdj_d", "kdj_j",
            "macd_dif", "macd_dea", "macd_histogram", "atr_14",
            "ma5", "ma10", "ma20", "ma60", "ma120", "ma250",
            "boll_upper", "boll_mid", "boll_lower",
            "bias_5", "bias_10", "bias_20"
        ]
        
        with Sender(self.host, self.ilp_port) as sender:
            for row in df.iter_rows(named=True):
                ts = self._parse_timestamp(row.get("trade_date") or row.get("ts"))
                
                columns = {}
                for col in momentum_cols:
                    val = row.get(col)
                    if val is not None and val == val:  # 排除 NaN
                        columns[col] = float(val)
                
                sender.row(
                    "factors_momentum",
                    symbols={"code": row.get("stock_code") or row.get("code")},
                    columns=columns,
                    at=ts
                )
            sender.flush()
    
    def insert_factors_valuation(self, df: pl.DataFrame):
        """批量插入估值因子数据"""
        from questdb.ingress import Sender
        
        valuation_cols = [
            "pe", "pe_ttm", "pb", "ps", "ps_ttm",
            "total_mv", "float_mv", "turnover_rate", "turnover_free",
            "volume_ratio", "dividend_yield"
        ]
        
        with Sender(self.host, self.ilp_port) as sender:
            for row in df.iter_rows(named=True):
                ts = self._parse_timestamp(row.get("trade_date") or row.get("ts"))
                
                columns = {}
                for col in valuation_cols:
                    val = row.get(col)
                    if val is not None and val == val:
                        columns[col] = float(val)
                
                sender.row(
                    "factors_valuation",
                    symbols={"code": row.get("stock_code") or row.get("code")},
                    columns=columns,
                    at=ts
                )
            sender.flush()
    
    # ==================== 数据查询 ====================
    
    def query(self, sql: str) -> pl.DataFrame:
        """
        执行 SQL 查询并返回 Polars DataFrame
        
        Args:
            sql: SQL 查询语句
            
        Returns:
            Polars DataFrame
        """
        import requests
        import json
        
        resp = requests.get(
            f"http://{self.host}:{self.http_port}/exec",
            params={"query": sql}
        )
        
        if resp.status_code != 200:
            raise RuntimeError(f"Query failed: {resp.text}")
        
        data = resp.json()
        columns = [col["name"] for col in data.get("columns", [])]
        rows = data.get("dataset", [])
        
        if not rows:
            return pl.DataFrame()
        
        return pl.DataFrame(rows, schema=columns, orient="row")
    
    def get_daily_data(
        self, 
        codes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pl.DataFrame:
        """
        获取基础行情数据
        
        Args:
            codes: 股票代码列表
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        """
        conditions = []
        
        if codes:
            code_list = ",".join([f"'{c}'" for c in codes])
            conditions.append(f"code IN ({code_list})")
        
        if start_date:
            conditions.append(f"ts >= '{start_date}'")
        
        if end_date:
            conditions.append(f"ts <= '{end_date}'")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        sql = f"SELECT * FROM base_daily WHERE {where_clause} ORDER BY ts, code"
        return self.query(sql)
    
    # ==================== 工具方法 ====================
    
    def _parse_timestamp(self, value) -> int:
        """将日期值转换为纳秒时间戳"""
        if isinstance(value, (int, float)):
            # 假设是秒级时间戳
            return int(value * 1_000_000_000)
        elif isinstance(value, str):
            # 尝试解析日期字符串
            for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(value, fmt)
                    return int(dt.timestamp() * 1_000_000_000)
                except ValueError:
                    continue
        elif isinstance(value, (datetime, date)):
            if isinstance(value, date) and not isinstance(value, datetime):
                value = datetime.combine(value, datetime.min.time())
            return int(value.timestamp() * 1_000_000_000)
        
        raise ValueError(f"Cannot parse timestamp: {value}")
    
    def health_check(self) -> bool:
        """检查 QuestDB 服务是否可用"""
        import requests
        try:
            resp = requests.get(f"http://{self.host}:{self.http_port}/exec", params={"query": "SELECT 1"}, timeout=5)
            return resp.status_code == 200
        except:
            return False


# 单例实例
_instance: Optional[QuestDBManager] = None

def get_questdb_manager() -> QuestDBManager:
    """获取 QuestDB 管理器单例"""
    global _instance
    if _instance is None:
        _instance = QuestDBManager()
    return _instance
