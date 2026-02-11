import React, { useState } from 'react'
import { FileText, CheckCircle2, XCircle, Sparkles, AlertCircle } from 'lucide-react'

function DataPreparationPanel() {
  const [jsonlData, setJsonlData] = useState('')
  const [validationStatus, setValidationStatus] = useState(null)
  const [validationMessage, setValidationMessage] = useState('')
  const [isValidating, setIsValidating] = useState(false)
  const [isCleaning, setIsCleaning] = useState(false)

  const validateJSONL = (text) => {
    if (!text.trim()) {
      return { valid: false, message: '数据为空' }
    }

    const lines = text.trim().split('\n')
    let errorCount = 0
    const errors = []

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      if (!line) continue

      try {
        const parsed = JSON.parse(line)
        if (!parsed.messages || !Array.isArray(parsed.messages)) {
          errors.push(`第 ${i + 1} 行: 缺少 messages 字段或格式不正确`)
          errorCount++
        }
      } catch (e) {
        errors.push(`第 ${i + 1} 行: JSON 格式错误 - ${e.message}`)
        errorCount++
      }
    }

    if (errorCount === 0) {
      return { valid: true, message: `✅ 验证通过！共 ${lines.length} 条有效记录` }
    } else {
      return {
        valid: false,
        message: `❌ 发现 ${errorCount} 个错误`,
        errors: errors.slice(0, 5), // 只显示前5个错误
      }
    }
  }

  const handleValidate = async () => {
    setIsValidating(true)
    try {
      const response = await fetch('http://localhost:5001/api/data/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: jsonlData }),
      })

      if (!response.ok) {
        throw new Error('验证请求失败')
      }

      const result = await response.json()
      setValidationStatus(result.valid)
      
      // 如果有错误，保存错误信息
      if (!result.valid && result.errors) {
        setValidationMessage({
          message: result.message,
          errors: result.errors,
        })
      } else {
        setValidationMessage(result.message)
      }
    } catch (error) {
      setValidationStatus(false)
      setValidationMessage('验证请求失败: ' + error.message)
    } finally {
      setIsValidating(false)
    }
  }

  const handleCleanData = async () => {
    setIsCleaning(true)
    try {
      const response = await fetch('http://localhost:5001/api/data/clean', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: jsonlData }),
      })

      if (!response.ok) {
        throw new Error('清理请求失败')
      }

      const result = await response.json()
      
      if (result.success) {
        setJsonlData(result.cleaned_data)
        setValidationStatus(null)
        setValidationMessage('数据已清理完成')
      } else {
        setValidationMessage('清理失败: ' + (result.error || '未知错误'))
      }
    } catch (error) {
      setValidationMessage('清理请求失败: ' + error.message)
    } finally {
      setIsCleaning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
          <FileText className="w-5 h-5 text-blue-400" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-dark-text">数据整理面板</h2>
          <p className="text-sm text-dark-text-muted">编辑和验证 JSONL 格式的训练数据</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Editor Section */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-dark-surface border border-dark-border rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-dark-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-dark-text-muted" />
                <span className="text-sm font-medium text-dark-text">训练数据 (JSONL)</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleValidate}
                  disabled={isValidating}
                  className="px-3 py-1.5 text-xs font-medium bg-blue-500/10 text-blue-400 rounded-md hover:bg-blue-500/20 transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {isValidating ? '验证中...' : '验证格式'}
                </button>
                <button
                  onClick={handleCleanData}
                  disabled={isCleaning}
                  className="px-3 py-1.5 text-xs font-medium bg-purple-500/10 text-purple-400 rounded-md hover:bg-purple-500/20 transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {isCleaning ? '清理中...' : '洗数'}
                </button>
              </div>
            </div>
            <textarea
              value={jsonlData}
              onChange={(e) => setJsonlData(e.target.value)}
              placeholder='{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}'
              className="w-full h-[600px] bg-dark-bg text-dark-text p-4 font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50 scrollbar-thin"
            />
          </div>
        </div>

        {/* Validation Panel */}
        <div className="space-y-4">
          <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
            <div className="flex items-center gap-2 mb-4">
              <AlertCircle className="w-4 h-4 text-dark-text-muted" />
              <span className="text-sm font-medium text-dark-text">验证结果</span>
            </div>
            {validationStatus !== null && (
              <div
                className={`p-3 rounded-md ${
                  validationStatus
                    ? 'bg-green-500/10 border border-green-500/20'
                    : 'bg-red-500/10 border border-red-500/20'
                }`}
              >
                <div
                  className={`flex items-center gap-2 mb-2 ${
                    validationStatus ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {validationStatus ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : (
                    <XCircle className="w-4 h-4" />
                  )}
                  <span className="text-sm font-medium">
                    {typeof validationMessage === 'string' ? validationMessage : validationMessage?.message || '验证完成'}
                  </span>
                </div>
                {!validationStatus && validationMessage && typeof validationMessage === 'object' && validationMessage.errors && (
                  <div className="mt-2 space-y-1">
                    <p className="text-xs text-dark-text-muted">错误详情：</p>
                    <ul className="text-xs text-red-400 space-y-1 list-disc list-inside max-h-32 overflow-y-auto">
                      {validationMessage.errors.map((error, idx) => (
                        <li key={idx}>{error}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
            {validationStatus === null && (
              <p className="text-sm text-dark-text-muted">点击"验证格式"按钮检查数据</p>
            )}
          </div>

          <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
            <h3 className="text-sm font-medium text-dark-text mb-3">数据统计</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-dark-text-muted">总行数</span>
                <span className="text-dark-text font-mono">
                  {jsonlData.split('\n').filter((l) => l.trim()).length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-text-muted">字符数</span>
                <span className="text-dark-text font-mono">{jsonlData.length}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DataPreparationPanel

