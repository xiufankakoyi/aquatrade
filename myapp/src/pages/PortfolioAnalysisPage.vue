<template>
  <div class="portfolio-page">
    <!-- 背景氛围层 -->
    <div class="portfolio-bg"></div>
    <div class="portfolio-grain"></div>
    
    <div class="portfolio-content space-y-6 p-6">
      <!-- Header -->
      <div class="flex justify-between items-center">
        <div class="flex items-center gap-3">
          <div class="w-1 h-8 bg-gradient-to-b from-[#06b6d4] to-[#089981] rounded-full"></div>
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">实盘持仓分析</h1>
            <p class="text-xs text-white/40 mt-0.5 font-mono tracking-wider">PORTFOLIO ANALYSIS</p>
          </div>
        </div>
        <div class="flex space-x-3">
          <button
            @click="refreshData"
            :disabled="portfolioStore.isLoading"
            class="btn-aqua px-4 py-2 bg-white/5 hover:bg-white/10 text-white/70 rounded-xl transition-all duration-200 disabled:opacity-50 border border-white/10 hover:border-[#06b6d4]/30 flex items-center gap-2 backdrop-blur-sm"
          >
            <i class="fas fa-sync-alt" :class="{ 'animate-spin': portfolioStore.isLoading }"></i>
            <span>刷新</span>
          </button>
          <button
            @click="showAddModal = true"
            class="btn-aqua px-4 py-2 bg-[#06b6d4]/15 hover:bg-[#06b6d4]/25 text-[#06b6d4] rounded-xl transition-all duration-200 flex items-center gap-2 border border-[#06b6d4]/20 hover:border-[#06b6d4]/40"
          >
            <i class="fas fa-plus"></i>
            <span>添加持仓</span>
          </button>
          <button
            @click="handlePushFeishu"
            :disabled="portfolioStore.isLoading"
            class="btn-aqua px-4 py-2 bg-[#089981]/15 hover:bg-[#089981]/25 text-[#34d399] rounded-xl transition-all duration-200 disabled:opacity-50 flex items-center gap-2 border border-[#089981]/20 hover:border-[#089981]/40"
          >
            <i class="fas fa-paper-plane"></i>
            <span>推送飞书</span>
          </button>
        </div>
      </div>

      <!-- Top Stats Cards -->
      <div class="grid grid-cols-5 gap-4">
        <div class="aqua-metric-card">
          <div class="aqua-metric-label">总资产</div>
          <div class="aqua-metric-value text-white">{{ formatMoney(totalAssets) }}</div>
          <div class="text-xs text-white/30 mt-1 font-mono">原始资金 {{ formatMoney(initialCapital) }}</div>
        </div>
        <div class="aqua-metric-card">
          <div class="aqua-metric-label">总市值</div>
          <div class="aqua-metric-value text-white">{{ formatMoney(portfolioStore.summary.total_market_value) }}</div>
          <div class="text-xs mt-1 font-mono" :class="positionRatio > 80 ? 'text-[#f23645]' : positionRatio > 50 ? 'text-[#f5a623]' : 'text-[#34d399]'">
            仓位 {{ positionRatio.toFixed(1) }}%
          </div>
        </div>
        <div class="aqua-metric-card">
          <div class="aqua-metric-label">浮动盈亏</div>
          <div class="aqua-metric-value" :class="portfolioStore.summary.total_profit_loss >= 0 ? 'text-[#f23645]' : 'text-[#089981]'">
            {{ formatMoney(portfolioStore.summary.total_profit_loss) }}
          </div>
          <div class="text-xs text-white/30 mt-1">未实现盈亏</div>
        </div>
        <div 
          class="aqua-metric-card"
          :class="portfolioStore.summary.total_profit_loss >= 0 ? 'aqua-card-up' : 'aqua-card-down'"
        >
          <div class="aqua-metric-label">总盈亏</div>
          <div class="aqua-metric-value" :class="portfolioStore.summary.total_profit_loss >= 0 ? 'text-[#f23645]' : 'text-[#089981]'">
            {{ formatMoney(portfolioStore.summary.total_profit_loss) }}
          </div>
          <div 
            class="aqua-metric-change"
            :class="portfolioStore.summary.total_profit_loss_pct >= 0 ? 'aqua-change-up' : 'aqua-change-down'"
          >
            <i :class="portfolioStore.summary.total_profit_loss_pct >= 0 ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
            {{ Math.abs(portfolioStore.summary.total_profit_loss_pct).toFixed(2) }}%
          </div>
        </div>
        <div class="aqua-metric-card">
          <div class="aqua-metric-label">持仓数量</div>
          <div class="aqua-metric-value text-white">{{ portfolioStore.summary.position_count }}</div>
          <div class="text-xs text-white/30 mt-1">只持仓</div>
        </div>
      </div>

      <!-- Main Content Grid -->
      <div class="grid grid-cols-3 gap-6">
        <!-- Industry Distribution -->
        <div class="aqua-card p-6">
          <div class="flex items-center gap-2 mb-5">
            <div class="w-8 h-8 rounded-lg bg-[#06b6d4]/10 flex items-center justify-center border border-[#06b6d4]/20">
              <i class="fas fa-industry text-[#06b6d4] text-sm"></i>
            </div>
            <h2 class="text-lg font-semibold text-white">行业分布</h2>
          </div>
          <div class="space-y-3">
            <div 
              v-for="(weight, industry) in portfolioStore.industryDistribution" 
              :key="industry"
              class="group"
            >
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-white/50 text-sm font-medium group-hover:text-white transition-colors">{{ industry }}</span>
                <span class="text-white/40 text-sm font-mono">{{ weight.toFixed(1) }}%</span>
              </div>
              <div class="aqua-progress-bar">
                <div 
                  class="aqua-progress-fill"
                  :style="{ width: `${weight}%` }"
                ></div>
              </div>
            </div>
            <div v-if="Object.keys(portfolioStore.industryDistribution).length === 0" class="empty-state py-8">
              <i class="fas fa-chart-pie empty-state-icon"></i>
              <span class="text-sm">暂无行业分布数据</span>
            </div>
          </div>
        </div>

        <!-- Position Distribution -->
        <div class="aqua-card p-6">
          <div class="flex items-center gap-2 mb-5">
            <div class="w-8 h-8 rounded-lg bg-[#089981]/10 flex items-center justify-center border border-[#089981]/20">
              <i class="fas fa-chart-pie text-[#34d399] text-sm"></i>
            </div>
            <h2 class="text-lg font-semibold text-white">仓位分布</h2>
          </div>
          <div class="h-64 flex items-center justify-center">
            <PortfolioPieChart :positions="portfolioStore.positions" />
          </div>
        </div>

        <!-- Profit/Loss Distribution -->
        <div class="aqua-card p-6">
          <div class="flex items-center gap-2 mb-5">
            <div class="w-8 h-8 rounded-lg bg-[#f5a623]/10 flex items-center justify-center border border-[#f5a623]/20">
              <i class="fas fa-balance-scale text-[#f5a623] text-sm"></i>
            </div>
            <h2 class="text-lg font-semibold text-white">盈亏分布</h2>
          </div>
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <span class="text-white/50 text-sm">盈利个股</span>
              <span class="text-[#f23645] font-mono font-semibold">{{ profitCount }} 只</span>
            </div>
            <div class="aqua-progress-bar">
              <div 
                class="aqua-progress-fill bg-[#f23645]"
                :style="{ width: `${profitCount > 0 ? (profitCount / portfolioStore.positions.length * 100) : 0}%` }"
              ></div>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-white/50 text-sm">亏损个股</span>
              <span class="text-[#089981] font-mono font-semibold">{{ lossCount }} 只</span>
            </div>
            <div class="aqua-progress-bar">
              <div 
                class="aqua-progress-fill bg-[#089981]"
                :style="{ width: `${lossCount > 0 ? (lossCount / portfolioStore.positions.length * 100) : 0}%` }"
              ></div>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-white/50 text-sm">持平个股</span>
              <span class="text-white/40 font-mono font-semibold">{{ neutralCount }} 只</span>
            </div>
            <div class="aqua-progress-bar">
              <div 
                class="aqua-progress-fill bg-white/30"
                :style="{ width: `${neutralCount > 0 ? (neutralCount / portfolioStore.positions.length * 100) : 0}%` }"
              ></div>
            </div>
            <div class="pt-4 border-t border-white/10 mt-4">
              <div class="flex items-center justify-between mb-2">
                <span class="text-white/50 text-sm">最大盈利</span>
                <span class="text-[#f23645] font-mono">{{ maxProfit }}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-white/50 text-sm">最大亏损</span>
                <span class="text-[#089981] font-mono">{{ maxLoss }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Position Details Table -->
      <div class="aqua-card p-6">
        <div class="flex items-center justify-between mb-5">
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center border border-white/10">
              <i class="fas fa-list text-white/50 text-sm"></i>
            </div>
            <h2 class="text-lg font-semibold text-white">持仓明细</h2>
            <span class="px-2 py-0.5 bg-white/5 text-white/40 text-xs rounded-full border border-white/10">
              {{ portfolioStore.positions.length }} 只
            </span>
          </div>
          <button 
            @click="showPositionHistoryModal = true"
            class="btn-aqua px-3 py-1.5 bg-[#06b6d4]/10 hover:bg-[#06b6d4]/20 text-[#06b6d4] rounded-lg text-sm flex items-center gap-2 border border-[#06b6d4]/20"
          >
            <i class="fas fa-history"></i>
            持仓历史
          </button>
        </div>
        <div class="overflow-x-auto">
          <table class="aqua-table">
            <thead>
              <tr>
                <th class="text-left">股票</th>
                <th class="text-right">买入价</th>
                <th class="text-right">现价</th>
                <th class="text-right">持仓</th>
                <th class="text-right">市值</th>
                <th class="text-right">盈亏</th>
                <th class="text-right">仓位</th>
                <th class="text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="position in portfolioStore.positions" 
                :key="position.id"
                class="group"
              >
                <td>
                  <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg bg-[#06b6d4]/10 flex items-center justify-center border border-[#06b6d4]/20">
                      <span class="text-[#06b6d4] text-xs font-bold">{{ position.stock_name?.charAt(0) }}</span>
                    </div>
                    <div>
                      <div class="text-white/80 font-medium">{{ position.stock_name }}</div>
                      <div class="text-white/30 text-xs font-mono">{{ position.stock_code }}</div>
                    </div>
                  </div>
                </td>
                <td class="text-right">
                  <span class="text-white/50 font-mono">{{ formatPrice(position.buy_price) }}</span>
                </td>
                <td class="text-right">
                  <span v-if="position.current_price" class="text-white font-mono font-medium">
                    {{ formatPrice(position.current_price) }}
                  </span>
                  <span v-else class="text-white/30">-</span>
                </td>
                <td class="text-right">
                  <span class="text-white/50 font-mono">{{ formatShares(position.shares) }}</span>
                </td>
                <td class="text-right">
                  <span class="text-white font-mono font-medium">
                    {{ position.market_value ? formatMoney(position.market_value) : '-' }}
                  </span>
                </td>
                <td class="text-right">
                  <div v-if="position.profit_loss !== undefined && position.profit_loss !== null">
                    <div 
                      class="font-mono font-semibold"
                      :class="position.profit_loss >= 0 ? 'text-[#f23645]' : 'text-[#089981]'"
                    >
                      {{ formatMoney(position.profit_loss) }}
                    </div>
                    <div 
                      v-if="position.profit_loss_pct !== null && position.profit_loss_pct !== undefined"
                      class="text-xs font-mono mt-0.5"
                      :class="position.profit_loss_pct >= 0 ? 'text-[#f23645]' : 'text-[#089981]'"
                    >
                      <i :class="position.profit_loss_pct >= 0 ? 'fas fa-caret-up' : 'fas fa-caret-down'"></i>
                      {{ Math.abs(position.profit_loss_pct).toFixed(2) }}%
                    </div>
                  </div>
                  <span v-else class="text-white/30">-</span>
                </td>
                <td class="text-right">
                  <div class="flex items-center justify-end gap-2">
                    <div class="w-12 h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <div 
                        class="h-full rounded-full transition-all duration-300"
                        :class="position.weight > 30 ? 'bg-[#f23645]' : position.weight > 15 ? 'bg-[#f5a623]' : 'bg-[#06b6d4]'"
                        :style="{ width: `${Math.min(position.weight || 0, 100)}%` }"
                      ></div>
                    </div>
                    <span class="text-white/50 font-mono text-sm w-12">{{ position.weight ? position.weight.toFixed(1) + '%' : '-' }}</span>
                  </div>
                </td>
                <td>
                  <div class="flex items-center justify-center gap-0.5 opacity-40 group-hover:opacity-100 transition-opacity">
                    <button 
                      @click="openStopLossModal(position)"
                      class="aqua-icon-btn text-[#f5a623] hover:text-[#f5a623] hover:bg-[#f5a623]/10"
                      title="设置止损止盈"
                    >
                      <i class="fas fa-shield-alt text-xs"></i>
                    </button>
                    <button 
                      @click="openAdjustModal(position, 'add')"
                      class="aqua-icon-btn text-[#089981] hover:text-[#089981] hover:bg-[#089981]/10"
                      title="加仓"
                    >
                      <i class="fas fa-plus text-xs"></i>
                    </button>
                    <button 
                      @click="openAdjustModal(position, 'reduce')"
                      class="aqua-icon-btn text-[#f23645] hover:text-[#f23645] hover:bg-[#f23645]/10"
                      title="减仓"
                    >
                      <i class="fas fa-minus text-xs"></i>
                    </button>
                    <button 
                      @click="viewKline(position)"
                      class="aqua-icon-btn text-[#06b6d4] hover:text-[#06b6d4] hover:bg-[#06b6d4]/10"
                      title="查看K线"
                    >
                      <i class="fas fa-chart-line text-xs"></i>
                    </button>
                    <button 
                      @click="editPosition(position)"
                      class="aqua-icon-btn text-white/40 hover:text-white/70 hover:bg-white/5"
                      title="编辑"
                    >
                      <i class="fas fa-edit text-xs"></i>
                    </button>
                    <button 
                      @click="confirmDelete(position)"
                      class="aqua-icon-btn text-white/40 hover:text-[#f23645] hover:bg-[#f23645]/10"
                      title="删除"
                    >
                      <i class="fas fa-trash text-xs"></i>
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="portfolioStore.positions.length === 0">
                <td colspan="8">
                  <div class="empty-state py-12">
                    <i class="fas fa-folder-open empty-state-icon"></i>
                    <span class="text-base">暂无持仓数据</span>
                    <p class="text-sm text-white/30 mt-2">点击"添加持仓"开始管理您的投资组合</p>
                    <button
                      @click="showAddModal = true"
                      class="btn-aqua mt-4 px-4 py-2 bg-[#06b6d4]/15 hover:bg-[#06b6d4]/25 text-[#06b6d4] rounded-lg text-sm border border-[#06b6d4]/20"
                    >
                      <i class="fas fa-plus mr-2"></i>
                      添加第一笔持仓
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Watchlist Module -->
      <WatchlistModule />
    </div>

    <!-- Modals -->
    <div 
      v-if="showAddModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showAddModal = false"
    >
      <div class="bg-[#1a1f2e] rounded-lg p-6 w-full max-w-md border border-slate-700">
        <h3 class="text-lg font-semibold text-white mb-4">
          {{ editingPosition ? '编辑持仓' : '添加持仓' }}
        </h3>
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <StockSearchInput
                v-model="form.stock_code"
                label="股票代码 *"
                placeholder="输入代码或名称搜索"
                :disabled="!!editingPosition"
                @select="handleStockSelect"
              />
            </div>
            <div>
              <label class="block text-slate-400 text-sm mb-1">股票名称 *</label>
              <input
                v-model="form.stock_name"
                type="text"
                required
                readonly
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none disabled:opacity-50 cursor-not-allowed"
                placeholder="自动填充"
              />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-slate-400 text-sm mb-1">买入价 *</label>
              <input 
                v-model.number="form.buy_price" 
                type="number" 
                step="0.001"
                required
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-slate-400 text-sm mb-1">持仓数量 *</label>
              <input 
                v-model.number="form.shares" 
                type="number" 
                step="0.001"
                required
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-slate-400 text-sm mb-1">总成本 *</label>
              <input 
                v-model.number="form.cost" 
                type="number" 
                step="0.001"
                required
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-slate-400 text-sm mb-1">买入日期 *</label>
              <input 
                v-model="form.buy_date" 
                type="date" 
                required
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-slate-400 text-sm mb-1">止损价</label>
              <input 
                v-model.number="form.stop_loss" 
                type="number" 
                step="0.001"
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-slate-400 text-sm mb-1">止盈价</label>
              <input 
                v-model.number="form.take_profit" 
                type="number" 
                step="0.001"
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div>
            <label class="block text-slate-400 text-sm mb-1">备注</label>
            <textarea 
              v-model="form.notes" 
              rows="2"
              class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none resize-none"
            ></textarea>
          </div>
          <div class="flex justify-end space-x-3 pt-4">
            <button 
              type="button"
              @click="closeModal"
              class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors"
            >
              取消
            </button>
            <button 
              type="submit"
              :disabled="portfolioStore.isLoading"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors disabled:opacity-50"
            >
              {{ editingPosition ? '更新' : '添加' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div 
      v-if="showStopLossModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showStopLossModal = false"
    >
      <div class="bg-[#1a1f2e] rounded-lg p-6 w-full max-w-md border border-slate-700">
        <h3 class="text-lg font-semibold text-white mb-4">
          <i class="fas fa-shield-alt text-yellow-400 mr-2"></i>
          设置止损止盈 - {{ stopLossForm.stock_name }}
        </h3>
        <div class="mb-4 p-3 bg-slate-800/50 rounded-lg">
          <div class="flex justify-between text-sm">
            <span class="text-slate-400">当前价格</span>
            <span class="text-white font-mono">{{ stopLossForm.current_price ? formatPrice(stopLossForm.current_price) : '-' }}</span>
          </div>
          <div class="flex justify-between text-sm mt-2">
            <span class="text-slate-400">买入价格</span>
            <span class="text-white font-mono">{{ formatPrice(stopLossForm.buy_price) }}</span>
          </div>
        </div>
        <form @submit.prevent="handleStopLossSubmit" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-slate-400 text-sm mb-1">止损价</label>
              <input 
                v-model.number="stopLossForm.stop_loss" 
                type="number" 
                step="0.001"
                placeholder="设置止损价"
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-yellow-500 focus:outline-none"
              />
              <p v-if="stopLossForm.stop_loss && stopLossForm.buy_price" class="text-xs text-slate-500 mt-1">
                止损幅度: {{ ((stopLossForm.stop_loss - stopLossForm.buy_price) / stopLossForm.buy_price * 100).toFixed(2) }}%
              </p>
            </div>
            <div>
              <label class="block text-slate-400 text-sm mb-1">止盈价</label>
              <input 
                v-model.number="stopLossForm.take_profit" 
                type="number" 
                step="0.001"
                placeholder="设置止盈价"
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-green-500 focus:outline-none"
              />
              <p v-if="stopLossForm.take_profit && stopLossForm.buy_price" class="text-xs text-slate-500 mt-1">
                止盈幅度: {{ ((stopLossForm.take_profit - stopLossForm.buy_price) / stopLossForm.buy_price * 100).toFixed(2) }}%
              </p>
            </div>
          </div>
          <div class="flex justify-end space-x-3 pt-4">
            <button 
              type="button"
              @click="showStopLossModal = false"
              class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors"
            >
              取消
            </button>
            <button 
              type="submit"
              :disabled="portfolioStore.isLoading"
              class="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded transition-colors disabled:opacity-50"
            >
              保存
            </button>
          </div>
        </form>
      </div>
    </div>

    <div 
      v-if="showAdjustModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showAdjustModal = false"
    >
      <div class="bg-[#1a1f2e] rounded-lg p-6 w-full max-w-md border border-slate-700">
        <h3 class="text-lg font-semibold text-white mb-4">
          <i :class="adjustForm.type === 'add' ? 'fas fa-plus text-green-400' : 'fas fa-minus text-orange-400'" class="mr-2"></i>
          {{ adjustForm.type === 'add' ? '加仓' : '减仓' }} - {{ adjustForm.stock_name }}
        </h3>
        <div class="mb-4 p-3 bg-slate-800/50 rounded-lg">
          <div class="flex justify-between text-sm">
            <span class="text-slate-400">当前持仓</span>
            <span class="text-white font-mono">{{ adjustForm.current_shares }} 股</span>
          </div>
          <div class="flex justify-between text-sm mt-2">
            <span class="text-slate-400">当前成本</span>
            <span class="text-white font-mono">{{ formatMoney(adjustForm.current_cost) }}</span>
          </div>
        </div>
        <form @submit.prevent="handleAdjustSubmit" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-slate-400 text-sm mb-1">{{ adjustForm.type === 'add' ? '买入' : '卖出' }}价格 *</label>
              <input 
                v-model.number="adjustForm.price" 
                type="number" 
                step="0.001"
                required
                :placeholder="adjustForm.type === 'add' ? '买入价格' : '卖出价格'"
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-slate-400 text-sm mb-1">{{ adjustForm.type === 'add' ? '买入' : '卖出' }}数量 *</label>
              <input 
                v-model.number="adjustForm.shares" 
                type="number" 
                step="0.001"
                required
                :max="adjustForm.type === 'reduce' ? adjustForm.current_shares : undefined"
                :placeholder="adjustForm.type === 'add' ? '买入数量' : '卖出数量'"
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
              <p v-if="adjustForm.type === 'reduce' && adjustForm.shares" class="text-xs text-slate-500 mt-1">
                剩余: {{ adjustForm.current_shares - adjustForm.shares }} 股
              </p>
            </div>
          </div>
          <div v-if="adjustForm.type === 'add'">
            <label class="block text-slate-400 text-sm mb-1">新增成本</label>
            <input 
              :value="adjustForm.price && adjustForm.shares ? (adjustForm.price * adjustForm.shares).toFixed(2) : ''"
              type="text"
              readonly
              placeholder="自动计算"
              class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-400 focus:outline-none cursor-not-allowed"
            />
          </div>
          <div class="flex justify-end space-x-3 pt-4">
            <button 
              type="button"
              @click="showAdjustModal = false"
              class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors"
            >
              取消
            </button>
            <button 
              type="submit"
              :disabled="portfolioStore.isLoading"
              :class="adjustForm.type === 'add' ? 'bg-green-600 hover:bg-green-500' : 'bg-orange-600 hover:bg-orange-500'"
              class="px-4 py-2 text-white rounded transition-colors disabled:opacity-50"
            >
              确认{{ adjustForm.type === 'add' ? '加仓' : '减仓' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div 
      v-if="showKlineModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showKlineModal = false"
    >
      <div class="bg-[#1a1f2e] rounded-lg w-full max-w-5xl border border-slate-700" style="height: 600px;">
        <div class="flex justify-between items-center p-4 border-b border-slate-700">
          <h3 class="text-lg font-semibold text-white">
            <i class="fas fa-chart-line text-purple-400 mr-2"></i>
            {{ klineStock?.stock_name }} ({{ klineStock?.stock_code }}) K线图
          </h3>
          <button 
            @click="showKlineModal = false"
            class="text-slate-400 hover:text-white"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="p-4 h-[calc(100%-60px)]">
          <div ref="klineContainer" class="w-full h-full bg-slate-800/50 rounded-lg"></div>
        </div>
      </div>
    </div>

    <!-- Add History Record Modal -->
    <div 
      v-if="showAddHistoryModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]"
      @click.self="showAddHistoryModal = false"
    >
      <div class="bg-[#1a1f2e] rounded-lg w-full max-w-md border border-slate-700 p-6">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-lg font-semibold text-white">
            <i class="fas fa-plus-circle text-[#2962ff] mr-2"></i>
            添加历史交易记录
          </h3>
          <button 
            @click="showAddHistoryModal = false"
            class="text-slate-400 hover:text-white"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="handleAddHistorySubmit" class="space-y-4">
          <div>
            <label class="block text-slate-400 text-sm mb-1">股票代码 *</label>
            <StockSearchInput
              v-model="historyForm.stock_code"
              label=""
              placeholder="输入代码或名称搜索"
              @select="handleHistoryStockSelect"
            />
          </div>
          
          <div>
            <label class="block text-slate-400 text-sm mb-1">股票名称 *</label>
            <input
              v-model="historyForm.stock_name"
              type="text"
              required
              readonly
              class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none disabled:opacity-50 cursor-not-allowed"
              placeholder="自动填充"
            />
          </div>
          
          <div>
            <label class="block text-slate-400 text-sm mb-1">操作类型 *</label>
            <select
              v-model="historyForm.action"
              required
              class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
            >
              <option value="buy">买入（新建持仓）</option>
              <option value="add">加仓</option>
              <option value="reduce">减仓</option>
              <option value="sell">卖出（清仓）</option>
            </select>
          </div>
          
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-slate-400 text-sm mb-1">成交价格 *</label>
              <input
                v-model.number="historyForm.price"
                type="number"
                step="0.001"
                required
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                placeholder="0.00"
              />
            </div>
            <div>
              <label class="block text-slate-400 text-sm mb-1">成交数量 *</label>
              <input
                v-model.number="historyForm.shares"
                type="number"
                required
                class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                placeholder="0"
              />
            </div>
          </div>
          
          <div>
            <label class="block text-slate-400 text-sm mb-1">成交日期 *</label>
            <input
              v-model="historyForm.date"
              type="date"
              required
              class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
            />
          </div>
          
          <div>
            <label class="block text-slate-400 text-sm mb-1">备注</label>
            <input
              v-model="historyForm.notes"
              type="text"
              class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              placeholder="可选"
            />
          </div>
          
          <div class="flex justify-end gap-3 pt-4">
            <button 
              type="button"
              @click="showAddHistoryModal = false"
              class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors"
            >
              取消
            </button>
            <button 
              type="submit"
              :disabled="portfolioStore.isLoading"
              class="px-4 py-2 bg-[#2962ff] hover:bg-[#1e4bd8] text-white rounded transition-colors disabled:opacity-50"
            >
              确认添加
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Batch Import Modal -->
    <div 
      v-if="showBatchImportModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]"
      @click.self="showBatchImportModal = false"
    >
      <div class="bg-[#1a1f2e] rounded-lg w-full max-w-2xl border border-slate-700 p-6 max-h-[80vh] flex flex-col">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-lg font-semibold text-white">
            <i class="fas fa-file-import text-[#089981] mr-2"></i>
            批量导入历史交易
          </h3>
          <button 
            @click="showBatchImportModal = false"
            class="text-slate-400 hover:text-white"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <div class="mb-4 p-3 bg-[#2d2d30] rounded-lg">
          <p class="text-sm text-[#b2b5be] mb-2">
            <i class="fas fa-info-circle text-[#2962ff] mr-1"></i>
            支持以下两种格式（每行一条记录）：
          </p>
          <div class="space-y-2 text-xs text-[#787b86]">
            <div>
              <span class="text-[#089981]">格式一（股票名称+空格分隔）：</span>
              <code class="block bg-[#1e1e1e] p-2 rounded mt-1">
                生益科技 买入 69.14 300 2026-02-25<br>
                通富微电 卖出 52.11 1200 2026-02-26
              </code>
            </div>
            <div>
              <span class="text-[#2962ff]">格式二（股票代码+逗号分隔）：</span>
              <code class="block bg-[#1e1e1e] p-2 rounded mt-1">
                600183,buy,69.14,300,2026-02-25<br>
                002156,sell,52.11,1200,2026-02-26
              </code>
            </div>
          </div>
          <p class="text-xs text-[#787b86] mt-2">
            操作类型：买入/buy、卖出/sell | 系统自动判断加仓/减仓
          </p>
        </div>
        
        <textarea
          v-model="batchImportText"
          rows="10"
          class="flex-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none font-mono text-sm"
          placeholder="在此粘贴交易记录..."
        ></textarea>
        
        <div class="flex justify-between items-center mt-4">
          <div class="text-sm text-[#787b86]">
            预计导入: {{ batchImportPreview.length }} 条记录
          </div>
          <div class="flex gap-3">
            <button 
              @click="showBatchImportModal = false"
              class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors"
            >
              取消
            </button>
            <button 
              @click="handleBatchImport"
              :disabled="portfolioStore.isLoading || batchImportPreview.length === 0"
              class="px-4 py-2 bg-[#089981] hover:bg-[#078a73] text-white rounded transition-colors disabled:opacity-50"
            >
              确认导入
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Position History Modal -->
    <div 
      v-if="showPositionHistoryModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showPositionHistoryModal = false"
    >
      <div class="bg-[#1a1f2e] rounded-lg w-full max-w-4xl border border-slate-700 max-h-[80vh] flex flex-col">
        <div class="flex justify-between items-center p-4 border-b border-slate-700">
          <h3 class="text-lg font-semibold text-white">
            <i class="fas fa-history text-[#2962ff] mr-2"></i>
            持仓历史
          </h3>
          <div class="flex items-center gap-2">
            <button 
              @click="openBatchImportModal"
              class="px-3 py-1.5 bg-[#089981]/20 hover:bg-[#089981]/30 text-[#089981] rounded-lg text-sm flex items-center gap-2"
            >
              <i class="fas fa-file-import"></i>
              批量导入
            </button>
            <button 
              @click="openAddHistoryModal"
              class="px-3 py-1.5 bg-[#2962ff]/20 hover:bg-[#2962ff]/30 text-[#2962ff] rounded-lg text-sm flex items-center gap-2"
            >
              <i class="fas fa-plus"></i>
              添加记录
            </button>
            <button 
              @click="showPositionHistoryModal = false"
              class="text-slate-400 hover:text-white"
            >
              <i class="fas fa-times"></i>
            </button>
          </div>
        </div>
        
        <!-- Stats Summary -->
        <div v-if="portfolioStore.positionHistoryStats" class="p-4 border-b border-slate-700 bg-[#1e2330]">
          <div class="grid grid-cols-5 gap-4 text-center">
            <div>
              <div class="text-2xl font-bold text-white">{{ portfolioStore.positionHistoryStats.total_trades }}</div>
              <div class="text-xs text-[#787b86]">总交易次数</div>
            </div>
            <div>
              <div class="text-2xl font-bold text-[#f23645]">{{ portfolioStore.positionHistoryStats.buy_count }}</div>
              <div class="text-xs text-[#787b86]">买入</div>
            </div>
            <div>
              <div class="text-2xl font-bold text-[#089981]">{{ portfolioStore.positionHistoryStats.sell_count }}</div>
              <div class="text-xs text-[#787b86]">卖出</div>
            </div>
            <div>
              <div class="text-2xl font-bold text-[#f5a623]">{{ portfolioStore.positionHistoryStats.add_count }}</div>
              <div class="text-xs text-[#787b86]">加仓</div>
            </div>
            <div>
              <div class="text-2xl font-bold text-[#2962ff]">{{ portfolioStore.positionHistoryStats.reduce_count }}</div>
              <div class="text-xs text-[#787b86]">减仓</div>
            </div>
          </div>
        </div>
        
        <!-- History List -->
        <div class="flex-1 overflow-auto p-4">
          <table class="w-full">
            <thead class="sticky top-0 bg-[#1a1f2e]">
              <tr class="text-left text-[#787b86] text-sm border-b border-slate-700">
                <th class="pb-3">日期</th>
                <th class="pb-3">股票</th>
                <th class="pb-3">操作</th>
                <th class="pb-3 text-right">数量</th>
                <th class="pb-3 text-right">价格</th>
                <th class="pb-3 text-right">金额</th>
                <th class="pb-3">备注</th>
                <th class="pb-3 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="item in portfolioStore.positionHistory" 
                :key="item.id"
                class="border-b border-slate-800 text-sm group hover:bg-slate-800/30"
              >
                <td class="py-3 text-[#b2b5be]">{{ item.date }}</td>
                <td class="py-3">
                  <div class="text-white font-medium">{{ item.stock_name }}</div>
                  <div class="text-[#787b86] text-xs">{{ item.stock_code }}</div>
                </td>
                <td class="py-3">
                  <span 
                    class="px-2 py-1 rounded text-xs font-medium"
                    :class="{
                      'bg-[#f23645]/20 text-[#f23645]': item.action === 'buy',
                      'bg-[#089981]/20 text-[#089981]': item.action === 'sell',
                      'bg-[#f5a623]/20 text-[#f5a623]': item.action === 'add',
                      'bg-[#2962ff]/20 text-[#2962ff]': item.action === 'reduce'
                    }"
                  >
                    {{ actionLabels[item.action] }}
                  </span>
                </td>
                <td class="py-3 text-right text-white font-mono">{{ item.shares }}</td>
                <td class="py-3 text-right text-white font-mono">{{ formatPrice(item.price) }}</td>
                <td class="py-3 text-right font-mono" :class="item.amount >= 0 ? 'text-[#f23645]' : 'text-[#089981]'">
                  {{ formatMoney(Math.abs(item.amount)) }}
                </td>
                <td class="py-3 text-[#787b86]">{{ item.notes || '-' }}</td>
                <td class="py-3 text-center">
                  <button 
                    @click="handleDeleteHistory(item)"
                    class="text-slate-500 hover:text-[#f23645] transition-colors opacity-0 group-hover:opacity-100"
                    title="删除记录"
                  >
                    <i class="fas fa-trash-alt"></i>
                  </button>
                </td>
              </tr>
              <tr v-if="portfolioStore.positionHistory.length === 0">
                <td colspan="7" class="py-8 text-center text-[#787b86]">
                  <i class="fas fa-inbox text-3xl mb-2"></i>
                  <p>暂无持仓历史记录</p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed, watch } from 'vue';
import { message } from 'ant-design-vue';
import { usePortfolioStore, useWatchlistStore } from '../store/portfolioStore';
import PortfolioPieChart from '../components/charts/PortfolioPieChart.vue';
import StockSearchInput from '../components/StockSearchInput.vue';
import WatchlistModule from '../components/WatchlistModule.vue';
import axios from '../api/index';

const watchlistStore = useWatchlistStore();

/**
 * 股票信息接口
 */
interface StockInfo {
  code: string;
  name: string;
  symbol: string;
  market: 'SH' | 'SZ';
}

const portfolioStore = usePortfolioStore();

const showAddModal = ref(false);
const editingPosition = ref<any>(null);

const initialCapital = ref(500000);

const totalAssets = computed(() => {
  return initialCapital.value + portfolioStore.summary.total_profit_loss;
});

const positionRatio = computed(() => {
  if (!totalAssets.value || totalAssets.value <= 0) return 0;
  return (portfolioStore.summary.total_market_value / totalAssets.value) * 100;
});

const profitCount = computed(() => 
  portfolioStore.positions.filter(p => (p.profit_loss_pct || 0) > 0).length
);

const lossCount = computed(() => 
  portfolioStore.positions.filter(p => (p.profit_loss_pct || 0) < 0).length
);

const neutralCount = computed(() => 
  portfolioStore.positions.filter(p => (p.profit_loss_pct || 0) === 0).length
);

const maxProfit = computed(() => {
  const profits = portfolioStore.positions
    .filter(p => (p.profit_loss_pct || 0) > 0)
    .map(p => p.profit_loss_pct || 0);
  if (profits.length === 0) return '-';
  return '+' + Math.max(...profits).toFixed(2) + '%';
});

const maxLoss = computed(() => {
  const losses = portfolioStore.positions
    .filter(p => (p.profit_loss_pct || 0) < 0)
    .map(p => p.profit_loss_pct || 0);
  if (losses.length === 0) return '-';
  return Math.min(...losses).toFixed(2) + '%';
});

const form = reactive({
  stock_code: '',
  stock_name: '',
  buy_price: 0,
  shares: 0,
  cost: 0,
  buy_date: new Date().toISOString().split('T')[0],
  stop_loss: null as number | null,
  take_profit: null as number | null,
  notes: ''
});

const formatMoney = (value: number) => {
  if (value >= 10000) {
    return (value / 10000).toFixed(2) + '万';
  }
  return value.toFixed(2);
};

const formatPrice = (value: number | undefined | null) => {
  if (value === undefined || value === null || isNaN(value)) {
    return '-';
  }
  const str = value.toString();
  if (str.includes('.') && str.split('.')[1]?.length > 2) {
    return value.toFixed(3);
  }
  return value.toFixed(2);
};

/**
 * 格式化持仓数量
 * 大于10000显示为"X万"
 */
const formatShares = (value: number | undefined | null) => {
  if (value === undefined || value === null || isNaN(value)) {
    return '-';
  }
  if (value >= 10000) {
    return (value / 10000).toFixed(2) + '万';
  }
  return value.toString();
};

const refreshData = async () => {
  await Promise.all([
    portfolioStore.fetchAnalysis(),
    portfolioStore.fetchSignals()
  ]);
};

const editPosition = (position: any) => {
  editingPosition.value = position;
  Object.assign(form, {
    stock_code: position.stock_code,
    stock_name: position.stock_name,
    buy_price: position.buy_price,
    shares: position.shares,
    cost: position.cost,
    buy_date: position.buy_date,
    stop_loss: position.stop_loss,
    take_profit: position.take_profit,
    notes: position.notes || ''
  });
  showAddModal.value = true;
};

const confirmDelete = async (position: any) => {
  console.log(`[confirmDelete] 准备删除持仓:`, position);
  
  if (!position.id) {
    message.error('持仓ID不存在，无法删除');
    return;
  }
  
  if (confirm(`确定要删除 ${position.stock_name}(${position.stock_code}) 吗？`)) {
    console.log(`[confirmDelete] 用户确认删除 ID=${position.id}`);
    const success = await portfolioStore.deletePosition(position.id);
    console.log(`[confirmDelete] 删除结果:`, success, '错误:', portfolioStore.error);
    if (success) {
      message.success('删除成功');
    } else if (portfolioStore.error) {
      message.error(`删除失败: ${portfolioStore.error}`);
    } else {
      message.error('删除失败，请重试');
    }
  }
};

const closeModal = () => {
  showAddModal.value = false;
  editingPosition.value = null;
  Object.assign(form, {
    stock_code: '',
    stock_name: '',
    buy_price: 0,
    shares: 0,
    cost: 0,
    buy_date: new Date().toISOString().split('T')[0],
    stop_loss: null,
    take_profit: null,
    notes: ''
  });
};

const handleSubmit = async () => {
  const positionData = {
    stock_code: form.stock_code,
    stock_name: form.stock_name,
    buy_price: form.buy_price,
    shares: form.shares,
    cost: form.cost,
    buy_date: form.buy_date,
    stop_loss: form.stop_loss,
    take_profit: form.take_profit,
    notes: form.notes,
    is_active: true
  };

  if (editingPosition.value) {
    await portfolioStore.updatePosition({
      ...positionData,
      id: editingPosition.value.id
    });
  } else {
    // 添加新持仓
    const newId = await portfolioStore.addPosition(positionData);
    
    // 记录买入历史
    if (newId) {
      await portfolioStore.addPositionHistory({
        position_id: newId,
        stock_code: form.stock_code,
        stock_name: form.stock_name,
        action: 'buy',
        shares: form.shares,
        price: form.buy_price,
        amount: form.cost,
        date: form.buy_date,
        notes: form.notes || `买入 ${form.shares} 股，价格 ${form.buy_price}`
      });
    }
  }
  
  closeModal();
};

const handlePushFeishu = async () => {
  const success = await portfolioStore.pushToFeishu();
  if (success) {
    alert('推送成功！');
  } else if (portfolioStore.error) {
    alert('推送失败：' + portfolioStore.error);
  }
};

/**
 * 处理股票选择事件
 * @param stock - 选中的股票信息
 */
const handleStockSelect = (stock: StockInfo) => {
  form.stock_code = stock.code;
  form.stock_name = stock.name;
};

onMounted(async () => {
  refreshData();
  
  await watchlistStore.fetchFeishuConfig();
  
  if (watchlistStore.feishuConfig.is_configured) {
    const result = await watchlistStore.checkSignals();
    if (result && result.notification_count > 0) {
      message.info(`检测到 ${result.notification_count} 个信号${result.notified ? '，已推送飞书' : ''}`);
    }
  }
});

const showStopLossModal = ref(false);
const stopLossForm = reactive({
  id: 0,
  stock_code: '',
  stock_name: '',
  buy_price: 0,
  current_price: 0,
  stop_loss: null as number | null,
  take_profit: null as number | null
});

const openStopLossModal = (position: any) => {
  stopLossForm.id = position.id;
  stopLossForm.stock_code = position.stock_code;
  stopLossForm.stock_name = position.stock_name;
  stopLossForm.buy_price = position.buy_price;
  stopLossForm.current_price = position.current_price || 0;
  stopLossForm.stop_loss = position.stop_loss;
  stopLossForm.take_profit = position.take_profit;
  showStopLossModal.value = true;
};

const handleStopLossSubmit = async () => {
  const success = await portfolioStore.updatePosition({
    id: stopLossForm.id,
    stock_code: stopLossForm.stock_code,
    stock_name: stopLossForm.stock_name,
    buy_price: stopLossForm.buy_price,
    shares: portfolioStore.positions.find(p => p.id === stopLossForm.id)?.shares || 0,
    cost: portfolioStore.positions.find(p => p.id === stopLossForm.id)?.cost || 0,
    buy_date: portfolioStore.positions.find(p => p.id === stopLossForm.id)?.buy_date || '',
    stop_loss: stopLossForm.stop_loss,
    take_profit: stopLossForm.take_profit,
    is_active: true
  });
  
  if (success !== false) {
    showStopLossModal.value = false;
    message.success('止损止盈设置已保存');
  }
};

const showAdjustModal = ref(false);
const adjustForm = reactive({
  id: 0,
  type: 'add' as 'add' | 'reduce',
  stock_code: '',
  stock_name: '',
  current_shares: 0,
  current_cost: 0,
  price: 0,
  shares: 0
});

const openAdjustModal = (position: any, type: 'add' | 'reduce') => {
  adjustForm.id = position.id;
  adjustForm.type = type;
  adjustForm.stock_code = position.stock_code;
  adjustForm.stock_name = position.stock_name;
  adjustForm.current_shares = position.shares;
  adjustForm.current_cost = position.cost;
  adjustForm.price = position.current_price || 0;
  adjustForm.shares = 0;
  showAdjustModal.value = true;
};

const handleAdjustSubmit = async () => {
  const position = portfolioStore.positions.find(p => p.id === adjustForm.id);
  if (!position) return;

  const today = new Date().toISOString().split('T')[0];

  if (adjustForm.type === 'add') {
    const newShares = position.shares + adjustForm.shares;
    const newCost = position.cost + (adjustForm.price * adjustForm.shares);
    const newBuyPrice = newCost / newShares;
    const addAmount = adjustForm.price * adjustForm.shares;
    
    // 更新持仓
    await portfolioStore.updatePosition({
      id: position.id,
      stock_code: position.stock_code,
      stock_name: position.stock_name,
      buy_price: newBuyPrice,
      shares: newShares,
      cost: newCost,
      buy_date: position.buy_date,
      stop_loss: position.stop_loss,
      take_profit: position.take_profit,
      notes: position.notes,
      is_active: true
    });
    
    // 记录加仓历史
    await portfolioStore.addPositionHistory({
      position_id: position.id!,
      stock_code: position.stock_code,
      stock_name: position.stock_name,
      action: 'add',
      shares: adjustForm.shares,
      price: adjustForm.price,
      amount: addAmount,
      date: today,
      notes: `加仓 ${adjustForm.shares} 股，价格 ${adjustForm.price}`
    });
    
    showAdjustModal.value = false;
    message.success(`加仓成功，新增 ${adjustForm.shares} 股`);
  } else {
    const sellAmount = adjustForm.price * adjustForm.shares;
    
    if (adjustForm.shares >= position.shares) {
      // 清仓
      await portfolioStore.deletePosition(position.id);
      
      // 记录清仓历史
      await portfolioStore.addPositionHistory({
        position_id: position.id!,
        stock_code: position.stock_code,
        stock_name: position.stock_name,
        action: 'sell',
        shares: position.shares,
        price: adjustForm.price,
        amount: -sellAmount,
        date: today,
        notes: `清仓 ${position.shares} 股，价格 ${adjustForm.price}`
      });
      
      message.success('已清仓');
    } else {
      const costReduction = (position.cost / position.shares) * adjustForm.shares;
      const newShares = position.shares - adjustForm.shares;
      const newCost = position.cost - costReduction;
      
      // 更新持仓
      await portfolioStore.updatePosition({
        id: position.id,
        stock_code: position.stock_code,
        stock_name: position.stock_name,
        buy_price: position.buy_price,
        shares: newShares,
        cost: newCost,
        buy_date: position.buy_date,
        stop_loss: position.stop_loss,
        take_profit: position.take_profit,
        notes: position.notes,
        is_active: true
      });
      
      // 记录减仓历史
      await portfolioStore.addPositionHistory({
        position_id: position.id!,
        stock_code: position.stock_code,
        stock_name: position.stock_name,
        action: 'reduce',
        shares: adjustForm.shares,
        price: adjustForm.price,
        amount: -sellAmount,
        date: today,
        notes: `减仓 ${adjustForm.shares} 股，价格 ${adjustForm.price}`
      });
      
      message.success(`减仓成功，卖出 ${adjustForm.shares} 股`);
    }
    showAdjustModal.value = false;
  }
};

const showKlineModal = ref(false);
const klineStock = ref<any>(null);
const klineContainer = ref<HTMLElement | null>(null);

const viewKline = (position: any) => {
  klineStock.value = position;
  showKlineModal.value = true;
};

// Position History
const showPositionHistoryModal = ref(false);
const showAddHistoryModal = ref(false);
const showBatchImportModal = ref(false);
const actionLabels: Record<string, string> = {
  buy: '买入',
  sell: '卖出',
  add: '加仓',
  reduce: '减仓'
};

// History form
const historyForm = reactive({
  stock_code: '',
  stock_name: '',
  action: 'buy' as 'buy' | 'sell' | 'add' | 'reduce',
  price: 0,
  shares: 0,
  date: new Date().toISOString().split('T')[0],
  notes: ''
});

// Batch import
const batchImportText = ref('');

const ACTION_MAP: Record<string, string> = {
  '买入': 'buy',
  '卖出': 'sell',
  '加仓': 'add',
  '减仓': 'reduce',
  'buy': 'buy',
  'sell': 'sell',
  'add': 'add',
  'reduce': 'reduce',
};

const parseImportLine = (line: string): { stock_code: string; stock_name: string; action: string; price: number; shares: number; date: string; notes: string } | null => {
  const trimmedLine = line.trim();
  if (!trimmedLine) return null;
  
  // Try comma-separated format first: 股票代码,操作类型,价格,数量,日期
  if (trimmedLine.includes(',')) {
    const parts = trimmedLine.split(',').map(s => s.trim());
    if (parts.length >= 5) {
      return {
        stock_code: parts[0],
        stock_name: '',
        action: ACTION_MAP[parts[1]] || parts[1],
        price: parseFloat(parts[2]),
        shares: parseFloat(parts[3]),
        date: parts[4],
        notes: parts[5] || ''
      };
    }
    return null;
  }
  
  // Try space/tab-separated format: 股票名称 操作类型 价格 数量 日期
  const parts = trimmedLine.split(/[\t\s]+/).map(s => s.trim()).filter(s => s);
  if (parts.length >= 5) {
    const stockName = parts[0];
    const actionRaw = parts[1];
    const price = parseFloat(parts[2]);
    const shares = parseFloat(parts[3]);
    const date = parts[4];
    const notes = parts.slice(5).join(' ') || '';
    
    if (isNaN(price) || isNaN(shares)) return null;
    
    return {
      stock_code: '',
      stock_name: stockName,
      action: ACTION_MAP[actionRaw] || actionRaw,
      price,
      shares,
      date,
      notes
    };
  }
  
  return null;
};

const batchImportPreview = computed(() => {
  if (!batchImportText.value.trim()) return [];
  
  const lines = batchImportText.value.trim().split('\n');
  const records = [];
  
  for (const line of lines) {
    const parsed = parseImportLine(line);
    if (parsed) {
      records.push(parsed);
    }
  }
  
  return records;
});

const openAddHistoryModal = () => {
  historyForm.stock_code = '';
  historyForm.stock_name = '';
  historyForm.action = 'buy';
  historyForm.price = 0;
  historyForm.shares = 0;
  historyForm.date = new Date().toISOString().split('T')[0];
  historyForm.notes = '';
  showAddHistoryModal.value = true;
};

const openBatchImportModal = () => {
  batchImportText.value = '';
  showBatchImportModal.value = true;
};

const handleHistoryStockSelect = (stock: StockInfo) => {
  historyForm.stock_code = stock.code;
  historyForm.stock_name = stock.name;
};

const handleAddHistorySubmit = async () => {
  const amount = historyForm.price * historyForm.shares;
  
  // 查找是否已有该股票的持仓
  const existingPosition = portfolioStore.positions.find(
    p => p.stock_code === historyForm.stock_code
  );
  
  if (historyForm.action === 'buy') {
    // 买入 - 创建新持仓
    if (existingPosition) {
      message.error('该股票已有持仓，请使用加仓功能');
      return;
    }
    
    const newId = await portfolioStore.addPosition({
      stock_code: historyForm.stock_code,
      stock_name: historyForm.stock_name,
      buy_price: historyForm.price,
      shares: historyForm.shares,
      cost: amount,
      buy_date: historyForm.date,
      stop_loss: null,
      take_profit: null,
      notes: historyForm.notes,
      is_active: true
    });
    
    if (newId) {
      await portfolioStore.addPositionHistory({
        position_id: newId,
        stock_code: historyForm.stock_code,
        stock_name: historyForm.stock_name,
        action: 'buy',
        shares: historyForm.shares,
        price: historyForm.price,
        amount: amount,
        date: historyForm.date,
        notes: historyForm.notes || `买入 ${historyForm.shares} 股，价格 ${historyForm.price}`
      });
      message.success('买入记录添加成功');
      showAddHistoryModal.value = false;
      refreshData();
    }
  } else if (historyForm.action === 'add') {
    // 加仓
    if (!existingPosition) {
      message.error('该股票没有持仓，请先买入');
      return;
    }
    
    const newShares = existingPosition.shares + historyForm.shares;
    const newCost = existingPosition.cost + amount;
    const newBuyPrice = newCost / newShares;
    
    await portfolioStore.updatePosition({
      id: existingPosition.id,
      stock_code: existingPosition.stock_code,
      stock_name: existingPosition.stock_name,
      buy_price: newBuyPrice,
      shares: newShares,
      cost: newCost,
      buy_date: existingPosition.buy_date,
      stop_loss: existingPosition.stop_loss,
      take_profit: existingPosition.take_profit,
      notes: existingPosition.notes,
      is_active: true
    });
    
    await portfolioStore.addPositionHistory({
      position_id: existingPosition.id!,
      stock_code: historyForm.stock_code,
      stock_name: historyForm.stock_name,
      action: 'add',
      shares: historyForm.shares,
      price: historyForm.price,
      amount: amount,
      date: historyForm.date,
      notes: historyForm.notes || `加仓 ${historyForm.shares} 股，价格 ${historyForm.price}`
    });
    
    message.success('加仓记录添加成功');
    showAddHistoryModal.value = false;
    refreshData();
  } else if (historyForm.action === 'reduce') {
    // 减仓
    if (!existingPosition) {
      message.error('该股票没有持仓');
      return;
    }
    
    if (historyForm.shares >= existingPosition.shares) {
      message.error('减仓数量不能超过当前持仓，请使用卖出');
      return;
    }
    
    const costReduction = (existingPosition.cost / existingPosition.shares) * historyForm.shares;
    const newShares = existingPosition.shares - historyForm.shares;
    const newCost = existingPosition.cost - costReduction;
    
    await portfolioStore.updatePosition({
      id: existingPosition.id,
      stock_code: existingPosition.stock_code,
      stock_name: existingPosition.stock_name,
      buy_price: existingPosition.buy_price,
      shares: newShares,
      cost: newCost,
      buy_date: existingPosition.buy_date,
      stop_loss: existingPosition.stop_loss,
      take_profit: existingPosition.take_profit,
      notes: existingPosition.notes,
      is_active: true
    });
    
    await portfolioStore.addPositionHistory({
      position_id: existingPosition.id!,
      stock_code: historyForm.stock_code,
      stock_name: historyForm.stock_name,
      action: 'reduce',
      shares: historyForm.shares,
      price: historyForm.price,
      amount: -amount,
      date: historyForm.date,
      notes: historyForm.notes || `减仓 ${historyForm.shares} 股，价格 ${historyForm.price}`
    });
    
    message.success('减仓记录添加成功');
    showAddHistoryModal.value = false;
    refreshData();
  } else if (historyForm.action === 'sell') {
    // 卖出/清仓
    if (!existingPosition) {
      message.error('该股票没有持仓');
      return;
    }
    
    await portfolioStore.deletePosition(existingPosition.id!);
    
    await portfolioStore.addPositionHistory({
      position_id: existingPosition.id!,
      stock_code: historyForm.stock_code,
      stock_name: historyForm.stock_name,
      action: 'sell',
      shares: existingPosition.shares,
      price: historyForm.price,
      amount: -amount,
      date: historyForm.date,
      notes: historyForm.notes || `清仓 ${existingPosition.shares} 股，价格 ${historyForm.price}`
    });
    
    message.success('卖出记录添加成功');
    showAddHistoryModal.value = false;
    refreshData();
  }
};

const handleBatchImport = async () => {
  const records = batchImportPreview.value;
  if (records.length === 0) return;
  
  let successCount = 0;
  let errorCount = 0;
  const errors: string[] = [];
  
  for (const record of records) {
    try {
      let stockCode = record.stock_code;
      let stockName = record.stock_name;
      
      // If stock_code is empty, search by name
      if (!stockCode && stockName) {
        const stockInfo = await getStockInfo(stockName);
        if (stockInfo) {
          stockCode = stockInfo.code;
          stockName = stockInfo.name;
        } else {
          errors.push(`${stockName}: 未找到对应股票`);
          errorCount++;
          continue;
        }
      } else if (stockCode && !stockName) {
        stockName = await getStockName(stockCode);
      }
      
      const existingPosition = portfolioStore.positions.find(
        p => p.stock_code === stockCode
      );
      const amount = record.price * record.shares;
      
      if (record.action === 'buy') {
        if (existingPosition) {
          const newShares = existingPosition.shares + record.shares;
          const newCost = existingPosition.cost + amount;
          const avgPrice = newCost / newShares;
          
          await portfolioStore.updatePosition({
            id: existingPosition.id,
            stock_code: existingPosition.stock_code,
            stock_name: existingPosition.stock_name,
            buy_price: avgPrice,
            shares: newShares,
            cost: newCost,
            buy_date: existingPosition.buy_date,
            stop_loss: existingPosition.stop_loss,
            take_profit: existingPosition.take_profit,
            notes: existingPosition.notes,
            is_active: true
          });
          
          await portfolioStore.addPositionHistory({
            position_id: existingPosition.id!,
            stock_code: stockCode,
            stock_name: existingPosition.stock_name,
            action: 'add',
            shares: record.shares,
            price: record.price,
            amount: amount,
            date: record.date,
            notes: record.notes || `加仓 ${record.shares} 股`
          });
          successCount++;
        } else {
          const newId = await portfolioStore.addPosition({
            stock_code: stockCode,
            stock_name: stockName,
            buy_price: record.price,
            shares: record.shares,
            cost: amount,
            buy_date: record.date,
            stop_loss: null,
            take_profit: null,
            notes: record.notes,
            is_active: true
          });
          
          if (newId) {
            await portfolioStore.addPositionHistory({
              position_id: newId,
              stock_code: stockCode,
              stock_name: stockName,
              action: 'buy',
              shares: record.shares,
              price: record.price,
              amount: amount,
              date: record.date,
              notes: record.notes
            });
            successCount++;
          }
        }
      } else if (record.action === 'sell') {
        if (!existingPosition) {
          errors.push(`${stockName}: 无持仓无法卖出`);
          errorCount++;
          continue;
        }
        
        if (record.shares >= existingPosition.shares) {
          await portfolioStore.deletePosition(existingPosition.id!);
          await portfolioStore.addPositionHistory({
            position_id: existingPosition.id!,
            stock_code: stockCode,
            stock_name: existingPosition.stock_name,
            action: 'sell',
            shares: existingPosition.shares,
            price: record.price,
            amount: -existingPosition.shares * record.price,
            date: record.date,
            notes: record.notes || `清仓 ${existingPosition.shares} 股`
          });
          successCount++;
        } else {
          const costReduction = (existingPosition.cost / existingPosition.shares) * record.shares;
          const newShares = existingPosition.shares - record.shares;
          const newCost = existingPosition.cost - costReduction;
          
          await portfolioStore.updatePosition({
            id: existingPosition.id,
            stock_code: existingPosition.stock_code,
            stock_name: existingPosition.stock_name,
            buy_price: existingPosition.buy_price,
            shares: newShares,
            cost: newCost,
            buy_date: existingPosition.buy_date,
            stop_loss: existingPosition.stop_loss,
            take_profit: existingPosition.take_profit,
            notes: existingPosition.notes,
            is_active: true
          });
          
          await portfolioStore.addPositionHistory({
            position_id: existingPosition.id!,
            stock_code: stockCode,
            stock_name: existingPosition.stock_name,
            action: 'reduce',
            shares: record.shares,
            price: record.price,
            amount: -amount,
            date: record.date,
            notes: record.notes || `减仓 ${record.shares} 股`
          });
          successCount++;
        }
      } else {
        errors.push(`${stockName}: 未知操作类型 ${record.action}`);
        errorCount++;
      }
    } catch (e) {
      errors.push(`${stockName}: 导入失败`);
      errorCount++;
    }
  }
  
  if (errors.length > 0) {
    message.warning(`导入完成：成功 ${successCount} 条，失败 ${errorCount} 条\n${errors.slice(0, 3).join('\n')}`);
  } else {
    message.success(`导入完成：成功 ${successCount} 条`);
  }
  
  if (successCount > 0) {
    showBatchImportModal.value = false;
    refreshData();
  }
};

// Helper function to get stock name
const getStockInfo = async (codeOrName: string): Promise<{ code: string; name: string } | null> => {
  // Check if it's a 6-digit code
  if (/^\d{6}$/.test(codeOrName)) {
    // It's a code, try to find in existing positions first
    const pos = portfolioStore.positions.find(p => p.stock_code === codeOrName);
    if (pos) return { code: codeOrName, name: pos.stock_name };
    
    // Search from API
    try {
      const response = await axios.get('/api/stocks/search', {
        params: { keyword: codeOrName }
      });
      if (response.data.success && response.data.data.length > 0) {
        const match = response.data.data.find((s: any) => s.code === codeOrName);
        if (match) return { code: match.code, name: match.name };
      }
    } catch (e) {
      console.error('获取股票信息失败:', e);
    }
    
    return { code: codeOrName, name: codeOrName };
  }
  
  // It's a name, search from API
  try {
    const response = await axios.get('/api/stocks/search', {
      params: { keyword: codeOrName }
    });
    if (response.data.success && response.data.data.length > 0) {
      const match = response.data.data.find((s: any) => s.name === codeOrName);
      if (match) return { code: match.code, name: match.name };
      
      // If no exact match, use the first result
      const firstMatch = response.data.data[0];
      if (firstMatch) return { code: firstMatch.code, name: firstMatch.name };
    }
  } catch (e) {
    console.error('获取股票信息失败:', e);
  }
  
  // Not found
  return null;
};

const getStockName = async (code: string): Promise<string> => {
  const info = await getStockInfo(code);
  return info?.name || code;
};

// Delete history record
const handleDeleteHistory = async (item: any) => {
  if (confirm(`确定要删除这条 ${item.stock_name} 的${actionLabels[item.action]}记录吗？`)) {
    const success = await portfolioStore.deletePositionHistory(item.id);
    if (success) {
      message.success('删除成功');
    } else {
      message.error('删除失败');
    }
  }
};

// Watch for modal open to fetch history
watch(showPositionHistoryModal, (newVal) => {
  if (newVal) {
    portfolioStore.fetchPositionHistory();
  }
});
</script>

<style scoped>
.portfolio-page {
  position: relative;
  min-height: 100vh;
  background: #03080d;
}

.portfolio-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(ellipse at 30% 85%, rgba(6, 182, 212, 0.04) 0%, transparent 50%),
    radial-gradient(ellipse at 75% 20%, rgba(6, 182, 212, 0.02) 0%, transparent 35%);
  pointer-events: none;
}

.portfolio-grain {
  position: fixed;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  opacity: 0.02;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
}

.portfolio-content {
  position: relative;
  z-index: 2;
}

/* 玻璃拟态卡片 */
.aqua-card {
  background: rgba(8, 12, 16, 0.6);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.aqua-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(6, 182, 212, 0.15) 50%,
    transparent 100%
  );
}

.aqua-card:hover {
  border-color: rgba(6, 182, 212, 0.15);
  box-shadow: 0 4px 24px rgba(6, 182, 212, 0.08);
}

/* 指标卡片 */
.aqua-metric-card {
  background: rgba(8, 12, 16, 0.5);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 1.25rem;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}

.aqua-metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg,
    rgba(6, 182, 212, 0.5) 0%,
    rgba(52, 211, 153, 0.3) 50%,
    transparent 100%
  );
  opacity: 0.4;
}

