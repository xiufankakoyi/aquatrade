import json
import os
import csv
from datetime import datetime
from pathlib import Path

class StockDataCleaner:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.date = self.data_dir.name
        self.data = {}
        self.load_data()
    
    def load_data(self):
        """加载所有 JSON 数据"""
        files = {
            'dragon_tiger': 'dragon_tiger_list.json',
            'limit_up': 'limit_up_filter.json',
            'market_sentiment': 'market_sentiment_cycle.json',
            'risk_monitor': 'risk_monitor_list.json',
            'sector_heat': 'sector_heat_stats.json',
            'ladder_detail': 'ladder_hierarchy_detail.json',
            'ladder_trend': 'ladder_trend_summary.json'
        }
        
        for key, filename in files.items():
            file_path = self.data_dir / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.data[key] = json.load(f)
    
    def generate_market_dashboard(self):
        """生成大盘表 market_dashboard.csv"""
        if 'market_sentiment' not in self.data: return None
        sentiment_data = self.data['market_sentiment']['data'][0]
        
        # 炸板率和跌停数
        broken_ratio = sentiment_data['emotionMetrics']['brokenRatio']
        limit_down_count = sentiment_data['emotionMetrics']['limitDownCount']
        
        # 主线题材（取前两个）
        themes = sentiment_data['themes'][:2]
        main_themes = ','.join([theme['name'] for theme in themes])
        
        # 最高板高度
        ladder = sentiment_data['ladder']
        max_height = max(map(int, ladder.keys())) if ladder else 0
        
        # 写入数据结构供后续 LanceDB 使用
        dashboard_data = {
            'trade_date': self.date,
            'broken_ratio': broken_ratio,
            'limit_down_count': limit_down_count,
            'main_themes': main_themes,
            'max_height': max_height
        }
        
        # 写入 CSV (保留原逻辑作为备份)
        output_path = self.data_dir / 'market_dashboard.csv'
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['日期', '炸板率', '跌停数', '主线题材', '最高板高度'])
            writer.writerow([self.date, broken_ratio, limit_down_count, main_themes, max_height])
        
        print(f"✓ market_dashboard.csv 生成完成: {output_path}")
        return dashboard_data
    
    def generate_stock_feature_matrix(self):
        """生成个股因子表 stock_feature_matrix.csv"""
        if 'limit_up' not in self.data: return []
        
        # 获取龙虎榜数据
        dragon_tiger_data = self.data.get('dragon_tiger', {}).get('data', [])
        # 获取风险监控数据
        risk_monitor_data = self.data.get('risk_monitor', {}).get('data', [])
        # 获取涨停过滤数据
        limit_up_data = self.data['limit_up']['data']['stocks']
        
        # 构建辅助数据结构
        stock_regulation = {stock.get('code', '') for stock in risk_monitor_data if stock.get('code')}
        stock_institution_buy = {}
        for record in dragon_tiger_data:
            stock_code = record['stockCode']
            has_institution = any(branch['branchName'] == '机构专用' for branch in record['lhbBranch']['buyBranches'])
            if has_institution:
                stock_institution_buy[stock_code] = True
        
        matrix_rows = []
        # 写入 CSV
        output_path = self.data_dir / 'stock_feature_matrix.csv'
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['代码', '连板数', '封单额', '换手率', '是否监管', '是否机构买入', '龙头地位标签'])
            
            for stock in limit_up_data:
                stock_code = stock['code']
                continue_num = stock['continue_num']
                order_amount = stock['order_amount']
                turnover_rate = stock['turnover_rate']
                is_reg = stock_code in stock_regulation
                is_inst = stock_institution_buy.get(stock_code, False)
                
                # 龙头地位标签
                tags = stock.get('tags', [])
                leader_tag = ','.join(tags) if tags else '无'
                
                writer.writerow([stock_code, continue_num, order_amount, turnover_rate, '是' if is_reg else '否', '是' if is_inst else '否', leader_tag])
                
                matrix_rows.append({
                    'trade_date': self.date,
                    'stock_code': stock_code,
                    'stock_name': stock.get('name', ''),
                    'continue_num': continue_num,
                    'order_amount': order_amount,
                    'turnover_rate': turnover_rate,
                    'is_regulation': is_reg,
                    'is_institution_buy': is_inst,
                    'leader_tag': leader_tag
                })
        
        print(f"✓ stock_feature_matrix.csv 生成完成: {output_path}")
        return matrix_rows
    
    def generate_ai_daily_brief(self):
        """生成 AI 压缩提示词 ai_daily_brief.txt"""
        sentiment_data = self.data['market_sentiment']['data'][0]
        limit_up_data = self.data['limit_up']['data']['stocks']
        sector_heat = self.data['sector_heat']['data']
        ladder_detail = self.data['ladder_detail']
        
        # 筛选高标股（连板数 >= 3）
        high_stocks = [stock for stock in limit_up_data if stock['continue_num'] >= 3]
        high_stocks.sort(key=lambda x: x['continue_num'], reverse=True)
        
        # 1. 首板与题材发散
        first_board_stocks = [stock for stock in limit_up_data if stock['continue_num'] == 1]
        # 构建辅助数据结构
        first_board_by_theme = {} 
        for stock in first_board_stocks:
            theme = stock.get('jiuyangongshe_category_name', '其他')
            if theme not in first_board_by_theme:
                first_board_by_theme[theme] = []
            first_board_by_theme[theme].append(stock['name'])
        
        # 获取监管股票列表
        risk_monitor_data = self.data.get('risk_monitor', {}).get('data', [])
        regulated_stocks = set()
        for stock in risk_monitor_data:
            stock_code = stock.get('code', '')
            if stock_code:
                regulated_stocks.add(stock_code)
        
        # 2. 涨停梯队完整性
        # 从ladder_detail获取更完整的梯队信息
        ladder_boards = ladder_detail['dates'][0]['boards']
        complete_ladder = {}
        for board in ladder_boards:
            level = board['level']
            for stock in board['stocks']:
                for tag in stock.get('tags', []):
                    if tag not in complete_ladder:
                        complete_ladder[tag] = {}
                    if level not in complete_ladder[tag]:
                        complete_ladder[tag][level] = []
                    complete_ladder[tag][level].append(stock['name'])
        
        # 3. 炸板股与亏钱效应
        broken_ratio = sentiment_data['emotionMetrics']['brokenRatio']
        broken_count = sentiment_data['emotionMetrics']['brokenCount']
        
        # 4. 核心中军走势
        # 按市值排序，找出每个题材的大市值股票
        market_cap_by_theme = {} 
        for stock in limit_up_data:
            theme = stock.get('jiuyangongshe_category_name', '其他')
            if theme not in market_cap_by_theme:
                market_cap_by_theme[theme] = []
            market_cap_by_theme[theme].append({
                'name': stock['name'],
                'code': stock['code'],
                'market_cap': stock['total_market_cap'],
                'industry': stock['industry']
            })
        # 对每个题材按市值排序
        for theme in market_cap_by_theme:
            market_cap_by_theme[theme].sort(key=lambda x: x['market_cap'], reverse=True)
        
        # 5. 量能与市场风格
        turnover = sentiment_data['turnover']['value']
        
        # 6. 情绪量化指标
        promotion_rates = sentiment_data['emotionMetrics']['promotionRates']
        
        # 7. 轮动信号
        # 从sector_heat获取板块热度信息
        main_themes = [theme['name'] for theme in sentiment_data['themes'][:2]]
        other_themes = [theme['name'] for theme in sentiment_data['themes'][2:]]
        
        # 构建 brief 内容
        brief = []
        brief.append(f"日期：{self.date}")
        brief.append(f"市场情绪：上涨家数 {sentiment_data['marketSentiment']['rise']}，下跌家数 {sentiment_data['marketSentiment']['fall']}")
        brief.append(f"炸板率：{broken_ratio:.2%}，跌停数：{sentiment_data['emotionMetrics']['limitDownCount']}")
        brief.append(f"主线题材：{','.join(main_themes)}")
        brief.append(f"最高板高度：{max(map(int, sentiment_data['ladder'].keys()))} 板")
        brief.append(f"两市成交总额：{turnover}")
        brief.append("")
        
        # 1. 首板与题材发散
        brief.append("1. 首板与题材发散：")
        brief.append(f"   首板总数：{len(first_board_stocks)}")
        for theme, stocks in first_board_by_theme.items():
            brief.append(f"   {theme}：{len(stocks)}只")
        # 检查是否有全新题材
        all_themes = [theme['name'] for theme in sector_heat]
        new_themes = [theme for theme in all_themes if theme not in ['商业航天', '脑机接口', '化工']]
        if new_themes:
            brief.append(f"   全新题材：{','.join(new_themes)}")
        brief.append("")
        
        # 2. 涨停梯队完整性
        brief.append("2. 涨停梯队完整性：")
        for theme in main_themes:
            if theme in complete_ladder:
                heights = sorted(complete_ladder[theme].keys(), reverse=True)
                brief.append(f"   {theme}梯队：")
                for height in heights:
                    stocks_str = ','.join(complete_ladder[theme][height][:5])  # 只显示前5只
                    if len(complete_ladder[theme][height]) > 5:
                        stocks_str += f"等{len(complete_ladder[theme][height])}只"
                    brief.append(f"     {height}板：{stocks_str}")
        brief.append("")
        
        # 3. 炸板股与亏钱效应
        brief.append("3. 炸板股与亏钱效应：")
        brief.append(f"   炸板总数：{broken_count}")
        brief.append(f"   炸板率：{broken_ratio:.2%}")
        # 计算炸板率高低
        if broken_ratio > 0.2:
            brief.append("   炸板率较高，市场分歧明显")
        elif broken_ratio < 0.1:
            brief.append("   炸板率较低，市场情绪稳定")
        else:
            brief.append("   炸板率适中，市场分歧可控")
        brief.append("")
        
        # 4. 核心中军走势
        brief.append("4. 核心中军走势：")
        for theme in main_themes:
            if theme in market_cap_by_theme and market_cap_by_theme[theme]:
                中军 = market_cap_by_theme[theme][0]
                brief.append(f"   {theme}中军：{中军['name']}（{中军['code']}），市值：{中军['market_cap']:,}元")
        brief.append("")
        
        # 5. 量能与市场风格
        brief.append("5. 量能与市场风格：")
        brief.append(f"   两市成交总额：{turnover}")
        # 判断量能高低
        if sentiment_data['turnover']['isHigh']:
            brief.append("   量能较高，市场活跃度提升")
        else:
            brief.append("   量能适中，市场稳定运行")
        brief.append("   （注：缺少连板指数与同花顺全A指数对比数据）")
        brief.append("")
        
        # 6. 情绪量化指标
        brief.append("6. 情绪量化指标：")
        brief.append(f"   1进2晋级率：{promotion_rates.get('1to2', 0)}%")
        brief.append(f"   2进3晋级率：{promotion_rates.get('2to3', 0)}%")
        brief.append(f"   3进4晋级率：{promotion_rates.get('3to4', 0)}%")
        brief.append(f"   高标晋级率：{promotion_rates.get('high', 0)}%")
        # 计算平均晋级率
        avg_promotion = sum(promotion_rates.values()) / len(promotion_rates) if promotion_rates else 0
        if avg_promotion > 80:
            brief.append("   平均晋级率较高，情绪加速")
        elif avg_promotion < 30:
            brief.append("   平均晋级率较低，情绪降温")
        else:
            brief.append("   平均晋级率适中，情绪稳定")
        brief.append("")
        
        # 7. 轮动信号
        brief.append("7. 轮动信号：")
        if other_themes:
            brief.append(f"   其他活跃题材：{','.join(other_themes)}")
        # 从sector_heat获取板块热度变化
        sector_counts = {item['name']: item['count'] for item in sector_heat}
        active_sectors = [name for name, count in sector_counts.items() if count >= 5]
        if active_sectors:
            brief.append(f"   活跃板块：{','.join(active_sectors)}")
        brief.append("")
        
        # 高标股逻辑
        brief.append("8. 高标股逻辑：")
        for stock in high_stocks:
            stock_brief = f"   {stock['name']}（{stock['code']}）：{stock['continue_num']}连板，"
            stock_brief += f"涨停类型：{stock['limit_up_type']}，"
            # 将封单额转换为亿元单位
            order_amount_yuan = stock['order_amount']
            order_amount_yiyuan = order_amount_yuan / 1e8
            stock_brief += f"封单额：{order_amount_yiyuan:.2f}亿元，"
            stock_brief += f"换手率：{stock['turnover_rate']:.2f}%，"
            # 使用原始分析内容而非概括
            analysis = stock.get('jiuyangongshe_analysis', stock['reason_type'])
            # 简化分析内容，只保留第一行核心逻辑
            core_analysis = analysis.split('\n')[0]
            stock_brief += f"概念：{core_analysis}"
            
            # 添加监管标记
            tags = stock.get('tags', [])
            if stock['code'] in regulated_stocks:
                tags.append("[⚠️监管]")
            
            if tags:
                stock_brief += f"，标签：{','.join(tags)}"
            
            brief.append(stock_brief)
        
        # 写入文件
        with open('ai_daily_brief.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(brief))
        
        print("✓ ai_daily_brief.txt 生成完成")
    
    def run(self):
        """执行完整的 ETL 流程"""
        print(f"开始处理 {self.date} 的数据...")
        self.generate_market_dashboard()
        self.generate_stock_feature_matrix()
        self.generate_ai_daily_brief()
        print("所有文件生成完成！")

if __name__ == "__main__":
    # 获取最新的日期目录
    data_lake_dir = 'c:\\Users\\Liu\\Desktop\\projects\\quant\\data_lake'
    dates = [d for d in os.listdir(data_lake_dir) if os.path.isdir(os.path.join(data_lake_dir, d))]
    latest_date = max(dates)
    
    data_dir = os.path.join(data_lake_dir, latest_date)
    cleaner = StockDataCleaner(data_dir)
    cleaner.run()