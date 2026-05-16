const io = require('../myapp/node_modules/socket.io-client');

console.log('=== 测试 Socket.IO 流式回测 ===\n');

const socket = io('http://localhost:5000', {
  path: '/socket.io',
  transports: ['polling'],
  timeout: 20000,
  forceNew: true
});

const events = [];

// 监听所有事件
const eventNames = ['connect', 'disconnect', 'connect_error', 'error', 
  'backtest_start', 'backtest_error', 'backtest_cancelled', 'backtest_cancel_ack',
  'initializing', 'initialized', 'daily_update', 'new_trade', 'metrics_update', 
  'final_metrics', 'risk_update', 'stream_complete', 'progress', 'request_received'];

eventNames.forEach(eventName => {
  socket.on(eventName, (data) => {
    const timestamp = new Date().toISOString();
    const dataStr = data !== undefined ? JSON.stringify(data, null, 2).substring(0, 500) : 'undefined';
    const logEntry = `[${timestamp}] ${eventName}: ${dataStr}`;
    events.push({ event: eventName, data, timestamp });
    console.log(logEntry);
    
    // 如果是错误事件，打印完整错误
    if (eventName === 'backtest_error') {
      console.error('\n❌ 回测错误:', JSON.stringify(data, null, 2));
    }
  });
});

socket.on('connect', () => {
  console.log('✅ Socket.IO 已连接:', socket.id);
  
  // 发送回测请求
  const params = {
    strategy_name: '收敛三角形倒计时策略',
    start_date: '2024-05-20',
    end_date: '2024-05-25',
    benchmark_code: '000300'
  };
  
  console.log('\n📤 发送回测请求:', params);
  socket.emit('run_streaming_backtest', params);
});

// 等待 20 秒后断开
setTimeout(() => {
  console.log('\n=== 事件摘要 ===');
  console.log('收到的事件数:', events.length);
  
  const errorEvents = events.filter(e => e.event.includes('error'));
  if (errorEvents.length > 0) {
    console.log('\n错误事件:');
    errorEvents.forEach(e => {
      console.log(`  - ${e.event}:`, JSON.stringify(e.data, null, 2));
    });
  }
  
  socket.disconnect();
  console.log('\n断开连接');
  process.exit(0);
}, 20000);
