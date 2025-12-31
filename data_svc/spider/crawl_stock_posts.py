"""
爬取指定股票近一年来的所有帖子
用法: python crawl_stock_posts.py --stock-code 000592 --months 12
"""

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
import datetime
import argparse
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# User-Agent列表
USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# 配置
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 解析命令行参数
parser = argparse.ArgumentParser(description="爬取指定股票近一年来的所有帖子")
parser.add_argument("--stock-code", type=str, required=True, help="股票代码，如 000592")
parser.add_argument("--months", type=int, default=12, help="爬取近N个月的帖子（默认12个月）")
parser.add_argument("--threads", type=int, default=5, help="爬取线程数（默认5个）")
parser.add_argument("--fetch-content", action="store_true", help="是否爬取帖子正文内容")
parser.add_argument("--max-pages", type=int, default=1000, help="最大爬取页数（默认1000页）")
parser.add_argument("--chromedriver-path", type=str, default=r"I:\chromedriver-win64\chromedriver.exe", help="ChromeDriver路径")
args = parser.parse_args()

STOCK_CODE = args.stock_code
MONTHS = args.months
NUM_THREADS = max(1, args.threads)
FETCH_CONTENT = args.fetch_content
MAX_PAGES = args.max_pages
CHROMEDRIVER_PATH = args.chromedriver_path

# 计算时间范围
end_date = datetime.datetime.now()
start_date = end_date - datetime.timedelta(days=MONTHS * 30)
print(f"时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")

def create_driver():
    """为每个线程创建独立的WebDriver实例"""
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    this_ua = random.choice(USER_AGENT_LIST)
    options.add_argument(f'user-agent={this_ua}')
    # 禁止加载图片（省资源且不容易被封）
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.javascript": 1,
    }
    options.add_experimental_option("prefs", prefs)
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def fetch_page_posts(list_url: str, thread_driver=None):
    """爬取列表页的帖子"""
    local_driver = thread_driver if thread_driver is not None else create_driver()
    
    # 随机延迟
    time.sleep(random.uniform(2, 4))
    
    try:
        local_driver.get(list_url)
        print(f"  已打开页面: {list_url}")
    except Exception as e:
        print(f"  页面加载失败: {e}")
        return []
    
    posts = []
    
    # 方法1: 使用Selenium DOM解析
    try:
        elements = local_driver.find_elements(By.CSS_SELECTOR, ".article-h")
        
        if not elements:
            elements = local_driver.find_elements(By.CSS_SELECTOR, ".listitem, tr.list-item")
        
        if elements:
            print(f"  [DOM解析] 页面上发现了 {len(elements)} 条帖子，开始提取...")
            for elem in elements:
                try:
                    # 提取阅读量
                    try:
                        read_count = elem.find_element(By.CSS_SELECTOR, ".l1").text.strip()
                    except:
                        read_count = "0"
                    
                    # 提取评论量
                    try:
                        comment_count = elem.find_element(By.CSS_SELECTOR, ".l2").text.strip()
                    except:
                        comment_count = "0"
                    
                    # 提取标题和链接
                    try:
                        title_elm = elem.find_element(By.CSS_SELECTOR, ".l3 a")
                        title = title_elm.text.strip()
                        href = title_elm.get_attribute("href")
                        
                        # 提取帖子ID
                        post_id = ""
                        if href:
                            match = re.search(r'news,.*?,(.+?)\.html', href)
                            if match:
                                post_id = match.group(1)
                    except:
                        continue
                    
                    # 提取时间
                    try:
                        publish_time = elem.find_element(By.CSS_SELECTOR, ".l5").text.strip()
                    except:
                        publish_time = ""
                    
                    # 排除广告
                    if "广告" in title:
                        continue
                    
                    posts.append({
                        "post_id": post_id,
                        "post_title": title,
                        "post_click_count": read_count,
                        "post_comment_count": comment_count,
                        "post_publish_time": publish_time,
                        "post_last_time": publish_time,
                        "post_url": href,
                        "stockbar_code": STOCK_CODE,
                        "stockbar_name": ""
                    })
                except Exception as inner_e:
                    continue
            
            if len(posts) > 0:
                print(f"  [DOM解析] 成功提取到 {len(posts)} 条数据")
                return posts
    except Exception as e:
        print(f"  [DOM解析] 尝试失败: {e}")
    
    # 方法2: 使用正则表达式提取
    print("  [DOM解析] 未获取到数据，尝试使用正则提取...")
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
    
    print("  警告：该页面无法提取数据，跳过。")
    return []

