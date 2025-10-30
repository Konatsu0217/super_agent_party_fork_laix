# -- coding: utf-8 --
"""
图像处理工具模块
负责图像URL处理、base64转换、缓存等
"""
import os
import hashlib
import logging
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from py.llm_tool import get_image_base64, get_image_media_type
from py.get_setting import UPLOAD_FILES_DIR


class ImageProcessor:
    """图像处理器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    async def process_image_url(self, image_url: str, fastapi_base_url: str, port: int) -> Dict[str, Any]:
        """
        处理图像URL，转换为base64格式
        
        Args:
            image_url: 图像URL
            fastapi_base_url: FastAPI基础URL
            port: 端口号
            
        Returns:
            包含处理后的图像信息的字典
        """
        if not image_url.startswith("http"):
            return {
                "url": image_url,
                "hash": hashlib.md5(image_url.encode()).hexdigest()
            }
            
        # 处理本地服务器URL
        if fastapi_base_url in image_url:
            image_url = image_url.replace(fastapi_base_url, f"http://127.0.0.1:{port}/")
            
        # 转换为base64
        base64_image = await get_image_base64(image_url)
        media_type = await get_image_media_type(image_url)
        
        return {
            "url": f"data:{media_type};base64,{base64_image}",
            "hash": hashlib.md5(image_url.encode()).hexdigest()
        }
        
    async def get_image_description(self, image_url: str, settings: Dict[str, Any]) -> Optional[str]:
        """
        获取图像描述，优先使用缓存，否则调用vision API
        
        Args:
            image_url: 图像URL
            settings: 系统设置
            
        Returns:
            图像描述内容
        """
        image_hash = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = os.path.join(UPLOAD_FILES_DIR, f"{image_hash}.txt")
        
        # 检查缓存
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                self._logger.warning(f"读取图像缓存失败: {e}")
        
        # 调用vision API
        try:
            if settings.get('vision', {}).get('enabled'):
                return await self._call_vision_api(image_url, settings, 'vision')
            else:
                return await self._call_vision_api(image_url, settings, 'main')
        except Exception as e:
            self._logger.error(f"调用vision API失败: {e}")
            return None
            
    async def _call_vision_api(self, image_url: str, settings: Dict[str, Any], api_type: str) -> str:
        """
        调用vision API获取图像描述
        
        Args:
            image_url: 图像URL
            settings: 系统设置
            api_type: API类型 ('vision' 或 'main')
            
        Returns:
            图像描述内容
        """
        # 转换图像URL
        base64_image = await get_image_base64(image_url)
        media_type = await get_image_media_type(image_url)
        data_url = f"data:{media_type};base64,{base64_image}"
        
        # 准备消息内容
        images_content = [
            {"type": "text", "text": "请仔细描述图片中的内容，包含图片中可能存在的文字、数字、颜色、形状、大小、位置、人物、物体、场景等信息。"},
            {"type": "image_url", "image_url": {"url": data_url}}
        ]
        
        # 选择API配置
        if api_type == 'vision':
            api_key = settings['vision']['api_key']
            base_url = settings['vision']['base_url']
            model = settings['vision']['model']
            temperature = settings['vision']['temperature']
        else:
            api_key = settings['api_key']
            base_url = settings['base_url']
            model = settings['model']
            temperature = settings['temperature']
        
        # 创建客户端并调用
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": images_content}],
            temperature=temperature,
        )
        
        content = response.choices[0].message.content
        
        # 缓存结果
        image_hash = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = os.path.join(UPLOAD_FILES_DIR, f"{image_hash}.txt")
        
        try:
            with open(cache_file, "w", encoding='utf-8') as f:
                f.write(str(content))
        except Exception as e:
            self._logger.warning(f"缓存图像描述失败: {e}")
        
        return content
        
    def get_image_hash(self, image_url: str) -> str:
        """获取图像URL的哈希值"""
        return hashlib.md5(image_url.encode()).hexdigest()
        
    def format_image_info(self, image_url: str, content: str, image_hash: str = None) -> str:
        """
        格式化图像信息
        
        Args:
            image_url: 图像URL
            content: 图像内容描述
            image_hash: 图像哈希值
            
        Returns:
            格式化后的图像信息字符串
        """
        if not image_hash:
            image_hash = self.get_image_hash(image_url)
            
        return f"\n\n图片(URL:{image_url} 哈希值：{image_hash})信息如下：\n\n{content}\n\n"


# 全局图像处理器实例
image_processor = ImageProcessor()