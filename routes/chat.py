# -- coding: utf-8 --
"""
聊天API路由模块
负责处理聊天相关的API请求
"""
import json
import logging
from typing import Dict, Any, List, Union, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from config.settings import config_manager
from message.formatter import message_formatter
from message.injector import system_message_injector
from message.memory import memory_message_injector
from streaming.async_tools import async_tool_manager
from streaming.research import deep_research_system


class ChatRequest(BaseModel):
    """聊天请求模型"""
    messages: List[Dict[str, Any]]
    model: str = Field(default=None)
    temperature: float = 0.7
    tools: Dict[str, Any] = Field(default=None)
    stream: bool = False
    max_tokens: int = Field(default=None)
    top_p: float = 1.0
    fileLinks: List[str] = Field(default=None)
    enable_thinking: bool = False
    enable_deep_research: bool = False
    enable_web_search: bool = False
    asyncToolsID: List[str] = Field(default=None)
    reasoning_effort: str = Field(default=None)


class ChatResponse(BaseModel):
    """聊天响应模型"""
    choices: List[Dict[str, Any]]
    model: str
    usage: Dict[str, Any] = Field(default=None)


class ChatRouter:
    """聊天路由器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    async def process_chat_request(self, request: ChatRequest, fastapi_request: Request) -> Dict[str, Any]:
        """
        处理聊天请求
        
        Args:
            request: 聊天请求
            fastapi_request: FastAPI请求对象
            
        Returns:
            聊天响应
        """
        try:
            # 获取基础URL
            base_url = f"http://127.0.0.1:{fastapi_request.url.port}/"
            
            # 加载设置
            settings = await config_manager.get_settings()
            if not settings:
                raise HTTPException(status_code=500, detail="系统设置未初始化")
            
            # 处理异步工具结果
            if request.asyncToolsID:
                await self._process_async_tools(request, base_url)
            
            # 预处理消息
            processed_messages = await self._preprocess_messages(request, settings, base_url)
            
            # 获取客户端
            client = config_manager.get_client("main")
            reasoner_client = config_manager.get_client("reasoner")
            
            if not client:
                raise HTTPException(status_code=500, detail="主客户端未初始化")
            
            # 生成响应
            if request.stream:
                return self._generate_stream_response(
                    client, reasoner_client, request, settings, base_url
                )
            else:
                return await self._generate_complete_response(
                    client, reasoner_client, request, settings, base_url
                )
                
        except Exception as e:
            self._logger.error(f"处理聊天请求失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_async_tools(self, request: ChatRequest, base_url: str):
        """处理异步工具结果"""
        if not request.asyncToolsID:
            return
        
        # 获取已完成的工具
        completed_tools = await async_tool_manager.get_completed_tools(request.asyncToolsID)
        
        for tool_data in completed_tools:
            # 保存结果到文件
            file_link = await async_tool_manager.save_tool_result(tool_data, base_url)
            
            # 添加到消息中
            is_error = tool_data["status"] == "error"
            request.messages = await async_tool_manager.add_tool_to_messages(
                request.messages, tool_data, file_link, is_error
            )
        
        # 处理待处理的工具
        pending_tools = await async_tool_manager.get_pending_tools(request.asyncToolsID)
        
        for tool_data in pending_tools:
            # 添加工具调用到消息中
            tool_call_message = {
                "tool_calls": [
                    {
                        "id": "agentParty",
                        "function": {
                            "arguments": json.dumps(tool_data["parameters"]),
                            "name": tool_data["name"],
                        },
                        "type": "function",
                    }
                ],
                "role": "assistant",
                "content": "",
            }
            
            # 添加工具结果消息
            tool_result_message = {
                "role": "tool",
                "tool_call_id": "agentParty",
                "name": tool_data["name"],
                "content": f"{tool_data['name']}工具已成功启动，获取结果需要花费很久的时间。请不要再次调用该工具，因为工具结果将生成后自动发送，再次调用也不能更快的获取到结果。请直接告诉用户，你会在获得结果后回答他的问题。"
            }
            
            # 在倒数第一个元素之前插入
            if request.messages:
                request.messages.insert(-1, tool_call_message)
                request.messages.insert(-1, tool_result_message)
    
    async def _preprocess_messages(self, request: ChatRequest, settings: Dict[str, Any], base_url: str) -> List[Dict[str, Any]]:
        """预处理消息"""
        messages = request.messages.copy()
        
        # 提取图像信息
        images = await message_formatter.extract_images_from_messages(messages, base_url, 3456)
        
        # 移除消息中的图像，转换为文本格式
        messages = message_formatter.remove_images_from_messages(messages)
        
        # 注入图像描述
        messages = message_formatter.inject_image_descriptions(messages, images, settings)
        
        # 注入系统消息
        messages = await self._inject_system_messages(messages, request, settings)
        
        return messages
    
    async def _inject_system_messages(self, messages: List[Dict[str, Any]], request: ChatRequest, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """注入系统消息"""
        # 获取客户端
        ha_client = config_manager.get_client("ha")
        chrome_client = config_manager.get_client("chrome")
        
        # 注入Home Assistant设备信息
        messages = await system_message_injector.inject_ha_devices(messages, settings, ha_client)
        
        # 注入Chrome状态信息
        messages = await system_message_injector.inject_chrome_status(messages, settings, chrome_client)
        
        # 注入自主行为信息
        messages = system_message_injector.inject_auto_behavior_info(messages, settings)
        
        # 注入TTS音色信息
        messages = system_message_injector.inject_tts_voice_info(messages, settings)
        
        # 注入桌面视觉信息
        messages = system_message_injector.inject_desktop_vision_info(messages, settings)
        
        # 注入时间信息
        local_timezone = config_manager.local_timezone
        messages = system_message_injector.inject_time_info(messages, settings, local_timezone)
        
        # 注入推理信息
        messages = system_message_injector.inject_inference_info(messages, settings)
        
        # 注入LaTeX信息
        messages = system_message_injector.inject_latex_info(messages, settings)
        
        # 注入语言信息
        messages = system_message_injector.inject_language_info(messages, settings)
        
        # 注入贴纸包信息
        messages = system_message_injector.inject_sticker_info(messages, settings)
        
        # 注入文本到图像信息
        messages = system_message_injector.inject_text2img_info(messages, settings)
        
        # 注入表情信息
        messages = system_message_injector.inject_expression_info(messages, settings)
        
        # 注入记忆相关信息
        messages = await self._inject_memory_messages(messages, settings)
        
        return messages
    
    async def _inject_memory_messages(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """注入记忆相关消息"""
        # 注入用户名
        messages = memory_message_injector.inject_user_name(messages, settings)
        
        # 获取当前记忆配置
        current_memory = await self._get_current_memory(settings)
        
        if current_memory:
            # 注入角色信息
            messages = memory_message_injector.inject_character_info(messages, settings, current_memory)
            
            # 注入相关记忆
            # TODO: 需要实现记忆管理器
            # messages = await memory_message_injector.inject_relevant_memories(messages, settings, current_memory, memory_manager)
            
            # 注入通用系统提示
            messages = memory_message_injector.inject_generic_system_prompt(messages, settings, current_memory)
        
        return messages
    
    async def _get_current_memory(self, settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取当前记忆配置"""
        memory_settings = settings.get("memorySettings", {})
        
        if not memory_settings.get("is_memory") or not memory_settings.get("selectedMemory"):
            return None
        
        memory_id = memory_settings["selectedMemory"]
        
        # 在记忆列表中查找
        for memory in settings.get("memories", []):
            if memory.get("id") == memory_id:
                return memory
        
        return None
    
    def _generate_stream_response(self, client, reasoner_client, request: ChatRequest, settings: Dict[str, Any], base_url: str):
        """生成流式响应"""
        # TODO: 实现流式响应生成
        # 这里需要导入streaming模块的相应功能
        pass
    
    async def _generate_complete_response(self, client, reasoner_client, request: ChatRequest, settings: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        """生成完整响应"""
        # TODO: 实现完整响应生成
        # 这里需要导入streaming模块的相应功能
        pass


# 全局聊天路由器实例
chat_router = ChatRouter()