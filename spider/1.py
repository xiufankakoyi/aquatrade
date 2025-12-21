from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import traceback
import re
import json
import csv
import time
import datetime  # CHANGED: 添加datetime模块用于记录爬取时间
import argparse
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import msvcrt
except ImportError:
    msvcrt = None

from pathlib import Path

# 【新增】准备一批最新的 User-Agent 列表
USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

#获取股票代码
import tushare as ts
import pandas as pd

# CHANGED: 定义要爬取的板块列表（指数吧和行业板块）
PLATE_CODES = {
    # 指数吧
    "上证指数吧": "zs_000001",
    "深证成指吧": "zs_399001", 
    "创业板指吧": "zs_399006",
    
    # 热门行业板块
    "白酒板块": "bk_885525",  # 白酒概念
    "新能源板块": "bk_885744",  # 新能源
    "半导体板块": "bk_885845",  # 半导体
    "新能源汽车": "bk_885461",  # 新能源汽车
    "光伏概念": "bk_885531",  # 光伏概念
    "锂电池": "bk_885750",  # 锂电池
    "人工智能": "bk_885728",  # 人工智能
    "芯片概念": "bk_885756",  # 芯片概念
    "5G概念": "bk_885556",  # 5G概念
    "医疗": "bk_885683",  # 医疗器械
    "房地产": "bk_885744",  # 房地产开发
    "银行": "bk_885524",  # 银行
    "证券": "bk_885744",  # 证券
    "保险": "bk_885744",  # 保险
    "钢铁": "bk_885744",  # 钢铁
    "煤炭": "bk_885744",  # 煤炭
}

def get_popular_stocks_from_guba(driver, limit=300):
    """
    从东方财富股吧人气榜获取前N名股票代码
    
    Args:
        driver: WebDriver实例
        limit: 获取前N名（默认300）
    
    Returns:
        list: 股票代码列表（格式：sz000001, sh600000等）
    """
    print(f"正在获取东方财富人气榜前 {limit} 名股票...")
    codes = []
    
    try:
        # 访问人气榜页面
        rank_url = "https://guba.eastmoney.com/rank"
        driver.get(rank_url)
        time.sleep(3)  # 等待页面加载
        
        html = driver.page_source
        
        # 方法1: 尝试从页面中提取人气榜数据
        # 东方财富人气榜通常在特定的JavaScript变量中
        pattern = re.compile(r'rank_list\s*=\s*(\[[\s\S]*?\])', re.S)
        match = pattern.search(html)
        
        if match:
            try:
                rank_data = json.loads(match.group(1))
                for item in rank_data[:limit]:
                    # 提取股票代码，格式可能是 "000001" 或 "sz000001"
                    code = item.get('code') or item.get('stock_code') or item.get('symbol', '')
                    if code:
                        # 标准化代码格式
                        if not code.startswith(('sz', 'sh')):
                            if code.startswith('0') or code.startswith('3'):
                                code = f"sz{code}"
                            elif code.startswith('6'):
                                code = f"sh{code}"
                        codes.append(code)
            except Exception as e:
                print(f"解析人气榜JSON失败: {e}")
        
        # 方法2: 如果方法1失败，尝试从HTML表格中提取
        if not codes:
            try:
                # 查找包含股票代码的元素
                code_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/list,'], .code, .stock-code")
                for elem in code_elements[:limit]:
                    try:
                        href = elem.get_attribute('href') or ''
                        text = elem.text.strip()
                        
                        # 从href中提取代码
                        match = re.search(r'/list,([^_\.]+)', href)
                        if match:
                            code = match.group(1)
                            if code and code not in codes:
                                codes.append(code)
                        # 或者从文本中提取
                        elif re.match(r'^\d{6}$', text):
                            if text.startswith(('0', '3')):
                                code = f"sz{text}"
                            elif text.startswith('6'):
                                code = f"sh{text}"
                            else:
                                code = text
                            if code and code not in codes:
                                codes.append(code)
                    except:
                        continue
            except Exception as e:
                print(f"从HTML提取股票代码失败: {e}")
        
        # 方法3: 如果还是失败，使用tushare获取热门股票（按市值或成交量）
        if not codes or len(codes) < limit:
            print(f"从人气榜获取到 {len(codes)} 只股票，使用tushare补充...")
            try:
                ts.set_token("c32d8386d48a5c9e453add46d222912cdf866b3026950cba05c8b90b")
                pro = ts.pro_api()
                
                # 获取所有股票基本信息
                df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
                
                # 按市值或成交量排序，取前N名
                # 这里简化处理，直接取前N只股票
                df = df.head(limit)
                
                df["code_fmt"] = df["ts_code"].str.replace(
                    r"(\d+)\.(\w+)", 
                    lambda m: m.group(2).lower() + m.group(1),
                    regex=True
                )
                
                tushare_codes = df["code_fmt"].tolist()
                # 合并去重
                for code in tushare_codes:
                    if code not in codes:
                        codes.append(code)
                        if len(codes) >= limit:
                            break
            except Exception as e:
                print(f"使用tushare获取股票代码失败: {e}")
        
        codes = codes[:limit]  # 确保不超过限制
        print(f"成功获取 {len(codes)} 只股票代码")
        return codes
        
    except Exception as e:
        print(f"获取人气榜股票失败: {e}")
        traceback.print_exc()
        # 如果失败，返回空列表，后续会使用tushare的默认逻辑
        return []

# 初始化时先获取人气榜股票（如果需要）
# 注意：这里先不获取，等driver初始化后再获取
codes = []  # 将在主循环中填充

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

THROTTLE_PAGES_DEFAULT = 100
THROTTLE_SLEEP_SECONDS_DEFAULT = 300
MAX_PAGES_BEFORE_REST = 199  # 5个线程总共爬取超过199页后休息
REST_SECONDS = 300  # 休息300秒

parser = argparse.ArgumentParser()
parser.add_argument("--group-index", type=int, default=0)
parser.add_argument("--group-total", type=int, default=1)
parser.add_argument("--throttle-pages", type=int, default=THROTTLE_PAGES_DEFAULT)
parser.add_argument("--throttle-sleep", type=int, default=THROTTLE_SLEEP_SECONDS_DEFAULT)
parser.add_argument("--fetch-content", action="store_true", help="是否爬取帖子正文内容（会增加运行时间）")
parser.add_argument("--update-existing", action="store_true", help="更新已有CSV文件中缺少内容的帖子")
parser.add_argument("--update-all", action="store_true", help="全量更新：重新爬取所有数据，包括标题、内容等所有字段")
parser.add_argument("--threads", type=int, default=5, help="爬取线程数（默认5个）")
args = parser.parse_args()

