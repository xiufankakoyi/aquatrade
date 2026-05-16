"""
持仓管理相关路由
"""
import re
from flask import Blueprint, request
from server.performance_utils import json_response
from datetime import datetime
from config.logger import get_logger
from pathlib import Path
import json

logger = get_logger(__name__)


def to_camel_case(snake_str: str) -> str:
    """snake_case 转 camelCase"""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def convert_to_camel(data):
    """递归转换字典的 key 为 camelCase"""
    if isinstance(data, dict):
        return {to_camel_case(k): convert_to_camel(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_camel(item) for item in data]
    return data

# Signal config file path
SIGNAL_CONFIG_PATH = Path(__file__).parent.parent.parent / 'data' / 'signal_condition_config.json'

portfolio_bp = Blueprint('portfolio', __name__, url_prefix='/api/portfolio')


@portfolio_bp.route('/positions', methods=['GET'])
def get_positions():
    """
    获取所有持仓
    """
    from core.portfolio.position_manager import PositionManager
    
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        manager = PositionManager()
        positions = manager.get_all_positions(active_only=active_only)
        
        positions_data = []
        for pos in positions:
            pos_dict = {}
            for key, value in pos.__dict__.items():
                if not key.startswith('_'):
                    pos_dict[key] = value
            positions_data.append(convert_to_camel(pos_dict))
        
        return json_response({
            "success": True,
            "data": positions_data
        })
    except Exception as e:
        logger.error(f"获取持仓失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/positions', methods=['POST'])
def add_position():
    """
    添加持仓
    """
    from core.portfolio.position_manager import PositionManager, Position
    
    try:
        data = request.get_json()
        if not data:
            return json_response({"success": False, "error": "缺少请求数据"}, status_code=400)
        
        required_fields = ['stock_code', 'stock_name', 'buy_price', 'shares', 'cost', 'buy_date']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return json_response({"success": False, "error": f"缺少必要字段: {missing}"}, status_code=400)
        
        position = Position(
            stock_code=str(data['stock_code']).zfill(6),
            stock_name=data['stock_name'],
            buy_price=float(data['buy_price']),
            shares=float(data['shares']),
            cost=float(data['cost']),
            buy_date=data['buy_date'],
            stop_loss=float(data['stop_loss']) if data.get('stop_loss') else None,
            take_profit=float(data['take_profit']) if data.get('take_profit') else None,
            notes=data.get('notes', '')
        )
        
        manager = PositionManager()
        position_id = manager.add_position(position)
        
        return json_response({
            "success": True,
            "data": {"id": position_id}
        })
    except Exception as e:
        logger.error(f"添加持仓失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/positions/<int:position_id>', methods=['PUT'])
def update_position(position_id: int):
    """
    更新持仓
    """
    from core.portfolio.position_manager import PositionManager, Position
    
    try:
        data = request.get_json()
        if not data:
            return json_response({"success": False, "error": "缺少请求数据"}, status_code=400)
        
        print(f"[update_position] 收到更新请求, position_id={position_id}")
        print(f"[update_position] data={data}")
        
        manager = PositionManager()
        existing = manager.get_position(position_id)
        if not existing:
            return json_response({"success": False, "error": "持仓不存在"}, status_code=404)
        
        is_active_value = data.get('is_active', existing.is_active)
        print(f"[update_position] is_active from request: {is_active_value}, type: {type(is_active_value)}")
        
        position = Position(
            id=position_id,
            stock_code=str(data.get('stock_code', existing.stock_code)).zfill(6),
            stock_name=data.get('stock_name', existing.stock_name),
            buy_price=float(data.get('buy_price', existing.buy_price)),
            shares=float(data.get('shares', existing.shares)),
            cost=float(data.get('cost', existing.cost)),
            buy_date=data.get('buy_date', existing.buy_date),
            stop_loss=float(data['stop_loss']) if data.get('stop_loss') else existing.stop_loss,
            take_profit=float(data['take_profit']) if data.get('take_profit') else existing.take_profit,
            notes=data.get('notes', existing.notes),
            is_active=bool(is_active_value)
        )
        
        print(f"[update_position] position.is_active={position.is_active}, type={type(position.is_active)}")
        
        success = manager.update_position(position)
        
        return json_response({
            "success": success,
            "data": {"id": position_id} if success else None
        })
    except Exception as e:
        logger.error(f"更新持仓失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/positions/<int:position_id>', methods=['DELETE'])
def delete_position(position_id: int):
    """
    删除持仓
    """
    from core.portfolio.position_manager import PositionManager
    
    try:
        manager = PositionManager()
        success = manager.delete_position(position_id)
        
        return json_response({
            "success": success
        })
    except Exception as e:
        logger.error(f"删除持仓失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/analysis', methods=['GET'])
def get_analysis():
    """
    获取持仓分析（盈亏、仓位占比、行业分布）
    """
    from core.portfolio.position_manager import PositionManager
    
    try:
        manager = PositionManager()
        positions = manager.get_all_positions(active_only=True)
        
        if not positions:
            return json_response({
                "success": True,
                "data": {
                    "positions": [],
                    "summary": {
                        "total_market_value": 0,
                        "total_cost": 0,
                        "total_profit_loss": 0,
                        "total_profit_loss_pct": 0,
                        "position_count": 0
                    },
                    "industry_distribution": {}
                }
            })
        
        from core.portfolio.signal_engine import SignalEngine
        signal_engine = SignalEngine()
        stock_codes = [p.stock_code for p in positions]
        latest_prices = signal_engine.get_latest_prices(stock_codes)
        
        analysis = manager.calculate_analysis(positions, latest_prices)
        
        analyzed_positions = analysis.get('positions', [])
        analyzed_positions = convert_to_camel(analyzed_positions)
        
        industry_dist = manager.get_industry_distribution_from_dict(analysis.get('positions', []))
        
        analysis['positions'] = analyzed_positions
        analysis['industry_distribution'] = industry_dist
        
        return json_response({
            "success": True,
            "data": convert_to_camel(analysis)
        })
    except Exception as e:
        logger.error(f"获取持仓分析失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/signals', methods=['GET'])
def get_signals():
    """
    获取今日信号
    """
    from core.portfolio.position_manager import PositionManager
    from core.portfolio.signal_engine import SignalEngine
    
    try:
        manager = PositionManager()
        positions = manager.get_all_positions(active_only=True)
        stock_codes = [p.stock_code for p in positions]
        
        watchlist = request.args.get('watchlist', '')
        if watchlist:
            stock_codes.extend([c.strip() for c in watchlist.split(',') if c.strip()])
        
        signal_engine = SignalEngine()
        signals = signal_engine.generate_signals(list(set(stock_codes)))
        
        result = {
            'buy': convert_to_camel([s.__dict__ for s in signals['buy']]),
            'sell': convert_to_camel([s.__dict__ for s in signals['sell']]),
            'watch': convert_to_camel([s.__dict__ for s in signals['watch']])
        }
        
        return json_response({
            "success": True,
            "data": result
        })
    except Exception as e:
        logger.error(f"获取信号失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/signals/history', methods=['GET'])
def get_signal_history():
    """
    获取历史信号
    """
    from core.portfolio.signal_engine import SignalEngine
    
    try:
        stock_code = request.args.get('stock_code')
        days = int(request.args.get('days', 30))
        
        signal_engine = SignalEngine()
        history = signal_engine.get_signal_history(stock_code, days)
        
        return json_response({
            "success": True,
            "data": history
        })
    except Exception as e:
        logger.error(f"获取历史信号失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/rules', methods=['GET'])
def get_rules():
    """
    获取信号规则配置
    """
    from core.portfolio.signal_engine import SignalEngine
    
    try:
        signal_engine = SignalEngine()
        
        return json_response({
            "success": True,
            "data": signal_engine.rules
        })
    except Exception as e:
        logger.error(f"获取规则失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/rules', methods=['POST'])
def update_rules():
    """
    更新信号规则配置
    """
    from core.portfolio.signal_engine import SignalEngine
    
    try:
        data = request.get_json()
        if not data:
            return json_response({"success": False, "error": "缺少请求数据"}, status_code=400)
        
        signal_engine = SignalEngine()
        signal_engine.save_rules(data)
        
        return json_response({
            "success": True,
            "data": signal_engine.rules
        })
    except Exception as e:
        logger.error(f"更新规则失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/report', methods=['GET'])
def get_report():
    """
    生成每日报告
    """
    from core.portfolio.report_generator import ReportGenerator
    
    try:
        generator = ReportGenerator()
        report = generator.generate_daily_report()
        
        return json_response({
            "success": True,
            "data": {"report": report}
        })
    except Exception as e:
        logger.error(f"生成报告失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/push', methods=['POST'])
def push_to_feishu():
    """
    推送报告到飞书
    """
    from core.portfolio.report_generator import ReportGenerator
    
    try:
        data = request.get_json() or {}
        webhook_url = data.get('webhook_url')
        
        generator = ReportGenerator()
        success = generator.generate_and_push(webhook_url)
        
        return json_response({
            "success": success,
            "message": "推送成功" if success else "推送失败"
        })
    except Exception as e:
        logger.error(f"推送飞书失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/suggestions', methods=['GET'])
def get_suggestions():
    """
    获取操作建议
    """
    from core.portfolio.report_generator import ReportGenerator
    
    try:
        watchlist = request.args.get('watchlist', '')
        watchlist_codes = [c.strip() for c in watchlist.split(',') if c.strip()] if watchlist else None
        
        generator = ReportGenerator()
        suggestions = generator.generate_operation_suggestions(watchlist=watchlist_codes)
        
        return json_response({
            "success": True,
            "data": suggestions
        })
    except Exception as e:
        logger.error(f"获取操作建议失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/import', methods=['POST'])
def import_positions():
    """
    从 Excel 导入持仓
    """
    from core.portfolio.position_manager import PositionManager
    
    try:
        data = request.get_json()
        if not data or 'file_path' not in data:
            return json_response({"success": False, "error": "缺少 file_path 参数"}, status_code=400)
        
        manager = PositionManager()
        count = manager.import_from_excel(data['file_path'])
        
        return json_response({
            "success": True,
            "data": {"imported_count": count}
        })
    except Exception as e:
        logger.error(f"导入持仓失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/signal-config', methods=['GET'])
def get_signal_config():
    """
    获取信号条件配置
    """
    try:
        if SIGNAL_CONFIG_PATH.exists():
            with open(SIGNAL_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {
                "signalType": "buy",
                "conditionGroups": []
            }
        
        return json_response({
            "success": True,
            "data": config
        })
    except Exception as e:
        logger.error(f"获取信号配置失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/signal-config', methods=['POST'])
def update_signal_config():
    """
    更新信号条件配置
    """
    try:
        data = request.get_json()
        if not data:
            return json_response({"success": False, "error": "缺少请求数据"}, status_code=400)
        
        SIGNAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(SIGNAL_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return json_response({
            "success": True,
            "data": data
        })
    except Exception as e:
        logger.error(f"更新信号配置失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


FEISHU_WEBHOOK_PATH = Path(__file__).parent.parent.parent / 'data' / 'feishu_webhook.json'


@portfolio_bp.route('/watchlist', methods=['GET'])
def get_watchlist():
    """
    获取监控股票列表
    """
    from core.portfolio.watchlist_manager import WatchlistManager
    
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        manager = WatchlistManager()
        items = manager.get_all_items(active_only=active_only)
        
        return json_response({
            "success": True,
            "data": convert_to_camel([item.__dict__ for item in items])
        })
    except Exception as e:
        logger.error(f"获取监控列表失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/watchlist', methods=['POST'])
def add_watchlist_item():
    """
    添加监控股票
    
    Request Body:
    {
        "stock_code": "000001",
        "stock_name": "平安银行",
        "buy_target_price": 10.5,  // 可选，买入目标价
        "sell_target_price": 15.0,  // 可选，卖出目标价
        "conditions": [  // 可选，监控条件列表
            {"key": "ma5_break_up", "enabled": true, "params": {}},
            {"key": "rsi_oversold", "enabled": true, "params": {"threshold": 30}}
        ],
        "notes": "备注",
        "tags": ["科技", "龙头"],
        "is_active": true,
        "feishu_notify": true
    }
    """
    from core.portfolio.watchlist_manager import WatchlistManager, WatchItem
    
    try:
        data = request.get_json()
        if not data:
            return json_response({"success": False, "error": "缺少请求数据"}, status_code=400)
        
        required_fields = ['stock_code', 'stock_name']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return json_response({"success": False, "error": f"缺少必要字段: {missing}"}, status_code=400)
        
        item = WatchItem(
            stock_code=str(data['stock_code']).zfill(6),
            stock_name=data['stock_name'],
            buy_target_price=float(data['buy_target_price']) if data.get('buy_target_price') else None,
            sell_target_price=float(data['sell_target_price']) if data.get('sell_target_price') else None,
            conditions=data.get('conditions', []),
            notes=data.get('notes', ''),
            tags=data.get('tags', []),
            is_active=bool(data.get('is_active', True)),
            feishu_notify=bool(data.get('feishu_notify', True))
        )
        
        manager = WatchlistManager()
        item_id = manager.add_item(item)
        
        return json_response({
            "success": True,
            "data": {"id": item_id}
        })
    except Exception as e:
        logger.error(f"添加监控股票失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/watchlist/<int:item_id>', methods=['PUT'])
def update_watchlist_item(item_id: int):
    """
    更新监控股票
    """
    from core.portfolio.watchlist_manager import WatchlistManager, WatchItem
    
    try:
        data = request.get_json()
        if not data:
            return json_response({"success": False, "error": "缺少请求数据"}, status_code=400)
        
        manager = WatchlistManager()
        existing = manager.get_item(item_id)
        if not existing:
            return json_response({"success": False, "error": "监控记录不存在"}, status_code=404)
        
        item = WatchItem(
            id=item_id,
            stock_code=str(data.get('stock_code', existing.stock_code)).zfill(6),
            stock_name=data.get('stock_name', existing.stock_name),
            buy_target_price=float(data['buy_target_price']) if data.get('buy_target_price') else existing.buy_target_price,
            sell_target_price=float(data['sell_target_price']) if data.get('sell_target_price') else existing.sell_target_price,
            conditions=data.get('conditions', existing.conditions),
            notes=data.get('notes', existing.notes),
            tags=data.get('tags', existing.tags),
            is_active=bool(data.get('is_active', existing.is_active)),
            feishu_notify=bool(data.get('feishu_notify', existing.feishu_notify)),
            last_trigger_time=existing.last_trigger_time,
            last_trigger_condition=existing.last_trigger_condition,
            last_notify_time=existing.last_notify_time
        )
        
        success = manager.update_item(item)
        
        return json_response({
            "success": success,
            "data": {"id": item_id} if success else None
        })
    except Exception as e:
        logger.error(f"更新监控股票失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/watchlist/<int:item_id>', methods=['DELETE'])
def delete_watchlist_item(item_id: int):
    """
    删除监控股票
    """
    from core.portfolio.watchlist_manager import WatchlistManager
    
    try:
        manager = WatchlistManager()
        success = manager.delete_item(item_id)
        
        return json_response({
            "success": success
        })
    except Exception as e:
        logger.error(f"删除监控股票失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/watchlist/check-signals', methods=['POST'])
def check_watchlist_signals():
    """
    检查监控股票信号并发送飞书通知
    
    前端上线时调用此接口，自动检测信号并推送
    """
    from core.portfolio.watchlist_manager import WatchlistManager
    
    try:
        data = request.get_json() or {}
        webhook_url = data.get('webhook_url')
        cooldown_hours = data.get('cooldown_hours', 4)
        
        if not webhook_url:
            if FEISHU_WEBHOOK_PATH.exists():
                with open(FEISHU_WEBHOOK_PATH, 'r', encoding='utf-8') as f:
                    webhook_config = json.load(f)
                    webhook_url = webhook_config.get('webhook_url')
        
        manager = WatchlistManager()
        result = manager.check_all_signals(
            feishu_webhook=webhook_url,
            cooldown_hours=cooldown_hours
        )
        
        return json_response({
            "success": True,
            "data": result
        })
    except Exception as e:
        logger.error(f"检查信号失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/watchlist/batch', methods=['POST'])
def batch_add_watchlist():
    """
    批量添加监控股票
    
    Request Body:
    {
        "items": [
            {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "conditions": [...],
                ...
            }
        ]
    }
    """
    from core.portfolio.watchlist_manager import WatchlistManager, WatchItem
    
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return json_response({"success": False, "error": "缺少 items 字段"}, status_code=400)
        
        items_data = data['items']
        items = []
        
        for item_data in items_data:
            item = WatchItem(
                stock_code=str(item_data.get('stock_code', '')).zfill(6),
                stock_name=item_data.get('stock_name', ''),
                buy_target_price=float(item_data['buy_target_price']) if item_data.get('buy_target_price') else None,
                sell_target_price=float(item_data['sell_target_price']) if item_data.get('sell_target_price') else None,
                conditions=item_data.get('conditions', []),
                notes=item_data.get('notes', ''),
                tags=item_data.get('tags', []),
                is_active=bool(item_data.get('is_active', True)),
                feishu_notify=bool(item_data.get('feishu_notify', True))
            )
            items.append(item)
        
        manager = WatchlistManager()
        count = manager.batch_add(items)
        
        return json_response({
            "success": True,
            "data": {"added_count": count}
        })
    except Exception as e:
        logger.error(f"批量添加监控股票失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/feishu-webhook', methods=['GET'])
def get_feishu_webhook():
    """
    获取飞书 webhook 配置
    """
    try:
        if FEISHU_WEBHOOK_PATH.exists():
            with open(FEISHU_WEBHOOK_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {"webhook_url": ""}
        
        masked_url = ""
        if config.get('webhook_url'):
            url = config['webhook_url']
            if len(url) > 30:
                masked_url = url[:20] + "****" + url[-10:]
            else:
                masked_url = "****"
        
        return json_response({
            "success": True,
            "data": {
                "webhook_url": config.get('webhook_url', ''),
                "masked_url": masked_url,
                "is_configured": bool(config.get('webhook_url'))
            }
        })
    except Exception as e:
        logger.error(f"获取飞书配置失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/feishu-webhook', methods=['POST'])
def update_feishu_webhook():
    """
    更新飞书 webhook 配置
    """
    try:
        data = request.get_json()
        if not data or 'webhook_url' not in data:
            return json_response({"success": False, "error": "缺少 webhook_url 字段"}, status_code=400)
        
        FEISHU_WEBHOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(FEISHU_WEBHOOK_PATH, 'w', encoding='utf-8') as f:
            json.dump({"webhook_url": data['webhook_url']}, f)
        
        return json_response({
            "success": True,
            "message": "飞书 webhook 配置已保存"
        })
    except Exception as e:
        logger.error(f"更新飞书配置失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/feishu-webhook/test', methods=['POST'])
def test_feishu_webhook():
    """
    测试飞书 webhook 推送
    """
    from core.dragon_eye.feishu_push import FeishuPush
    
    try:
        data = request.get_json() or {}
        webhook_url = data.get('webhook_url')
        
        if not webhook_url:
            if FEISHU_WEBHOOK_PATH.exists():
                with open(FEISHU_WEBHOOK_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    webhook_url = config.get('webhook_url')
        
        if not webhook_url:
            return json_response({"success": False, "error": "未配置飞书 webhook"}, status_code=400)
        
        feishu = FeishuPush(webhook_url)
        
        test_message = f"🔔 **测试消息**\n\n这是一条来自 AquaTrade 的测试通知。\n\n发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        success = feishu.push_markdown(test_message, "AquaTrade 测试通知")
        
        return json_response({
            "success": success,
            "message": "测试消息发送成功" if success else "测试消息发送失败"
        })
    except Exception as e:
        logger.error(f"测试飞书推送失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/watchlist/conditions', methods=['GET'])
def get_supported_conditions():
    """
    获取支持的监控条件列表
    """
    from core.portfolio.watchlist_manager import WatchlistManager
    
    try:
        conditions = WatchlistManager.get_supported_conditions()
        
        return json_response({
            "success": True,
            "data": conditions
        })
    except Exception as e:
        logger.error(f"获取监控条件失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/position-history', methods=['GET'])
def get_position_history():
    """
    获取持仓历史记录
    """
    from core.portfolio.position_history_manager import PositionHistoryManager
    
    try:
        position_id = request.args.get('position_id', type=int)
        
        manager = PositionHistoryManager()
        history = manager.get_history(position_id)
        stats = manager.get_stats(position_id)
        
        return json_response({
            "success": True,
            "data": {
                "history": convert_to_camel([h.__dict__ for h in history]),
                "stats": convert_to_camel(stats.__dict__)
            }
        })
    except Exception as e:
        logger.error(f"获取持仓历史失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/position-history', methods=['POST'])
def add_position_history():
    """
    添加持仓历史记录
    """
    from core.portfolio.position_history_manager import PositionHistoryManager, PositionHistory
    
    try:
        data = request.get_json()
        if not data:
            return json_response({"success": False, "error": "缺少请求数据"}, status_code=400)
        
        required_fields = ['position_id', 'stock_code', 'stock_name', 'action', 'shares', 'price', 'amount', 'date']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return json_response({"success": False, "error": f"缺少必要字段: {missing}"}, status_code=400)
        
        history = PositionHistory(
            position_id=int(data['position_id']),
            stock_code=str(data['stock_code']).zfill(6),
            stock_name=data['stock_name'],
            action=data['action'],
            shares=float(data['shares']),
            price=float(data['price']),
            amount=float(data['amount']),
            date=data['date'],
            notes=data.get('notes', '')
        )
        
        manager = PositionHistoryManager()
        history_id = manager.add_history(history)
        
        return json_response({
            "success": True,
            "data": {"id": history_id}
        })
    except Exception as e:
        logger.error(f"添加持仓历史失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@portfolio_bp.route('/position-history/<int:history_id>', methods=['DELETE'])
def delete_position_history(history_id):
    """
    删除持仓历史记录
    """
    from core.portfolio.position_history_manager import PositionHistoryManager
    
    try:
        manager = PositionHistoryManager()
        success = manager.delete_history(history_id)
        
        if success:
            return json_response({
                "success": True,
                "message": "删除成功"
            })
        else:
            return json_response({
                "success": False,
                "error": "记录不存在或删除失败"
            }, status_code=404)
    except Exception as e:
        logger.error(f"删除持仓历史失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)
