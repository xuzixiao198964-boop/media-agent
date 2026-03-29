## 3. 视频处理模块详细设计（续）

### 3.3 核心类详细设计

#### 3.3.1 VideoUploadService类（视频上传服务）
```python
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
import os
import hashlib
import shutil
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
from models import Video, VideoMetadata, VideoProcessingTask
from schemas import VideoUploadRequest, VideoChunkUpload, VideoMetadataUpdate
from config import settings
from utils.file_utils import generate_unique_filename, calculate_file_hash
from utils.video_utils import extract_video_metadata, generate_thumbnail
from exceptions import (
    FileTooLargeError,
    InvalidFileTypeError,
    UploadChunkError,
    FileHashMismatchError,
    StorageError
)

class VideoUploadService:
    """视频上传服务类"""
    
    def __init__(self, db: Session):
        self.db = db
        self.chunk_size = 5 * 1024 * 1024  # 5MB
        self.max_file_size = 2 * 1024 * 1024 * 1024  # 2GB
        self.allowed_formats = {
            'mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm', 'mpeg', 'mpg'
        }
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def initiate_upload(self, user_id: int, upload_request: VideoUploadRequest) -> Dict[str, Any]:
        """
        初始化视频上传
        
        Args:
            user_id: 用户ID
            upload_request: 上传请求
            
        Returns:
            Dict: 上传信息
        """
        # 验证文件大小
        if upload_request.file_size > self.max_file_size:
            raise FileTooLargeError(f"文件大小超过限制: {self.max_file_size // (1024*1024)}MB")
        
        # 验证文件格式
        file_ext = upload_request.filename.split('.')[-1].lower()
        if file_ext not in self.allowed_formats:
            raise InvalidFileTypeError(f"不支持的文件格式: {file_ext}")
        
        # 生成唯一文件名
        unique_filename = generate_unique_filename(upload_request.filename)
        
        # 计算文件哈希（基于文件名和大小）
        file_hash = self._calculate_initial_hash(upload_request)
        
        # 检查是否已存在相同文件
        existing_video = self.db.query(Video).filter(
            Video.user_id == user_id,
            Video.file_hash == file_hash,
            Video.status != 'deleted'
        ).first()
        
        if existing_video:
            return {
                'video_id': existing_video.id,
                'status': 'already_exists',
                'message': '相同文件已存在',
                'video': self._format_video_info(existing_video)
            }
        
        # 创建视频记录
        video = Video(
            user_id=user_id,
            filename=unique_filename,
            original_filename=upload_request.filename,
            file_size=upload_request.file_size,
            file_hash=file_hash,
            storage_path=self._get_storage_path(user_id, unique_filename),
            storage_type='local',
            status='uploading',
            privacy=upload_request.privacy or 'private',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db.add(video)
        self.db.commit()
        self.db.refresh(video)
        
        # 创建上传目录
        upload_dir = self._get_upload_dir(video.id)
        os.makedirs(upload_dir, exist_ok=True)
        
        # 计算分片信息
        total_chunks = (upload_request.file_size + self.chunk_size - 1) // self.chunk_size
        
        return {
            'video_id': video.id,
            'upload_id': str(video.id),
            'chunk_size': self.chunk_size,
            'total_chunks': total_chunks,
            'upload_dir': upload_dir,
            'status': 'ready'
        }
    
    async def upload_chunk(self, user_id: int, video_id: int, 
                          chunk_data: VideoChunkUpload) -> Dict[str, Any]:
        """
        上传文件分片
        
        Args:
            user_id: 用户ID
            video_id: 视频ID
            chunk_data: 分片数据
            
        Returns:
            Dict: 上传结果
        """
        # 验证视频
        video = self.db.query(Video).filter(
            Video.id == video_id,
            Video.user_id == user_id,
            Video.status == 'uploading'
        ).first()
        
        if not video:
            raise ValueError("视频不存在或状态不正确")
        
        # 验证分片索引
        total_chunks = (video.file_size + self.chunk_size - 1) // self.chunk_size
        if chunk_data.chunk_index >= total_chunks:
            raise UploadChunkError("分片索引超出范围")
        
        # 计算分片偏移
        chunk_offset = chunk_data.chunk_index * self.chunk_size
        chunk_size = min(self.chunk_size, video.file_size - chunk_offset)
        
        # 验证分片大小
        if len(chunk_data.data) != chunk_size:
            raise UploadChunkError(f"分片大小不匹配: 期望{chunk_size}, 实际{len(chunk_data.data)}")
        
        # 保存分片
        upload_dir = self._get_upload_dir(video_id)
        chunk_filename = f"chunk_{chunk_data.chunk_index:06d}"
        chunk_path = os.path.join(upload_dir, chunk_filename)
        
        try:
            # 写入分片文件
            with open(chunk_path, 'wb') as f:
                f.write(chunk_data.data)
            
            # 更新视频进度
            uploaded_size = (chunk_data.chunk_index + 1) * self.chunk_size
            if uploaded_size > video.file_size:
                uploaded_size = video.file_size
            
            progress = int((uploaded_size / video.file_size) * 100)
            video.processing_progress = progress
            video.updated_at = datetime.utcnow()
            self.db.commit()
            
            return {
                'video_id': video_id,
                'chunk_index': chunk_data.chunk_index,
                'progress': progress,
                'uploaded_size': uploaded_size,
                'total_size': video.file_size,
                'status': 'success'
            }
            
        except Exception as e:
            raise UploadChunkError(f"保存分片失败: {str(e)}")
    
    async def complete_upload(self, user_id: int, video_id: int) -> Dict[str, Any]:
        """
        完成上传
        
        Args:
            user_id: 用户ID
            video_id: 视频ID
            
        Returns:
            Dict: 完成结果
        """
        # 验证视频
        video = self.db.query(Video).filter(
            Video.id == video_id,
            Video.user_id == user_id,
            Video.status == 'uploading'
        ).first()
        
        if not video:
            raise ValueError("视频不存在或状态不正确")
        
        upload_dir = self._get_upload_dir(video_id)
        temp_file_path = os.path.join(upload_dir, 'temp_combined')
        
        try:
            # 合并分片
            await self._merge_chunks(video_id, temp_file_path)
            
            # 计算文件哈希
            actual_hash = await self._calculate_file_hash(temp_file_path)
            
            # 验证文件哈希
            if actual_hash != video.file_hash:
                raise FileHashMismatchError("文件哈希不匹配")
            
            # 验证文件大小
            actual_size = os.path.getsize(temp_file_path)
            if actual_size != video.file_size:
                raise FileHashMismatchError("文件大小不匹配")
            
            # 移动文件到最终位置
            final_path = video.storage_path
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            shutil.move(temp_file_path, final_path)
            
            # 更新视频状态
            video.status = 'uploaded'
            video.uploaded_at = datetime.utcnow()
            video.updated_at = datetime.utcnow()
            
            # 提取视频元数据
            metadata = await self._extract_video_metadata(final_path)
            
            # 更新视频信息
            video.duration = metadata.get('duration')
            video.width = metadata.get('width')
            video.height = metadata.get('height')
            video.resolution = metadata.get('resolution')
            video.frame_rate = metadata.get('frame_rate')
            video.video_codec = metadata.get('video_codec')
            video.video_bitrate = metadata.get('video_bitrate')
            video.audio_codec = metadata.get('audio_codec')
            video.audio_bitrate = metadata.get('audio_bitrate')
            video.format = metadata.get('format')
            
            # 生成缩略图
            thumbnail_path = await self._generate_thumbnail(final_path, video_id)
            video.thumbnail_path = thumbnail_path
            
            self.db.commit()
            
            # 创建默认元数据记录
            metadata_record = VideoMetadata(
                video_id=video_id,
                title=video.original_filename.rsplit('.', 1)[0],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.db.add(metadata_record)
            self.db.commit()
            
            # 创建转码任务
            transcode_task = VideoProcessingTask(
                video_id=video_id,
                task_type='transcode',
                task_name='初始转码',
                parameters={
                    'preset': 'balanced',
                    'output_format': 'mp4',
                    'resolution': 'original'
                },
                status='pending',
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.db.add(transcode_task)
            self.db.commit()
            
            # 异步启动处理
            asyncio.create_task(self._start_video_processing(video_id))
            
            return {
                'video_id': video_id,
                'status': 'completed',
                'message': '上传完成',
                'video': self._format_video_info(video),
                'next_steps': ['metadata_extraction', 'thumbnail_generation', 'transcoding']
            }
            
        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            
            # 更新错误状态
            video.status = 'error'
            video.processing_errors = [str(e)]
            video.updated_at = datetime.utcnow()
            self.db.commit()
            
            raise StorageError(f"完成上传失败: {str(e)}")
    
    async def _merge_chunks(self, video_id: int, output_path: str):
        """合并分片"""
        upload_dir = self._get_upload_dir(video_id)
        
        # 获取所有分片文件
        chunk_files = []
        for filename in os.listdir(upload_dir):
            if filename.startswith('chunk_'):
                chunk_files.append(filename)
        
        # 按索引排序
        chunk_files.sort()
        
        # 合并文件
        with open(output_path, 'wb') as output_file:
            for chunk_file in chunk_files:
                chunk_path = os.path.join(upload_dir, chunk_file)
                with open(chunk_path, 'rb') as input_file:
                    shutil.copyfileobj(input_file, output_file)
        
        # 清理分片文件
        for chunk_file in chunk_files:
            os.remove(os.path.join(upload_dir, chunk_file))
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            calculate_file_hash,
            file_path
        )
    
    async def _extract_video_metadata(self, file_path: str) -> Dict[str, Any]:
        """提取视频元数据"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            extract_video_metadata,
            file_path
        )
    
    async def _generate_thumbnail(self, file_path: str, video_id: int) -> str:
        """生成缩略图"""
        thumbnail_dir = self._get_thumbnail_dir(video_id)
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        thumbnail_path = os.path.join(thumbnail_dir, 'thumbnail_000.jpg')
        
        await asyncio.get_event_loop().run_in_executor(
            self.executor,
            generate_thumbnail,
            file_path,
            thumbnail_path,
            0  # 第0秒
        )
        
        return thumbnail_path
    
    async def _start_video_processing(self, video_id: int):
        """启动视频处理"""
        # 这里可以启动转码、分析等后台任务
        pass
    
    def _calculate_initial_hash(self, upload_request: VideoUploadRequest) -> str:
        """计算初始哈希"""
        content = f"{upload_request.filename}:{upload_request.file_size}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_storage_path(self, user_id: int, filename: str) -> str:
        """获取存储路径"""
        user_dir = f"user_{user_id:08d}"
        date_dir = datetime.utcnow().strftime("%Y/%m/%d")
        return os.path.join(settings.VIDEO_STORAGE_PATH, user_dir, date_dir, filename)
    
    def _get_upload_dir(self, video_id: int) -> str:
        """获取上传目录"""
        return os.path.join(settings.TEMP_STORAGE_PATH, f"upload_{video_id:08d}")
    
    def _get_thumbnail_dir(self, video_id: int) -> str:
        """获取缩略图目录"""
        return os.path.join(settings.THUMBNAIL_STORAGE_PATH, f"video_{video_id:08d}")
    
    def _format_video_info(self, video: Video) -> Dict[str, Any]:
        """格式化视频信息"""
        return {
            'id': video.id,
            'filename': video.filename,
            'original_filename': video.original_filename,
            'file_size': video.file_size,
            'status': video.status,
            'privacy': video.privacy,
            'progress': video.processing_progress,
            'created_at': video.created_at.isoformat() if video.created_at else None,
            'uploaded_at': video.uploaded_at.isoformat() if video.uploaded_at else None
        }

#### 3.3.2 VideoProcessingService类（视频处理服务）
```python
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import os
import subprocess
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from models import Video, VideoProcessingTask
from schemas import VideoProcessRequest, TranscodePreset
from config import settings
from utils.video_utils import (
    transcode_video,
    resize_video,
    add_watermark,
    extract_audio,
    concat_videos,
    trim_video
)
from exceptions import (
    VideoProcessingError,
    InvalidParametersError,
    ResourceUnavailableError
)

