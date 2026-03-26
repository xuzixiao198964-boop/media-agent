from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import logging
from typing import List

from app.config import settings
from app.database import engine, Base, get_db
from app.api import auth, articles, videos, ai, publish
from app.core.security import verify_token

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建数据库表
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动应用...")
    
    # 创建数据库表（开发环境）
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表创建完成")
    
    yield
    
    logger.info("关闭应用...")
    await engine.dispose()

# 创建FastAPI应用
app = FastAPI(
    title="Media Agent API",
    description="自动化内容生成和发布平台",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
if settings.CORS_ORIGINS:
    origins = settings.CORS_ORIGINS.split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 认证中间件
security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    """获取当前用户"""
    payload = verify_token(token.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "media-agent",
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "欢迎使用 Media Agent API",
        "documentation": "/docs",
        "version": "1.0.0"
    }

# 注册路由
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["认证"]
)

app.include_router(
    articles.router,
    prefix="/api/v1/articles",
    tags=["资讯"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    videos.router,
    prefix="/api/v1/videos",
    tags=["视频"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    ai.router,
    prefix="/api/v1/ai",
    tags=["AI生成"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    publish.router,
    prefix="/api/v1/publish",
    tags=["发布"],
    dependencies=[Depends(get_current_user)]
)

# 错误处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP异常处理"""
    logger.error(f"HTTP异常: {exc.detail}")
    return {
        "error": True,
        "code": exc.status_code,
        "message": exc.detail
    }

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """通用异常处理"""
    logger.error(f"未处理异常: {str(exc)}")
    return {
        "error": True,
        "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "message": "内部服务器错误"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9090,
        reload=settings.DEBUG
    )