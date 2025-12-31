import React, { useState, useEffect, useRef } from 'react'
import { BarChart3, RefreshCw, ExternalLink, AlertTriangle, CheckCircle2 } from 'lucide-react'

function AimVisualization() {
  const [aimUrl, setAimUrl] = useState('http://localhost:43800')
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [loadSuccess, setLoadSuccess] = useState(false)
  const iframeRef = useRef(null)
  const timeoutRef = useRef(null)

  const checkIframeLoad = () => {
    setIsLoading(true)
    setLoadError(false)
    setLoadSuccess(false)

    // 设置超时检测（10秒）
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    timeoutRef.current = setTimeout(() => {
      // 检查 iframe 是否成功加载
      try {
        const iframe = iframeRef.current
        if (iframe) {
          // 尝试访问 iframe 内容（可能会因为跨域失败，这是正常的）
          try {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
            if (!iframeDoc) {
              // 跨域情况下无法访问，但可能已经加载成功
              // 我们假设如果超时后没有明显错误，就是加载成功
              setLoadSuccess(true)
            } else {
              setLoadSuccess(true)
            }
          } catch (e) {
            // 跨域错误是正常的，不一定是加载失败
            // 如果 Aim 服务运行正常，即使跨域也会显示内容
            setLoadSuccess(true)
          }
        }
        setIsLoading(false)
      } catch (error) {
        setLoadError(true)
        setIsLoading(false)
      }
    }, 10000) // 10秒超时
  }

  const handleRefresh = () => {
    if (iframeRef.current) {
      iframeRef.current.src = aimUrl
    }
    checkIframeLoad()
  }

  const handleOpenInNewTab = () => {
    window.open(aimUrl, '_blank')
  }

  useEffect(() => {
    // 当 URL 改变时重新加载
    if (iframeRef.current) {
      iframeRef.current.src = aimUrl
      checkIframeLoad()
    }
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aimUrl])

  const handleIframeLoad = () => {
    setIsLoading(false)
    // 检查 iframe 是否真的加载成功
    try {
      const iframe = iframeRef.current
      if (iframe) {
        // 尝试访问内容（可能会因为跨域失败，这是正常的）
        try {
          const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
          if (iframeDoc && iframeDoc.body) {
            // 成功访问到内容
            setLoadSuccess(true)
            setLoadError(false)
          } else {
            // 跨域情况，假设加载成功
            setLoadSuccess(true)
            setLoadError(false)
          }
        } catch (e) {
          // 跨域错误，但 iframe 可能已加载
          // 设置一个延迟检查，如果 iframe 有内容就认为成功
          setTimeout(() => {
            try {
              const iframe = iframeRef.current
              if (iframe && iframe.contentWindow) {
                setLoadSuccess(true)
                setLoadError(false)
              }
            } catch (err) {
              // 仍然无法访问，但可能是跨域，不标记为错误
              setLoadSuccess(true)
              setLoadError(false)
            }
          }, 1000)
        }
      }
    } catch (error) {
      // 如果出现错误，可能是连接失败
      setLoadError(true)
      setLoadSuccess(false)
    }
    
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
  }
  
  const handleIframeError = () => {
    setIsLoading(false)
    setLoadError(true)
    setLoadSuccess(false)
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
          <BarChart3 className="w-5 h-5 text-green-400" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-dark-text">可视化监控</h2>
          <p className="text-sm text-dark-text-muted">Aim Stack 实验追踪与可视化</p>
        </div>
      </div>

      {/* Control Panel */}
      <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-dark-text">Aim URL</label>
            <input
              type="text"
              value={aimUrl}
              onChange={(e) => setAimUrl(e.target.value)}
              placeholder="http://localhost:43800"
              className="px-3 py-2 bg-dark-bg border border-dark-border rounded-md text-sm text-dark-text focus:outline-none focus:ring-2 focus:ring-green-500/50 w-64"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              className="px-4 py-2 bg-dark-border hover:bg-dark-border/80 text-dark-text rounded-md text-sm font-medium transition-colors flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              刷新
            </button>
            <button
              onClick={handleOpenInNewTab}
              className="px-4 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-400 rounded-md text-sm font-medium transition-colors flex items-center gap-2"
            >
              <ExternalLink className="w-4 h-4" />
              新窗口打开
            </button>
          </div>
        </div>
      </div>

      {/* IFrame Container */}
      <div className="bg-dark-surface border border-dark-border rounded-lg overflow-hidden relative" style={{ height: '800px' }}>
        <iframe
          ref={iframeRef}
          src={aimUrl}
          className="w-full h-full border-0"
          title="Aim Stack Visualization"
          onLoad={handleIframeLoad}
          onError={handleIframeError}
        />
        
        {/* Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-dark-surface/90 backdrop-blur-sm flex items-center justify-center z-10">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 text-blue-400 animate-spin mx-auto mb-2" />
              <p className="text-sm text-dark-text">正在加载 Aim Stack UI...</p>
              <p className="text-xs text-dark-text-muted mt-1">如果长时间无法加载，请检查 Aim 服务是否运行</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {loadError && !isLoading && (
          <div className="absolute inset-0 bg-dark-surface flex items-center justify-center z-10">
            <div className="text-center max-w-md px-6">
              <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-dark-text mb-2">无法连接到 Aim Stack</h3>
              <p className="text-sm text-dark-text-muted mb-4">
                Aim Stack 服务未运行在 <code className="text-blue-400">{aimUrl}</code>
              </p>
              <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 mb-4 text-left">
                <p className="text-xs text-yellow-400 font-medium mb-2">快速启动步骤：</p>
                <ol className="text-xs text-dark-text-muted space-y-1 list-decimal list-inside">
                  <li>安装 Aim: <code className="text-yellow-400">pip install aim</code></li>
                  <li>启动服务: <code className="text-yellow-400">aim up --port 43800</code></li>
                  <li>等待几秒后刷新此页面</li>
                </ol>
              </div>
              <div className="flex gap-2 justify-center">
                <button
                  onClick={handleRefresh}
                  className="px-4 py-2 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 rounded-md text-sm font-medium transition-colors flex items-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  重试
                </button>
                <button
                  onClick={handleOpenInNewTab}
                  className="px-4 py-2 bg-dark-border hover:bg-dark-border/80 text-dark-text rounded-md text-sm font-medium transition-colors flex items-center gap-2"
                >
                  <ExternalLink className="w-4 h-4" />
                  新窗口打开
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success Indicator */}
        {loadSuccess && !isLoading && (
          <div className="absolute top-4 right-4 bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-2 flex items-center gap-2 z-20">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <span className="text-xs text-green-400 font-medium">已连接</span>
          </div>
        )}
      </div>

      {/* Info Panel */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <BarChart3 className="w-5 h-5 text-blue-400 mt-0.5" />
          <div className="flex-1">
            <h3 className="text-sm font-medium text-blue-400 mb-1">使用说明</h3>
            <ul className="text-xs text-dark-text-muted space-y-1 list-disc list-inside">
              <li>确保 Aim Stack 服务正在运行（默认端口：43800）</li>
              <li><strong>安装 Aim:</strong> <code className="text-blue-400">pip install aim</code></li>
              <li><strong>启动 Aim:</strong> <code className="text-blue-400">aim up</code> 或 <code className="text-blue-400">aim up --port 43800</code></li>
              <li>在训练配置中启用 "Aim Logging" 开关以记录训练指标</li>
              <li>训练开始后，指标会自动同步到 Aim Stack</li>
              <li>如果无法加载，请检查 Aim 服务状态和 URL 配置，或尝试在新窗口打开</li>
            </ul>
            <div className="mt-3 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded text-xs">
              <strong className="text-yellow-400">提示：</strong> 如果看到连接被拒绝，说明 Aim 服务未启动。请先运行 <code className="text-yellow-400">aim up</code> 启动服务。
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AimVisualization