GROUP_INDEX = max(0, args.group_index)
GROUP_TOTAL = max(1, args.group_total)
THROTTLE_PAGES = max(1, args.throttle_pages)
THROTTLE_SLEEP_SECONDS = max(0, args.throttle_sleep)
FETCH_CONTENT = args.fetch_content
UPDATE_EXISTING = args.update_existing
UPDATE_ALL = args.update_all
NUM_THREADS = max(1, args.threads)  # CHANGED: 线程数，默认5个

# 如果启用全量更新，自动启用内容爬取
if UPDATE_ALL:
    FETCH_CONTENT = True

# CHANGED: 全局页面计数器（线程安全）
global_page_count = 0
page_count_lock = threading.Lock()
rest_event = threading.Event()  # 用于通知所有线程休息

def create_driver():
    """为每个线程创建独立的WebDriver实例"""
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    this_ua = random.choice(USER_AGENT_LIST)
    options.add_argument(f'user-agent={this_ua}')
    # 【关键修改】把无头模式注释掉！无头模式容易被识别为机器人
    # options.add_argument('--headless')
    # 禁止加载图片（保留！这个省资源且不容易被封）
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.javascript": 1,
    }
    options.add_experimental_option("prefs", prefs)
    service = Service(r"I:\\chromedriver-win64\\chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# 保留主线程的driver（用于单线程模式）
options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument(f'user-agent={random.choice(USER_AGENT_LIST)}')
# 【关键修改】把无头模式注释掉！无头模式容易被识别为机器人
# options.add_argument('--headless')
# 禁止加载图片（保留！这个省资源且不容易被封）
prefs = {
    "profile.managed_default_content_settings.images": 2,
    "profile.managed_default_content_settings.javascript": 1,
}
options.add_experimental_option("prefs", prefs)
service = Service(r"I:\\chromedriver-win64\\chromedriver.exe")
driver = webdriver.Chrome(service=service, options=options)

try:
    if GROUP_TOTAL == 6 and 0 <= GROUP_INDEX < 6:
        col = GROUP_INDEX % 3
        row = GROUP_INDEX // 3
        width, height = 640, 540
        x = col * width
        y = row * height
        driver.set_window_position(x, y)
        driver.set_window_size(width, height)
except Exception:
    pass

page_request_count = 0
captcha_trigger_count = 0
auto_throttle_enabled = False
pages_since_throttle = 0
human_mode = False

def increment_page_count():
    """增加全局页面计数，如果超过限制则触发休息"""
    global global_page_count
    with page_count_lock:
        global_page_count += 1
        current_count = global_page_count
        print(f"[全局计数] 已爬取 {current_count} 页")
        
        if current_count > MAX_PAGES_BEFORE_REST:
            print(f"[休息触发] 5个线程总共已爬取 {current_count} 页，超过 {MAX_PAGES_BEFORE_REST} 页，触发休息 {REST_SECONDS} 秒")
            rest_event.set()  # 通知所有线程休息
            global_page_count = 0  # 重置计数器
            return True
    return False

def wait_for_rest_if_needed():
    """如果休息事件被触发，等待休息时间"""
    if rest_event.is_set():
        print(f"[休息中] 等待 {REST_SECONDS} 秒...")
        time.sleep(REST_SECONDS)
        rest_event.clear()  # 清除休息事件
        print(f"[休息完成] 继续爬取...")

def load_existing_posts(csv_file):
    existing_rows = []
    seen_keys = set()
    seen_post_ids = set()  # CHANGED: 使用post_id作为主要去重标识
    original_fieldnames = []
    if csv_file.exists():
        with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            original_fieldnames = list(reader.fieldnames or [])
            for row in reader:
                # 优先使用post_id去重，如果没有post_id则使用标题+时间
                post_id = row.get("post_id", "").strip()
                if post_id:
                    seen_post_ids.add(post_id)
                else:
                    key = (
                        row.get("post_title", ""),
                        row.get("post_publish_time", ""),
                        row.get("post_last_time", ""),
                    )
                    seen_keys.add(key)
                existing_rows.append(row)
    return existing_rows, seen_keys, seen_post_ids, original_fieldnames

def update_existing_posts_with_content(csv_file, target_bar_code):
    """更新已有CSV文件中缺少内容的帖子"""
    existing_rows = []
    seen_keys = set()
    posts_to_fetch = []
    original_fieldnames = []
    
    if csv_file.exists():
        with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            original_fieldnames = list(reader.fieldnames or [])
            
            for row in reader:
                key = (
                    row.get("post_title", ""),
                    row.get("post_publish_time", ""),
                    row.get("post_last_time", ""),
                )
                
                # 确保所有字段都存在（兼容旧格式）
                if "post_id" not in row:
                    row["post_id"] = ""
                if "post_content" not in row:
                    row["post_content"] = ""
                if "post_comments" not in row:
                    row["post_comments"] = ""  # CHANGED: 确保评论字段存在
                if "post_title" not in row:
                    row["post_title"] = ""  # CHANGED: 确保标题字段存在
                
                existing_rows.append(row)
                seen_keys.add(key)
                
                # 检查是否需要补充内容
                post_id = row.get("post_id", "")
                post_content = row.get("post_content", "")
                
                # 如果没有post_id，尝试从其他字段推断
                if not post_id:
                    # 尝试从URL或其他字段提取
                    post_url = row.get("post_url", "") or row.get("url", "")
                    if post_url:
                        match = re.search(r'news,[^,]+,(.+?)\.html', post_url)
                        if match:
                            post_id = match.group(1)
                            row["post_id"] = post_id
                
                if post_id and (not post_content or len(post_content.strip()) == 0):
                    posts_to_fetch.append((len(existing_rows) - 1, post_id, row.get("post_title", "")))
    
    return existing_rows, seen_keys, posts_to_fetch, original_fieldnames

def vify():
    """验证函数（暂未使用）"""
    try:
        driver.find_element(By.ID, "login")
    except:
        pass
    return

def fetch_page_posts(list_url: str, thread_driver=None):
    global page_request_count
    
    # 兼容处理：如果传入了 thread_driver 就用它，否则用全局 driver
    local_driver = thread_driver if thread_driver is not None else driver

    page_request_count += 1
    
    # 随机延迟，模拟真人操作（你之前的改动）
    time.sleep(random.uniform(2, 4))
    
    try:
        local_driver.get(list_url)
        print(f"  已打开页面: {list_url}")
    except Exception as e:
        print(f"  页面加载失败: {e}")
        return []

    posts = []
    
    # ---------------------------------------------------------
    # 策略一：尝试用"所见即所得"法（Selenium DOM解析）—— 推荐现在用这个
    # ---------------------------------------------------------
    try:
        # 东方财富股吧列表通常长这样：class="article-h"
        # 我们查找所有的帖子行
        elements = local_driver.find_elements(By.CSS_SELECTOR, ".article-h")
        
        # 如果没找到 .article-h，可能是新版界面，尝试 .listitem 或 tr
        if not elements:
            elements = local_driver.find_elements(By.CSS_SELECTOR, ".listitem, tr.list-item")
            
        if elements:
            print(f"  [DOM解析] 页面上直观发现了 {len(elements)} 条帖子，开始提取...")
            for elem in elements:
                try:
                    # 提取阅读量 (l1)
                    try:
                        read_count = elem.find_element(By.CSS_SELECTOR, ".l1").text.strip()
                    except:
                        read_count = "0"
                        
                    # 提取评论量 (l2)
                    try:
                        comment_count = elem.find_element(By.CSS_SELECTOR, ".l2").text.strip()
                    except:
                        comment_count = "0"
                        
                    # 提取标题和链接 (l3 > a)
                    try:
                        title_elm = elem.find_element(By.CSS_SELECTOR, ".l3 a")
                        title = title_elm.text.strip()
                        href = title_elm.get_attribute("href")
                        
                        # 提取帖子ID
                        post_id = ""
                        if href:
                            # 尝试从URL提取ID: news,code,id.html
                            match = re.search(r'news,.*?,(.+?)\.html', href)
                            if match:
                                post_id = match.group(1)
                    except:
                        continue # 没有标题的行直接跳过
                        
                    # 提取时间 (l5)
                    try:
                        publish_time = elem.find_element(By.CSS_SELECTOR, ".l5").text.strip()
                    except:
                        publish_time = ""

                    # 排除置顶帖/广告（通常没有阅读量或者格式不对）
                    if "广告" in title:
                        continue

                    # 构造数据包
                    posts.append({
                        "post_id": post_id,
                        "post_title": title,
                        "post_click_count": read_count,
                        "post_comment_count": comment_count,
                        "post_publish_time": publish_time,
                        "post_last_time": publish_time, # 列表页通常只有发布时间或最后回复时间，暂且混用
                        "post_url": href,
                        "stockbar_code": "", # 外层会补全
                        "stockbar_name": ""  # 外层会补全
                    })
                except Exception as inner_e:
                    continue # 单行解析失败不影响整体
            
            if len(posts) > 0:
                print(f"  [DOM解析] 成功提取到 {len(posts)} 条数据，直接返回！")
                return posts
    except Exception as e:
        print(f"  [DOM解析] 尝试失败: {e}")

    # ---------------------------------------------------------
    # 策略二：如果上面失败了，再试原来的正则（作为备用）
    # ---------------------------------------------------------
    print("  [DOM解析] 未获取到数据，尝试使用正则提取隐藏变量...")
    html = local_driver.page_source
    pattern = re.compile(r"article_list\s*=\s*({[\s\S]*?});", re.S)
    m = pattern.search(html)
    
    if m:
        try:
            json_str = m.group(1)
            data = json.loads(json_str)
            raw_posts = data.get('re') or []
            print(f"  [正则解析] 成功提取 {len(raw_posts)} 条数据")
            return raw_posts
        except:
            pass
            
    print("  警告：该页面既无法通过DOM解析，也无法通过正则提取，跳过。")
    return []


def clean_post_content(content: str) -> str:
    """
    清洗帖子内容，移除无关信息
    
    移除的内容包括：
    - 导航栏和页面结构元素
    - 广告和推荐内容
    - 声明和提示信息
    - 无关的链接和按钮文本
    """
    if not content:
        return ""
    
    # 需要移除的无关内容模式（按优先级排序）
    patterns_to_remove = [
        # 导航栏和页面结构
        r'^东方财富网.*?股吧首页.*?基金吧.*?话题.*?问董秘.*?人气榜',
        r'^您好，欢迎来股吧！.*?登录/注册',
        r'^股吧搜索.*?热搜：',
        r'^最近访问:',
        r'^返回.*?吧$',
        r'^社区.*?吧帖子正文$',
        r'^来自.*?\d+.*?\d+.*?收藏.*?分享到：',
        r'^炒股第一步，先开个股票账户$',
        r'\$.*?\([A-Z]{2}\d{6}\)\$',  # 股票代码格式 $深振业Ａ(SZ000006)$
        r'^本文提到：.*?$',
        r'^举报$',
        r'^郑重声明：.*?风险自担',
        r'^请勿相信.*?谨防上当受骗',
        r'^网友评论.*?人评论$',
        r'^登录.*?注册.*?表情.*?添加图片.*?清除.*?发布$',
        r'^温馨提示：.*?《.*?》',
        r'^全部评论\(\d+\)$',
        r'^只看作者.*?最新$',
        r'^行情.*?资金流向.*?详情$',
        r'^净超大.*?净大单.*?净中单.*?净小单$',
        r'^智能点评.*?龙虎榜单.*?限售解禁',
        r'^融资融券.*?高管持股.*?大宗交易',
        r'^机构持仓.*?股权质押.*?并购重组',
        r'^股票回购.*?公司投资.*?股东分析',
        r'^最新业绩.*?研报公告.*?条件选股',
        r'^多空看盘.*?看涨.*?看跌$',
        r'^所属板块.*?%',
        r'^该吧人气用户.*?换一换$',
        r'^关注.*?粉丝.*?条相关讨论$',
        r'^关注该股的股友还关注$',
        r'^股吧热榜.*?个股话题.*?资讯文章$',
        r'^股票名称.*?人气排名.*?较昨日变动$',
        r'^第\d+名.*?持平.*?↑.*?↓',
        r'^查看更多.*?刷新.*?反馈$',
        r'^大盘星图.*?一览市场行情.*?全屏$',
        r'^分时.*?日K.*?周K.*?月K$',
        r'^行情.*?资金.*?人气$',
        r'^大盘.*?上证指数.*?深证成指.*?沪深300',
        r'^中小100.*?创业板指',
        r'^分时日K周K月K$',
        
        # 常见的页面元素
        r'^收藏.*?分享$',
        r'^点赞.*?评论$',
        r'^回复.*?楼$',
        r'^转发$',
        r'^举报.*?删除$',
        
        # 时间和位置信息（保留在内容中的，但移除单独的时间行）
        r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s*$',  # 单独的时间行
        r'^来自\s+.*?\s*$',  # 单独的"来自XX"行
        
        # 评论相关
        r'^\d+人评论$',
        r'^评论$',
        r'^点赞$',
    ]
    
    # 逐行处理，移除包含无关内容的行
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        original_line = line
        line = line.strip()
        
        # 跳过空行（稍后统一处理）
        if not line:
            continue
        
        # 检查是否包含需要移除的内容
        should_remove = False
        for pattern in patterns_to_remove:
            if re.search(pattern, line, re.IGNORECASE):
                should_remove = True
                break
        
        # 跳过太短的行（可能是导航元素）
        if len(line) < 3:
            should_remove = True
        
        # 跳过只包含数字、符号或单个字符的行（但保留可能是有意义的内容）
        if len(line) <= 2 and re.match(r'^[\d\s\-\+\%\$\#\@\*\(\)\[\]\.\,\:\;]+$', line):
            should_remove = True
        
        # 跳过只包含百分比、数字和符号的行（可能是行情数据）
        if re.match(r'^[\d\.\-\+\%\s]+$', line) and len(line) < 20:
            should_remove = True
        
        # 跳过包含多个连续特殊字符的行
        if re.search(r'[\.\,\:\;\-\+\%\$\#\@\*\(\)\[\]]{3,}', line):
            should_remove = True
        
        if not should_remove:
            cleaned_lines.append(line)
    
    # 重新组合内容
    cleaned_content = '\n'.join(cleaned_lines)
    
    # 移除股票代码格式（在行中出现的）
    cleaned_content = re.sub(r'\$[^$]+\$', '', cleaned_content)
    
    # 最终清理：移除多余的空白字符
    cleaned_content = re.sub(r'[ \t]+', ' ', cleaned_content)  # 多个空格/制表符替换为单个空格
    cleaned_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_content)  # 多个换行替换为两个
    cleaned_content = cleaned_content.strip()
    
    return cleaned_content


