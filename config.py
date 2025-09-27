"""
Telegram商户机器人配置文件
包含机器人设置、管理员ID、消息模板和环境特定配置
"""

import os
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class BotConfig:
    """机器人配置设置"""
    token: str  # 机器人令牌
    webhook_url: str  # Webhook URL地址
    webhook_path: str = "/webhook"  # Webhook路径
    webhook_port: int = 8000  # Webhook端口
    use_webhook: bool = True  # 是否使用Webhook模式，开发时设为False使用轮询


@dataclass
class DatabaseConfig:
    """数据库配置设置"""
    db_path: str  # 数据库文件路径
    connection_timeout: int = 30  # 连接超时时间（秒）
    max_connections: int = 10  # 最大连接数


# ============================================================================
# 上榜流程配置 - 版本切换控制
# ============================================================================

# 上榜流程版本控制 - 控制使用新版还是旧版流程
USE_NEW_BINDING_FLOW = True  # True=新版7步动态流程, False=旧版固定流程

# 新版7步流程特性开关
BINDING_FLOW_CONFIG = {
    "use_new_flow": USE_NEW_BINDING_FLOW,
    "enable_user_detection": True,      # 启用用户信息自动检测
    "enable_bot_detection": True,       # 启用机器人行为检测  
    "enable_keyword_system": True,      # 启用关键词标签系统
    "enable_price_collection": True,    # 启用价格信息收集
    "enable_smart_validation": True,    # 启用智能数据验证
    "auto_region_sync": True,           # 自动同步地区数据到商户表
}

# 流程版本说明
BINDING_FLOW_VERSION_INFO = {
    "current_version": "NewBindingFlow" if USE_NEW_BINDING_FLOW else "BindingFlow v1.0",
    "description": "7步动态智能上榜流程" if USE_NEW_BINDING_FLOW else "5步固定上榜流程",
    "features": [
        "智能用户检测", "动态地区管理", "关键词系统", "价格收集", "机器人防护"
    ] if USE_NEW_BINDING_FLOW else [
        "固定地区选项", "固定分类选项", "基础资料生成"
    ]
}


# 环境变量配置
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")  # 从环境变量获取机器人令牌
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-app.railway.app")  # Webhook URL地址
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "123456789").split(",")]  # 管理员ID列表
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "-1001234567890")  # 频道/群组ID
WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD", "admin123")  # 网页管理面板密码

# 生成 deeplink 所用的 Bot 用户名（自动根据 RUN_MODE 选择默认值，可被环境变量覆盖）
def _sanitize_bot_username(u: str) -> str:
    try:
        return (u or '').lstrip('@').strip()
    except Exception:
        return u

def _resolve_deeplink_bot_username() -> str:
    run_mode = os.getenv("RUN_MODE", "dev").lower()
    # 1) 显式配置优先
    env_value = os.getenv("DEEPLINK_BOT_USERNAME")
    if env_value:
        return _sanitize_bot_username(env_value)
    # 2) 根据运行模式选择默认
    if run_mode == 'dev':
        # 本地开发默认使用 @wudixxoobot
        return _sanitize_bot_username("wudixxoobot")
    # 生产/其他模式默认使用 @xiaojisystembot
    return _sanitize_bot_username("xiaojisystembot")

DEEPLINK_BOT_USERNAME = _resolve_deeplink_bot_username()

# 帖子状态配置 - 帖子生命周期管理
POST_STATUSES = [
    'pending_submission',  # 等待商户提交信息
    'pending_approval',    # 等待管理员审核
    'approved',           # 已审核，等待发布
    'published',          # 已发布
    'expired'             # 已过期
]

# 机器人配置实例
bot_config = BotConfig(
    token=BOT_TOKEN,  # 机器人令牌
    webhook_url=WEBHOOK_URL,  # Webhook URL
    use_webhook=os.getenv("USE_WEBHOOK", "true").lower() == "true"  # 是否使用Webhook模式
)

# 轮询单实例锁开关：默认仅在轮询模式开启（开发环境常用），生产Webhook默认关闭
_env_lock = os.getenv("POLLING_LOCK_ENABLED")
if _env_lock is None:
    POLLING_LOCK_ENABLED = not bot_config.use_webhook
else:
    POLLING_LOCK_ENABLED = _env_lock.lower() == "true"

