import json
import os
import csv
import threading
from datetime import datetime, timedelta
import requests

class StockDataCleaner:
    def __init__(self, data_dir, output_dir):
        self.data_dir = data_dir
        self.date = os.path.basename(data_dir)
        self.output_dir = output_dir
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
    
    def find_date_data(self, data_list, date_str):
        """从数据列表中找到指定日期的数据"""
        for item in data_list:
            if item.get('date') == date_str:
                return item
        return None
    
    def get_previous_trading_day(self, date_str):
        """获取前一个交易日（跳过周末）"""
        date = datetime.strptime(date_str, '%Y-%m-%d')
        while True:
            date -= timedelta(days=1)
            if date.weekday() < 5:  # 0-4 是周一到周五
                return date.strftime('%Y-%m-%d')
    
    def format_change(self, current, previous):
        """格式化变化量"""
        change = current - previous
        if change > 0:
            return f"增{change:.0f}家", f"+{change/previous*100:.1f}%" if previous != 0 else "+∞%"
        elif change < 0:
            return f"减{abs(change):.0f}家", f"{change/previous*100:.1f}%" if previous != 0 else "-∞%"
        else:
            return "持平", "0%"
    
    def format_pct_change(self, current, previous):
        """格式化百分比变化"""
        change = current - previous
        if change > 0:
            return f"+{change*100:.1f}pct"
        elif change < 0:
            return f"{change*100:.1f}pct"
        else:
            return "持平"
    
    def get_trend_description(self, change_pct, metric_type='general'):
        """根据变化幅度给出趋势描述"""
        abs_change = abs(change_pct)
        direction = "回暖" if change_pct > 0 else "降温" if change_pct < 0 else "稳定"
        
        if abs_change < 0.05:
            return f"基本{direction}"
        elif abs_change < 0.15:
            return f"小幅{direction}"
        elif abs_change < 0.30:
            return f"明显{direction}"
        elif abs_change < 0.50:
            return f"大幅{direction}"
        else:
            return f"巨幅{direction}"
    
    def analyze_theme_changes(self, current_themes, previous_themes):
        """分析主题变化"""
        current_dict = {t['name']: t['count'] for t in current_themes}
        previous_dict = {t['name']: t['count'] for t in previous_themes}
        
        continuing = []  # 持续主题
        new_themes = []  # 新晋主题
        fading = []  # 退潮主题
        
        for name, count in current_dict.items():
            if name in previous_dict:
                prev_count = previous_dict[name]
                change_pct = (count - prev_count) / prev_count if prev_count > 0 else 0
                continuing.append({
                    'name': name,
                    'count': count,
                    'prev_count': prev_count,
                    'change_pct': change_pct
                })
            else:
                new_themes.append({'name': name, 'count': count})
        
        for name, count in previous_dict.items():
            if name not in current_dict:
                fading.append({'name': name, 'prev_count': count})
        
        return continuing, new_themes, fading
    
    def get_theme_sustained_days(self, data_list, theme_name, current_date):
        """
        获取主题的持续天数
        从当前日期往前数，该主题连续出现的天数
        """
        days = 0
        # 找到当前日期在 data_list 中的索引
        current_idx = None
        for i, item in enumerate(data_list):
            if item.get('date') == current_date:
                current_idx = i
                break
        
        if current_idx is None:
            return 1
        
        # 往前检查该主题是否连续出现
        for i in range(current_idx, len(data_list)):
            item = data_list[i]
            themes = {t['name'] for t in item.get('themes', [])}
            if theme_name in themes:
                days += 1
            else:
                break
        
        return days
    
    def classify_themes_enhanced(self, current_themes, previous_themes, data_list, current_date):
        """
        细化的主题分类
        返回: 主线列表, 支线列表, 新晋列表, 退潮列表
        """
        current_dict = {t['name']: t['count'] for t in current_themes}
        previous_dict = {t['name']: t['count'] for t in previous_themes}
        
        main_themes = []  # 主线
        branch_themes = []  # 支线
        new_themes = []  # 新晋
        fading = []  # 退潮
        
        # 计算每个当前主题的持续天数
        for name, count in current_dict.items():
            sustained_days = self.get_theme_sustained_days(data_list, name, current_date)
            
            if name in previous_dict:
                # 持续主题，根据数量和天数判断是主线还是支线
                prev_count = previous_dict[name]
                if count >= 10 or sustained_days >= 3:
                    main_themes.append({
                        'name': name,
                        'count': count,
                        'days': sustained_days,
                        'prev_count': prev_count
                    })
                else:
                    branch_themes.append({
                        'name': name,
                        'count': count,
                        'days': sustained_days,
                        'prev_count': prev_count
                    })
            else:
                # 新晋主题
                new_themes.append({
                    'name': name,
                    'count': count,
                    'days': 1
                })
        
        # 退潮主题
        for name, prev_count in previous_dict.items():
            if name not in current_dict:
                fading.append({
                    'name': name,
                    'prev_count': prev_count,
                    'count': 0
                })
        
        return main_themes, branch_themes, new_themes, fading
    
    def judge_cycle_phase(self, cur, prev, prev2=None):
        """判断周期阶段"""
        rise = cur['marketSentiment']['rise']
        fall = cur['marketSentiment']['fall']
        broken_ratio = cur['emotionMetrics']['brokenRatio']
        limit_down = cur['emotionMetrics']['limitDownCount']
        
        # 获取连板高度
        ladder = cur.get('ladder', {})
        max_height = max([int(k) for k in ladder.keys()]) if ladder else 0
        
        # 判断逻辑
        if fall > 3500 and broken_ratio > 0.40 and limit_down > 50:
            return "冰点期", ["下跌家数超3500", "炸板率超40%", "跌停数超50只"]
        elif rise > 4000 and broken_ratio < 0.20:
            return "高潮期", ["上涨家数超4000", "炸板率低于20%", "情绪高涨"]
        elif max_height >= 5 and self.is_theme_sustained(cur, prev, prev2):
            return "发酵期", [f"连板高度突破{max_height}板", "主线题材持续", "赚钱效应扩散"]
        elif broken_ratio > 0.30 and limit_down > 20:
            return "退潮期", ["炸板率超30%", "跌停数增加", "接力情绪降温"]
        elif rise > prev['marketSentiment']['rise'] and broken_ratio < prev['emotionMetrics']['brokenRatio']:
            return "复苏期", ["上涨家数增加", "炸板率下降", "情绪开始回暖"]
        else:
            return "震荡期", ["多空分歧", "方向不明", "等待信号"]
    
    def is_theme_sustained(self, cur, prev, prev2=None):
        """判断主题是否持续"""
        cur_themes = {t['name'] for t in cur.get('themes', [])[:2]}
        prev_themes = {t['name'] for t in prev.get('themes', [])[:2]}
        
        if cur_themes & prev_themes:  # 有交集
            return True
        if prev2:
            prev2_themes = {t['name'] for t in prev2.get('themes', [])[:2]}
            if cur_themes & prev2_themes:
                return True
        return False
    
    def generate_market_dashboard(self):
        """生成大盘表 market_dashboard.csv"""
        market_sentiment = self.data.get('market_sentiment', {})
        data_list = market_sentiment.get('data', [])
        
        if not data_list:
            print(f"⚠️ market_sentiment数据为空，跳过生成market_dashboard.csv")
            return
        
        sentiment_data = data_list[0]
        broken_ratio = sentiment_data.get('emotionMetrics', {}).get('brokenRatio', 0)
        limit_down_count = sentiment_data.get('emotionMetrics', {}).get('limitDownCount', 0)
        themes = sentiment_data.get('themes', [])[:2]
        main_themes = ','.join([theme.get('name', '') for theme in themes])
        ladder = sentiment_data.get('ladder', {})
        max_height = max(map(int, ladder.keys())) if ladder else 0
        
        file_path = os.path.join(self.output_dir, 'market_dashboard.csv')
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['日期', '炸板率', '跌停数', '主线题材', '最高板高度'])
            writer.writerow([self.date, broken_ratio, limit_down_count, main_themes, max_height])
        
        print("✓ market_dashboard.csv 生成完成")
    
    def generate_stock_feature_matrix(self):
        """生成个股因子表 stock_feature_matrix.csv"""
        if 'limit_up' not in self.data or 'data' not in self.data['limit_up'] or 'stocks' not in self.data['limit_up']['data']:
            print(f"⚠️ limit_up数据不完整，跳过生成stock_feature_matrix.csv")
            return
        
        dragon_tiger_data = self.data.get('dragon_tiger', {}).get('data', [])
        risk_monitor_data = self.data.get('risk_monitor', {}).get('data', [])
        limit_up_data = self.data['limit_up']['data']['stocks']
        
        stock_regulation = set()
        for stock in risk_monitor_data:
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
        
        file_path = os.path.join(self.output_dir, 'stock_feature_matrix.csv')
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['代码', '连板数', '封单额', '换手率', '是否监管', '是否机构买入', '龙头地位标签'])
            
            for stock in limit_up_data:
                stock_code = stock.get('code', '')
                continue_num = stock.get('continue_num', 0)
                order_amount = stock.get('order_amount', 0)
                turnover_rate = stock.get('turnover_rate', 0)
                is_regulation = '是' if stock_code in stock_regulation else '否'
                is_institution_buy = '是' if stock_code in stock_institution_buy else '否'
                tags = stock.get('tags', [])
                leader_tag = ','.join(tags) if tags else '无'
                
                writer.writerow([stock_code, continue_num, order_amount, turnover_rate, is_regulation, is_institution_buy, leader_tag])
        
        print("✓ stock_feature_matrix.csv 生成完成")
    
    def generate_ai_daily_brief(self):
        """生成 AI 压缩提示词 ai_daily_brief.txt"""
        market_sentiment = self.data.get('market_sentiment', {})
        data_list = market_sentiment.get('data', [])
        
        if not data_list:
            print(f"⚠️ market_sentiment数据为空，跳过生成ai_daily_brief.txt")
            return
        
        # 找到当前日期和前一日期的数据
        current_data = self.find_date_data(data_list, self.date)
        prev_date = self.get_previous_trading_day(self.date)
        previous_data = self.find_date_data(data_list, prev_date)
        
        if not current_data:
            print(f"⚠️ 未找到当前日期 {self.date} 的数据")
            return
        
        # 检查其他必要数据
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
        
        brief = []
        brief.append(f"日期：{self.date}")
        brief.append("")
        
        # ========== 模块1: 市场情绪对比 ==========
        if previous_data:
            brief.append("【情绪对比】较前日({})：".format(prev_date))
            
            cur_rise = current_data['marketSentiment']['rise']
            prev_rise = previous_data['marketSentiment']['rise']
            rise_change, rise_pct = self.format_change(cur_rise, prev_rise)
            rise_trend = self.get_trend_description((cur_rise - prev_rise) / prev_rise if prev_rise else 0)
            brief.append(f"  上涨家数{rise_change}（{rise_pct}）至{cur_rise:.0f}家，赚钱效应{rise_trend}")
            
            cur_fall = current_data['marketSentiment']['fall']
            prev_fall = previous_data['marketSentiment']['fall']
            fall_change, fall_pct = self.format_change(cur_fall, prev_fall)
            fall_trend = "抛压减轻" if cur_fall < prev_fall else "抛压增加" if cur_fall > prev_fall else "抛压稳定"
            brief.append(f"  下跌家数{fall_change}（{fall_pct}）至{cur_fall:.0f}家，{fall_trend}")
            
            # 涨跌比
            cur_ratio = cur_rise / cur_fall if cur_fall > 0 else 999
            prev_ratio = prev_rise / prev_fall if prev_fall > 0 else 999
            brief.append(f"  涨跌比：{cur_ratio:.2f}:1（前日{prev_ratio:.2f}:1）")
            brief.append("")
        
        # ========== 模块2: 亏钱效应对比 ==========
        if previous_data:
            brief.append("【亏钱效应对比】：")
            
            cur_broken = current_data['emotionMetrics']['brokenRatio']
            prev_broken = previous_data['emotionMetrics']['brokenRatio']
            broken_change = self.format_pct_change(cur_broken, prev_broken)
            if cur_broken > prev_broken:
                broken_judge = "市场分歧增加"
            elif cur_broken < prev_broken:
                broken_judge = "市场分歧减小"
            else:
                broken_judge = "分歧维持"
            brief.append(f"  炸板率{cur_broken*100:.2f}%（{broken_change}）→ {broken_judge}")
            
            cur_down = current_data['emotionMetrics']['limitDownCount']
            prev_down = previous_data['emotionMetrics']['limitDownCount']
            down_change, down_pct = self.format_change(cur_down, prev_down)
            if cur_down > 20:
                risk_level = "高风险"
            elif cur_down > 10:
                risk_level = "中等风险"
            elif cur_down > 5:
                risk_level = "低风险"
            else:
                risk_level = "风险可控"
            brief.append(f"  跌停数{cur_down:.0f}只（{down_change}，{down_pct}）→ {risk_level}")
            
            cur_broken_count = current_data['emotionMetrics']['brokenCount']
            prev_broken_count = previous_data['emotionMetrics']['brokenCount']
            broken_count_change, _ = self.format_change(cur_broken_count, prev_broken_count)
            if cur_broken_count > prev_broken_count:
                discord = "亏钱效应扩散"
            elif cur_broken_count < prev_broken_count:
                discord = "亏钱效应收敛"
            else:
                discord = "亏钱效应维持"
            brief.append(f"  断板数{cur_broken_count:.0f}只（{broken_count_change}）→ {discord}")
            brief.append("")
        
        # ========== 模块3: 接力情绪对比 ==========
        if previous_data:
            brief.append("【接力情绪对比】：")
            cur_rates = current_data['emotionMetrics']['promotionRates']
            prev_rates = previous_data['emotionMetrics']['promotionRates']
            
            for rate_key, rate_name in [('1to2', '1进2'), ('2to3', '2进3'), ('high', '高标')]:
                cur_rate = cur_rates.get(rate_key, 0)
                prev_rate = prev_rates.get(rate_key, 0)
                rate_change = cur_rate - prev_rate
                if rate_change > 0:
                    rate_desc = "积极"
                elif rate_change < 0:
                    rate_desc = "谨慎"
                else:
                    rate_desc = "稳定"
                brief.append(f"  {rate_name}：{cur_rate}%（{rate_change:+.0f}pct）→ {rate_desc}")
            brief.append("")
        
        # ========== 模块4: 主题轮动（细化版） ==========
        if previous_data:
            brief.append("【主题轮动】：")
            cur_themes = current_data.get('themes', [])
            prev_themes = previous_data.get('themes', [])
            
            # 使用细化的主题分类
            main_themes, branch_themes, new_themes, fading = self.classify_themes_enhanced(
                cur_themes, prev_themes, data_list, self.date
            )
            
            # 主线（可能有多个）
            if main_themes:
                main_str = ", ".join([f"{t['name']}（第{t['days']}日，{t['count']}只）" for t in main_themes])
                brief.append(f"  主线：{main_str}")
            
            # 支线
            if branch_themes:
                branch_str = ", ".join([f"{t['name']}（第{t['days']}日，{t['count']}只）" for t in branch_themes])
                brief.append(f"  支线：{branch_str}")
            
            # 新晋
            if new_themes:
                new_str = ", ".join([f"{t['name']}（首日，{t['count']}只）" for t in new_themes])
                brief.append(f"  新晋：{new_str}")
            
            # 退潮（显示从多少只降至0只）
            if fading:
                fade_str = ", ".join([f"{t['name']}（从{t['prev_count']}只降至0只）" for t in fading])
                brief.append(f"  退潮：{fade_str}")
            
            brief.append("")
        
        # ========== 模块5: 周期定位 ==========
        if previous_data:
            brief.append("【周期定位】：")
            phase, reasons = self.judge_cycle_phase(current_data, previous_data)
            brief.append(f"  当前阶段：{phase}")
            brief.append(f"  判断理由：")
            for i, reason in enumerate(reasons, 1):
                brief.append(f"    {i}. {reason}")
            brief.append("")
        
        # ========== 模块6: 梯队结构分析 ==========
        brief.append("【梯队结构】：")
        if ladder_detail.get('dates'):
            boards = ladder_detail['dates'][0].get('boards', [])
            ladder_dist = {}
            for board in boards:
                level = board.get('level', 0)
                stocks = board.get('stocks', [])
                ladder_dist[level] = len(stocks)
            
            # 找出最高板
            max_level = max(ladder_dist.keys()) if ladder_dist else 0
            levels_str = "-".join([str(l) for l in sorted(ladder_dist.keys(), reverse=True)])
            brief.append(f"  梯队分布：{levels_str}（最高{max_level}板）")
            
            # 强点弱点分析
            level_1_count = ladder_dist.get(1, 0)
            level_2_count = ladder_dist.get(2, 0)
            
            if level_1_count >= 30:
                brief.append(f"  强点：1板基数充足（{level_1_count}只），后备力量充足")
            else:
                brief.append(f"  弱点：1板基数不足（{level_1_count}只），后续乏力")
            
            if level_2_count >= 5:
                brief.append(f"  强点：2板衔接良好（{level_2_count}只），晋级率健康")
            elif level_2_count > 0:
                brief.append(f"  弱点：2板断层（仅{level_2_count}只），晋级率偏低")
            else:
                brief.append(f"  风险：2板断层严重，接力情绪差")
            brief.append("")
        
        # ========== 模块7: 梯队名单 ==========
        brief.append("【梯队名单】：")
        if ladder_detail.get('dates'):
            boards = ladder_detail['dates'][0].get('boards', [])
            # 按 level 降序排列
            boards_sorted = sorted(boards, key=lambda x: x.get('level', 0), reverse=True)
            
            for board in boards_sorted:
                level = board.get('level', 0)
                stocks = board.get('stocks', [])
                
                if level == 1:
                    # 1板只显示数量
                    brief.append(f"  {level}板：共{len(stocks)}只（详见核心板块）")
                else:
                    # 2板及以上显示具体股票名称和题材
                    stock_details = []
                    for stock in stocks[:5]:  # 最多显示5只
                        name = stock.get('name', '')
                        # 使用 jiuyangongshe_category_name 或 tags 获取题材
                        theme = stock.get('jiuyangongshe_category_name', '')
                        if not theme:
                            tags = stock.get('tags', [])
                            # 过滤掉"总龙头"、"空间龙头"等标签，保留题材标签
                            theme_tags = [t for t in tags if t not in ['总龙头', '空间龙头', '人气核心']]
                            theme = theme_tags[0] if theme_tags else '其他'
                        stock_details.append(f"{name}（{theme}）")
                    
                    if len(stocks) > 5:
                        stock_details.append(f"等{len(stocks)}只")
                    
                    brief.append(f"  {level}板：" + "、".join(stock_details))
            brief.append("")
        
        # ========== 模块8: 龙头族谱 ==========
        brief.append("【龙头族谱】：")
        
        # 识别各类龙头
        total_leader = None
        space_leader = None
        emotion_leader = None
        
        for stock in limit_up_data:
            tags = stock.get('tags', [])
            if '总龙头' in tags or '空间龙头' in tags:
                if not total_leader or stock.get('continue_num', 0) > total_leader.get('continue_num', 0):
                    total_leader = stock
            if '人气核心' in tags:
                emotion_leader = stock
        
        # 从 ladder_detail 找 auto_position
        if ladder_detail.get('dates'):
            for board in ladder_detail['dates'][0].get('boards', []):
                for stock in board.get('stocks', []):
                    if stock.get('auto_position') == '总龙头':
                        total_leader = stock
                    if stock.get('auto_position') == '空间龙头':
                        space_leader = stock
        
        if total_leader:
            name = total_leader.get('name', '')
            code = total_leader.get('code', '')
            continue_num = total_leader.get('continue_num', 0)
            theme = total_leader.get('jiuyangongshe_category_name', '未知')
            brief.append(f"  总龙头：{name}（{code}）{continue_num}板，{theme}")
        
        if space_leader and space_leader != total_leader:
            name = space_leader.get('name', '')
            code = space_leader.get('code', '')
            continue_num = space_leader.get('continue_num', 0)
            brief.append(f"  空间龙：{name}（{code}）{continue_num}板")
        
        if emotion_leader:
            name = emotion_leader.get('name', '')
            code = emotion_leader.get('code', '')
            turnover = emotion_leader.get('turnover_rate', 0)
            brief.append(f"  情绪龙：{name}（{code}），换手{turnover:.2f}%，人气核心")
        
        # 主线龙
        if current_data and current_data.get('themes'):
            main_theme = current_data['themes'][0]['name']
            main_stocks = [s for s in limit_up_data if s.get('jiuyangongshe_category_name') == main_theme]
            if main_stocks:
                main_stocks.sort(key=lambda x: x.get('continue_num', 0), reverse=True)
                leader = main_stocks[0]
                brief.append(f"  主线龙：{leader.get('name')}（{leader.get('code')}）{leader.get('continue_num')}板，{main_theme}")
        brief.append("")
        
        # ========== 模块8: 情绪指标温度 ==========
        brief.append("【情绪指标】：")
        if current_data:
            rise = current_data['marketSentiment']['rise']
            fall = current_data['marketSentiment']['fall']
            broken_ratio = current_data['emotionMetrics']['brokenRatio']
            limit_down = current_data['emotionMetrics']['limitDownCount']
            rates = current_data['emotionMetrics']['promotionRates']
            
            # 计算情绪温度（0-100）
            temp_score = 50
            if rise > fall:
                temp_score += 20
            if broken_ratio < 0.25:
                temp_score += 15
            if limit_down < 10:
                temp_score += 10
            if rates.get('1to2', 0) > 30:
                temp_score += 5
            
            temp_score = min(100, max(0, temp_score))
            
            if temp_score >= 80:
                temp_desc = "过热"
            elif temp_score >= 60:
                temp_desc = "偏暖"
            elif temp_score >= 40:
                temp_desc = "中性"
            elif temp_score >= 20:
                temp_desc = "偏冷"
            else:
                temp_desc = "冰点"
            
            brief.append(f"  情绪温度：{temp_score}/100（{temp_desc}）")
            brief.append(f"  🔼 上涨：{rise}家  🔽 下跌：{fall}家")
            brief.append(f"  💥 炸板率：{broken_ratio*100:.1f}%  📉 跌停：{limit_down}只")
            brief.append(f"  📈 晋级率：1→2:{rates.get('1to2', 0)}% 2→3:{rates.get('2to3', 0)}% 高标:{rates.get('high', 0)}%")
            brief.append("")
        
        # ========== 模块9: 核心板块与个股详情（原Section 8.2） ==========
        brief.append("【核心板块与个股详情】：")
        brief.append("")
        
        # 时间戳格式化函数
        def format_limit_time(ts):
            if not ts:
                return "09:25:00"
            try:
                return datetime.fromtimestamp(int(ts)).strftime('%H:%M:%S')
            except:
                return "09:25:00"
        
        # 获取前3大主线题材
        top_themes = sorted(sector_heat, key=lambda x: x.get('count', 0), reverse=True)[:3]
        
        for idx, theme_data in enumerate(top_themes, 1):
            theme_name = theme_data.get('name', '')
            theme_count = theme_data.get('count', 0)
            
            brief.append(f"主线{idx}：{theme_name}（{theme_count}只）")
            
            # 获取该题材下的所有涨停股
            theme_stocks = [s for s in limit_up_data if s.get('jiuyangongshe_category_name') == theme_name]
            # 按连板数降序排列
            theme_stocks.sort(key=lambda x: x.get('continue_num', 0), reverse=True)
            
            for stock in theme_stocks[:8]:  # 每个题材最多显示8只
                name = stock.get('name', '')
                code = stock.get('code', '')
                continue_num = stock.get('continue_num', 0)
                
                # 获取逻辑（reason_type 或 jiuyangongshe_analysis）
                logic = stock.get('reason_type', '')
                if not logic:
                    analysis = stock.get('jiuyangongshe_analysis', '')
                    if analysis:
                        logic = analysis.split('\n')[0][:20]  # 取第一行前20字
                
                # 第1行：名称代码+连板+逻辑
                brief.append(f"  {name}({code}) {continue_num}板：{logic}")
                
                # 第2行：封单数据
                order_amount = stock.get('order_amount', 0)
                trading_amount = stock.get('trading_amount', 0)
                actual_currency = stock.get('actual_currency_value', 0) or 0
                
                order_amount_yi = order_amount / 1e8
                seal_ratio = (order_amount / trading_amount * 100) if trading_amount > 0 else 0
                seal_flow = (order_amount / actual_currency * 100) if actual_currency > 0 else 0
                
                brief.append(f"    封单{order_amount_yi:.2f}亿/封成{seal_ratio:.1f}%/封流{seal_flow:.1f}%")
                
                # 第3行：实流+题材
                actual_yi = actual_currency / 1e8
                brief.append(f"    实流{actual_yi:.2f}亿 题材:{stock.get('jiuyangongshe_category_name', '')}")
            
            if len(theme_stocks) > 8:
                brief.append(f"  ...等共{len(theme_stocks)}只")
            
            brief.append("")
        
        # ========== 模块10: 龙虎榜机构与游资博弈 ==========
        brief.append("【龙虎榜博弈】：")
        dragon_tiger_data = self.data.get('dragon_tiger', {}).get('data', [])
        
        famous_yz_seats = [
            '华鑫证券有限责任公司绍兴胜利东路证券营业部',
            '华鑫证券有限责任公司上海分公司',
            '国泰君安证券股份有限公司南京太平南路证券营业部',
            '中国银河证券股份有限公司绍兴证券营业部',
            '中信证券股份有限公司上海溧阳路证券营业部',
            '东方财富证券股份有限公司拉萨团结路第一证券营业部',
            '东方财富证券股份有限公司拉萨东环路第一证券营业部',
            '国盛证券有限责任公司宁波桑田路证券营业部',
            '财通证券股份有限公司杭州上塘路证券营业部',
        ]
        
        institution_buys = []
        yz_dominant = []
        
        for record in dragon_tiger_data:
            stock_code = record.get('stockCode', '')
            stock_name = record.get('stockName', '')
            lhb_branch = record.get('lhbBranch', {})
            buy_branches = lhb_branch.get('buyBranches', [])
            sell_branches = lhb_branch.get('sellBranches', [])
            
            institution_buy = sum(b.get('netValue', 0) for b in buy_branches if b.get('branchName') == '机构专用')
            institution_sell = sum(s.get('netValue', 0) for s in sell_branches if s.get('branchName') == '机构专用')
            institution_net = institution_buy - institution_sell
            
            yz_buy = sum(b.get('netValue', 0) for b in buy_branches if b.get('branchName') in famous_yz_seats)
            yz_sell = sum(s.get('netValue', 0) for s in sell_branches if s.get('branchName') in famous_yz_seats)
            yz_net = yz_buy - yz_sell
            
            if institution_net > 1000:
                institution_buys.append({'name': stock_name, 'code': stock_code, 'net': institution_net})
            elif yz_net > 1000 and institution_net < 500:
                yz_dominant.append({'name': stock_name, 'code': stock_code, 'yz_net': yz_net})
        
        institution_buys.sort(key=lambda x: x['net'], reverse=True)
        yz_dominant.sort(key=lambda x: x['yz_net'], reverse=True)
        
        if institution_buys:
            brief.append("  机构净买入Top：")
            for item in institution_buys[:3]:
                brief.append(f"    {item['name']}({item['code']}): {item['net']:.0f}万")
        
        if yz_dominant:
            brief.append("  游资主导：")
            for item in yz_dominant[:3]:
                brief.append(f"    {item['name']}({item['code']}): {item['yz_net']:.0f}万")
        
        if not institution_buys and not yz_dominant:
            brief.append("  当日龙虎榜无显著机构或游资动向")
        brief.append("")
        
        # 写入文件
        file_path = os.path.join(self.output_dir, 'ai_daily_brief.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(brief))
        
        print("✓ ai_daily_brief.txt 生成完成")
    
    def run(self):
        """执行完整的 ETL 流程"""
        print(f"开始处理 {self.date} 的数据...")
        self.generate_market_dashboard()
        self.generate_stock_feature_matrix()
        self.generate_ai_daily_brief()
        print("所有文件生成完成！")


class FeishuPush:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def read_file_content(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"读取文件失败: {e}")
            return None
    
    def txt_to_markdown(self, txt_content):
        if not txt_content:
            return None
        
        lines = txt_content.split('\n')
        markdown = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('日期：'):
                markdown.append(f"## 📅 {line}")
            elif line.startswith('【'):
                markdown.append(f"\n### {line}")
            elif line.startswith('  '):
                markdown.append(line)
            else:
                markdown.append(line)
        
        return '\n'.join(markdown)
    
    def push_markdown(self, markdown_content):
        if not markdown_content:
            print("❌ Markdown内容为空，无法推送")
            return False
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "📊 量化复盘日报"},
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": markdown_content
                        }
                    }
                ]
            }
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                print("✅ 飞书Markdown消息推送成功")
                return True
            else:
                print(f"❌ 飞书推送失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ 飞书推送异常: {e}")
            return False
    
    def push_text(self, content):
        if not content:
            print("❌ 内容为空，无法推送")
            return False
        
        payload = {
            "msg_type": "text",
            "content": {"text": content}
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                print("✅ 飞书文本消息推送成功")
                return True
            else:
                print(f"❌ 飞书推送失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 飞书推送异常: {e}")
            return False


def get_valid_date_dir(base_dir, mode='clean'):
    """获取有效的日期目录"""
    if not os.path.exists(base_dir):
        print(f"❌ 基础目录不存在: {base_dir}")
        return None
    
    dates = []
    for d in os.listdir(base_dir):
        dir_path = os.path.join(base_dir, d)
        if os.path.isdir(dir_path):
            try:
                datetime.strptime(d, '%Y-%m-%d')
                if mode == 'push':
                    ai_brief_path = os.path.join(dir_path, 'ai_daily_brief.txt')
                    if os.path.exists(ai_brief_path):
                        dates.append(d)
                else:
                    dates.append(d)
            except ValueError:
                continue
    
    if not dates:
        print(f"❌ 没有找到有效的日期目录")
        return None
    
    dates.sort(reverse=True)
    
    if mode == 'push':
        for date in dates:
            dir_path = os.path.join(base_dir, date)
            ai_brief_path = os.path.join(dir_path, 'ai_daily_brief.txt')
            if os.path.exists(ai_brief_path):
                print(f"✅ 找到包含完整数据的最新目录: {date}")
                return date
        print(f"⚠️ 没有找到包含ai_daily_brief.txt的目录")
        return dates[0]
    
    print(f"✅ 使用最新目录: {dates[0]}")
    return dates[0]


if __name__ == "__main__":
    import sys
    
    target_date = None
    run_mode = 'clean'
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "push":
            run_mode = 'push'
            i += 1
        elif sys.argv[i] == "--date" and i + 1 < len(sys.argv):
            target_date = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    if run_mode == 'push':
        webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/868d66cc-7980-4bc0-b2da-45c27aa21bb3"
        
        cleaned_data_dir = r'c:\Users\Liu\Desktop\projects\quant\data\cleaned_data'
        
        if target_date:
            latest_date = target_date
            print(f"✅ 使用指定日期: {latest_date}")
        else:
            latest_date = get_valid_date_dir(cleaned_data_dir, mode='push')
            if not latest_date:
                sys.exit(1)
        
        file_path = os.path.join(cleaned_data_dir, latest_date, "ai_daily_brief.txt")
        feishu = FeishuPush(webhook_url)
        content = feishu.read_file_content(file_path)
        
        if content:
            markdown_content = feishu.txt_to_markdown(content)
            if markdown_content:
                feishu.push_markdown(markdown_content)
            else:
                feishu.push_text(content)
        else:
            print(f"❌ 文件内容读取失败或文件为空，无法推送: {file_path}")
    else:
        data_lake_dir = r'c:\Users\Liu\Desktop\projects\quant\data\data_lake'
        cleaned_data_dir = r'c:\Users\Liu\Desktop\projects\quant\data\cleaned_data'
        
        if target_date:
            data_dir = os.path.join(data_lake_dir, target_date)
            output_dir = os.path.join(cleaned_data_dir, target_date)
            if not os.path.exists(data_dir):
                print(f"❌ 指定的日期目录不存在: {data_dir}")
                sys.exit(1)
            os.makedirs(output_dir, exist_ok=True)
            cleaner = StockDataCleaner(data_dir, output_dir)
            cleaner.run()
            
            print("\n" + "="*50)
            print("📤 清洗完成，开始自动推送数据到飞书...")
            print("="*50 + "\n")
            
            # 飞书推送改为后台线程执行，避免阻塞主流程
            def push_to_feishu_async(output_dir, webhook_url):
                """后台线程执行飞书推送"""
                file_path = os.path.join(output_dir, "ai_daily_brief.txt")
                feishu = FeishuPush(webhook_url)
                content = feishu.read_file_content(file_path)
                
                if content:
                    markdown_content = feishu.txt_to_markdown(content)
                    if markdown_content:
                        feishu.push_markdown(markdown_content)
                    else:
                        feishu.push_text(content)
                else:
                    print(f"❌ 文件内容读取失败或文件为空，无法推送: {file_path}")
            
            webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/868d66cc-7980-4bc0-b2da-45c27aa21bb3"
            push_thread = threading.Thread(
                target=push_to_feishu_async,
                args=(output_dir, webhook_url),
                daemon=True
            )
            push_thread.start()
            print("✅ 飞书推送已启动（后台异步执行）")
            
        else:
            latest_date = get_valid_date_dir(data_lake_dir, mode='clean')
            if not latest_date:
                sys.exit(1)
            
            data_dir = os.path.join(data_lake_dir, latest_date)
            output_dir = os.path.join(cleaned_data_dir, latest_date)
            os.makedirs(output_dir, exist_ok=True)
            cleaner = StockDataCleaner(data_dir, output_dir)
            cleaner.run()
            
            print("\n" + "="*50)
            print("📤 清洗完成，开始自动推送数据到飞书...")
            print("="*50 + "\n")
            
            # 飞书推送改为后台线程执行
            def push_to_feishu_async(output_dir, webhook_url):
                """后台线程执行飞书推送"""
                file_path = os.path.join(output_dir, "ai_daily_brief.txt")
                feishu = FeishuPush(webhook_url)
                content = feishu.read_file_content(file_path)
                
                if content:
                    markdown_content = feishu.txt_to_markdown(content)
                    if markdown_content:
                        feishu.push_markdown(markdown_content)
                    else:
                        feishu.push_text(content)
                else:
                    print(f"❌ 文件内容读取失败或文件为空，无法推送: {file_path}")
            
            webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/868d66cc-7980-4bc0-b2da-45c27aa21bb3"
            push_thread = threading.Thread(
                target=push_to_feishu_async,
                args=(output_dir, webhook_url),
                daemon=True
            )
            push_thread.start()
            print("✅ 飞书推送已启动（后台异步执行）")
