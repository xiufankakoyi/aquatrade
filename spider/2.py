import time
import json
import re
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
# === 配置区域 ===
CHROME_DRIVER_PATH = r"I:\\chromedriver-win64\\chromedriver.exe"

def create_driver():
    options = webdriver.ChromeOptions()
    # 禁用自动化特征，防止简单的反爬
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    
    service = Service(CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    
    # 注入JS移除webdriver属性
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    
    return driver

# # ==========================================
# # 1. 解析人气榜 (修复错位：使用锚点定位法)
# # ==========================================
# def extract_rank_list(driver):
#     url = "https://guba.eastmoney.com/rank/"
#     print(f"\n[1/4] 正在抓取人气榜: {url}")
#     driver.get(url)
    
#     try:
#         WebDriverWait(driver, 10).until(
#             EC.presence_of_element_located((By.CSS_SELECTOR, "tr, .listitem"))
#         )
#     except:
#         print("  -> 等待超时，尝试直接解析...")

#     data_list = []
#     # 获取页面所有行
#     rows = driver.find_elements(By.CSS_SELECTOR, "tr, .listitem")
#     print(f"  -> 找到 {len(rows)} 行数据，开始全量提取...")
    
#     # === 修改开始：使用 enumerate 生成排名，并提取更多字段 ===
#     for i, row in enumerate(rows): 
#         # 1. 解决排名问题：直接用 (索引+1) 作为排名，不依赖网页文本
#         current_rank = str(i)
        
#         text = row.text.replace('\n', ' ')
#         if not text: continue
        
#         parts = text.split()
        
#         # --- 核心修复：基于“代码”的位置向左右寻找 ---
#         code_index = -1
#         stock_code = ""
        
#         # 先找到由6位数字组成的股票代码，这是唯一的“锚点”
#         for idx, part in enumerate(parts):
#             if re.match(r'^\d{6}$', part):
#                 code_index = idx
#                 stock_code = part
#                 break
        
#         if code_index != -1:
#             try:
#                 # A. 股票名称：代码的右边一个
#                 name = parts[code_index + 1] if (code_index + 1) < len(parts) else ""
                
#                 # B. 排名较昨日变动：代码的左边一个
#                 # 注意：如果是第1名，网页文本可能是 "↑3 002703"，代码在索引1，变动在索引0
#                 rank_change = ""
#                 if code_index > 0:
#                     rank_change = parts[code_index - 1]
#                     # 过滤掉可能的纯数字排名误判（防止把 "4" 当成变动）
#                     # 通常变动包含 symbols 或者是较小的数字，或者是 "-"
                
#                 # C. 寻找百分比数据（新晋粉丝、铁杆粉丝）
#                 # 策略：从列表末尾往回找，通常最后两个是粉丝数据
#                 new_fans = ""
#                 loyal_fans = ""
                
#                 percentages = [p for p in parts if "%" in p]
#                 if len(percentages) >= 3:
#                     # 通常顺序是：涨跌幅(9.99%) ... 新晋(83.11%) 铁杆(16.89%)
#                     # 取最后两个
#                     loyal_fans = percentages[-1]
#                     new_fans = percentages[-2]
#                     change_pct = percentages[-3] # 涨跌幅
#                 else:
#                     change_pct = ""

#                 # D. 最新价：在名称后面找浮点数
#                 price = ""
#                 for j in range(code_index + 2, len(parts)):
#                     if re.match(r'^-?\d+\.\d+$', parts[j]):
#                         price = parts[j]
#                         break

#                 item = {
#                     "排名": current_rank,         # 修复：使用生成的排名
#                     "代码": stock_code,
#                     "名称": name,
#                     "最新价": price,
#                     "涨跌幅": change_pct,
#                     "排名变动": rank_change,      # 新增
#                     "新晋粉丝": new_fans,         # 新增
#                     "铁杆粉丝": loyal_fans        # 新增
#                 }
#                 data_list.append(item)
#             except Exception as e:
#                 continue
#     # === 修改结束 ===

#     # 打印完整数据，不截断
#     print(json.dumps(data_list, indent=2, ensure_ascii=False))

# ==========================================
# 2. 解析个股人气详情 (保持不变)
# ==========================================
def extract_stock_rank_detail(driver):
    code_num = "002703"
    prefix = "sh" if code_num.startswith("6") else "sz"
    full_code = f"{prefix}{code_num}"
    
    # 1. 使用你找到的正确 API 获取多空数据
    api_url = f"https://eminterservice.eastmoney.com/UserData/GetWebTape?code={full_code}"
    print(f"\n[2/4] 正在抓取个股详情 API: {api_url}")
    
    api_info = {}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://guba.eastmoney.com/"
        }
        resp = requests.get(api_url, headers=headers, timeout=5)
        
        if resp.status_code == 200:
            res_json = resp.json()
            if res_json.get("Status") == 1:
                d = res_json.get("Data", {})
                # 转换小数为百分比
                bull = float(d.get("TapeZ", 0)) * 100
                bear = float(d.get("TapeD", 0)) * 100
                api_info["多空日期"] = d.get("Date")
                api_info["看涨比例"] = f"{bull:.2f}%"
                api_info["看跌比例"] = f"{bear:.2f}%"
                print(f"  -> [API成功] {api_info}")
            else:
                print(f"  -> [API返回] 状态非1: {res_json}")
        else:
            print(f"  -> [API失败] 状态码: {resp.status_code}")
            
    except Exception as e:
        print(f"  -> [API报错] {e}")

    # 2. 结合 Selenium 抓取页面文本
    url = f"https://guba.eastmoney.com/rank/stock?code={code_num}&from="
    driver.get(url)
    time.sleep(1)
    
    page_info = {"API数据": api_info}
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        match_rank = re.search(r'第\s*(\d+)\s*名', body_text)
        if match_rank: page_info['当前排名'] = match_rank.group(1)
        
        match_fans = re.search(r'新晋粉丝.*?(\d+\.?\d*%)', body_text)
        if match_fans: page_info['新晋粉丝'] = match_fans.group(1)
    except: pass
    
    print(json.dumps(page_info, indent=2, ensure_ascii=False))

