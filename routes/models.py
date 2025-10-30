# -- coding: utf-8 --
"""
模型管理API路由模块
负责处理模型相关的API请求
"""
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException
from config.settings import config_manager


class ProviderModelRequest(BaseModel):
    """提供商模型请求"""
    provider_id: str = Field(..., description="提供商ID")


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    description: str = Field(default="")
    context_length: int = Field(default=0)
    max_tokens: int = Field(default=0)


class ProviderModelsResponse(BaseModel):
    """提供商模型响应"""
    provider_id: str
    models: List[ModelInfo]
    success: bool = Field(default=True)
    message: str = Field(default="")


class ModelRouter:
    """模型路由器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    async def get_models(self) -> Dict[str, Any]:
        """
        获取可用模型列表
        
        Returns:
            模型列表响应
        """
        try:
            settings = await config_manager.get_settings()
            if not settings or 'modelProviders' not in settings:
                return {
                    "models": [],
                    "success": False,
                    "message": "模型提供商配置未找到"
                }
            
            # 提取模型信息
            models = []
            for provider in settings['modelProviders']:
                provider_models = provider.get('models', [])
                for model in provider_models:
                    models.append({
                        "id": model.get('id', ''),
                        "name": model.get('name', ''),
                        "provider": provider.get('name', ''),
                        "providerId": provider.get('id', ''),
                        "context_length": model.get('context_length', 0),
                        "max_tokens": model.get('max_tokens', 0)
                    })
            
            return {
                "models": models,
                "success": True,
                "message": f"成功获取 {len(models)} 个模型"
            }
            
        except Exception as e:
            self._logger.error(f"获取模型列表失败: {e}")
            return {
                "models": [],
                "success": False,
                "message": f"获取模型列表失败: {str(e)}"
            }
    
    async def get_agents(self) -> Dict[str, Any]:
        """
        获取可用智能体列表
        
        Returns:
            智能体列表响应
        """
        try:
            settings = await config_manager.get_settings()
            if not settings or 'agents' not in settings:
                return {
                    "agents": [],
                    "success": False,
                    "message": "智能体配置未找到"
                }
            
            # 提取智能体信息
            agents = []
            for agent in settings['agents']:
                agents.append({
                    "id": agent.get('id', ''),
                    "name": agent.get('name', ''),
                    "description": agent.get('description', ''),
                    "type": agent.get('type', ''),
                    "enabled": agent.get('enabled', False)
                })
            
            return {
                "agents": agents,
                "success": True,
                "message": f"成功获取 {len(agents)} 个智能体"
            }
            
        except Exception as e:
            self._logger.error(f"获取智能体列表失败: {e}")
            return {
                "agents": [],
                "success": False,
                "message": f"获取智能体列表失败: {str(e)}"
            }
    
    async def fetch_provider_models(self, request: ProviderModelRequest) -> ProviderModelsResponse:
        """
        获取指定提供商的模型列表
        
        Args:
            request: 提供商模型请求
            
        Returns:
            提供商模型响应
        """
        try:
            settings = await config_manager.get_settings()
            if not settings or 'modelProviders' not in settings:
                return ProviderModelsResponse(
                    provider_id=request.provider_id,
                    models=[],
                    success=False,
                    message="模型提供商配置未找到"
                )
            
            # 查找指定提供商
            target_provider = None
            for provider in settings['modelProviders']:
                if provider.get('id') == request.provider_id:
                    target_provider = provider
                    break
            
            if not target_provider:
                return ProviderModelsResponse(
                    provider_id=request.provider_id,
                    models=[],
                    success=False,
                    message=f"未找到提供商: {request.provider_id}"
                )
            
            # 提取模型信息
            models = []
            for model in target_provider.get('models', []):
                models.append(ModelInfo(
                    id=model.get('id', ''),
                    name=model.get('name', ''),
                    description=model.get('description', ''),
                    context_length=model.get('context_length', 0),
                    max_tokens=model.get('max_tokens', 0)
                ))
            
            return ProviderModelsResponse(
                provider_id=request.provider_id,
                models=models,
                success=True,
                message=f"成功获取 {len(models)} 个模型"
            )
            
        except Exception as e:
            self._logger.error(f"获取提供商模型失败: {e}")
            return ProviderModelsResponse(
                provider_id=request.provider_id,
                models=[],
                success=False,
                message=f"获取提供商模型失败: {str(e)}"
            )
    
    async def get_model_config(self, model_id: str) -> Dict[str, Any]:
        """
        获取指定模型的配置信息
        
        Args:
            model_id: 模型ID
            
        Returns:
            模型配置信息
        """
        try:
            settings = await config_manager.get_settings()
            if not settings or 'modelProviders' not in settings:
                return {
                    "success": False,
                    "message": "模型提供商配置未找到",
                    "config": {}
                }
            
            # 查找模型
            target_model = None
            target_provider = None
            
            for provider in settings['modelProviders']:
                for model in provider.get('models', []):
                    if model.get('id') == model_id:
                        target_model = model
                        target_provider = provider
                        break
                if target_model:
                    break
            
            if not target_model:
                return {
                    "success": False,
                    "message": f"未找到模型: {model_id}",
                    "config": {}
                }
            
            # 构建配置信息
            config = {
                "id": target_model.get('id', ''),
                "name": target_model.get('name', ''),
                "description": target_model.get('description', ''),
                "provider": {
                    "id": target_provider.get('id', ''),
                    "name": target_provider.get('name', ''),
                    "vendor": target_provider.get('vendor', ''),
                    "base_url": target_provider.get('base_url', ''),
                    "api_key": target_provider.get('api_key', '')
                },
                "context_length": target_model.get('context_length', 0),
                "max_tokens": target_model.get('max_tokens', 0),
                "temperature": target_model.get('temperature', 0.7),
                "top_p": target_model.get('top_p', 1.0),
                "supported_modes": target_model.get('supported_modes', ['chat'])
            }
            
            return {
                "success": True,
                "message": f"成功获取模型配置: {model_id}",
                "config": config
            }
            
        except Exception as e:
            self._logger.error(f"获取模型配置失败: {e}")
            return {
                "success": False,
                "message": f"获取模型配置失败: {str(e)}",
                "config": {}
            }


# 全局模型路由器实例
model_router = ModelRouter()