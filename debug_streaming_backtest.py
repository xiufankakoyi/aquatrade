"""
使用 Playwright 调试流式回测功能
检查 initializing 事件是否正确发送和接收
"""
import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright

LOG_FILE = Path(__file__).parent / '.cursor' / 'debug_playwright_streaming.log'

async def debug_streaming_backtest():
    """调试流式回测功能"""
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 记录日志
        def log(message, data=None):
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            entry = {
                "timestamp": timestamp,
                "message": message,
                "data": data or {}
            }
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"[{timestamp}] {message}")
        
        log("开始流式回测调试会话", {})
        
        # 监听所有 Socket.IO 事件
        socketio_events = []
        socketio_requests = []
        
        # 监听网络请求
        async def handle_request(request):
            if 'socket.io' in request.url:
                socketio_requests.append({
                    "url": request.url,
                    "method": request.method,
                    "timestamp": time.time()
                })
                log("Socket.IO 请求", {"url": request.url, "method": request.method})
        
        async def handle_response(response):
            if 'socket.io' in response.url:
                try:
                    body = await response.body()
                    headers = response.headers
                    socketio_events.append({
                        "url": response.url,
                        "status": response.status,
                        "headers": dict(headers),
                        "body_size": len(body),
                        "timestamp": time.time()
                    })
                    log("Socket.IO 响应", {
                        "url": response.url,
                        "status": response.status,
                        "body_size": len(body),
                        "headers": {k: v for k, v in headers.items() if 'access-control' in k.lower()}
                    })
                except Exception as e:
                    log("Socket.IO 响应处理失败", {"error": str(e)})
        
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        # 监听控制台消息
        def handle_console(msg):
            log("Console", {"level": msg.type, "text": str(msg.text)})
        
        page.on("console", handle_console)
        
        # 访问前端页面
        try:
            log("尝试访问前端: http://localhost:5173", {})
            await page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=30000)
            log("页面加载成功: http://localhost:5173", {})
        except Exception as e:
            log("页面加载失败，但继续执行", {"error": str(e)})
            # 不关闭浏览器，继续尝试
        
        # 等待页面完全加载
        await page.wait_for_timeout(2000)
        log("页面完全加载完成", {})
        
        # 等待页面加载完成
        await page.wait_for_timeout(3000)
        
        # 注入代码监听 Socket.IO 事件（多次尝试，因为 Socket.IO 可能延迟初始化）
        for attempt in range(5):
            try:
                result = await page.evaluate("""
                    (() => {
                        if (!window._socketioEvents) {
                            window._socketioEvents = [];
                        }
                        if (!window._socketioListeners) {
                            window._socketioListeners = {};
                        }
                        
                        // 尝试多种方式获取 Socket.IO 实例
                        let socket = null;
                        if (window.io && window.io.sockets) {
                            socket = window.io.sockets.socket || window.io.socket;
                        }
                        if (!socket && window.socket) {
                            socket = window.socket;
                        }
                        if (!socket && window.__socketio_instance) {
                            socket = window.__socketio_instance;
                        }
                        
                        if (socket && !socket.__playwright_wrapped) {
                            socket.__playwright_wrapped = true;
                            
                            // 监听所有事件
                            const originalEmit = socket.emit.bind(socket);
                            socket.emit = function(...args) {
                                window._socketioEvents.push({
                                    type: 'emit',
                                    event: args[0],
                                    data: args[1],
                                    timestamp: Date.now()
                                });
                                console.log('[PLAYWRIGHT] Socket.IO emit:', args[0], args[1]);
                                return originalEmit(...args);
                            };
                            
                            const originalOn = socket.on.bind(socket);
                            socket.on = function(event, callback) {
                                if (!window._socketioListeners[event]) {
                                    window._socketioListeners[event] = [];
                                }
                                window._socketioListeners[event].push(callback);
                                
                                // 包装回调以记录事件
                                const wrappedCallback = function(...args) {
                                    window._socketioEvents.push({
                                        type: 'on',
                                        event: event,
                                        data: args[0],
                                        timestamp: Date.now()
                                    });
                                    console.log('[PLAYWRIGHT] Socket.IO received:', event, args[0]);
                                    return callback(...args);
                                };
                                return originalOn(event, wrappedCallback);
                            };
                            
                            return { success: true, socket_id: socket.id };
                        }
                        
                        return { success: false, has_socket: !!socket };
                    })();
                """)
                if result.get('success'):
                    log("Socket.IO 事件监听已设置", result)
                    break
                else:
                    log(f"尝试 {attempt + 1}/5: Socket.IO 实例未找到或已包装", result)
                    await page.wait_for_timeout(1000)
            except Exception as e:
                log(f"设置事件监听失败 (尝试 {attempt + 1}/5)", {"error": str(e)})
                await page.wait_for_timeout(1000)
        
        # 等待 Socket.IO 连接
        log("等待 Socket.IO 连接...", {})
        await page.wait_for_timeout(5000)
        
        # 检查连接状态
        try:
            connection_status = await page.evaluate("""
                () => {
                    let socket = null;
                    if (window.io && window.io.sockets) {
                        socket = window.io.sockets.socket || window.io.socket;
                    }
                    if (!socket && window.socket) {
                        socket = window.socket;
                    }
                    if (!socket && window.__socketio_instance) {
                        socket = window.__socketio_instance;
                    }
                    return {
                        connected: socket?.connected || false,
                        id: socket?.id || null,
                        events_count: (window._socketioEvents || []).length,
                        recent_events: (window._socketioEvents || []).slice(-5)
                    };
                }
            """)
            log("Socket.IO 连接状态", connection_status)
        except Exception as e:
            log("检查连接状态时出错", {"error": str(e)})
        
        # 查找并点击回测按钮
        log("查找回测按钮...", {})
        try:
            # 尝试多种选择器
            buttons = await page.query_selector_all("button")
            log(f"找到 {len(buttons)} 个按钮", {})
            
            # 查找包含"回测"或"运行"的按钮
            backtest_button = None
            for btn in buttons:
                text = await btn.inner_text()
                if "回测" in text or "运行" in text or "start" in text.lower() or "run" in text.lower():
                    backtest_button = btn
                    log(f"找到回测按钮: {text}", {})
                    break
            
            if backtest_button:
                log("点击回测按钮...", {})
                await backtest_button.click()
                log("回测按钮已点击", {})
            else:
                log("未找到回测按钮，尝试通过 JavaScript 触发", {})
                # 尝试通过 JavaScript 触发
                await page.evaluate("""
                    () => {
                        // 查找所有按钮并点击包含"回测"的
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const backtestBtn = buttons.find(btn => 
                            btn.textContent.includes('回测') || 
                            btn.textContent.includes('运行') ||
                            btn.textContent.toLowerCase().includes('start') ||
                            btn.textContent.toLowerCase().includes('run')
                        );
                        if (backtestBtn) {
                            backtestBtn.click();
                            return true;
                        }
                        return false;
                    }
                """)
        except Exception as e:
            log("触发回测失败", {"error": str(e)})
        
        # 监听事件 60 秒
        log("开始监听回测事件（60秒）...", {})
        start_time = time.time()
        last_event_time = start_time
        event_count = 0
        
        while time.time() - start_time < 60:
            await page.wait_for_timeout(1000)  # 每秒检查一次
            
            # 检查是否有新事件
            try:
                events = await page.evaluate("""
                    () => {
                        return window._socketioEvents || [];
                    }
                """)
                
                if len(events) > event_count:
                    new_events = events[event_count:]
                    for event in new_events:
                        log("收到 Socket.IO 事件", {
                            "type": event.get("type"),
                            "event": event.get("event"),
                            "has_data": "data" in event,
                            "timestamp": event.get("timestamp")
                        })
                        # 特别关注 initializing 事件
                        if event.get("event") == "initializing" or (isinstance(event.get("data"), dict) and event.get("data", {}).get("type") == "initializing"):
                            log("✓ 收到 initializing 事件！", event.get("data"))
                    event_count = len(events)
                    last_event_time = time.time()
                
                # 检查是否有超时（30秒没有新事件）
                if time.time() - last_event_time > 30:
                    log("⚠️ 30秒没有收到新事件", {
                        "last_event_time": last_event_time,
                        "current_time": time.time(),
                        "elapsed": time.time() - last_event_time
                    })
                    break
                    
            except Exception as e:
                log("检查事件时出错", {"error": str(e)})
        
        # 最终统计
        try:
            final_events = await page.evaluate("""
                () => {
                    return {
                        total_events: window._socketioEvents?.length || 0,
                        events: window._socketioEvents || [],
                        listeners: window._socketioListeners || {}
                    };
                }
            """)
            
            log("最终事件统计", {
                "total_events": final_events.get("total_events", 0),
                "event_types": [e.get("event") for e in final_events.get("events", [])],
                "has_initializing": any(
                    e.get("event") == "initializing" or 
                    (isinstance(e.get("data"), dict) and e.get("data", {}).get("type") == "initializing")
                    for e in final_events.get("events", [])
                )
            })
        except Exception as e:
            log("获取最终统计失败", {"error": str(e)})
        
        log("调试会话结束", {})
        
        # 保持浏览器打开 5 秒以便观察
        await page.wait_for_timeout(5000)
        await browser.close()

if __name__ == "__main__":
    # 清空日志文件
    if LOG_FILE.exists():
        LOG_FILE.write_text('', encoding='utf-8')
    
    asyncio.run(debug_streaming_backtest())

