# -- coding: utf-8 --
"""
消息处理基础模块
包含消息格式化和基础处理函数
"""
import copy
import logging
from typing import List, Dict, Any, Optional


class MessageFormatter:
    """消息格式化器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    def remove_images_from_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从消息中移除图像内容，只保留文本
        
        Args:
            messages: 原始消息列表
            
        Returns:
            处理后的消息列表
        """
        if not messages:
            return messages
            
        processed_messages = copy.deepcopy(messages)
        
        for message in processed_messages:
            if 'content' in message and isinstance(message['content'], list):
                # 查找文本内容
                for item in message['content']:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        message['content'] = item['text']
                        break
                        
        return processed_messages
        
    async def extract_images_from_messages(self, messages: List[Dict[str, Any]], fastapi_base_url: str, port: int) -> List[Dict[str, Any]]:
        """
        从消息中提取图像信息
        
        Args:
            messages: 原始消息列表
            fastapi_base_url: FastAPI基础URL
            port: 服务端口号
            
        Returns:
            图像信息列表
        """
        from tools.image import image_processor
        
        images = []
        
        for index, message in enumerate(messages):
            if 'content' not in message or not isinstance(message['content'], list):
                continue
                
            image_urls = []
            
            for item in message['content']:
                if isinstance(item, dict) and item.get('type') == 'image_url':
                    # 处理图像URL
                    processed_image = await image_processor.process_image_url(
                        item["image_url"]["url"], 
                        fastapi_base_url, 
                        port
                    )
                    
                    # 更新原始item
                    item["image_url"]["url"] = processed_image["url"]
                    item["image_url"]["hash"] = processed_image["hash"]
                    
                    image_urls.append(item)
                    
            if image_urls:
                images.append({
                    'index': index, 
                    'images': image_urls
                })
                
        return images
        
    async def inject_image_descriptions(self, messages: List[Dict[str, Any]], images: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将图像描述注入到消息中
        
        Args:
            messages: 原始消息列表
            images: 图像信息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        from tools.image import image_processor
        
        processed_messages = copy.deepcopy(messages)
        
        if settings.get('vision', {}).get('enabled'):
            # Vision模式：将描述作为文本添加到消息内容
            for image_info in images:
                index = image_info['index']
                if index >= len(processed_messages):
                    continue
                    
                for img_item in image_info['images']:
                    # 获取图像描述
                    description = await image_processor.get_image_description(
                        img_item["image_url"]["url"], 
                        settings
                    )
                    
                    if description:
                        # 添加到消息内容
                        if 'content' in processed_messages[index]:
                            formatted_info = image_processor.format_image_info(
                                img_item["image_url"]["url"], 
                                description,
                                img_item["image_url"]["hash"]
                            )
                            processed_messages[index]['content'] += formatted_info
        else:
            # 非Vision模式：保持图像URL在消息中
            for image_info in images:
                index = image_info['index']
                if index >= len(processed_messages):
                    continue
                    
                # 转换消息内容为列表格式
                if isinstance(processed_messages[index].get('content'), str):
                    processed_messages[index]['content'] = [
                        {"type": "text", "text": processed_messages[index]['content']}
                    ]
                elif not isinstance(processed_messages[index].get('content'), list):
                    processed_messages[index]['content'] = [{"type": "text", "text": ""}]
                
                # 添加图像项
                for img_item in image_info['images']:
                    processed_messages[index]['content'].append({
                        "type": "image_url", 
                        "image_url": {"url": img_item["image_url"]["url"]}
                    })
                    
        return processed_messages
        
    def create_system_message(self, content: str) -> Dict[str, Any]:
        """创建系统消息"""
        return {
            'role': 'system',
            'content': content
        }
        
    def add_system_message(self, messages: List[Dict[str, Any]], content: str, position: str = 'start') -> List[Dict[str, Any]]:
        """
        添加系统消息到消息列表
        
        Args:
            messages: 原始消息列表
            content: 系统消息内容
            position: 添加位置 ('start' 或 'end')
            
        Returns:
            处理后的消息列表
        """
        system_msg = self.create_system_message(content)
        
        if position == 'start':
            messages.insert(0, system_msg)
        else:
            messages.append(system_msg)
            
        return messages
        
    def append_to_first_system_message(self, messages: List[Dict[str, Any]], content: str) -> List[Dict[str, Any]]:
        """
        向第一个系统消息追加内容
        
        Args:
            messages: 原始消息列表
            content: 要追加的内容
            
        Returns:
            处理后的消息列表
        """
        if not messages:
            return self.add_system_message(messages, content)
            
        # 查找第一个系统消息
        for message in messages:
            if message.get('role') == 'system':
                if isinstance(message.get('content'), str):
                    message['content'] += content
                return messages
                
        # 如果没有系统消息，创建一个
        return self.add_system_message(messages, content)


# 全局消息格式化器实例
message_formatter = MessageFormatter()