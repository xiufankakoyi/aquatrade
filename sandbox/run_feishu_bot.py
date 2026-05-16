"""
飞书机器人启动脚本 (run_feishu_bot.py)
启动 WebSocket 长连接机器人，支持文本消息和图片 OCR 识别
"""
import json
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.feishu_bot import FeishuBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def handle_image_message(message_info, bot):
    """
    处理图片消息 - 下载图片 → OCR 识别 → 返回 JSON 结果
    
    Args:
        message_info: 消息信息
        bot: 机器人实例
    """
    message_id = message_info.get('message_id')
    chat_id = message_info.get('chat_id')
    content = message_info.get('content', '')
    
    try:
        content_json = json.loads(content)
        image_key = content_json.get('image_key')
        
        if not image_key:
            bot.reply_text(message_id, "❌ 无法获取图片信息")
            return
        
        logger.info(f"开始处理图片: image_key={image_key}")
        
        bot.reply_text(message_id, "📸 正在识别图片中的文字...")
        
        ocr_result = bot.ocr_recognize_from_message(message_id, image_key)
        
        if not ocr_result:
            bot.reply_text(message_id, "❌ OCR 识别失败，请稍后重试")
            return
        
        full_text = ocr_result.get('full_text', '')
        trades = parse_trade_records(full_text)
        
        if trades:
            result_lines = ["📊 交易记录解析结果\n"]
            result_lines.append("股票名称\t\t成交时间\t\t成交数量\t\t成交额\t\t成交方向")
            result_lines.append("-" * 60)
            
            for trade in trades:
                result_lines.append(
                    f"{trade['stock_name']}\t\t{trade['trade_time']}\t\t{trade['quantity']}\t\t{trade['amount']}\t\t{trade['direction']}"
                )
            
            result_lines.append(f"\n共解析 {len(trades)} 条交易记录")
            result_text = "\n".join(result_lines)
        else:
            result_text = f"""📄 OCR 识别结果

识别到 {len(ocr_result.get('text_lines', []))} 行文字：

{full_text}

---
📊 详细信息:
- 图片 Key: {image_key}
- 识别时间: {datetime.now().strftime('%H:%M:%S')}"""
        
        bot.send_text(chat_id, result_text)
        
        logger.info(f"OCR 识别完成: {len(trades) if trades else 0} 条交易记录")
        
    except json.JSONDecodeError:
        bot.reply_text(message_id, "❌ 图片消息格式错误")
    except Exception as e:
        logger.error(f"处理图片消息失败: {e}", exc_info=True)
        bot.reply_text(message_id, f"❌ 处理失败: {str(e)}")


def parse_trade_records(text: str) -> list:
    """
    解析交易记录
    
    根据实际 OCR 格式解析：
    股票名称
    买/卖 + 时间
    价格
    数量
    金额
    
    Args:
        text: OCR 识别的文本
        
    Returns:
        交易记录列表
    """
    import re
    
    trades = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 识别股票名称（2-4个汉字）
        if re.match(r'^[\u4e00-\u9fa5]{2,4}$', line):
            stock_name = line
            
            # 检查下一条是否是买卖标记+时间
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                
                # 匹配 "买14:50:19" 或 "卖11:06:26"
                time_match = re.match(r'^(买|卖)(\d{2}:\d{2}:\d{2})$', next_line)
                
                if time_match:
                    direction = '买入' if time_match.group(1) == '买' else '卖出'
                    trade_time = time_match.group(2)
                    
                    # 后续应该是：价格、数量、金额
                    if i + 4 < len(lines):
                        price = lines[i + 2]
                        quantity = lines[i + 3]
                        amount = lines[i + 4]
                        
                        # 验证格式
                        if (re.match(r'^\d+\.\d+$', price) and 
                            re.match(r'^\d+$', quantity) and
                            re.match(r'^\d+\.\d+$', amount)):
                            
                            trades.append({
                                'stock_name': stock_name,
                                'trade_time': trade_time,
                                'quantity': quantity,
                                'amount': amount,
                                'direction': direction,
                                'price': price,
                            })
                            i += 5
                            continue
        
        i += 1
    
    return trades


def handle_text_message(message_info, bot, text):
    """
    处理文本消息
    
    Args:
        message_info: 消息信息
        bot: 机器人实例
        text: 文本内容
    """
    message_id = message_info.get('message_id')
    chat_id = message_info.get('chat_id')
    
    if text.strip() == '/hello':
        bot.send_text(chat_id, "你好！我是 AquaTrade 机器人 🤖")
    
    elif text.strip() == '/help':
        help_content = """
**可用命令**

- `/help` - 显示帮助信息
- `/hello` - 问候
- `/status` - 查看系统状态

**图片 OCR 识别**

直接发送图片，机器人会自动识别图片中的文字并返回 JSON 格式结果。

**功能说明**

本机器人用于 AquaTrade 量化交易系统，支持：
- 📸 图片 OCR 文字识别
- 📊 实时行情推送
- 📈 交易信号通知
- 📋 策略执行报告
"""
        bot.send_markdown(chat_id, "帮助", help_content)
    
    elif text.strip() == '/status':
        bot.send_text(chat_id, "✅ 系统运行正常\n📊 数据服务在线\n🔗 WebSocket 连接已建立\n📸 OCR 服务就绪")
    
    else:
        bot.send_text(chat_id, f"收到消息: {text}\n\n输入 /help 查看可用命令\n或直接发送图片进行 OCR 识别")


def handle_message(message_info, bot):
    """
    统一消息处理器
    
    Args:
        message_info: 消息信息
        bot: 机器人实例
    """
    content_type = message_info.get('content_type', '')
    content = message_info.get('content', '')
    
    if content_type == 'image':
        handle_image_message(message_info, bot)
    
    elif content_type == 'text':
        try:
            content_json = json.loads(content)
            text = content_json.get('text', '')
        except (json.JSONDecodeError, TypeError):
            text = content
        
        handle_text_message(message_info, bot, text)
    
    else:
        logger.debug(f"跳过非文本/图片消息: {content_type}")


def main():
    """主函数"""
    logger.info("正在启动飞书机器人...")
    
    bot = FeishuBot()
    
    bot.on_message(handle_message)
    
    def signal_handler(sig, frame):
        logger.info("收到停止信号，正在关闭...")
        bot.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("机器人启动成功，等待消息...")
    logger.info("支持功能: 文本消息回复、图片 OCR 识别")
    bot.start(blocking=True)


if __name__ == "__main__":
    main()
