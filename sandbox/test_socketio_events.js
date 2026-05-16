const io = require('../myapp/node_modules/socket.io-client');

console.log('=== 测试 Socket.IO 事件流 ===\n');

const socket = io('http://localhost:5000', {
  path: '/socket.io',
  transports: ['polling'],
  timeout: 20000,
  forceNew: true
});

const events = [];
let errorReceived = false;
let streamCompleteReceived = false;

// 监听所有事件
const eventNames = ['connect', 'disconnect', 'connect_error', 'error', 
  'backtest_start', 'backtest_error', 'backtest_cancelled', 'backtest_cancel_ack',
  'initializing', 'initialized', 'daily_equity', 'new_trade', 'metrics_update', 
  'final_metrics', 'risk_update', 'stream_complete', 'progress', 'request_received'];

eventNames.forEach(eventName => {
  socket.on(eventName, (data) => {
    const timestamp = new Date().toISOString();
    events.push({ event: eventName, data, timestamp });
    
    if (eventName === 'backtest_error') {
      errorReceived = true;
      console.error(`\n❌ [${timestamp}] 收到 backtest_error:`);
      console.error('  数据:', JSON.stringify(data, null, 2));
    } else if (eventName === 'stream_complete') {
      streamCompleteReceived = true;
      console.log(`\n✅ [${timestamp}] 收到 stream_complete:`);
      console.log('  数据:', JSON.stringify(data, null, 2).substring(0, 500));
    } else if (eventName === 'daily_equity') {
      console.log(`[${timestamp}] daily_equity: ${JSON.stringify(data).substring(0, 100)}`);
    } else {
      console.log(`[${timestamp}] ${eventName}`);
    }
  });
});

socket.on('connect', () => {
  console.log('✅ Socket.IO 已连接:', socket.id);
  
  const params = {
    strategy_name: '收敛三角形倒计时策略',
    start_date: '2024-05-20',
    end_date: '2024-05-25',
    benchmark_code: '000300'
  };
  
  console.log('\n📤 发送回测请求:', params);
  socket.emit('run_streaming_backtest', params);
});

// 等待 30 秒后总结
setTimeout(() => {
  console.log('\n\n=== 事件摘要 ===');
  console.log('总事件数:', events.length);
  console.log('是否收到 backtest_error:', errorReceived);
  console.log('是否收到 stream_complete:', streamCompleteReceived);
  
  if (errorReceived && streamCompleteReceived) {
    console.log('\n⚠️ 同时收到了 backtest_error 和 stream_complete！');
    console.log('  这可能是后端在处理 stream_complete 时抛出了异常');
  } else if (streamCompleteReceived) {
    console.log('\n✅ 回测成功完成');
  } else if (errorReceived) {
    console.log('\n❌ 回测失败');
  }
  
  socket.disconnect();
  process.exit(0);
}, 30000);
