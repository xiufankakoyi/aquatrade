import React, { useState } from 'react'
import { Settings, Play, Loader2, CheckCircle2, XCircle } from 'lucide-react'

function TrainingConfigPanel() {
  const [learningRate, setLearningRate] = useState(3e-4)
  const [loraRank, setLoraRank] = useState(8)
  const [batchSize, setBatchSize] = useState(2)
  const [gradientCheckpointing, setGradientCheckpointing] = useState(true)
  const [aimLogging, setAimLogging] = useState(true)
  const [isTraining, setIsTraining] = useState(false)
  const [progress, setProgress] = useState(0)
  const [trainingStatus, setTrainingStatus] = useState(null)

  const loraRankOptions = [4, 8, 16, 32, 64]

  const formatLearningRate = (value) => {
    return value.toExponential(1)
  }

  const handleStartTraining = async () => {
    setIsTraining(true)
    setProgress(0)
    setTrainingStatus(null)

    try {
      // 调用实际 API
      const response = await fetch('http://localhost:5001/api/train/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          learning_rate: learningRate,
          lora_rank: loraRank,
          batch_size: batchSize,
          gradient_checkpointing: gradientCheckpointing,
          aim_logging: aimLogging,
        }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || '训练启动失败')
      }

      const result = await response.json()
      
      // 轮询训练状态
      const statusInterval = setInterval(async () => {
        try {
          const statusResponse = await fetch('http://localhost:5001/api/train/status')
          const status = await statusResponse.json()
          
          setProgress(status.progress || 0)
          
          if (status.status === 'completed') {
            clearInterval(statusInterval)
            setIsTraining(false)
            setTrainingStatus('success')
          } else if (status.status === 'error') {
            clearInterval(statusInterval)
            setIsTraining(false)
            setTrainingStatus('error')
          }
        } catch (error) {
          console.error('获取训练状态失败:', error)
        }
      }, 1000) // 每秒轮询一次

      // 设置超时（30分钟）
      setTimeout(() => {
        clearInterval(statusInterval)
        if (isTraining) {
          setIsTraining(false)
          setTrainingStatus('error')
        }
      }, 30 * 60 * 1000)
      
    } catch (error) {
      setIsTraining(false)
      setTrainingStatus('error')
      console.error('训练启动失败:', error)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
          <Settings className="w-5 h-5 text-purple-400" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-dark-text">训练配置面板</h2>
          <p className="text-sm text-dark-text-muted">配置 LoRA 微调参数</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration Panel */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-dark-surface border border-dark-border rounded-lg p-6 space-y-6">
            {/* Learning Rate */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium text-dark-text">Learning Rate</label>
                <span className="text-sm font-mono text-blue-400">{formatLearningRate(learningRate)}</span>
              </div>
              <input
                type="range"
                min={-6}
                max={-3}
                step={0.1}
                value={Math.log10(learningRate)}
                onChange={(e) => setLearningRate(Math.pow(10, parseFloat(e.target.value)))}
                className="w-full h-2 bg-dark-border rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
              <div className="flex justify-between text-xs text-dark-text-muted mt-1">
                <span>1e-6</span>
                <span>1e-3</span>
              </div>
            </div>

            {/* LoRA Rank */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium text-dark-text">LoRA Rank</label>
                <span className="text-sm font-mono text-purple-400">{loraRank}</span>
              </div>
              <div className="flex gap-2">
                {loraRankOptions.map((rank) => (
                  <button
                    key={rank}
                    onClick={() => setLoraRank(rank)}
                    className={`
                      flex-1 px-4 py-2 rounded-md text-sm font-medium transition-all
                      ${
                        loraRank === rank
                          ? 'bg-purple-500 text-white'
                          : 'bg-dark-border text-dark-text-muted hover:bg-dark-border/80 hover:text-dark-text'
                      }
                    `}
                  >
                    {rank}
                  </button>
                ))}
              </div>
            </div>

            {/* Batch Size */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium text-dark-text">Batch Size</label>
                <span className="text-sm font-mono text-green-400">{batchSize}</span>
              </div>
              <input
                type="range"
                min={1}
                max={16}
                step={1}
                value={batchSize}
                onChange={(e) => setBatchSize(parseInt(e.target.value))}
                className="w-full h-2 bg-dark-border rounded-lg appearance-none cursor-pointer accent-green-500"
              />
              <div className="flex justify-between text-xs text-dark-text-muted mt-1">
                <span>1</span>
                <span>16</span>
              </div>
            </div>

            {/* Toggles */}
            <div className="space-y-4 pt-4 border-t border-dark-border">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-dark-text">Gradient Checkpointing</label>
                  <p className="text-xs text-dark-text-muted">用时间换显存</p>
                </div>
                <button
                  onClick={() => setGradientCheckpointing(!gradientCheckpointing)}
                  className={`
                    relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                    ${gradientCheckpointing ? 'bg-blue-500' : 'bg-dark-border'}
                  `}
                >
                  <span
                    className={`
                      inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                      ${gradientCheckpointing ? 'translate-x-6' : 'translate-x-1'}
                    `}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-dark-text">Aim Logging</label>
                  <p className="text-xs text-dark-text-muted">启用 Aim 实验追踪</p>
                </div>
                <button
                  onClick={() => setAimLogging(!aimLogging)}
                  className={`
                    relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                    ${aimLogging ? 'bg-purple-500' : 'bg-dark-border'}
                  `}
                >
                  <span
                    className={`
                      inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                      ${aimLogging ? 'translate-x-6' : 'translate-x-1'}
                    `}
                  />
                </button>
              </div>
            </div>
          </div>

          {/* Training Button */}
          <button
            onClick={handleStartTraining}
            disabled={isTraining}
            className={`
              w-full py-4 px-6 rounded-lg font-medium text-white transition-all
              flex items-center justify-center gap-2
              ${
                isTraining
                  ? 'bg-dark-border cursor-not-allowed'
                  : 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700'
              }
            `}
          >
            {isTraining ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                训练中...
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                开始训练
              </>
            )}
          </button>

          {/* Progress Bar */}
          {isTraining && (
            <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-dark-text">训练进度</span>
                <span className="text-sm font-mono text-blue-400">{Math.round(progress)}%</span>
              </div>
              <div className="w-full h-2 bg-dark-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Status Message */}
          {trainingStatus && (
            <div
              className={`
                p-4 rounded-lg border flex items-center gap-3
                ${
                  trainingStatus === 'success'
                    ? 'bg-green-500/10 border-green-500/20 text-green-400'
                    : 'bg-red-500/10 border-red-500/20 text-red-400'
                }
              `}
            >
              {trainingStatus === 'success' ? (
                <CheckCircle2 className="w-5 h-5" />
              ) : (
                <XCircle className="w-5 h-5" />
              )}
              <span className="text-sm">
                {trainingStatus === 'success'
                  ? '训练完成！模型已保存'
                  : '训练失败，请检查配置'}
              </span>
            </div>
          )}
        </div>

        {/* Summary Panel */}
        <div className="space-y-4">
          <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
            <h3 className="text-sm font-medium text-dark-text mb-4">配置摘要</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-dark-text-muted">Learning Rate</span>
                <span className="text-dark-text font-mono">{formatLearningRate(learningRate)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-text-muted">LoRA Rank</span>
                <span className="text-dark-text font-mono">{loraRank}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-text-muted">Batch Size</span>
                <span className="text-dark-text font-mono">{batchSize}</span>
              </div>
              <div className="pt-3 border-t border-dark-border space-y-2">
                <div className="flex justify-between">
                  <span className="text-dark-text-muted">Gradient Checkpointing</span>
                  <span className={gradientCheckpointing ? 'text-green-400' : 'text-dark-text-muted'}>
                    {gradientCheckpointing ? '开启' : '关闭'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-dark-text-muted">Aim Logging</span>
                  <span className={aimLogging ? 'text-purple-400' : 'text-dark-text-muted'}>
                    {aimLogging ? '开启' : '关闭'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default TrainingConfigPanel

