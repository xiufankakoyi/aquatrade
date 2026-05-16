// 测试列计算
const defaultColumns = [
  { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code', width: 100, align: 'center' },
  { title: '开盘价', dataIndex: 'open', key: 'open', width: 90, align: 'right' },
  { title: '最高价', dataIndex: 'high', key: 'high', width: 90, align: 'right' },
  { title: '最低价', dataIndex: 'low', key: 'low', width: 90, align: 'right' },
  { title: '收盘价', dataIndex: 'close', key: 'close', width: 90, align: 'right' },
  { title: '涨跌幅', dataIndex: 'change_pct', key: 'change_pct', width: 90, align: 'right' },
  { title: '成交量', dataIndex: 'volume', key: 'volume', width: 100, align: 'right' },
  { title: '成交额', dataIndex: 'amount', key: 'amount', width: 110, align: 'right' },
  { title: '换手率', dataIndex: 'turnover_rate', key: 'turnover_rate', width: 90, align: 'right' },
  { title: '总市值', dataIndex: 'total_mv', key: 'total_mv', width: 110, align: 'right' },
];

const extendedColumns = [
  { title: '流通市值', dataIndex: 'float_mv', key: 'float_mv', width: 110, align: 'right' },
  { title: '市盈率', dataIndex: 'pe', key: 'pe', width: 80, align: 'right' },
  { title: '市净率', dataIndex: 'pb', key: 'pb', width: 80, align: 'right' },
  { title: 'MA5', dataIndex: 'ma5', key: 'ma5', width: 90, align: 'right' },
  { title: 'MA10', dataIndex: 'ma10', key: 'ma10', width: 90, align: 'right' },
  { title: 'MA20', dataIndex: 'ma20', key: 'ma20', width: 90, align: 'right' },
  { title: 'RSI(6)', dataIndex: 'rsi_6', key: 'rsi_6', width: 80, align: 'right' },
  { title: 'RSI(12)', dataIndex: 'rsi_12', key: 'rsi_12', width: 80, align: 'right' },
  { title: 'MACD柱状线', dataIndex: 'macd_bar', key: 'macd_bar', width: 110, align: 'right' },
  { title: 'KDJ J', dataIndex: 'kdj_j', key: 'kdj_j', width: 80, align: 'right' },
  { title: '布林上轨', dataIndex: 'boll_upper', key: 'boll_upper', width: 90, align: 'right' },
  { title: '布林下轨', dataIndex: 'boll_lower', key: 'boll_lower', width: 90, align: 'right' },
  { title: '均线多头排列', dataIndex: 'ma_bull_alignment', key: 'ma_bull_alignment', width: 110, align: 'center' },
  { title: '金叉', dataIndex: 'golden_cross', key: 'golden_cross', width: 70, align: 'center' },
  { title: '死叉', dataIndex: 'death_cross', key: 'death_cross', width: 70, align: 'center' },
  { title: '5日收益', dataIndex: 'ret_5d', key: 'ret_5d', width: 90, align: 'right' },
  { title: '20日收益', dataIndex: 'ret_20d', key: 'ret_20d', width: 90, align: 'right' },
  { title: '20日波动率', dataIndex: 'volatility_20d', key: 'volatility_20d', width: 100, align: 'right' },
  { title: '最大回撤(20)', dataIndex: 'max_drawdown_20d', key: 'max_drawdown_20d', width: 110, align: 'right' },
  { title: 'Beta(60)', dataIndex: 'beta_60d', key: 'beta_60d', width: 90, align: 'right' },
  { title: 'Alpha(60)', dataIndex: 'alpha_60d', key: 'alpha_60d', width: 90, align: 'right' },
  { title: '相关系数(60)', dataIndex: 'corr_60d', key: 'corr_60d', width: 100, align: 'right' },
  { title: '相关系数(120)', dataIndex: 'corr_120d', key: 'corr_120d', width: 100, align: 'right' },
  { title: '相关系数(250)', dataIndex: 'corr_250d', key: 'corr_250d', width: 100, align: 'right' },
  { title: 'Beta(120)', dataIndex: 'beta_120d', key: 'beta_120d', width: 90, align: 'right' },
  { title: 'Beta(250)', dataIndex: 'beta_250d', key: 'beta_250d', width: 90, align: 'right' },
  { title: 'Alpha(120)', dataIndex: 'alpha_120d', key: 'alpha_120d', width: 90, align: 'right' },
  { title: 'Alpha(250)', dataIndex: 'alpha_250d', key: 'alpha_250d', width: 90, align: 'right' },
  { title: '60日收益', dataIndex: 'ret_60d', key: 'ret_60d', width: 90, align: 'right' },
];

// 模拟有数据的情况
const displayColumns = [...defaultColumns, ...extendedColumns];
const scrollX = displayColumns.reduce((total, col) => total + (col.width || 100), 0);

console.log('默认列数:', defaultColumns.length);
console.log('扩展列数:', extendedColumns.length);
console.log('总列数:', displayColumns.length);
console.log('scrollX:', scrollX);
console.log('\n列列表:');
displayColumns.forEach((col, i) => {
  console.log(`${i + 1}. ${col.title} (${col.width}px)`);
});