# 消息模板配置 - 定义机器人发送的各种消息格式
MESSAGE_TEMPLATES = {
    # 管理员相关消息
    "admin_help": """
🔧 管理员命令:

/set_button - 配置自定义消息和按钮
/view_stats - 查看点击和交互统计
/generate_code - 生成商户绑定码
/help - 显示此帮助信息
    """,
    
    "merchant_info_template": """
老师名称：{name}
地区：{province} - {region}
价格：P{p_price} | PP{pp_price}
一句话优势：{adv_sentence}
特点：{keywords}
    """,
    
    # 新版商家信息精简模板
    "merchant_info_simple": """
📋 {name} ({merchant_type})
📍 {province} - {region} | 💰 P{p_price}/PP{pp_price}
🏷️ {keywords}
📞 {contact_info}
    """,
    
    # 商户相关消息
    "merchant_welcome": """
🏪 欢迎来到商户注册系统！

要开始注册，请发送"上榜流程"来开始注册过程。
    """,
    
    "binding_code_request": """
🔑 要注册为商户，您需要一个绑定码。

请联系管理员 @{admin_username} 获取您的绑定码。
    """,
    
    "binding_code_prompt": """
🔑 请输入您的绑定码：
    """,
    
    "invalid_binding_code": """
❌ 绑定码无效或已过期。请联系管理员获取新的绑定码。
    """,
    
    "binding_success": """
✅ 注册成功！

您的商户资料已创建并激活。现在您可以通过机器人接收客户咨询。
    """,
    
    # 新7步绑定流程消息模板
    "user_info_detection": """
🔍 用户信息检测

我们正在分析您的Telegram账号信息...

检测到以下信息：
👤 用户名: {username}
📝 姓名: {full_name}
📊 账号类型: {user_type}
🤖 机器人概率: {bot_probability:.1%}

{detection_details}
    """,
    
    "merchant_type_selection": """
🏪 步骤 1/7: 选择商家类型

请选择您要注册的商家类型：

每种类型提供不同的服务模式和功能。选择最符合您业务需求的类型。
    """,
    
    "province_selection": """
🌍 步骤 2/7: 选择省份

请选择您的商户所在省份：

我们会根据地区为您提供本地化的服务和推荐。
    """,
    
    "region_selection": """
🏙️ 步骤 3/7: 选择区域

您选择的省份: {province_name}

请选择您的具体所在区域：
    """,
    
    "p_price_input": """
💰 步骤 4/7: 设置P价格

请输入您的P价格（主要服务价格）：

💡 输入说明：
• 请输入数字金额（如：100）
• 支持小数点（如：99.5）
• 这将作为您的主要服务定价
    """,
    
    "pp_price_input": """
💎 步骤 5/7: 设置PP价格

您的P价格: ¥{p_price}

请输入您的PP价格（高级服务价格）：

💡 输入说明：
• 请输入数字金额（如：200）
• 支持小数点（如：199.5）
• 这将作为您的高级服务定价
• 通常PP价格高于P价格
    """,
    
    "adv_sentence_input": """
📝 步骤 6/7: 一句话优势

请输入你的一句话优势（建议≤30字）：

💡 填写建议：
• 用简短话语突出核心优势
• 避免长段落与联系方式
• 不超过30字
• 将在频道贴文首行展示
    """,
    
    "keyword_selection": """
🏷️ 步骤 7/7: 选择关键词

请选择适合您商户的关键词标签（可多选）：

已选择关键词: {selected_keywords}

💡 选择建议：
• 选择与您服务相关的关键词
• 多个关键词有助于客户找到您
• 点击关键词进行选择/取消选择
• 选择完成后点击"完成选择"
    """,
    
    "binding_confirmation": """
✅ 注册信息确认

请确认以下信息是否正确：

👤 商户类型: {merchant_type}
📍 地区: {province} - {region}
💰 P价格: ¥{p_price}
💎 PP价格: ¥{pp_price}
📝 一句话优势: {adv_sentence}
🏷️ 关键词: {keywords}

🔍 用户检测结果: {user_analysis}

确认无误请点击"确认注册"，需要修改请点击"重新填写"。
    """,
    
    "binding_flow_complete": """
🎉 注册完成！

恭喜！您的商户资料已成功创建并激活。

📋 您的商户信息:
👤 类型: {merchant_type}
📍 地区: {province} - {region}
💰 价格: P¥{p_price} / PP¥{pp_price}
📝 一句话优势: {adv_sentence}
🏷️ 关键词: {keywords}

🚀 接下来您可以:
• 等待客户通过机器人联系您
• 在频道中查看您的商户信息
• 随时联系管理员更新资料

感谢使用我们的服务！
    """,
    
    # 错误和验证消息
    "invalid_price_format": """
❌ 价格格式错误

请输入有效的数字金额，例如：
• 100 （整数）
• 99.5 （小数）
• 不要包含货币符号或其他字符

请重新输入：
    """,
    
    "adv_sentence_too_long": """
❌ 一句话优势过长

当前长度：{current_length} 字符
限制长度：30 字

请重新输入更精炼的优势描述：
    """,
    
    "bot_detection_warning": """
⚠️ 账号检测警告

我们的系统检测到您的账号可能是机器人账号：

🤖 检测结果: {bot_probability:.1%} 机器人概率
📝 检测原因: 
{detection_reasons}

如果您是真实用户，请联系管理员进行人工审核。
继续注册请点击"继续注册"，取消请点击"取消注册"。
    """,
    
    "user_analysis_summary": """
📊 用户分析报告

🔍 检测结果: {result_type}
📈 置信度: {confidence:.1%}
🎯 综合评分: {final_score:.2f}/1.0

📋 分析详情:
{analysis_details}

💡 建议: {recommendation}
    """,
    
    # 订单通知消息
    "order_notification_merchant": """
🔔 新订单通知

👤 客户: {username} {user_handle}
📅 时间: {order_time}
🛍️ 服务: {service_type}
💰 价格: {price}

请联系客户安排服务。
    """,
    
    # 频道点击通知消息
    "channel_click_notification": """
📺 频道关注通知

{user_display} 用户点击了您的频道链接
    """,
    
    # 频道信息显示消息
    "channel_info_display": """
📺 {channel_name}

🔗 [点击关注频道]({channel_link})

关注我们的官方频道，获取最新资讯和优惠信息！
    """,
    
    "order_confirmation_user": """
✅ 订单已确认

您的{service_type}请求已发送给商户。

📞 商户联系方式: {merchant_contact}

商户将很快联系您安排详细信息。
    """,
    
    # 错误消息
    "error_general": """
❌ 出现了一些问题。请稍后重试或联系客服。
    """,
    
    "error_not_authorized": """
🚫 您没有权限使用此命令。
    """,
    
    "error_merchant_not_found": """
❌ 未找到商户。请检查链接并重试。
    """,
    
    "error_binding_flow": """
❌ 绑定流程错误

在处理您的注册时出现了问题：{error_details}

请重新开始注册流程，或联系管理员获取帮助。
    """,
    
    "error_database": """
❌ 数据库错误

系统暂时无法处理您的请求。请稍后重试。

如果问题持续存在，请联系管理员。
    """,
    
    # 统计模板
    "stats_template": """
📊 机器人统计

📅 时间段: {period}
👥 总用户数: {total_users}
🔘 按钮点击数: {button_clicks}
📝 创建订单数: {orders_created}
🏪 活跃商户数: {active_merchants}

热门按钮:
{top_buttons}
    """,
    
    # 管理员通知消息
    "admin_new_merchant_notification": """
🏪 新商户注册通知

📅 注册时间: {registration_time}
👤 商户信息:
• 用户名: @{username}
• 姓名: {full_name}
• 商户类型: {merchant_type}
• 地区: {province} - {region}
• 价格: P¥{p_price} / PP¥{pp_price}

🤖 用户检测结果:
• 账号类型: {user_type}
• 机器人概率: {bot_probability:.1%}
• 置信度: {confidence:.1%}

💡 检测详情: {detection_summary}
    """,
}

