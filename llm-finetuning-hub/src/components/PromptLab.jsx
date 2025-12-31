import React, { useState } from 'react'
import { Sparkles, Play, Copy, Check, AlertCircle } from 'lucide-react'

function PromptLab() {
  const [originalPrompt, setOriginalPrompt] = useState('')
  const [finetunedPrompt, setFinetunedPrompt] = useState('')
  const [originalResponse, setOriginalResponse] = useState('')
  const [finetunedResponse, setFinetunedResponse] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showDiff, setShowDiff] = useState(true)
  const [copied, setCopied] = useState({ original: false, finetuned: false })

  const handleCompare = async () => {
    if (!originalPrompt.trim() || !finetunedPrompt.trim()) {
      return
    }

    setIsLoading(true)
    setOriginalResponse('')
    setFinetunedResponse('')

    try {
      // 调用实际 API
      const [originalRes, finetunedRes] = await Promise.all([
        fetch('http://localhost:5001/api/predict', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: originalPrompt, use_finetuned: false }),
        }),
        fetch('http://localhost:5001/api/predict', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: finetunedPrompt, use_finetuned: true }),
        }),
      ])

      if (!originalRes.ok || !finetunedRes.ok) {
        throw new Error('预测请求失败')
      }

      const originalData = await originalRes.json()
      const finetunedData = await finetunedRes.json()

      setOriginalResponse(originalData.response || originalData.full_response || '无响应')
      setFinetunedResponse(finetunedData.response || finetunedData.full_response || '无响应')
    } catch (error) {
      console.error('预测失败:', error)
      setOriginalResponse('预测失败: ' + error.message)
      setFinetunedResponse('预测失败: ' + error.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text)
    setCopied({ ...copied, [type]: true })
    setTimeout(() => setCopied({ ...copied, [type]: false }), 2000)
  }

  const getDiffHighlight = (text1, text2) => {
    // 简单的差异高亮逻辑（实际应该使用更专业的 diff 库）
    // 这里使用字符级别的简单对比
    const chars1 = text1.split('')
    const chars2 = text2.split('')
    const maxLen = Math.max(chars1.length, chars2.length)
    const diff = []

    for (let i = 0; i < maxLen; i++) {
      if (i >= chars1.length) {
        diff.push({ char: chars2[i], type: 'added' })
      } else if (i >= chars2.length) {
        diff.push({ char: chars1[i], type: 'removed' })
      } else if (chars1[i] !== chars2[i]) {
        diff.push({ char: chars1[i], type: 'removed' })
        diff.push({ char: chars2[i], type: 'added' })
      } else {
        diff.push({ char: chars1[i], type: 'same' })
      }
    }

    return diff
  }

  const diffHighlight = showDiff && originalResponse && finetunedResponse
    ? getDiffHighlight(originalResponse, finetunedResponse)
    : null

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
          <Sparkles className="w-5 h-5 text-purple-400" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-dark-text">提示词对比实验室</h2>
          <p className="text-sm text-dark-text-muted">对比基座模型和微调模型的输出差异</p>
        </div>
      </div>

      {/* Prompt Input Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Original Prompt */}
        <div className="bg-dark-surface border border-dark-border rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-dark-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-dark-text">原始 Prompt</span>
              <span className="text-xs px-2 py-0.5 bg-blue-500/10 text-blue-400 rounded">基座模型</span>
            </div>
            <button
              onClick={() => handleCopy(originalPrompt, 'original')}
              className="p-1.5 hover:bg-dark-border rounded transition-colors"
            >
              {copied.original ? (
                <Check className="w-4 h-4 text-green-400" />
              ) : (
                <Copy className="w-4 h-4 text-dark-text-muted" />
              )}
            </button>
          </div>
          <textarea
            value={originalPrompt}
            onChange={(e) => setOriginalPrompt(e.target.value)}
            placeholder="输入原始提示词..."
            className="w-full h-48 bg-dark-bg text-dark-text p-4 font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50 scrollbar-thin"
          />
        </div>

        {/* Finetuned Prompt */}
        <div className="bg-dark-surface border border-dark-border rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-dark-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-dark-text">微调 Prompt</span>
              <span className="text-xs px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded">LoRA 模型</span>
            </div>
            <button
              onClick={() => handleCopy(finetunedPrompt, 'finetuned')}
              className="p-1.5 hover:bg-dark-border rounded transition-colors"
            >
              {copied.finetuned ? (
                <Check className="w-4 h-4 text-green-400" />
              ) : (
                <Copy className="w-4 h-4 text-dark-text-muted" />
              )}
            </button>
          </div>
          <textarea
            value={finetunedPrompt}
            onChange={(e) => setFinetunedPrompt(e.target.value)}
            placeholder="输入微调后的提示词..."
            className="w-full h-48 bg-dark-bg text-dark-text p-4 font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-500/50 scrollbar-thin"
          />
        </div>
      </div>

      {/* Compare Button */}
      <div className="flex items-center justify-center">
        <button
          onClick={handleCompare}
          disabled={isLoading || !originalPrompt.trim() || !finetunedPrompt.trim()}
          className={`
            px-6 py-3 rounded-lg font-medium text-white transition-all
            flex items-center gap-2
            ${
              isLoading || !originalPrompt.trim() || !finetunedPrompt.trim()
                ? 'bg-dark-border cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700'
            }
          `}
        >
          <Play className="w-5 h-5" />
          {isLoading ? '生成中...' : '开始对比'}
        </button>
      </div>

      {/* Response Comparison */}
      {(originalResponse || finetunedResponse) && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-dark-text">输出对比</h3>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showDiff}
                onChange={(e) => setShowDiff(e.target.checked)}
                className="w-4 h-4 rounded border-dark-border bg-dark-surface text-blue-500 focus:ring-blue-500"
              />
              <span className="text-sm text-dark-text-muted">高亮差异</span>
            </label>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Original Response */}
            <div className="bg-dark-surface border border-dark-border rounded-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-dark-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-dark-text">基座模型输出</span>
                </div>
                <button
                  onClick={() => handleCopy(originalResponse, 'original')}
                  className="p-1.5 hover:bg-dark-border rounded transition-colors"
                >
                  {copied.original ? (
                    <Check className="w-4 h-4 text-green-400" />
                  ) : (
                    <Copy className="w-4 h-4 text-dark-text-muted" />
                  )}
                </button>
              </div>
              <div className="p-4">
                {showDiff && diffHighlight ? (
                  <div className="text-sm font-mono whitespace-pre-wrap">
                    {diffHighlight.map((item, idx) => (
                      <span
                        key={idx}
                        className={
                          item.type === 'added'
                            ? 'bg-green-500/20 text-green-400'
                            : item.type === 'removed'
                            ? 'bg-red-500/20 text-red-400 line-through'
                            : 'text-dark-text'
                        }
                      >
                        {item.char}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-dark-text whitespace-pre-wrap font-mono">
                    {originalResponse}
                  </p>
                )}
              </div>
            </div>

            {/* Finetuned Response */}
            <div className="bg-dark-surface border border-dark-border rounded-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-dark-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-dark-text">微调模型输出</span>
                </div>
                <button
                  onClick={() => handleCopy(finetunedResponse, 'finetuned')}
                  className="p-1.5 hover:bg-dark-border rounded transition-colors"
                >
                  {copied.finetuned ? (
                    <Check className="w-4 h-4 text-green-400" />
                  ) : (
                    <Copy className="w-4 h-4 text-dark-text-muted" />
                  )}
                </button>
              </div>
              <div className="p-4">
                {showDiff && diffHighlight ? (
                  <div className="text-sm font-mono whitespace-pre-wrap">
                    {diffHighlight.map((item, idx) => (
                      <span
                        key={idx}
                        className={
                          item.type === 'added'
                            ? 'bg-green-500/20 text-green-400'
                            : item.type === 'removed'
                            ? 'bg-red-500/20 text-red-400 line-through'
                            : 'text-dark-text'
                        }
                      >
                        {item.char}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-dark-text whitespace-pre-wrap font-mono">
                    {finetunedResponse}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!originalResponse && !finetunedResponse && !isLoading && (
        <div className="bg-dark-surface border border-dark-border rounded-lg p-12 text-center">
          <AlertCircle className="w-12 h-12 text-dark-text-muted mx-auto mb-4" />
          <p className="text-dark-text-muted">输入提示词并点击"开始对比"查看模型输出差异</p>
        </div>
      )}
    </div>
  )
}

export default PromptLab

