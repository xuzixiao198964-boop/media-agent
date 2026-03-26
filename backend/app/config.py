from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    APP_NAME: str = "Media Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/media_agent"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_DB: int = 0
    
    # JWT配置
    ACCESS_TOKEN_SECRET: str = "your_access_token_secret_key_here_change_in_production"
    REFRESH_TOKEN_SECRET: str = "your_refresh_token_secret_key_here_change_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # 密码安全配置
    BCRYPT_ROUNDS: int = 12
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_MAX_LENGTH: int = 128
    
    # 登录限制配置
    LOGIN_ATTEMPTS_PER_IP: int = 5
    LOGIN_ATTEMPTS_PER_USER: int = 3
    LOGIN_BLOCK_TIME_MINUTES: int = 15
    
    # 文件上传配置
    MAX_UPLOAD_SIZE: int = 2147483648  # 2GB
    CHUNK_SIZE: int = 5242880  # 5MB
    ALLOWED_VIDEO_FORMATS: List[str] = ["mp4", "mov", "avi", "mkv", "flv", "wmv", "webm", "mpeg", "mpg"]
    
    # 存储路径配置
    VIDEO_STORAGE_PATH: str = "/var/media/videos"
    TEMP_STORAGE_PATH: str = "/var/media/temp"
    THUMBNAIL_STORAGE_PATH: str = "/var/media/thumbnails"
    PROCESSED_STORAGE_PATH: str = "/var/media/processed"
    
    # AI服务配置
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    # TTS服务配置
    AZURE_TTS_KEY: Optional[str] = None
    AZURE_TTS_REGION: str = "eastasia"
    GOOGLE_TTS_KEY: Optional[str] = None
    
    # 平台API配置
    YOUTUBE_API_KEY: Optional[str] = None
    TIKTOK_ACCESS_TOKEN: Optional[str] = None
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = None
    BILIBILI_ACCESS_TOKEN: Optional[str] = None
    
    # CORS配置
    CORS_ORIGINS: str = "http://localhost:8001,http://127.0.0.1:8001"
    
    # 任务队列配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    
    # 监控配置
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建配置实例
settings = Settings()

# 创建必要的目录
def create_directories():
    """创建必要的存储目录"""
    directories = [
        settings.VIDEO_STORAGE_PATH,
        settings.TEMP_STORAGE_PATH,
        settings.THUMBNAIL_STORAGE_PATH,
        settings.PROCESSED_STORAGE_PATH,
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# 初始化时创建目录
if settings.ENVIRONMENT == "development":
    create_directories()