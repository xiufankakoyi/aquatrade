"""
爬虫行为规范包装器 (Crawler Etiquette)
=====================================

实现防封禁三件套：
1. 随机请求抖动（Random Delay）
2. 动态 User-Agent 轮换
3. 异常回退机制（指数退避重试）

使用示例:
    >>> @crawler_retry(max_retries=3, base_delay=1.0)
    >>> def fetch_data(url):
    >>>     return requests.get(url, headers=rotate_user_agent())
    
    >>> # 或使用类继承
    >>> class MyCrawler(CrawlerEtiquette):
    >>>     def fetch(self, url):
    >>>         return self.safe_request(url)
"""

import random
import time
import functools
from typing import Optional, List, Callable, Dict, Any
from datetime import datetime

from config.logger import get_logger

logger = get_logger(__name__)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0",
]


def rotate_user_agent() -> str:
    """
    轮换 User-Agent
    
    Returns:
        随机选择的 User-Agent 字符串
    """
    return random.choice(USER_AGENTS)


def random_delay(
    min_delay: float = 1.5,
    max_delay: float = 3.5
) -> float:
    """
    随机延迟
    
    Args:
        min_delay: 最小延迟（秒）
        max_delay: 最大延迟（秒）
        
    Returns:
        实际延迟时间
    """
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
    return delay


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True
) -> float:
    """
    指数退避计算
    
    Args:
        attempt: 当前尝试次数（从 0 开始）
        base_delay: 基础延迟
        max_delay: 最大延迟
        jitter: 是否添加随机抖动
        
    Returns:
        延迟时间（秒）
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    
    if jitter:
        delay = delay * (0.5 + random.random())
    
    return delay


def crawler_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    爬虫重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟
        max_delay: 最大延迟
        exceptions: 要捕获的异常类型
        on_retry: 重试时的回调函数
        
    使用示例:
        >>> @crawler_retry(max_retries=3, base_delay=1.0)
        >>> def fetch_page(url):
        >>>     response = requests.get(url, timeout=10)
        >>>     response.raise_for_status()
        >>>     return response.text
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        delay = exponential_backoff(attempt - 1, base_delay, max_delay)
                        logger.warning(
                            f"[Crawler] 第 {attempt} 次重试 {func.__name__}，"
                            f"等待 {delay:.2f}s"
                        )
                        time.sleep(delay)
                        
                        if on_retry:
                            on_retry(attempt, last_exception)
                    
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"[Crawler] {func.__name__} 失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    
                    if attempt == max_retries:
                        logger.error(f"[Crawler] {func.__name__} 重试耗尽")
                        raise
            
            return None
        
        return wrapper
    return decorator


class CrawlerEtiquette:
    """
    爬虫行为规范基类
    
    封装了防封禁三件套，子类继承后可直接使用。
    
    使用示例:
        >>> class EastMoneyCrawler(CrawlerEtiquette):
        >>>     def fetch_dragon_list(self, date: str):
        >>>         url = f"https://data.eastmoney.com/..."
        >>>         response = self.safe_request(url)
        >>>         return response.json()
    """
    
    def __init__(
        self,
        name: str = "Crawler",
        min_delay: float = 1.5,
        max_delay: float = 3.5,
        max_retries: int = 3,
        base_backoff: float = 1.0
    ):
        self._name = name
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._request_count = 0
        self._last_request_time: Optional[float] = None
    
    def _get_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        获取请求头（包含随机 UA）
        
        Args:
            extra_headers: 额外的请求头
            
        Returns:
            完整的请求头字典
        """
        headers = {
            "User-Agent": rotate_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        
        if extra_headers:
            headers.update(extra_headers)
        
        return headers
    
    def _apply_delay(self) -> None:
        """应用随机延迟"""
        random_delay(self._min_delay, self._max_delay)
    
    def safe_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        **kwargs
    ):
        """
        安全请求（带重试和延迟）
        
        Args:
            url: 请求 URL
            method: HTTP 方法
            params: URL 参数
            data: 表单数据
            json_data: JSON 数据
            headers: 请求头
            timeout: 超时时间
            **kwargs: 其他 requests 参数
            
        Returns:
            requests.Response 对象
        """
        import requests
        
        final_headers = self._get_headers(headers)
        
        last_exception = None
        
        for attempt in range(self._max_retries + 1):
            try:
                if attempt > 0:
                    delay = exponential_backoff(attempt - 1, self._base_backoff)
                    logger.warning(
                        f"[{self._name}] 第 {attempt} 次重试请求: {url[:50]}..."
                    )
                    time.sleep(delay)
                
                self._apply_delay()
                
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=final_headers,
                    timeout=timeout,
                    **kwargs
                )
                
                response.raise_for_status()
                
                self._request_count += 1
                self._last_request_time = time.time()
                
                return response
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(
                    f"[{self._name}] 请求失败 (尝试 {attempt + 1}/{self._max_retries + 1}): {e}"
                )
                
                if attempt == self._max_retries:
                    logger.error(f"[{self._name}] 请求重试耗尽: {url[:50]}...")
                    raise
        
        return None
    
    def safe_get(self, url: str, **kwargs):
        """安全 GET 请求"""
        return self.safe_request(url, method="GET", **kwargs)
    
    def safe_post(self, url: str, **kwargs):
        """安全 POST 请求"""
        return self.safe_request(url, method="POST", **kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取爬虫统计信息"""
        return {
            "name": self._name,
            "request_count": self._request_count,
            "last_request_time": self._last_request_time
        }


class TushareBatchFetcher(CrawlerEtiquette):
    """
    Tushare 批量数据拉取器
    
    按日期拉取全市场数据，避免逐股票请求。
    """
    
    def __init__(self, token: Optional[str] = None):
        super().__init__(
            name="TushareFetcher",
            min_delay=0.1,
            max_delay=0.3,
            max_retries=3
        )
        
        self._token = token
        self._pro = None
    
    def _init_pro(self):
        """初始化 Tushare Pro API"""
        if self._pro is None:
            import tushare as ts
            if self._token:
                ts.set_token(self._token)
            self._pro = ts.pro_api()
        return self._pro
    
    def fetch_daily_by_date(
        self,
        trade_date: str,
        fields: Optional[List[str]] = None
    ) -> "pl.DataFrame":
        """
        按日期拉取全市场日线数据
        
        Args:
            trade_date: 交易日期 (YYYYMMDD)
            fields: 需要的字段列表
            
        Returns:
            Polars DataFrame（原始除权数据）
        """
        import polars as pl
        
        pro = self._init_pro()
        
        default_fields = [
            "ts_code", "trade_date", "open", "high", "low", "close",
            "vol", "amount", "adj_factor", "pct_chg"
        ]
        
        fetch_fields = fields or default_fields
        
        df = pro.daily(
            trade_date=trade_date,
            fields=",".join(fetch_fields)
        )
        
        if df is None or df.empty:
            return pl.DataFrame()
        
        result_df = pl.from_pandas(df)
        
        result_df = result_df.with_columns([
            pl.col("ts_code").alias("stock_code"),
            pl.col("vol").alias("volume")
        ])
        
        if "adj_factor" not in result_df.columns:
            result_df = result_df.with_columns(pl.lit(1.0).alias("adj_factor"))
        
        return result_df
    
    def fetch_adj_factor(
        self,
        ts_code: Optional[str] = None,
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> "pl.DataFrame":
        """
        拉取复权因子
        
        Args:
            ts_code: 股票代码
            trade_date: 单日日期
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Polars DataFrame
        """
        import polars as pl
        
        pro = self._init_pro()
        
        df = pro.adj_factor(
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date
        )
        
        if df is None or df.empty:
            return pl.DataFrame()
        
        return pl.from_pandas(df)
