# -- coding: utf-8 --
"""
API路由模块初始化文件
统一导入所有路由模块
"""

# 聊天路由
from .chat import ChatRequest, ChatResponse, chat_router

# 模型管理路由
from .models import (
    ProviderModelRequest, ModelInfo, ProviderModelsResponse,
    model_router
)

# TTS路由
from .tts import (
    TTSRequest, TTSResponse, TTSStatusResponse,
    tts_router
)

# 文件上传路由
from .files import (
    FileUploadResponse, FileListResponse,
    file_router
)

# WebSocket路由
from .websocket import WebSocketManager, websocket_manager

# 路由模块列表
__all__ = [
    # 聊天相关
    'ChatRequest',
    'ChatResponse', 
    'chat_router',
    
    # 模型管理相关
    'ProviderModelRequest',
    'ModelInfo',
    'ProviderModelsResponse',
    'model_router',
    
    # TTS相关
    'TTSRequest',
    'TTSResponse',
    'TTSStatusResponse',
    'tts_router',
    
    # 文件上传相关
    'FileUploadResponse',
    'FileListResponse',
    'file_router',
    
    # WebSocket相关
    'WebSocketManager',
    'websocket_manager'
]