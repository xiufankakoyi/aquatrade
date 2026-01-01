"""
情感分析相关路由
"""
from flask import Blueprint, jsonify, request
import pandas as pd
from datetime import datetime, timedelta
import random
from typing import List, Dict, Any
import numpy as np
from pathlib import Path
import duckdb
import re
import warnings
import math
from server.performance_utils import json_response

# 创建蓝图
sentiment_bp = Blueprint('sentiment', __name__, url_prefix='/api')

# 注意：常量和函数在函数内部延迟导入，避免循环依赖

def get_parquet_path() -> Path:
    """获取Parquet文件路径"""
    from config.config import Config
    return Path(Config.PARQUET_DIR) / 'guba_posts.parquet'


@sentiment_bp.route('/stock_sentiment', methods=['GET'])
def get_stock_sentiment():
    """基于股吧爬虫数据的股票舆情汇总，优先使用 Parquet+DuckDB，加速查询。"""
    try:
        base_dir = Path(__file__).parent.parent

        limit_param = request.args.get('limit')
        try:
            limit = int(limit_param) if limit_param is not None else 50
        except (TypeError, ValueError):
            limit = 50

        # 1. 优先尝试使用 Parquet + DuckDB（由 scripts/build_guba_posts_parquet.py 预生成）
        parquet_path = base_dir / 'parquet_data' / 'guba_posts.parquet'
        if duckdb is not None and parquet_path.exists():
            try:
                parquet_str = str(parquet_path).replace('\\', '/')
                # DuckDB 直接在 Parquet 上聚合，避免逐文件读取 CSV
                # 优化：使用 TRY_CAST 但减少重复转换，添加 WHERE 过滤提高性能
                sql = f'''
                    SELECT
                        symbol,
                        COALESCE(CAST(stockbar_code AS VARCHAR), CAST(RIGHT(symbol, 6) AS VARCHAR)) AS stockCode,
                        COALESCE(CAST(stockbar_name AS VARCHAR), '') AS stockName,
                        COUNT(*) AS totalPosts,
                        SUM(COALESCE(TRY_CAST(post_click_count AS BIGINT), 0)) AS totalClicks,
                        SUM(COALESCE(TRY_CAST(post_comment_count AS BIGINT), 0)) AS totalComments,
                        SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) > 0 THEN 1 ELSE 0 END) AS bullishCount,
                        SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) < 0 THEN 1 ELSE 0 END) AS bearishCount,
                        SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) = 0 OR bullish_bearish IS NULL THEN 1 ELSE 0 END) AS neutralCount,
                        COALESCE(AVG(TRY_CAST(bullish_bearish AS DOUBLE)), 0.0) AS sentimentScore,
                        MAX(TRY_CAST(post_publish_time AS TIMESTAMP)) AS lastPostTime,
                        COUNT(DISTINCT CAST(TRY_CAST(post_publish_time AS TIMESTAMP) AS DATE)) AS activeDays
                    FROM read_parquet('{parquet_str}')
                    WHERE symbol IS NOT NULL
                    GROUP BY symbol, stockbar_code, stockbar_name
                    ORDER BY totalComments DESC, totalPosts DESC
                    LIMIT ?
                '''

                effective_limit = limit if limit and limit > 0 else 1000
                con = duckdb.connect()
                try:
                    # 设置 DuckDB 性能参数以加速查询
                    try:
                        con.execute("SET threads TO 4")
                    except Exception:
                        pass  # 如果设置失败，使用默认值
                    try:
                        con.execute("SET memory_limit='2GB'")
                    except Exception:
                        pass
                    df = con.execute(sql, [effective_limit]).df()
                finally:
                    con.close()

                # 转换为前端期望的字段格式
                results = []
                for _, row in df.iterrows():
                    last_ts = row.get('lastPostTime')
                    if pd.isna(last_ts):
                        last_str = None
                    else:
                        # DuckDB 返回 Timestamp 时直接格式化为字符串
                        last_str = str(last_ts)

                    active_days = row.get('activeDays')
                    try:
                        active_days_int = int(active_days) if active_days is not None else None
                    except (TypeError, ValueError):
                        active_days_int = None

                    results.append({
                        "symbol": row.get('symbol') or '',
                        "stockCode": row.get('stockCode') or '',
                        "stockName": row.get('stockName') or '',
                        "totalPosts": int(row.get('totalPosts') or 0),
                        "totalClicks": int(row.get('totalClicks') or 0),
                        "totalComments": int(row.get('totalComments') or 0),
                        "bullishCount": int(row.get('bullishCount') or 0),
                        "bearishCount": int(row.get('bearishCount') or 0),
                        "neutralCount": int(row.get('neutralCount') or 0),
                        "sentimentScore": float(row.get('sentimentScore') or 0.0),
                        "lastPostTime": last_str,
                        "activeDays": active_days_int,
                    })

                return json_response({"success": True, "data": results})
            except Exception:
                # DuckDB / Parquet 出错则回退到原始 CSV 方案
                pass

        # 2. 回退：沿用原来的逐 CSV 读取逻辑，保证兼容性
        from config.config import Config
        data_dir = Path(Config.SPIDER_DATA_DIR)
        if not data_dir.exists():
            return json_response({"success": True, "data": []})

        results = []

        for csv_path in sorted(data_dir.glob('*_posts.csv')):
            symbol_code = csv_path.stem.replace('_posts', '')

            try:
                df = pd.read_csv(csv_path, encoding='utf-8-sig')
            except Exception:
                continue

            if df is None or df.empty:
                continue

            total_posts = int(len(df))

            if 'post_click_count' in df.columns:
                total_clicks = int(pd.to_numeric(df['post_click_count'], errors='coerce').fillna(0).sum())
            else:
                total_clicks = 0

            if 'post_comment_count' in df.columns:
                total_comments = int(pd.to_numeric(df['post_comment_count'], errors='coerce').fillna(0).sum())
            else:
                total_comments = 0

            bullish_count = 0
            bearish_count = 0
            neutral_count = 0
            sentiment_score = 0.0
            if 'bullish_bearish' in df.columns:
                bb = pd.to_numeric(df['bullish_bearish'], errors='coerce').fillna(0)
                bullish_count = int((bb > 0).sum())
                bearish_count = int((bb < 0).sum())
                neutral_count = int((bb == 0).sum())
                sentiment_score = float(bb.mean()) if len(bb) > 0 else 0.0

            stock_code = None
            stock_name = None
            if 'stockbar_code' in df.columns:
                try:
                    stock_code = str(df['stockbar_code'].iloc[0])
                except Exception:
                    stock_code = None
            if 'stockbar_name' in df.columns:
                try:
                    stock_name = str(df['stockbar_name'].iloc[0])
                except Exception:
                    stock_name = None

            last_post_time = None
            active_days = None
            if 'post_publish_time' in df.columns:
                try:
                    # 抑制日期解析格式警告
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', category=UserWarning, message='.*Could not infer format.*')
                        # 使用 format='mixed' 允许混合格式，提高解析性能并避免警告
                        # 如果 pandas 版本不支持，会回退到自动推断
                        try:
                            times = pd.to_datetime(
                                df['post_publish_time'],
                                format='mixed',
                                errors='coerce'
                            )
                        except (ValueError, TypeError):
                            # 回退到自动推断（兼容旧版本 pandas）
                            times = pd.to_datetime(
                                df['post_publish_time'],
                                errors='coerce'
                            )
                    if not times.isna().all():
                        last = times.max()
                        last_post_time = last.isoformat(sep=' ', timespec='seconds')
                        active_days = int(times.dt.date.nunique())
                except Exception:
                    # 兜底：解析异常时直接忽略时间信息，避免阻塞接口
                    last_post_time = None
                    active_days = None

            results.append({
                "symbol": symbol_code,
                "stockCode": stock_code or symbol_code[-6:],
                "stockName": stock_name or "",
                "totalPosts": total_posts,
                "totalClicks": total_clicks,
                "totalComments": total_comments,
                "bullishCount": bullish_count,
                "bearishCount": bearish_count,
                "neutralCount": neutral_count,
                "sentimentScore": sentiment_score,
                "lastPostTime": last_post_time,
                "activeDays": active_days,
            })

        results.sort(key=lambda x: (x['totalComments'], x['totalPosts']), reverse=True)
        if limit > 0:
            results = results[:limit]

        return json_response({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "data": []}), 500


