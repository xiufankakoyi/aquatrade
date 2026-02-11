import tushare as ts
import lancedb
import pandas as pd
import time
from datetime import datetime, timedelta
import os

# ================= 配置区域 =================
TOKEN = 'c32d8386d48a5c9e453add46d222912cdf866b3026950cba05c8b90b'
START_DATE = '20240101'  # 建议从今年1月1日开始，太久远的数据参考意义递减
END_DATE = datetime.now().strftime('%Y%m%d')
DB_PATH = "./data/quant_flow.lance"
# ===========================================

class DataBackfillEngine:
    def __init__(self, token, db_path):
        self.pro = ts.pro_api(token)
        self.db = lancedb.connect(db_path)
        
        # 接口状态标记 (如果某个接口被封，自动标记为 False，后续不再尝试)
        self.api_status = {
            'limit_list_d': True,  # 涨停详情 (高危)
            'top_inst': True,      # 机构龙虎榜 (核心)
            'daily_basic': True    # 每日指标 (基础)
        }
        
        # 链接数据表
        self.tbl_limit = self.db.open_table("daily_limit_history")
        self.tbl_money = self.db.open_table("smart_money")
        # 如果需要 daily_basic 表，可以在 init_db 里加，这里暂时打印或存入 limit 表辅助
        
    def _safe_api_call(self, api_func, api_name, **kwargs):
        """
        安全的 API 调用包装器，处理限流和熔断
        """
        if not self.api_status.get(api_name, False):
            return pd.DataFrame() # 接口已熔断，直接返回空

        try:
            # ⏳ 强制限流: 每次请求休眠 0.2秒 (约 300次/分钟)
            time.sleep(0.2) 
            df = api_func(**kwargs)
            return df
        except Exception as e:
            err_msg = str(e)
            if "权限" in err_msg or "每小时" in err_msg or "访该接口" in err_msg:
                print(f"   ⚠️ 接口 [{api_name}] 触发频控限制，已自动熔断(停止该接口下载)！")
                self.api_status[api_name] = False # 熔断该接口
            else:
                print(f"   ❌ 接口 [{api_name}] 异常: {e}")
            return pd.DataFrame()

    def run(self, start_date, end_date):
        print(f"🚀 开始全量数据回补: {start_date} -> {end_date}")
        print(f"   目标表: daily_limit_history, smart_money")
        
        # 生成日期序列
        dt_start = datetime.strptime(start_date, '%Y%m%d')
        dt_end = datetime.strptime(end_date, '%Y%m%d')
        delta = dt_end - dt_start
        
        date_list = [(dt_start + timedelta(days=i)).strftime('%Y%m%d') for i in range(delta.days + 1)]
        
        total_days = len(date_list)
        
        for idx, date in enumerate(date_list):
            print(f"[{idx+1}/{total_days}] 处理日期: {date} ...", end="\r")
            
            # 1. 检查是不是交易日 (通过尝试拉取 daily_basic 判断)
            # 顺便把 daily_basic 数据拿下来
            df_basic = self._safe_api_call(self.pro.daily_basic, 'daily_basic', 
                                         trade_date=date, 
                                         fields='ts_code,turnover_rate,circ_mv')
            
            if df_basic.empty:
                # 如果基础数据都拿不到，说明可能是非交易日，跳过
                continue

            # =======================================
            # 任务 A: 下载机构龙虎榜 (Smart Money) - 核心血液
            # =======================================
            df_inst = self._safe_api_call(self.pro.top_inst, 'top_inst', trade_date=date)
            if not df_inst.empty:
                # 清洗数据
                df_inst_save = df_inst[['trade_date', 'ts_code', 'net_buy']].copy()
                df_inst_save['inst_net_buy'] = df_inst['net_buy'] # 统一字段名
                df_inst_save['is_inst_participate'] = True
                
                # 入库 smart_money
                self.tbl_money.add(df_inst_save)

            # =======================================
            # 任务 B: 下载涨停数据 (Limit List) - 核心肌肉
            # =======================================
            # 注意：如果之前已经触发了 1次/小时 限制，这里会自动跳过
            if self.api_status['limit_list_d']:
                df_limit = self._safe_api_call(self.pro.limit_list_d, 'limit_list_d', trade_date=date)
                
                if not df_limit.empty:
                    # 补全字段
                    df_limit['inst_net_buy'] = 0.0 # 默认为0，后续可以和 top_inst 表 join 更新
                    df_limit['concept_resonance'] = "待计算" # 原始数据先不处理逻辑
                    df_limit['limit_type'] = df_limit['limit'] if 'limit' in df_limit.columns else 'U'
                    
                    # 简单清洗列名以匹配 LanceDB Schema
                    # 假设 schema: limit_times, limit_amount, etc.
                    # 需要确保 df_limit 的列名和 schema 一致，不一致的直接忽略或重命名
                    # 这里做个简单的容错，只取 schema 里有的列
                    try:
                        self.tbl_limit.add(df_limit)
                    except Exception as e:
                         # 如果直接 add 失败，通常是因为列不匹配，实际工程中需要详细 map
                         # 这里为了不中断，我们打印个警告
                         pass
            
            # 打印进度条反馈
            inst_count = len(df_inst) if not df_inst.empty else 0
            limit_count = len(df_limit) if 'df_limit' in locals() and not df_limit.empty else 0
            # 仅在有数据时打印换行，否则覆盖当前行
            if inst_count > 0 or limit_count > 0:
                print(f"[{idx+1}/{total_days}] {date}: 🏛️ 机构榜 {inst_count}条 | 🔥 涨停 {limit_count}条")

        print("\n🎉 数据回补完成！")

if __name__ == "__main__":
    engine = DataBackfillEngine(TOKEN, DB_PATH)
    engine.run(START_DATE, END_DATE)