def fetch_post_comments(post_id: str, stockbar_code: str, thread_driver=None) -> str:
    """
    爬取帖子的评论内容
    
    Returns:
        评论内容（多条评论用换行分隔）
    """
    global page_request_count
    local_driver = thread_driver if thread_driver is not None else driver
    
    post_url = f"https://guba.eastmoney.com/news,{stockbar_code},{post_id}.html"
    
    try:
        # 如果已经打开了这个页面，就不需要重新加载
        if local_driver.current_url != post_url:
            local_driver.get(post_url)
            time.sleep(2)  # 等待页面加载
        
        comments = []
        html = local_driver.page_source
        
        # 方法1: 尝试使用Selenium选择器提取评论
        try:
            # 尝试多种评论选择器
            comment_selectors = [
                "div.comment-item",
                "div.comment",
                "div.reply-item",
                "div.reply",
                "[class*='comment']",
                "[class*='reply']",
                "[id*='comment']",
                "[id*='reply']",
            ]
            
            for selector in comment_selectors:
                try:
                    elements = local_driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        for elem in elements:
                            try:
                                text = elem.text.strip()
                                # 过滤掉太短或太长的（可能是导航元素）
                                if 10 < len(text) < 5000:
                                    # 检查是否包含常见的中文词汇（更可能是评论）
                                    if re.search(r'[\u4e00-\u9fa5]{3,}', text):
                                        # 清洗评论内容
                                        cleaned_comment = clean_post_content(text)
                                        if cleaned_comment:
                                            comments.append(cleaned_comment)
                            except:
                                continue
                        if comments:
                            break
                except:
                    continue
        except Exception as e:
            print(f"    CSS选择器提取评论时出错: {e}")
        
        # 方法2: 如果Selenium没找到，尝试用正则表达式从HTML中提取
        if not comments:
            try:
                # 尝试匹配评论区域的HTML
                comment_patterns = [
                    r'<div[^>]*class="[^"]*comment[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="[^"]*reply[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*id="[^"]*comment[^"]*"[^>]*>(.*?)</div>',
                ]
                
                for pattern_str in comment_patterns:
                    pattern = re.compile(pattern_str, re.S | re.I)
                    matches = pattern.findall(html)
                    if matches:
                        for match in matches:
                            # 移除HTML标签
                            text = re.sub(r'<[^>]+>', '', match).strip()
                            # 移除script和style标签内容
                            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.S | re.I)
                            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S | re.I)
                            text = text.strip()
                            
                            if 10 < len(text) < 5000 and re.search(r'[\u4e00-\u9fa5]{3,}', text):
                                cleaned_comment = clean_post_content(text)
                                if cleaned_comment:
                                    comments.append(cleaned_comment)
                        if comments:
                            break
            except Exception as e:
                print(f"    正则提取评论时出错: {e}")
        
        # 去重并合并评论
        unique_comments = []
        seen = set()
        for comment in comments:
            # 使用前50个字符作为去重键
            key = comment[:50].strip()
            if key and key not in seen:
                seen.add(key)
                unique_comments.append(comment)
        
        result = '\n\n---\n\n'.join(unique_comments) if unique_comments else ""
        
        if result:
            print(f"    成功获取评论，共 {len(unique_comments)} 条")
        else:
            print(f"    未找到评论内容")
        
        return result
        
    except Exception as e:
        print(f"    获取评论时出错: {e}")
        return ""