# 按钮模板配置 - 定义各种场景下使用的按钮布局
BUTTON_TEMPLATES = {
    # 商户服务选择按钮
    "merchant_services": [
        {"text": "📅 预约老师课程", "callback_data": "service_appointment"},  # 预约服务按钮
        {"text": "👥 关注老师频道", "callback_data": "service_follow"},  # 关注按钮
        {"text": "📋 返回榜单", "callback_data": "back_to_list"}  # 返回列表按钮
    ],
    
    # 管理员统计筛选按钮
    "admin_stats_filter": [
        {"text": "📅 今天", "callback_data": "stats_today"},  # 今日统计
        {"text": "📅 本周", "callback_data": "stats_week"},  # 本周统计
        {"text": "📅 本月", "callback_data": "stats_month"},  # 本月统计
        {"text": "🔙 返回", "callback_data": "admin_menu"}  # 返回管理菜单
    ],
    
    # 新7步流程按钮模板 - 这些按钮将从数据库动态生成
    # 商家类型选择按钮（动态生成）
    "merchant_types": [
        {"text": "👨‍🏫 个人导师", "callback_data": "type_personal_tutor"},
        {"text": "🏢 教育机构", "callback_data": "type_education_center"},
        {"text": "💄 美容服务", "callback_data": "type_beauty_service"},
        {"text": "🍽️ 餐饮服务", "callback_data": "type_food_service"},
        {"text": "🛠️ 维修服务", "callback_data": "type_repair_service"},
        {"text": "📦 其他服务", "callback_data": "type_other_service"}
    ],
    
    # 省份选择按钮（从数据库动态生成）
    "provinces_dynamic": "provinces_from_database",  # 标记为动态内容
    
    # 区域选择按钮（从数据库动态生成）
    "regions_dynamic": "regions_from_database",  # 标记为动态内容
    
    # 关键词选择按钮（从数据库动态生成）
    "keywords_dynamic": "keywords_from_database",  # 标记为动态内容
    
    # 绑定流程控制按钮
    "binding_flow_control": [
        {"text": "⏭️ 下一步", "callback_data": "binding_next"},
        {"text": "⏮️ 上一步", "callback_data": "binding_prev"},
        {"text": "✅ 确认注册", "callback_data": "binding_confirm"},
        {"text": "🔄 重新填写", "callback_data": "binding_restart"},
        {"text": "❌ 取消注册", "callback_data": "binding_cancel"}
    ],
    
    # 机器人检测处理按钮
    "bot_detection_actions": [
        {"text": "✅ 继续注册", "callback_data": "bot_detection_continue"},
        {"text": "❌ 取消注册", "callback_data": "bot_detection_cancel"},
        {"text": "🤖 申请人工审核", "callback_data": "bot_detection_manual_review"}
    ],
    
    # 关键词选择控制按钮
    "keyword_selection_control": [
        {"text": "✅ 完成选择", "callback_data": "keyword_selection_done"},
        {"text": "🔄 重新选择", "callback_data": "keyword_selection_reset"},
        {"text": "⏭️ 跳过此步", "callback_data": "keyword_selection_skip"}
    ],
    
    # 价格输入辅助按钮
    "price_input_helpers": [
        {"text": "💰 常见价格: ¥100", "callback_data": "price_100"},
        {"text": "💎 常见价格: ¥200", "callback_data": "price_200"},
        {"text": "💰 常见价格: ¥300", "callback_data": "price_300"},
        {"text": "📝 自定义输入", "callback_data": "price_custom"}
    ],
    
    # 注册确认页面按钮
    "registration_confirmation": [
        {"text": "✅ 确认注册", "callback_data": "registration_confirm"},
        {"text": "✏️ 修改商家类型", "callback_data": "edit_merchant_type"},
        {"text": "🌍 修改地区", "callback_data": "edit_location"},
        {"text": "💰 修改价格", "callback_data": "edit_prices"},
        {"text": "📝 修改描述", "callback_data": "edit_description"},
        {"text": "🏷️ 修改关键词", "callback_data": "edit_keywords"},
        {"text": "❌ 取消注册", "callback_data": "registration_cancel"}
    ],
    
    # 管理员地区管理按钮
    "admin_region_management": [
        {"text": "🏙️ 省份管理", "callback_data": "admin_region_provinces"},
        {"text": "🏛️ 区域管理", "callback_data": "admin_region_regions"},
        {"text": "📊 统计信息", "callback_data": "admin_region_stats"},
        {"text": "↩️ 返回", "callback_data": "admin_main"}
    ],
    
    # 管理员关键词管理按钮
    "admin_keyword_management": [
        {"text": "📝 查看关键词", "callback_data": "admin_keyword_list"},
        {"text": "➕ 添加关键词", "callback_data": "admin_keyword_add"},
        {"text": "🏷️ 分类管理", "callback_data": "admin_keyword_categories"},
        {"text": "📊 使用统计", "callback_data": "admin_keyword_stats"},
        {"text": "↩️ 返回", "callback_data": "admin_main"}
    ],
    
    # 通用导航按钮
    "navigation": [
        {"text": "🔙 返回", "callback_data": "back"},  # 返回按钮
        {"text": "✅ 确认", "callback_data": "confirm"},  # 确认按钮
        {"text": "❌ 取消", "callback_data": "cancel"}  # 取消按钮
    ]
}

