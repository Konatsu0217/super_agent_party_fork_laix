# -- coding: utf-8 --
"""
TTS状态跟踪器工具
负责管理TTS播放状态和弹幕消费状态
"""
import logging
from typing import Dict, Any


class TTSStateTracker:
    """TTS状态跟踪器 - 只跟踪TTS播放状态"""
    
    def __init__(self):
        self.tts_playing = False  # TTS是否正在播放
        self._logger = logging.getLogger(__name__)
        
    def set_tts_playing(self, playing: bool = True) -> None:
        """设置TTS播放状态"""
        global can_consume
        self.tts_playing = playing
        can_consume = not playing  # TTS播放时不能消费弹幕
        
        status_msg = "播放中" if playing else "已停止"
        consume_msg = "暂停" if playing else "允许"
        self._logger.info(f"🎙️ TTS状态: {status_msg}, 弹幕消费: {consume_msg}")
            
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "tts_playing": self.tts_playing,
            "can_consume": not self.tts_playing
        }
        
    def is_playing(self) -> bool:
        """检查是否正在播放"""
        return self.tts_playing
        
    def can_consume_messages(self) -> bool:
        """检查是否可以消费消息"""
        return not self.tts_playing


# 全局状态变量
can_consume = True  # 初始状态

# 全局TTS状态跟踪器实例
tts_tracker = TTSStateTracker()