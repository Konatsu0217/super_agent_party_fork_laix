# -- coding: utf-8 --
"""
文件上传API路由模块
负责处理文件上传相关的API请求
"""
import os
import uuid
import logging
import mimetypes
from typing import Dict, Any, List
from fastapi import UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from config.constants import ALLOWED_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_VIDEO_EXTENSIONS
from py.get_setting import UPLOAD_FILES_DIR


class FileUploadResponse(BaseModel):
    """文件上传响应模型"""
    success: bool
    message: str
    file_path: str = Field(default=None)
    file_url: str = Field(default=None)
    file_type: str = Field(default=None)
    file_size: int = Field(default=None)


class FileListResponse(BaseModel):
    """文件列表响应模型"""
    success: bool
    files: List[Any] = Field(default=[])
    total_count: int = Field(default=0)
    message: str = Field(default="")


class FileRouter:
    """文件上传路由器"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    def _get_file_extension(self, filename: str) -> str:
        """获取文件扩展名"""
        return os.path.splitext(filename)[1].lower().lstrip('.')
        
    def _is_allowed_file(self, filename: str) -> bool:
        """检查文件是否允许上传"""
        ext = self._get_file_extension(filename)
        return ext in ALLOWED_EXTENSIONS
        
    def _get_file_type(self, filename: str) -> str:
        """获取文件类型"""
        ext = self._get_file_extension(filename)
        
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            return "image"
        elif ext in ALLOWED_VIDEO_EXTENSIONS:
            return "video"
        elif ext in ALLOWED_EXTENSIONS:
            return "document"
        else:
            return "unknown"
        
    async def upload_file(self, file: UploadFile, subfolder: str = "") -> FileUploadResponse:
        """
        上传文件
        
        Args:
            file: 上传的文件
            subfolder: 子文件夹路径
            
        Returns:
            文件上传响应
        """
        try:
            if not file.filename:
                return FileUploadResponse(
                    success=False,
                    message="文件名不能为空"
                )
            
            # 检查文件类型
            if not self._is_allowed_file(file.filename):
                return FileUploadResponse(
                    success=False,
                    message=f"不支持的文件类型: {file.filename}"
                )
            
            # 生成唯一文件名
            file_ext = self._get_file_extension(file.filename)
            unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
            
            # 构建文件路径
            if subfolder:
                upload_dir = UPLOAD_FILES_DIR / subfolder
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / unique_filename
            else:
                file_path = UPLOAD_FILES_DIR / unique_filename
            
            # 保存文件
            content = await file.read()
            file_size = len(content)
            
            # 检查文件大小 (限制100MB)
            if file_size > 100 * 1024 * 1024:
                return FileUploadResponse(
                    success=False,
                    message="文件大小超过100MB限制"
                )
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            # 获取文件类型
            file_type = self._get_file_type(file.filename)
            
            # 构建文件URL
            file_url = f"/uploads/{subfolder}/{unique_filename}" if subfolder else f"/uploads/{unique_filename}"
            
            self._logger.info(f"文件上传成功: {file.filename} -> {unique_filename} ({file_size} bytes)")
            
            return FileUploadResponse(
                success=True,
                message="文件上传成功",
                file_path=str(file_path),
                file_url=file_url,
                file_type=file_type,
                file_size=file_size
            )
            
        except Exception as e:
            self._logger.error(f"文件上传失败: {e}")
            return FileUploadResponse(
                success=False,
                message=f"文件上传失败: {str(e)}"
            )
    
    async def upload_image(self, file: UploadFile) -> FileUploadResponse:
        """
        上传图片文件
        
        Args:
            file: 上传的图片文件
            
        Returns:
            图片上传响应
        """
        try:
            if not file.filename:
                return FileUploadResponse(
                    success=False,
                    message="文件名不能为空"
                )
            
            # 检查是否为图片
            ext = self._get_file_extension(file.filename)
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                return FileUploadResponse(
                    success=False,
                    message=f"不支持的图片格式: {file.filename}"
                )
            
            return await self.upload_file(file, "images")
            
        except Exception as e:
            self._logger.error(f"图片上传失败: {e}")
            return FileUploadResponse(
                success=False,
                message=f"图片上传失败: {str(e)}"
            )
    
    async def upload_document(self, file: UploadFile) -> FileUploadResponse:
        """
        上传文档文件
        
        Args:
            file: 上传的文档文件
            
        Returns:
            文档上传响应
        """
        try:
            if not file.filename:
                return FileUploadResponse(
                    success=False,
                    message="文件名不能为空"
                )
            
            # 检查是否为文档
            ext = self._get_file_extension(file.filename)
            if ext not in ALLOWED_EXTENSIONS:
                return FileUploadResponse(
                    success=False,
                    message=f"不支持的文档格式: {file.filename}"
                )
            
            return await self.upload_file(file, "documents")
            
        except Exception as e:
            self._logger.error(f"文档上传失败: {e}")
            return FileUploadResponse(
                success=False,
                message=f"文档上传失败: {str(e)}"
            )
    
    def get_uploaded_files(self, file_type: str = "all", limit: int = 100) -> FileListResponse:
        """
        获取已上传的文件列表
        
        Args:
            file_type: 文件类型 (all, image, video, document)
            limit: 返回文件数量限制
            
        Returns:
            文件列表响应
        """
        try:
            files = []
            
            # 获取上传目录
            upload_dirs = [UPLOAD_FILES_DIR]
            if file_type in ["image", "video", "document"]:
                specific_dir = UPLOAD_FILES_DIR / f"{file_type}s"
                if specific_dir.exists():
                    upload_dirs = [specific_dir]
            
            # 扫描文件
            for upload_dir in upload_dirs:
                if not upload_dir.exists():
                    continue
                    
                for file_path in upload_dir.iterdir():
                    if file_path.is_file():
                        stat = file_path.stat()
                        file_ext = self._get_file_extension(file_path.name)
                        
                        # 过滤文件类型
                        if file_type != "all":
                            if file_type == "image" and file_ext not in ALLOWED_IMAGE_EXTENSIONS:
                                continue
                            elif file_type == "video" and file_ext not in ALLOWED_VIDEO_EXTENSIONS:
                                continue
                            elif file_type == "document" and file_ext not in ALLOWED_EXTENSIONS:
                                continue
                        
                        files.append({
                            "filename": file_path.name,
                            "url": f"/uploads/{file_path.relative_to(UPLOAD_FILES_DIR)}",
                            "type": self._get_file_type(file_path.name),
                            "size": stat.st_size,
                            "created_time": stat.st_ctime,
                            "modified_time": stat.st_mtime
                        })
            
            # 按修改时间排序，最新的在前
            files.sort(key=lambda x: x["modified_time"], reverse=True)
            
            # 限制数量
            files = files[:limit]
            
            return FileListResponse(
                success=True,
                files=files,
                total_count=len(files),
                message=f"成功获取 {len(files)} 个文件"
            )
            
        except Exception as e:
            self._logger.error(f"获取文件列表失败: {e}")
            return FileListResponse(
                success=False,
                files=[],
                total_count=0,
                message=f"获取文件列表失败: {str(e)}"
            )
    
    def delete_file(self, filename: str) -> Dict[str, Any]:
        """
        删除文件
        
        Args:
            filename: 文件名
            
        Returns:
            删除结果
        """
        try:
            # 查找文件
            file_path = None
            for root, dirs, files in os.walk(UPLOAD_FILES_DIR):
                if filename in files:
                    file_path = os.path.join(root, filename)
                    break
            
            if not file_path or not os.path.exists(file_path):
                return {
                    "success": False,
                    "message": f"文件未找到: {filename}"
                }
            
            # 删除文件
            os.remove(file_path)
            
            self._logger.info(f"文件删除成功: {filename}")
            
            return {
                "success": True,
                "message": f"文件删除成功: {filename}"
            }
            
        except Exception as e:
            self._logger.error(f"文件删除失败: {e}")
            return {
                "success": False,
                "message": f"文件删除失败: {str(e)}"
            }


# 全局文件路由器实例
file_router = FileRouter()