# 有限状态机(FSM)配置
FSM_STORAGE_KEY = "fsm_storage"  # FSM存储键名
FSM_TIMEOUT = 3600  # FSM状态超时时间（1小时）

# 速率限制配置 - 防止用户过度请求
RATE_LIMIT = {
    "default": 10,  # 普通用户每秒10个请求（更宽松）
    "admin": 50,    # 管理员每秒50个请求
    "burst": 20     # 允许突发20个请求（支持快速点击）
}

# 商户注册模式配置
QUICK_REGISTRATION_MODE = os.getenv("QUICK_REGISTRATION_MODE", "true").lower() == "true"  # True=快速注册(管理员填写), False=7步用户填写

# 网页管理面板配置
WEB_CONFIG = {
    "host": "0.0.0.0",  # 监听所有网络接口
    "port": int(os.getenv("PORT", "8000")),  # 服务端口，默认8000
    "debug": os.getenv("DEBUG", "false").lower() == "true",  # 调试模式开关
    "admin_password": WEB_ADMIN_PASSWORD  # 管理员密码
}

# 自动回复功能配置
AUTO_REPLY_CONFIG = {
    "enabled": os.getenv("AUTO_REPLY_ENABLED", "true").lower() == "true",  # 功能开关
    "max_triggers_per_admin": int(os.getenv("AUTO_REPLY_MAX_TRIGGERS", "100")),  # 每个管理员最大触发词数
    "max_messages_per_trigger": int(os.getenv("AUTO_REPLY_MAX_MESSAGES", "20")),  # 每个触发词最大消息数
    "cache_expiry_hours": int(os.getenv("AUTO_REPLY_CACHE_HOURS", "24")),  # 缓存过期时间（小时）
    "stats_update_interval": int(os.getenv("AUTO_REPLY_STATS_INTERVAL", "3600")),  # 统计更新间隔（秒）
    "enable_admin_bypass": True,  # 管理员消息是否也触发自动回复
    "enable_variable_validation": True,  # 是否启用变量验证
    "max_message_length": 4000,  # 单条回复消息最大长度
}

