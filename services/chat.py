# -- coding: utf-8 --
"""
聊天服务模块
负责处理聊天相关的业务逻辑
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from pydantic import BaseModel
from config.settings import config_manager
from message.formatter import message_formatter
from message.injector import system_message_injector
from message.memory import memory_message_injector
from streaming.async_tools import async_tool_manager
from streaming.research import deep_research_system
from tools.dispatcher import tool_dispatcher
from tools.mcp import mcp_manager


class ChatService:
    """聊天服务"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    async def process_chat_request(
        self, 
        messages: List[Dict[str, Any]], 
        settings: Dict[str, Any],
        base_url: str,
        enable_streaming: bool = True,
        enable_thinking: bool = False,
        enable_deep_research: bool = False,
        enable_web_search: bool = False,
        async_tools_id: Optional[List[str]] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        处理聊天请求
        
        Args:
            messages: 消息列表
            settings: 系统设置
            base_url: 基础URL
            enable_streaming: 是否启用流式响应
            enable_thinking: 是否启用思考模式
            enable_deep_research: 是否启用深度研究
            enable_web_search: 是否启用网络搜索
            async_tools_id: 异步工具ID列表
            **kwargs: 其他参数
            
        Yields:
            流式响应块
        """
        try:
            # 预处理消息
            processed_messages = await self._preprocess_messages(
                messages, settings, base_url, async_tools_id
            )
            
            # 获取客户端
            client = config_manager.get_client("main")
            reasoner_client = config_manager.get_client("reasoner")
            
            if not client:
                raise ValueError("主客户端未初始化")
            
            # 确定研究阶段
            drs_stage = deep_research_system.get_initial_stage(len(processed_messages))
            
            # 构建工具列表
            tools = await self._build_tools_list(settings, processed_messages)
            
            # 处理深度研究
            if enable_deep_research or settings.get('tools', {}).get('deepsearch', {}).get('enabled'):
                processed_messages = await self._process_deep_research(
                    processed_messages, settings, drs_stage, enable_streaming
                )
            
            # 处理推理
            if enable_thinking or settings.get('reasoner', {}).get('enabled'):
                processed_messages = await self._process_reasoning(
                    processed_messages, settings, tools, enable_streaming
                )
            
            # 生成响应
            if enable_streaming:
                async for chunk in self._generate_stream_response(
                    client, processed_messages, settings, tools, **kwargs
                ):
                    yield chunk
            else:
                response = await self._generate_complete_response(
                    client, processed_messages, settings, tools, **kwargs
                )
                yield response
                
        except Exception as e:
            self._logger.error(f"处理聊天请求失败: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def _preprocess_messages(
        self, 
        messages: List[Dict[str, Any]], 
        settings: Dict[str, Any],
        base_url: str,
        async_tools_id: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """预处理消息"""
        # 处理异步工具结果
        if async_tools_id:
            await self._process_async_tools(messages, settings, base_url, async_tools_id)
        
        # 提取图像信息
        images = await message_formatter.extract_images_from_messages(messages, base_url, 3456)
        
        # 移除消息中的图像，转换为文本格式
        messages = message_formatter.remove_images_from_messages(messages)
        
        # 注入图像描述
        messages = message_formatter.inject_image_descriptions(messages, images, settings)
        
        # 注入系统消息
        messages = await self._inject_system_messages(messages, settings)
        
        return messages
    
    async def _process_async_tools(
        self, 
        messages: List[Dict[str, Any]], 
        settings: Dict[str, Any],
        base_url: str,
        async_tools_id: List[str]
    ):
        """处理异步工具结果"""
        # 获取已完成的工具
        completed_tools = await async_tool_manager.get_completed_tools(async_tools_id)
        
        for tool_data in completed_tools:
            # 保存结果到文件
            file_link = await async_tool_manager.save_tool_result(tool_data, base_url)
            
            # 添加到消息中
            is_error = tool_data["status"] == "error"
            messages = await async_tool_manager.add_tool_to_messages(
                messages, tool_data, file_link, is_error
            )
        
        # 处理待处理的工具
        pending_tools = await async_tool_manager.get_pending_tools(async_tools_id)
        
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
            if messages:
                messages.insert(-1, tool_call_message)
                messages.insert(-1, tool_result_message)
    
    async def _inject_system_messages(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
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
    
    async def _build_tools_list(self, settings: Dict[str, Any], messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建工具列表"""
        tools = []
        
        # 添加MCP工具
        mcp_clients = mcp_manager.get_enabled_clients()
        for server_name, mcp_client in mcp_clients.items():
            if server_name in settings.get('mcpServers', {}):
                server_config = settings['mcpServers'][server_name]
                if not server_config.get('disabled', False) and server_config.get('processingStatus') == 'ready':
                    disable_tools = []
                    for tool in server_config.get("tools", []):
                        if tool.get("enabled", True) == False:
                            disable_tools.append(tool["name"])
                    
                    functions = await mcp_manager.get_openai_functions(server_name, disable_tools)
                    if functions:
                        tools.extend(functions)
        
        # 添加其他工具...
        # TODO: 添加更多工具类型
        
        return tools
    
    async def _process_deep_research(
        self, 
        messages: List[Dict[str, Any]], 
        settings: Dict[str, Any],
        drs_stage: int,
        enable_streaming: bool
    ) -> List[Dict[str, Any]]:
        """处理深度研究"""
        # TODO: 实现深度研究逻辑
        return messages
    
    async def _process_reasoning(
        self, 
        messages: List[Dict[str, Any]], 
        settings: Dict[str, Any],
        tools: List[Dict[str, Any]],
        enable_streaming: bool
    ) -> List[Dict[str, Any]]:
        """处理推理"""
        # TODO: 实现推理逻辑
        return messages
    
    async def _generate_stream_response(
        self, 
        client, 
        messages: List[Dict[str, Any]], 
        settings: Dict[str, Any],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """生成流式响应"""
        # TODO: 实现流式响应生成
        pass
    
    async def _generate_complete_response(
        self, 
        client, 
        messages: List[Dict[str, Any]], 
        settings: Dict[str, Any],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """生成完整响应"""
        # TODO: 实现完整响应生成
        pass


# 全局聊天服务实例
chat_service = ChatService()