def clean_post_content(content: str) -> str:
    """清洗帖子内容"""
    if not content:
        return ""
    
    # 移除HTML标签
    content = re.sub(r'<[^>]+>', '', content)
    # 移除多余空白
    content = re.sub(r'\s+', ' ', content)
    return content.strip()

def fetch_post_content(post_id: str, stockbar_code: str, thread_driver=None):
    """爬取单个帖子的正文内容和评论"""
    local_driver = thread_driver if thread_driver is not None else create_driver()
    
    post_url = f"https://guba.eastmoney.com/news,{stockbar_code},{post_id}.html"
    
    try:
        time.sleep(random.uniform(1.5, 3.5))
        local_driver.get(post_url)
        print(f"    正在获取帖子内容: {post_url}")
        
        time.sleep(3)
        
        content = ""
        html = local_driver.page_source
        
        # 方法1: 使用Selenium选择器
        try:
            selectors = [
                "div.stockcodec",
                "div#articlecontent",
                "div.article",
                "[class*='stockcodec']",
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
        
        # 方法2: 使用正则表达式
        if not content or len(content) < 50:
            try:
                patterns = [
                    r'<div[^>]*class="[^"]*stockcodec[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*id="articlecontent"[^>]*>(.*?)</div>',
                ]
                
                for pattern_str in patterns:
                    pattern = re.compile(pattern_str, re.S | re.I)
                    matches = pattern.findall(html)
                    if matches:
                        for match in matches:
                            text = re.sub(r'<[^>]+>', '', match).strip()
                            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.S | re.I)
                            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S | re.I)
                            if len(text) > len(content):
                                content = text
                        if content:
                            break
            except Exception as e:
                print(f"    正则提取时出错: {e}")
        
        if content:
            content = clean_post_content(content)
            print(f"    成功获取帖子内容，长度: {len(content)} 字符")
        else:
            print(f"    警告: 未能提取到帖子内容")
        
        # 获取评论（简化处理）
        comments = ""
        
        return content, comments
        
    except Exception as e:
        print(f"    访问帖子详情页时出错: {e}")
        return "", ""

def parse_time(time_str):
    """解析时间字符串，返回datetime对象"""
    if not time_str:
        return None
    
    # 处理各种时间格式
    time_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m-%d %H:%M",
        "%m-%d",
    ]
    
    # 如果是相对时间（如"12-23 12:52"），需要加上年份
    if re.match(r'^\d{2}-\d{2}', time_str):
        current_year = datetime.datetime.now().year
        time_str = f"{current_year}-{time_str}"
    
    for fmt in time_formats:
        try:
            dt = datetime.datetime.strptime(time_str, fmt)
            # 如果年份是当前年份但月份大于当前月份，说明是去年
            if dt.year == datetime.datetime.now().year and dt.month > datetime.datetime.now().month:
                dt = dt.replace(year=dt.year - 1)
            return dt
        except:
            continue
    
    return None

def is_within_time_range(time_str, start_date, end_date):
    """判断时间是否在指定范围内"""
    dt = parse_time(time_str)
    if dt is None:
        return True  # 如果无法解析时间，默认保留
    return start_date <= dt <= end_date

