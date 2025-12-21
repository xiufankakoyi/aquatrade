from flask import Blueprint, jsonify, request
import pandas as pd
from datetime import datetime, timedelta
import random
from typing import List, Dict, Any
import numpy as np
from pathlib import Path
import duckdb

# 创建蓝图
sentiment_bp = Blueprint('sentiment', __name__)

def get_parquet_path() -> Path:
    """获取Parquet文件路径"""
    return Path(__file__).parent.parent / 'parquet_data' / 'guba_posts.parquet'

@sentiment_bp.route('/api/sentiment/trend', methods=['GET'])
def get_sentiment_trend():
    """获取情感趋势数据（从真实数据库查询）"""
    try:
        symbol = request.args.get('symbol')
        days = int(request.args.get('days', 7))  # 默认最近7天
        
        parquet_path = get_parquet_path()
        
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
        
        # 确保按日期排序
        data.sort(key=lambda x: x['date'])
        
        return jsonify({
            'success': True,
            'data': data,
            'message': f'Successfully retrieved sentiment trend for {symbol or "all stocks"}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'data': []
        }), 500

@sentiment_bp.route('/api/sentiment/lda_topics', methods=['GET'])
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
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'topics': topics_sorted
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@sentiment_bp.route('/api/sentiment/scatter', methods=['GET'])
def get_sentiment_scatter():
    """获取情感-热度散点图数据"""
    try:
        # 模拟数据：生成20只股票的数据点
        stocks = []
        for i in range(20):
            stocks.append({
                'symbol': f'600{100+i}',
                'name': f'股票{100+i}',
                'comment_count': random.randint(100, 10000),  # 评论数（热度）
                'sentiment': round(random.uniform(-1, 1), 2),  # 情感得分
                'market_cap': random.randint(10, 1000)  # 市值（亿）
            })
        
        return jsonify({
            'success': True,
            'data': stocks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
