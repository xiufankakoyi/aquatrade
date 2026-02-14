document.addEventListener('DOMContentLoaded', function() {
    // Enhanced Error Tracking System
    const ErrorTracker = {
        maxLogEntries: 100,
        currentAction: 'page_load',
        actionStack: [],
        
        init() {
            this.setupGlobalErrorHandlers();
            this.setupPerformanceTracking();
            this.setupUserActionTracking();
        },
        
        setupGlobalErrorHandlers() {
            // Global error handler
            window.onerror = (message, source, lineno, colno, error) => {
                this.captureError('javascript_runtime', {
                    message,
                    source,
                    lineno,
                    colno,
                    stack: error?.stack || 'No stack trace available',
                    errorType: error?.constructor?.name || 'Error'
                });
                return false;
            };
            
            // Unhandled promise rejection handler
            window.addEventListener('unhandledrejection', (event) => {
                this.captureError('unhandled_promise', {
                    message: event.reason?.message || String(event.reason),
                    stack: event.reason?.stack || 'No stack trace available',
                    errorType: event.reason?.constructor?.name || 'PromiseRejection'
                });
                event.preventDefault();
            });
            
            // Network error handler
            window.addEventListener('error', (event) => {
                if (event.target.tagName === 'IMG' || event.target.tagName === 'SCRIPT' || event.target.tagName === 'LINK') {
                    this.captureError('resource_load', {
                        resourceType: event.target.tagName,
                        resourceUrl: event.target.src || event.target.href,
                        message: `Failed to load ${event.target.tagName.toLowerCase()} resource`
                    });
                }
            });
            
            // Network status handlers
            window.addEventListener('offline', () => {
                this.captureError('network_status', {
                    status: 'offline',
                    message: 'Network connection lost'
                });
            });
            
            window.addEventListener('online', () => {
                this.logInfo('network_status', {
                    status: 'online',
                    message: 'Network connection restored'
                });
            });
        },
        
        setupPerformanceTracking() {
            window.addEventListener('load', () => {
                setTimeout(() => {
                    const navigation = performance.getEntriesByType('navigation')[0];
                    const paint = performance.getEntriesByType('paint');
                    
                    this.logInfo('performance', {
                        pageLoadTime: navigation?.duration?.toFixed(2) + 'ms',
                        firstPaint: paint?.find(p => p.name === 'first-paint')?.duration?.toFixed(2) + 'ms',
                        firstContentfulPaint: paint?.find(p => p.name === 'first-contentful-paint')?.duration?.toFixed(2) + 'ms'
                    });
                }, 0);
            });
        },
        
        setupUserActionTracking() {
            this.pushAction('page_load');
            
            document.querySelectorAll('button, input, select').forEach(el => {
                el.addEventListener('focus', () => {
                    if (el.id || el.className) {
                        this.pushAction(`focus_on_${el.id || el.className}`);
                    }
                });
            });
        },
        
        pushAction(action) {
            this.actionStack.push({
                action,
                timestamp: this.getTimestamp()
            });
            if (this.actionStack.length > 10) {
                this.actionStack.shift();
            }
        },
        
        getTimestamp() {
            const now = new Date();
            return now.toISOString() + '.' + String(now.getMilliseconds()).padStart(3, '0');
        },
        
        getBrowserInfo() {
            const ua = navigator.userAgent;
            let browser = 'Unknown';
            let version = 'Unknown';
            
            if (ua.includes('Chrome')) {
                browser = 'Chrome';
                version = ua.match(/Chrome\/(\d+)/)?.[1] || 'Unknown';
            } else if (ua.includes('Firefox')) {
                browser = 'Firefox';
                version = ua.match(/Firefox\/(\d+)/)?.[1] || 'Unknown';
            } else if (ua.includes('Safari') && !ua.includes('Chrome')) {
                browser = 'Safari';
                version = ua.match(/Version\/(\d+)/)?.[1] || 'Unknown';
            } else if (ua.includes('Edge')) {
                browser = 'Edge';
                version = ua.match(/Edge\/(\d+)/)?.[1] || 'Unknown';
            }
            
            return {
                browser,
                version,
                platform: navigator.platform,
                os: this.getOS(),
                language: navigator.language,
                screenResolution: `${window.screen.width}x${window.screen.height}`,
                windowSize: `${window.innerWidth}x${window.innerHeight}`,
                cookiesEnabled: navigator.cookieEnabled,
                doNotTrack: navigator.doNotTrack
            };
        },
        
        getOS() {
            const ua = navigator.userAgent;
            if (ua.includes('Windows')) return 'Windows';
            if (ua.includes('Mac')) return 'macOS';
            if (ua.includes('Linux')) return 'Linux';
            if (ua.includes('Android')) return 'Android';
            if (ua.includes('iOS') || ua.includes('iPhone') || ua.includes('iPad')) return 'iOS';
            return 'Unknown';
        },
        
        captureError(category, errorData) {
            const logEntry = {
                id: this.generateId(),
                timestamp: this.getTimestamp(),
                category,
                severity: this.determineSeverity(category),
                errorData,
                browserInfo: this.getBrowserInfo(),
                actionStack: [...this.actionStack],
                pageInfo: {
                    url: window.location.href,
                    referrer: document.referrer,
                    userAgent: navigator.userAgent
                }
            };
            
            this.storeLog(logEntry);
            this.displayErrorModal(logEntry);
            this.reportErrorToBackend(logEntry);
            
            return logEntry;
        },
        
        logInfo(category, infoData) {
            const logEntry = {
                id: this.generateId(),
                timestamp: this.getTimestamp(),
                category,
                severity: 'info',
                infoData,
                browserInfo: this.getBrowserInfo()
            };
            
            this.storeLog(logEntry);
            console.log(`[${logEntry.timestamp}] [INFO] ${category}:`, infoData);
            
            return logEntry;
        },
        
        determineSeverity(category) {
            const severityMap = {
                javascript_runtime: 'error',
                unhandled_promise: 'error',
                network_status: 'warning',
                resource_load: 'warning',
                api_error: 'error',
                validation_error: 'warning',
                permission_error: 'error'
            };
            return severityMap[category] || 'error';
        },
        
        generateId() {
            return Date.now().toString(36) + Math.random().toString(36).substr(2);
        },
        
        storeLog(logEntry) {
            try {
                const logs = JSON.parse(localStorage.getItem('errorLogs') || '[]');
                logs.unshift(logEntry);
                
                while (logs.length > this.maxLogEntries) {
                    logs.pop();
                }
                
                localStorage.setItem('errorLogs', JSON.stringify(logs));
            } catch (e) {
                console.error('Failed to store error log:', e);
            }
        },
        
        displayErrorModal(logEntry) {
            let modal = document.getElementById('error-detail-modal');
            
            if (!modal) {
                modal = this.createErrorModal();
            }
            
            const modalBody = modal.querySelector('.modal-body');
            modalBody.innerHTML = this.formatErrorDetails(logEntry);
            
            modal.classList.remove('hidden');
        },
        
        createErrorModal() {
            const modal = document.createElement('div');
            modal.id = 'error-detail-modal';
            modal.className = 'modal-overlay hidden';
            modal.innerHTML = `
                <div class="modal-content error-modal">
                    <div class="modal-header error-header">
                        <h3>⚠️ Error Details</h3>
                        <button class="modal-close" onclick="ErrorTracker.closeModal()">×</button>
                    </div>
                    <div class="modal-body"></div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="ErrorTracker.copyError()">📋 Copy Error</button>
                        <button class="btn btn-primary" onclick="ErrorTracker.refreshPage()">🔄 Refresh Page</button>
                        <button class="btn btn-warning" onclick="ErrorTracker.reportError()">📨 Report Issue</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            
            const style = document.createElement('style');
            style.textContent = `
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.7);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 10000;
                    animation: fadeIn 0.3s ease;
                }
                .modal-overlay.hidden {
                    display: none;
                }
                .modal-content {
                    background: white;
                    border-radius: 12px;
                    width: 90%;
                    max-width: 700px;
                    max-height: 80vh;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                    animation: slideUp 0.3s ease;
                }
                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .modal-header {
                    padding: 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .modal-header.error-header {
                    background: linear-gradient(135deg, #dc3545, #c82333);
                    color: white;
                }
                .modal-header h3 {
                    margin: 0;
                    font-size: 18px;
                }
                .modal-close {
                    background: none;
                    border: none;
                    color: white;
                    font-size: 28px;
                    cursor: pointer;
                    line-height: 1;
                    opacity: 0.8;
                    transition: opacity 0.2s;
                }
                .modal-close:hover {
                    opacity: 1;
                }
                .modal-body {
                    padding: 20px;
                    overflow-y: auto;
                    flex: 1;
                }
                .modal-footer {
                    padding: 15px 20px;
                    border-top: 1px solid #eee;
                    display: flex;
                    gap: 10px;
                    justify-content: flex-end;
                    flex-wrap: wrap;
                }
                .error-section {
                    margin-bottom: 20px;
                    padding: 15px;
                    background: #f8f9fa;
                    border-radius: 8px;
                }
                .error-section h4 {
                    margin: 0 0 10px 0;
                    color: #333;
                    font-size: 14px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .error-section.error .error-title {
                    color: #dc3545;
                    font-size: 16px;
                    margin-bottom: 10px;
                }
                .error-detail-row {
                    display: flex;
                    margin-bottom: 8px;
                    font-size: 13px;
                }
                .error-detail-label {
                    font-weight: 600;
                    color: #666;
                    width: 140px;
                    flex-shrink: 0;
                }
                .error-detail-value {
                    color: #333;
                    word-break: break-all;
                }
                .stack-trace {
                    background: #2d2d2d;
                    color: #f8f8f2;
                    padding: 15px;
                    border-radius: 8px;
                    font-family: 'Monaco', 'Menlo', monospace;
                    font-size: 12px;
                    line-height: 1.5;
                    overflow-x: auto;
                    white-space: pre-wrap;
                }
                .browser-info-grid {
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 8px;
                }
                .browser-info-item {
                    font-size: 12px;
                }
                .btn {
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                    transition: all 0.2s;
                }
                .btn-primary {
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                }
                .btn-primary:hover {
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                }
                .btn-secondary {
                    background: #6c757d;
                    color: white;
                }
                .btn-secondary:hover {
                    background: #5a6268;
                }
                .btn-warning {
                    background: #ffc107;
                    color: #212529;
                }
                .btn-warning:hover {
                    background: #e0a800;
                }
                .severity-badge {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    text-transform: uppercase;
                }
                .severity-badge.error {
                    background: #dc3545;
                    color: white;
                }
                .severity-badge.warning {
                    background: #ffc107;
                    color: #212529;
                }
                .severity-badge.info {
                    background: #17a2b8;
                    color: white;
                }
            `;
            document.head.appendChild(style);
            
            return modal;
        },
        
        formatErrorDetails(logEntry) {
            const { timestamp, category, severity, errorData, browserInfo, actionStack, pageInfo } = logEntry;
            
            let html = `
                <div class="error-section error">
                    <div class="error-title">
                        <span class="severity-badge ${severity}">${severity.toUpperCase()}</span>
                        <span style="margin-left: 10px;">${category.replace(/_/g, ' ').toUpperCase()}</span>
                    </div>
                </div>
                
                <div class="error-section">
                    <h4>⏰ Timestamp</h4>
                    <div class="error-detail-row">
                        <span class="error-detail-label">Time:</span>
                        <span class="error-detail-value">${timestamp}</span>
                    </div>
                </div>
            `;
            
            if (errorData.message) {
                html += `
                    <div class="error-section">
                        <h4>❌ Error Message</h4>
                        <div class="error-detail-row">
                            <span class="error-detail-label">Message:</span>
                            <span class="error-detail-value">${this.escapeHtml(errorData.message)}</span>
                        </div>
                        ${errorData.errorType ? `
                        <div class="error-detail-row">
                            <span class="error-detail-label">Type:</span>
                            <span class="error-detail-value">${errorData.errorType}</span>
                        </div>
                        ` : ''}
                        ${errorData.lineno ? `
                        <div class="error-detail-row">
                            <span class="error-detail-label">Location:</span>
                            <span class="error-detail-value">${this.escapeHtml(errorData.source || 'Unknown')}:${errorData.lineno}:${errorData.colno}</span>
                        </div>
                        ` : ''}
                    </div>
                `;
            }
            
            if (errorData.stack) {
                html += `
                    <div class="error-section">
                        <h4>📋 Stack Trace</h4>
                        <pre class="stack-trace">${this.escapeHtml(errorData.stack)}</pre>
                    </div>
                `;
            }
            
            if (actionStack && actionStack.length > 0) {
                html += `
                    <div class="error-section">
                        <h4>🔄 User Action Path</h4>
                        ${actionStack.map(action => `
                            <div class="error-detail-row">
                                <span class="error-detail-label">${action.timestamp}</span>
                                <span class="error-detail-value">${action.action}</span>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
            
            if (browserInfo) {
                html += `
                    <div class="error-section">
                        <h4>🌐 Browser Environment</h4>
                        <div class="browser-info-grid">
                            <div class="browser-info-item">
                                <strong>Browser:</strong> ${browserInfo.browser} ${browserInfo.version}
                            </div>
                            <div class="browser-info-item">
                                <strong>OS:</strong> ${browserInfo.os}
                            </div>
                            <div class="browser-info-item">
                                <strong>Platform:</strong> ${browserInfo.platform}
                            </div>
                            <div class="browser-info-item">
                                <strong>Language:</strong> ${browserInfo.language}
                            </div>
                            <div class="browser-info-item">
                                <strong>Screen:</strong> ${browserInfo.screenResolution}
                            </div>
                            <div class="browser-info-item">
                                <strong>Window:</strong> ${browserInfo.windowSize}
                            </div>
                            <div class="browser-info-item">
                                <strong>Cookies:</strong> ${browserInfo.cookiesEnabled ? 'Yes' : 'No'}
                            </div>
                            <div class="browser-info-item">
                                <strong>DNT:</strong> ${browserInfo.doNotTrack || 'Not set'}
                            </div>
                        </div>
                    </div>
                `;
            }
            
            html += `
                <div class="error-section">
                    <h4>📄 Page Information</h4>
                    <div class="error-detail-row">
                        <span class="error-detail-label">URL:</span>
                        <span class="error-detail-value">${this.escapeHtml(pageInfo.url)}</span>
                    </div>
                    <div class="error-detail-row">
                        <span class="error-detail-label">User Agent:</span>
                        <span class="error-detail-value" style="font-size: 11px;">${this.escapeHtml(pageInfo.userAgent)}</span>
                    </div>
                </div>
            `;
            
            return html;
        },
        
        escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        closeModal() {
            const modal = document.getElementById('error-detail-modal');
            if (modal) {
                modal.classList.add('hidden');
            }
        },
        
        copyError() {
            const modal = document.getElementById('error-detail-modal');
            const errorContent = modal?.querySelector('.modal-body')?.innerText;
            
            if (errorContent) {
                navigator.clipboard.writeText(errorContent).then(() => {
                    this.showToast('Error details copied to clipboard!');
                }).catch(() => {
                    this.showToast('Failed to copy error details');
                });
            }
        },
        
        refreshPage() {
            window.location.reload();
        },
        
        reportError() {
            const modal = document.getElementById('error-detail-modal');
            const errorContent = modal?.querySelector('.modal-body')?.innerText;
            
            const subject = encodeURIComponent('Quant Crawler Error Report');
            const body = encodeURIComponent(`Error Details:\n\n${errorContent}\n\nPlease investigate this issue.`);
            
            window.open(`mailto:support@quantcrawler.com?subject=${subject}&body=${body}`);
        },
        
        showToast(message) {
            let toast = document.getElementById('error-toast');
            if (!toast) {
                toast = document.createElement('div');
                toast.id = 'error-toast';
                toast.style.cssText = `
                    position: fixed;
                    bottom: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #333;
                    color: white;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-size: 14px;
                    z-index: 10001;
                    animation: fadeInUp 0.3s ease;
                `;
                document.body.appendChild(toast);
                
                const style = document.createElement('style');
                style.textContent = `
                    @keyframes fadeInUp {
                        from { opacity: 0; transform: translate(-50%, 20px); }
                        to { opacity: 1; transform: translate(-50%, 0); }
                    }
                `;
                document.head.appendChild(style);
            }
            
            toast.textContent = message;
            toast.style.display = 'block';
            
            setTimeout(() => {
                toast.style.display = 'none';
            }, 3000);
        },
        
        async reportErrorToBackend(logEntry) {
            try {
                await fetch('/api/error-report', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        ...logEntry,
                        reportedAt: this.getTimestamp()
                    })
                });
            } catch (e) {
                console.error('Failed to report error to backend:', e);
            }
        },
        
        getRecentLogs(limit = 10) {
            try {
                const logs = JSON.parse(localStorage.getItem('errorLogs') || '[]');
                return logs.slice(0, limit);
            } catch (e) {
                return [];
            }
        },
        
        clearLogs() {
            localStorage.removeItem('errorLogs');
            this.logInfo('logs_cleared', { message: 'Error logs have been cleared' });
        }
    };
    
    window.ErrorTracker = ErrorTracker;
    ErrorTracker.init();
    
    // Stop polling when page unloads to prevent request conflicts
    window.addEventListener('beforeunload', () => {
        if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
        }
    });
    
    const tabBtns = document.querySelectorAll('.tab-btn');
    const modeContents = document.querySelectorAll('.mode-content');
    const singleDateInput = document.getElementById('single-date');
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    const submitBtn = document.getElementById('submit-btn');
    const statusArea = document.getElementById('status-area');
    const statusContent = document.getElementById('status-content');
    const recoveryActions = document.getElementById('recovery-actions');
    const retryBtn = document.getElementById('retry-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const cancelBtn = document.getElementById('cancel-btn');

    let currentMode = 'single';
    let currentJobId = null;
    let statusPollingInterval = null;
    let eventSource = null;  // SSE 连接
    let retryCount = 0;
    const MAX_RETRIES = 3;
    let lastDateArg = null;
    
    // SSE 日志缓冲区
    let logBuffer = [];
    const MAX_LOG_LINES = 500;  // 最大保留日志行数
    
    // 连接 SSE 流
    function connectEventSource(jobId, onComplete) {
        // 关闭已有连接
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        
        // 清空日志缓冲区
        logBuffer = [];
        
        // 检查浏览器是否支持 EventSource
        if (typeof EventSource === 'undefined') {
            console.log('浏览器不支持 EventSource，回退到轮询模式');
            return false;
        }
        
        try {
            eventSource = new EventSource(`/api/stream?job_id=${jobId}`);
            
            eventSource.onopen = function() {
                console.log(`[SSE] 连接到任务 ${jobId}`);
            };
            
            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    handleSSEMessage(data, jobId, onComplete);
                } catch (e) {
                    console.error('[SSE] 解析消息失败:', e);
                }
            };
            
            eventSource.onerror = function(error) {
                console.error('[SSE] 连接错误:', error);
                // 自动重连由 EventSource 原生支持
            };
            
            return true;
        } catch (e) {
            console.error('[SSE] 创建连接失败:', e);
            return false;
        }
    }
    
    // 处理 SSE 消息
    function handleSSEMessage(data, jobId, onComplete) {
        switch (data.type) {
            case 'log':
                // 添加日志到缓冲区
                appendLog(data.message);
                break;
                
            case 'progress':
                // 更新进度
                updateProgress(data.percent, data.api);
                break;
                
            case 'heartbeat':
                // 心跳，保持连接
                break;
                
            case 'completed':
                // 任务完成
                closeEventSource();
                if (onComplete) {
                    onComplete(data.success, data.message);
                }
                break;
                
            case 'error':
                // 任务错误
                closeEventSource();
                if (onComplete) {
                    onComplete(false, data.message);
                }
                break;
        }
    }
    
    // 添加日志（增量渲染）
    function appendLog(message) {
        logBuffer.push(message);
        
        // 限制日志行数，防止内存溢出
        if (logBuffer.length > MAX_LOG_LINES) {
            logBuffer.shift();  // 移除最旧的日志
        }
        
        // 更新显示
        renderLogContainer();
    }
    
    // 渲染日志容器（使用 insertAdjacentHTML 优化性能）
    function renderLogContainer() {
        // 查找或创建日志容器
        let logContainer = document.getElementById('log-container');
        if (!logContainer) {
            // 创建日志容器
            logContainer = document.createElement('div');
            logContainer.id = 'log-container';
            logContainer.className = 'log-container';
            logContainer.style.cssText = `
                max-height: 400px;
                overflow-y: auto;
                background: #1a1a2e;
                border-radius: 8px;
                padding: 12px;
                margin-top: 12px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.5;
                color: #a0a0b0;
                contain: content;
            `;
            
            // 插入到状态内容中
            const existingPre = statusContent.querySelector('pre');
            if (existingPre) {
                existingPre.replaceWith(logContainer);
            } else {
                statusContent.appendChild(logContainer);
            }
        }
        
        // 只渲染最后 100 行（虚拟滚动效果）
        const displayLines = logBuffer.slice(-100);
        const html = displayLines.map(line => `<div class="log-line">${escapeHtml(line)}</div>`).join('');
        
        // 使用 innerHTML 一次性更新（比 insertAdjacentHTML 更高效）
        logContainer.innerHTML = html;
        
        // 自动滚动到底部
        logContainer.scrollTop = logContainer.scrollHeight;
    }
    
    // HTML 转义
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // 更新进度
    function updateProgress(percent, api) {
        let progressContainer = document.getElementById('progress-container');
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.id = 'progress-container';
            progressContainer.innerHTML = `
                <div class="progress-container">
                    <div class="progress-bar" id="progress-bar" style="width: 0%"></div>
                </div>
                <div class="progress-text" id="progress-text">进度: 0%</div>
                <div class="current-api" id="current-api"></div>
            `;
            statusContent.insertBefore(progressContainer, statusContent.firstChild);
        }
        
        const bar = document.getElementById('progress-bar');
        const text = document.getElementById('progress-text');
        const apiDiv = document.getElementById('current-api');
        
        if (bar) bar.style.width = `${percent}%`;
        if (text) text.textContent = `进度: ${percent}%`;
        if (apiDiv && api) apiDiv.textContent = `🔄 正在爬取: ${api}`;
    }
    
    // 关闭 SSE 连接
    function closeEventSource() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
            console.log('[SSE] 连接已关闭');
        }
    }

    const today = new Date().toISOString().split('T')[0];
    singleDateInput.value = today;
    startDateInput.value = today;
    endDateInput.value = today;

    function showErrorBanner(message) {
        const banner = document.getElementById('error-banner');
        const messageEl = document.getElementById('error-message');
        messageEl.textContent = message;
        banner.classList.remove('hidden');
    }

    function hideErrorBanner() {
        const banner = document.getElementById('error-banner');
        banner.classList.add('hidden');
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const mode = this.dataset.mode;
            ErrorTracker.pushAction(`switch_to_${mode}_mode`);

            tabBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            modeContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${mode}-mode`) {
                    content.classList.add('active');
                }
            });

            currentMode = mode;
            hideStatus();
            hideErrorBanner();
        });
    });

    function validateDates() {
        const startDate = new Date(startDateInput.value);
        const endDate = new Date(endDateInput.value);

        if (startDate > endDate) {
            return { valid: false, message: '开始日期不能晚于结束日期' };
        }

        return { valid: true };
    }

    function validateSingleDate() {
        const dateValue = singleDateInput.value;
        if (!dateValue) {
            return { valid: false, message: '请选择日期' };
        }

        const date = new Date(dateValue);
        if (isNaN(date.getTime())) {
            return { valid: false, message: '日期格式无效' };
        }

        return { valid: true };
    }

    function showStatus(type, message, details = null) {
        statusArea.classList.remove('hidden');
        recoveryActions.classList.add('hidden');
        
        let html = `<div class="${type}">${message}</div>`;

        if (details) {
            html += `<pre>${details}</pre>`;
        }

        statusContent.innerHTML = html;
    }

    function hideStatus() {
        statusArea.classList.add('hidden');
        statusContent.innerHTML = '';
        recoveryActions.classList.add('hidden');
        
        // 关闭 SSE 连接
        closeEventSource();
        
        if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
        }
        currentJobId = null;
        retryCount = 0;
        logBuffer = [];
    }

    function buildCommand() {
        if (currentMode === 'single') {
            const validation = validateSingleDate();
            if (!validation.valid) {
                ErrorTracker.captureError('validation_error', {
                    message: validation.message,
                    field: 'single-date',
                    value: singleDateInput.value
                });
                throw new Error(validation.message);
            }
            return singleDateInput.value;
        } else {
            const validation = validateDates();
            if (!validation.valid) {
                ErrorTracker.captureError('validation_error', {
                    message: validation.message,
                    field: 'date-range',
                    startDate: startDateInput.value,
                    endDate: endDateInput.value
                });
                throw new Error(validation.message);
            }
            return `${startDateInput.value}-${endDateInput.value}`;
        }
    }

    async function fetchWithTimeout(url, options, timeout = 30000) {
        const controller = new AbortController();
        let timeoutId = null;
        
        const cleanup = () => {
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
        };
        
        timeoutId = setTimeout(() => {
            try {
                controller.abort();
            } catch (e) {
                // Ignore abort errors during cleanup
            }
        }, timeout);

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            cleanup();
            return response;
        } catch (error) {
            cleanup();
            
            // Provide more descriptive error message
            let enhancedMessage = error.message;
            let errorCategory = 'network_error';
            
            if (error.name === 'AbortError') {
                if (error.message === 'signal is aborted without reason' || !error.message) {
                    enhancedMessage = `Request to ${url} timed out after ${timeout}ms. The server may be busy or not responding.`;
                    errorCategory = 'timeout_error';
                } else {
                    enhancedMessage = `Request to ${url} was cancelled: ${error.message}`;
                    errorCategory = 'request_cancelled';
                }
            } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
                enhancedMessage = `Network error: Unable to connect to ${url}. Please check your network connection.`;
                errorCategory = 'network_error';
            }
            
            ErrorTracker.captureError(errorCategory, {
                url,
                message: enhancedMessage,
                name: error.name,
                stack: error.stack,
                timeout,
                originalMessage: error.message
            });
            
            // Create a new error with enhanced message
            const enhancedError = new Error(enhancedMessage);
            enhancedError.name = error.name;
            enhancedError.url = url;
            enhancedError.timeout = timeout;
            
            throw enhancedError;
        }
    }

    async function checkJobStatus(jobId) {
        try {
            const response = await fetchWithTimeout(`/api/status?job_id=${jobId}`, 5000);
            
            if (!response.ok) {
                ErrorTracker.captureError('api_error', {
                    url: `/api/status?job_id=${jobId}`,
                    status: response.status,
                    statusText: response.statusText
                });
                throw new Error(`HTTP ${response.status}: Failed to check job status`);
            }

            const result = await response.json();

            if (result.success && result.job) {
                const job = result.job;

                if (job.status === 'running') {
                    // 显示进度信息
                    let statusHtml = '';
                    
                    // 进度条
                    const progress = job.progress_percent || 0;
                    statusHtml += `
                        <div class="progress-container">
                            <div class="progress-bar" style="width: ${progress}%"></div>
                        </div>
                        <div class="progress-text">进度: ${progress}%</div>
                    `;
                    
                    // 当前正在爬取的 API
                    if (job.current_api) {
                        statusHtml += `<div class="current-api">🔄 正在爬取: ${job.current_api}</div>`;
                    }
                    
                    // 显示最后几行输出
                    const output = job.output || 'Crawler is running...';
                    statusHtml += `<pre>${output}</pre>`;
                    
                    statusArea.classList.remove('hidden');
                    statusContent.innerHTML = `<div class="info">正在运行... 任务ID: ${jobId}</div>${statusHtml}`;
                    recoveryActions.classList.add('hidden');
                } else if (job.status === 'completed') {
                    clearInterval(statusPollingInterval);
                    statusPollingInterval = null;

                    if (job.success) {
                        showStatus('success', '爬取完成！', job.output || '完成');
                        recoveryActions.classList.add('hidden');
                    } else {
                        ErrorTracker.captureError('job_failure', {
                            jobId,
                            output: job.output,
                            success: job.success
                        });
                        showStatus('error', '爬取失败', job.output || '未知错误');
                        showRecoveryActions('retry', 'cancel');
                    }

                    submitBtn.disabled = false;
                    submitBtn.textContent = '开始爬取';
                }
            } else {
                throw new Error(result.error || 'Invalid job response');
            }
        } catch (error) {
            ErrorTracker.captureError('status_check_error', {
                jobId,
                message: error.message,
                name: error.name,
                stack: error.stack
            });
            console.error('Status check error:', error);
        }
    }

    function showRecoveryActions(...actions) {
        recoveryActions.classList.remove('hidden');
        
        retryBtn.style.display = actions.includes('retry') ? 'block' : 'none';
        refreshBtn.style.display = actions.includes('refresh') ? 'block' : 'none';
        cancelBtn.style.display = actions.includes('cancel') ? 'block' : 'none';
    }

    async function handleSubmit() {
        ErrorTracker.pushAction('click_submit_button');
        
        try {
            submitBtn.disabled = true;
            submitBtn.textContent = '启动中...';
            hideStatus();
            hideErrorBanner();

            const dateArg = buildCommand();
            lastDateArg = dateArg;
            ErrorTracker.pushAction(`submit_with_date_${dateArg}`);
            showStatus('info', `开始爬取: ${dateArg}`);

            console.log('Sending request to /api/run with date:', dateArg);

            const response = await fetchWithTimeout('/api/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    date: dateArg
                })
            }, 10000);

            console.log('Response received:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                ErrorTracker.captureError('api_error', {
                    url: '/api/run',
                    status: response.status,
                    statusText: response.statusText,
                    responseBody: errorText,
                    requestData: { date: dateArg }
                });
                throw new Error(`HTTP error: ${response.status}`);
            }

            const result = await response.json();
            console.log('Server response:', result);

            if (result.success) {
                currentJobId = result.job_id;
                retryCount = 0;
                ErrorTracker.logInfo('job_started', { job_id: currentJobId, date: dateArg });
                showStatus('info', `爬取已开始! 任务ID: ${currentJobId}`, '正在后台运行...');

                submitBtn.textContent = '运行中...';
                
                // 尝试使用 SSE 连接
                const sseConnected = connectEventSource(currentJobId, (success, message) => {
                    // SSE 完成回调
                    if (success) {
                        showStatus('success', '爬取完成！', message);
                        recoveryActions.classList.add('hidden');
                    } else {
                        ErrorTracker.captureError('job_failure', {
                            jobId: currentJobId,
                            message: message,
                            success: false
                        });
                        showStatus('error', '爬取失败', message || '未知错误');
                        showRecoveryActions('retry', 'cancel');
                    }
                    
                    submitBtn.disabled = false;
                    submitBtn.textContent = '开始爬取';
                });
                
                // 如果 SSE 连接失败，回退到轮询模式
                if (!sseConnected) {
                    console.log('SSE 连接失败，使用轮询模式');
                    statusPollingInterval = setInterval(() => {
                        if (currentJobId) {
                            checkJobStatus(currentJobId);
                        }
                    }, 2000);
                }
            } else {
                ErrorTracker.captureError('api_business_error', {
                    url: '/api/run',
                    error: result.error,
                    requestData: { date: dateArg },
                    response: result
                });
                throw new Error(result.error || 'Unknown error from server');
            }

        } catch (error) {
            ErrorTracker.captureError('submit_error', {
                message: error.message,
                name: error.name,
                stack: error.stack,
                dateArg: lastDateArg,
                retryCount
            });
            
            console.error('Error:', error);

            if (error.name === 'AbortError') {
                showErrorBanner('请求超时，服务器可能繁忙或无响应');
                showStatus('error', '请求超时', '服务器在10秒内未响应');
                showRecoveryActions('retry');
            } else if (error.message.includes('Failed to fetch')) {
                showErrorBanner('网络错误，请检查网络连接');
                showStatus('error', '网络错误', error.message);
                showRecoveryActions('retry', 'refresh');
            } else {
                showErrorBanner('发生错误，点击查看详情');
                showStatus('error', `错误: ${error.message}`);
                showRecoveryActions('retry', 'cancel');
                
                document.getElementById('error-banner').onclick = () => {
                    const recentLogs = ErrorTracker.getRecentLogs(1);
                    if (recentLogs.length > 0) {
                        ErrorTracker.displayErrorModal(recentLogs[0]);
                    }
                };
            }

            submitBtn.disabled = false;
            submitBtn.textContent = '开始爬取';
        }
    }

    submitBtn.addEventListener('click', handleSubmit);

    retryBtn.addEventListener('click', function() {
        ErrorTracker.pushAction('click_retry_button');
        retryCount++;
        if (retryCount <= MAX_RETRIES) {
            console.log(`重试 ${retryCount}/${MAX_RETRIES}`);
            handleSubmit();
        } else {
            ErrorTracker.captureError('max_retries_exceeded', {
                retryCount,
                lastDateArg
            });
            showErrorBanner('已达到最大重试次数，请稍后重试');
            showRecoveryActions('refresh', 'cancel');
        }
    });

    refreshBtn.addEventListener('click', function() {
        ErrorTracker.pushAction('click_refresh_button');
        if (currentJobId) {
            checkJobStatus(currentJobId);
        } else {
            window.location.reload();
        }
    });

    cancelBtn.addEventListener('click', function() {
        ErrorTracker.pushAction('click_cancel_button');
        hideStatus();
        hideErrorBanner();
        submitBtn.disabled = false;
        submitBtn.textContent = '开始爬取';
    });

    // Clean & Push functionality
    const cleanDateInput = document.getElementById('clean-date');
    const cleanPushBtn = document.getElementById('clean-push-btn');

    // Set default date for clean & push
    cleanDateInput.value = today;

    async function handleCleanAndPush() {
        ErrorTracker.pushAction('click_clean_push_button');

        const dateValue = cleanDateInput.value;
        if (!dateValue) {
            showErrorBanner('请选择清洗推送的日期');
            return;
        }

        try {
            cleanPushBtn.disabled = true;
            cleanPushBtn.textContent = '处理中...';
            hideStatus();
            hideErrorBanner();

            showStatus('info', `开始清洗推送: ${dateValue}`);

            console.log('Sending request to /api/clean-and-push with date:', dateValue);

            const response = await fetchWithTimeout('/api/clean-and-push', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    date: dateValue
                })
            }, 15000);  // 15秒应该足够，因为飞书推送已改为异步执行

            console.log('Response received:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                ErrorTracker.captureError('api_error', {
                    url: '/api/clean-and-push',
                    status: response.status,
                    statusText: response.statusText,
                    responseBody: errorText,
                    requestData: { date: dateValue }
                });
                throw new Error(`HTTP error: ${response.status}`);
            }

            const result = await response.json();
            console.log('Server response:', result);

            if (result.success) {
                currentJobId = result.job_id;
                retryCount = 0;
                ErrorTracker.logInfo('clean_push_started', { job_id: currentJobId, date: dateValue });
                showStatus('info', `清洗推送已开始! 任务ID: ${currentJobId}`, '正在后台处理...');

                cleanPushBtn.textContent = '处理中...';
                
                // 尝试使用 SSE 连接
                const sseConnected = connectEventSource(currentJobId, (success, message) => {
                    // SSE 完成回调
                    if (success) {
                        showStatus('success', '清洗推送完成！', message);
                        recoveryActions.classList.add('hidden');
                        // 复制报告内容到剪贴板（传入日期）
                        copyReportToClipboard(dateValue);
                    } else {
                        ErrorTracker.captureError('clean_push_failure', {
                            jobId: currentJobId,
                            message: message,
                            success: false
                        });
                        showStatus('error', '清洗推送失败', message || '未知错误');
                        showRecoveryActions('retry', 'cancel');
                    }
                    
                    cleanPushBtn.disabled = false;
                    cleanPushBtn.textContent = '🚀 清洗并推送到飞书';
                });
                
                // 如果 SSE 连接失败，回退到轮询模式
                if (!sseConnected) {
                    console.log('SSE 连接失败，使用轮询模式');
                    statusPollingInterval = setInterval(() => {
                        if (currentJobId) {
                            checkCleanPushStatus(currentJobId);
                        }
                    }, 2000);
                }
            } else {
                ErrorTracker.captureError('api_business_error', {
                    url: '/api/clean-and-push',
                    error: result.error,
                    requestData: { date: dateValue },
                    response: result
                });
                throw new Error(result.error || 'Unknown error from server');
            }

        } catch (error) {
            ErrorTracker.captureError('clean_push_error', {
                message: error.message,
                name: error.name,
                stack: error.stack,
                dateValue: dateValue
            });

            console.error('Error:', error);

            if (error.name === 'AbortError') {
                showErrorBanner('请求超时，服务器可能繁忙或无响应');
                showStatus('error', '请求超时', '服务器在10秒内未响应');
            } else if (error.message.includes('Failed to fetch')) {
                showErrorBanner('网络错误，请检查网络连接');
                showStatus('error', '网络错误', error.message);
            } else {
                showErrorBanner('清洗推送过程中发生错误');
                showStatus('error', `错误: ${error.message}`);
            }

            cleanPushBtn.disabled = false;
            cleanPushBtn.textContent = '🚀 清洗并推送到飞书';
        }
    }

    async function checkCleanPushStatus(jobId) {
        try {
            const response = await fetchWithTimeout(`/api/status?job_id=${jobId}`, {}, 5000);

            if (!response.ok) {
                ErrorTracker.captureError('api_error', {
                    url: `/api/status?job_id=${jobId}`,
                    status: response.status,
                    statusText: response.statusText
                });
                throw new Error(`HTTP ${response.status}: Failed to check job status`);
            }

            const result = await response.json();

            if (result.success && result.job) {
                const job = result.job;

                if (job.status === 'running') {
                    // 显示进度信息
                    let statusHtml = '';

                    // 进度条
                    const progress = job.progress_percent || 0;
                    statusHtml += `
                        <div class="progress-container">
                            <div class="progress-bar" style="width: ${progress}%"></div>
                        </div>
                        <div class="progress-text">进度: ${progress}%</div>
                    `;

                    // 显示最后几行输出
                    const output = job.output || '处理中...';
                    statusHtml += `<pre>${output}</pre>`;

                    statusArea.classList.remove('hidden');
                    statusContent.innerHTML = `<div class="info">清洗推送运行中... 任务ID: ${jobId}</div>${statusHtml}`;
                    recoveryActions.classList.add('hidden');
                } else if (job.status === 'completed') {
                    clearInterval(statusPollingInterval);
                    statusPollingInterval = null;

                    if (job.success) {
                        showStatus('success', '清洗推送完成！', job.output || '完成');
                        recoveryActions.classList.add('hidden');
                        
                        // 复制报告内容到剪贴板（传入日期）
                        copyReportToClipboard(job.date);
                    } else {
                        ErrorTracker.captureError('clean_push_failure', {
                            jobId,
                            output: job.output,
                            success: job.success
                        });
                        showStatus('error', '清洗推送失败', job.output || '未知错误');
                        showRecoveryActions('retry', 'cancel');
                    }

                    cleanPushBtn.disabled = false;
                    cleanPushBtn.textContent = '🚀 清洗并推送到飞书';
                }
            } else {
                throw new Error(result.error || '无效的任务响应');
            }
        } catch (error) {
            ErrorTracker.captureError('status_check_error', {
                jobId,
                message: error.message,
                name: error.name,
                stack: error.stack
            });
            console.error('Status check error:', error);
        }
    }

    // 复制报告内容到剪贴板
    async function copyReportToClipboard(date) {
        try {
            if (!date) {
                console.log('没有指定日期，无法复制报告');
                return;
            }
            
            // 从服务器获取报告内容
            const response = await fetchWithTimeout(`/api/report?date=${date}`, {}, 5000);
            
            if (!response.ok) {
                throw new Error(`获取报告失败: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (!result.success || !result.content) {
                console.log('报告内容为空或获取失败');
                return;
            }
            
            // 使用 Clipboard API 复制到剪贴板
            await navigator.clipboard.writeText(result.content);
            
            // 显示复制成功提示
            showCopySuccessNotification();
            
            ErrorTracker.logInfo('clipboard_copy_success', {
                contentLength: result.content.length,
                date: date
            });
        } catch (error) {
            console.error('复制到剪贴板失败:', error);
            ErrorTracker.captureError('clipboard_copy_failed', {
                message: error.message,
                name: error.name,
                date: date
            });
            // 复制失败不影响主流程，静默处理
        }
    }
    
    // 显示复制成功提示
    function showCopySuccessNotification() {
        // 创建提示元素
        const notification = document.createElement('div');
        notification.className = 'copy-notification';
        notification.innerHTML = `
            <span class="copy-icon">📋</span>
            <span class="copy-text">报告已复制到剪贴板</span>
        `;
        
        // 添加样式
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            font-weight: 500;
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
        `;
        
        // 添加动画样式
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
        
        // 添加到页面
        document.body.appendChild(notification);
        
        // 3秒后自动移除
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => {
                notification.remove();
                style.remove();
            }, 300);
        }, 3000);
    }

    cleanPushBtn.addEventListener('click', handleCleanAndPush);

    ErrorTracker.logInfo('app_initialized', {
        mode: 'single',
        defaultDate: today
    });
});