def fetch_all_pages(stock_code, max_pages=1000):
    """爬取所有页面的帖子"""
    base_url = f"https://guba.eastmoney.com/list,{stock_code}.html"
    all_posts = []
    seen_post_ids = set()
    
    def fetch_page_worker(page_num):
        """线程工作函数：爬取单个列表页"""
        thread_driver = create_driver()
        try:
            if page_num == 1:
                list_url = base_url
            else:
                list_url = f"https://guba.eastmoney.com/list,{stock_code}_{page_num}.html"
            
            print(f"[线程 {threading.current_thread().name}] 开始抓取第 {page_num} 页: {list_url}")
            page_posts = fetch_page_posts(list_url, thread_driver)
            
            # 过滤该股票的帖子
            filtered_posts = [
                p for p in page_posts
                if p.get("stockbar_code") == stock_code or stock_code in str(p.get("stockbar_code", ""))
            ]
            
            # 提取post_id并去重
            unique_posts = []
            for post in filtered_posts:
                post_id = (post.get("post_id") or post.get("id") or 
                          post.get("article_id") or post.get("postid") or "")
                
                if not post_id:
                    post_url = post.get("post_url", "") or post.get("url", "")
                    if post_url:
                        match = re.search(r'news,[^,]+,(.+?)\.html', post_url)
                        if match:
                            post_id = match.group(1)
                
                if post_id and post_id in seen_post_ids:
                    continue
                
                if post_id:
                    seen_post_ids.add(post_id)
                    post["post_id"] = post_id
                
                unique_posts.append(post)
            
            print(f"[线程 {threading.current_thread().name}] 第 {page_num} 页完成，获取 {len(unique_posts)} 条新帖子")
            return page_num, unique_posts
        except Exception as e:
            print(f"[线程 {threading.current_thread().name}] 第 {page_num} 页出错: {e}")
            traceback.print_exc()
            return page_num, []
        finally:
            try:
                thread_driver.quit()
            except:
                pass
    
    # 使用线程池爬取页面
    page_num = 1
    consecutive_empty_pages = 0
    max_consecutive_empty = 3  # 连续3页没有新帖子就停止
    
    while page_num <= max_pages:
        # 批量爬取多页
        batch_size = NUM_THREADS * 2  # 每次爬取一批页面
        pages_to_fetch = list(range(page_num, min(page_num + batch_size, max_pages + 1)))
        page_results = {}
        
        with ThreadPoolExecutor(max_workers=NUM_THREADS, thread_name_prefix="Crawler") as executor:
            future_to_page = {executor.submit(fetch_page_worker, page): page for page in pages_to_fetch}
            
            for future in as_completed(future_to_page):
                p_num, page_posts = future.result()
                page_results[p_num] = page_posts
        
        # 按页面顺序处理结果
        batch_has_new = False
        for p_num in sorted(page_results.keys()):
            posts = page_results[p_num]
            if posts:
                batch_has_new = True
                consecutive_empty_pages = 0
                
                # 检查时间范围
                filtered_posts = []
                for post in posts:
                    time_str = post.get("post_publish_time", "") or post.get("post_last_time", "")
                    if is_within_time_range(time_str, start_date, end_date):
                        filtered_posts.append(post)
                    else:
                        # 如果帖子时间超出范围，说明后续页面也不在范围内
                        print(f"  检测到超出时间范围的帖子: {time_str}")
                
                all_posts.extend(filtered_posts)
                
                # 如果过滤后没有帖子，说明已经超出时间范围
                if not filtered_posts and posts:
                    print(f"  第 {p_num} 页的帖子已超出时间范围，停止爬取")
                    return all_posts
            else:
                consecutive_empty_pages += 1
        
        if not batch_has_new:
            consecutive_empty_pages += batch_size
        
        if consecutive_empty_pages >= max_consecutive_empty:
            print(f"连续 {consecutive_empty_pages} 页没有新帖子，停止爬取")
            break
        
        page_num += batch_size
        time.sleep(2)  # 批次之间稍作延迟
    
    return all_posts

