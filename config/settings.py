# -- coding: utf-8 --
"""
系统配置管理模块
负责管理应用配置、客户端初始化等
"""
import os
import logging
import time
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from py.dify_openai_async import DifyOpenAIAsync
from py.get_setting import load_settings, save_settings, LOG_DIR
from config.constants import (
    DEFAULT_HOST, DEFAULT_PORT, LOG_FORMAT, LOG_DATE_FORMAT,
    FILE_PATH_TEMPLATES
)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.settings = None
        self.logger = None
        self.client = None
        self.reasoner_client = None
        self.ha_client = None
        self.chrome_mcp_client = None
        self.mcp_clients = {}
        self.locales = {}
        self.local_timezone = None
        
    async def initialize(self):
        """初始化配置管理器"""
        # 初始化日志
        self.logger = await self._init_logger()
        
        # 加载设置
        self.settings = await load_settings()
        
        # 加载本地化
        await self._load_locales()
        
        # 初始化时区
        await self._init_timezone()
        
        # 初始化客户端
        await self._init_clients()
        
        return self
        
    async def _init_logger(self) -> logging.Logger:
        """初始化日志系统"""
        timestamp = time.time()
        log_path = os.path.join(LOG_DIR, FILE_PATH_TEMPLATES["backend_log"].format(timestamp=timestamp))
        
        logger = logging.getLogger("app")
        logger.setLevel(logging.INFO)
        
        # 文件处理器
        file_handler = logging.FileHandler(log_path, mode='a')
        file_handler.setLevel(logging.INFO)
        
        # 设置格式
        formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        file_handler.setFormatter(formatter)
        
        # 清除现有处理器
        if logger.hasHandlers():
            logger.handlers.clear()
        
        logger.addHandler(file_handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        logger.info("===== 日志系统初始化成功 =====")
        logger.info(f"日志文件路径: {log_path}")
        
        return logger
        
    async def _load_locales(self):
        """加载本地化配置"""
        from py.get_setting import base_path
        import json
        
        with open(base_path + "/config/locales.json", "r", encoding="utf-8") as f:
            self.locales = json.load(f)
            
    async def _init_timezone(self):
        """初始化时区"""
        from tzlocal import get_localzone
        self.local_timezone = get_localzone()
        
    async def _init_clients(self):
        """初始化AI客户端"""
        if not self.settings:
            return
            
        # 获取供应商配置
        vendor = self._get_vendor_by_id(self.settings['selectedProvider'])
        reasoner_vendor = self._get_vendor_by_id(self.settings['reasoner']['selectedProvider'])
        
        # 设置客户端类
        client_class = DifyOpenAIAsync if vendor == 'Dify' else AsyncOpenAI
        reasoner_client_class = DifyOpenAIAsync if reasoner_vendor == 'Dify' else AsyncOpenAI
        
        # 创建客户端
        self.client = client_class(
            api_key=self.settings['api_key'], 
            base_url=self.settings['base_url']
        )
        self.reasoner_client = reasoner_client_class(
            api_key=self.settings['reasoner']['api_key'], 
            base_url=self.settings['reasoner']['base_url']
        )
        
        # 设置代理
        await self._setup_proxy()
        
    def _get_vendor_by_id(self, provider_id: str) -> str:
        """根据提供商ID获取供应商名称"""
        for modelProvider in self.settings['modelProviders']:
            if modelProvider['id'] == provider_id:
                return modelProvider['vendor']
        return 'OpenAI'
        
    async def _setup_proxy(self):
        """设置代理环境变量"""
        if self.settings["systemSettings"]["proxy"] and self.settings["systemSettings"]["proxyEnabled"]:
            os.environ['http_proxy'] = self.settings["systemSettings"]["proxy"].strip()
            os.environ['https_proxy'] = self.settings["systemSettings"]["proxy"].strip()
        else:
            os.environ['http_proxy'] = ''
            os.environ['https_proxy'] = ''
            
    def get_client(self, client_type: str = "main") -> Any:
        """获取客户端实例"""
        if client_type == "main":
            return self.client
        elif client_type == "reasoner":
            return self.reasoner_client
        elif client_type == "ha":
            return self.ha_client
        elif client_type == "chrome":
            return self.chrome_mcp_client
        return None
        
    def get_mcp_client(self, server_name: str) -> Any:
        """获取MCP客户端"""
        return self.mcp_clients.get(server_name)
        
    def set_mcp_client(self, server_name: str, client: Any):
        """设置MCP客户端"""
        self.mcp_clients[server_name] = client
        
    async def get_current_language(self) -> str:
        """获取当前语言"""
        if self.settings:
            return self.settings.get("currentLanguage", "en")
        return "en"
        
    async def translate(self, text: str) -> str:
        """翻译文本"""
        target_language = await self.get_current_language()
        return self.locales.get(target_language, {}).get(text, text)


# 全局配置管理器实例
config_manager = ConfigManager()


async def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    return config_manager