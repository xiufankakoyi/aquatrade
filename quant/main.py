import os
import time
import json
import math
import random
import requests
import argparse
import sys
import re
from datetime import datetime, timedelta

# --- Selenium 相关库 (新增 Edge 支持) ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# ==========================================
# 1. 配置区域 (Configuration)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
TARGET_SITE_URL = "https://stock.quicktiny.cn/"

# 默认配置
DEFAULT_CONFIG = {
    "TOKEN": "", 
    "USERNAME": "",  # 新增：账号
    "PASSWORD": "",  # 新增：密码
    "HEADERS": {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "priority": "u=1, i",
        "referer": "https://stock.quicktiny.cn/",
        "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    },
    "DATA_DIR": os.path.join(BASE_DIR, "data_lake")
}

def load_config():
    """加载配置"""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                ext_config = json.load(f)
                config.update(ext_config)
        except Exception as e:
            print(f"⚠️ 配置文件读取失败: {e}")
    return config

def save_token_to_config(new_token):
    """保存新 Token 到 config.json"""
    clean_token = new_token.replace("Bearer ", "").strip()
    current_conf = load_config()
    current_conf["TOKEN"] = clean_token
    
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(current_conf, f, ensure_ascii=False, indent=2)
    print(f"💾 新 Token 已保存到配置文件")
    return clean_token

# ==========================================
# 2. Token 自动获取模块 (双浏览器保险版)
# ==========================================
def get_browser_driver():
    """
    尝试启动浏览器：优先 Edge，失败则转 Chrome
    """
    # 方案 A: 尝试 Microsoft Edge (Windows 必有)
    try:
        print("   [1/2] 尝试启动 Microsoft Edge...")
        options = EdgeOptions()
        # 直接使用系统已安装的Edge，无需下载驱动
        driver = webdriver.Edge(options=options)
        return driver
    except Exception as e:
        print(f"   ⚠️ Edge 启动失败 (未安装或路径错误)")

    # 方案 B: 尝试 Chrome
    try:
        print("   [2/2] 尝试启动 Google Chrome...")
        options = ChromeOptions()
        # options.add_argument("--headless") # 调试阶段注释掉
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"❌ 浏览器启动全军覆没: {e}")
        return None