@sentiment_bp.route('/stock_sentiment_words', methods=['GET'])
def get_stock_sentiment_words():
    """返回单只股票用于词云的关键词和情绪权重。"""
    try:
        from config.config import Config

        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({"success": False, "error": "缺少 symbol 参数"}), 400

        parquet_path = Path(Config.PARQUET_DIR) / 'guba_posts.parquet'
        df = None

        # 优先从 Parquet + DuckDB 读取该股票的帖子
        if duckdb is not None and parquet_path.exists():
            try:
                parquet_str = str(parquet_path).replace('\\', '/')
                sql = f"""
                    SELECT
                        symbol,
                        stockbar_code,
                        stockbar_name,
                        post_title,
                        post_click_count,
                        post_comment_count,
                        post_forward_count,
                        post_publish_time,
                        TRY_CAST(bullish_bearish AS DOUBLE) AS bullish_bearish
                    FROM read_parquet('{parquet_str}')
                    WHERE symbol = ?
                """
                con = duckdb.connect()
                try:
                    df = con.execute(sql, [symbol]).df()
                finally:
                    con.close()
            except Exception:
                df = None

        # 回退：直接读取 spider/data/{symbol}_posts.csv
        if df is None:
            from config.config import Config
            csv_path = Path(Config.SPIDER_DATA_DIR) / f'{symbol}_posts.csv'
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path, encoding='utf-8-sig')
                    df = df.copy()
                    df['symbol'] = symbol
                except Exception:
                    df = None

        if df is None or df.empty:
            return json_response({"success": True, "data": {
                "symbol": symbol,
                "stockCode": symbol[-6:],
                "stockName": "",
                "totalPosts": 0,
                "totalClicks": 0,
                "totalComments": 0,
                "overallSentiment": None,
                "words": [],
            }})

        # 规范化数值列
        for col in ("post_click_count", "post_comment_count", "post_forward_count"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        total_posts = int(len(df))
        total_clicks = int(df["post_click_count"].sum())
        total_comments = int(df["post_comment_count"].sum())

        # 延迟导入避免循环依赖
        from server.app import (
            STOPWORDS, ANNOUNCEMENT_PATTERNS, AD_KEYWORDS, 
            STOCK_TERMS, _init_jieba, jieba
        )
        
        # 情绪与分词库（若不可用则降级）
        try:
            from snownlp import SnowNLP  # type: ignore[import]
            # 使用延迟初始化的 jieba
            _init_jieba()
            sentiment_available = True
        except Exception:
            SnowNLP = None  # type: ignore[assignment]
            sentiment_available = False

        word_stats: Dict[str, Dict[str, float]] = {}
        total_sentiment = 0.0
        sentiment_weight_sum = 0.0

        def tokenize(text: str):
            """
            改进的分词函数，确保细粒度分词，避免出现完整句子
            1. 使用精确模式分词，避免长词
            2. 对分词结果进行二次切分，确保词长度合理
            3. 只保留2-4个字的词（避免5-6字的短语被当作一个词）
            """
            if not text:
                return []
            
            words = []
            
            # 优先使用 jieba 精确模式分词（cut_all=False）
            if sentiment_available:
                # 确保 jieba 已初始化
                _init_jieba()
                if jieba is not None:
                    try:
                        # 使用精确模式，避免过度合并
                        seg_list = jieba.cut(text, cut_all=False)
                    
                        for word in seg_list:
                            word = word.strip()
                            if not word or word.isspace():
                                continue
                            
                            word_len = len(word)
                            
                            # 只保留2-4个字的词（避免出现长短语）
                            if word_len < 2 or word_len > 4:
                                # 如果词太长（>4），尝试进一步切分
                                if word_len > 4:
                                    # 对长词进行二次切分
                                    sub_words = jieba.cut(word, cut_all=False)
                                    for sub_word in sub_words:
                                        sub_word = sub_word.strip()
                                        sub_len = len(sub_word)
                                        if 2 <= sub_len <= 4 and sub_word not in STOPWORDS:
                                            words.append(sub_word)
                                continue
                            
                            # 过滤停用词
                            if word in STOPWORDS:
                                continue
                            
                            # 过滤纯数字
                            if word.isdigit():
                                continue
                            
                            words.append(word)
                    except Exception:
                        # 如果分词失败，使用简单切分
                        words = [w.strip() for w in re.findall(r"[\u4e00-\u9fff]{2,4}", text)
                                if w.strip() and w.strip() not in STOPWORDS and not w.strip().isdigit()]
            else:
                # 简单回退：按中文连续字符切分，只保留2-4个字
                words = [w.strip() for w in re.findall(r"[\u4e00-\u9fff]{2,4}", text)
                        if w.strip() and w.strip() not in STOPWORDS and not w.strip().isdigit()]
            
            # 去重但保持顺序
            seen = set()
            unique_words = []
            for w in words:
                if w not in seen:
                    seen.add(w)
                    unique_words.append(w)
            
            return unique_words

        def should_filter_title(title: str) -> bool:
            """在分词前过滤长句子和广告语"""
            if not title:
                return True
            
            # 过滤过长的标题（超过35个字符，可能是公告或广告）
            if len(title) > 35:
                return True
            
            # 过滤包含公告模式的标题
            for pattern in ANNOUNCEMENT_PATTERNS:
                if re.search(pattern, title):
                    return True
            
            # 过滤包含广告关键词的标题
            for keyword in AD_KEYWORDS:
                if keyword in title:
                    return True
            
            # 过滤包含过多标点符号的标题（可能是格式化文本）
            punctuation_count = len(re.findall(r'[，。、；：！？]', title))
            if punctuation_count > 3:
                return True
            
            return False

        for _, row in df.iterrows():
            title = str(row.get("post_title") or "").strip()
            if not title:
                continue
            
            # 在分词前过滤长句子和广告语
            if should_filter_title(title):
                continue

            clicks = float(row.get("post_click_count") or 0.0)
            comments = float(row.get("post_comment_count") or 0.0)
            forwards = float(row.get("post_forward_count") or 0.0)

            # 将帖子数、评论数、点击数综合为权重（对大数取 log 减少极端值影响）
            weight = 1.0 + math.log1p(clicks) + 2.0 * math.log1p(comments) + 1.5 * math.log1p(forwards)

            # 优先使用数据库中已计算好的 bullish_bearish 字段（与散点图保持一致）
            # 如果不存在，再使用 SnowNLP 实时计算
            score = None
            bb_value = None
            if 'bullish_bearish' in df.columns:
                try:
                    bb_value = row.get("bullish_bearish")
                    if bb_value is not None and pd.notna(bb_value):
                        # bullish_bearish 已经是 -1 到 1 之间的值，需要转换为 0-1 范围用于分类
                        # 但我们可以直接使用它来判断正负面
                        bb_float = float(bb_value)
                        if bb_float > 0:
                            # 正面：将 -1到1 映射到 0.5到1
                            score = 0.5 + (bb_float * 0.5)
                        elif bb_float < 0:
                            # 负面：将 -1到0 映射到 0到0.5
                            score = 0.5 + (bb_float * 0.5)
                        else:
                            # 中性
                            score = 0.5
                except (ValueError, TypeError):
                    score = None
            
            # 如果数据库中没有 bullish_bearish，回退到 SnowNLP
            if score is None and sentiment_available and SnowNLP is not None:
                try:
                    score = float(SnowNLP(title).sentiments)
                except Exception:
                    score = None

            if score is not None:
                total_sentiment += score * weight
                sentiment_weight_sum += weight

            # 改进情感分类阈值：使用更严格的阈值，提高区分度
            # 个股评论情感通常更极端，使用 0.55/0.45 作为阈值
            if score is None:
                label = "neutral"
            elif score >= 0.55:  # 从0.6降低到0.55，提高正面识别率
                label = "positive"
            elif score <= 0.45:  # 从0.4提高到0.45，提高负面识别率
                label = "negative"
            else:
                label = "neutral"

            # 分词处理（tokenize 内部已经处理了过滤）
            for token in tokenize(title):
                info = word_stats.setdefault(token, {
                    "weight": 0.0,
                    "positiveWeight": 0.0,
                    "negativeWeight": 0.0,
                    "count": 0.0,
                })
                info["weight"] += weight
                info["count"] += 1.0
                
                # 如果有 bullish_bearish 值，直接使用它来计算情绪权重
                # 这样可以更准确地反映情绪，与散点图保持一致
                if bb_value is not None and pd.notna(bb_value):
                    bb_float = float(bb_value)
                    if bb_float > 0:
                        info["positiveWeight"] += weight * bb_float  # 正面权重 = weight * 情绪强度
                    elif bb_float < 0:
                        info["negativeWeight"] += weight * abs(bb_float)  # 负面权重 = weight * |情绪强度|
                    # bb_float == 0 时，不累加正负面权重（保持为0，表示中性）
                else:
                    # 如果没有 bullish_bearish，使用 label 分类（回退方案）
                    if label == "positive":
                        info["positiveWeight"] += weight
                    elif label == "negative":
                        info["negativeWeight"] += weight

        words = []
        for token, info in word_stats.items():
            weight = float(info.get("weight", 0.0))
            positive_weight = float(info.get("positiveWeight", 0.0))
            negative_weight = float(info.get("negativeWeight", 0.0))
            count = int(info.get("count", 0.0))
            
            # 计算情绪倾向（-1 到 1，-1=完全负面，0=中性，1=完全正面）
            # 改进：使用更敏感的计算方式，提高区分度
            sentiment_score = 0.0
            if weight > 0:
                # 情绪得分 = (正面权重 - 负面权重) / 总权重
                sentiment_score = (positive_weight - negative_weight) / weight
                # 放大差异：如果正负面权重差异明显，增强信号
                if abs(sentiment_score) > 0.3:
                    # 对极端情绪进行放大（但不超过±1）
                    sentiment_score = sentiment_score * 1.2
                # 限制在 -1 到 1 之间
                sentiment_score = max(-1.0, min(1.0, sentiment_score))
            
            words.append({
                "word": token,
                "weight": weight,  # 词的总权重，用于控制词云中词的大小（weight 越大，词越大）
                "positiveWeight": positive_weight,  # 正面情绪权重
                "negativeWeight": negative_weight,  # 负面情绪权重
                "count": count,  # 词出现的次数
                "sentiment": sentiment_score,  # 情绪得分（-1到1），用于控制词的颜色
            })

        # 按权重排序，确保词大小与出现程度正相关（权重高的词排在前面）
        words.sort(key=lambda x: x["weight"], reverse=True)
        words = words[:150]

        if sentiment_weight_sum > 0:
            overall_sentiment = total_sentiment / sentiment_weight_sum
        else:
            overall_sentiment = None

        stock_code = str(df.get("stockbar_code").iloc[0]) if "stockbar_code" in df.columns and len(df) > 0 else symbol[-6:]
        stock_name = str(df.get("stockbar_name").iloc[0]) if "stockbar_name" in df.columns and len(df) > 0 else ""

        return jsonify({
            "success": True,
            "data": {
                "symbol": symbol,
                "stockCode": stock_code,
                "stockName": stock_name,
                "totalPosts": total_posts,
                "totalClicks": total_clicks,
                "totalComments": total_comments,
                "overallSentiment": overall_sentiment,
                "words": words,
            },
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "data": None}), 500


@sentiment_bp.route('/stock_sentiment_timeline', methods=['GET'])
def get_stock_sentiment_timeline():
    """获取个股多空博弈时间序列数据（按时间分组，显示看多、看空、中立三条线）"""
    try:
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({"success": False, "error": "缺少 symbol 参数", "data": []}), 400
        
        from config.config import Config
        parquet_path = Path(Config.PARQUET_DIR) / 'guba_posts.parquet'
        
        if duckdb is None or not parquet_path.exists():
            return jsonify({"success": False, "error": "Parquet 数据文件不存在", "data": []}), 500
        
        parquet_str = str(parquet_path).replace('\\', '/')
        
        # 提取6位数字代码
        if symbol.startswith('sz') or symbol.startswith('sh'):
            code_6 = symbol[2:] if len(symbol) > 2 else symbol
            full_symbol = symbol
        else:
            code_6 = symbol[-6:] if len(symbol) >= 6 else symbol.zfill(6)
            full_symbol = symbol
        
        # 构建多种匹配条件
        symbol_conditions = [
            f"symbol = '{full_symbol}'",
            f"symbol = '{code_6}'",
            f"RIGHT(symbol, 6) = '{code_6}'",
            f"stockbar_code = '{code_6}'",
            f"symbol LIKE '%{code_6}%'"
        ]
        where_clause = ' OR '.join(symbol_conditions)
        
        # 按时间分组（按小时），统计看多、看空、中立的数量
        sql = f"""
            SELECT
                DATE_TRUNC('hour', TRY_CAST(post_publish_time AS TIMESTAMP)) AS time_hour,
                SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) > 0 THEN 1 ELSE 0 END) AS bullishCount,
                SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) < 0 THEN 1 ELSE 0 END) AS bearishCount,
                SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) = 0 OR bullish_bearish IS NULL THEN 1 ELSE 0 END) AS neutralCount,
                COUNT(*) AS totalCount,
                COALESCE(CAST(stockbar_name AS VARCHAR), '') AS stockName
            FROM read_parquet('{parquet_str}')
            WHERE ({where_clause})
                AND TRY_CAST(post_publish_time AS TIMESTAMP) IS NOT NULL
            GROUP BY time_hour, stockbar_name
            ORDER BY time_hour ASC
        """
        
        con = duckdb.connect()
        try:
            con.execute("SET threads TO 4")
            con.execute("SET memory_limit='2GB'")
            df = con.execute(sql).df()
        finally:
            con.close()
        
        if df.empty:
            return json_response({"success": True, "data": [], "stockName": ""})
        
        # 获取股票名称（从第一条记录）
        stock_name = str(df.iloc[0].get('stockName', '')) if 'stockName' in df.columns else ''
        
        # 转换为前端需要的格式
        results = []
        for _, row in df.iterrows():
            time_hour = row.get('time_hour')
            if pd.isna(time_hour):
                continue
            
            # 格式化时间为字符串（如 "2024-01-01 09:00"）
            if isinstance(time_hour, pd.Timestamp):
                time_str = time_hour.strftime('%Y-%m-%d %H:%M')
            else:
                time_str = str(time_hour)
            
            results.append({
                'time': time_str,
                'bullishCount': int(row.get('bullishCount', 0)),
                'bearishCount': int(row.get('bearishCount', 0)),
                'neutralCount': int(row.get('neutralCount', 0)),
                'totalCount': int(row.get('totalCount', 0))
            })
        
        return jsonify({
            "success": True,
            "data": results,
            "stockName": stock_name
        })
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取个股多空博弈时间序列数据失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e), "data": []}), 500


