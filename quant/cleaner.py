import json
import os
import csv
from datetime import datetime

class StockDataCleaner:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.date = os.path.basename(data_dir)
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
            file_path = os.path.join(self.data_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.data[key] = json.load(f)
    
    def generate_market_dashboard(self):
        """生成大盘表 market_dashboard.csv"""
        # 检查market_sentiment数据是否为空
        market_sentiment = self.data.get('market_sentiment', {})
        data_list = market_sentiment.get('data', [])
        
        if not data_list:
            print(f"⚠️ market_sentiment数据为空，跳过生成market_dashboard.csv")
            return
        
        sentiment_data = data_list[0]
        
        # 炸板率和跌停数
        broken_ratio = sentiment_data.get('emotionMetrics', {}).get('brokenRatio', 0)
        limit_down_count = sentiment_data.get('emotionMetrics', {}).get('limitDownCount', 0)
        
        # 主线题材（取前两个）
        themes = sentiment_data.get('themes', [])[:2]
        main_themes = ','.join([theme.get('name', '') for theme in themes])
        
        # 最高板高度
        ladder = sentiment_data.get('ladder', {})
        max_height = max(map(int, ladder.keys())) if ladder else 0
        
        # 写入 CSV
        with open('market_dashboard.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['日期', '炸板率', '跌停数', '主线题材', '最高板高度'])
            writer.writerow([self.date, broken_ratio, limit_down_count, main_themes, max_height])
        
        print("✓ market_dashboard.csv 生成完成")
    
    def generate_stock_feature_matrix(self):
        """生成个股因子表 stock_feature_matrix.csv"""
        # 检查limit_up数据是否完整
        if 'limit_up' not in self.data or 'data' not in self.data['limit_up'] or 'stocks' not in self.data['limit_up']['data']:
            print(f"⚠️ limit_up数据不完整，跳过生成stock_feature_matrix.csv")
            return
        
        # 获取龙虎榜数据，用于判断是否有机构买入
        dragon_tiger_data = self.data.get('dragon_tiger', {}).get('data', [])
        # 获取风险监控数据，用于判断是否监管
        risk_monitor_data = self.data.get('risk_monitor', {}).get('data', [])
        # 获取涨停过滤数据，用于主要因子
        limit_up_data = self.data['limit_up']['data']['stocks']
        
        # 构建辅助数据结构
        stock_regulation = set()
        for stock in risk_monitor_data:
            # 风险监控数据中的code字段是股票代码
            stock_code = stock.get('code', '')
            if stock_code:
                stock_regulation.add(stock_code)
        
        stock_institution_buy = {}
        for record in dragon_tiger_data:
            try:
                stock_code = record.get('stockCode', '')
                lhb_branch = record.get('lhbBranch', {})
                buy_branches = lhb_branch.get('buyBranches', [])
                has_institution = any(branch.get('branchName') == '机构专用' for branch in buy_branches)
                if has_institution and stock_code:
                    stock_institution_buy[stock_code] = True
            except:
                continue
        
        # 写入 CSV
        with open('stock_feature_matrix.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['代码', '连板数', '封单额', '换手率', '是否监管', '是否机构买入', '龙头地位标签'])
            
            for stock in limit_up_data:
                stock_code = stock.get('code', '')
                continue_num = stock.get('continue_num', 0)
                order_amount = stock.get('order_amount', 0)
                turnover_rate = stock.get('turnover_rate', 0)
                is_regulation = '是' if stock_code in stock_regulation else '否'
                is_institution_buy = '是' if stock_code in stock_institution_buy else '否'
                
                # 龙头地位标签
                tags = stock.get('tags', [])
                leader_tag = ','.join(tags) if tags else '无'
                
                writer.writerow([stock_code, continue_num, order_amount, turnover_rate, is_regulation, is_institution_buy, leader_tag])
        
        print("✓ stock_feature_matrix.csv 生成完成")
    
    def generate_ai_daily_brief(self):
        """生成 AI 压缩提示词 ai_daily_brief.txt"""
        # 检查market_sentiment数据是否为空
        market_sentiment = self.data.get('market_sentiment', {})
        data_list = market_sentiment.get('data', [])
        
        if not data_list:
            print(f"⚠️ market_sentiment数据为空，跳过生成ai_daily_brief.txt")
            return
        
        sentiment_data = data_list[0]
        
        # 检查其他必要数据是否存在
        if 'limit_up' not in self.data or 'data' not in self.data['limit_up'] or 'stocks' not in self.data['limit_up']['data']:
            print(f"⚠️ limit_up数据不完整，跳过生成ai_daily_brief.txt")
            return
            
        if 'sector_heat' not in self.data or 'data' not in self.data['sector_heat']:
            print(f"⚠️ sector_heat数据不完整，跳过生成ai_daily_brief.txt")
            return
            
        if 'ladder_detail' not in self.data:
            print(f"⚠️ ladder_detail数据缺失，跳过生成ai_daily_brief.txt")
            return
            
        limit_up_data = self.data['limit_up']['data']['stocks']
        sector_heat = self.data['sector_heat']['data']
        ladder_detail = self.data['ladder_detail']
        
        # 筛选高标股（连板数 >= 3）
        high_stocks = [stock for stock in limit_up_data if stock.get('continue_num', 0) >= 3]
        high_stocks.sort(key=lambda x: x.get('continue_num', 0), reverse=True)
        
        # 1. 首板与题材发散
        first_board_stocks = [stock for stock in limit_up_data if stock.get('continue_num', 0) == 1]
        # 构建辅助数据结构
        first_board_by_theme = {} 
        for stock in first_board_stocks:
            theme = stock.get('jiuyangongshe_category_name', '其他')
            if theme not in first_board_by_theme:
                first_board_by_theme[theme] = []
            first_board_by_theme[theme].append(stock.get('name', ''))
        
        # 获取监管股票列表
        risk_monitor_data = self.data.get('risk_monitor', {}).get('data', [])
        regulated_stocks = set()
        for stock in risk_monitor_data:
            stock_code = stock.get('code', '')
            if stock_code:
                regulated_stocks.add(stock_code)
        
        # 2. 涨停梯队完整性
        # 从ladder_detail获取更完整的梯队信息
        if not ladder_detail.get('dates'):
            print(f"⚠️ ladder_detail数据不完整，跳过生成ai_daily_brief.txt")
            return
            
        ladder_boards = ladder_detail['dates'][0].get('boards', [])
        complete_ladder = {}
        for board in ladder_boards:
            level = board.get('level', '')
            for stock in board.get('stocks', []):
                for tag in stock.get('tags', []):
                    if tag not in complete_ladder:
                        complete_ladder[tag] = {}
                    if level not in complete_ladder[tag]:
                        complete_ladder[tag][level] = []
                    complete_ladder[tag][level].append(stock.get('name', ''))
        
        # 3. 炸板股与亏钱效应
        broken_ratio = sentiment_data.get('emotionMetrics', {}).get('brokenRatio', 0)
        broken_count = sentiment_data.get('emotionMetrics', {}).get('brokenCount', 0)
        
        # 4. 核心中军走势
        # 按市值排序，找出每个题材的大市值股票
        market_cap_by_theme = {} 
        for stock in limit_up_data:
            theme = stock.get('jiuyangongshe_category_name', '其他')
            if theme not in market_cap_by_theme:
                market_cap_by_theme[theme] = []
            market_cap_by_theme[theme].append({
                'name': stock.get('name', ''),
                'code': stock.get('code', ''),
                'market_cap': stock.get('total_market_cap', 0.0),
                'industry': stock.get('industry', '')
            })
        # 对每个题材按市值排序，处理可能的None值
        for theme in market_cap_by_theme:
            market_cap_by_theme[theme].sort(key=lambda x: x['market_cap'] if x['market_cap'] is not None else 0.0, reverse=True)
        
        # 5. 量能与市场风格
        turnover = sentiment_data.get('turnover', {}).get('value', '未知')
        
        # 6. 情绪量化指标
        promotion_rates = sentiment_data.get('emotionMetrics', {}).get('promotionRates', {})
        
        # 7. 轮动信号
        # 从sector_heat获取板块热度信息
        main_themes = [theme.get('name', '') for theme in sentiment_data.get('themes', [])[:2]]
        other_themes = [theme.get('name', '') for theme in sentiment_data.get('themes', [])[2:]]
        
        # 构建 brief 内容
        brief = []
        brief.append(f"日期：{self.date}")
        
        # 安全访问市场情绪数据
        market_sentiment_data = sentiment_data.get('marketSentiment', {})
        rise_count = market_sentiment_data.get('rise', 0)
        fall_count = market_sentiment_data.get('fall', 0)
        brief.append(f"市场情绪：上涨家数 {rise_count}，下跌家数 {fall_count}")
        
        # 安全访问跌停数
        limit_down_count = sentiment_data.get('emotionMetrics', {}).get('limitDownCount', 0)
        brief.append(f"炸板率：{broken_ratio:.2%}，跌停数：{limit_down_count}")
        
        brief.append(f"主线题材：{','.join(main_themes)}")
        
        # 安全访问最高板高度
        ladder = sentiment_data.get('ladder', {})
        max_height = max(map(int, ladder.keys())) if ladder else 0
        brief.append(f"最高板高度：{max_height} 板")
        
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
    # data_lake_dir = 'c:\\Users\\Liu\\Desktop\\projects\\quant\\data_lake'
    data_lake_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data_lake')
    dates = [d for d in os.listdir(data_lake_dir) if os.path.isdir(os.path.join(data_lake_dir, d))]
    latest_date = max(dates)
    
    data_dir = os.path.join(data_lake_dir, latest_date)
    cleaner = StockDataCleaner(data_dir)
    cleaner.run()