# 订阅验证功能配置
SUBSCRIPTION_VERIFICATION_CONFIG = {
    "enabled": os.getenv("SUBSCRIPTION_VERIFICATION_ENABLED", "false").lower() == "true",  # 总开关
    "required_subscriptions": [
        # 示例配置，可通过Web界面管理
        # {
        #     "display_name": "主频道",                    # 用户界面显示名称
        #     "join_link": "https://t.me/your_channel",   # 用户点击按钮跳转链接
        #     "chat_id": "@your_channel"                  # API检查用的频道标识符
        # }
    ]
}

# 数据库配置 - 使用PathManager管理路径
from pathmanager import PathManager

database_config = DatabaseConfig(
    db_path=PathManager.get_database_path()  # 使用PathManager获取数据库路径
)

# 日志配置 - 设置日志记录格式和输出方式
LOGGING_CONFIG = {
    "version": 1,  # 配置版本
    "disable_existing_loggers": False,  # 不禁用现有日志记录器
    "formatters": {
        "default": {
            # 默认日志格式：时间、级别、模块、消息
            "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        }
    },
    "handlers": {
        "default": {
            "level": "INFO",  # 控制台输出INFO级别
            "formatter": "default",  # 使用默认格式
            "class": "logging.StreamHandler",  # 流处理器
            "stream": "ext://sys.stdout",  # 输出到标准输出
        },
        "file": {
            "level": "DEBUG",  # 文件记录DEBUG级别
            "formatter": "default",  # 使用默认格式
            "class": "logging.FileHandler",  # 文件处理器
            "filename": PathManager.get_log_file_path("bot"),  # 日志文件路径
        }
    },
    "root": {
        "level": "INFO",  # 根日志级别
        "handlers": ["default", "file"]  # 使用控制台和文件处理器
    }
}

# 配置验证函数
def validate_config() -> bool:
    """验证所有必需的配置是否存在"""
    # 检查机器人令牌是否配置
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ BOT_TOKEN未配置。请设置BOT_TOKEN环境变量。")
        return False
    
    # 检查管理员ID是否配置
    if not ADMIN_IDS or ADMIN_IDS == [123456789]:
        print("⚠️  ADMIN_IDS未配置。请设置ADMIN_IDS环境变量。")
        print("   使用默认管理员ID: 123456789")
    
    return True

# 导入时初始化目录结构
# 使用PathManager确保所有必要目录存在
PathManager.create_directory_structure()
