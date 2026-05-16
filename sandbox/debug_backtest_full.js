const io = require('../myapp/node_modules/socket.io-client');

console.log('=== 测试 Socket.IO 流式回测（详细日志） ===\n');

const socket = io('http://localhost:5000', {
  path: '/socket.io',
  transports: ['polling'],
  timeout: 20000,
  forceNew: true
});

const events = [];
let hasError = false;

// 监听所有事件
const eventNames = ['connect', 'disconnect', 'connect_error', 'error', 
  'backtest_start', 'backtest_error', 'backtest_cancelled', 'backtest_cancel_ack',
  'initializing', 'initialized', 'daily_update', 'new_trade', 'metrics_update', 
  'final_metrics', 'risk_update', 'stream_complete', 'progress', 'request_received'];

eventNames.forEach(eventName => {
  socket.on(eventName, (data) => {
    const timestamp = new Date().toISOString();
    events.push({ event: eventName, data, timestamp });
    
    if (eventName === 'backtest_error') {
      hasError = true;
      console.error(`\n❌ [${timestamp}] 回测错误:`, JSON.stringify(data, null, 2));
    } else if (eventName === 'stream_complete') {
      console.log(`\n✅ [${timestamp}] 回测完成!`);
      console.log('  最终权益:', data?.finalEquity);
      console.log('  总收益率:', data?.totalReturn + '%');
      console.log('  交易次数:', data?.totalTrades);
      console.log('  交易记录数:', data?.trades?.length || 0);
    } else if (eventName === 'daily_update') {
      // 解码 MsgPack 数据
      if (data && data._msgpack && data._data) {
        try {
          const msgpack = require('../myapp/node_modules/@msgpack/msgpack');
          const decoded = msgpack.decode(Buffer.from(data._data, 'base64'));
          console.log(`[${timestamp}] daily_update: date=${decoded.date}, strategyReturn=${decoded.strategyReturn?.toFixed(4)}, benchmarkReturn=${decoded.benchmarkReturn?.toFixed(4)}`);
        } catch (e) {
          console.log(`[${timestamp}] daily_update: (MsgPack decode failed)`);
        }
      } else {
        console.log(`[${timestamp}] daily_update:`, JSON.stringify(data).substring(0, 100));
      }
    } else if (eventName === 'metrics_update') {
      if (data && data._msgpack && data._data) {
        try {
          const msgpack = require('../myapp/node_modules/@msgpack/msgpack');
          const decoded = msgpack.decode(Buffer.from(data._data, 'base64'));
          console.log(`[${timestamp}] metrics_update:`, JSON.stringify(decoded, null, 2));
        } catch (e) {
          console.log(`[${timestamp}] metrics_update: (MsgPack decode failed)`);
        }
      }
    } else {
      const dataStr = data !== undefined ? JSON.stringify(data).substring(0, 200) : 'undefined';
      console.log(`[${timestamp}] ${eventName}:`, dataStr);
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
  console.log('\n\n=== 最终摘要 ===');
  console.log('总事件数:', events.length);
  console.log('是否有错误:', hasError);
  
  const streamComplete = events.find(e => e.event === 'stream_complete');
  if (streamComplete) {
    console.log('\n✅ 回测成功完成!');
    console.log('  数据:', JSON.stringify(streamComplete.data, null, 2));
  } else if (hasError) {
    console.log('\n❌ 回测失败，有错误发生');
  } else {
    console.log('\n⚠️ 未收到 stream_complete 事件');
  }
  
  socket.disconnect();
  process.exit(0);
}, 30000);
