# -- coding: utf-8 --
"""
MCP客户端管理器模块
负责管理MCP客户端的初始化、状态跟踪和工具调用
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple, List
from py.mcp_clients import McpClient
from config.constants import MCP_INIT_TIMEOUT, MCP_MAX_WAIT_FAILURE


class MCPClientManager:
    """MCP客户端管理器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._clients: Dict[str, McpClient] = {}
        self._init_tasks: List[asyncio.Task] = []
        self._settings = None
        
    def set_settings(self, settings: Dict[str, Any]):
        """设置系统配置"""
        self._settings = settings
        
    async def initialize_clients(self, mcp_servers: Dict[str, Dict[str, Any]]):
        """
        初始化所有MCP客户端
        
        Args:
            mcp_servers: MCP服务器配置字典
        """
        if not mcp_servers:
            return
            
        self._logger.info(f"开始初始化 {len(mcp_servers)} 个MCP客户端")
        
        # 创建所有初始化任务
        for server_name, server_config in mcp_servers.items():
            task = asyncio.create_task(
                self._init_client_with_timeout(server_name, server_config)
            )
            self._init_tasks.append(task)
        
        # 后台收集结果
        asyncio.create_task(self._collect_init_results())
        
    async def _init_client_with_timeout(
        self, 
        server_name: str, 
        server_config: Dict[str, Any],
        timeout: float = MCP_INIT_TIMEOUT,
        max_wait_failure: float = MCP_MAX_WAIT_FAILURE
    ) -> Tuple[str, Optional[McpClient], Optional[str]]:
        """
        初始化单个MCP客户端，带超时和失败处理
        
        Args:
            server_name: 服务器名称
            server_config: 服务器配置
            timeout: 初始化超时时间
            max_wait_failure: 失败等待时间
            
        Returns:
            (服务器名称, 客户端实例或None, 错误信息或None)
        """
        # 如果配置里直接禁用
        if server_config.get("disabled"):
            self._logger.info(f"MCP服务器 {server_name} 被禁用，跳过初始化")
            return server_name, None, "disabled"

        # 预创建客户端实例
        mcp_client = self._clients.get(server_name) or McpClient()
        self._clients[server_name] = mcp_client

        # 用于同步回调的事件
        failure_event = asyncio.Event()
        first_error: Optional[str] = None

        async def on_failure(msg: str) -> None:
            nonlocal first_error
            # 仅第一次生效
            if first_error is not None:
                return
            first_error = msg
            self._logger.error(f"MCP服务器 {server_name} 初始化失败: {msg}")

            # 记录到 settings
            if self._settings:
                self._settings.setdefault("mcpServers", {}).setdefault(server_name, {})
                self._settings["mcpServers"][server_name]["disabled"] = True
                self._settings["mcpServers"][server_name]["processingStatus"] = "server_error"

            # 把当前客户端标为禁用并关闭
            mcp_client.disabled = True
            await mcp_client.close()
            failure_event.set()

        # 真正初始化
        init_task = asyncio.create_task(
            mcp_client.initialize(
                server_name,
                server_config,
                on_failure_callback=on_failure
            )
        )

        try:
            # 先等初始化本身（最多 timeout 秒）
            await asyncio.wait_for(init_task, timeout=timeout)

            # 初始化没抛异常，再等待看会不会触发 on_failure
            try:
                await asyncio.wait_for(failure_event.wait(), timeout=max_wait_failure)
            except asyncio.TimeoutError:
                # 5 秒内没收到失败回调，认为成功
                pass

            # 最终判定
            if first_error:
                return server_name, None, first_error
            return server_name, mcp_client, None

        except asyncio.TimeoutError:
            # 初始化阶段就超时
            error_msg = f"MCP服务器 {server_name} 初始化超时"
            self._logger.error(error_msg)
            return server_name, None, "timeout"

        except Exception as exc:
            # 任何其他异常
            error_msg = f"MCP服务器 {server_name} 初始化异常: {str(exc)}"
            self._logger.exception(error_msg)
            return server_name, None, str(exc)

        finally:
            # 如果任务还活着，保险起见取消掉
            if not init_task.done():
                init_task.cancel()
                try:
                    await init_task
                except asyncio.CancelledError:
                    pass

    async def _collect_init_results(self):
        """收集所有初始化任务的结果"""
        self._logger.info(f"开始收集 {len(self._init_tasks)} 个MCP初始化任务的结果")
        
        success_count = 0
        failure_count = 0
        
        for task in asyncio.as_completed(self._init_tasks):
            server_name, mcp_client, error = await task
            
            if error:
                self._logger.error(f"MCP客户端 {server_name} 初始化失败: {error}")
                failure_count += 1
                
                # 更新设置中的状态
                if self._settings and server_name in self._settings.get("mcpServers", {}):
                    self._settings['mcpServers'][server_name]['disabled'] = True
                    self._settings['mcpServers'][server_name]['processingStatus'] = 'server_error'
                    
                # 创建禁用状态的客户端
                disabled_client = McpClient()
                disabled_client.disabled = True
                self._clients[server_name] = disabled_client
            else:
                self._logger.info(f"MCP客户端 {server_name} 初始化成功")
                success_count += 1
                self._clients[server_name] = mcp_client
        
        self._logger.info(f"MCP客户端初始化完成: 成功 {success_count} 个, 失败 {failure_count} 个")
        
        # 保存设置更新
        if self._settings:
            from py.get_setting import save_settings
            await save_settings(self._settings)
            
            # 广播设置更新
            from config.settings import config_manager
            await config_manager.broadcast_settings_update(self._settings)

    def get_client(self, server_name: str) -> Optional[McpClient]:
        """获取指定名称的MCP客户端"""
        return self._clients.get(server_name)
        
    def get_all_clients(self) -> Dict[str, McpClient]:
        """获取所有MCP客户端"""
        return self._clients.copy()
        
    def get_enabled_clients(self) -> Dict[str, McpClient]:
        """获取所有启用的MCP客户端"""
        return {
            name: client for name, client in self._clients.items() 
            if not getattr(client, 'disabled', False)
        }
        
    async def call_tool(self, server_name: str, tool_name: str, tool_params: Dict[str, Any]) -> Any:
        """
        调用指定MCP客户端的工具
        
        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            tool_params: 工具参数
            
        Returns:
            工具执行结果
        """
        client = self.get_client(server_name)
        if not client:
            self._logger.error(f"未找到MCP客户端: {server_name}")
            return None
            
        if getattr(client, 'disabled', False):
            self._logger.warning(f"MCP客户端 {server_name} 已被禁用")
            return None
            
        try:
            return await client.call_tool(tool_name, tool_params)
        except Exception as e:
            self._logger.error(f"调用MCP工具失败 {server_name}.{tool_name}: {e}")
            return None
            
    async def get_openai_functions(self, server_name: str, disable_tools: List[str] = None) -> List[Dict[str, Any]]:
        """
        获取指定MCP客户端的OpenAI函数定义
        
        Args:
            server_name: 服务器名称
            disable_tools: 要禁用的工具列表
            
        Returns:
            OpenAI函数定义列表
        """
        client = self.get_client(server_name)
        if not client or getattr(client, 'disabled', False):
            return []
            
        try:
            return await client.get_openai_functions(disable_tools=disable_tools or [])
        except Exception as e:
            self._logger.error(f"获取OpenAI函数定义失败 {server_name}: {e}")
            return []
            
    async def close_all_clients(self):
        """关闭所有MCP客户端"""
        self._logger.info("正在关闭所有MCP客户端...")
        
        # 取消所有初始化任务
        for task in self._init_tasks:
            if not task.done():
                task.cancel()
                
        # 等待所有任务完成
        if self._init_tasks:
            await asyncio.gather(*self._init_tasks, return_exceptions=True)
            
        # 关闭所有客户端
        close_tasks = []
        for server_name, client in self._clients.items():
            try:
                task = asyncio.create_task(client.close())
                close_tasks.append(task)
            except Exception as e:
                self._logger.error(f"关闭MCP客户端 {server_name} 失败: {e}")
                
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
            
        self._clients.clear()
        self._init_tasks.clear()
        self._logger.info("所有MCP客户端已关闭")


# 全局MCP客户端管理器实例
mcp_manager = MCPClientManager()