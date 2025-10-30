# -- coding: utf-8 --
"""
重构后的主服务器文件
基于模块化架构，保持原有功能不变
"""
import os
import sys
import argparse
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

# FastAPI相关导入
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from pydantic import BaseModel

# 配置模块
from config.constants import DEFAULT_HOST, DEFAULT_PORT
from config.settings import config_manager

# 工具模块
from tools import tts_tracker, tool_dispatcher, mcp_manager

# 消息处理模块
from message import message_formatter, system_message_injector, memory_message_injector

# 流式响应模块
from streaming import async_tool_manager, deep_research_system

# API路由模块
from routes import (
    ChatRequest, ChatResponse,
    ProviderModelRequest, ProviderModelsResponse,
    TTSRequest, TTSResponse, TTSStatusResponse,
    FileUploadResponse, FileListResponse,
    chat_router, model_router, tts_router, file_router, websocket_manager
)

# 业务逻辑模块
from services import chat_service, tool_service

# 原始模块导入（保持兼容性）
from py.get_setting import load_settings, save_settings, configure_host_port
from py.llm_tool import get_image_base64, get_image_media_type


# 命令行参数解析
def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="运行ASGI应用服务器")
    parser.add_argument("--host", default=DEFAULT_HOST, help="ASGI服务器主机，默认127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="ASGI服务器端口，默认3456")
    return parser.parse_args()


# 应用生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger = logging.getLogger("app")
    logger.info("🚀 应用启动中...")
    
    try:
        # 初始化数据库
        from py.get_setting import init_db
        await init_db()
        
        # 初始化配置管理器
        await config_manager.initialize()
        
        # 设置工具分发器
        tool_dispatcher.set_mcp_clients(mcp_manager.get_all_clients())
        tool_dispatcher.set_ha_client(config_manager.get_client("ha"))
        tool_dispatcher.set_chrome_mcp_client(config_manager.get_client("chrome"))
        
        # 加载工具钩子
        settings = await load_settings()
        await tool_dispatcher.load_tool_hooks(settings)
        
        # 初始化MCP客户端
        if settings and 'mcpServers' in settings:
            mcp_manager.set_settings(settings)
            await mcp_manager.initialize_clients(settings['mcpServers'])
        
        logger.info("✅ 应用启动完成")
        
        yield
        
        # 关闭时清理
        logger.info("🛑 应用关闭中...")
        
        # 关闭MCP客户端
        await mcp_manager.close_all_clients()
        
        logger.info("✅ 应用关闭完成")
        
    except Exception as e:
        logger.error(f"应用生命周期管理失败: {e}")
        raise


# 创建FastAPI应用
app = FastAPI(
    title="Super Agent Party API",
    description="重构后的Super Agent Party API服务器",
    version="2.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORS预检请求处理
@app.middleware("http")
async def cors_options_workaround(request: Request, call_next):
    """处理CORS预检请求"""
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400",
            }
        )
    return await call_next(request)


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "modules": {
            "config": config_manager is not None,
            "tools": tool_dispatcher is not None,
            "mcp": mcp_manager is not None,
            "chat": chat_service is not None
        }
    }


# 聊天API端点
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest, fastapi_request: Request):
    """OpenAI兼容的聊天完成API"""
    try:
        return await chat_router.process_chat_request(request, fastapi_request)
    except Exception as e:
        logging.error(f"聊天API错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 模型管理API端点
@app.get("/v1/models")
async def list_models():
    """获取可用模型列表"""
    return await model_router.get_models()


@app.post("/v1/models/fetch")
async def fetch_provider_models(request: ProviderModelRequest):
    """获取指定提供商的模型列表"""
    return await model_router.fetch_provider_models(request)


# TTS API端点
@app.get("/v1/tts/status")
async def get_tts_status():
    """获取TTS状态"""
    return await tts_router.get_tts_status()


@app.post("/v1/tts/synthesize")
async def tts_synthesize(request: TTSRequest):
    """文本转语音"""
    return await tts_router.text_to_speech(request)


@app.post("/v1/tts/stop")
async def tts_stop():
    """停止TTS播放"""
    return await tts_router.stop_tts()


@app.get("/v1/tts/voices")
async def get_tts_voices():
    """获取可用音色列表"""
    return await tts_router.get_available_voices()


# 文件上传API端点
@app.post("/v1/files/upload")
async def upload_file(file: UploadFile):
    """上传文件"""
    return await file_router.upload_file(file)


@app.post("/v1/files/upload/image")
async def upload_image(file: UploadFile):
    """上传图片"""
    return await file_router.upload_image(file)


@app.post("/v1/files/upload/document")
async def upload_document(file: UploadFile):
    """上传文档"""
    return await file_router.upload_document(file)


@app.get("/v1/files")
async def list_files(file_type: str = "all", limit: int = 100):
    """获取文件列表"""
    return file_router.get_uploaded_files(file_type, limit)


@app.delete("/v1/files/{filename}")
async def delete_file(filename: str):
    """删除文件"""
    return file_router.delete_file(filename)


# WebSocket端点
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
    """WebSocket连接端点"""
    await websocket_manager.connect(websocket, client_id)
    
    try:
        while True:
            # 接收消息
            message = await websocket.receive_text()
            
            # 处理消息
            await websocket_manager.handle_websocket_message(websocket, message)
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"WebSocket错误: {e}")
        websocket_manager.disconnect(websocket)


# 设置主机和端口
args = parse_args()
configure_host_port(args.host, args.port)


# 主函数
def main():
    """主函数"""
    import uvicorn
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger("app")
    logger.info(f"🌟 启动Super Agent Party API服务器")
    logger.info(f"📡 监听地址: http://{args.host}:{args.port}")
    
    # 启动服务器
    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()