"""
敏感配置文件 (config/secrets.py)
==============================
存放所有 API 密钥、Token 等敏感信息。

【安全说明】
- 此文件已在 .gitignore 中，不会被提交到 Git
- 首次使用请复制 secrets_template.py 为 secrets.py 并填入真实值
- 切勿将此文件分享给他人或上传到公开仓库
"""

class Secrets:
    """敏感配置类 - 存放所有密钥和凭证"""
    
    # ============================================
    # Tushare 金融数据接口
    # 获取地址：https://tushare.pro/register
    # ============================================
    TUSHARE_TOKEN = ""
    
    # ============================================
    # DragonEye 龙虎榜监控凭证
    # ============================================
    DRAGON_USERNAME = ""
    DRAGON_PASSWORD = ""
    DRAGON_TOKEN = ""
    
    # ============================================
    # QuickTiny (stock.quicktiny.cn) 爬虫凭证
    # 用于获取龙头股、市场情绪等数据
    # ============================================
    QUICKTINY_TOKEN = ""
    QUICKTINY_USERNAME = ""
    QUICKTINY_PASSWORD = ""
    
    # ============================================
    # 飞书配置
    # ============================================
    # Webhook 推送地址（用于单向消息推送）
    FEISHU_WEBHOOK = ""
    
    # 机器人配置（用于 WebSocket 长连接）
    # 获取方式：飞书开放平台 -> 开发者后台 -> 应用详情页 -> 凭证与基础信息
    # 
    # 【必需权限】
    # 在飞书开放平台 -> 权限管理 中开通以下权限：
    # - im:message - 获取与发送消息
    # - im:message:send_as_bot - 以应用身份发消息
    # - im:message.p2p_msg:readonly - 读取用户发给机器人的单聊消息
    # - im:message.group_at_msg:readonly - 接收群聊中@机器人消息事件
    # - im:chat - 获取群组信息
    # - im:resource - 获取消息中的图片/文件资源
    # - optical_char_recognition:optical_char_recognition - OCR 文字识别
    # 
    # 【事件订阅】
    # 在事件与回调 -> 事件配置 中添加：
    # - im.message.receive_v1 - 接收消息事件
    # 
    # 【订阅方式】
    # 选择「使用长连接接收事件」
    FEISHU_APP_ID = ""
    FEISHU_APP_SECRET = ""
    
    # ============================================
    # LLM 大模型配置
    # ============================================
    LLM_API_BASE = "http://127.0.0.1:1234/v1"
    LLM_API_KEY = "lm-studio"
    LLM_MODEL_NAME = "qwen2.5-7b"
    
    # ============================================
    # Redis 配置（如需密码认证）
    # ============================================
    REDIS_PASSWORD = ""
    
    # ============================================
    # 其他 API 密钥
    # ============================================
    # 在此添加其他第三方服务密钥
