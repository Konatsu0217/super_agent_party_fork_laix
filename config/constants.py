# -- coding: utf-8 --
"""
系统常量配置文件
包含所有允许的文件扩展名、配置常量等
"""

# 允许的文件扩展名
ALLOWED_EXTENSIONS = [
    # 办公文档
    'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'pdf', 'pages', 
    'numbers', 'key', 'rtf', 'odt', 'epub',
    
    # 编程开发
    'js', 'ts', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 'go', 'rs',
    'swift', 'kt', 'dart', 'rb', 'php', 'html', 'css', 'scss', 'less',
    'vue', 'svelte', 'jsx', 'tsx', 'json', 'xml', 'yml', 'yaml', 
    'sql', 'sh',
    
    # 数据配置
    'csv', 'tsv', 'txt', 'md', 'log', 'conf', 'ini', 'env', 'toml'
]

# 允许的图片扩展名
ALLOWED_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']

# 允许的视频扩展名
ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', '3gp', 'm4v']

# 默认配置
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3456

# TTS状态常量
TTS_PLAYING = "播放中"
TTS_STOPPED = "已停止"
CONSUME_PAUSED = "暂停"
CONSUME_ALLOWED = "允许"

# 日志格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 系统消息模板
SYSTEM_MESSAGE_TEMPLATES = {
    "ha_devices": "以下是home assistant连接的设备信息：{}",
    "chrome_status": "以下是浏览器的当前信息：{}",
    "auto_behavior": "当你看到被插入到对话之间的系统消息，这是自主行为系统向你发送的消息...",
    "tts_voices": "你可以使用以下音色：\n{}\n，当你生成回答时...",
    "desktop_vision": "用户与你对话时，会自动发给你当前的桌面截图。\n\n",
    "time_info": "消息发送时间：{}  {}\n\n",
    "inference": "回答用户前请先思考推理，再回答问题...",
    "latex": "当你想使用latex公式时，你必须是用...",
    "language": "请使用{}语言推理分析思考...",
    "stickers": "图片库名称：{}，包含的图片：{}\n\n",
    "text2img": "当你使用画图工具后，必须将图片的URL放在markdown的图片标签中...",
    "expressions": "你可以使用以下表情：<happy> <angry> <sad> <neutral> <surprised> <relaxed>..."
}

# 深度研究阶段
DRS_STAGE_1 = 1  # 明确用户需求阶段
DRS_STAGE_2 = 2  # 查询搜索阶段  
DRS_STAGE_3 = 3  # 生成结果阶段

DRS_STAGE_NAMES = {
    DRS_STAGE_1: "明确用户需求阶段",
    DRS_STAGE_2: "查询搜索阶段", 
    DRS_STAGE_3: "生成结果阶段"
}

DRS_STAGE_MESSAGES = {
    DRS_STAGE_1: "当前阶段为明确用户需求阶段，你需要分析用户的需求...",
    DRS_STAGE_2: "当前阶段为查询搜索阶段，利用你的知识库、互联网搜索...",
    DRS_STAGE_3: "当前阶段为生成结果阶段，根据当前收集到的所有信息..."
}

# 工具名称映射
TOOL_NAME_MAPPING = {
    "multi_tool_use.": "",
    "custom_http_": "",
    "comfyui_": ""
}

# 超时配置
MCP_INIT_TIMEOUT = 6.0
MCP_MAX_WAIT_FAILURE = 5.0

# 缓存配置
MEMORY_CACHE_EXPIRE = 3600  # 1小时
TOOL_TEMP_EXPIRE = 7200     # 2小时

# 文件路径模板
FILE_PATH_TEMPLATES = {
    "backend_log": "backend_{timestamp}.log",
    "image_cache": "{image_hash}.txt",
    "tool_temp": "{timestamp}_{uid}.txt"
}