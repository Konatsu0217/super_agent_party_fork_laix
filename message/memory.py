# -- coding: utf-8 --
"""
记忆系统消息注入器模块
负责注入与记忆相关的系统消息
"""
import json
import logging
from typing import List, Dict, Any, Optional


class MemoryMessageInjector:
    """记忆系统消息注入器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    def inject_user_name(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入用户名信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        memory_settings = settings.get("memorySettings", {})
        if not memory_settings.get("is_memory") or not memory_settings.get("userName"):
            return messages
            
        user_name = memory_settings["userName"]
        user_message = f"与你交流的用户名为：\n\n{user_name}\n\n"
        
        return self._append_to_first_system_message(messages, user_message)
        
    def inject_character_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any], current_memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入角色信息（世界观、角色设定、性格等）
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            current_memory: 当前记忆配置
            
        Returns:
            处理后的消息列表
        """
        if not current_memory:
            return messages
            
        user_name = settings.get("memorySettings", {}).get("userName", "")
        char_name = current_memory.get("name", "")
        
        # 注入世界观设定
        messages = self._inject_lore(messages, current_memory, user_name, char_name)
        
        # 注入角色设定
        messages = self._inject_description(messages, current_memory, user_name, char_name)
        
        # 注入性格设定
        messages = self._inject_personality(messages, current_memory, user_name, char_name)
        
        # 注入对话示例
        messages = self._inject_examples(messages, current_memory, user_name, char_name)
        
        # 注入系统提示
        messages = self._inject_system_prompt(messages, current_memory, user_name, char_name)
        
        return messages
        
    def _inject_lore(self, messages: List[Dict[str, Any]], current_memory: Dict[str, Any], user_name: str, char_name: str) -> List[Dict[str, Any]]:
        """注入世界观设定"""
        character_book = current_memory.get("characterBook", [])
        if not character_book:
            return messages
            
        # 获取用户提示和助手回复
        user_prompt = self._get_user_prompt(messages)
        assistant_reply = self._get_assistant_reply(messages)
        
        lore_content = ""
        for lore in character_book:
            lore_keys = lore.get("keysRaw", "").split("\n")
            lore_keys = [key.strip() for key in lore_keys if key.strip()]
            
            # 如果关键词匹配，添加世界观内容
            if lore_keys and any(key in user_prompt or key in assistant_reply for key in lore_keys):
                content = lore.get('content', '')
                # 替换变量
                content = content.replace("{{user}}", user_name).replace("{{char}}", char_name)
                lore_content += content + "\n\n"
        
        if lore_content:
            lore_message = f"世界观设定：\n\n{lore_content}世界观设定结束\n\n"
            messages = self._append_to_first_system_message(messages, lore_message)
            self._logger.info(f"添加世界观设定：{lore_content[:100]}...")
            
        return messages
        
    def _inject_description(self, messages: List[Dict[str, Any]], current_memory: Dict[str, Any], user_name: str, char_name: str) -> List[Dict[str, Any]]:
        """注入角色设定"""
        description = current_memory.get("description", "")
        if not description:
            return messages
            
        # 替换变量
        description = description.replace("{{user}}", user_name).replace("{{char}}", char_name)
        
        desc_message = f"角色设定：\n\n{description}\n\n角色设定结束\n\n"
        messages = self._append_to_first_system_message(messages, desc_message)
        self._logger.info(f"添加角色设定：{description[:100]}...")
        
        return messages
        
    def _inject_personality(self, messages: List[Dict[str, Any]], current_memory: Dict[str, Any], user_name: str, char_name: str) -> List[Dict[str, Any]]:
        """注入性格设定"""
        personality = current_memory.get("personality", "")
        if not personality:
            return messages
            
        # 替换变量
        personality = personality.replace("{{user}}", user_name).replace("{{char}}", char_name)
        
        personality_message = f"性格设定：\n\n{personality}\n\n性格设定结束\n\n"
        messages = self._append_to_first_system_message(messages, personality_message)
        self._logger.info(f"添加性格设定：{personality[:100]}...")
        
        return messages
        
    def _inject_examples(self, messages: List[Dict[str, Any]], current_memory: Dict[str, Any], user_name: str, char_name: str) -> List[Dict[str, Any]]:
        """注入对话示例"""
        examples = current_memory.get("mesExample", "")
        if not examples:
            return messages
            
        # 替换变量
        examples = examples.replace("{{user}}", user_name).replace("{{char}}", char_name)
        
        examples_message = f"对话示例：\n\n{examples}\n\n对话示例结束\n\n"
        messages = self._append_to_first_system_message(messages, examples_message)
        self._logger.info(f"添加对话示例：{examples[:100]}...")
        
        return messages
        
    def _inject_system_prompt(self, messages: List[Dict[str, Any]], current_memory: Dict[str, Any], user_name: str, char_name: str) -> List[Dict[str, Any]]:
        """注入系统提示"""
        system_prompt = current_memory.get("systemPrompt", "")
        if not system_prompt:
            return messages
            
        # 替换变量
        system_prompt = system_prompt.replace("{{user}}", user_name).replace("{{char}}", char_name)
        
        prompt_message = f"系统提示：\n\n{system_prompt}\n\n系统提示结束\n\n"
        messages = self._append_to_first_system_message(messages, prompt_message)
        self._logger.info(f"添加系统提示：{system_prompt[:100]}...")
        
        return messages
        
    async def inject_relevant_memories(self, messages: List[Dict[str, Any]], settings: Dict[str, Any], current_memory: Dict[str, Any], memory_manager: Any) -> List[Dict[str, Any]]:
        """
        注入相关记忆
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            current_memory: 当前记忆配置
            memory_manager: 记忆管理器
            
        Returns:
            处理后的消息列表
        """
        if not settings.get("memorySettings", {}).get("is_memory"):
            return messages
            
        if not current_memory or not memory_manager:
            return messages
            
        user_prompt = self._get_user_prompt(messages)
        memory_id = settings.get("memorySettings", {}).get("selectedMemory", "")
        memory_limit = settings.get("memorySettings", {}).get("memoryLimit", 5)
        
        try:
            relevant_memories = memory_manager.search(
                query=user_prompt, 
                user_id=memory_id, 
                limit=memory_limit
            )
            
            if relevant_memories:
                memories_json = json.dumps(relevant_memories, ensure_ascii=False)
                memories_message = f"之前的相关记忆：\n\n{memories_json}\n\n相关结束\n\n"
                messages = self._append_to_first_system_message(messages, memories_message)
                self._logger.info(f"添加相关记忆：{len(relevant_memories)} 条")
                
        except Exception as e:
            self._logger.error(f"搜索相关记忆失败: {e}")
            
        return messages
        
    def inject_generic_system_prompt(self, messages: List[Dict[str, Any]], settings: Dict[str, Any], current_memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入通用系统提示
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            current_memory: 当前记忆配置
            
        Returns:
            处理后的消息列表
        """
        generic_prompt = settings.get("memorySettings", {}).get("genericSystemPrompt", "")
        if not generic_prompt:
            return messages
            
        user_name = settings.get("memorySettings", {}).get("userName", "")
        char_name = current_memory.get("name", "") if current_memory else ""
        
        # 替换变量
        generic_prompt = generic_prompt.replace("{{user}}", user_name).replace("{{char}}", char_name)
        
        prompt_message = f"系统提示：\n\n{generic_prompt}\n\n系统提示结束\n\n"
        messages = self._append_to_first_system_message(messages, prompt_message)
        self._logger.info(f"添加通用系统提示：{generic_prompt[:100]}...")
        
        return messages
        
    def _get_user_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """获取用户提示"""
        if not messages:
            return ""
            
        # 从后往前找用户消息
        for message in reversed(messages):
            if message.get('role') == 'user':
                return message.get('content', '')
                
        return ""
        
    def _get_assistant_reply(self, messages: List[Dict[str, Any]]) -> str:
        """获取助手回复"""
        if not messages:
            return ""
            
        # 从后往前找助手消息
        for message in reversed(messages):
            if message.get('role') == 'assistant':
                return message.get('content', '')
                
        return ""
        
    def _append_to_first_system_message(self, messages: List[Dict[str, Any]], content: str) -> List[Dict[str, Any]]:
        """
        向第一个系统消息追加内容，如果没有则创建
        
        Args:
            messages: 消息列表
            content: 要追加的内容
            
        Returns:
            处理后的消息列表
        """
        if not messages:
            return messages
            
        # 查找第一个系统消息
        for message in messages:
            if message.get('role') == 'system':
                if isinstance(message.get('content'), str):
                    message['content'] += content
                return messages
                
        # 如果没有系统消息，在开头创建一个
        messages.insert(0, {
            'role': 'system',
            'content': content
        })
        
        return messages


# 全局记忆消息注入器实例
memory_message_injector = MemoryMessageInjector()