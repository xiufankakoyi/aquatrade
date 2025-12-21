import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# === 配置 ===
CHROME_DRIVER_PATH = r"I:\\chromedriver-win64\\chromedriver.exe"

def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    
    # 【核心黑科技】开启性能日志 (Performance Logging)
    # 这让 Selenium 有能力“监听”浏览器发出的每一个网络请求
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 1,
        "profile.managed_default_content_settings.javascript": 1
    })
    
    service = Service(CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def sniff_network_requests():
    driver = create_driver()
    try:
        url = "https://guba.eastmoney.com/rank/stock?code=002703&from="
        print(f"🕵️ 正在潜入页面: {url}")
        driver.get(url)
        
        print("⏳ 等待页面和图表加载 (5秒)...")
        time.sleep(5) 
        
        print("\n" + "="*50)
        print("开始分析网络请求日志...")
        print("="*50)
        
        # 获取浏览器的性能日志
        logs = driver.get_log("performance")
        
        found_apis = []
        
        for entry in logs:
            try:
                message = json.loads(entry["message"])["message"]
                
                # 我们只关心“发送请求”的事件
                if message["method"] == "Network.requestWillBeSent":
                    request_url = message["params"]["request"]["url"]
                    
                    # 【核心过滤】我们只找包含这些关键字的 URL
                    # 1. GetData.aspx (您截图里看到的)
                    # 2. eminterservice (之前GetWebTape所在的域名)
                    if "GetData.aspx" in request_url or "eminterservice" in request_url:
                        if request_url not in found_apis:
                            found_apis.append(request_url)
                            print(f"👉 发现可疑 API: {request_url}")
                            
            except Exception:
                continue

        if not found_apis:
            print("❌ 未抓取到特定 API。请确保您的 ChromeDriver 支持 Performance Logging。")
        else:
            print(f"\n✅ 成功捕获 {len(found_apis)} 个关键接口！请把上面的 URL 复制给我。")

    finally:
        # driver.quit() # 可以先不关，方便对比
        print("\n嗅探结束。")

if __name__ == "__main__":
    sniff_network_requests()