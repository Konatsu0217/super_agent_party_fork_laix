# -- coding: utf-8 --
"""
消息处理模块初始化文件
统一导入所有消息处理模块
"""

# 消息格式化器
from .formatter import MessageFormatter, message_formatter

# 系统消息注入器
from .injector import SystemMessageInjector, system_message_injector

# 记忆消息注入器
from .memory import MemoryMessageInjector, memory_message_injector

# 消息模块列表
__all__ = [
    # 消息格式化
    'MessageFormatter',
    'message_formatter',
    
    # 系统消息注入
    'SystemMessageInjector',
    'system_message_injector',
    
    # 记忆消息注入
    'MemoryMessageInjector',
    'memory_message_injector'
]