def fetch_post_content(post_id: str, stockbar_code: str, thread_driver=None):
    """
    爬取单个帖子的正文内容和评论
    
    Args:
        post_id: 帖子ID
        stockbar_code: 股票代码
        thread_driver: 线程专用的WebDriver实例（如果为None则使用全局driver）
    """
    global page_request_count, captcha_trigger_count
    
    # CHANGED: 使用线程专用的driver或全局driver
    local_driver = thread_driver if thread_driver is not None else driver
    
    post_url = f"https://guba.eastmoney.com/news,{stockbar_code},{post_id}.html"
    page_request_count += 1
    
    try:
        # 模拟用户点击进入详情的停顿
        time.sleep(random.uniform(1.5, 3.5))
        local_driver.get(post_url)
        print(f"    正在获取帖子内容: {post_url}")
        
        # 等待页面加载
        time.sleep(3)  # 增加等待时间确保页面完全加载
        
        content = ""
        html = local_driver.page_source
        
        # 方法1: 尝试从页面源码中提取正文（更可靠）
        # 东方财富股吧的帖子正文通常在特定的div中
        try:
            # 尝试多种正则表达式模式匹配正文区域
            patterns = [
                # 匹配包含stockcodec类的div
                r'<div[^>]*class="[^"]*stockcodec[^"]*"[^>]*>(.*?)</div>',
                # 匹配id为articlecontent的div
                r'<div[^>]*id="articlecontent"[^>]*>(.*?)</div>',
                # 匹配class包含article的div
                r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
                # 匹配class包含content的div
                r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
                # 尝试匹配正文区域（更通用的模式）
                r'<div[^>]*class="[^"]*post[^"]*content[^"]*"[^>]*>(.*?)</div>',
            ]
            
            for pattern_str in patterns:
                pattern = re.compile(pattern_str, re.S | re.I)
                matches = pattern.findall(html)
                if matches:
                    # 取最长的匹配（通常是正文）
                    for match in matches:
                        text = re.sub(r'<[^>]+>', '', match).strip()
                        # 移除script和style标签内容
                        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.S | re.I)
                        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S | re.I)
                        text = text.strip()
                        if len(text) > len(content):
                            content = text
                    if content:
                        break
        
        except Exception as e:
            print(f"    正则提取时出错: {e}")
        
        # 方法2: 如果正则没找到，尝试使用Selenium选择器
        if not content or len(content) < 50:
            try:
                selectors = [
                    "div.stockcodec",
                    "div#articlecontent",
                    "div.article",
                    "div.content",
                    "[class*='stockcodec']",
                    "[id*='article']",
                    "[class*='article']",
                ]
                
                for selector in selectors:
                    try:
                        elements = local_driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            text = elem.text.strip()
                            if len(text) > len(content) and len(text) > 50:
                                content = text
                                break
                        if content and len(content) > 50:
                            break
                    except:
                        continue
            except Exception as e:
                print(f"    CSS选择器提取时出错: {e}")
        
        # 方法3: 如果还是没找到，尝试查找包含大量文本的div
        if not content or len(content) < 50:
            try:
                # 查找所有div，选择文本最长的
                all_divs = local_driver.find_elements(By.TAG_NAME, "div")
                for div in all_divs:
                    try:
                        text = div.text.strip()
                        # 过滤掉太短或太长的（可能是导航栏等）
                        if 100 < len(text) < 50000 and len(text) > len(content):
                            # 检查是否包含常见的中文词汇（更可能是正文）
                            if re.search(r'[\u4e00-\u9fa5]{10,}', text):
                                content = text
                    except:
                        continue
            except Exception as e:
                print(f"    查找div时出错: {e}")
        
        if content:
            # CHANGED: 使用清洗函数清理内容，移除导航栏、广告、声明等无关信息
            content = clean_post_content(content)
            print(f"    成功获取帖子内容，清洗后长度: {len(content)} 字符")
        else:
            print(f"    警告: 未能提取到帖子内容，尝试保存页面源码用于调试...")
            # 保存页面源码用于调试
            debug_file = DATA_DIR / f"debug_post_{post_id}.html"
            try:
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"    已保存页面源码到: {debug_file}")
            except:
                pass
        
        # CHANGED: 同时获取评论内容
        comments = fetch_post_comments(post_id, stockbar_code, local_driver)
        
        # 返回内容和评论的元组
        return content, comments
        
    except Exception as e:
        print(f"    访问帖子详情页时出错: {e}")
        traceback.print_exc()
        return "", ""  # CHANGED: 返回元组（内容，评论）


