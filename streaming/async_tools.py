# -- coding: utf-8 --
"""
异步工具管理器模块
负责管理异步工具的执行状态和结果
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Any, Optional
from py.get_setting import TOOL_TEMP_DIR


class AsyncToolManager:
    """异步工具管理器"""
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger(__name__)
        
    async def execute_tool(self, tool_id: str, tool_name: str, args: Dict[str, Any], settings: Dict[str, Any], user_prompt: str):
        """
        执行异步工具
        
        Args:
            tool_id: 工具ID
            tool_name: 工具名称
            args: 工具参数
            settings: 系统设置
            user_prompt: 用户提示
        """
        try:
            from tools.dispatcher import tool_dispatcher
            from py.know_base import rerank_knowledge_base
            
            # 执行工具
            results = await tool_dispatcher.dispatch_tool(tool_name, args, settings)
            
            # 处理异步迭代器
            if hasattr(results, '__aiter__'):
                buffer = []
                async for chunk in results:
                    buffer.append(chunk)
                results = "".join(buffer)
            
            # 特殊处理知识库查询
            if tool_name == "query_knowledge_base" and isinstance(results, list):
                if settings.get("KBSettings", {}).get("is_rerank"):
                    results = await rerank_knowledge_base(user_prompt, results)
                results = json.dumps(results, ensure_ascii=False, indent=4)
            
            # 保存结果
            async with self._lock:
                self._tools[tool_id] = {
                    "status": "completed",
                    "result": results,
                    "name": tool_name,
                    "parameters": args,
                }
                
            self._logger.info(f"异步工具 {tool_name} (ID: {tool_id}) 执行完成")
            
        except Exception as e:
            self._logger.error(f"异步工具 {tool_name} (ID: {tool_id}) 执行失败: {e}")
            
            async with self._lock:
                self._tools[tool_id] = {
                    "status": "error",
                    "result": str(e),
                    "name": tool_name,
                    "parameters": args,
                }
    
    async def get_completed_tools(self, tool_ids: List[str]) -> List[Dict[str, Any]]:
        """
        获取已完成的工具结果
        
        Args:
            tool_ids: 工具ID列表
            
        Returns:
            已完成的工具结果列表
        """
        completed_tools = []
        
        async with self._lock:
            # 收集已完成的工具
            for tool_id in list(self._tools.keys()):
                if tool_id in tool_ids and self._tools[tool_id]["status"] in ("completed", "error"):
                    tool_data = self._tools.pop(tool_id)  # 移除已处理的工具
                    completed_tools.append({
                        "tool_id": tool_id,
                        **tool_data
                    })
        
        return completed_tools
    
    async def get_pending_tools(self, tool_ids: List[str]) -> List[Dict[str, Any]]:
        """
        获取待处理的工具
        
        Args:
            tool_ids: 工具ID列表
            
        Returns:
            待处理的工具列表
        """
        pending_tools = []
        
        async with self._lock:
            for tool_id in tool_ids:
                if tool_id in self._tools and self._tools[tool_id]["status"] == "pending":
                    pending_tools.append({
                        "tool_id": tool_id,
                        "name": self._tools[tool_id]["name"],
                        "parameters": self._tools[tool_id]["parameters"]
                    })
        
        return pending_tools
    
    async def save_tool_result(self, tool_data: Dict[str, Any], fastapi_base_url: str) -> str:
        """
        保存工具结果到文件
        
        Args:
            tool_data: 工具数据
            fastapi_base_url: FastAPI基础URL
            
        Returns:
            文件链接
        """
        try:
            # 生成文件名
            timestamp = time.time()
            uid = str(uuid.uuid4())
            filename = f"{timestamp}_{uid}.txt"
            
            # 保存到文件
            file_path = TOOL_TEMP_DIR / filename
            with open(file_path, "w", encoding='utf-8') as f:
                f.write(str(tool_data["result"]))
            
            # 返回文件链接
            file_link = f"{fastapi_base_url}tool_temp/{filename}"
            
            self._logger.info(f"工具结果已保存到文件: {file_link}")
            return file_link
            
        except Exception as e:
            self._logger.error(f"保存工具结果失败: {e}")
            raise
    
    async def add_tool_to_messages(self, messages: List[Dict[str, Any]], tool_data: Dict[str, Any], file_link: str, is_error: bool = False) -> List[Dict[str, Any]]:
        """
        将工具调用添加到消息中
        
        Args:
            messages: 原始消息列表
            tool_data: 工具数据
            file_link: 文件链接
            is_error: 是否为错误结果
            
        Returns:
            处理后的消息列表
        """
        from config.settings import config_manager
        
        # 添加工具调用消息
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
        if is_error:
            tool_result_message = {
                "role": "system",
                "content": f"之前调用的异步工具（{tool_data['tool_id']}）发生错误：\n\n{tool_data['result']}\n\n====错误结束====\n\n"
            }
        else:
            tool_result_message = {
                "role": "tool",
                "tool_call_id": "agentParty",
                "name": tool_data["name"],
                "content": f"之前调用的异步工具（{tool_data['tool_id']}）的结果：\n\n{tool_data['result']}\n\n====结果结束====\n\n你必须根据工具结果回复未回复的问题或需求。请不要重复调用该工具！"
            }
        
        # 在倒数第一个元素之前插入
        if messages:
            messages.insert(-1, tool_call_message)
            messages.insert(-1, tool_result_message)
        else:
            messages.extend([tool_call_message, tool_result_message])
        
        return messages
    
    def create_tool_chunk(self, tool_data: Dict[str, Any], file_link: str, is_error: bool = False) -> Dict[str, Any]:
        """
        创建工具结果的流式响应块
        
        Args:
            tool_data: 工具数据
            file_link: 文件链接
            is_error: 是否为错误结果
            
        Returns:
            流式响应块
        """
        from config.settings import config_manager
        
        # 获取翻译文本
        result_text = "tool_result"  # 这里需要实际的翻译逻辑
        
        return {
            "choices": [{
                "delta": {
                    "tool_content": f"""<div class="highlight-block"><div style="margin-bottom: 10px;">{tool_data['tool_id']}{result_text}</div><div>{str(tool_data['result'])}</div></div>""",
                    "async_tool_id": tool_data['tool_id'],
                    "tool_link": file_link,
                }
            }]
        }
    
    def get_tool_status(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """获取工具状态"""
        return self._tools.get(tool_id)
    
    def update_tool_status(self, tool_id: str, status: str, result: Any = None):
        """更新工具状态"""
        if tool_id in self._tools:
            self._tools[tool_id]["status"] = status
            if result is not None:
                self._tools[tool_id]["result"] = result
    
    def clear_all_tools(self):
        """清除所有工具状态"""
        self._tools.clear()
        self._logger.info("已清除所有异步工具状态")


# 全局异步工具管理器实例
async_tool_manager = AsyncToolManager()