def launch_browser_for_token():
    """启动浏览器捕获 Token"""
    print("\n" + "="*50)
    print("🔓 Token 失效！正在启动浏览器...")
    print("👉 请在弹出的窗口中【扫码登录】或【等待自动登录】")
    print("="*50 + "\n")

    # 加载配置，获取账号密码
    config = load_config()
    username = config.get("USERNAME", "")
    password = config.get("PASSWORD", "")

    driver = get_browser_driver()
    if not driver:
        print("❌ 无法找到 Chrome 或 Edge 浏览器，请确保至少安装了一个。")
        sys.exit(1)
    
    captured_token = None
    
    try:
        driver.get(TARGET_SITE_URL)
        
        # 新增：自动填写账号密码
        if username and password:
            print(f"\n🔑 检测到账号密码，尝试自动登录...")
            time.sleep(3)  # 等待页面加载
            
            try:
                # 尝试查找登录相关元素（需要根据实际页面调整）
                # 注意：这些选择器是示例，需要根据实际页面结构调整
                # 切换到账号密码登录
                # driver.find_element(By.XPATH, "//div[contains(text(), '账号密码登录')]").click()
                # time.sleep(1)
                
                # 查找账号输入框
                username_input = driver.find_element(By.XPATH, "//input[@type='text' or @placeholder='手机号' or @placeholder='账号']")
                password_input = driver.find_element(By.XPATH, "//input[@type='password' or @placeholder='密码']")
                login_button = driver.find_element(By.XPATH, "//button[contains(text(), '登录') or contains(text(), 'Login')]")
                
                # 填写账号密码
                username_input.send_keys(username)
                password_input.send_keys(password)
                time.sleep(1)
                login_button.click()
                print("   ✅ 已提交账号密码登录请求")
            except Exception as e:
                print(f"   ⚠️ 自动登录失败（可能是登录页面结构变化）: {e}")
                print("   👉 请手动扫码或填写账号密码登录")
        
        # 循环检测 Token (180秒)
        for i in range(180):
            time.sleep(1)
            
            # 注入 JS 嗅探
            token_candidate = driver.execute_script("""
                let keys = ['token', 'Token', 'Authorization', 'user_token', 'access_token'];
                for (let key of keys) {
                    let val = localStorage.getItem(key);
                    if (val && val.includes('eyJ')) return val;
                }
                for (let i = 0; i < localStorage.length; i++) {
                    let val = localStorage.getItem(localStorage.key(i));
                    if (val && val.includes('eyJ')) return val;
                }
                return null;
            """)
            
            if token_candidate:
                match = re.search(r'(eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+)', token_candidate)
                if match:
                    captured_token = match.group(1)
                    print(f"\n🎉 成功捕获 Token!")
                    break
            
            print(f"⏳ 等待登录... ({i}/180s)", end="\r")
            
    except Exception as e:
        print(f"❌ 浏览器操作异常: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass
        
    if captured_token:
        return save_token_to_config(captured_token)
    else:
        print("\n❌ 获取 Token 失败（超时）。")
        sys.exit(1)

# ==========================================
# 3. API 接口配置 (不变)
# ==========================================
API_MAP = {
    "ladder_trend_summary": { "url": "https://stock.quicktiny.cn/api/ladder?startDate={date_dash}&endDate={date_dash}", "type": "simple" },
    "ladder_hierarchy_detail": { "url": "https://stock.quicktiny.cn/api/ladder/day/{date_nodash}", "type": "simple" },
    "limit_up_filter": { "url": "https://stock.quicktiny.cn/api/limit-up/filter?date={date_nodash}&reasonTypeInput=&page={page}&limit=100", "type": "pagination", "data_key": "stocks" },
    "sector_heat_stats": { "url": "https://stock.quicktiny.cn/api/limit-up/filter/concept-tags-stats?date={date_nodash}", "type": "simple" },
    "market_sentiment_cycle": { "url": "https://stock.quicktiny.cn/api/ladder/cycle-analysis?startDate={date_dash}&endDate={date_dash}", "type": "simple" },
    "dragon_tiger_list": { "url": "https://stock.quicktiny.cn/api/admin/dragon-tiger-board-user?startDate={date_dash}&endDate={date_dash}&pageSize=100&stockCode=&stockName=&infoClassCode=&branchSearch=", "type": "simple" },
    "risk_monitor_list": { "url": "https://stock.quicktiny.cn/api/ladder/exchange-monitor/list?type=all", "type": "simple" }
}

# ==========================================
# 4. 智能爬虫类 (集成自愈逻辑)
# ==========================================
class StealthCrawler:
    def __init__(self):
        self.config = load_config()
        self.session = requests.Session()
        self.refresh_session_headers()

    def refresh_session_headers(self):
        headers = self.config["HEADERS"].copy()
        token = self.config.get("TOKEN", "")
        if token:
            headers["authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

    def random_sleep(self):
        sleep_time = random.uniform(2.5, 5.5) 
        print(f"   ☕ 休息 {sleep_time:.1f}s...", end="\r")
        time.sleep(sleep_time)

    def fetch_simple(self, url, retry_count=0):
        try:
            resp = self.session.get(url)
            
            # Token 过期处理
            if resp.status_code == 401:
                if retry_count >= 1:
                    print("\n❌ Token 获取后依然无效，退出。")
                    sys.exit(1)
                    
                print(f"\n⚠️ 接口返回 401 (未授权) -> 触发自动登录流程")
                
                # 启动浏览器获取新 Token
                new_token = launch_browser_for_token()
                
                # 更新当前内存中的配置
                self.config["TOKEN"] = new_token
                self.refresh_session_headers()
                
                print("🔄 正在重试请求...")
                return self.fetch_simple(url, retry_count=1)
            
            if resp.status_code == 200:
                return resp.json()
            return None
            
        except Exception as e:
            print(f"\n❌ 网络请求异常: {e}")
            return None

    def fetch_pagination(self, url_template, data_key):
        all_items = []
        page = 1
        
        while True:
            current_url = url_template.replace("{page}", str(page))
            print(f"   [📄 第{page}页] ... ", end="")
            
            resp_json = self.fetch_simple(current_url)
            
            if not resp_json or "data" not in resp_json:
                print("停止(无数据)")
                break
                
            current_data = resp_json.get("data", {})
            if isinstance(current_data, dict):
                items = current_data.get(data_key, [])
                pagination_info = current_data.get("pagination", {})
                total_count = pagination_info.get("total", 0)
                page_size = pagination_info.get("pageSize", 100)
            else:
                items = []
                total_count = 0
                page_size = 100

            if not items:
                print("停止(空列表)")
                break
                
            all_items.extend(items)
            print(f"获取 {len(items)} 条 (累计 {len(all_items)})")
            
            total_pages = math.ceil(total_count / page_size)
            if page >= total_pages:
                break
            
            page += 1
            self.random_sleep()
            
        return {
            "success": True,
            "data": {
                data_key: all_items,
                "note": "Auto-merged by crawler"
            }
        }

    def run_task(self, target_date):
        date_nodash = target_date.strftime("%Y%m%d")
        date_dash = target_date.strftime("%Y-%m-%d")
        
        day_dir = os.path.join(self.config["DATA_DIR"], date_dash)
        if not os.path.exists(day_dir):
            os.makedirs(day_dir)

        print(f"\n📅 处理日期: {date_dash}")

        for api_key, api_conf in API_MAP.items():
            file_path = os.path.join(day_dir, f"{api_key}.json")
            if os.path.exists(file_path):
                print(f"   [✅ 已存在] {api_key}")
                continue

            url_final = api_conf["url"].format(
                date_nodash=date_nodash, 
                date_dash=date_dash,
                page="{page}"
            )

            try:
                print(f"   [📡 请求] {api_key} ... ", end="")
                
                final_data = None
                if api_conf["type"] == "pagination":
                    print("") 
                    final_data = self.fetch_pagination(url_final, api_conf["data_key"])
                else:
                    final_data = self.fetch_simple(url_final)
                    
                if final_data:
                    print("成功")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(final_data, f, ensure_ascii=False, indent=2)
                    self.random_sleep()
                    
            except Exception as e:
                print(f"❌ 异常: {e}")

# ==========================================
# 5. 主入口
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QuantData 自动爬虫 (含自动登录)")
    parser.add_argument("--date", type=str, help="指定爬取日期 (格式 YYYY-MM-DD)")
    parser.add_argument("--backfill", type=int, help="向前回溯补录几天的数据", default=0)
    args = parser.parse_args()
    
    crawler = StealthCrawler()
    
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d")
        crawler.run_task(target)
    elif args.backfill > 0:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.backfill)
        curr = start_date
        while curr <= end_date:
            crawler.run_task(curr)
            curr += timedelta(days=1)
    else:
        target = datetime.now()
        print(f"🚀 默认抓取今天 ({target.strftime('%Y-%m-%d')})")
        crawler.run_task(target)
        
    print("\n🎉 任务结束。")