def main():
    """主函数"""
    print("=" * 60)
    print(f"开始爬取股票 {STOCK_CODE} 近 {MONTHS} 个月的所有帖子")
    print(f"时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    print(f"使用 {NUM_THREADS} 个线程")
    print("=" * 60)
    
    # 爬取所有帖子
    print("\n步骤1: 爬取帖子列表...")
    all_posts = fetch_all_pages(STOCK_CODE, MAX_PAGES)
    
    # 按时间排序
    all_posts.sort(key=lambda p: parse_time(p.get("post_publish_time", "") or p.get("post_last_time", "")) or datetime.datetime.min, reverse=True)
    
    print(f"\n共获取 {len(all_posts)} 条帖子")
    
    # 保存到CSV
    csv_file = DATA_DIR / f"{STOCK_CODE}_posts_{MONTHS}months.csv"
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
        "post_url",
        "crawl_time",
    ]
    
    # 加载已有数据
    existing_rows = []
    seen_post_ids = set()
    if csv_file.exists():
        with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                post_id = row.get("post_id", "").strip()
                if post_id:
                    seen_post_ids.add(post_id)
                existing_rows.append(row)
        print(f"加载已有数据 {len(existing_rows)} 条")
    
    # 添加爬取时间戳
    crawl_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 创建全局driver用于爬取内容
    global_driver = None
    if FETCH_CONTENT:
        global_driver = create_driver()
    
    # 处理新帖子
    new_posts_count = 0
    for idx, post in enumerate(all_posts, 1):
        post_id = post.get("post_id", "")
        
        # 去重
        if post_id and post_id in seen_post_ids:
            continue
        
        if post_id:
            seen_post_ids.add(post_id)
        
        # 爬取帖子内容
        post_content = ""
        post_comments = ""
        if FETCH_CONTENT and post_id:
            print(f"  正在爬取帖子内容 [{idx}/{len(all_posts)}]: {post.get('post_title', '')[:50]}...")
            try:
                result = fetch_post_content(post_id, STOCK_CODE, global_driver)
                if isinstance(result, tuple):
                    post_content, post_comments = result
                else:
                    post_content = result
                time.sleep(1)  # 延迟避免请求过快
            except Exception as e:
                print(f"    爬取内容失败: {e}")
        
        row = {
            "stockbar_code": STOCK_CODE,
            "stockbar_name": post.get("stockbar_name", ""),
            "post_id": post_id,
            "post_title": post.get("post_title", ""),
            "post_content": post_content,
            "post_comments": post_comments,
            "post_click_count": post.get("post_click_count", ""),
            "post_comment_count": post.get("post_comment_count", ""),
            "post_forward_count": post.get("post_forward_count", ""),
            "post_publish_time": post.get("post_publish_time", ""),
            "post_last_time": post.get("post_last_time", ""),
            "post_has_pic": post.get("post_has_pic", ""),
            "post_has_video": post.get("post_has_video", ""),
            "bullish_bearish": post.get("bullish_bearish", ""),
            "post_url": post.get("post_url", ""),
            "crawl_time": crawl_time,
        }
        
        existing_rows.append(row)
        new_posts_count += 1
    
    # 关闭全局driver
    if global_driver:
        try:
            global_driver.quit()
        except:
            pass
    
    # 按时间排序
    existing_rows.sort(
        key=lambda r: parse_time(r.get("post_publish_time", "") or r.get("post_last_time", "")) or datetime.datetime.min,
        reverse=True
    )
    
    # 保存到CSV
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
    
    print(f"\n完成！共保存 {len(existing_rows)} 条帖子到 {csv_file}")
    print(f"新增 {new_posts_count} 条帖子")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断，退出程序")
    except Exception as e:
        print(f"\n\n发生错误: {e}")
        traceback.print_exc()