.aqua-metric-card:hover {
  border-color: rgba(6, 182, 212, 0.12);
  transform: translateY(-1px);
}

.aqua-card-up::before {
  background: linear-gradient(90deg,
    rgba(242, 54, 69, 0.5) 0%,
    rgba(242, 54, 69, 0.2) 50%,
    transparent 100%
  );
}

.aqua-card-down::before {
  background: linear-gradient(90deg,
    rgba(8, 153, 129, 0.5) 0%,
    rgba(8, 153, 129, 0.2) 50%,
    transparent 100%
  );
}

.aqua-metric-label {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 0.5rem;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.aqua-metric-value {
  font-family: 'JetBrains Mono', 'Roboto Mono', monospace;
  font-variant-numeric: tabular-nums;
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.aqua-metric-change {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 6px;
  margin-top: 0.5rem;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.aqua-change-up {
  background: rgba(242, 54, 69, 0.12);
  color: #f23645;
}

.aqua-change-down {
  background: rgba(8, 153, 129, 0.12);
  color: #089981;
}

/* 按钮 */
.btn-aqua {
  transition: all 0.2s ease;
  font-size: 0.85rem;
}

.btn-aqua:hover {
  transform: translateY(-1px);
}

.btn-aqua:active {
  transform: translateY(0);
}

/* 进度条 */
.aqua-progress-bar {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
}

.aqua-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #06b6d4, #34d399);
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

/* 表格 */
.aqua-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

.aqua-table thead th {
  padding: 0.75rem 1rem;
  font-size: 0.7rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.aqua-table tbody tr {
  transition: all 0.2s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.aqua-table tbody tr:hover {
  background: rgba(6, 182, 212, 0.04);
}

.aqua-table tbody td {
  padding: 0.875rem 1rem;
  font-size: 0.875rem;
}

/* 图标按钮 */
.aqua-icon-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  cursor: pointer;
  border: none;
  background: transparent;
}

.aqua-icon-btn:hover {
  transform: scale(1.1);
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.4);
}

.empty-state-icon {
  font-size: 2rem;
  margin-bottom: 0.75rem;
  opacity: 0.5;
}
</style>
