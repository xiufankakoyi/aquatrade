"""
Playwright 自动调试脚本 - 回测进度更新问题
使用新的浏览器上下文，不影响现有网页
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

# 日志文件路径
LOG_FILE = Path(r'd:\aquatrade\.cursor\debug_playwright.log')

def log_message(message: str, data: dict = None):
    """记录日志到文件"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    log_entry = {
        "timestamp": timestamp,
        "message": message,
        "data": data or {}
    }
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            f.flush()
    except Exception as e:
        print(f"日志写入失败: {e}")

async def intercept_socketio_messages(page: Page):
    """拦截并记录所有 Socket.IO 消息"""
    # 监听所有网络请求（包括 WebSocket 和 HTTP 轮询）
    async def handle_request(request):
        url = request.url
        if 'socket.io' in url:
            log_message("Socket.IO 请求", {"url": url, "method": request.method})
    
    async def handle_response(response):
        url = response.url
        if 'socket.io' in url:
            try:
                body = await response.body()
                log_message("Socket.IO 响应", {
                    "url": url, 
                    "status": response.status, 
                    "body_size": len(body),
                    "headers": dict(response.headers)
                })
            except:
                pass
    
    page.on('request', handle_request)
    page.on('response', handle_response)
    
    # 注入代码来监听 Socket.IO 事件（在页面加载后）
    await page.add_init_script("""
        // 全局事件记录器
        window.__playwright_socketio_emit = [];
        window.__playwright_socketio_received = [];
        window.__playwright_socketio_on = [];
        
        // 拦截 socket.io-client 的 emit 和 on
        const originalIo = window.io;
        if (originalIo) {
            window.io = function(...args) {
                const socket = originalIo.apply(this, args);
                
                // 拦截 emit
                const originalEmit = socket.emit.bind(socket);
                socket.emit = function(event, data, ...rest) {
                    console.log('[PLAYWRIGHT] Socket.IO emit:', event, data);
                    window.__playwright_socketio_emit.push({
                        event: event,
                        data: data,
                        timestamp: Date.now()
                    });
                    return originalEmit(event, data, ...rest);
                };
                
                // 拦截 on
                const originalOn = socket.on.bind(socket);
                socket.on = function(event, callback) {
                    console.log('[PLAYWRIGHT] Socket.IO on:', event);
                    window.__playwright_socketio_on.push({
                        event: event,
                        timestamp: Date.now()
                    });
                    
                    // 包装回调函数以记录接收的事件
                    const wrappedCallback = function(data) {
                        console.log('[PLAYWRIGHT] Socket.IO received:', event, data);
                        window.__playwright_socketio_received.push({
                            event: event,
                            data: data,
                            timestamp: Date.now()
                        });
                        return callback.apply(this, arguments);
                    };
                    
                    return originalOn(event, wrappedCallback);
                };
                
                return socket;
            };
        }
        
        // 也尝试拦截已经存在的 socket 实例
        const checkExistingSocket = () => {
            if (window.__socketio_instance || window.socket) {
                const socket = window.__socketio_instance || window.socket;
                if (socket && !socket.__playwright_wrapped) {
                    socket.__playwright_wrapped = true;
                    const originalEmit = socket.emit.bind(socket);
                    socket.emit = function(event, data, ...rest) {
                        console.log('[PLAYWRIGHT] Existing socket emit:', event, data);
                        window.__playwright_socketio_emit.push({
                            event: event,
                            data: data,
                            timestamp: Date.now()
                        });
                        return originalEmit(event, data, ...rest);
                    };
                    
                    const originalOn = socket.on.bind(socket);
                    socket.on = function(event, callback) {
                        console.log('[PLAYWRIGHT] Existing socket on:', event);
                        window.__playwright_socketio_on.push({
                            event: event,
                            timestamp: Date.now()
                        });
                        
                        const wrappedCallback = function(data) {
                            console.log('[PLAYWRIGHT] Existing socket received:', event, data);
                            window.__playwright_socketio_received.push({
                                event: event,
                                data: data,
                                timestamp: Date.now()
                            });
                            return callback.apply(this, arguments);
                        };
                        
                        return originalOn(event, wrappedCallback);
                    };
                }
            }
        };
        
        // 定期检查
        setInterval(checkExistingSocket, 1000);
    """)