def maybe_global_throttle():
    global pages_since_throttle, auto_throttle_enabled, human_mode

    if not auto_throttle_enabled or human_mode:
        return

    pages_since_throttle += 1
    THROTTLE_PAGES_HARD = 99
    COOLDOWN_SECONDS = THROTTLE_SLEEP_SECONDS if THROTTLE_SLEEP_SECONDS > 0 else 300

    if pages_since_throttle < THROTTLE_PAGES_HARD:
        return

    pages_since_throttle = 0

    if COOLDOWN_SECONDS <= 0:
        return

    print(f"  [节流] 自首次风控解除以来，已成功抓取 {THROTTLE_PAGES_HARD} 个列表页，计划休息 {COOLDOWN_SECONDS} 秒以降低风险...")
    print("  若你在旁边且希望进入\"有人状态\"（不再自动 99+300 节流），可在等待期间在控制台按回车；否则将自动完成本次等待。")

    start_sleep = time.time()
    last_report = -1
    try:
        while True:
            elapsed = time.time() - start_sleep
            remaining = int(COOLDOWN_SECONDS - elapsed)
            if remaining <= 0:
                print("  [节流] 本轮自动等待结束，继续抓取...")
                break

            if remaining != last_report and (remaining % 60 == 0 or remaining <= 10):
                print(f"  [节流] 剩余等待 {remaining} 秒...")
                last_report = remaining

            if msvcrt is not None and msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\r", b"\n"):
                    human_mode = True
                    print("  检测到回车，切换为\"有人状态\"，本轮等待提前结束，后续不再执行 99+300 自动节流。")
                    return

            time.sleep(1)
    except Exception:
        # 如果监听过程中出错，退回到简单 sleep，避免影响主体逻辑
        time.sleep(COOLDOWN_SECONDS)


all_posts = []