class VideoProcessingService:
    """视频处理服务类"""
    
    def __init__(self, db: Session):
        self.db = db
        self.executor = ThreadPoolExecutor(max_workers=settings.MAX_PROCESSING_WORKERS)
        self.active_tasks = {}
    
    async def create_processing_task(self, video_id: int, 
                                   process_request: VideoProcessRequest) -> VideoProcessingTask:
        """
        创建处理任务
        
        Args:
            video_id: 视频ID
            process_request: 处理请求
            
        Returns:
            VideoProcessingTask: 创建的任务
        """
        # 验证视频
        video = self.db.query(Video).filter(
            Video.id == video_id,
            Video.status == 'ready'
        ).first()
        
        if not video:
            raise ValueError("视频不存在或不可用")
        
        # 验证参数
        self._validate_process_parameters(process_request)
        
        # 创建任务
        task = VideoProcessingTask(
            video_id=video_id,
            task_type=process_request.task_type,
            task_name=process_request.task_name or f"{process_request.task_type}_task",
            parameters=process_request.parameters.dict() if hasattr(process_request.parameters, 'dict') else process_request.parameters,
            priority=process_request.priority or 0,
            status='pending',
            input_path=video.storage_path,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        # 异步执行任务
        asyncio.create_task(self._execute_processing_task(task.id))
        
        return task
    
    async def _execute_processing_task(self, task_id: int):
        """执行处理任务"""
        task = self.db.query(VideoProcessingTask).filter(
            VideoProcessingTask.id == task_id
        ).first()
        
        if not task:
            return
        
        # 更新状态为处理中
        task.status = 'processing'
        task.started_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        self.db.commit()
        
        try:
            # 根据任务类型执行不同的处理
            if task.task_type == 'transcode':
                result = await self._transcode_video(task)
            elif task.task_type == 'resize':
                result = await self._resize_video(task)
            elif task.task_type == 'watermark':
                result = await self._add_watermark(task)
            elif task.task_type == 'extract_audio':
                result = await self._extract_audio(task)
            elif task.task_type == 'concat':
                result = await self._concat_videos(task)
            elif task.task_type == 'trim':
                result = await self._trim_video(task)
            else:
                raise InvalidParametersError(f"不支持的任务类型: {task.task_type}")
            
            # 更新任务状态
            task.status = 'success'
            task.progress = 100
            task.output_path = result.get('output_path')
            task.result_metadata = result.get('metadata', {})
            task.completed_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()
            
            # 更新视频信息（如果是转码任务）
            if task.task_type == 'transcode' and result.get('output_path'):
                video = self.db.query(Video).filter(Video.id == task.video_id).first()
                if video:
                    # 可以在这里更新视频的转码版本信息
                    pass
            
            self.db.commit()
            
        except Exception as e:
            # 处理失败
            task.status = 'failed'
            task.error_message = str(e)
            task.error_details = {'exception_type': type(e).__name__}
            task.completed_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()
            
            # 检查是否需要重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.next_retry_at = datetime.utcnow() + timedelta(minutes=5 * task.retry_count)
                task.status = 'pending'
            
            self.db.commit()
            
            # 记录错误日志
            self._log_processing_error(task_id, str(e))
    
    async def _transcode_video(self, task: VideoProcessingTask) -> Dict[str, Any]:
        """转码视频"""
        try:
            parameters = task.parameters
            
            # 获取预设配置
            preset_name = parameters.get('preset', 'balanced')
            preset = self._get_transcode_preset(preset_name)
            
            # 构建输出路径
            output_filename = f"transcoded_{task.video_id}_{preset_name}.mp4"
            output_dir = self._get_output_dir(task.video_id, 'transcoded')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            # 执行转码
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                transcode_video,
                task.input_path,
                output_path,
                preset
            )
            
            return {
                'output_path': output_path,
                'metadata': {
                    'preset': preset_name,
                    'input_size': os.path.getsize(task.input_path),
                    'output_size': os.path.getsize(output_path),
                    'compression_ratio': result.get('compression_ratio'),
                    'processing_time': result.get('processing_time')
                }
            }
            
        except Exception as e:
            raise VideoProcessingError(f"转码失败: {str(e)}")
    
    async def _resize_video(self, task: VideoProcessingTask) -> Dict[str, Any]:
        """调整视频分辨率"""
        try:
            parameters = task.parameters
            resolution = parameters.get('resolution', '720p')
            
            # 解析分辨率
            if resolution == '240p':
                width, height = 426, 240
            elif resolution == '360p':
                width, height = 640, 360
            elif resolution == '480p':
                width, height = 854, 480
            elif resolution == '720p':
                width, height = 1280, 720
            elif resolution == '1080p':
                width, height = 1920, 1080
            elif resolution == 'original':
                # 获取原始分辨率
                video = self.db.query(Video).filter(Video.id == task.video_id).first()
                width, height = video.width, video.height
            else:
                # 自定义分辨率
                if 'x' in resolution:
                    width, height = map(int, resolution.split('x'))
                else:
                    raise InvalidParametersError(f"无效的分辨率: {resolution}")
            
            # 构建输出路径
            output_filename = f"resized_{task.video_id}_{resolution}.mp4"
            output_dir = self._get_output_dir(task.video_id, 'resized')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            # 执行调整
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                resize_video,
                task.input_path,
                output_path,
                width,
                height
            )
            
            return {
                'output_path': output_path,
                'metadata': {
                    'resolution': f"{width}x{height}",
                    'original_resolution': parameters.get('original_resolution'),
                    'processing_time': result.get('processing_time')
                }
            }
            
        except Exception as e:
            raise VideoProcessingError(f"调整分辨率失败: {str(e)}")
    
    async def _add_watermark(self, task: VideoProcessingTask) -> Dict[str, Any]:
        """添加水印"""
        try:
            parameters = task.parameters
            watermark_type = parameters.get('type', 'text')
            
            # 构建输出路径
            output_filename = f"watermarked_{task.video_id}.mp4"
            output_dir = self._get_output_dir(task.video_id, 'watermarked')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            if watermark_type == 'text':
                # 文字水印
                text = parameters.get('text', 'Watermark')
                position = parameters.get('position', 'bottom-right')
                font_size = parameters.get('font_size', 24)
                opacity = parameters.get('opacity', 0.7)
                
                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    add_watermark,
                    task.input_path,
                    output_path,
                    {
                        'type': 'text',
                        'text': text,
                        'position': position,
                        'font_size': font_size,
                        'opacity': opacity
                    }
                )
                
            elif watermark_type == 'image':
                # 图片水印
                image_path = parameters.get('image_path')
                if not image_path or not os.path.exists(image_path):
                    raise InvalidParametersError("水印图片路径无效")
                
                position = parameters.get('position', 'bottom-right')
                scale = parameters.get('scale', 0.1)  # 相对于视频宽度的比例
                opacity = parameters.get('opacity', 0.7)
                
                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    add_watermark,
                    task.input_path,
                    output_path,
                    {
                        'type': 'image',
                        'image_path': image_path,
                        'position': position,
                        'scale': scale,
                        'opacity': opacity
                    }
                )
            
            else:
                raise InvalidParametersError(f"不支持的水印类型: {watermark_type}")
            
            return {
                'output_path': output_path,
                'metadata': {
                    'watermark_type': watermark_type,
                    'position': parameters.get('position'),
                    'processing_time': result.get('processing_time')
                }
            }
            
        except Exception as e:
            raise VideoProcessingError(f"添加水印失败: {str(e)}")
    
    async def _extract_audio(self, task: VideoProcessingTask) -> Dict[str, Any]:
        """提取音频"""
        try:
            parameters = task.parameters
            format = parameters.get('format', 'mp3')
            quality = parameters.get('quality', 'standard')
            
            # 构建输出路径
            output_filename = f"audio_{task.video_id}.{format}"
            output_dir = self._get_output_dir(task.video_id, 'audio')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            # 执行提取
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                extract_audio,
                task.input_path,
                output_path,
                format,
                quality
            )
            
            return {
                'output_path': output_path,
                'metadata': {
                    'format': format,
                    'quality': quality,
                    'duration': result.get('duration'),
                    'file_size': os.path.getsize(output_path),
                    'processing_time': result.get('processing_time')
                }
            }
            
        except Exception as e:
            raise VideoProcessingError(f"提取音频失败: {str(e)}")
    
    async def _concat_videos(self, task: VideoProcessingTask) -> Dict[str, Any]:
        """合并视频"""
        try:
            parameters = task.parameters
            video_ids = parameters.get('video_ids', [])
            
            if not video_ids or len(video_ids) < 2:
                raise InvalidParametersError("至少需要2个视频进行合并")
            
            # 获取所有视频路径
            video_paths = []
            for vid in video_ids:
                video = self.db.query(Video).filter(Video.id == vid).first()
                if video and video.status == 'ready':
                    video_paths.append(video.storage_path)
                else:
                    raise ValueError(f"视频 {vid} 不存在或不可用")
            
            # 构建输出路径
            output_filename = f"concatenated_{task.video_id}.mp4"
            output_dir = self._get_output_dir(task.video_id, 'concatenated')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            # 执行合并
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                concat_videos,
                video_paths,
                output_path
            )
            
            return {
                'output_path': output_path,
                'metadata': {
                    'input_videos': len(video_paths),
                    'total_duration': result.get('total_duration'),
                    'processing_time': result.get('processing_time')
                }
            }
            
        except Exception as e:
            raise VideoProcessingError(f"合并视频失败: {str(e)}")
    
    async def _trim_video(self, task: VideoProcessingTask) -> Dict[str, Any]:
        """裁剪视频"""
        try:
            parameters = task.parameters
            start_time = parameters.get('start_time', 0)  # 秒
            end_time = parameters.get('end_time')
            duration = parameters.get('duration')
            
            # 验证参数
            if end_time is not None and start_time >= end_time:
                raise InvalidParametersError("结束时间必须大于开始时间")
            
            if duration is not None and duration <= 0:
                raise InvalidParametersError("持续时间必须大于0")
            
            # 构建输出路径
            output_filename = f"trimmed_{task.video_id}.mp4"
            output_dir = self._get_output_dir(task.video_id, 'trimmed')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            # 执行裁剪
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                trim_video,
                task.input_path,
                output_path,
                start_time,
                end_time,
                duration
            )
            
            return {
                'output_path': output_path,
                'metadata': {
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': result.get('duration'),
                    'processing_time': result.get('processing_time')
                }
            }
            
        except Exception as e:
            raise VideoProcessingError(f"裁剪视频失败: {str(e)}")
    
    def _validate_process_parameters(self, process_request: VideoProcessRequest):
        """验证处理参数"""
        task_type = process_request.task_type
        
        if task_type == 'transcode':
            if not hasattr(process_request, 'parameters') or not process_request.parameters:
                raise InvalidParametersError("转码任务需要参数")
            
            preset = process_request.parameters.get('preset')
            if preset not in ['fast', 'balanced', 'high_quality']:
                raise InvalidParametersError(f"无效的转码预设: {preset}")
        
        elif task_type == 'resize':
            resolution = process_request.parameters.get('resolution')
            valid_resolutions = ['240p', '360p', '480p', '720p', '1080p', 'original']
            if resolution not in valid_resolutions and 'x' not in str(resolution):
                raise InvalidParametersError(f"无效的分辨率: {resolution}")
        
        elif task_type == 'watermark':
            watermark_type = process_request.parameters.get('type')
            if watermark_type not in ['text', 'image']:
                raise InvalidParametersError(f"无效的水印类型: {watermark_type}")
            
            if watermark_type == 'text' and not process_request.parameters.get('text'):
                raise InvalidParametersError("文字水印需要文本内容")
            
            if watermark_type == 'image' and not process_request.parameters.get('image_path'):
                raise InvalidParametersError("图片水印需要图片路径")
        
        elif task_type == 'extract_audio':
            format = process_request.parameters.get('format', 'mp3')
            if format not in ['mp3', 'wav', 'aac', 'flac']:
                raise InvalidParametersError(f"不支持的音频格式: {format}")
        
        elif task_type == 'concat':
            video_ids = process_request.parameters.get('video_ids', [])
            if len(video_ids) < 2:
                raise InvalidParametersError("合并任务至少需要2个视频")
        
        elif task_type == 'trim':
            start_time = process_request.parameters.get('start_time', 0)
            if start_time < 0:
                raise InvalidParametersError("开始时间不能为负数")
    
    def _get_transcode_preset(self, preset_name: str) -> Dict[str, Any]:
        """获取转码预设"""
        presets = {
            'fast': {
                'video_codec': 'libx264',
                'video_preset': 'ultrafast',
                'video_crf': 28,
                'audio_codec': 'aac',
                'audio_bitrate': '64k',
                'scale': 'original'
            },
            'balanced': {
                'video_codec': 'libx264',
                'video_preset': 'medium',
                'video_crf': 23,
                'audio_codec': 'aac',
                'audio_bitrate': '96k',
                'scale': 'original'
            },
            'high_quality': {
                'video_codec': 'libx264',
                'video_preset': 'slow',
                'video_crf': 18,
                'audio_codec': 'aac',
                'audio_bitrate': '128k',
                'scale': 'original'
            }
        }
        
        return presets.get(preset_name, presets['balanced'])
    
    def _get_output_dir(self, video_id: int, task_type: str) -> str:
        """获取输出目录"""
        return os.path.join(
            settings.PROCESSED_STORAGE_PATH,
            f"video_{video_id:08d}",
            task_type
        )
    
    def _log_processing_error(self, task_id: int, error_message: str):
        """记录处理错误"""
        # 这里可以记录到专门的错误日志系统
        print(f"视频处理任务 {task_id} 错误: {error_message}")

