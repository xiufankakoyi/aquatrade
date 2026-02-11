import React, { useState } from 'react'
import { Sparkles, Settings, Code2, BarChart3 } from 'lucide-react'
import DataPreparationPanel from './components/DataPreparationPanel'
import TrainingConfigPanel from './components/TrainingConfigPanel'
import PromptLab from './components/PromptLab'
import AimVisualization from './components/AimVisualization'

function App() {
  const [activeTab, setActiveTab] = useState('data')

  const tabs = [
    { id: 'data', label: '数据整理', icon: Code2 },
    { id: 'training', label: '训练配置', icon: Settings },
    { id: 'prompt', label: '提示词实验室', icon: Sparkles },
    { id: 'visualization', label: '可视化监控', icon: BarChart3 },
  ]

  return (
    <div className="min-h-screen bg-dark-bg">
      {/* Header */}
      <header className="border-b border-dark-border bg-dark-surface/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-dark-text">LLM Fine-tuning Hub</h1>
                <p className="text-sm text-dark-text-muted">AI 实验控制台</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="border-b border-dark-border bg-dark-surface/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center gap-2 px-4 py-3 text-sm font-medium transition-all
                    border-b-2 -mb-px
                    ${
                      activeTab === tab.id
                        ? 'border-blue-500 text-blue-400'
                        : 'border-transparent text-dark-text-muted hover:text-dark-text hover:border-dark-border'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'data' && <DataPreparationPanel />}
        {activeTab === 'training' && <TrainingConfigPanel />}
        {activeTab === 'prompt' && <PromptLab />}
        {activeTab === 'visualization' && <AimVisualization />}
      </main>
    </div>
  )
}

export default App