try:
    # CHANGED: 获取人气榜前300名股票
    print("=" * 50)
    print("开始获取东方财富人气榜前300名股票...")
    stock_codes = get_popular_stocks_from_guba(driver, limit=300)
    
    # 如果获取失败，使用tushare作为备选
    if not stock_codes or len(stock_codes) < 50:
        print("从人气榜获取股票数量不足，使用tushare作为备选...")
        ts.set_token("c32d8386d48a5c9e453add46d222912cdf866b3026950cba05c8b90b")
        pro = ts.pro_api()
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
        df["code_fmt"] = df["ts_code"].str.replace(
            r"(\d+)\.(\w+)", 
            lambda m: m.group(2).lower() + m.group(1),
            regex=True
        )
        tushare_codes = df["code_fmt"].tolist()[:300]
        stock_codes = tushare_codes
        print(f"使用tushare获取了 {len(stock_codes)} 只股票")
    
    print(f"总共将爬取 {len(stock_codes)} 只股票")
    
    # CHANGED: 添加板块爬取
    print("=" * 50)
    print("开始爬取板块数据...")
    plate_items = list(PLATE_CODES.items())
    print(f"将爬取 {len(plate_items)} 个板块: {', '.join([name for name, _ in plate_items])}")

    if GROUP_TOTAL > 1:
        if GROUP_INDEX < 0 or GROUP_INDEX >= GROUP_TOTAL:
            raise ValueError("group-index must be in [0, group-total-1]")
        stock_codes = stock_codes[GROUP_INDEX::GROUP_TOTAL]
        print(f"分组参数: group_index={GROUP_INDEX}, group_total={GROUP_TOTAL}，本进程负责 {len(stock_codes)} 只股票")

    start_page = 1
    end_page = 10  # 增加到10页，减少新帖子对结果的影响

    # CHANGED: 先爬取板块数据
    print("=" * 50)
    print("开始爬取板块数据...")
    plate_items = list(PLATE_CODES.items())
    print(f"将爬取 {len(plate_items)} 个板块: {', '.join([name for name, _ in plate_items])}")
    
    for plate_name, plate_code in plate_items:
        print("=" * 50)
        print(f"开始爬取板块: {plate_name} ({plate_code})")
        
        csv_file = DATA_DIR / f"plate_{plate_code}_posts.csv"
        
        # 如果文件存在且不是更新模式，跳过
        if csv_file.exists() and not UPDATE_EXISTING and not UPDATE_ALL:
            print(f"检测到已有数据文件 {csv_file}，跳过该板块以避免重复爬取。")
            continue
        
        # 如果是全量更新模式，删除旧文件
        if csv_file.exists() and UPDATE_ALL:
            csv_file.unlink()
            print(f"  已删除旧文件，将重新爬取所有数据")
        
        code_posts = []
        base_url = f"https://guba.eastmoney.com/list,{plate_code}.html"
        
        # 使用多线程爬取列表页
        def fetch_page_worker(page_num):
            """线程工作函数：爬取单个列表页"""
            thread_driver = create_driver()
            try:
                if page_num == 1:
                    list_url = base_url
                else:
                    list_url = f"https://guba.eastmoney.com/list,{plate_code}_{page_num}.html"
                
                print(f"[线程 {threading.current_thread().name}] 开始抓取第 {page_num} 页: {list_url}")
                page_posts = fetch_page_posts(list_url, thread_driver)
                print(f"[线程 {threading.current_thread().name}] 第 {page_num} 页完成，获取 {len(page_posts)} 条帖子")
                return page_num, page_posts
            except Exception as e:
                print(f"[线程 {threading.current_thread().name}] 第 {page_num} 页出错: {e}")
                return page_num, []
            finally:
                try:
                    thread_driver.quit()
                except:
                    pass
        
        # 使用线程池爬取所有页面
        pages_to_fetch = list(range(start_page, end_page + 1))
        page_results = {}
        
        with ThreadPoolExecutor(max_workers=NUM_THREADS, thread_name_prefix="PlateCrawler") as executor:
            future_to_page = {executor.submit(fetch_page_worker, page): page for page in pages_to_fetch}
            
            for future in as_completed(future_to_page):
                page_num, page_posts = future.result()
                page_results[page_num] = page_posts
        
        # 按页面顺序合并结果
        for page_num in sorted(page_results.keys()):
            code_posts.extend(page_results[page_num])
        
        # 过滤该板块的帖子
        code_posts = [
            p for p in code_posts
            if p.get("stockbar_code") == plate_code or plate_code in str(p.get("stockbar_code", ""))
        ]
        
        code_posts.sort(key=lambda p: p.get("post_publish_time", ""), reverse=True)
        
        print(f"板块 {plate_name} 过滤后剩余 {len(code_posts)} 条帖子")
        
        # 保存板块数据（简化处理，不爬取内容，只保存列表页数据）
        fieldnames = [
            "stockbar_code",
            "stockbar_name",
            "post_id",
            "post_title",
            "post_content",
            "post_comments",
            "post_click_count",
            "post_comment_count",
            "post_forward_count",
            "post_publish_time",
            "post_last_time",
            "post_has_pic",
            "post_has_video",
            "bullish_bearish",
            "crawl_time",  # CHANGED: 添加爬取时间戳字段
        ]
        
        existing_rows, seen_keys, seen_post_ids, original_fieldnames = load_existing_posts(csv_file)
        
        # 添加爬取时间戳
        crawl_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for post in code_posts:
            # 优先提取post_id
            post_id = (post.get("post_id") or post.get("id") or 
                      post.get("article_id") or post.get("postid") or "")
            
            if not post_id:
                post_url = post.get("post_url", "") or post.get("url", "")
                if post_url:
                    match = re.search(r'news,[^,]+,(.+?)\.html', post_url)
                    if match:
                        post_id = match.group(1)
            
            # CHANGED: 优先使用post_id去重，更可靠
            if post_id and post_id in seen_post_ids and not UPDATE_ALL:
                continue
            
            # 如果没有post_id，使用标题+时间作为备用去重方式
            if not post_id:
                key = (
                    post.get("post_title", ""),
                    post.get("post_publish_time", ""),
                    post.get("post_last_time", ""),
                )
                if key in seen_keys and not UPDATE_ALL:
                    continue
                seen_keys.add(key)
            else:
                seen_post_ids.add(post_id)
            
            row = {
                "stockbar_code": plate_code,
                "stockbar_name": plate_name,
                "post_id": post_id,
                "post_title": post.get("post_title", ""),
                "post_content": "",
                "post_comments": "",
                "post_click_count": post.get("post_click_count", ""),
                "post_comment_count": post.get("post_comment_count", ""),
                "post_forward_count": post.get("post_forward_count", ""),
                "post_publish_time": post.get("post_publish_time", ""),
                "post_last_time": post.get("post_last_time", ""),
                "post_has_pic": post.get("post_has_pic", ""),
                "post_has_video": post.get("post_has_video", ""),
                "bullish_bearish": post.get("bullish_bearish", ""),
                "crawl_time": crawl_time,  # CHANGED: 添加爬取时间戳
            }
            
            existing_rows.append(row)
        
        existing_rows.sort(key=lambda r: r.get("post_publish_time", ""), reverse=True)
        
        if original_fieldnames:
            merged_fieldnames = []
            seen = set()
            for field in original_fieldnames:
                if field not in seen:
                    merged_fieldnames.append(field)
                    seen.add(field)
            for field in fieldnames:
                if field not in seen:
                    merged_fieldnames.append(field)
                    seen.add(field)
            fieldnames = merged_fieldnames
        
        with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in existing_rows:
                writer.writerow(row)
        
        print(f"已将板块 {plate_name} 的数据写入 {csv_file}，共 {len(existing_rows)} 条记录。")
    
    # CHANGED: 然后爬取股票数据
    print("=" * 50)
    print("开始爬取股票数据...")
    
    for stock_code in stock_codes:
        target_bar_code = stock_code[-6:]
        csv_file = DATA_DIR / f"{stock_code}_posts.csv"
        
        # 如果文件存在且不是更新模式，跳过
        if csv_file.exists() and not UPDATE_EXISTING and not UPDATE_ALL:
            print(f"检测到已有数据文件 {csv_file}，跳过该股票以避免重复爬取。")
            print("  提示: 使用 --update-existing 参数可以更新已有文件的内容")
            print("  提示: 使用 --update-all 参数可以全量更新所有数据")
            continue
        
        # 如果是全量更新模式，重新爬取所有数据
        if csv_file.exists() and UPDATE_ALL:
            print(f"检测到已有数据文件 {csv_file}，启用全量更新模式，将重新爬取所有数据...")
            # 删除旧文件，重新爬取
            csv_file.unlink()
            print(f"  已删除旧文件，将重新爬取所有数据")
        
        # 如果是更新模式，检查是否需要补充内容
        if csv_file.exists() and UPDATE_EXISTING and not UPDATE_ALL:
            existing_rows, seen_keys, posts_to_fetch, original_fieldnames = update_existing_posts_with_content(csv_file, target_bar_code)
            
            # 如果没有post_id，需要从列表页重新获取
            posts_without_id = [i for i, row in enumerate(existing_rows) if not row.get("post_id", "").strip()]
            if posts_without_id:
                print(f"检测到已有数据文件 {csv_file}，发现 {len(posts_without_id)} 条帖子缺少post_id，需要从列表页重新获取...")
                # 重新爬取列表页获取post_id
                base_url = f"https://guba.eastmoney.com/list,{target_bar_code}.html"
                print(f"  正在访问列表页获取帖子ID: {base_url}")
                page_posts = fetch_page_posts(base_url)
                
                # 建立标题到post_id的映射
                title_to_id = {}
                for p in page_posts:
                    if p.get("stockbar_code") == target_bar_code:
                        title = p.get("post_title", "")
                        post_id = (p.get("post_id") or p.get("id") or 
                                  p.get("article_id") or p.get("postid") or "")
                        if title and post_id:
                            title_to_id[title] = post_id
                
                # 更新缺少post_id的行
                updated_count = 0
                for row_idx in posts_without_id:
                    row = existing_rows[row_idx]
                    title = row.get("post_title", "")
                    if title in title_to_id:
                        row["post_id"] = title_to_id[title]
                        updated_count += 1
                        # 如果这个帖子也缺少内容，添加到待爬取列表
                        if not row.get("post_content", "").strip():
                            posts_to_fetch.append((row_idx, row["post_id"], title))
                
                print(f"  成功更新了 {updated_count} 条帖子的post_id")
                # 重新检查哪些帖子需要爬取内容
                if not posts_to_fetch:
                    posts_to_fetch = [
                        (i, row.get("post_id", ""), row.get("post_title", ""))
                        for i, row in enumerate(existing_rows)
                        if row.get("post_id", "") and not row.get("post_content", "").strip()
                    ]
            
            if posts_to_fetch:
                print(f"检测到已有数据文件 {csv_file}，发现 {len(posts_to_fetch)} 条帖子缺少内容，开始补充...")
                # 更新模式下自动启用内容爬取
                if not FETCH_CONTENT:
                    print("  提示: --update-existing 模式下自动启用内容爬取")
                
                for idx, (row_idx, post_id, post_title) in enumerate(posts_to_fetch, 1):
                    print(f"  正在补充内容 [{idx}/{len(posts_to_fetch)}]: {post_title[:50]}...")
                    result = fetch_post_content(post_id, target_bar_code)
                    # CHANGED: 处理返回的元组（内容，评论）
                    if isinstance(result, tuple):
                        post_content, post_comments = result
                    else:
                        post_content = result
                        post_comments = ""
                    existing_rows[row_idx]["post_content"] = post_content
                    existing_rows[row_idx]["post_comments"] = post_comments
                    time.sleep(1)
                
                # 保存更新后的数据
                # 使用原有字段名，并确保包含必要的新字段
                base_fieldnames = [
                    "stockbar_code", "stockbar_name", "post_id", "post_title", "post_content", "post_comments",
                    "post_click_count", "post_comment_count", "post_forward_count",
                    "post_publish_time", "post_last_time", "post_has_pic", "post_has_video", "bullish_bearish",
                ]
                # 合并原有字段和新字段，保留原有字段的顺序，新字段追加到末尾
                fieldnames = []
                seen = set()
                # 先添加原有字段（如果存在）
                if original_fieldnames:
                    for field in original_fieldnames:
                        if field not in seen:
                            fieldnames.append(field)
                            seen.add(field)
                # 再添加新字段（如果不存在）
                for field in base_fieldnames:
                    if field not in seen:
                        fieldnames.append(field)
                        seen.add(field)
                
                with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in existing_rows:
                        writer.writerow(row)
                print(f"已更新 {csv_file}，补充了 {len(posts_to_fetch)} 条帖子的内容。")
                continue
            else:
                print(f"检测到已有数据文件 {csv_file}，所有帖子都已包含内容，跳过。")
                continue

        code_posts = []
        base_url = f"https://guba.eastmoney.com/list,{target_bar_code}.html"

        print("################################")
        print(f"开始抓取股票代码 {stock_code} 的帖子...")
        print(f"使用 {NUM_THREADS} 个线程进行爬取")

        # CHANGED: 使用多线程爬取列表页
        def fetch_page_worker(page_num):
            """线程工作函数：爬取单个列表页"""
            thread_driver = create_driver()
            try:
                if page_num == 1:
                    list_url = base_url
                else:
                    list_url = f"https://guba.eastmoney.com/list,{target_bar_code}_{page_num}.html"
                
                print(f"[线程 {threading.current_thread().name}] 开始抓取第 {page_num} 页: {list_url}")
                page_posts = fetch_page_posts(list_url, thread_driver)
                print(f"[线程 {threading.current_thread().name}] 第 {page_num} 页完成，获取 {len(page_posts)} 条帖子")
                return page_num, page_posts
            except Exception as e:
                print(f"[线程 {threading.current_thread().name}] 第 {page_num} 页出错: {e}")
                return page_num, []
            finally:
                try:
                    thread_driver.quit()
                except:
                    pass

        # 使用线程池爬取所有页面
        pages_to_fetch = list(range(start_page, end_page + 1))
        page_results = {}
        
        with ThreadPoolExecutor(max_workers=NUM_THREADS, thread_name_prefix="Crawler") as executor:
            future_to_page = {executor.submit(fetch_page_worker, page): page for page in pages_to_fetch}
            
            for future in as_completed(future_to_page):
                page_num, page_posts = future.result()
                page_results[page_num] = page_posts
        
        # 按页面顺序合并结果
        for page_num in sorted(page_results.keys()):
            code_posts.extend(page_results[page_num])

        print("==============================")
        code_posts = [
            p for p in code_posts
            if p.get("stockbar_code") == target_bar_code
        ]

        code_posts.sort(key=lambda p: p.get("post_publish_time", ""), reverse=True)

        print(f"股票代码 {stock_code} 过滤后剩余 {len(code_posts)} 条帖子，开始爬取帖子内容...")

        fieldnames = [
            "stockbar_code",
            "stockbar_name",
            "post_id",
            "post_title",
            "post_content",
            "post_comments",  # CHANGED: 添加评论字段
            "post_click_count",
            "post_comment_count",
            "post_forward_count",
            "post_publish_time",
            "post_last_time",
            "post_has_pic",
            "post_has_video",
            "bullish_bearish",
            "crawl_time",  # CHANGED: 添加爬取时间戳字段
        ]

        existing_rows, seen_keys, seen_post_ids, original_fieldnames = load_existing_posts(csv_file)
        
        # 添加爬取时间戳
        crawl_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for idx, post in enumerate(code_posts, 1):
            # 优先提取post_id
            post_id = (post.get("post_id") or post.get("id") or 
                      post.get("article_id") or post.get("postid") or "")
            
            if not post_id:
                post_url = post.get("post_url", "") or post.get("url", "")
                if post_url:
                    match = re.search(r'news,[^,]+,(.+?)\.html', post_url)
                    if match:
                        post_id = match.group(1)
            
            # CHANGED: 优先使用post_id去重，更可靠
            existing_row_idx = None
            if post_id:
                if post_id in seen_post_ids:
                    if not UPDATE_ALL:
                        print(f"  跳过已存在的帖子(通过ID) [{idx}/{len(code_posts)}]: {post.get('post_title', '')[:50]}...")
                        continue
                    # 查找对应的已有记录
                    for i, row in enumerate(existing_rows):
                        if row.get("post_id", "").strip() == post_id:
                            existing_row_idx = i
                            break
                    if existing_row_idx is not None:
                        print(f"  更新已有帖子(通过ID) [{idx}/{len(code_posts)}]: {post.get('post_title', '')[:50]}...")
                    else:
                        seen_post_ids.add(post_id)
                else:
                    seen_post_ids.add(post_id)
            else:
                # 如果没有post_id，使用标题+时间作为备用去重方式
                key = (
                    post.get("post_title", ""),
                    post.get("post_publish_time", ""),
                    post.get("post_last_time", ""),
                )
                if key in seen_keys:
                    if not UPDATE_ALL:
                        print(f"  跳过已存在的帖子(通过标题+时间) [{idx}/{len(code_posts)}]: {post.get('post_title', '')[:50]}...")
                        continue
                    # 查找对应的已有记录
                    for i, row in enumerate(existing_rows):
                        if (row.get("post_title", "") == post.get("post_title", "") and
                            row.get("post_publish_time", "") == post.get("post_publish_time", "") and
                            row.get("post_last_time", "") == post.get("post_last_time", "")):
                            existing_row_idx = i
                            break
                    if existing_row_idx is not None:
                        print(f"  更新已有帖子(通过标题+时间) [{idx}/{len(code_posts)}]: {post.get('post_title', '')[:50]}...")
                    else:
                        seen_keys.add(key)
                else:
                    seen_keys.add(key)
            
            # 爬取帖子内容
            post_content = ""
            post_comments = ""
            # 更新模式或显式启用时爬取内容
            should_fetch = FETCH_CONTENT or UPDATE_EXISTING
            if should_fetch:
                if post_id:
                    print(f"  正在爬取帖子 [{idx}/{len(code_posts)}]: {post.get('post_title', '')[:50]}...")
                    result = fetch_post_content(post_id, target_bar_code)
                    # CHANGED: 处理返回的元组（内容，评论）
                    if isinstance(result, tuple):
                        post_content, post_comments = result
                    else:
                        post_content = result
                        post_comments = ""
                    # 添加小延迟，避免请求过快
                    time.sleep(1)
                else:
                    print(f"  警告: 帖子缺少ID，跳过内容爬取: {post.get('post_title', '')[:50]}...")
            else:
                print(f"  跳过内容爬取 [{idx}/{len(code_posts)}] (未启用 --fetch-content): {post.get('post_title', '')[:50]}...")
            
            row = {
                "stockbar_code": post.get("stockbar_code", ""),
                "stockbar_name": post.get("stockbar_name", ""),
                "post_id": post_id,
                "post_title": post.get("post_title", ""),  # CHANGED: 确保标题被保存
                "post_content": post_content,
                "post_comments": post_comments,  # CHANGED: 添加评论字段
                "post_click_count": post.get("post_click_count", ""),
                "post_comment_count": post.get("post_comment_count", ""),
                "post_forward_count": post.get("post_forward_count", ""),
                "post_publish_time": post.get("post_publish_time", ""),
                "post_last_time": post.get("post_last_time", ""),
                "post_has_pic": post.get("post_has_pic", ""),
                "post_has_video": post.get("post_has_video", ""),
                "bullish_bearish": post.get("bullish_bearish", ""),
                "crawl_time": crawl_time,  # CHANGED: 添加爬取时间戳
            }
            
            # CHANGED: 如果是全量更新模式且记录已存在，更新已有记录；否则添加新记录
            if UPDATE_ALL and existing_row_idx is not None:
                # 更新已有记录的所有字段
                existing_rows[existing_row_idx].update(row)
            else:
                existing_rows.append(row)

        existing_rows.sort(key=lambda r: r.get("post_publish_time", ""), reverse=True)

        # 如果文件已存在，保留原有字段名，并添加新字段
        if original_fieldnames:
            # 合并原有字段和新字段
            merged_fieldnames = []
            seen = set()
            # 先添加原有字段（如果存在）
            for field in original_fieldnames:
                if field not in seen:
                    merged_fieldnames.append(field)
                    seen.add(field)
            # 再添加新字段（如果不存在）
            for field in fieldnames:
                if field not in seen:
                    merged_fieldnames.append(field)
                    seen.add(field)
            fieldnames = merged_fieldnames

        with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in existing_rows:
                writer.writerow(row)

        print(f"已将股票 {stock_code} 的数据写入 {csv_file}，共 {len(existing_rows)} 条记录。")

except Exception as e:
    print(f"抓取过程中出现错误: {e}")
    print(f"异常类型: {type(e)}")
    print("详细 traceback 如下:")
    traceback.print_exc()

finally:
    driver.quit()
    print("浏览器已关闭。")
    print(f"本次运行共访问列表页 {page_request_count} 次，疑似触发验证 {captcha_trigger_count} 次。")