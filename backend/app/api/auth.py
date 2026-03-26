from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.database import get_db
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserProfile, PasswordChange
from app.services.auth_messages import AuthService
from app.core.security import verify_token

router = APIRouter()
security = HTTPBearer()

@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册
    
    仅需要用户名和密码，无需邮箱和手机号
    """
    try:
        auth_service = AuthService(db)
        
        # 获取客户端信息
        client_ip = request.client.host if request.client else "0.0.0.0"
        user_agent = request.headers.get("user-agent", "")
        
        client_info = {
            "ip": client_ip,
            "user_agent": user_agent,
            "device_fingerprint": request.headers.get("x-device-fingerprint", "")
        }
        
        # 注册用户
        result = await auth_service.register(user_data, client_info)
        
        return {
            "success": True,
            "message": "注册成功",
            "data": {
                "user_id": result["user_id"],
                "username": user_data.username,
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"]
            }
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )

@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录
    
    仅支持用户名+密码登录
    """
    try:
        auth_service = AuthService(db)
        
        # 获取客户端信息
        client_ip = request.client.host if request.client else "0.0.0.0"
        user_agent = request.headers.get("user-agent", "")
        
        client_info = {
            "ip": client_ip,
            "user_agent": user_agent,
            "device_fingerprint": request.headers.get("x-device-fingerprint", "")
        }
        
        # 用户登录
        result = await auth_service.login(
            username=user_data.username,
            password=user_data.password,
            client_info=client_info
        )
        
        return TokenResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )

@router.post("/refresh", response_model=Dict[str, Any])
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    刷新访问令牌
    """
    try:
        auth_service = AuthService(db)
        
        # 从请求头获取刷新令牌
        refresh_token = request.headers.get("x-refresh-token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少刷新令牌"
            )
        
        # 获取客户端信息
        client_ip = request.client.host if request.client else "0.0.0.0"
        user_agent = request.headers.get("user-agent", "")
        
        client_info = {
            "ip": client_ip,
            "user_agent": user_agent
        }
        
        # 刷新令牌
        result = await auth_service.refresh_token(refresh_token, client_info)
        
        return {
            "success": True,
            "access_token": result["access_token"],
            "token_type": "bearer",
            "expires_in": 1800  # 30分钟
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="令牌刷新失败"
        )

@router.post("/logout")
async def logout(
    request: Request,
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登出
    """
    try:
        auth_service = AuthService(db)
        
        # 验证令牌
        payload = verify_token(token.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        # 用户登出
        await auth_service.logout(user_id, token.credentials)
        
        return {
            "success": True,
            "message": "登出成功"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出失败"
        )

@router.get("/profile", response_model=UserProfile)
async def get_profile(
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户信息
    """
    try:
        auth_service = AuthService(db)
        
        # 验证令牌
        payload = verify_token(token.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        # 获取用户信息
        user = await auth_service.get_user_profile(user_id)
        
        return UserProfile(**user)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )

@router.put("/profile")
async def update_profile(
    profile_data: UserProfile,
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    更新用户信息
    """
    try:
        auth_service = AuthService(db)
        
        # 验证令牌
        payload = verify_token(token.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        # 更新用户信息
        await auth_service.update_user_profile(user_id, profile_data.dict(exclude_unset=True))
        
        return {
            "success": True,
            "message": "用户信息更新成功"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户信息失败"
        )

@router.post("/password")
async def change_password(
    password_data: PasswordChange,
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    修改密码
    """
    try:
        auth_service = AuthService(db)
        
        # 验证令牌
        payload = verify_token(token.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        # 修改密码
        await auth_service.change_password(user_id, password_data)
        
        return {
            "success": True,
            "message": "密码修改成功"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败"
        )

@router.get("/sessions")
async def get_sessions(
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户活跃会话
    """
    try:
        auth_service = AuthService(db)
        
        # 验证令牌
        payload = verify_token(token.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        # 获取活跃会话
        sessions = await auth_service.get_active_sessions(user_id)
        
        return {
            "success": True,
            "data": sessions
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取会话失败"
        )

@router.delete("/sessions/{session_id}")
async def terminate_session(
    session_id: int,
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    终止指定会话
    """
    try:
        auth_service = AuthService(db)
        
        # 验证令牌
        payload = verify_token(token.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        # 终止会话
        success = await auth_service.terminate_session(user_id, session_id)
        
        if success:
            return {
                "success": True,
                "message": "会话终止成功"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="终止会话失败"
        )