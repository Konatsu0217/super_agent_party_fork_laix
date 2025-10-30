# -- coding: utf-8 --
"""
系统消息注入器模块
负责根据系统设置向消息中注入各种系统提示
"""
import json
import logging
from typing import List, Dict, Any, Optional
from config.constants import SYSTEM_MESSAGE_TEMPLATES


class SystemMessageInjector:
    """系统消息注入器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    async def inject_ha_devices(self, messages: List[Dict[str, Any]], settings: Dict[str, Any], ha_client: Any) -> List[Dict[str, Any]]:
        """
        注入Home Assistant设备信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            ha_client: Home Assistant客户端
            
        Returns:
            处理后的消息列表
        """
        if not settings.get("HASettings", {}).get("enabled") or not ha_client:
            return messages
            
        try:
            ha_devices = await ha_client.call_tool("GetLiveContext", {})
            ha_message = SYSTEM_MESSAGE_TEMPLATES["ha_devices"].format(ha_devices)
            
            return self._append_to_first_system_message(messages, ha_message)
        except Exception as e:
            self._logger.error(f"注入HA设备信息失败: {e}")
            return messages
            
    async def inject_chrome_status(self, messages: List[Dict[str, Any]], settings: Dict[str, Any], chrome_client: Any) -> List[Dict[str, Any]]:
        """
        注入Chrome浏览器状态信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            chrome_client: Chrome MCP客户端
            
        Returns:
            处理后的消息列表
        """
        if not settings.get("chromeMCPSettings", {}).get("enabled") or not chrome_client:
            return messages
            
        try:
            chrome_status = await chrome_client.call_tool("get_windows_and_tabs", {})
            chrome_message = SYSTEM_MESSAGE_TEMPLATES["chrome_status"].format(chrome_status)
            
            return self._append_to_first_system_message(messages, chrome_message)
        except Exception as e:
            self._logger.error(f"注入Chrome状态信息失败: {e}")
            return messages
            
    def inject_auto_behavior_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入自主行为系统信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        if not messages:
            return messages
            
        if messages[-1].get('role') != 'system' or not settings.get('tools', {}).get('autoBehavior', {}).get('enabled'):
            return messages
            
        return self._append_to_first_system_message(messages, SYSTEM_MESSAGE_TEMPLATES["auto_behavior"])
        
    def inject_tts_voice_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入TTS音色信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        tts_settings = settings.get('ttsSettings', {})
        if not tts_settings.get('enabled') or not tts_settings.get('newtts'):
            return messages
            
        # 收集启用的音色
        enabled_voices = []
        for voice_key, voice_config in tts_settings['newtts'].items():
            if voice_config.get('enabled'):
                enabled_voices.append(voice_key)
                
        if not enabled_voices:
            return messages
            
        voices_json = json.dumps(enabled_voices, ensure_ascii=False)
        self._logger.info(f"可用音色：{voices_json}")
        
        voice_message = SYSTEM_MESSAGE_TEMPLATES["tts_voices"].format(voices_json)
        
        return self._append_to_first_system_message(messages, voice_message)
        
    def inject_desktop_vision_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入桌面视觉信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        if not settings.get('vision', {}).get('desktopVision'):
            return messages
            
        return self._append_to_first_system_message(messages, SYSTEM_MESSAGE_TEMPLATES["desktop_vision"])
        
    def inject_time_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any], local_timezone: Any) -> List[Dict[str, Any]]:
        """
        注入时间信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            local_timezone: 本地时区
            
        Returns:
            处理后的消息列表
        """
        if not settings.get('tools', {}).get('time', {}).get('enabled'):
            return messages
            
        if settings.get('tools', {}).get('time', {}).get('triggerMode') != 'beforeThinking':
            return messages
            
        import time
        time_message = SYSTEM_MESSAGE_TEMPLATES["time_info"].format(
            local_timezone, 
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        )
        
        # 添加到最新消息
        if messages:
            messages[-1]['content'] = time_message + messages[-1]['content']
            
        return messages
        
    def inject_inference_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入推理信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        if not settings.get('tools', {}).get('inference', {}).get('enabled'):
            return messages
            
        inference_message = SYSTEM_MESSAGE_TEMPLATES["inference"]
        
        # 添加到最新消息
        if messages:
            messages[-1]['content'] = f"{inference_message}\n\n用户：" + messages[-1]['content']
            
        return messages
        
    def inject_latex_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入LaTeX公式信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        if not settings.get('tools', {}).get('formula', {}).get('enabled'):
            return messages
            
        return self._append_to_first_system_message(messages, SYSTEM_MESSAGE_TEMPLATES["latex"])
        
    def inject_language_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入语言信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        language_config = settings.get('tools', {}).get('language', {})
        if not language_config.get('enabled'):
            return messages
            
        language = language_config.get('language', '中文')
        tone = language_config.get('tone', '正式')
        
        language_message = SYSTEM_MESSAGE_TEMPLATES["language"].format(language, tone)
        
        return self._append_to_first_system_message(messages, language_message)
        
    def inject_sticker_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入贴纸包信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        sticker_packs = settings.get("stickerPacks", [])
        if not sticker_packs:
            return messages
            
        enabled_packs = []
        for sticker_pack in sticker_packs:
            if sticker_pack.get("enabled"):
                enabled_packs.append({
                    'name': sticker_pack['name'],
                    'stickers': sticker_pack.get('stickers', [])
                })
                
        if not enabled_packs:
            return messages
            
        for pack in enabled_packs:
            sticker_message = SYSTEM_MESSAGE_TEMPLATES["stickers"].format(
                pack['name'], 
                json.dumps(pack['stickers'])
            )
            messages = self._append_to_first_system_message(messages, sticker_message)
            
        # 添加使用说明
        usage_message = "\n\n当你需要使用图片时，请将图片的URL放在markdown的图片标签中，例如：\n\n![图片名](图片URL)\n\n，图片markdown必须另起并且独占一行！"
        messages = self._append_to_first_system_message(messages, usage_message)
        
        return messages
        
    def inject_text2img_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入文本到图像信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        if not settings.get('text2imgSettings', {}).get('enabled'):
            return messages
            
        text2img_message = SYSTEM_MESSAGE_TEMPLATES["text2img"]
        
        return self._append_to_first_system_message(messages, text2img_message)
        
    def inject_expression_info(self, messages: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        注入表情信息
        
        Args:
            messages: 原始消息列表
            settings: 系统设置
            
        Returns:
            处理后的消息列表
        """
        if not settings.get('VRMConfig', {}).get('enabledExpressions'):
            return messages
            
        return self._append_to_first_system_message(messages, SYSTEM_MESSAGE_TEMPLATES["expressions"])
        
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


# 全局系统消息注入器实例
system_message_injector = SystemMessageInjector()