## 4. AI内容生成模块详细设计

### 4.1 模块概述
AI内容生成模块负责文案生成、语音合成、视频合成、流水线管理等功能，主要使用DeepSeek系列模型。

### 4.2 数据库表详细设计

#### 4.2.1 ai_templates表（AI模板表）
```sql
CREATE TABLE ai_templates (
    id SERIAL PRIMARY KEY,
    
    -- 模板信息
    name VARCHAR(100) NOT NULL,
    description TEXT,
    template_type VARCHAR(50) NOT NULL CHECK (template_type IN ('text', 'voice', 'video', 'workflow')),
    category VARCHAR(50),
    
    -- 配置信息
    model_config JSONB NOT NULL DEFAULT '{}',
    prompt_template TEXT NOT NULL,
    input_schema JSONB DEFAULT '{}',
    output_schema JSONB DEFAULT '{}',
    
    -- 参数配置
    default_parameters JSONB DEFAULT '{}',
    parameter_constraints JSONB DEFAULT '{}',
    
    -- 状态信息
    is_active BOOLEAN DEFAULT true,
    is_system BOOLEAN DEFAULT false,
    version VARCHAR(20) DEFAULT '1.0',
    
    -- 使用统计
    usage_count INTEGER DEFAULT 0,
    avg_rating DECIMAL(3,2) DEFAULT 0,
    
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    
    -- 索引
    INDEX idx_ai_templates_template_type (template_type),
    INDEX idx_ai_templates_category (category),
    INDEX idx_ai_templates_is_active (is_active),
    INDEX idx_ai_templates_is_system (is_system),
    
    -- 约束
    CONSTRAINT uniq_template_name UNIQUE (name, version)
);

COMMENT ON TABLE ai_templates IS 'AI模板表';
COMMENT ON COLUMN ai_templates.model_config IS '模型配置，JSON格式';
COMMENT ON COLUMN ai_templates.prompt_template IS '提示词模板';
COMMENT ON COLUMN ai_templates.input_schema IS '输入数据模式，JSON Schema格式';
COMMENT ON COLUMN ai_templates.output_schema IS '输出数据模式，JSON Schema格式';
```

#### 4.2.2 generation_tasks表（生成任务表）
```sql
CREATE TABLE generation_tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 任务信息
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('text', 'voice', 'video', 'workflow')),
    template_id INTEGER REFERENCES ai_templates(id),
    
