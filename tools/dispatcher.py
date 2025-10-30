# -- coding: utf-8 --
"""
工具分发器模块
负责管理和分发各种工具调用
"""
import json
import logging
from typing import Dict, Any, List, Optional, AsyncIterator, Union
from config.constants import TOOL_NAME_MAPPING


class ToolDispatcher:
    """工具分发器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._tool_hooks = {}
        self._mcp_clients = {}
        self._ha_client = None
        self._chrome_mcp_client = None
        
    def set_mcp_clients(self, mcp_clients: Dict[str, Any]):
        """设置MCP客户端"""
        self._mcp_clients = mcp_clients
        
    def set_ha_client(self, ha_client: Any):
        """设置Home Assistant客户端"""
        self._ha_client = ha_client
        
    def set_chrome_mcp_client(self, chrome_client: Any):
        """设置Chrome MCP客户端"""
        self._chrome_mcp_client = chrome_client
        
    async def load_tool_hooks(self, settings: Dict[str, Any]):
        """加载工具钩子"""
        # 动态导入工具模块
        from py.web_search import (
            DDGsearch_async, searxng_async, Tavily_search_async,
            Bing_search_async, Google_search_async, Brave_search_async,
            Exa_search_async, Serper_search_async, bochaai_search_async,
            jina_crawler_async, Crawl4Ai_search_async
        )
        from py.know_base import query_knowledge_base
        from py.agent_tool import agent_tool_call
        from py.a2a_tool import a2a_tool_call
        from py.llm_tool import custom_llm_tool
        from py.pollinations import pollinations_image, openai_image, siliconflow_image
        from py.load_files import get_file_content
        from py.code_interpreter import e2b_code_async, local_run_code_async
        from py.custom_http import fetch_custom_http
        from py.comfyui_tool import comfyui_tool_call
        from py.utility_tools import (
            time_async, get_weather_async, get_location_coordinates_async,
            get_weather_by_city_async, get_wikipedia_summary_and_sections,
            get_wikipedia_section_content, search_arxiv_papers
        )
        from py.autoBehavior import auto_behavior
        from py.cli_tool import claude_code_async, qwen_code_async
        
        self._tool_hooks = {
            "DDGsearch_async": DDGsearch_async,
            "searxng_async": searxng_async,
            "Tavily_search_async": Tavily_search_async,
            "query_knowledge_base": query_knowledge_base,
            "jina_crawler_async": jina_crawler_async,
            "Crawl4Ai_search_async": Crawl4Ai_search_async,
            "agent_tool_call": agent_tool_call,
            "a2a_tool_call": a2a_tool_call,
            "custom_llm_tool": custom_llm_tool,
            "pollinations_image": pollinations_image,
            "get_file_content": get_file_content,
            "get_image_content": None,  # 需要特殊处理
            "e2b_code_async": e2b_code_async,
            "local_run_code_async": local_run_code_async,
            "openai_image": openai_image,
            "siliconflow_image": siliconflow_image,
            "Bing_search_async": Bing_search_async,
            "Google_search_async": Google_search_async,
            "Brave_search_async": Brave_search_async,
            "Exa_search_async": Exa_search_async,
            "Serper_search_async": Serper_search_async,
            "bochaai_search_async": bochaai_search_async,
            "comfyui_tool_call": comfyui_tool_call,
            "time_async": time_async,
            "get_weather_async": get_weather_async,
            "get_location_coordinates_async": get_location_coordinates_async,
            "get_weather_by_city_async": get_weather_by_city_async,
            "get_wikipedia_summary_and_sections": get_wikipedia_summary_and_sections,
            "get_wikipedia_section_content": get_wikipedia_section_content,
            "search_arxiv_papers": search_arxiv_papers,
            "auto_behavior": auto_behavior,
            "claude_code_async": claude_code_async,
            "qwen_code_async": qwen_code_async
        }
        
    async def dispatch_tool(self, tool_name: str, tool_params: Dict[str, Any], settings: Dict[str, Any]) -> Optional[Union[str, List, AsyncIterator[str]]]:
        """
        分发工具调用
        
        Args:
            tool_name: 工具名称
            tool_params: 工具参数
            settings: 系统设置
            
        Returns:
            工具执行结果
        """
        self._logger.info(f"分发工具: {tool_name}, 参数: {tool_params}")
        
        # 处理特殊工具名称
        tool_name = self._normalize_tool_name(tool_name)
        
        # 处理自定义HTTP工具
        if tool_name.startswith("custom_http_"):
            return await self._handle_custom_http(tool_name, tool_params, settings)
            
        # 处理ComfyUI工具
        if tool_name.startswith("comfyui_"):
            return await self._handle_comfyui_tool(tool_name, tool_params, settings)
            
        # Home Assistant工具
        if self._ha_client and settings.get("HASettings", {}).get("enabled"):
            result = await self._handle_ha_tool(tool_name, tool_params)
            if result is not None:
                return result
                
        # Chrome MCP工具
        if self._chrome_mcp_client and settings.get("chromeMCPSettings", {}).get("enabled"):
            result = await self._handle_chrome_tool(tool_name, tool_params)
            if result is not None:
                return result
                
        # MCP客户端工具
        result = await self._handle_mcp_tool(tool_name, tool_params)
        if result is not None:
            return result
            
        # 内置工具
        return await self._handle_builtin_tool(tool_name, tool_params, settings)
        
    def _normalize_tool_name(self, tool_name: str) -> str:
        """标准化工具名称"""
        for prefix, replacement in TOOL_NAME_MAPPING.items():
            if tool_name.startswith(prefix):
                return tool_name.replace(prefix, replacement)
        return tool_name
        
    async def _handle_custom_http(self, tool_name: str, tool_params: Dict[str, Any], settings: Dict[str, Any]) -> str:
        """处理自定义HTTP工具"""
        actual_name = tool_name.replace("custom_http_", "")
        
        settings_custom_http = settings.get('custom_http', [])
        tool_custom_http = None
        
        for custom in settings_custom_http:
            if custom['name'] == actual_name:
                tool_custom_http = custom
                break
                
        if not tool_custom_http:
            self._logger.error(f"未找到自定义HTTP工具: {actual_name}")
            return f"Error: Custom HTTP tool {actual_name} not found"
            
        method = tool_custom_http['method']
        url = tool_custom_http['url']
        headers = tool_custom_http['headers']
        
        from py.custom_http import fetch_custom_http
        result = await fetch_custom_http(method, url, headers, tool_params)
        return str(result)
        
    async def _handle_comfyui_tool(self, tool_name: str, tool_params: Dict[str, Any], settings: Dict[str, Any]) -> str:
        """处理ComfyUI工具"""
        actual_name = tool_name.replace("comfyui_", "")
        
        text_input = tool_params.get('text_input')
        text_input_2 = tool_params.get('text_input_2')
        image_input = tool_params.get('image_input')
        image_input_2 = tool_params.get('image_input_2')
        
        from py.comfyui_tool import comfyui_tool_call
        result = await comfyui_tool_call(actual_name, text_input, image_input, text_input_2, image_input_2)
        return str(result)
        
    async def _handle_ha_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Optional[str]:
        """处理Home Assistant工具"""
        ha_tool_list = self._ha_client._tools
        if tool_name in ha_tool_list:
            result = await self._ha_client.call_tool(tool_name, tool_params)
            return self._format_tool_result(result)
        return None
        
    async def _handle_chrome_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Optional[str]:
        """处理Chrome MCP工具"""
        Chrome_tool_list = self._chrome_mcp_client._tools
        if tool_name in Chrome_tool_list:
            result = await self._chrome_mcp_client.call_tool(tool_name, tool_params)
            return self._format_tool_result(result)
        return None
        
    async def _handle_mcp_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Optional[str]:
        """处理MCP客户端工具"""
        for server_name, mcp_client in self._mcp_clients.items():
            if tool_name in mcp_client._conn.tools:
                result = await mcp_client.call_tool(tool_name, tool_params)
                return self._format_tool_result(result)
        return None
        
    async def _handle_builtin_tool(self, tool_name: str, tool_params: Dict[str, Any], settings: Dict[str, Any]) -> Optional[str]:
        """处理内置工具"""
        if tool_name not in self._tool_hooks:
            self._logger.warning(f"未找到工具: {tool_name}")
            return None
            
        tool_call = self._tool_hooks[tool_name]
        try:
            ret_out = await tool_call(**tool_params)
            
            # 特殊处理auto_behavior
            if tool_name == "auto_behavior":
                settings = ret_out
                from config.settings import config_manager
                await config_manager.broadcast_behavior_update(settings)
                ret_out = "任务设置成功！"
                
            return ret_out
        except Exception as e:
            self._logger.error(f"调用工具 {tool_name} 失败: {e}")
            return f"Error calling tool {tool_name}: {e}"
            
    def _format_tool_result(self, result: Any) -> str:
        """格式化工具结果"""
        if isinstance(result, str):
            return result
        elif hasattr(result, 'model_dump'):
            return str(result.model_dump())
        else:
            return str(result)


# 全局工具分发器实例
tool_dispatcher = ToolDispatcher()