# # ==========================================
# # 3. 解析帖子列表 (移除截断，增加人工暂停)
# # ==========================================
# def extract_post_list(driver):
#     url = "https://guba.eastmoney.com/list,000592.html"
#     print(f"\n[3/4] 正在抓取帖子列表: {url}")
#     driver.get(url)
#     time.sleep(2)
    
#     posts = []
    
#     # 循环检查，给人工验证的机会
#     max_retries = 3
#     for attempt in range(max_retries):
#         elements = driver.find_elements(By.CSS_SELECTOR, ".article-h, .listitem, tr.list-item")
#         valid_elements = [e for e in elements if "阅读" not in e.text] # 过滤表头
        
#         if len(valid_elements) > 0:
#             print(f"  -> 成功获取到 {len(valid_elements)} 行数据，开始全量提取...")
#             for elem in valid_elements: # 移除切片，提取所有
#                 try:
#                     # 获取完整文本，不截断
#                     full_text = elem.text.replace('\n', ' ')
#                     posts.append(full_text)
#                 except: continue
#             break
#         else:
#             print(f"  ⚠️ 警告 (尝试 {attempt+1}/{max_retries}): 未提取到帖子，可能触发了验证码！")
#             print("  >>> 请切换到浏览器窗口，手动完成滑块验证 <<<")
#             print("  >>> 验证完成后，请回到这里按 [回车键] 继续... <<<")
#             input() 
#             time.sleep(2)

#     if posts:
#         # 打印完整列表，不截断
#         print(json.dumps(posts, indent=2, ensure_ascii=False))
#     else:
#         print("  ❌ 未能获取帖子列表。")

# # ==========================================
# # 4. 解析帖子正文 (移除截断)
# # ==========================================
# def extract_post_content(driver):
#     url = "https://guba.eastmoney.com/news,000592,1642061341.html"
#     print(f"\n[4/4] 正在抓取帖子正文: {url}")
#     driver.get(url)
#     time.sleep(2)
    
#     result = {}
#     try:
#         candidates = driver.find_elements(By.CSS_SELECTOR, "div, p, article")
#         longest_text = ""
#         for cand in candidates:
#             if not cand.is_displayed(): continue
#             text = cand.text.strip()
#             if len(text) > 50 and len(text) > len(longest_text):
#                 longest_text = text
        
#         if longest_text:
#             # 移除所有换行符以便在一行显示，或者保留原样
#             # 这里保留原样，不做任何截断
#             result["正文完整内容"] = longest_text
#     except Exception as e:
#         result["错误"] = str(e)

#     print(json.dumps(result, indent=2, ensure_ascii=False))

# ==========================================
# 主程序
# ==========================================
if __name__ == "__main__":
    driver = create_driver()
    try:
        #extract_rank_list(driver)
        extract_stock_rank_detail(driver)
        extract_post_list(driver)
        extract_post_content(driver)
    except Exception as e:
        print(f"发生未知错误: {e}")
    finally:
        print("\n全部流程结束。")
        # driver.quit() # 建议保留浏览器开启以便观察