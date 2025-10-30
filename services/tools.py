# -- coding: utf-8 --
"""
工具服务模块
负责管理工具的调用和状态
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from tools.dispatcher import tool_dispatcher
from tools.mcp import mcp_manager
from streaming.async_tools import async_tool_manager


class ToolService:
    """工具服务"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    async def execute_tool(self, tool_name: str, tool_params: Dict[str, Any], settings: Dict[str, Any]) -> Any:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            tool_params: 工具参数
            settings: 系统设置
            
        Returns:
            工具执行结果
        """
        try:
            self._logger.info(f"执行工具: {tool_name}, 参数: {tool_params}")
            
            # 通过工具分发器执行工具
            result = await tool_dispatcher.dispatch_tool(tool_name, tool_params, settings)
            
            self._logger.info(f"工具执行完成: {tool_name}")
            return result
            
        except Exception as e:
            self._logger.error(f"工具执行失败 {tool_name}: {e}")
            raise
    
    async def execute_tool_async(self, tool_id: str, tool_name: str, tool_params: Dict[str, Any], settings: Dict[str, Any], user_prompt: str) -> str:
        """
        异步执行工具
        
        Args:
            tool_id: 工具ID
            tool_name: 工具名称
            tool_params: 工具参数
            settings: 系统设置
            user_prompt: 用户提示
            
        Returns:
            工具ID
        """
        try:
            self._logger.info(f"异步执行工具: {tool_name} (ID: {tool_id})")
            
            # 启动异步任务
            asyncio.create_task(
                async_tool_manager.execute_tool(tool_id, tool_name, tool_params, settings, user_prompt)
            )
            
            return tool_id
            
        except Exception as e:
            self._logger.error(f"异步工具执行失败 {tool_name} (ID: {tool_id}): {e}")
            raise
    
    async def get_tool_status(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工具状态
        
        Args:
            tool_id: 工具ID
            
        Returns:
            工具状态信息
        """
        return async_tool_manager.get_tool_status(tool_id)
    
    async def get_available_tools(self, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        获取可用工具列表
        
        Args:
            settings: 系统设置
            
        Returns:
            可用工具列表
        """
        try:
            tools = []
            
            # 获取MCP工具
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
            
            # 获取内置工具
            builtin_tools = await self._get_builtin_tools(settings)
            tools.extend(builtin_tools)
            
            self._logger.info(f"获取到 {len(tools)} 个可用工具")
            return tools
            
        except Exception as e:
            self._logger.error(f"获取可用工具列表失败: {e}")
            return []
    
    async def _get_builtin_tools(self, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        获取内置工具
        
        Args:
            settings: 系统设置
            
        Returns:
            内置工具列表
        """
        tools = []
        
        # 时间工具
        if settings.get('tools', {}).get('time', {}).get('enabled'):
            tools.append({
                "type": "function",
                "function": {
                    "name": "time_async",
                    "description": "获取当前时间",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            })
        
        # 天气工具
        if settings.get('tools', {}).get('accuweather', {}).get('enabled'):
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather_async",
                        "description": "获取天气信息",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string", "description": "地点"}
                            },
                            "required": ["location"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather_by_city_async",
                        "description": "根据城市获取天气",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string", "description": "城市名称"}
                            },
                            "required": ["city"]
                        }
                    }
                }
            ])
        
        # 维基百科工具
        if settings.get('tools', {}).get('wikipedia', {}).get('enabled'):
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "get_wikipedia_summary_and_sections",
                        "description": "获取维基百科摘要和章节",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "查询关键词"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_wikipedia_section_content",
                        "description": "获取维基百科章节内容",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "page_title": {"type": "string", "description": "页面标题"},
                                "section_title": {"type": "string", "description": "章节标题"}
                            },
                            "required": ["page_title", "section_title"]
                        }
                    }
                }
            ])
        
        # 论文搜索工具
        if settings.get('tools', {}).get('arxiv', {}).get('enabled'):
            tools.append({
                "type": "function",
                "function": {
                    "name": "search_arxiv_papers",
                    "description": "搜索arXiv论文",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词"},
                            "max_results": {"type": "integer", "description": "最大结果数", "default": 10}
                        },
                        "required": ["query"]
                    }
                }
            })
        
        # 知识库工具
        if settings.get("knowledgeBases"):
            enabled_kb = [kb for kb in settings["knowledgeBases"] if kb.get("enabled") and kb.get("processingStatus") == "completed"]
            if enabled_kb:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "query_knowledge_base",
                        "description": "查询知识库",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "kb_id": {"type": "string", "description": "知识库ID"},
                                "query": {"type": "string", "description": "查询内容"}
                            },
                            "required": ["kb_id", "query"]
                        }
                    }
                })
        
        # 文件处理工具
        if settings.get('tools', {}).get('getFile', {}).get('enabled'):
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "get_file_content",
                        "description": "获取文件内容",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {"type": "string", "description": "文件路径"}
                            },
                            "required": ["file_path"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_image_content",
                        "description": "获取图像内容描述",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "image_url": {"type": "string", "description": "图像URL"}
                            },
                            "required": ["image_url"]
                        }
                    }
                }
            ])
        
        # 自主行为工具
        if settings.get('tools', {}).get('autoBehavior', {}).get('enabled'):
            tools.append({
                "type": "function",
                "function": {
                    "name": "auto_behavior",
                    "description": "自主行为管理",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "行为类型"},
                            "parameters": {"type": "object", "description": "行为参数"}
                        },
                        "required": ["action", "parameters"]
                    }
                }
            })
        
        # 代码执行工具
        if settings.get('codeSettings', {}).get('enabled'):
            code_engine = settings.get('codeSettings', {}).get('engine', 'local')
            if code_engine == 'e2b':
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "e2b_code_async",
                        "description": "在E2B沙箱中执行代码",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "代码内容"},
                                "language": {"type": "string", "description": "编程语言", "default": "python"}
                            },
                            "required": ["code"]
                        }
                    }
                })
            elif code_engine == 'sandbox':
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "local_run_code_async",
                        "description": "在本地沙箱中执行代码",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "代码内容"},
                                "language": {"type": "string", "description": "编程语言", "default": "python"}
                            },
                            "required": ["code"]
                        }
                    }
                })
        
        # 搜索工具
        if settings.get('webSearch', {}).get('enabled'):
            search_engine = settings.get('webSearch', {}).get('engine', 'duckduckgo')
            search_tools = {
                'duckduckgo': 'DDGsearch_async',
                'searxng': 'searxng_async',
                'tavily': 'Tavily_search_async',
                'bing': 'Bing_search_async',
                'google': 'Google_search_async',
                'brave': 'Brave_search_async',
                'exa': 'Exa_search_async',
                'serper': 'Serper_search_async',
                'bochaai': 'bochaai_search_async'
            }
            
            if search_engine in search_tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": search_tools[search_engine],
                        "description": f"使用{search_engine}进行网络搜索",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "搜索查询"}
                            },
                            "required": ["query"]
                        }
                    }
                })
        
        # 图像生成工具
        if settings.get('text2imgSettings', {}).get('enabled'):
            img_engine = settings.get('text2imgSettings', {}).get('engine', 'pollinations')
            if img_engine == 'pollinations':
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "pollinations_image",
                        "description": "使用Pollinations生成图像",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string", "description": "图像描述"},
                                "width": {"type": "integer", "description": "图像宽度", "default": 1024},
                                "height": {"type": "integer", "description": "图像高度", "default": 1024}
                            },
                            "required": ["prompt"]
                        }
                    }
                })
            elif img_engine == 'openai':
                img_vendor = settings.get('text2imgSettings', {}).get('vendor', 'openai')
                if img_vendor == 'siliconflow':
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": "siliconflow_image",
                            "description": "使用SiliconFlow生成图像",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "prompt": {"type": "string", "description": "图像描述"},
                                    "model": {"type": "string", "description": "模型名称"}
                                },
                                "required": ["prompt"]
                            }
                        }
                    })
                else:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": "openai_image",
                            "description": "使用OpenAI生成图像",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "prompt": {"type": "string", "description": "图像描述"},
                                    "size": {"type": "string", "description": "图像尺寸", "default": "1024x1024"},
                                    "quality": {"type": "string", "description": "图像质量", "default": "standard"}
                                },
                                "required": ["prompt"]
                            }
                        }
                    })
        
        # 网页爬取工具
        if settings.get('webSearch', {}).get('crawler') in ['jina', 'crawl4ai']:
            crawler = settings.get('webSearch', {}).get('crawler')
            if crawler == 'jina':
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "jina_crawler_async",
                        "description": "使用Jina爬虫获取网页内容",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "网页URL"}
                            },
                            "required": ["url"]
                        }
                    }
                })
            elif crawler == 'crawl4ai':
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "Crawl4Ai_search_async",
                        "description": "使用Crawl4AI爬虫获取网页内容",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "网页URL"}
                            },
                            "required": ["url"]
                        }
                    }
                })
        
        # CLI工具
        if settings.get('CLISettings', {}).get('enabled'):
            cli_engine = settings.get('CLISettings', {}).get('engine', 'cc')
            if cli_engine == 'cc':
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "claude_code_async",
                        "description": "使用Claude Code执行命令",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "description": "要执行的命令"}
                            },
                            "required": ["command"]
                        }
                    }
                })
            elif cli_engine == 'qc':
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "qwen_code_async",
                        "description": "使用Qwen Code执行命令",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "description": "要执行的命令"}
                            },
                            "required": ["command"]
                        }
                    }
                })
        
        # 智能体工具
        if settings.get('agents'):
            enabled_agents = [agent for agent in settings['agents'] if agent.get('enabled')]
            if enabled_agents:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "agent_tool_call",
                        "description": "调用智能体工具",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "agent_id": {"type": "string", "description": "智能体ID"},
                                "task": {"type": "string", "description": "任务描述"}
                            },
                            "required": ["agent_id", "task"]
                        }
                    }
                })
        
        # A2A工具
        if settings.get('a2a'):
            enabled_a2a = [a2a for a2a in settings['a2a'] if a2a.get('enabled')]
            if enabled_a2a:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "a2a_tool_call",
                        "description": "调用A2A工具",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "service_name": {"type": "string", "description": "服务名称"},
                                "task": {"type": "string", "description": "任务描述"}
                            },
                            "required": ["service_name", "task"]
                        }
                    }
                })
        
        # 自定义HTTP工具
        if settings.get("custom_http"):
            for custom_http in settings["custom_http"]:
                if custom_http.get("enabled"):
                    if not custom_http.get('body'):
                        custom_http['body'] = "{}"
                    
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": f"custom_http_{custom_http['name']}",
                            "description": custom_http.get('description', f"自定义HTTP工具: {custom_http['name']}"),
                            "parameters": json.loads(custom_http['body'])
                        }
                    })
        
        # ComfyUI工作流工具
        if settings.get("workflows"):
            for workflow in settings["workflows"]:
                if workflow.get("enabled"):
                    comfyui_properties = {}
                    comfyui_required = []
                    
                    if workflow.get("text_input") is not None:
                        comfyui_properties["text_input"] = {
                            "description": "第一个文字输入，需要输入的提示词，用于生成图片或者视频，如果无特别提示，默认为英文",
                            "type": "string"
                        }
                        comfyui_required.append("text_input")
                    
                    if workflow.get("text_input_2") is not None:
                        comfyui_properties["text_input_2"] = {
                            "description": "第二个文字输入，需要输入的提示词，用于生成图片或者视频，如果无特别提示，默认为英文",
                            "type": "string"
                        }
                        comfyui_required.append("text_input_2")
                    
                    if workflow.get("image_input") is not None:
                        comfyui_properties["image_input"] = {
                            "description": "第一个图片输入，需要输入的图片，必须是图片URL，可以是外部链接，也可以是服务器内部的URL",
                            "type": "string"
                        }
                        comfyui_required.append("image_input")
                    
                    if workflow.get("image_input_2") is not None:
                        comfyui_properties["image_input_2"] = {
                            "description": "第二个图片输入，需要输入的图片，必须是图片URL，可以是外部链接，也可以是服务器内部的URL",
                            "type": "string"
                        }
                        comfyui_required.append("image_input_2")
                    
                    comfyui_parameters = {
                        "type": "object",
                        "properties": comfyui_properties,
                        "required": comfyui_required
                    }
                    
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": f"comfyui_{workflow['unique_filename']}",
                            "description": f"{workflow['description']}。如果要输入图片提示词或者修改提示词，尽可能使用英语。返回的图片结果，请将图片的URL放入![image]()这样的markdown语法中，用户才能看到图片。如果是视频，请将视频的URL放入<video controls> <source src=''></video>的中src中，用户才能看到视频。如果有多个结果，则请用换行符分隔开这几个图片或者视频，用户才能看到多个结果。",
                            "parameters": comfyui_parameters
                        }
                    })
        
        # 自定义LLM工具
        if settings.get('llm_tools'):
            enabled_llm_tools = [tool for tool in settings['llm_tools'] if tool.get('enabled')]
            if enabled_llm_tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "custom_llm_tool",
                        "description": "调用自定义LLM工具",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "tool_name": {"type": "string", "description": "工具名称"},
                                "parameters": {"type": "object", "description": "工具参数"}
                            },
                            "required": ["tool_name", "parameters"]
                        }
                    }
                })
        
        self._logger.info(f"构建工具列表完成，共 {len(tools)} 个工具")
        return tools


# 全局工具服务实例
tool_service = ToolService()