@sentiment_bp.route('/sentiment_trends', methods=['GET'])
def get_sentiment_trends():
    """获取情感趋势数据（从真实数据库查询）"""
    try:
        symbol = request.args.get('symbol')
        days = int(request.args.get('days', 7))
        
        from config.config import Config
        parquet_path = Path(Config.PARQUET_DIR) / 'guba_posts.parquet'
        
        if duckdb is None or not parquet_path.exists():
            return jsonify({
                'success': False,
                'error': 'Parquet 数据文件不存在',
                'data': []
            }), 500
        
        parquet_str = str(parquet_path).replace('\\', '/')
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # 构建 WHERE 条件
        where_conditions = [
            "TRY_CAST(post_publish_time AS TIMESTAMP) IS NOT NULL",
            f"CAST(TRY_CAST(post_publish_time AS TIMESTAMP) AS DATE) >= '{start_date_str}'",
            f"CAST(TRY_CAST(post_publish_time AS TIMESTAMP) AS DATE) <= '{end_date_str}'"
        ]
        
        # 如果提供了 symbol，添加股票过滤条件
        if symbol:
            # 提取6位数字代码
            if symbol.startswith('sz') or symbol.startswith('sh'):
                code_6 = symbol[2:] if len(symbol) > 2 else symbol
                full_symbol = symbol
            else:
                code_6 = symbol[-6:] if len(symbol) >= 6 else symbol.zfill(6)
                full_symbol = symbol
            
            symbol_conditions = [
                f"symbol = '{full_symbol}'",
                f"symbol = '{code_6}'",
                f"RIGHT(symbol, 6) = '{code_6}'",
                f"stockbar_code = '{code_6}'",
                f"symbol LIKE '%{code_6}%'"
            ]
            where_conditions.append(f"({' OR '.join(symbol_conditions)})")
        
        where_clause = ' AND '.join(where_conditions)
        
        # 按日期分组，统计每天的帖子数量和平均情感得分
        sql = f"""
            SELECT
                CAST(TRY_CAST(post_publish_time AS TIMESTAMP) AS DATE) AS date,
                COUNT(*) AS post_count,
                COALESCE(AVG(TRY_CAST(bullish_bearish AS DOUBLE)), 0.0) AS avg_sentiment
            FROM read_parquet('{parquet_str}')
            WHERE {where_clause}
            GROUP BY date
            ORDER BY date ASC
        """
        
        con = duckdb.connect()
        try:
            con.execute("SET threads TO 4")
            con.execute("SET memory_limit='2GB'")
            df = con.execute(sql).df()
        finally:
            con.close()
        
        # 转换为前端需要的格式
        data = []
        if not df.empty:
            for _, row in df.iterrows():
                date_val = row.get('date')
                if pd.isna(date_val):
                    continue
                
                # 格式化日期
                if isinstance(date_val, pd.Timestamp):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)
                
                data.append({
                    'date': date_str,
                    'post_count': int(row.get('post_count', 0)),
                    'avg_sentiment': round(float(row.get('avg_sentiment', 0.0)), 3)
                })
        
        # 确保按日期排序（虽然 SQL 已经排序了，但这里再确保一次）
        data.sort(key=lambda x: x['date'])
        
        return jsonify({
            'success': True,
            'data': data,
            'message': f'Successfully retrieved sentiment trend for {symbol or "all stocks"}'
        })
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取情感趋势数据失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'data': []
        }), 500


@sentiment_bp.route('/lda_topics', methods=['GET'])
def get_lda_topics():
    """获取LDA主题分布数据"""
    try:
        symbol = request.args.get('symbol')
        
        # 模拟5个主题及其分布
        topics = [
            {'topic': '短期炒作', 'weight': random.uniform(0.1, 0.4)},
            {'topic': '业绩利好', 'weight': random.uniform(0.1, 0.3)},
            {'topic': '主力出货', 'weight': random.uniform(0.05, 0.25)},
            {'topic': '重组传闻', 'weight': random.uniform(0.05, 0.2)},
            {'topic': '散户被套', 'weight': random.uniform(0.05, 0.2)}
        ]
        
        # 归一化权重
        total = sum(t['weight'] for t in topics)
        for t in topics:
            t['weight'] = round(t['weight'] / total, 2)
        
        # 按权重排序
        topics_sorted = sorted(topics, key=lambda x: x['weight'], reverse=True)
        
        # 转换为前端期望的格式
        topic_names = [t['topic'] for t in topics_sorted]
        topic_scores = [t['weight'] for t in topics_sorted]
        
        return jsonify({
            'success': True,
            'data': {
                'topics': topic_names,
                'scores': topic_scores
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
