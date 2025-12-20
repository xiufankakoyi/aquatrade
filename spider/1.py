from selenium import webdriver
from selenium.webdriver.chrome.service import Service

import traceback
import re
import json
import csv
import time
import argparse
try:
    import msvcrt
except ImportError:
    msvcrt = None

from pathlib import Path

#获取股票代码
import tushare as ts
import pandas as pd

ts.set_token("c32d8386d48a5c9e453add46d222912cdf866b3026950cba05c8b90b")
pro = ts.pro_api()
df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
df["code_fmt"] = df["ts_code"].str.replace(
    r"(\d+)\.(\w+)", 
    lambda m: m.group(2).lower() + m.group(1),
    regex=True
)

codes = df["code_fmt"].tolist()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

THROTTLE_PAGES_DEFAULT = 100
THROTTLE_SLEEP_SECONDS_DEFAULT = 300

parser = argparse.ArgumentParser()
parser.add_argument("--group-index", type=int, default=0)
parser.add_argument("--group-total", type=int, default=1)
parser.add_argument("--throttle-pages", type=int, default=THROTTLE_PAGES_DEFAULT)
parser.add_argument("--throttle-sleep", type=int, default=THROTTLE_SLEEP_SECONDS_DEFAULT)
args = parser.parse_args()

GROUP_INDEX = max(0, args.group_index)
GROUP_TOTAL = max(1, args.group_total)
THROTTLE_PAGES = max(1, args.throttle_pages)
THROTTLE_SLEEP_SECONDS = max(0, args.throttle_sleep)

options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('user-agent=Mozilla/5.0...')
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

def load_existing_posts(csv_file):
    existing_rows = []
    seen_keys = set()
    if csv_file.exists():
        with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (
                    row.get("post_title", ""),
                    row.get("post_publish_time", ""),
                    row.get("post_last_time", ""),
                )
                existing_rows.append(row)
                seen_keys.add(key)
    return existing_rows, seen_keys

def vify():
    driver.find_element_by_id("login")
    return

def fetch_page_posts(list_url: str):
    global page_request_count, captcha_trigger_count, auto_throttle_enabled, pages_since_throttle, human_mode

    page_request_count += 1
    prev_captcha_count = captcha_trigger_count
    driver.get(list_url)
    print(f"已打开页面: {list_url}，开始从 page_source 中提取 article_list...")
    print(f"  [统计] 本次运行已访问列表页次数: {page_request_count}")

    pattern = re.compile(r"article_list\s*=\s*({[\s\S]*?});", re.S)

    first_block = True
    poll_interval = 5
    human_wait_seconds = 301

    waited = 0

    while True:
        html = driver.page_source
        m = pattern.search(html)
        if m:
            break

        if first_block:
            captcha_trigger_count += 1
            print("  未匹配到 article_list 变量，可能触发了验证或页面尚未加载完成。")
            print(f"  [统计] 自脚本启动以来，疑似触发验证的次数: {captcha_trigger_count}")
            print(f"  [统计] 当前已访问列表页总次数: {page_request_count}")
            first_block = False
        else:
            print("  仍未匹配到 article_list 变量，可能验证未完成或页面尚未加载完成。")

        if waited < human_wait_seconds:
            remaining = max(0, human_wait_seconds - waited)
            print("  如果已经完成验证，请稍候，程序会每隔几秒自动重试当前页面...")
            print(f"  [验证窗口] 本轮最多等待约 {remaining} 秒...")
            time.sleep(poll_interval)
            waited += poll_interval
        else:
            print("  长时间未检测到 article_list，立即重新加载当前页面以重试...")
            driver.get(list_url)
            waited = 0
            first_block = True

    json_str = m.group(1)
    try:
        data = json.loads(json_str)
    except Exception as je:
        print("  解析 article_list JSON 失败:", je)
        return []

    posts = data.get('re') or []
    print(f"  在 article_list 中找到 {len(posts)} 条帖子记录。")

    # 如果本次调用中出现了新的验证码并最终恢复正常，说明刚刚完成一次风控解除
    if captcha_trigger_count > prev_captcha_count:
        auto_throttle_enabled = True
        pages_since_throttle = 0
        human_mode = False

    maybe_global_throttle()

    return posts


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
    stock_codes = codes

    if GROUP_TOTAL > 1:
        if GROUP_INDEX < 0 or GROUP_INDEX >= GROUP_TOTAL:
            raise ValueError("group-index must be in [0, group-total-1]")
        stock_codes = stock_codes[GROUP_INDEX::GROUP_TOTAL]
        print(f"分组参数: group_index={GROUP_INDEX}, group_total={GROUP_TOTAL}，本进程负责 {len(stock_codes)} 只股票")

    start_page = 1
    end_page = 3

    for stock_code in stock_codes:
        target_bar_code = stock_code[-6:]
        csv_file = DATA_DIR / f"{stock_code}_posts.csv"
        if csv_file.exists():
            print(f"检测到已有数据文件 {csv_file}，跳过该股票以避免重复爬取。")
            continue

        code_posts = []
        base_url = f"https://guba.eastmoney.com/list,{target_bar_code}.html"

        print("################################")
        print(f"开始抓取股票代码 {stock_code} 的帖子...")

        for page in range(start_page, end_page + 1):
            if page == 1:
                list_url = base_url
            else:
                list_url = f"https://guba.eastmoney.com/list,{target_bar_code}_{page}.html"

            print("==============================")
            print(f"开始抓取第 {page} 页: {list_url}")
            page_posts = fetch_page_posts(list_url)
            code_posts.extend(page_posts)

        print("==============================")
        code_posts = [
            p for p in code_posts
            if p.get("stockbar_code") == target_bar_code
        ]

        code_posts.sort(key=lambda p: p.get("post_publish_time", ""), reverse=True)

        print(f"股票代码 {stock_code} 过滤后剩余 {len(code_posts)} 条帖子，准备写入 CSV 文件...")

        fieldnames = [
            "stockbar_code",
            "stockbar_name",
            "post_title",
            "post_click_count",
            "post_comment_count",
            "post_forward_count",
            "post_publish_time",
            "post_last_time",
            "post_has_pic",
            "post_has_video",
            "bullish_bearish",
        ]

        existing_rows, seen_keys = load_existing_posts(csv_file)

        for post in code_posts:
            key = (
                post.get("post_title", ""),
                post.get("post_publish_time", ""),
                post.get("post_last_time", ""),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            row = {
                "stockbar_code": post.get("stockbar_code", ""),
                "stockbar_name": post.get("stockbar_name", ""),
                "post_title": post.get("post_title", ""),
                "post_click_count": post.get("post_click_count", ""),
                "post_comment_count": post.get("post_comment_count", ""),
                "post_forward_count": post.get("post_forward_count", ""),
                "post_publish_time": post.get("post_publish_time", ""),
                "post_last_time": post.get("post_last_time", ""),
                "post_has_pic": post.get("post_has_pic", ""),
                "post_has_video": post.get("post_has_video", ""),
                "bullish_bearish": post.get("bullish_bearish", ""),
            }
            existing_rows.append(row)

        existing_rows.sort(key=lambda r: r.get("post_publish_time", ""), reverse=True)

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