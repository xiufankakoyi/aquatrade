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
    """获取情感趋势数据"""
    try:
        symbol = request.args.get('symbol')
        days = int(request.args.get('days', 7))  # 默认最近7天
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)
        
        # 这里简化处理，实际应该从数据库查询
        dates = pd.date_range(start_date, end_date, freq='D')
        
        # 生成模拟数据
        data = [{
            'date': date.strftime('%Y-%m-%d'),
            'post_count': random.randint(50, 200),  # 帖子数量
            'avg_sentiment': round(random.uniform(-0.5, 0.5), 2)  # 情感得分
        } for date in dates]
        
        return jsonify({
            'success': True,
            'data': data,
            'message': f'Successfully retrieved sentiment trend for {symbol}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
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