async def monitor_console(page: Page):
    """监听控制台输出"""
    def handle_console(msg):
        text = msg.text
        log_message("Console", {"level": msg.type, "text": text})
        if 'initializing' in text.lower() or 'backtest' in text.lower() or 'socket' in text.lower():
            print(f"[CONSOLE {msg.type}] {text}")
    
    page.on('console', handle_console)

async def wait_for_socketio_connection(page: Page, timeout: int = 30):
    """等待 Socket.IO 连接建立"""
    log_message("等待 Socket.IO 连接...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # 检查 Socket.IO 连接状态
            connected = await page.evaluate("""
                () => {
                    if (window.io && window.__socketio_instance) {
                        return window.__socketio_instance.connected;
                    }
                    // 尝试从全局变量中查找
                    const socket = window.__socket || window.socket;
                    return socket && socket.connected;
                }
            """)
            
            if connected:
                log_message("Socket.IO 连接已建立")
                return True
            
            await asyncio.sleep(0.5)
        except Exception as e:
            log_message("检查连接状态时出错", {"error": str(e)})
            await asyncio.sleep(0.5)
    
    log_message("Socket.IO 连接超时", {"timeout": timeout})
    return False

async def get_socketio_events(page: Page):
    """获取所有记录的 Socket.IO 事件"""
    try:
        events = await page.evaluate("""
            () => {
                return {
                    emitted: window.__playwright_socketio_emit || [],
                    received: window.__playwright_socketio_received || [],
                    listeners: window.__playwright_socketio_on || []
                };
            }
        """)
        return events
    except Exception as e:
        log_message("获取 Socket.IO 事件失败", {"error": str(e)})
        return {"emitted": [], "received": [], "listeners": []}

async def run_backtest_debug():
    """运行回测调试"""
    async with async_playwright() as p:
        # 使用新的浏览器上下文，不影响现有网页
        browser = await p.chromium.launch(
            headless=False,  # 显示浏览器窗口以便观察
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # 创建新的上下文（独立于现有浏览器会话）
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        
        # 清空日志文件
        if LOG_FILE.exists():
            LOG_FILE.unlink()
        log_message("开始 Playwright 调试会话")
        
        try:
            # 设置监听
            await intercept_socketio_messages(page)
            await monitor_console(page)
            
            # 访问前端页面（尝试多个可能的端口）
            frontend_urls = [
                'http://localhost:5173',
                'http://localhost:5174',
                'http://localhost:3000',
                'http://localhost:8080'
            ]
            
            page_loaded = False
            for url in frontend_urls:
                try:
                    log_message(f"尝试访问前端: {url}")
                    await page.goto(url, wait_until='domcontentloaded', timeout=10000)
                    log_message(f"页面加载成功: {url}")
                    page_loaded = True
                    break
                except Exception as e:
                    log_message(f"无法访问 {url}", {"error": str(e)})
                    continue
            
            if not page_loaded:
                log_message("错误: 无法访问前端页面，请确保前端服务器正在运行")
                log_message("错误: 无法访问前端页面")
                print("\n❌ 无法访问前端页面！")
                print("请确保前端服务器正在运行。")
                print("如果使用 Vite，请运行: npm run dev")
                print("如果使用其他服务器，请检查端口配置")
                print("\n浏览器窗口将保持打开，您可以手动访问前端页面")
                # 不返回，继续等待用户手动操作
                print("等待60秒，如果您手动打开了页面，脚本将继续监控...")
                await asyncio.sleep(60)
            
            # 等待页面完全加载
            await page.wait_for_load_state('networkidle', timeout=30000)
            log_message("页面完全加载完成")
            
            # 等待页面完全加载
            await asyncio.sleep(3)
            
            # 等待 Socket.IO 连接
            connected = await wait_for_socketio_connection(page, timeout=30)
            if not connected:
                log_message("警告: Socket.IO 连接未建立，但继续执行")
            
            # 等待一下让 Socket.IO 完全初始化
            await asyncio.sleep(2)
            
            # 获取初始 Socket.IO 事件
            initial_events = await get_socketio_events(page)
            log_message("初始 Socket.IO 事件", initial_events)
            
            # 通过 JavaScript 直接触发回测
            log_message("通过 JavaScript 触发回测...")
            backtest_triggered = await page.evaluate("""
                async () => {
                    try {
                        // 查找回测相关的函数或按钮
                        const buttons = Array.from(document.querySelectorAll('button'));
                        console.log('[PLAYWRIGHT] 所有按钮:', buttons.map(b => ({
                            text: b.textContent?.trim(),
                            class: b.className,
                            id: b.id
                        })));
                        
                        // 尝试找到包含"回测"或"开始"的按钮
                        const backtestBtn = buttons.find(b => {
                            const text = b.textContent?.trim() || '';
                            return text.includes('回测') || text.includes('开始') || 
                                   text.includes('Start') || text.includes('Run');
                        });
                        
                        if (backtestBtn) {
                            console.log('[PLAYWRIGHT] 找到回测按钮，点击:', backtestBtn.textContent);
                            backtestBtn.click();
                            return { success: true, method: 'button_click', button_text: backtestBtn.textContent };
                        }
                        
                        // 尝试通过 Vue 组件触发
                        if (window.__VUE__) {
                            console.log('[PLAYWRIGHT] 检测到 Vue，尝试通过组件触发');
                        }
                        
                        // 尝试直接调用 API
                        const socket = window.__socketio_instance || window.socket;
                        if (socket && socket.connected) {
                            console.log('[PLAYWRIGHT] 通过 Socket.IO 直接触发回测');
                            socket.emit('run_streaming_backtest', {
                                strategy_name: '聚宽量比市值策略pro',
                                start_date: '2024-05-20',
                                end_date: '2025-01-15',
                                benchmark_code: '000300'
                            });
                            return { success: true, method: 'socket_emit' };
                        }
                        
                        return { success: false, reason: 'no_method_found' };
                    } catch (e) {
                        return { success: false, error: e.message };
                    }
                }
            """)
            
            log_message("回测触发结果", backtest_triggered)
            
            if not backtest_triggered.get('success'):
                log_message("警告: 无法自动触发回测，请手动点击回测按钮")
                print("\n⚠️  无法自动触发回测，请在浏览器窗口中手动点击回测按钮")
                print("脚本将继续监控事件...\n")
            
            # 等待并监控回测过程
            log_message("开始监控回测过程...")
            start_time = time.time()
            last_event_time = start_time
            event_count = 0
            
            while time.time() - start_time < 120:  # 最多等待2分钟
                await asyncio.sleep(1)
                
                # 获取 Socket.IO 事件
                events = await get_socketio_events(page)
                new_received = len(events.get('received', []))
                
                if new_received > event_count:
                    event_count = new_received
                    last_event_time = time.time()
                    log_message(f"收到新事件 (总数: {event_count})", {
                        "latest_events": events.get('received', [])[-5:]  # 最近5个事件
                    })
                    
                    # 检查是否有 initializing 事件
                    for event in events.get('received', []):
                        if event.get('event') == 'initializing':
                            log_message("✅ 收到 initializing 事件", event)
                
                # 检查是否超时（30秒没有新事件）
                if time.time() - last_event_time > 30:
                    log_message("⚠️ 30秒没有收到新事件", {
                        "last_event_time": last_event_time,
                        "current_time": time.time(),
                        "elapsed": time.time() - last_event_time
                    })
                    break
                
                # 检查页面状态
                try:
                    page_state = await page.evaluate("""
                        () => {
                            return {
                                readyState: document.readyState,
                                socketConnected: window.__socketio_instance?.connected || false,
                                hasErrors: document.querySelector('.error, [class*="error"]') !== null
                            };
                        }
                    """)
                    if page_state.get('hasErrors'):
                        log_message("页面检测到错误元素")
                except:
                    pass
            
            # 最终事件统计
            final_events = await get_socketio_events(page)
            log_message("最终事件统计", {
                "emitted_count": len(final_events.get('emitted', [])),
                "received_count": len(final_events.get('received', [])),
                "listeners_count": len(final_events.get('listeners', [])),
                "all_received_events": final_events.get('received', []),
                "all_emitted_events": final_events.get('emitted', [])
            })
            
            # 等待一段时间以便观察
            log_message("调试完成，等待10秒后关闭...")
            await asyncio.sleep(10)
            
        except Exception as e:
            log_message("调试过程中出错", {"error": str(e), "traceback": str(e.__traceback__)})
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # 不关闭浏览器，让用户观察
            log_message("调试会话结束")
            print(f"\n调试日志已保存到: {LOG_FILE}")
            print("浏览器窗口将保持打开，您可以手动关闭")

if __name__ == "__main__":
    print("=" * 60)
    print("Playwright 回测调试脚本")
    print("=" * 60)
    print("正在启动新的浏览器窗口（不影响现有网页）...")
    print(f"日志将保存到: {LOG_FILE}")
    print("=" * 60)
    
    asyncio.run(run_backtest_debug())

