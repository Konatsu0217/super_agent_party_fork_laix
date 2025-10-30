# -- coding: utf-8 --
"""
WebSocket路由模块
负责处理WebSocket连接和消息
"""
import json
import logging
from typing import Dict, Any, Set, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
from config.settings import config_manager


class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._active_connections: Set[WebSocket] = set()
        self._connection_info: Dict[WebSocket, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """
        接受WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
            client_id: 客户端ID
        """
        await websocket.accept()
        self._active_connections.add(websocket)
        self._connection_info[websocket] = {
            "client_id": client_id or str(id(websocket)),
            "connected_at": self._get_timestamp()
        }
        
        self._logger.info(f"WebSocket连接已建立: {self._connection_info[websocket]['client_id']}")
        
        # 发送欢迎消息
        await self.send_personal_message(websocket, {
            "type": "connection",
            "status": "connected",
            "client_id": self._connection_info[websocket]['client_id']
        })
    
    def disconnect(self, websocket: WebSocket):
        """
        断开WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
        """
        if websocket in self._active_connections:
            client_id = self._connection_info[websocket]['client_id']
            self._active_connections.remove(websocket)
            del self._connection_info[websocket]
            
            self._logger.info(f"WebSocket连接已断开: {client_id}")
    
    async def send_personal_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        向指定连接发送消息
        
        Args:
            websocket: WebSocket连接对象
            message: 消息内容
        """
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            self._logger.error(f"发送个人消息失败: {e}")
            # 如果发送失败，断开连接
            await self.disconnect(websocket)
    
    async def broadcast_message(self, message: Dict[str, Any]):
        """
        向所有连接广播消息
        
        Args:
            message: 消息内容
        """
        disconnected_connections = []
        
        for connection in self._active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                self._logger.error(f"广播消息失败: {e}")
                disconnected_connections.append(connection)
        
        # 清理断开的连接
        for connection in disconnected_connections:
            self.disconnect(connection)
    
    async def broadcast_settings_update(self, settings: Dict[str, Any]):
        """
        广播设置更新
        
        Args:
            settings: 更新后的设置
        """
        message = {
            "type": "settings",
            "data": settings,
            "timestamp": self._get_timestamp()
        }
        
        await self.broadcast_message(message)
        self._logger.info("设置更新已广播到所有客户端")
    
    async def broadcast_behavior_update(self, settings: Dict[str, Any]):
        """
        广播行为更新
        
        Args:
            settings: 更新后的设置
        """
        message = {
            "type": "behavior",
            "data": settings,
            "timestamp": self._get_timestamp()
        }
        
        await self.broadcast_message(message)
        self._logger.info("行为更新已广播到所有客户端")
    
    async def broadcast_chat_message(self, message: Dict[str, Any], exclude: WebSocket = None):
        """
        广播聊天消息
        
        Args:
            message: 聊天消息
            exclude: 排除的连接
        """
        message["type"] = "chat"
        message["timestamp"] = self._get_timestamp()
        
        disconnected_connections = []
        
        for connection in self._active_connections:
            if connection == exclude:
                continue
                
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                self._logger.error(f"广播聊天消息失败: {e}")
                disconnected_connections.append(connection)
        
        # 清理断开的连接
        for connection in disconnected_connections:
            self.disconnect(connection)
    
    async def broadcast_tts_status(self, status: Dict[str, Any]):
        """
        广播TTS状态更新
        
        Args:
            status: TTS状态
        """
        message = {
            "type": "tts_status",
            "data": status,
            "timestamp": self._get_timestamp()
        }
        
        await self.broadcast_message(message)
        self._logger.info("TTS状态更新已广播到所有客户端")
    
    def get_connection_count(self) -> int:
        """
        获取当前连接数
        
        Returns:
            连接数
        """
        return len(self._active_connections)
    
    def get_connection_info(self, websocket: WebSocket) -> Dict[str, Any]:
        """
        获取连接信息
        
        Args:
            websocket: WebSocket连接对象
            
        Returns:
            连接信息
        """
        return self._connection_info.get(websocket, {}) or {}
    
    def get_all_connections_info(self) -> Dict[str, Any]:
        """
        获取所有连接的信息
        
        Returns:
            所有连接的信息
        """
        return {
            "total_connections": self.get_connection_count(),
            "connections": [
                {
                    "client_id": info["client_id"],
                    "connected_at": info["connected_at"]
                }
                for info in self._connection_info.values()
            ]
        }
    
    def _get_timestamp(self) -> str:
        """
        获取当前时间戳
        
        Returns:
            时间戳字符串
        """
        import time
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    
    async def handle_websocket_message(self, websocket: WebSocket, message: str):
        """
        处理WebSocket消息
        
        Args:
            websocket: WebSocket连接对象
            message: 消息内容
        """
        try:
            data = json.loads(message)
            message_type = data.get("type", "")
            
            self._logger.info(f"收到WebSocket消息: type={message_type}, client={self._connection_info[websocket]['client_id']}")
            
            if message_type == "ping":
                # 响应ping消息
                await self.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": self._get_timestamp()
                })
            
            elif message_type == "get_status":
                # 返回状态信息
                await self.send_personal_message(websocket, {
                    "type": "status",
                    "data": {
                        "connection_count": self.get_connection_count(),
                        "server_time": self._get_timestamp()
                    },
                    "timestamp": self._get_timestamp()
                })
            
            elif message_type == "subscribe_tts":
                # 订阅TTS状态更新
                # TODO: 实现TTS状态订阅逻辑
                pass
            
            elif message_type == "unsubscribe_tts":
                # 取消订阅TTS状态更新
                # TODO: 实现TTS状态取消订阅逻辑
                pass
            
            else:
                # 未知消息类型
                await self.send_personal_message(websocket, {
                    "type": "error",
                    "message": f"未知的消息类型: {message_type}",
                    "timestamp": self._get_timestamp()
                })
                
        except json.JSONDecodeError as e:
            self._logger.error(f"解析WebSocket消息失败: {e}")
            await self.send_personal_message(websocket, {
                "type": "error",
                "message": "无效的消息格式",
                "timestamp": self._get_timestamp()
            })
        
        except Exception as e:
            self._logger.error(f"处理WebSocket消息失败: {e}")
            await self.send_personal_message(websocket, {
                "type": "error",
                "message": f"处理消息失败: {str(e)}",
                "timestamp": self._get_timestamp()
            })


# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()


# 更新配置管理器中的WebSocket管理器引用
config_manager.websocket_manager = websocket_manager