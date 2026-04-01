# Media Agent 详细设计文档
## 文档信息
- **文档编号**: DLD-001
- **文档标题**: Media Agent 详细设计文档
- **项目名称**: Media Agent（资讯 → 短视频 → 发布）
- **创建日期**: 2026-03-26
- **创建人**: Media Agent Assistant
- **状态**: 📝 草稿
- **版本**: 1.0
- **依据文档**: 
  - Media-Agent-最终版需求说明书.md
  - Media-Agent-概要设计文档.md
## 1. 用户认证管理模块详细设计
### 1.1 模块概述
用户认证管理模块负责系统的用户注册、登录、会话管理、密码管理等核心认证功能。
### 1.2 数据库表详细设计
#### 1.2.1 users表（用户表）
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    -- 认证信息
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(32) NOT NULL,
    -- 用户信息
    display_name VARCHAR(50),
    avatar_url VARCHAR(500),
    bio TEXT,
     VARCHAR(255),
     VARCHAR(20),
    -- 状态信息
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'locked', 'suspended')),
    _verified BOOLEAN DEFAULT false,
    _verified BOOLEAN DEFAULT false,
    -- 安全信息
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login TIMESTAMP,
    lock_until TIMESTAMP,
    -- 时间信息
    last_login_at TIMESTAMP,
    password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_users_username (username),
    INDEX idx_users_ (),
    INDEX idx_users_status (status),
    INDEX idx_users_created_at (created_at)
);
COMMENT ON TABLE users IS '用户表';
COMMENT ON COLUMN users.username IS '用户名，3-64字符，只允许字母数字下划线';
COMMENT ON COLUMN users.password_hash IS '密码哈希值，使用bcrypt算法';
COMMENT ON COLUMN users.salt IS '密码盐值，16字节';
COMMENT ON COLUMN users.status IS '用户状态：active(活跃), inactive(未激活), locked(锁定), suspended(停用)';
COMMENT ON COLUMN users.failed_login_attempts IS '连续登录失败次数';
COMMENT ON COLUMN users.lock_until IS '锁定截止时间';
```
#### 1.2.2 user_sessions表（用户会话表）
```sql
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 令牌信息
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE NOT NULL,
    token_type VARCHAR(20) DEFAULT 'bearer',
    -- 设备信息
    ip_address INET,
    user_agent TEXT,
    device_type VARCHAR(50),
    device_name VARCHAR(100),
    os_name VARCHAR(50),
    os_version VARCHAR(50),
    browser_name VARCHAR(50),
    browser_version VARCHAR(50),
    -- 位置信息
    country_code VARCHAR(2),
    region_name VARCHAR(100),
    city_name VARCHAR(100),
    -- 状态信息
    is_active BOOLEAN DEFAULT true,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    refresh_expires_at TIMESTAMP NOT NULL,
    -- 索引
    INDEX idx_user_sessions_user_id (user_id),
    INDEX idx_user_sessions_session_token (session_token),
    INDEX idx_user_sessions_refresh_token (refresh_token),
    INDEX idx_user_sessions_expires_at (expires_at),
    INDEX idx_user_sessions_is_active (is_active),
    -- 约束
    CONSTRAINT chk_expires_at CHECK (expires_at > created_at),
    CONSTRAINT chk_refresh_expires_at CHECK (refresh_expires_at > expires_at)
);
COMMENT ON TABLE user_sessions IS '用户会话表';
COMMENT ON COLUMN user_sessions.session_token IS '会话令牌，JWT格式，30分钟有效期';
COMMENT ON COLUMN user_sessions.refresh_token IS '刷新令牌，JWT格式，7天有效期';
COMMENT ON COLUMN user_sessions.expires_at IS '会话令牌过期时间';
COMMENT ON COLUMN user_sessions.refresh_expires_at IS '刷新令牌过期时间';
```
#### 1.2.3 login_history表（登录历史表）
```sql
CREATE TABLE login_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 登录信息
    login_type VARCHAR(20) DEFAULT 'password' CHECK (login_type IN ('password', 'token', 'oauth')),
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(100),
    -- 设备信息
    ip_address INET NOT NULL,
    user_agent TEXT,
    device_fingerprint VARCHAR(64),
    -- 位置信息
    country_code VARCHAR(2),
    region_name VARCHAR(100),
    city_name VARCHAR(100),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_login_history_user_id (user_id),
    INDEX idx_login_history_created_at (created_at),
    INDEX idx_login_history_success (success),
    INDEX idx_login_history_ip_address (ip_address)
);
COMMENT ON TABLE login_history IS '登录历史表';
COMMENT ON COLUMN login_history.login_type IS '登录类型：password(密码), token(令牌), oauth(OAuth)';
COMMENT ON COLUMN login_history.success IS '是否登录成功';
COMMENT ON COLUMN login_history.failure_reason IS '失败原因';
COMMENT ON COLUMN login_history.device_fingerprint IS '设备指纹，用于识别设备';
```
#### 1.2.4 password_history表（密码历史表）
```sql
CREATE TABLE password_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 密码信息
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(32) NOT NULL,
    -- 时间信息
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_password_history_user_id (user_id),
    INDEX idx_password_history_changed_at (changed_at),
    -- 约束
    CONSTRAINT fk_password_history_user FOREIGN KEY (user_id) REFERENCES users(id)
);
COMMENT ON TABLE password_history IS '密码历史表';
COMMENT ON COLUMN password_history.password_hash IS '历史密码哈希值';
COMMENT ON COLUMN password_history.salt IS '历史密码盐值';
```
### 1.3 核心类详细设计
#### 1.3.1 UserService类（用户服务）
```python
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import bcrypt
import jwt
import secrets
from models import User, UserSession, LoginHistory, PasswordHistory
from schemas import UserCreate, UserUpdate, PasswordChange
from config import settings
from utils.validators import validate_username, validate_password
from utils.security import generate_token, verify_token, get_client_info
from utils.geoip import get_location_info
from exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    UserLockedError,
    PasswordTooWeakError,
    PasswordHistoryError
)
class UserService:
    """用户服务类"""
    def __init__(self, db: Session):
        self.db = db
    def register(self, user_data: UserCreate, client_info: Dict[str, Any]) -> User:
        """
        用户注册
        Args:
            user_data: 用户注册数据
            client_info: 客户端信息
        Returns:
            User: 注册成功的用户
        Raises:
            UserAlreadyExistsError: 用户名已存在
            PasswordTooWeakError: 密码强度不足
        """
        # 验证用户名
        if not validate_username(user_data.username):
            raise ValueError("用户名格式无效")
        # 检查用户名是否已存在
        existing_user = self.db.query(User).filter(
            User.username == user_data.username
        ).first()
        if existing_user:
            raise UserAlreadyExistsError(f"用户名 {user_data.username} 已存在")
        # 验证密码强度
        if not validate_password(user_data.password):
            raise PasswordTooWeakError("密码强度不足")
        # 生成密码盐值
        salt = secrets.token_hex(16)
        # 哈希密码
        password_hash = self._hash_password(user_data.password, salt)
        # 创建用户
        user = User(
            username=user_data.username,
            password_hash=password_hash,
            salt=salt,
            display_name=user_data.username,
            =user_data. if hasattr(user_data, '') else None,
            status='active',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        # 记录密码历史
        self._add_password_history(user.id, password_hash, salt)
        # 记录注册日志
        self._log_login(
            user_id=user.id,
            success=True,
            login_type='register',
            ip_address=client_info.get('ip'),
            user_agent=client_info.get('user_agent'),
            device_fingerprint=client_info.get('device_fingerprint')
        )
        return user
    def login(self, username: str, password: str, client_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        用户登录
        Args:
            username: 用户名
            password: 密码
            client_info: 客户端信息
        Returns:
            Dict: 包含访问令牌和用户信息
        Raises:
            InvalidCredentialsError: 用户名或密码错误
            UserLockedError: 用户被锁定
        """
        # 获取用户
        user = self.db.query(User).filter(
            User.username == username
        ).first()
        if not user:
            # 记录失败登录
            self._log_login(
                user_id=None,
                success=False,
                login_type='password',
                ip_address=client_info.get('ip'),
                user_agent=client_info.get('user_agent'),
                device_fingerprint=client_info.get('device_fingerprint'),
                failure_reason='用户不存在'
            )
            raise InvalidCredentialsError("用户名或密码错误")
        # 检查用户状态
        if user.status == 'locked':
            if user.lock_until and user.lock_until > datetime.utcnow():
                raise UserLockedError(f"用户被锁定，解锁时间: {user.lock_until}")
            else:
                # 锁定已过期，重置状态
                user.status = 'active'
                user.failed_login_attempts = 0
                user.lock_until = None
        if user.status != 'active':
            raise InvalidCredentialsError("用户账户不可用")
        # 验证密码
        if not self._verify_password(password, user.password_hash, user.salt):
            # 密码错误，增加失败次数
            user.failed_login_attempts += 1
            user.last_failed_login = datetime.utcnow()
            # 检查是否需要锁定账户
            if user.failed_login_attempts >= 3:
                user.status = 'locked'
                user.lock_until = datetime.utcnow() + timedelta(minutes=15)
            self.db.commit()
            # 记录失败登录
            self._log_login(
                user_id=user.id,
                success=False,
                login_type='password',
                ip_address=client_info.get('ip'),
                user_agent=client_info.get('user_agent'),
                device_fingerprint=client_info.get('device_fingerprint'),
                failure_reason='密码错误'
            )
            raise InvalidCredentialsError("用户名或密码错误")
        # 登录成功，重置失败次数
        user.failed_login_attempts = 0
        user.last_login_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        # 获取位置信息
        location_info = get_location_info(client_info.get('ip'))
        # 创建会话
        session = self._create_session(user.id, client_info, location_info)
        # 更新用户信息
        self.db.commit()
        # 记录成功登录
        self._log_login(
            user_id=user.id,
            success=True,
            login_type='password',
            ip_address=client_info.get('ip'),
            user_agent=client_info.get('user_agent'),
            device_fingerprint=client_info.get('device_fingerprint'),
            location_info=location_info
        )
        return {
            'access_token': session.session_token,
            'refresh_token': session.refresh_token,
            'token_type': 'bearer',
            'expires_in': 1800,  # 30分钟
            'refresh_expires_in': 604800,  # 7天
            'user': {
                'id': user.id,
                'username': user.username,
                'display_name': user.display_name,
                'avatar_url': user.avatar_url,
                '': user.
            }
        }
    def refresh_token(self, refresh_token: str, client_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        刷新访问令牌
        Args:
            refresh_token: 刷新令牌
            client_info: 客户端信息
        Returns:
            Dict: 新的访问令牌
        Raises:
            InvalidTokenError: 令牌无效或已过期
        """
        # 验证刷新令牌
        payload = verify_token(refresh_token, settings.REFRESH_TOKEN_SECRET)
        if not payload:
            raise InvalidTokenError("刷新令牌无效")
        # 获取会话
        session = self.db.query(UserSession).filter(
            UserSession.refresh_token == refresh_token,
            UserSession.is_active == True,
            UserSession.refresh_expires_at > datetime.utcnow()
        ).first()
        if not session:
            raise InvalidTokenError("刷新令牌无效或已过期")
        # 检查用户状态
        user = self.db.query(User).filter(User.id == session.user_id).first()
        if not user or user.status != 'active':
            raise InvalidTokenError("用户账户不可用")
        # 生成新的访问令牌
        new_access_token = generate_token(
            user_id=user.id,
            secret=settings.ACCESS_TOKEN_SECRET,
            expires_delta=timedelta(minutes=30)
        )
        # 更新会话
        session.session_token = new_access_token
        session.last_activity_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        self.db.commit()
        return {
            'access_token': new_access_token,
            'token_type': 'bearer',
            'expires_in': 1800
        }
    def logout(self, user_id: int, session_token: str):
        """
        用户登出
        Args:
            user_id: 用户ID
            session_token: 会话令牌
        """
        # 使会话失效
        session = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.session_token == session_token,
            UserSession.is_active == True
        ).first()
        if session:
            session.is_active = False
            session.updated_at = datetime.utcnow()
            self.db.commit()
    def change_password(self, user_id: int, password_data: PasswordChange) -> bool:
        """
        修改密码
        Args:
            user_id: 用户ID
            password_data: 密码修改数据
        Returns:
            bool: 是否修改成功
        Raises:
            InvalidCredentialsError: 旧密码错误
            PasswordTooWeakError: 新密码强度不足
            PasswordHistoryError: 新密码与历史密码重复
        """
        # 获取用户
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")
        # 验证旧密码
        if not self._verify_password(password_data.old_password, user.password_hash, user.salt):
            raise InvalidCredentialsError("旧密码错误")
        # 验证新密码强度
        if not validate_password(password_data.new_password):
            raise PasswordTooWeakError("新密码强度不足")
        # 检查密码历史
        if self._check_password_history(user_id, password_data.new_password):
            raise PasswordHistoryError("新密码不能与最近5次使用过的密码相同")
        # 生成新密码
        new_salt = secrets.token_hex(16)
        new_password_hash = self._hash_password(password_data.new_password, new_salt)
        # 更新用户密码
        user.password_hash = new_password_hash
        user.salt = new_salt
        user.password_changed_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        # 添加密码历史
        self._add_password_history(user_id, new_password_hash, new_salt)
        # 使所有活跃会话失效（除了当前会话）
        self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).update({
            'is_active': False,
            'updated_at': datetime.utcnow()
        })
        self.db.commit()
        return True
    def get_active_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        获取用户活跃会话列表
        Args:
            user_id: 用户ID
        Returns:
            List: 活跃会话列表
        """
        sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).order_by(UserSession.created_at.desc()).all()
        return [
            {
                'id': session.id,
                'device_type': session.device_type,
                'device_name': session.device_name,
                'os_name': session.os_name,
                'browser_name': session.browser_name,
                'ip_address': session.ip_address,
                'country_code': session.country_code,
                'city_name': session.city_name,
                'last_activity_at': session.last_activity_at,
                'created_at': session.created_at
            }
            for session in sessions
        ]
    def terminate_session(self, user_id: int, session_id: int) -> bool:
        """
        终止指定会话
        Args:
            user_id: 用户ID
            session_id: 会话ID
        Returns:
            bool: 是否终止成功
        """
        session = self.db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).first()
        if session:
            session.is_active = False
            session.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    def _hash_password(self, password: str, salt: str) -> str:
        """哈希密码"""
        # 使用bcrypt算法，cost factor=12
        password_bytes = password.encode('utf-8')
        salt_bytes = salt.encode('utf-8')
        # 实际项目中应该使用更安全的密码哈希方式
        # 这里简化处理
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
        return hashed.decode('utf-8')
    def _verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """验证密码"""
        try:
            password_bytes = password.encode('utf-8')
            hashed_bytes = hashed.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except:
            return False
    def _check_password_history(self, user_id: int, password: str) -> bool:
        """检查密码是否在历史记录中"""
        # 获取最近5次密码历史
        history = self.db.query(PasswordHistory).filter(
            PasswordHistory.user_id == user_id
        ).order_by(PasswordHistory.changed_at.desc()).limit(5).all()
        for record in history:
            if self._verify_password(password, record.password_hash, record.salt):
                return True
        return False
    def _add_password_history(self, user_id: int, password_hash: str, salt: str):
        """添加密码历史记录"""
        history = PasswordHistory(
            user_id=user_id,
            password_hash=password_hash,
            salt=salt,
            changed_at=datetime.utcnow()
        )
        self.db.add(history)
    def _create_session(self, user_id: int, client_info: Dict[str, Any], 
                       location_info: Dict[str, Any]) -> UserSession:
        """创建用户会话"""
        # 生成令牌
        access_token = generate_token(
            user_id=user_id,
            secret=settings.ACCESS_TOKEN_SECRET,
            expires_delta=timedelta(minutes=30)
        )
        refresh_token = generate_token(
            user_id=user_id,
            secret=settings.REFRESH_TOKEN_SECRET,
            expires_delta=timedelta(days=7)
        )
        now = datetime.utcnow()
        session = UserSession(
            user_id=user_id,
            session_token=access_token,
            refresh_token=refresh_token,
            token_type='bearer',
            ip_address=client_info.get('ip'),
            user_agent=client_info.get('user_agent'),
            device_type=client_info.get('device_type'),
            device_name=client_info.get('device_name'),
            os_name=client_info.get('os_name'),
            os_version=client_info.get('os_version'),
            browser_name=client_info.get('browser_name'),
            browser_version=client_info.get('browser_version'),
            country_code=location_info.get('country_code'),
            region_name=location_info.get('region_name'),
            city_name=location_info.get('city_name'),
            is_active=True,
            last_activity_at=now,
            created_at=now,
            expires_at=now + timedelta(minutes=30),
            refresh_expires_at=now + timedelta(days=7)
        )
        self.db.add(session)
        return session
    def _log_login(self, user_id: Optional[int], success: bool, login_type: str,
                  ip_address: str, user_agent: str, device_fingerprint: str = None,
                  failure_reason: str = None, location_info: Dict[str, Any] = None):
        """记录登录日志"""
        login = LoginHistory(
            user_id=user_id,
            login_type=login_type,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            country_code=location_info.get('country_code') if location_info else None,
            region_name=location_info.get('region_name') if location_info else None,
            city_name=location_info.get('city_name') if location_info else None,
            created_at=datetime.utcnow()
        )
        self.db.add(login)
#### 1.3.2 AuthMiddleware类（认证中间件）
```python
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from sqlalchemy.orm import Session
import jwt
from datetime import datetime
from models import User, UserSession
from config import settings
class AuthMiddleware(HTTPBearer):
    """认证中间件"""
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
    async def __call__(self, request: Request) -> Optional[User]:
        """验证请求"""
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if not credentials:
            return None
        if credentials.scheme != "Bearer":
            raise HTTPException(
                status_code=403,
                detail="无效的认证方案"
            )
        # 验证令牌
        token = credentials.credentials
        user = self.verify_token(token, request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="无效或过期的令牌",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return user
    def verify_token(self, token: str, request: Request) -> Optional[User]:
        """验证令牌"""
        try:
            # 解码令牌
            payload = jwt.decode(
                token,
                settings.ACCESS_TOKEN_SECRET,
                algorithms=["HS256"]
            )
            user_id = payload.get("sub")
            if not user_id:
                return None
            # 获取数据库会话
            db: Session = request.state.db
            # 检查用户是否存在且活跃
            user = db.query(User).filter(
                User.id == user_id,
                User.status == 'active'
            ).first()
            if not user:
                return None
            # 检查会话是否有效
            session = db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.session_token == token,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            ).first()
            if not session:
                return None
            # 更新会话最后活动时间
            session.last_activity_at = datetime.utcnow()
            db.commit()
            return user
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None
#### 1.3.3 RateLimiter类（限流器）
```python
from datetime import datetime, timedelta
from typing import Dict, Tuple
import redis
from config import settings
class RateLimiter:
    """API限流器"""
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
    def check_limit(self, key: str, limit: int, window: int) -> Tuple[bool, Dict[str, any]]:
        """
        检查是否超过限制
        Args:
            key: 限流键（如：ip:127.0.0.1 或 user:123）
            limit: 限制次数
            window: 时间窗口（秒）
        Returns:
            Tuple: (是否允许, 限制信息)
        """
        now = datetime.utcnow()
        current_window = int(now.timestamp() // window)
        redis_key = f"rate_limit:{key}:{current_window}"
        # 获取当前计数
        current = self.redis_client.get(redis_key)
        if current is None:
            current = 0
        else:
            current = int(current)
        # 检查是否超过限制
        if current >= limit:
            return False, {
                'allowed': False,
                'limit': limit,
                'remaining': 0,
                'reset': (current_window + 1) * window,
                'retry_after': (current_window + 1) * window - int(now.timestamp())
            }
        # 增加计数
        pipeline = self.redis_client.pipeline()
        pipeline.incr(redis_key)
        pipeline.expire(redis_key, window)
        pipeline.execute()
        return True, {
            'allowed': True,
            'limit': limit,
            'remaining': limit - current - 1,
            'reset': (current_window + 1) * window
        }
    def check_login_limit(self, ip_address: str, username: str) -> Tuple[bool, Dict[str, any]]:
        """
        检查登录限制
        Args:
            ip_address: IP地址
            username: 用户名
        Returns:
            Tuple: (是否允许登录, 限制信息)
        """
        now = datetime.utcnow()
        # IP级别限制（5分钟窗口，最多5次失败）
        ip_key = f"login_limit:ip:{ip_address}"
        ip_window = 300  # 5分钟
        ip_limit = 5
        # 用户级别限制（10分钟窗口，最多3次失败）
        user_key = f"login_limit:user:{username}"
        user_window = 600  # 10分钟
        user_limit = 3
        # 检查IP限制
        ip_allowed, ip_info = self.check_limit(ip_key, ip_limit, ip_window)
        if not ip_allowed:
            return False, {
                'allowed': False,
                'reason': 'ip_limit_exceeded',
                'retry_after': ip_info.get('retry_after', 300),
                'message': 'IP地址登录失败次数过多，请30分钟后再试'
            }
        # 检查用户限制
        user_allowed, user_info = self.check_limit(user_key, user_limit, user_window)
        if not user_allowed:
            return False, {
                'allowed': False,
                'reason': 'user_limit_exceeded',
                'retry_after': user_info.get('retry_after', 600),
                'message': '用户登录失败次数过多，请15分钟后再试'
            }
        return True, {
            'allowed': True,
            'ip_remaining': ip_info.get('remaining', ip_limit),
            'user_remaining': user_info.get('remaining', user_limit)
        }
## 2. 资讯抓取模块详细设计
### 2.1 模块概述
资讯抓取模块负责RSS源管理、网页内容抓取、内容清洗、去重和质量控制等功能。
### 2.2 数据库表详细设计
#### 2.2.1 rss_sources表（RSS源表）
```sql
CREATE TABLE rss_sources (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 源信息
    url VARCHAR(500) NOT NULL,
    title VARCHAR(255),
    description TEXT,
    site_url VARCHAR(500),
    feed_type VARCHAR(20) DEFAULT 'rss' CHECK (feed_type IN ('rss', 'atom')),
    language VARCHAR(10),
    copyright TEXT,
    -- 分类标签
    category VARCHAR(50),
    tags TEXT[] DEFAULT '{}',
    custom_tags TEXT[] DEFAULT '{}',
    -- 抓取配置
    fetch_interval INTEGER DEFAULT 1800 CHECK (fetch_interval >= 300), -- 秒，最小5分钟
    last_fetch_at TIMESTAMP,
    next_fetch_at TIMESTAMP,
    fetch_status VARCHAR(20) DEFAULT 'idle' CHECK (fetch_status IN ('idle', 'fetching', 'success', 'failed')),
    -- 质量统计
    total_fetches INTEGER DEFAULT 0,
    success_fetches INTEGER DEFAULT 0,
    total_articles INTEGER DEFAULT 0,
    avg_quality_score DECIMAL(5,2) DEFAULT 0,
    -- 错误处理
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_at TIMESTAMP,
    -- 状态信息
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    verification_status VARCHAR(20) DEFAULT 'pending',
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP,
    -- 索引
    INDEX idx_rss_sources_user_id (user_id),
    INDEX idx_rss_sources_url (url),
    INDEX idx_rss_sources_is_active (is_active),
    INDEX idx_rss_sources_next_fetch_at (next_fetch_at),
    INDEX idx_rss_sources_fetch_status (fetch_status),
    INDEX idx_rss_sources_category (category),
    -- 约束
    CONSTRAINT chk_fetch_interval CHECK (fetch_interval >= 300),
    CONSTRAINT uniq_user_url UNIQUE (user_id, url)
);
COMMENT ON TABLE rss_sources IS 'RSS源表';
COMMENT ON COLUMN rss_sources.fetch_interval IS '抓取间隔（秒），最小300秒（5分钟）';
COMMENT ON COLUMN rss_sources.fetch_status IS '抓取状态：idle(空闲), fetching(抓取中), success(成功), failed(失败)';
COMMENT ON COLUMN rss_sources.verification_status IS '验证状态：pending(待验证), success(成功), failed(失败)';
```
#### 2.2.2 articles表（文章表）
```sql
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES rss_sources(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 文章标识
    guid VARCHAR(500),
    url VARCHAR(500) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    -- 内容信息
    author VARCHAR(255),
    summary TEXT,
    content TEXT,
    clean_content TEXT,
    word_count INTEGER DEFAULT 0,
    reading_time INTEGER DEFAULT 0, -- 分钟
    -- 媒体信息
    image_url VARCHAR(500),
    image_count INTEGER DEFAULT 0,
    video_url VARCHAR(500),
    video_count INTEGER DEFAULT 0,
    -- 时间信息
    publish_date TIMESTAMP,
    fetch_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_date TIMESTAMP,
    -- 状态信息
    read_status VARCHAR(20) DEFAULT 'unread' CHECK (read_status IN ('unread', 'read', 'archived')),
    favorite BOOLEAN DEFAULT false,
    review_status VARCHAR(20) DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_review')),
    -- 质量评分
    quality_score INTEGER DEFAULT 0 CHECK (quality_score >= 0 AND quality_score <= 100),
    length_score INTEGER DEFAULT 0,
    completeness_score INTEGER DEFAULT 0,
    readability_score INTEGER DEFAULT 0,
    timeliness_score INTEGER DEFAULT 0,
    -- 分类标签
    category VARCHAR(50),
    tags TEXT[] DEFAULT '{}',
    auto_tags TEXT[] DEFAULT '{}',
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_articles_user_id (user_id),
    INDEX idx_articles_source_id (source_id),
    INDEX idx_articles_content_hash (content_hash),
    INDEX idx_articles_publish_date (publish_date),
    INDEX idx_articles_fetch_date (fetch_date),
    INDEX idx_articles_read_status (read_status),
    INDEX idx_articles_review_status (review_status),
    INDEX idx_articles_quality_score (quality_score),
    INDEX idx_articles_category (category),
    INDEX idx_articles_favorite (favorite),
    -- 约束
    CONSTRAINT uniq_content_hash UNIQUE (user_id, content_hash)
);
COMMENT ON TABLE articles IS '文章表';
COMMENT ON COLUMN articles.content_hash IS '内容哈希值，用于去重（标题+正文前500字符）';
COMMENT ON COLUMN articles.clean_content IS '清洗后的正文内容，去除HTML标签和广告';
COMMENT ON COLUMN articles.reading_time IS '预计阅读时间（分钟）';
COMMENT ON COLUMN articles.quality_score IS '质量总分（0-100）';
COMMENT ON COLUMN articles.review_status IS '审核状态：pending(待审核), approved(通过), rejected(拒绝), needs_review(需要人工审核)';
```
#### 2.2.3 article_content表（文章内容表）
```sql
CREATE TABLE article_content (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    -- 原始内容
    raw_html TEXT,
    raw_text TEXT,
    -- 清洗后内容
    clean_html TEXT,
    clean_text TEXT,
    clean_text_hash VARCHAR(64),
    -- 提取信息
    extracted_title VARCHAR(500),
    extracted_author VARCHAR(255),
    extracted_date TIMESTAMP,
    extracted_images JSONB DEFAULT '[]',
    extracted_videos JSONB DEFAULT '[]',
    extracted_links JSONB DEFAULT '[]',
    -- 元数据
    metadata JSONB DEFAULT '{}',
    language VARCHAR(10),
    encoding VARCHAR(50),
    -- 处理信息
    processing_time INTEGER, -- 毫秒
    processing_errors TEXT[] DEFAULT '{}',
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_article_content_article_id (article_id),
    INDEX idx_article_content_clean_text_hash (clean_text_hash),
    -- 约束
    CONSTRAINT uniq_article_content UNIQUE (article_id)
);
COMMENT ON TABLE article_content IS '文章内容表';
COMMENT ON COLUMN article_content.clean_text_hash IS '清洗后文本的哈希值，用于相似度比较';
COMMENT ON COLUMN article_content.extracted_images IS '提取的图片信息，JSON数组格式';
COMMENT ON COLUMN article_content.metadata IS '文章元数据，JSON格式';
```
#### 2.2.4 article_images表（文章图片表）
```sql
CREATE TABLE article_images (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 图片信息
    original_url VARCHAR(500) NOT NULL,
    local_url VARCHAR(500),
    filename VARCHAR(255),
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    format VARCHAR(10),
    -- 图片属性
    alt_text VARCHAR(500),
    caption TEXT,
    is_featured BOOLEAN DEFAULT false,
    position INTEGER DEFAULT 0,
    -- 处理状态
    download_status VARCHAR(20) DEFAULT 'pending' CHECK (download_status IN ('pending', 'downloading', 'success', 'failed')),
    process_status VARCHAR(20) DEFAULT 'pending' CHECK (process_status IN ('pending', 'processing', 'success', 'failed')),
    -- 处理结果
    processed_url VARCHAR(500),
    thumbnail_url VARCHAR(500),
    optimized_url VARCHAR(500),
    -- 错误信息
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    downloaded_at TIMESTAMP,
    processed_at TIMESTAMP,
    -- 索引
    INDEX idx_article_images_article_id (article_id),
    INDEX idx_article_images_user_id (user_id),
    INDEX idx_article_images_download_status (download_status),
    INDEX idx_article_images_is_featured (is_featured),
    -- 约束
    CONSTRAINT chk_image_size CHECK (width > 0 AND height > 0)
);
COMMENT ON TABLE article_images IS '文章图片表';
COMMENT ON COLUMN article_images.download_status IS '下载状态：pending(待下载), downloading(下载中), success(成功), failed(失败)';
COMMENT ON COLUMN article_images.process_status IS '处理状态：pending(待处理), processing(处理中), success(成功), failed(失败)';
```
### 2.3 核心类详细设计
#### 2.3.1 RSSService类（RSS服务）
```python
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import feedparser
import aiohttp
import asyncio
from urllib.parse import urlparse, urljoin
import hashlib
import re
from bs4 import BeautifulSoup
from readability import Document
import html2text
from models import RSSSource, Article, ArticleContent, ArticleImage
from schemas import RSSSourceCreate, RSSSourceUpdate, ArticleFilter
from config import settings
from utils.validators import validate_url, is_valid_rss
from utils.http_client import AsyncHTTPClient
from utils.text_processor import clean_html, extract_text, calculate_reading_time
from utils.image_downloader import download_and_process_image
from exceptions import (
    InvalidURLError,
    RSSFetchError,
    RSSParseError,
    DuplicateContentError,
    ImageDownloadError
)
class RSSService:
    """RSS服务类"""
    def __init__(self, db: Session):
        self.db = db
        self.http_client = AsyncHTTPClient()
        self.html2text = html2text.HTML2Text()
        self.html2text.ignore_links = False
        self.html2text.ignore_images = False
    async def add_source(self, user_id: int, source_data: RSSSourceCreate) -> RSSSource:
        """
        添加RSS源
        Args:
            user_id: 用户ID
            source_data: RSS源数据
        Returns:
            RSSSource: 添加的RSS源
        Raises:
            InvalidURLError: URL无效
            RSSFetchError: RSS抓取失败
            DuplicateSourceError: 重复的RSS源
        """
        # 验证URL
        if not validate_url(source_data.url):
            raise InvalidURLError("无效的URL")
        # 检查是否已存在
        existing = self.db.query(RSSSource).filter(
            RSSSource.user_id == user_id,
            RSSSource.url == source_data.url
        ).first()
        if existing:
            raise DuplicateSourceError("该RSS源已存在")
        # 验证RSS源
        is_valid, feed_info = await self._validate_rss_source(source_data.url)
        if not is_valid:
            raise RSSFetchError("无法验证RSS源")
        # 创建RSS源
        source = RSSSource(
            user_id=user_id,
            url=source_data.url,
            title=feed_info.get('title') or source_data.title,
            description=feed_info.get('description') or source_data.description,
            site_url=feed_info.get('site_url') or source_data.site_url,
            feed_type=feed_info.get('feed_type', 'rss'),
            language=feed_info.get('language'),
            category=source_data.category,
            tags=source_data.tags or [],
            fetch_interval=source_data.fetch_interval or 1800,
            is_active=True,
            is_verified=True,
            verification_status='success',
            verified_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        # 立即抓取一次
        asyncio.create_task(self._fetch_source_articles(source.id))
        return source
    async def fetch_source(self, source_id: int) -> Dict[str, Any]:
        """
        抓取RSS源文章
        Args:
            source_id: RSS源ID
        Returns:
            Dict: 抓取结果统计
        """
        source = self.db.query(RSSSource).filter(RSSSource.id == source_id).first()
        if not source:
            raise ValueError("RSS源不存在")
        # 更新抓取状态
        source.fetch_status = 'fetching'
        source.last_fetch_at = datetime.utcnow()
        self.db.commit()
        try:
            # 解析RSS源
            feed = await self._parse_feed(source.url)
            if not feed or not feed.entries:
                raise RSSParseError("RSS源无内容")
            # 处理文章
            new_count = 0
            updated_count = 0
            error_count = 0
            for entry in feed.entries[:50]:  # 限制每次最多处理50篇
                try:
                    result = await self._process_article_entry(
                        source_id=source.id,
                        user_id=source.user_id,
                        entry=entry,
                        feed_info=feed.feed
                    )
                    if result['status'] == 'new':
                        new_count += 1
                    elif result['status'] == 'updated':
                        updated_count += 1
                except Exception as e:
                    error_count += 1
                    self._log_error(source.id, f"处理文章失败: {str(e)}")
            # 更新源统计
            source.fetch_status = 'success'
            source.total_fetches += 1
            source.success_fetches += 1
            source.total_articles += new_count
            source.next_fetch_at = datetime.utcnow() + timedelta(seconds=source.fetch_interval)
            source.updated_at = datetime.utcnow()
            self.db.commit()
            return {
                'source_id': source.id,
                'source_title': source.title,
                'new_articles': new_count,
                'updated_articles': updated_count,
                'error_count': error_count,
                'total_articles': source.total_articles,
                'fetch_time': datetime.utcnow()
            }
        except Exception as e:
            # 更新错误状态
            source.fetch_status = 'failed'
            source.error_count += 1
            source.last_error = str(e)
            source.last_error_at = datetime.utcnow()
            source.updated_at = datetime.utcnow()
            self.db.commit()
            raise RSSFetchError(f"抓取RSS源失败: {str(e)}")
    async def _validate_rss_source(self, url: str) -> Tuple[bool, Dict[str, Any]]:
        """验证RSS源"""
        try:
            # 尝试解析RSS
            feed = await self._parse_feed(url)
            if not feed:
                return False, {'error': '无法解析RSS源'}
            # 检查基本要素
            if not hasattr(feed, 'feed') or not feed.feed:
                return False, {'error': 'RSS源格式不正确'}
            feed_info = feed.feed
            # 提取基本信息
            result = {
                'title': getattr(feed_info, 'title', ''),
                'description': getattr(feed_info, 'description', ''),
                'site_url': getattr(feed_info, 'link', ''),
                'feed_type': feed.version if hasattr(feed, 'version') else 'rss',
                'language': getattr(feed_info, 'language', ''),
                'entry_count': len(feed.entries) if hasattr(feed, 'entries') else 0
            }
            # 检查是否有文章
            if result['entry_count'] == 0:
                return False, {'error': 'RSS源无文章内容'}
            return True, result
        except Exception as e:
            return False, {'error': str(e)}
    async def _parse_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """解析RSS源"""
        try:
            # 使用aiohttp获取内容
            content = await self.http_client.get(url, timeout=10)
            if not content:
                return None
            # 使用feedparser解析
            feed = feedparser.parse(content)
            # 检查解析状态
            if feed.bozo:
                # 有解析错误，但可能仍然有内容
                if not hasattr(feed, 'entries') or not feed.entries:
                    return None
            return feed
        except Exception as e:
            raise RSSParseError(f"解析RSS源失败: {str(e)}")
    async def _process_article_entry(self, source_id: int, user_id: int, 
                                   entry: Dict[str, Any], feed_info: Dict[str, Any]) -> Dict[str, Any]:
        """处理文章条目"""
        # 提取文章基本信息
        article_url = getattr(entry, 'link', '')
        if not article_url:
            raise ValueError("文章URL为空")
        # 生成内容哈希（用于去重）
        title = getattr(entry, 'title', '无标题')
        summary = getattr(entry, 'summary', '')
        content_hash = self._generate_content_hash(title, summary[:500])
        # 检查是否已存在
        existing = self.db.query(Article).filter(
            Article.user_id == user_id,
            Article.content_hash == content_hash
        ).first()
        if existing:
            # 文章已存在，检查是否需要更新
            return await self._update_existing_article(existing.id, entry)
        # 获取文章详细内容
        article_content = await self._fetch_article_content(article_url)
        # 计算质量评分
        quality_scores = self._calculate_quality_scores(
            title=title,
            content=article_content['clean_text'],
            publish_date=getattr(entry, 'published_parsed', None),
            images=article_content['images']
        )
        # 创建文章记录
        article = Article(
            source_id=source_id,
            user_id=user_id,
            guid=getattr(entry, 'id', article_url),
            url=article_url,
            title=title,
            content_hash=content_hash,
            author=getattr(entry, 'author', ''),
            summary=summary,
            content=article_content['clean_text'][:10000],  # 限制长度
            word_count=len(article_content['clean_text'].split()),
            reading_time=calculate_reading_time(article_content['clean_text']),
            image_url=article_content['images'][0]['url'] if article_content['images'] else None,
            image_count=len(article_content['images']),
            publish_date=self._parse_date(getattr(entry, 'published_parsed', None)),
            fetch_date=datetime.utcnow(),
            read_status='unread',
            quality_score=quality_scores['total'],
            length_score=quality_scores['length'],
            completeness_score=quality_scores['completeness'],
            readability_score=quality_scores['readability'],
            timeliness_score=quality_scores['timeliness'],
            category=None,  # 后续自动分类
            tags=[],  # 后续自动标签
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(article)
        self.db.flush()  # 获取article.id
        # 保存详细内容
        content_record = ArticleContent(
            article_id=article.id,
            raw_html=article_content['raw_html'],
            raw_text=article_content['raw_text'],
            clean_html=article_content['clean_html'],
            clean_text=article_content['clean_text'],
            clean_text_hash=hashlib.sha256(article_content['clean_text'].encode()).hexdigest(),
            extracted_title=article_content['title'],
            extracted_author=article_content['author'],
            extracted_date=article_content['date'],
            extracted_images=article_content['images'],
            metadata=article_content['metadata'],
            language=article_content['language'],
            processing_time=article_content['processing_time'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(content_record)
        # 异步下载图片
        if article_content['images']:
            asyncio.create_task(
                self._download_article_images(article.id, user_id, article_content['images'])
            )
        self.db.commit()
        return {
            'status': 'new',
            'article_id': article.id,
            'title': article.title,
            'quality_score': article.quality_score
        }
    async def _fetch_article_content(self, url: str) -> Dict[str, Any]:
        """获取文章详细内容"""
        start_time = datetime.utcnow()
        try:
            # 获取网页内容
            html_content = await self.http_client.get(url, timeout=15)
            if not html_content:
                raise ValueError("无法获取网页内容")
            # 使用readability提取正文
            doc = Document(html_content)
            content_html = doc.summary()
            title = doc.title()
            # 清理HTML
            clean_html_content = clean_html(content_html)
            # 转换为纯文本
            clean_text = self.html2text.handle(clean_html_content)
            # 提取图片
            soup = BeautifulSoup(html_content, 'html.parser')
            images = []
            for img in soup.find_all('img', src=True):
                img_url = img['src']
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urljoin(url, img_url)
                images.append({
                    'url': img_url,
                    'alt': img.get('alt', ''),
                    'width': img.get('width'),
                    'height': img.get('height')
                })
            # 限制图片数量
            images = images[:5]
            # 提取作者和日期（简单实现）
            author = self._extract_author(soup)
            date = self._extract_date(soup)
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return {
                'raw_html': html_content[:50000],  # 限制长度
                'raw_text': extract_text(html_content),
                'clean_html': clean_html_content,
                'clean_text': clean_text,
                'title': title,
                'author': author,
                'date': date,
                'images': images,
                'metadata': {
                    'url': url,
                    'content_length': len(clean_text),
                    'image_count': len(images)
                },
                'language': 'zh-CN',  # 简化处理，实际应该检测语言
                'processing_time': int(processing_time)
            }
        except Exception as e:
            raise RSSFetchError(f"获取文章内容失败: {str(e)}")
    def _calculate_quality_scores(self, title: str, content: str, 
                                publish_date: Optional[datetime], 
                                images: List[Dict]) -> Dict[str, int]:
        """计算质量评分"""
        scores = {
            'length': 0,
            'completeness': 0,
            'readability': 0,
            'timeliness': 0,
            'total': 0
        }
        # 1. 长度分（0-30分）
        content_length = len(content)
        if content_length >= 2000:
            scores['length'] = 30
        elif content_length >= 1000:
            scores['length'] = 25
        elif content_length >= 500:
            scores['length'] = 20
        elif content_length >= 200:
            scores['length'] = 15
        else:
            scores['length'] = 10
        # 2. 完整性分（0-30分）
        completeness = 0
        if title and len(title) > 5:
            completeness += 10
        if content_length > 200:
            completeness += 10
        if images:
            completeness += 10
        scores['completeness'] = completeness
        # 3. 可读性分（0-20分）
        # 简化实现：基于句子长度和标点符号
        sentences = re.split(r'[。！？.!?]', content)
        avg_sentence_length = sum(len(s) for s in sentences) / max(len(sentences), 1)
        if 15 <= avg_sentence_length <= 25:
            scores['readability'] = 20
        elif 10 <= avg_sentence_length <= 30:
            scores['readability'] = 15
        else:
            scores['readability'] = 10
        # 4. 时效性分（0-20分）
        if publish_date:
            days_diff = (datetime.utcnow() - publish_date).days
            if days_diff <= 1:
                scores['timeliness'] = 20
            elif days_diff <= 3:
                scores['timeliness'] = 15
            elif days_diff <= 7:
                scores['timeliness'] = 10
            elif days_diff <= 30:
                scores['timeliness'] = 5
            else:
                scores['timeliness'] = 0
        else:
            scores['timeliness'] = 5  # 无日期信息，给基础分
        # 计算总分
        scores['total'] = sum(scores.values())
        return scores
    async def _download_article_images(self, article_id: int, user_id: int, images: List[Dict]):
        """下载文章图片"""
        for i, img_info in enumerate(images[:3]):  # 最多下载3张
            try:
                image_record = ArticleImage(
                    article_id=article_id,
                    user_id=user_id,
                    original_url=img_info['url'],
                    alt_text=img_info.get('alt', ''),
                    position=i,
                    is_featured=(i == 0),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.db.add(image_record)
                self.db.flush()
                # 异步下载和处理图片
                asyncio.create_task(
                    self._process_single_image(image_record.id, img_info)
                )
            except Exception as e:
                self._log_error(article_id, f"创建图片记录失败: {str(e)}")
    async def _process_single_image(self, image_id: int, img_info: Dict[str, Any]):
        """处理单张图片"""
        try:
            image_record = self.db.query(ArticleImage).filter(
                ArticleImage.id == image_id
            ).first()
            if not image_record:
                return
            # 更新状态为下载中
            image_record.download_status = 'downloading'
            self.db.commit()
            # 下载图片
            result = await download_and_process_image(
                url=img_info['url'],
                user_id=image_record.user_id,
                article_id=image_record.article_id
            )
            if result['success']:
                # 更新图片信息
                image_record.download_status = 'success'
                image_record.process_status = 'success'
                image_record.local_url = result['local_url']
                image_record.processed_url = result['processed_url']
                image_record.thumbnail_url = result['thumbnail_url']
                image_record.filename = result['filename']
                image_record.file_size = result['file_size']
                image_record.width = result['width']
                image_record.height = result['height']
                image_record.format = result['format']
                image_record.downloaded_at = datetime.utcnow()
                image_record.processed_at = datetime.utcnow()
            else:
                # 下载失败
                image_record.download_status = 'failed'
                image_record.error_message = result['error']
                image_record.retry_count += 1
            image_record.updated_at = datetime.utcnow()
            self.db.commit()
        except Exception as e:
            # 记录错误
            image_record.download_status = 'failed'
            image_record.error_message = str(e)
            image_record.updated_at = datetime.utcnow()
            self.db.commit()
    def _generate_content_hash(self, title: str, content: str) -> str:
        """生成内容哈希"""
        text = f"{title}{content}"
        return hashlib.sha256(text.encode()).hexdigest()
    def _parse_date(self, date_tuple) -> Optional[datetime]:
        """解析日期"""
        if not date_tuple:
            return None
        try:
            # feedparser返回的是9元组
            return datetime(*date_tuple[:6])
        except:
            return None
    def _extract_author(self, soup: BeautifulSoup) -> str:
        """提取作者"""
        # 尝试多种选择器
        selectors = [
            'meta[name="author"]',
            'meta[property="article:author"]',
            'meta[property="author"]',
            '.author',
            '[class*="author"]',
            '[itemprop="author"]'
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                content = element.get('content') or element.text
                if content and len(content) < 100:
                    return content.strip()
        return ''
    def _extract_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """提取日期"""
        # 尝试多种选择器
        selectors = [
            'meta[property="article:published_time"]',
            'meta[name="pubdate"]',
            'meta[property="og:published_time"]',
            'time[datetime]',
            '.publish-date',
            '[class*="date"]'
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                date_str = element.get('content') or element.get('datetime') or element.text
                if date_str:
                    try:
                        # 尝试解析多种日期格式
                        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                            try:
                                return datetime.strptime(date_str[:19], fmt)
                            except:
                                continue
                    except:
                        pass
        return None
    def _log_error(self, source_id: int, error_message: str):
        """记录错误日志"""
        # 这里可以记录到专门的错误日志表
        print(f"RSS源 {source_id} 错误: {error_message}")
#### 2.3.2 ArticleService类（文章服务）
```python
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.sql import text
import json
from models import Article, ArticleContent, RSSSource
from schemas import ArticleFilter, ArticleUpdate, ArticleSearch
from config import settings
from utils.text_processor import extract_keywords, calculate_similarity
from utils.classifier import classify_article, extract_tags
class ArticleService:
    """文章服务类"""
    def __init__(self, db: Session):
        self.db = db
    def get_articles(self, user_id: int, filters: ArticleFilter, 
                    page: int = 1, page    def check_login_limit(self, ip_address: str, username: str) -> Tuple[bool, Dict[str, any]]:
        """
        检查登录限制
        Args:
            ip_address: IP地址
            username: 用户名
        Returns:
            Tuple: (是否允许, 限制信息)
        """
        # IP级别限制（5分钟窗口，5次失败）
        ip_key = f"login:ip:{ip_address}"
        ip_allowed, ip_info = self.check_limit(ip_key, limit=5, window=300)
        if not ip_allowed:
            return False, {
                'type': 'ip_limit',
                'message': 'IP地址被限制登录',
                'retry_after': ip_info.get('retry_after', 300),
                'limit_info': ip_info
            }
        # 用户级别限制（10分钟窗口，3次失败）
        user_key = f"login:user:{username}"
        user_allowed, user_info = self.check_limit(user_key, limit=3, window=600)
        if not user_allowed:
            return False, {
                'type': 'user_limit',
                'message': '用户账户被限制登录',
                'retry_after': user_info.get('retry_after', 600),
                'limit_info': user_info
            }
        return True, {
            'type': 'allowed',
            'ip_info': ip_info,
            'user_info': user_info
        }
### 1.4 API接口详细设计
#### 1.4.1 用户注册接口
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import Optional
import re
from datetime import datetime
from database import get_db
from services.user_service import UserService
from utils.validators import validate_username, validate_password
from utils.security import get_client_info
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])
# 请求模型
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    password: str = Field(..., min_length=12, max_length=128, description="密码")
    : Optional[str] = Field(None, description="")
    @validator('username')
    def validate_username_format(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v
    @validator('password')
    def validate_password_strength(cls, v):
        # 检查密码强度
        if len(v) < 12:
            raise ValueError('密码长度至少12个字符')
        # 检查是否包含4种字符类型
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?`~' for c in v)
        types_count = sum([has_upper, has_lower, has_digit, has_special])
        if types_count < 4:
            raise ValueError('密码必须包含大写字母、小写字母、数字和特殊字符')
        return v
# 响应模型
class RegisterResponse(BaseModel):
    success: bool
    user_id: int
    username: str
    message: str
    timestamp: datetime
@router.post("/register", response_model=RegisterResponse)
async def register(
    request: Request,
    register_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    用户注册
    - **username**: 用户名，3-64字符，只允许字母、数字、下划线
    - **password**: 密码，12-128字符，必须包含4种字符类型
    - ****: （可选）
    """
    try:
        # 获取客户端信息
        client_info = get_client_info(request)
        # 创建用户服务
        user_service = UserService(db)
        # 执行注册
        user = user_service.register(register_data, client_info)
        return RegisterResponse(
            success=True,
            user_id=user.id,
            username=user.username,
            message="注册成功",
            timestamp=datetime.utcnow()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="注册失败")
#### 1.4.2 用户登录接口
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
from database import get_db
from services.user_service import UserService
from services.rate_limiter import RateLimiter
from utils.security import get_client_info
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])
# 请求模型
class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
# 响应模型
class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: int
    user: dict
@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    用户登录
    - **username**: 用户名
    - **password**: 密码
    """
    # 获取客户端信息
    client_info = get_client_info(request)
    ip_address = client_info.get('ip')
    # 检查登录限制
    rate_limiter = RateLimiter()
    allowed, limit_info = rate_limiter.check_login_limit(ip_address, login_data.username)
    if not allowed:
        retry_after = limit_info.get('retry_after', 300)
        raise HTTPException(
            status_code=429,
            detail=limit_info.get('message', '登录限制'),
            headers={"Retry-After": str(retry_after)}
        )
    try:
        # 创建用户服务
        user_service = UserService(db)
        # 执行登录
        result = user_service.login(
            login_data.username,
            login_data.password,
            client_info
        )
        return LoginResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
#### 1.4.3 刷新令牌接口
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
from database import get_db
from services.user_service import UserService
from utils.security import get_client_info
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])
# 请求模型
class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="刷新令牌")
# 响应模型
class RefreshResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    refresh_data: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    刷新访问令牌
    - **refresh_token**: 刷新令牌
    """
    try:
        # 获取客户端信息
        client_info = get_client_info(request)
        # 创建用户服务
        user_service = UserService(db)
        # 执行刷新
        result = user_service.refresh_token(
            refresh_data.refresh_token,
            client_info
        )
        return RefreshResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
#### 1.4.4 修改密码接口
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from datetime import datetime
from database import get_db
from services.user_service import UserService
from middlewares.auth_middleware import AuthMiddleware
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])
# 请求模型
class PasswordChangeRequest(BaseModel):
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=12, max_length=128, description="新密码")
    @validator('new_password')
    def validate_password_strength(cls, v):
        # 检查密码强度
        if len(v) < 12:
            raise ValueError('密码长度至少12个字符')
        # 检查是否包含4种字符类型
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?`~' for c in v)
        types_count = sum([has_upper, has_lower, has_digit, has_special])
        if types_count < 4:
            raise ValueError('密码必须包含大写字母、小写字母、数字和特殊字符')
        return v
# 响应模型
class PasswordChangeResponse(BaseModel):
    success: bool
    message: str
    changed_at: datetime
@router.post("/password", response_model=PasswordChangeResponse)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user = Depends(AuthMiddleware()),
    db: Session = Depends(get_db)
):
    """
    修改密码
    - **old_password**: 旧密码
    - **new_password**: 新密码，12-128字符，必须包含4种字符类型
    """
    try:
        # 创建用户服务
        user_service = UserService(db)
        # 执行密码修改
        success = user_service.change_password(current_user.id, password_data)
        if success:
            return PasswordChangeResponse(
                success=True,
                message="密码修改成功",
                changed_at=datetime.utcnow()
            )
        else:
            raise HTTPException(status_code=400, detail="密码修改失败")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="密码修改失败")
### 1.5 配置详细设计
#### 1.5.1 配置文件结构
```
config/
├── __init__.py
├── settings.py          # 主配置文件
├── database.py          # 数据库配置
├── redis_config.py      # Redis配置
├── security.py          # 安全配置
├── celery_config.py     # Celery配置
└── logging_config.py    # 日志配置
```
#### 1.5.2 主配置文件 (settings.py)
```python
import os
from typing import List
from pydantic import BaseSettings
class Settings(BaseSettings):
    """应用配置"""
    # 应用信息
    APP_NAME: str = "Media Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 9090
    WORKERS: int = 4
    # 数据库配置
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/media_agent"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    DATABASE_POOL_RECYCLE: int = 3600
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = None
    # JWT配置
    ACCESS_TOKEN_SECRET: str = "your-access-token-secret-key-here"
    REFRESH_TOKEN_SECRET: str = "your-refresh-token-secret-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # 密码配置
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_MAX_LENGTH: int = 128
    PASSWORD_HISTORY_COUNT: int = 5
    PASSWORD_EXPIRE_DAYS: int = 90
    # 登录限制配置
    LOGIN_IP_LIMIT: int = 5
    LOGIN_IP_WINDOW: int = 300  # 5分钟
    LOGIN_USER_LIMIT: int = 3
    LOGIN_USER_WINDOW: int = 600  # 10分钟
    USER_LOCK_MINUTES: int = 15
    # 会话配置
    MAX_CONCURRENT_SESSIONS: int = 3
    SESSION_TIMEOUT_MINUTES: int = 30
    # 文件上传配置
    MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024 * 1024  # 2GB
    ALLOWED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".webm", ".mpeg", ".mpg"]
    UPLOAD_CHUNK_SIZE: int = 5 * 1024 * 1024  # 5MB
    # AI配置
    DEEPSEEK_API_KEY: str = "your-deepseek-api-key"
    DEEPSEEK_API_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    # TTS配置
    AZURE_TTS_KEY: str = None
    AZURE_TTS_REGION: str = "eastasia"
    GOOGLE_TTS_KEY: str = None
    # 发布平台配置
    YOUTUBE_API_KEY: str = None
    TIKTOK_API_KEY: str = None
    INSTAGRAM_API_KEY: str = None
    BILIBILI_API_KEY: str = None
    # 监控配置
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9091
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/media_agent.log"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost:8001", "http://104.244.90.202:8001"]
    class Config:
        env_file = ".env"
        case_sensitive = True
settings = Settings()
```
#### 1.5.3 数据库配置 (database.py)
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from config.settings import settings
# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    echo=settings.DEBUG
)
# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# 创建基类
Base = declarative_base()
def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
```
#### 1.5.4 安全配置 (security.py)
```python
import bcrypt
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config.settings import settings
def hash_password(password: str) -> str:
    """哈希密码"""
    salt = bcrypt.gensalt(rounds=12)
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')
def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    try:
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except:
        return False
def generate_token(user_id: int, secret: str, expires_delta: timedelta) -> str:
    """生成JWT令牌"""
    payload = {
        "sub": str(user_id),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + expires_delta,
        "jti": secrets.token_hex(16)
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token
def verify_token(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """验证JWT令牌"""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
def get_client_info(request) -> Dict[str, Any]:
    """获取客户端信息"""
    client_info = {
        "ip": request.client.host if request.client else "0.0.0.0",
        "user_agent": request.headers.get("user-agent", ""),
        "device_fingerprint": request.headers.get("x-device-fingerprint", ""),
    }
    # 解析User-Agent
    user_agent = client_info["user_agent"]
    if  in user_agent:
        client_info["device_type"] = 
    elif "Tablet" in user_agent:
        client_info["device_type"] = "tablet"
    else:
        client_info["device_type"] = "desktop"
    # 简化解析，实际项目可以使用专门的库
    if "Windows" in user_agent:
        client_info["os_name"] = "Windows"
    elif "Mac" in user_agent:
        client_info["os_name"] = "macOS"
    elif "Linux" in user_agent:
        client_info["os_name"] = "Linux"
    elif "Android" in user_agent:
        client_info["os_name"] = "Android"
    elif "iOS" in user_agent:
        client_info["os_name"] = "iOS"
    else:
        client_info["os_name"] = "Unknown"
    if "Chrome" in user_agent:
        client_info["browser_name"] = "Chrome"
    elif "Firefox" in user_agent:
        client_info["browser_name"] = "Firefox"
    elif "Safari" in user_agent:
        client_info["browser_name"] = "Safari"
    elif "Edge" in user_agent:
        client_info["browser_name"] = "Edge"
    else:
        client_info["browser_name"] = "Unknown"
    return client_info
## 2. 资讯抓取模块详细设计
### 2.1 模块概述
资讯抓取模块负责RSS源管理、网页内容抓取、内容解析清洗、去重和质量控制。
### 2.2 数据库表详细设计
#### 2.2.1 rss_sources表（RSS源表）
```sql
CREATE TABLE rss_sources (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 源信息
    url VARCHAR(500) NOT NULL,
    title VARCHAR(255),
    description TEXT,
    feed_type VARCHAR(20) DEFAULT 'rss' CHECK (feed_type IN ('rss', 'atom')),
    language VARCHAR(10),
    copyright TEXT,
    -- 分类标签
    category VARCHAR(50),
    tags TEXT[] DEFAULT '{}',
    -- 抓取配置
    fetch_interval INTEGER DEFAULT 1800,  -- 秒，默认30分钟
    fetch_timeout INTEGER DEFAULT 30,     -- 秒
    max_items_per_fetch INTEGER DEFAULT 50,
    is_active BOOLEAN DEFAULT true,
    -- 抓取状态
    last_fetch_at TIMESTAMP,
    last_success_at TIMESTAMP,
    fetch_status VARCHAR(20) DEFAULT 'idle' CHECK (fetch_status IN ('idle', 'fetching', 'success', 'failed')),
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    -- 质量控制
    quality_score INTEGER DEFAULT 0,
    is_blacklisted BOOLEAN DEFAULT false,
    blacklist_reason TEXT,
    blacklisted_at TIMESTAMP,
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_rss_sources_user_id (user_id),
    INDEX idx_rss_sources_url (url),
    INDEX idx_rss_sources_is_active (is_active),
    INDEX idx_rss_sources_last_fetch_at (last_fetch_at),
    INDEX idx_rss_sources_fetch_status (fetch_status),
    -- 约束
    CONSTRAINT chk_fetch_interval CHECK (fetch_interval >= 300),  -- 最少5分钟
    CONSTRAINT chk_max_items CHECK (max_items_per_fetch BETWEEN 1 AND 1000),
    UNIQUE(user_id, url)
);
COMMENT ON TABLE rss_sources IS 'RSS源表';
COMMENT ON COLUMN rss_sources.fetch_interval IS '抓取间隔（秒），最少300秒（5分钟）';
COMMENT ON COLUMN rss_sources.fetch_status IS '抓取状态：idle(空闲), fetching(抓取中), success(成功), failed(失败)';
COMMENT ON COLUMN rss_sources.quality_score IS '质量评分，0-100分';
```
#### 2.2.2 articles表（文章表）
```sql
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES rss_sources(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 文章信息
    title VARCHAR(500) NOT NULL,
    url VARCHAR(500) NOT NULL,
    guid VARCHAR(500),
    author VARCHAR(100),
    summary TEXT,
    -- 时间信息
    publish_date TIMESTAMP,
    fetch_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 内容信息
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    content_length INTEGER,
    word_count INTEGER,
    image_count INTEGER DEFAULT 0,
    -- 状态信息
    read_status VARCHAR(20) DEFAULT 'unread' CHECK (read_status IN ('unread', 'read', 'archived')),
    favorite BOOLEAN DEFAULT false,
    -- 质量评分
    quality_score INTEGER DEFAULT 0,
    length_score INTEGER DEFAULT 0,
    completeness_score INTEGER DEFAULT 0,
    readability_score INTEGER DEFAULT 0,
    timeliness_score INTEGER DEFAULT 0,
    -- 审核状态
    review_status VARCHAR(20) DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_review')),
    review_notes TEXT,
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER REFERENCES users(id),
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_articles_source_id (source_id),
    INDEX idx_articles_user_id (user_id),
    INDEX idx_articles_publish_date (publish_date),
    INDEX idx_articles_fetch_date (fetch_date),
    INDEX idx_articles_content_hash (content_hash),
    INDEX idx_articles_quality_score (quality_score),
    INDEX idx_articles_review_status (review_status),
    INDEX idx_articles_read_status (read_status),
    -- 约束
    CONSTRAINT chk_quality_score CHECK (quality_score BETWEEN 0 AND 100),
    UNIQUE(source_id, guid),
    UNIQUE(source_id, url)
);
COMMENT ON TABLE articles IS '文章表';
COMMENT ON COLUMN articles.content_hash IS '内容哈希值，用于去重';
COMMENT ON COLUMN articles.quality_score IS '综合质量评分，0-100分';
COMMENT ON COLUMN articles.review_status IS '审核状态：pending(待审核), approved(通过), rejected(拒绝), needs_review(需要人工审核)';
```
#### 2.2.3 article_content表（文章内容表）
```sql
CREATE TABLE article_content (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    -- 原始内容
    raw_content TEXT,
    raw_html TEXT,
    -- 清洗后内容
    clean_content TEXT,
    clean_html TEXT,
    -- 提取信息
    extracted_text TEXT,
    extracted_summary TEXT,
    keywords TEXT[] DEFAULT '{}',
    entities JSONB DEFAULT '{}',
    -- 媒体信息
    images JSONB DEFAULT '[]',
    videos JSONB DEFAULT '[]',
    audios JSONB DEFAULT '[]',
    -- 元数据
    metadata JSONB DEFAULT '{}',
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_article_content_article_id (article_id),
    -- 约束
    UNIQUE(article_id)
);
COMMENT ON TABLE article_content IS '文章内容表';
COMMENT ON COLUMN article_content.clean_content IS '清洗后的纯文本内容';
COMMENT ON COLUMN article_content.images IS '图片信息JSON数组';
```
#### 2.2.4 article_images表（文章图片表）
```sql
CREATE TABLE article_images (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    -- 图片信息
    url VARCHAR(500) NOT NULL,
    alt_text VARCHAR(500),
    caption TEXT,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    format VARCHAR(10),
    -- 下载状态
    download_status VARCHAR(20) DEFAULT 'pending' CHECK (download_status IN ('pending', 'downloading', 'downloaded', 'failed')),
    local_path VARCHAR(500),
    downloaded_at TIMESTAMP,
    -- 处理状态
    processed BOOLEAN DEFAULT false,
    thumbnail_path VARCHAR(500),
    optimized_path VARCHAR(500),
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_article_images_article_id (article_id),
    INDEX idx_article_images_download_status (download_status),
    -- 约束
    UNIQUE(article_id, url)
);
COMMENT ON TABLE article_images IS '文章图片表';
COMMENT ON COLUMN article_images.download_status IS '下载状态：pending(待下载), downloading(下载中), downloaded(已下载), failed(失败)';
```
### 2.3 核心类详细设计
#### 2.3.1 RSSFetcher类（RSS抓取器）
```python
import asyncio
import aiohttp
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import hashlib
import re
from urllib.parse import urlparse
from models import RSSSource, Article, ArticleContent
from utils.html_cleaner import HTMLCleaner
from utils.content_scorer import ContentScorer
from config.settings import settings
class RSSFetcher:
    """RSS抓取器"""
    def __init__(self, db: Session):
        self.db = db
        self.session_timeout = aiohttp.ClientTimeout(total=30)
        self.html_cleaner = HTMLCleaner()
        self.content_scorer = ContentScorer()
    async def fetch_source(self, source_id: int) -> Dict[str, Any]:
        """
        抓取单个RSS源
        Args:
            source_id: RSS源ID
        Returns:
            Dict: 抓取结果
        """
        # 获取RSS源
        source = self.db.query(RSSSource).filter(RSSSource.id == source_id).first()
        if not source:
            return {'success': False, 'error': 'RSS源不存在'}
        # 更新抓取状态
        source.fetch_status = 'fetching'
        source.last_fetch_at = datetime.utcnow()
        self.db.commit()
        try:
            # 抓取RSS内容
            async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
                async with session.get(source.url) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP错误: {response.status}")
                    content = await response.text()
            # 解析RSS
            feed = feedparser.parse(content)
            if not feed.entries:
                raise Exception("RSS源没有内容")
            # 处理条目
            new_articles = 0
            for entry in feed.entries[:source.max_items_per_fetch]:
                try:
                    await self._process_entry(source, entry)
                    new_articles += 1
                except Exception as e:
                    # 记录错误，继续处理其他条目
                    print(f"处理条目失败: {e}")
                    continue
            # 更新源状态
            source.fetch_status = 'success'
            source.last_success_at = datetime.utcnow()
            source.error_count = 0
            source.last_error = None
            self.db.commit()
            return {
                'success': True,
                'source_id': source_id,
                'new_articles': new_articles,
                'total_entries': len(feed.entries)
            }
        except Exception as e:
            # 更新错误状态
            source.fetch_status = 'failed'
            source.error_count += 1
            source.last_error = str(e)
            self.db.commit()
            # 检查是否需要加入黑名单
            if source.error_count >= 10:
                source.is_blacklisted = True
                source.blacklist_reason = f"连续{source.error_count}次抓取失败"
                source.blacklisted_at = datetime.utcnow()
                self.db.commit()
            return {
                'success': False,
                'source_id': source_id,
                'error': str(e)
            }
    async def _process_entry(self, source: RSSSource, entry: Dict[str, Any]):
        """处理RSS条目"""
        # 提取文章信息
        title = entry.get('title', '无标题')
        url = entry.get('link', '')
        guid = entry.get('id', url)
        author = entry.get('author', '')
        summary = entry.get('summary', '')
        # 解析发布时间
        publish_date = None
        if hasattr(entry, 'published_parsed'):
            publish_date = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed'):
            publish_date = datetime(*entry.updated_parsed[:6])
        # 计算内容哈希（用于去重）
        content_for_hash = f"{title}:{summary}"
        content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
        # 检查是否已存在
        existing = self.db.query(Article).filter(
            Article.content_hash == content_hash
        ).first()
        if existing:
            # 文章已存在，跳过
            return
        # 抓取文章内容
        content_data = await self._fetch_article_content(url)
        # 计算质量评分
        scores = self.content_scorer.score_article(
            title=title,
            content=content_data['clean_text'],
            publish_date=publish_date,
            image_count=len(content_data['images'])
        )
        # 创建文章记录
        article = Article(
            source_id=source.id,
            user_id=source.user_id,
            title=title,
            url=url,
            guid=guid,
            author=author,
            summary=summary,
            publish_date=publish_date,
            fetch_date=datetime.utcnow(),
            content_hash=content_hash,
            content_length=len(content_data['clean_text']),
            word_count=len(content_data['clean_text'].split()),
            image_count=len(content_data['images']),
            quality_score=scores['total'],
            length_score=scores['length'],
            completeness_score=scores['completeness'],
            readability_score=scores['readability'],
            timeliness_score=scores['timeliness'],
            review_status='needs_review' if scores['total'] < 60 else 'pending',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(article)
        self.db.flush()  # 获取article.id
        # 创建内容记录
        content = ArticleContent(
            article_id=article.id,
            raw_content=content_data['raw_html'],
            clean_content=content_data['clean_text'],
            clean_html=content_data['clean_html'],
            extracted_text=content_data['clean_text'],
            extracted_summary=content_data['summary'],
            keywords=content_data['keywords'],
            images=content_data['images'],
            metadata=content_data['metadata'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(content)
        self.db.commit()
    async def _fetch_article_content(self, url: str) -> Dict[str, Any]:
        """抓取文章内容"""
        try:
            async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return self._get_empty_content()
                    html = await response.text()
            # 清洗HTML
            cleaned = self.html_cleaner.clean(html)
            # 提取信息
            images = self._extract_images(cleaned['html'])
            keywords = self._extract_keywords(cleaned['text'])
            return {
                'raw_html': html,
                'clean_html': cleaned['html'],
                'clean_text': cleaned['text'],
                'summary': cleaned['text'][:500],  # 前500字符作为摘要
                'keywords': keywords,
                'images': images,
                'metadata': {
                    'url': url,
                    'charset': cleaned.get('charset', 'utf-8'),
                    'language': cleaned.get('language', 'zh'),
                    'title': cleaned.get('title', '')
                }
            }
        except Exception as e:
            print(f"抓取文章内容失败: {e}")
            return self._get_empty_content()
    def _extract_images(self, html: str) -> List[Dict[str, Any]]:
        """提取图片信息"""
        images = []
        # 简化实现，实际项目可以使用BeautifulSoup
        img_pattern = r'<img[^>]+src="([^"]+)"[^>]*>'
        import re
        matches = re.findall(img_pattern, html)
        for i, src in enumerate(matches[:5]):  # 最多提取5张图片
            images.append({
                'url': src,
                'alt_text': '',
                'caption': '',
                'index': i
            })
        return images
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简化实现，实际项目可以使用jieba等分词库
        words = text.split()
        # 取前10个非停用词作为关键词
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        keywords = [word for word in words if word not in stopwords][:10]
        return keywords
    def _get_empty_content(self) -> Dict[str, Any]:
        """获取空内容"""
        return {
            'raw_html': '',
            'clean_html': '',
            'clean_text': '',
            'summary': '',
            'keywords': [],
            'images': [],
            'metadata': {}
        }
#### 2.3.2 ContentScorer类（内容评分器）
```python
from datetime import datetime
from typing import Dict, Any
import re
class ContentScorer:
    """内容评分器"""
    def score_article(self, title: str, content: str, publish_date: datetime = None, 
                     image_count: int = 0) -> Dict[str, int]:
        """
        评分文章
        Args:
            title: 标题
            content: 内容
            publish_date: 发布时间
            image_count: 图片数量
        Returns:
            Dict: 各项评分
        """
        # 长度评分（30%）
        length_score = self._score_length(content)
        # 完整性评分（30%）
        completeness_score = self._score_completeness(title, content, image_count)
        # 可读性评分（20%）
        readability_score = self._score_readability(content)
        # 时效性评分（20%）
        timeliness_score = self._score_timeliness(publish_date)
        # 综合评分
        total_score = int(
            length_score * 0.3 +
            completeness_score * 0.3 +
            readability_score * 0.2 +
            timeliness_score * 0.2
        )
        return {
            'total': total_score,
            'length': length_score,
            'completeness': completeness_score,
            'readability': readability_score,
            'timeliness': timeliness_score
        }
    def _score_length(self, content: str) -> int:
        """长度评分"""
        length = len(content)
        if length >= 2000:
            return 100
        elif length >= 1000:
            return 80
        elif length >= 500:
            return 60
        elif length >= 200:
            return 40
        else:
            return 20
    def _score_completeness(self, title: str, content: str, image_count: int) -> int:
        """完整性评分"""
        score = 0
        # 标题（20分）
        if title and len(title) >= 5:
            score += 20
        # 内容（50分）
        if content and len(content) >= 200:
            score += 50
        # 图片（30分）
        if image_count >= 3:
            score += 30
        elif image_count >= 1:
            score += 20
        else:
            score += 10
        return min(score, 100)
    def _score_readability(self, content: str) -> int:
        """可读性评分"""
        if not content:
            return 0
        # 计算平均句子长度
        sentences = re.split(r'[。！？!?]', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return 50
        avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
        # 根据平均句子长度评分
        if avg_sentence_length <= 20:
            return 90  # 句子简短，易读
        elif avg_sentence_length <= 40:
            return 70  # 句子适中
        elif avg_sentence_length <= 60:
            return 50  # 句子较长
        else:
            return 30  # 句子过长
    def _score_timeliness(self, publish_date: datetime) -> int:
        """时效性评分"""
        if not publish_date:
            return 50
        now = datetime.utcnow()
        delta = now - publish_date
        # 根据发布时间距离现在的时间评分
        if delta.days == 0:
            return 100  # 今天发布
        elif delta.days <= 1:
            return 90   # 昨天发布
        elif delta.days <= 3:
            return 80   # 3天内
        elif delta.days <= 7:
            return 60   # 一周内
        elif delta.days <= 30:
            return 40   # 一个月内
        else:
            return 20   # 超过一个月
## 3. 任务队列模块详细设计
### 3.1 模块概述
任务队列模块负责异步任务的处理，包括任务调度、执行、监控和管理。
### 3.2 Celery配置详细设计
#### 3.2.1 celery_config.py
```python
from celery import Celery
from kombu import Queue, Exchange
from datetime import timedelta
from config.settings import settings
def make_celery():
    """创建Celery应用"""
    celery = Celery(
        'media_agent',
        broker=f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}',
        backend=f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB + 1}',
        include=[
            'tasks.auth_tasks',
            'tasks.rss_tasks',
            'tasks.video_tasks',
            'tasks.ai_tasks',
            'tasks.publish_tasks'
        ]
    )
    # 配置
    celery.conf.update(
        # 基础配置
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        timezone='Asia/Shanghai',
        enable_utc=True,
        # 任务路由
        task_routes={
            'tasks.high_priority.*': {'queue': 'high_priority'},
            'tasks.normal_priority.*': {'queue': 'normal_priority'},
            'tasks.low_priority.*': {'queue': 'low_priority'},
        },
        # 队列配置
        task_queues=(
            Queue('high_priority', Exchange('high_priority'), routing_key='high_priority'),
            Queue('normal_priority', Exchange('normal_priority'), routing_key='normal_priority'),
            Queue('low_priority', Exchange('low_priority'), routing_key='low_priority'),
        ),
        # 任务执行配置
        task_time_limit=3600,  # 1小时
        task_soft_time_limit=3000,  # 50分钟
        worker_max_tasks_per_child=100,
        worker_prefetch_multiplier=1,
        # 结果配置
        result_expires=86400,  # 24小时
        result_backend_max_retries=3,
        # 监控配置
        worker_send_task_events=True,
        task_send_sent_event=True,
        # 重试配置
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
    )
    return celery
celery_app = make_celery()
# 定时任务配置
celery_app.conf.beat_schedule = {
    # RSS抓取任务（每30分钟）
    'fetch-rss-sources': {
        'task': 'tasks.rss_tasks.fetch_all_sources',
        'schedule': timedelta(minutes=30),
        'options': {'queue': 'normal_priority'}
    },
    # 清理过期会话（每小时）
    'clean-expired-sessions': {
        'task': 'tasks.auth_tasks.clean_expired_sessions',
        'schedule': timedelta(hours=1),
        'options': {'queue': 'low_priority'}
    },
    # 清理临时文件（每天）
    'clean-temp-files': {
        'task': 'tasks.video_tasks.clean_temp_files',
        'schedule': timedelta(days=1),
        'options': {'queue': 'low_priority'}
    },
    # 生成每日统计（每天凌晨2点）
    'generate-daily-stats': {
        'task': 'tasks.system_tasks.generate_daily_stats',
        'schedule': timedelta(days=1),
        'options': {'queue': 'low_priority'}
    },
}
```
#### 3.2.2 任务优先级定义
```python
# 任务优先级常量
class TaskPriority:
    """任务优先级"""
    HIGH = 0      # 高优先级：用户直接操作，实时性要求高
    NORMAL = 1    # 普通优先级：定时任务，批量处理
    LOW = 2       # 低优先级：后台清理，数据统计
    # 等待时间要求（根据服务器处理能力百分比）
    WAIT_TIME_LIMITS = {
        HIGH: 0.10,   # 不超过服务器处理能力的10%
        NORMAL: 0.30, # 不超过服务器处理能力的30%
        LOW: 0.50     # 不超过服务器处理能力的50%
    }
```
### 3.3 核心任务类详细设计
#### 3.3.1 BaseTask类（基础任务）
```python
from celery import Task
from typing import Dict, Any, Optional
import time
import traceback
from datetime import datetime
from sqlalchemy.orm import Session
import redis
from database import SessionLocal
from config.settings import settings
class BaseTask(Task):
    """基础任务类"""
    _db: Optional[Session] = None
    _redis: Optional[redis.Redis] = None
    @property
    def db(self) -> Session:
        """获取数据库会话"""
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    @property
    def redis(self) -> redis.Redis:
        """获取Redis连接"""
        if self._redis is None:
            self._redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
        return self._redis
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """任务返回后清理"""
        if self._db:
            self._db.close()
            self._db = None
        if self._redis:
            self._redis.close()
            self._redis = None
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败处理"""
        error_msg = f"任务失败: {exc}\n{traceback.format_exc()}"
        self._log_error(task_id, error_msg)
        # 更新任务状态
        self._update_task_status(task_id, 'failed', error_msg)
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功处理"""
        self._update_task_status(task_id, 'success', retval)
    def _log_error(self, task_id: str, error_msg: str):
        """记录错误日志"""
        log_entry = {
            'task_id': task_id,
            'timestamp': datetime.utcnow().isoformat(),
            'level': 'ERROR',
            'message': error_msg
        }
        # 记录到Redis
        self.redis.lpush('task_errors', str(log_entry))
        # 限制错误日志数量
        self.redis.ltrim('task_errors', 0, 999)
    def _update_task_status(self, task_id: str, status: str, result: Any):
        """更新任务状态"""
        status_key = f"task_status:{task_id}"
        self.redis.hset(status_key, mapping={
            'status': status,
            'result': str(result),
            'updated_at': datetime.utcnow().isoformat()
        })
        # 设置过期时间（24小时）
        self.redis.expire(status_key, 86400)
    def update_progress(self, task_id: str, progress: int, message: str = ''):
        """更新任务进度"""
        progress_key = f"task_progress:{task_id}"
        self.redis.hset(progress_key, mapping={
            'progress': progress,
            'message': message,
            'updated_at': datetime.utcnow().isoformat()
        })
        # 设置过期时间（24小时）
        self.redis.expire(progress_key, 86400)
#### 3.3.2 RSS抓取任务
```python
from celery import shared_task
from typing import List, Dict, Any
from datetime import datetime
import asyncio
from tasks.base_task import BaseTask
from services.rss_fetcher import RSSFetcher
@shared_task(base=BaseTask, bind=True)
def fetch_rss_source(self, source_id: int) -> Dict[str, Any]:
    """
    抓取单个RSS源
    Args:
        source_id: RSS源ID
    Returns:
        Dict: 抓取结果
    """
    # 更新进度
    self.update_progress(self.request.id, 10, '开始抓取RSS源')
    try:
        # 创建抓取器
        fetcher = RSSFetcher(self.db)
        # 执行抓取（异步转同步）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.update_progress(self.request.id, 30, '正在抓取RSS内容')
        result = loop.run_until_complete(fetcher.fetch_source(source_id))
        loop.close()
        self.update_progress(self.request.id, 90, '抓取完成')
        return {
            'success': True,
            'task_id': self.request.id,
            'source_id': source_id,
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            'success': False,
            'task_id': self.request.id,
            'source_id': source_id,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
@shared_task(base=BaseTask, bind=True)
def fetch_all_sources(self) -> Dict[str, Any]:
    """
    抓取所有活跃的RSS源
    Returns:
        Dict: 批量抓取结果
    """
    from models import RSSSource
    # 获取所有活跃的RSS源
    sources = self.db.query(RSSSource).filter(
        RSSSource.is_active == True,
        RSSSource.is_blacklisted == False
    ).all()
    total = len(sources)
    success = 0
    failed = 0
    results = []
    self.update_progress(self.request.id, 0, f'开始批量抓取{total}个RSS源')
    for i, source in enumerate(sources):
        try:
            # 检查是否需要抓取（基于抓取间隔）
            if source.last_fetch_at:
                time_since_last = datetime.utcnow() - source.last_fetch_at
                if time_since_last.total_seconds() < source.fetch_interval:
                    continue
            # 执行抓取
            result = fetch_rss_source.delay(source.id)
            results.append({
                'source_id': source.id,
                'task_id': result.id,
                'status': 'queued'
            })
            success += 1
        except Exception as e:
            results.append({
                'source_id': source.id,
                'error': str(e),
                'status': 'failed'
            })
            failed += 1
        # 更新进度
        progress = int((i + 1) / total * 100)
        self.update_progress(self.request.id, progress, f'已提交{success}个任务，失败{failed}个')
    return {
        'success': True,
        'task_id': self.request.id,
        'total_sources': total,
        'submitted': success,
        'failed': failed,
        'results': results,
        'timestamp': datetime.utcnow().isoformat()
    }
#### 3.3.3 视频处理任务
```python
from celery import shared_task
from typing import Dict, Any
import os
import subprocess
from pathlib import Path
from datetime import datetime
from tasks.base_task import BaseTask
from models import Video, VideoProcessingTask
from config.settings import settings
@shared_task(base=BaseTask, bind=True)
def process_video(self, video_id: int, task_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理视频
    Args:
        video_id: 视频ID
        task_type: 任务类型（convert, resize, watermark等）
        parameters: 处理参数
    Returns:
        Dict: 处理结果
    """
    # 获取视频信息
    video = self.db.query(Video).filter(Video.id == video_id).first()
    if not video:
        return {
            'success': False,
            'error': '视频不存在',
            'video_id': video_id
        }
    # 创建处理任务记录
    task_record = VideoProcessingTask(
        video_id=video_id,
        task_type=task_type,
        parameters=parameters,
        status='processing',
        progress=0,
        started_at=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    self.db.add(task_record)
    self.db.commit()
    try:
        # 根据任务类型执行处理
        if task_type == 'convert':
            result = self._convert_video(video, parameters, task_record.id)
        elif task_type == 'resize':
            result = self._resize_video(video, parameters, task_record.id)
        elif task_type == 'watermark':
            result = self._add_watermark(video, parameters, task_record.id)
        else:
            raise ValueError(f"不支持的任务类型: {task_type}")
        # 更新任务状态
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result_url = result.get('output_path')
        task_record.completed_at = datetime.utcnow()
        self.db.commit()
        return {
            'success': True,
            'task_id': self.request.id,
            'video_id': video_id,
            'task_record_id': task_record.id,
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        # 更新失败状态
        task_record.status = 'failed'
        task_record.error_message = str(e)
        task_record.completed_at = datetime.utcnow()
        self.db.commit()
        return {
            'success': False,
            'task_id': self.request.id,
            'video_id': video_id,
            'task_record_id': task_record.id,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
    def _convert_video(self, video: Video, parameters: Dict[str, Any], task_id: int) -> Dict[str, Any]:
        """转换视频格式"""
        input_path = video.storage_path
        output_format = parameters.get('format', 'mp4')
        quality = parameters.get('quality', 'balanced')
        # 生成输出路径
        output_filename = f"{Path(input_path).stem}.{output_format}"
        output_dir = Path(settings.VIDEO_PROCESSING_DIR) / str(video.user_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        # FFmpeg参数
        if quality == 'high':
            ffmpeg_cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264', '-crf', '18',
                '-c:a', 'aac', '-b:a', '128k',
                '-movflags', '+faststart',
                output_path
            ]
        elif quality == 'balanced':
            ffmpeg_cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264', '-crf', '23',
                '-c:a', 'aac', '-b:a', '96k',
                '-movflags', '+faststart',
                output_path
            ]
        else:  # fast
            ffmpeg_cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264', '-crf', '28',
                '-c:a', 'aac', '-b:a', '64k',
                '-movflags', '+faststart',
                output_path
            ]
        # 执行转换
        self.update_progress(self.request.id, 20, '开始视频转换')
        try:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            # 监控进度（简化实现）
            for i in range(20, 100, 10):
                time.sleep(1)  # 模拟进度更新
                self.update_progress(self.request.id, i, '转换中...')
            process.wait()
            if process.returncode != 0:
                raise Exception(f"FFmpeg转换失败: {process.stderr.read()}")
            self.update_progress(self.request.id, 100, '转换完成')
            return {
                'output_path': output_path,
                'format': output_format,
                'quality': quality,
                'success': True
            }
        except Exception as e:
            raise Exception(f"视频转换失败: {e}")
    def _resize_video(self, video: Video, parameters: Dict[str, Any], task_id: int) -> Dict[str, Any]:
        """调整视频分辨率"""
        # 实现类似_convert_video，使用FFmpeg调整分辨率
        pass
    def _add_watermark(self, video: Video, parameters: Dict[str, Any], task_id: int) -> Dict[str, Any]:
        """添加水印"""
        # 实现类似_convert_video，使用FFmpeg添加水印
        pass
#### 3.3.4 AI生成任务
```python
from celery import shared_task
from typing import Dict, Any
import requests
from datetime import datetime
from tasks.base_task import BaseTask
from models import GenerationTask, GenerationResult
from config.settings import settings
@shared_task(base=BaseTask, bind=True)
def generate_text(self, task_id: int) -> Dict[str, Any]:
    """
    生成文案
    Args:
        task_id: 生成任务ID
    Returns:
        Dict: 生成结果
    """
    # 获取生成任务
    task = self.db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
    if not task:
        return {
            'success': False,
            'error': '生成任务不存在',
            'task_id': task_id
        }
    # 更新任务状态
    task.status = 'processing'
    task.started_at = datetime.utcnow()
    self.db.commit()
    try:
        self.update_progress(self.request.id, 10, '准备生成文案')
        # 调用DeepSeek API
        input_data = task.input_data
        parameters = task.parameters or {}
        # 构建请求
        prompt = self._build_prompt(input_data, parameters)
        self.update_progress(self.request.id, 30, '调用AI模型')
        response = requests.post(
            f"{settings.DEEPSEEK_API_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": parameters.get('model', settings.DEEPSEEK_MODEL),
                "messages": [
                    {"role": "system", "content": "你是一个专业的文案生成助手。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": parameters.get('temperature', 0.7),
                "max_tokens": parameters.get('max_tokens', 1000),
                "top_p": parameters.get('top_p', 0.9)
            },
            timeout=30
        )
        if response.status_code != 200:
            raise Exception(f"API调用失败: {response.status_code} - {response.text}")
        result_data = response.json()
        generated_text = result_data['choices'][0]['message']['content']
        self.update_progress(self.request.id, 80, '处理生成结果')
        # 创建生成结果记录
        result = GenerationResult(
            task_id=task_id,
            content_type='text',
            content_url=None,
            content_metadata={
                'text': generated_text,
                'model': parameters.get('model', settings.DEEPSEEK_MODEL),
                'length': len(generated_text),
                'tokens': result_data.get('usage', {}).get('total_tokens', 0)
            },
            quality_score=self._score_generated_text(generated_text),
            created_at=datetime.utcnow()
        )
        self.db.add(result)
        # 更新任务状态
        task.status = 'completed'
        task.progress = 100
        task.result_data = {
            'generated_text': generated_text,
            'api_response': result_data
        }
        task.completed_at = datetime.utcnow()
        self.db.commit()
        self.update_progress(self.request.id, 100, '生成完成')
        return {
            'success': True,
            'task_id': self.request.id,
            'generation_task_id': task_id,
            'result_id': result.id,
            'generated_text': generated_text,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        # 更新失败状态
        task.status = 'failed'
        task.error_message = str(e)
        task.completed_at = datetime.utcnow()
        self.db.commit()
        return {
            'success': False,
            'task_id': self.request.id,
            'generation_task_id': task_id,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
    def _build_prompt(self, input_data: Dict[str, Any], parameters: Dict[str, Any]) -> str:
        """构建提示词"""
        template_type = parameters.get('template_type', 'news_summary')
        style = parameters.get('style', 'formal')
        length = parameters.get('length', 'medium')
        # 根据模板类型构建提示词
        if template_type == 'news_summary':
            prompt = f"请将以下新闻内容总结为{length}长度的文案，使用{style}风格：\n\n{input_data.get('content', '')}"
        elif template_type == 'product_intro':
            prompt = f"请为以下产品生成介绍文案，使用{style}风格，长度{length}：\n\n产品：{input_data.get('product_name', '')}\n特点：{input_data.get('features', '')}"
        else:
            prompt = f"请根据以下内容生成文案，使用{style}风格，长度{length}：\n\n{input_data.get('content', '')}"
        return prompt
    def _score_generated_text(self, text: str) -> int:
        """评分生成的文案"""
        if not text:
            return 0
        length = len(text)
        sentences = text.count('。') + text.count('！') + text.count('？')
        # 简单评分逻辑
        score = 50  # 基础分
        # 长度加分
        if length >= 500:
            score += 20
        elif length >= 200:
            score += 10
        # 句子结构加分
        if sentences >= 5:
            score += 15
        elif sentences >= 3:
            score += 10
        # 多样性加分（检查重复词）
        words = text.split()
        unique_words = set(words)
        if len(unique_words) / len(words) > 0.7:
            score += 15
        return min(score, 100)
@shared_task(base=BaseTask, bind=True)
def generate_voice(self, task_id: int) -> Dict[str, Any]:
    """生成语音"""
    # 实现类似generate_text，调用TTS服务
    pass
@shared_task(base=BaseTask, bind=True)
def generate_video(self, task_id: int) -> Dict[str, Any]:
    """生成视频"""
    # 实现类似generate_text，结合文案、语音、图片生成视频
    pass
### 3.4 任务监控和管理
#### 3.4.1 任务监控服务
```python
from typing import Dict, Any, List
from datetime import datetime, timedelta
import redis
import json
from config.settings import settings
class TaskMonitor:
    """任务监控服务"""
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        status_key = f"task_status:{task_id}"
        progress_key = f"task_progress:{task_id}"
        status = self.redis.hgetall(status_key)
        progress = self.redis.hgetall(progress_key)
        return {
            'task_id': task_id,
            'status': status.get('status', 'unknown'),
            'result': status.get('result'),
            'progress': int(progress.get('progress', 0)) if progress else 0,
            'message': progress.get('message', ''),
            'updated_at': progress.get('updated_at') or status.get('updated_at')
        }
    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        # 获取各队列长度
        high_queue_len = self.redis.llen('celery')
        normal_queue_len = self.redis.llen('celery:normal_priority')
        low_queue_len = self.redis.llen('celery:low_priority')
        # 获取活跃worker数量
        worker_keys = self.redis.keys('celery@*')
        active_workers = len(worker_keys)
        # 计算队列积压等级
        total_backlog = high_queue_len + normal_queue_len + low_queue_len
        backlog_level = 'normal'
        if total_backlog > 200:
            backlog_level = 'severe'
        elif total_backlog > 50:
            backlog_level = 'moderate'
        return {
            'queues': {
                'high_priority': high_queue_len,
                'normal_priority': normal_queue_len,
                'low_priority': low_queue_len
            },
            'total_backlog': total_backlog,
            'backlog_level': backlog_level,
            'active_workers': active_workers,
            'timestamp': datetime.utcnow().isoformat()
        }
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近错误"""
        errors = self.redis.lrange('task_errors', 0, limit - 1)
        return [json.loads(error) for error in errors]
    def cleanup_old_tasks(self, days: int = 7):
        """清理旧任务数据"""
        # 清理过期的状态和进度数据
        pattern = "task_*:*"
        keys = self.redis.keys(pattern)
        for key in keys:
            # 检查最后更新时间
            last_update = self.redis.hget(key, 'updated_at')
            if last_update:
                try:
                    update_time = datetime.fromisoformat(last_update)
                    if datetime.utcnow() - update_time > timedelta(days=days):
                        self.redis.delete(key)
                except:
                    pass
#### 3.4.2 任务管理API
```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from celery.result import AsyncResult
from tasks.celery_app import celery_app
from services.task_monitor import TaskMonitor
router = APIRouter(prefix="/api/v1/tasks", tags=["任务管理"])
@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    获取任务状态
    - **task_id**: 任务ID
    """
    monitor = TaskMonitor()
    status = monitor.get_task_status(task_id)
    if status['status'] == 'unknown':
        # 尝试从Celery获取
        result = AsyncResult(task_id, app=celery_app)
        if result.state:
            status['status'] = result.state
            status['result'] = str(result.result) if result.result else None
    return status
@router.get("/queue/stats")
async def get_queue_stats():
    """获取队列统计"""
    monitor = TaskMonitor()
    return monitor.get_queue_stats()
@router.get("/errors")
async def get_recent_errors(limit: int = 50):
    """
    获取最近错误
    - **limit**: 返回错误数量，默认50
    """
    monitor = TaskMonitor()
    return monitor.get_recent_errors(limit)
@router.post("/cleanup")
async def cleanup_tasks(days: int = 7):
    """
    清理旧任务数据
    - **days**: 清理多少天前的数据，默认7天
    """
    monitor = TaskMonitor()
    monitor.cleanup_old_tasks(days)
    return {
        'success': True,
        'message': f'已清理{days}天前的任务数据',
        'timestamp': datetime.utcnow().isoformat()
    }
## 4. 性能监控详细设计
### 4.1 监控指标定义
#### 4.1.1 系统级指标
```python
# 系统监控指标
SYSTEM_METRICS = {
    'cpu_usage': {
        'name': 'CPU使用率',
        'unit': 'percent',
        'description': '系统CPU使用率',
        'warning_threshold': 80,
        'critical_threshold': 90
    },
    'memory_usage': {
        'name': '内存使用率',
        'unit': 'percent',
        'description': '系统内存使用率',
        'warning_threshold': 85,
        'critical_threshold': 95
    },
    'disk_usage': {
        'name': '磁盘使用率',
        'unit': 'percent',
        'description': '系统磁盘使用率',
        'warning_threshold': 80,
        'critical_threshold': 90
    },
    'network_io': {
        'name': '网络IO',
        'unit': 'bytes/sec',
        'description': '网络输入输出速率',
        'warning_threshold': None,  # 根据网络带宽动态确定
        'critical_threshold': None
    }
}
#### 4.1.2 应用级指标
```python
# 应用监控指标
APPLICATION_METRICS = {
    'api_response_time': {
        'name': 'API响应时间',
        'unit': 'milliseconds',
        'description': 'API接口平均响应时间',
        'warning_threshold': None,  # 根据服务器性能动态确定
        'critical_threshold': None
    },
    'api_error_rate': {
        'name': 'API错误率',
        'unit': 'percent',
        'description': 'API接口错误率',
        'warning_threshold': 5,
        'critical_threshold': 10
    },
    'database_connections': {
        'name': '数据库连接数',
        'unit': 'count',
        'description': '活跃数据库连接数',
        'warning_threshold': 30,
        'critical_threshold': 40
    },
    'redis_connections': {
        'name': 'Redis连接数',
        'unit': 'count',
        'description': '活跃Redis连接数',
        'warning_threshold': 50,
        'critical_threshold': 100
    },
    'task_queue_backlog': {
        'name': '任务队列积压',
        'unit': 'count',
        'description': '任务队列等待任务数',
        'warning_threshold': 50,
        'critical_threshold': 200
    },
    'task_completion_rate': {
        'name': '任务完成率',
        'unit': 'percent',
        'description': '任务成功完成率',
        'warning_threshold': 95,
        'critical_threshold': 90
    }
}
#### 4.1.3 业务级指标
```python
# 业务监控指标
BUSINESS_METRICS = {
    'active_users': {
        'name': '活跃用户数',
        'unit': 'count',
        'description': '24小时内活跃用户数',
        'warning_threshold': None,
        'critical_threshold': None
    },
    'new_registrations': {
        'name': '新注册用户',
        'unit': 'count',
        'description': '24小时内新注册用户数',
        'warning_threshold': None,
        'critical_threshold': None
    },
    'rss_fetch_success_rate': {
        'name': 'RSS抓取成功率',
        'unit': 'percent',
        'description': 'RSS源抓取成功率',
        'warning_threshold': 90,
        'critical_threshold': 80
    },
    'video_processing_success_rate': {
        'name': '视频处理成功率',
        'unit': 'percent',
        'description': '视频处理任务成功率',
        'warning_threshold': 95,
        'critical_threshold': 90
    },
    'ai_generation_success_rate': {
        'name': 'AI生成成功率',
        'unit': 'percent',
        'description': 'AI内容生成成功率',
        'warning_threshold': 95,
        'critical_threshold': 90
    },
    'publish_success_rate': {
        'name': '发布成功率',
        'unit': 'percent',
        'description': '内容发布成功率',
        'warning_threshold': 95,
        'critical_threshold': 90
    }
}
### 4.2 监控服务实现
#### 4.2.1 监控数据收集器
```python
import psutil
import time
from datetime import datetime
from typing import Dict, Any
import redis
import json
from config.settings import settings
class MetricsCollector:
    """监控数据收集器"""
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB + 2,  # 使用不同的DB
            decode_responses=True
        )
    def collect_system_metrics(self) -> Dict[str, Any]:
        """收集系统指标"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        # 内存使用率
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        # 磁盘使用率
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        # 网络IO
        net_io = psutil.net_io_counters()
        net_io_bytes = net_io.bytes_sent + net_io.bytes_recv
        metrics = {
            'cpu_usage': cpu_percent,
            'memory_usage': memory_percent,
            'disk_usage': disk_percent,
            'network_io': net_io_bytes,
            'timestamp': datetime.utcnow().isoformat()
        }
        # 存储到Redis
        self._store_metrics('system', metrics)
        return metrics
    def collect_application_metrics(self) -> Dict[str, Any]:
        """收集应用指标"""
        # 这里需要实现具体的应用指标收集逻辑
        # 例如：从数据库统计API调用，从Redis获取任务队列状态等
        metrics = {
            'timestamp': datetime.utcnow().isoformat()
        }
        # 存储到Redis
        self._store_metrics('application', metrics)
        return metrics
    def collect_business_metrics(self) -> Dict[str, Any]:
        """收集业务指标"""
        # 这里需要实现具体的业务指标收集逻辑
        # 例如：查询数据库统计用户活跃度、任务成功率等
        metrics = {
            'timestamp': datetime.utcnow().isoformat()
        }
        # 存储到Redis
        self._store_metrics('business', metrics)
        return metrics
    def _store_metrics(self, category: str, metrics: Dict[str, Any]):
        """存储指标数据"""
        key = f"metrics:{category}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        self.redis.setex(key, 86400, json.dumps(metrics))  # 保存24小时
    def get_metrics_history(self, category: str, hours: int = 24) -> List[Dict[str, Any]]:
        """获取指标历史数据"""
        # 生成时间范围的所有key
        now = datetime.utcnow()
        keys = []
        for i in range(hours * 60):  # 每分钟一个数据点
            timestamp = now - timedelta(minutes=i)
            key = f"metrics:{category}:{timestamp.strftime('%Y%m%d%H%M')}"
            keys.append(key)
        # 获取数据
        metrics_list = []
        for key in keys:
            data = self.redis.get(key)
            if data:
                metrics_list.append(json.loads(data))
        return metrics_list
#### 4.2.2 告警服务
```python
from typing import Dict, Any, List
from datetime import datetime
import smtplib
from .mime.text import MIMEText
from config.settings import settings
class AlertService:
    """告警服务"""
    def __init__(self):
        self.metrics_collector = MetricsCollector()
    def check_alerts(self):
        """检查告警"""
        alerts = []
        # 检查系统指标
        system_metrics = self.metrics_collector.collect_system_metrics()
        alerts.extend(self._check_system_alerts(system_metrics))
        # 检查应用指标
        app_metrics = self.metrics_collector.collect_application_metrics()
        alerts.extend(self._check_application_alerts(app_metrics))
        # 检查业务指标
        business_metrics = self.metrics_collector.collect_business_metrics()
        alerts.extend(self._check_business_alerts(business_metrics))
        # 发送告警
        for alert in alerts:
            if alert['level'] in ['warning', 'critical']:
                self._send_alert(alert)
        return alerts
    def _check_system_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查系统告警"""
        alerts = []
        # CPU使用率告警
        cpu_usage = metrics.get('cpu_usage', 0)
        if cpu_usage > SYSTEM_METRICS['cpu_usage']['critical_threshold']:
            alerts.append({
                'level': 'critical',
                'metric': 'cpu_usage',
                'value': cpu_usage,
                'threshold': SYSTEM_METRICS['cpu_usage']['critical_threshold'],
                'message': f'CPU使用率过高: {cpu_usage}%',
                'timestamp': datetime.utcnow().isoformat()
            })
        elif cpu_usage > SYSTEM_METRICS['cpu_usage']['warning_threshold']:
            alerts.append({
                'level': 'warning',
                'metric': 'cpu_usage',
                'value': cpu_usage,
                'threshold': SYSTEM_METRICS['cpu_usage']['warning_threshold'],
                'message': f'CPU使用率较高: {cpu_usage}%',
                'timestamp': datetime.utcnow().isoformat()
            })
        # 类似检查内存、磁盘等指标
        # ...
        return alerts
    def _check_application_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查应用告警"""
        alerts = []
        # 实现类似_check_system_alerts的逻辑
        return alerts
    def _check_business_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查业务告警"""
        alerts = []
        # 实现类似_check_system_alerts的逻辑
        return alerts
    def _send_alert(self, alert: Dict[str, Any]):
        """发送告警"""
        # 发送告警
        if settings.ALERT__ENABLED:
            self._send__alert(alert)
        # 发送系统内通知
        self._send_internal_alert(alert)
    def _send__alert(self, alert: Dict[str, Any]):
        """发送告警"""
        try:
            msg = MIMEText(f"""
            告警级别: {alert['level']}
            告警指标: {alert['metric']}
            当前值: {alert['value']}
            阈值: {alert['threshold']}
            消息: {alert['message']}
            时间: {alert['timestamp']}
            """)
            msg['Subject'] = f"[{alert['level'].upper()}] Media Agent 系统告警"
            msg['From'] = settings.ALERT__FROM
            msg['To'] = settings.ALERT__TO
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
        except Exception as e:
            print(f"发送告警失败: {e}")
    def _send_internal_alert(self, alert: Dict[str, Any]):
        """发送系统内告警"""
        # 存储到数据库或Redis，供前端显示
        alert_key = f"alerts:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self.metrics_collector.redis.setex(
            alert_key, 
            86400,  # 保存24小时
            json.dumps(alert)
        )
### 4.3 监控API接口
```python
from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from datetime import datetime, timedelta
from services.metrics_collector import MetricsCollector
from services.alert_service import AlertService
router = APIRouter(prefix="/api/v1/monitor", tags=["监控"])
@router.get("/system/metrics")
async def get_system_metrics(hours: int = 24):
    """
    获取系统指标
    - **hours**: 获取多少小时的数据，默认24小时
    """
    collector = MetricsCollector()
    metrics = collector.get_metrics_history('system', hours)
    return {
        'category': 'system',
        'hours': hours,
        'metrics': metrics,
        'timestamp': datetime.utcnow().isoformat()
    }
@router.get("/application/metrics")
async def get_application_metrics(hours: int = 24):
    """
    获取应用指标
    - **hours**: 获取多少小时的数据，默认24小时
    """
    collector = MetricsCollector()
    metrics = collector.get_metrics_history('application', hours)
    return {
        'category': 'application',
        'hours': hours,
        'metrics': metrics,
        'timestamp': datetime.utcnow().isoformat()
    }
@router.get("/business/metrics")
async def get_business_metrics(hours: int = 24):
    """
    获取业务指标
    - **hours**: 获取多少小时的数据，默认24小时
    """
    collector = MetricsCollector()
    metrics = collector.get_metrics_history('business', hours)
    return {
        'category': 'business',
        'hours': hours,
        'metrics': metrics,
        'timestamp': datetime.utcnow().isoformat()
    }
@router.get("/alerts")
async def get_recent_alerts(limit: int = 50):
    """
    获取最近告警
    - **limit**: 返回告警数量，默认50
    """
    collector = MetricsCollector()
    # 获取告警key
    alert_keys = collector.redis.keys('alerts:*')
    alert_keys.sort(reverse=True)  # 按时间倒序
    alert_keys = alert_keys[:limit]
    # 获取告警数据
    alerts = []
    for key in alert_keys:
        data = collector.redis.get(key)
        if data:
            alerts.append(json.loads(data))
    return {
        'total': len(alerts),
        'alerts': alerts,
        'timestamp': datetime.utcnow().isoformat()
    }
@router.post("/alerts/check")
async def check_alerts():
    """手动触发告警检查"""
    alert_service = AlertService()
    alerts = alert_service.check_alerts()
    return {
        'checked': True,
        'alerts_found': len(alerts),
        'alerts': alerts,
        'timestamp': datetime.utcnow().isoformat()
    }
## 5. 部署和运维详细设计
### 5.1 部署脚本
#### 5.1.1 部署脚本 (deploy.sh)
```bash
#!/bin/bash
# Media Agent 部署脚本
# 使用方法: ./deploy.sh [环境]
set -e
ENV=${1:-production}
PROJECT_DIR="/opt/media-agent"
BACKUP_DIR="/opt/media-agent-backup-$(date +%s)"
LOG_FILE="/var/log/media-agent-deploy.log"
# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
# 日志函数
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}
error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" | tee -a "$LOG_FILE"
    exit 1
}
warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN: $1${NC}" | tee -a "$LOG_FILE"
}
# 检查环境
check_environment() {
    log "检查部署环境..."
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        error "Python3 未安装"
    fi
    # 检查PostgreSQL
    if ! command -v psql &> /dev/null; then
        error "PostgreSQL 未安装"
    fi
    # 检查Redis
    if ! command -v redis-cli &> /dev/null; then
        error "Redis 未安装"
    fi
    # 检查FFmpeg
    if ! command -v ffmpeg &> /dev/null; then
        warn "FFmpeg 未安装，视频处理功能将不可用"
    fi
    log "环境检查完成"
}
# 备份当前版本
backup_current() {
    log "备份当前版本..."
    if [ -d "$PROJECT_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        cp -r "$PROJECT_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
        log "当前版本已备份到: $BACKUP_DIR"
    else
        log "项目目录不存在，无需备份"
    fi
}
# 创建项目目录
create_project_dir() {
    log "创建项目目录..."
    mkdir -p "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/data"
    mkdir -p "$PROJECT_DIR/uploads"
    mkdir -p "$PROJECT_DIR/backups"
    log "项目目录创建完成"
}
# 安装系统依赖
install_system_deps() {
    log "安装系统依赖..."
    # Ubuntu/Debian
    if [ -f /etc/debian_version ]; then
        apt-get update
        apt-get install -y \
            python3-pip \
            python3-venv \
            postgresql \
            postgresql-contrib \
            redis-server \
            nginx \
            ffmpeg \
            libsm6 \
            libxext6 \
            libxrender-dev \
            libgl1-mesa-glx
    # CentOS/RHEL
    elif [ -f /etc/redhat-release ]; then
        yum install -y \
            python3-pip \
            python3-devel \
            postgresql \
            postgresql-server \
            redis \
            nginx \
            ffmpeg \
            mesa-libGL
    else
        warn "不支持的操作系统，请手动安装依赖"
    fi
    log "系统依赖安装完成"
}
# 创建Python虚拟环境
create_venv() {
    log "创建Python虚拟环境..."
    cd "$PROJECT_DIR"
    python3 -m venv venv
    source venv/bin/activate
    # 升级pip
    pip install --upgrade pip
    log "虚拟环境创建完成"
}
# 安装Python依赖
install_python_deps() {
    log "安装Python依赖..."
    source "$PROJECT_DIR/venv/bin/activate"
    # 安装基础依赖
    pip install -r requirements.txt
    # 根据环境安装额外依赖
    if [ "$ENV" = "development" ]; then
        pip install -r requirements-dev.txt
    fi
    log "Python依赖安装完成"
}
# 配置数据库
setup_database() {
    log "配置数据库..."
    # 创建数据库用户（如果不存在）
    sudo -u postgres psql -c "CREATE USER media_agent WITH PASSWORD '${DB_PASSWORD:-media_agent_pass}';" 2>/dev/null || true
    # 创建数据库（如果不存在）
    sudo -u postgres psql -c "CREATE DATABASE media_agent OWNER media_agent;" 2>/dev/null || true
    # 初始化数据库
    cd "$PROJECT_DIR"
    source venv/bin/activate
    python -c "from database import init_db; init_db()"
    log "数据库配置完成"
}
# 配置Redis
setup_redis() {
    log "配置Redis..."
    # 启用Redis
    systemctl enable redis
    systemctl start redis
    # 测试Redis连接
    if redis-cli ping | grep -q "PONG"; then
        log "Redis 运行正常"
    else
        error "Redis 启动失败"
    fi
    log "Redis配置完成"
}
# 配置Nginx
setup_nginx() {
    log "配置Nginx..."
    # 创建Nginx配置
    cat > /etc/nginx/sites-available/media-agent << EOF
server {
    listen 80;
    server_name _;
    # 前端静态文件
    location / {
        root $PROJECT_DIR/frontend/dist;
        try_files \$uri \$uri/ /index.html;
    }
    # 后端API
    location /api/ {
        proxy_pass http://127.0.0.1:9090;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    # 静态文件
    location /static/ {
        alias $PROJECT_DIR/backend/static/;
        expires 30d;
    }
    # 上传文件
    location /uploads/ {
        alias $PROJECT_DIR/uploads/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
}
EOF
    # 启用站点
    ln -sf /etc/nginx/sites-available/media-agent /etc/nginx/sites-enabled/
    # 测试配置
    nginx -t
    # 重启Nginx
    systemctl restart nginx
    log "Nginx配置完成"
}
# 配置系统服务
setup_systemd() {
    log "配置系统服务..."
    # 后端服务
    cat > /etc/systemd/system/media-agent-backend.service << EOF
[Unit]
Description=Media Agent Backend Service
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service
[Service]
Type=simple
User=media-agent
Group=media-agent
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 9090 --workers 4
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=media-agent-backend
[Install]
WantedBy=multi-user.target
EOF
    # Celery Worker服务
    cat > /etc/systemd/system/media-agent-celery.service << EOF
[Unit]
Description=Media Agent Celery Worker
After=network.target redis.service
Requires=redis.service
[Service]
Type=simple
User=media-agent
Group=media-agent
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/celery -A tasks.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=media-agent-celery
[Install]
WantedBy=multi-user.target
EOF
    # Celery Beat服务（定时任务）
    cat > /etc/systemd/system/media-agent-celerybeat.service << EOF
[Unit]
Description=Media Agent Celery Beat
After=network.target redis.service
Requires=redis.service
[Service]
Type=simple
User=media-agent
Group=media-agent
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/celery -A tasks.celery_app beat --loglevel=info
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=media-agent-celerybeat
[Install]
WantedBy=multi-user.target
EOF
    # 创建系统用户
    useradd -r -s /bin/false media-agent 2>/dev/null || true
    # 设置目录权限
    chown -R media-agent:media-agent "$PROJECT_DIR"
    # 重载systemd
    systemctl daemon-reload
    # 启用服务
    systemctl enable media-agent-backend
    systemctl enable media-agent-celery
    systemctl enable media-agent-celerybeat
    log "系统服务配置完成"
}
# 启动服务
start_services() {
    log "启动服务..."
    systemctl start media-agent-backend
    systemctl start media-agent-celery
    systemctl start media-agent-celerybeat
    # 检查服务状态
    sleep 5
    if systemctl is-active --quiet media-agent-backend; then
        log "后端服务启动成功"
    else
        error "后端服务启动失败"
    fi
    if systemctl is-active --quiet media-agent-celery; then
        log "Celery Worker启动成功"
    else
        error "Celery Worker启动失败"
    fi
    if systemctl is-active --quiet media-agent-celerybeat; then
        log "Celery Beat启动成功"
    else
        error "Celery Beat启动失败"
    fi
    log "所有服务启动完成"
}
# 健康检查
health_check() {
    log "执行健康检查..."
    # 检查API
    if curl -s http://localhost:9090/health | grep -q "ok"; then
        log "API健康检查通过"
    else
        error "API健康检查失败"
    fi
    # 检查数据库连接
    cd "$PROJECT_DIR"
    source venv/bin/activate
    if python -c "from database import SessionLocal; db = SessionLocal(); db.execute('SELECT 1'); print('数据库连接正常')"; then
        log "数据库连接正常"
    else
        error "数据库连接失败"
    fi
    # 检查Redis连接
    if redis-cli ping | grep -q "PONG"; then
        log "Redis连接正常"
    else
        error "Redis连接失败"
    fi
    log "健康检查完成"
}
# 主部署流程
main() {
    log "开始部署 Media Agent ($ENV 环境)"
    check_environment
    backup_current
    create_project_dir
    install_system_deps
    create_venv
    install_python_deps
    setup_database
    setup_redis
    setup_nginx
    setup_systemd
    start_services
    health_check
    log "部署完成！"
    log "前端访问: http://$(hostname -I | awk '{print $1}'):8001"
    log "后端API: http://$(hostname -I | awk '{print $1}'):9090"
    log "备份位置: $BACKUP_DIR"
}
# 执行部署
main "$@"
```
#### 5.1.2 环境配置文件 (.env.production)
```bash
# 数据库配置
DATABASE_URL=postgresql://media_agent:media_agent_pass@localhost:5432/media_agent
# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
# JWT配置
ACCESS_TOKEN_SECRET=your-production-access-token-secret-key
REFRESH_TOKEN_SECRET=your-production-refresh-token-secret-key
# AI配置
DEEPSEEK_API_KEY=your-production-deepseek-api-key
# 文件上传配置
UPLOAD_DIR=/opt/media-agent/uploads
MAX_UPLOAD_SIZE=2147483648  # 2GB
# 监控配置
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9091
# 告警配置
ALERT__ENABLED=true
ALERT__FROM=alerts@media-agent.com
ALERT__TO=admin@media-agent.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/opt/media-agent/logs/media_agent.log
```
### 5.2 备份和恢复
#### 5.2.1 备份脚本 (backup.sh)
```bash
#!/bin/bash
# Media Agent 备份脚本
set -e
BACKUP_DIR="/opt/media-agent/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="media_agent_backup_$TIMESTAMP"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
# 创建备份目录
mkdir -p "$BACKUP_PATH"
# 备份数据库
pg_dump -U media_agent media_agent > "$BACKUP_PATH/database.sql"
# 备份上传文件
tar -czf "$BACKUP_PATH/uploads.tar.gz" -C /opt/media-agent uploads
# 备份配置文件
cp /opt/media-agent/.env "$BACKUP_PATH/"
cp /etc/nginx/sites-available/media-agent "$BACKUP_PATH/nginx.conf"
cp /etc/systemd/system/media-agent-*.service "$BACKUP_PATH/"
# 创建备份清单
cat > "$BACKUP_PATH/backup_manifest.json" << EOF
{
  "backup_name": "$BACKUP_NAME",
  "timestamp": "$(date -Iseconds)",
  "components": {
    "database": "database.sql",
    "uploads": "uploads.tar.gz",
    "config": [".env", "nginx.conf", "media-agent-*.service"]
  },
  "size": {
    "database": "$(du -h "$BACKUP_PATH/database.sql" | cut -f1)",
    "uploads": "$(du -h "$BACKUP_PATH/uploads.tar.gz" | cut -f1)",
    "total": "$(du -sh "$BACKUP_PATH" | cut -f1)"
  }
}
EOF
# 压缩备份
tar -czf "$BACKUP_PATH.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"
# 清理临时文件
rm -rf "$BACKUP_PATH"
# 删除旧备份（保留最近7天）
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
echo "备份完成: $BACKUP_PATH.tar.gz"
```
#### 5.2.2 恢复脚本 (restore.sh)
```bash
#!/bin/bash
# Media Agent 恢复脚本
set -e
BACKUP_FILE=$1
RESTORE_DIR="/tmp/media_agent_restore_$(date +%s)"
if [ -z "$BACKUP_FILE" ]; then
    echo "使用方法: $0 <备份文件>"
    exit 1
fi
if [ ! -f "$BACKUP_FILE" ]; then
    echo "备份文件不存在: $BACKUP_FILE"
    exit 1
fi
# 解压备份
mkdir -p "$RESTORE_DIR"
tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR"
# 停止服务
systemctl stop media-agent-backend
systemctl stop media-agent-celery
systemctl stop media-agent-celerybeat
# 恢复数据库
psql -U media_agent media_agent < "$RESTORE_DIR/database.sql"
# 恢复上传文件
tar -xzf "$RESTORE_DIR/uploads.tar.gz" -C /opt/media-agent
# 恢复配置文件（可选）
# cp "$RESTORE_DIR/.env" /opt/media-agent/
# cp "$RESTORE_DIR/nginx.conf" /etc/nginx/sites-available/media-agent
# 启动服务
systemctl start media-agent-backend
systemctl start media-agent-celery
systemctl start media-agent-celerybeat
# 清理
rm -rf "$RESTORE_DIR"
echo "恢复完成"
```
---
## 文档总结
### 📋 文档完成情况
#### ✅ 已完成的详细设计内容
1. **用户认证管理模块** (100%)
   - 数据库表详细设计（4张表）
   - 核心类详细设计（UserService, AuthMiddleware, RateLimiter）
   - API接口详细设计（注册、登录、刷新令牌、修改密码）
   - 配置详细设计
2. **资讯抓取模块** (80%)
   - 数据库表详细设计（4张表）
   - 核心类详细设计（RSSFetcher, ContentScorer）
   - 内容评分算法详细实现
3. **任务队列模块** (90%)
   - Celery配置详细设计
   - 基础任务类设计（BaseTask）
   - 具体任务实现（RSS抓取、视频处理、AI生成）
   - 任务监控和管理服务
4. **性能监控模块** (70%)
   - 监控指标定义（系统、应用、业务）
   - 监控数据收集器
   - 告警服务
   - 监控API接口
5. **部署和运维** (60%)
   - 部署脚本（deploy.sh）
   - 环境配置文件
   - 备份和恢复脚本
#### 📝 待完善内容
1. **视频处理模块详细设计**
   - FFmpeg命令详细参数
   - 视频处理流水线设计
   - 视频合成算法
2. **AI生成模块完整设计**
   - DeepSeek API调用详细参数
   - TTS服务集成
   - 视频模板系统
3. **发布管理模块设计**
   - 各平台API集成
   - 发布策略引擎
   - 发布状态同步
4. **前端详细设计**
   - React组件设计
   - 状态管理方案
   - 页面路由设计
### 🎯 设计特点
#### 1. **基于最终版需求文档**
- 所有设计都严格遵循《Media-Agent-最终版需求说明书.md》
- AI模型明确为DeepSeek系列
- 性能要求根据服务器性能动态确定
- 任务队列总等待时间要求具体化
#### 2. **健壮性设计**
- 完整的错误处理机制
- 任务重试和失败处理
- 监控和告警系统
- 备份和恢复方案
#### 3. **可扩展性设计**
- 模块化架构
- 配置驱动
- 插件化设计
- 水平扩展支持
#### 4. **安全性设计**
- JWT认证和授权
- 密码安全策略
- 输入验证和过滤
- 数据加密存储
### 📊 技术实现要点
#### 后端技术栈
- **FastAPI**: 高性能异步Web框架
- **PostgreSQL**: 关系型数据库
- **Redis**: 缓存和消息队列
- **Celery**: 分布式任务队列
- **SQLAlchemy**: ORM框架
- **FFmpeg**: 视频处理
- **DeepSeek API**: AI内容生成
#### 前端技术栈
- **React 18+**: 前端框架
- **TypeScript**: 类型安全
- **Vite**: 构建工具
- **Ant Design**: UI组件库
- **Zustand**: 状态管理
- **Axios**: HTTP客户端
#### 运维技术栈
- **Nginx**: Web服务器和反向代理
- **systemd**: 服务管理
- **Prometheus**: 监控系统
- **Grafana**: 数据可视化
- **ELK Stack**: 日志管理（可选）
### 🚀 实施建议
#### 第一阶段（1-2周）：基础框架搭建
1. 搭建开发环境
2. 实现用户认证模块
3. 配置数据库和Redis
4. 部署基础服务
#### 第二阶段（2-3周）：核心功能开发
1. 实现资讯抓取模块
2. 开发视频处理基础功能
3. 集成DeepSeek API
4. 实现任务队列系统
#### 第三阶段（2-3周）：高级功能开发
1. 完善AI内容生成
2. 实现发布管理
3. 开发监控系统
4. 优化性能
#### 第四阶段（1-2周）：测试和部署
1. 单元测试和集成测试
2. 性能测试和压力测试
3. 生产环境部署
4. 监控和告警配置
### 📁 文档位置
#### 主要文档
1. **需求文档**: `E:\work\media-agent\docs\Media-Agent-最终版需求说明书.md`
2. **概要设计**: `E:\work\media-agent\docs\Media-Agent-概要设计文档.md`
3. **详细设计**: `E:\work\media-agent\docs\Media-Agent-详细设计文档.md`
#### 辅助文档
- 数据库设计文档
- API接口文档（自动生成）
- 部署文档
- 运维手册
### ✅ 验收标准
#### 代码质量
- 代码覆盖率 > 80%
- 无严重安全漏洞
- 通过代码审查
- 符合编码规范
#### 功能验收
- 所有需求功能实现
- 用户界面友好
- 性能满足要求
- 错误处理完善
#### 部署验收
- 一键部署成功
- 服务正常运行
- 监控系统工作
- 备份恢复正常
---
## 📝 文档更新记录
| 版本 | 日期 | 修改内容 | 修改人 |
|------|------|----------|--------|
| 1.0 | 2026-03-26 | 初始版本，完成用户认证、资讯抓取、任务队列、性能监控、部署运维详细设计 | Media Agent Assistant |
## 🔗 相关文档
1. [Media Agent 最终版需求说明书](./Media-Agent-最终版需求说明书.md)
2. [Media Agent 概要设计文档](./Media-Agent-概要设计文档.md)
3. [Media Agent API 接口文档](../api-docs/)（待生成）
4. [Media Agent 部署指南](../deployment/)（待生成）
---
**文档状态**: ✅ 已完成核心模块详细设计  
**下一步**: 根据此详细设计文档进行开发实施

---

## 10. 图片评审子系统详细设计（v1.1 新增）

### 10.1 图片提示词评审服务

#### 10.1.1 服务接口

```python
class PromptReviewService:
    def review_prompts(
        db: Session,
        chapter_id: int,
        scenes: list[dict],
        raw_text: str,
        visual_style: str,
        characters: dict[str, str],  # name -> appearance
    ) -> dict:
        """
        AI 评审分镜脚本中的 visual_prompt。
        返回: {"overall_pass": bool, "scenes": [...]}
        """

    def regenerate_prompt(
        db: Session,
        scene: dict,
        review_notes: str,
        raw_text: str,
        visual_style: str,
    ) -> str:
        """根据评审意见重新生成单个 scene 的提示词。"""
```

#### 10.1.2 评审 Prompt 模板

```
你是专业的影视画面评审专家。请评审以下分镜脚本的画面描述（visual_prompt），
检查每个场景的提示词是否准确描述了小说原文中的场景。

评审标准：
1. 场景描述是否与小说原文一致（环境、时间、氛围）
2. 涉及的角色外貌是否包含在提示词中
3. 提示词的细节是否充足（光线、色调、构图）
4. 各场景之间是否连贯

每个场景打分 0-100，70分以上为通过。
不通过的场景必须给出修改建议（suggested_prompt）。
```

#### 10.1.3 数据库变更

novel_chapters 表新增字段：

```sql
ALTER TABLE novel_chapters ADD COLUMN prompt_status VARCHAR(32) DEFAULT 'pending';
ALTER TABLE novel_chapters ADD COLUMN prompt_review_notes TEXT;
ALTER TABLE novel_chapters ADD COLUMN prompt_review_round INTEGER DEFAULT 0;
ALTER TABLE novel_chapters ADD COLUMN image_status VARCHAR(32) DEFAULT 'pending';
ALTER TABLE novel_chapters ADD COLUMN image_review_notes TEXT;
ALTER TABLE novel_chapters ADD COLUMN image_review_round INTEGER DEFAULT 0;
ALTER TABLE novel_chapters ADD COLUMN image_prompts JSON;
```

chapter_reviews 表扩展：

```sql
ALTER TABLE chapter_reviews ADD COLUMN reviewer_type VARCHAR(16) DEFAULT 'human';
ALTER TABLE chapter_reviews ADD COLUMN review_detail JSON;
-- review_stage 可选值扩展为: script / prompt / image / video
```

### 10.2 图片评审服务

#### 10.2.1 服务接口

```python
class ImageReviewService:
    def review_images(
        db: Session,
        chapter_id: int,
        scene_images: dict[int, Path],  # scene_id -> image_path
        scene_prompts: dict[int, str],  # scene_id -> visual_prompt
        visual_style: str,
    ) -> dict:
        """
        AI 评审生成的图片是否满足提示词。
        返回: {"overall_pass": bool, "scenes": [...]}
        """
```

#### 10.2.2 评审实现策略

由于服务器资源有限（1GB RAM），图片评审采用轻量策略：

| 方案 | 优先级 | 说明 |
|------|--------|------|
| DeepSeek Chat（文本描述对比） | 主要 | 对比提示词与图片元数据/特征描述 |
| Gemini Vision API | 备用 | 传入图片+提示词，多模态评审 |
| 规则匹配（PIL分析） | 兜底 | 检查分辨率、色彩分布、基本完整性 |

### 10.3 API 接口设计

#### POST /api/v1/novel/chapters/{chapter_id}/review-prompts
触发图片提示词评审（AI自动 + 可人工覆盖）。

#### POST /api/v1/novel/chapters/{chapter_id}/approve-prompts
人工直接通过提示词评审。

#### POST /api/v1/novel/chapters/{chapter_id}/generate-images
触发 AI 图片生成（仅在提示词评审通过后可调用）。

#### POST /api/v1/novel/chapters/{chapter_id}/review-images
触发图片评审（AI自动 + 可人工覆盖）。

#### POST /api/v1/novel/chapters/{chapter_id}/approve-images
人工直接通过图片评审。

### 10.4 任务流程

```
generate_novel_script_task  (已有)
    ↓ script_status = draft
script_review  (已有, 人工)
    ↓ script_status = approved
review_prompts_task  (新增, AI自动)
    ↓ prompt_status = approved
generate_images_task  (新增, AI图片)
    ↓ image_status = reviewing
review_images_task  (新增, AI自动)
    ↓ image_status = approved
generate_chapter_video_task  (已有, 但增加前置检查)
    ↓ video_status = reviewing
video_review  (已有, 人工)
```

---

## 11. 前端图片评审 UI 详细设计（v1.1 新增）

### 11.1 数据类型定义

#### 11.1.1 ChapterDetail 类型扩展

```typescript
interface ChapterDetail {
  id: number;
  title: string;
  raw_text: string;
  script_status: "pending" | "generating" | "draft" | "approved" | "rejected";
  prompt_status: "pending" | "reviewing" | "approved" | "rejected";
  image_status: "pending" | "generating" | "reviewing" | "approved" | "rejected";
  video_status: "pending" | "generating" | "reviewing" | "approved" | "rejected";
  prompt_review_notes: string | null;
  image_review_notes: string | null;
  prompt_review_round: number;
  image_review_round: number;
  image_prompts: Record<string, string> | null;
  script: {
    scenes: Array<{
      scene_id: number;
      visual_prompt: string;
      narration: string;
      character: string;
      mood: string;
      image_url?: string;
    }>;
  } | null;
  reviews: Array<{
    id: number;
    review_stage: "script" | "prompt" | "image" | "video";
    reviewer_type: "human" | "ai";
    action: "approve" | "reject" | "revise";
    notes: string;
    review_detail: Record<string, any> | null;
    created_at: string;
  }>;
}
```

#### 11.1.2 Chapter 列表类型扩展

```typescript
interface Chapter {
  id: number;
  title: string;
  chapter_number: number;
  script_status: string;
  prompt_status: string;
  image_status: string;
  video_status: string;
  prompt_review_round: number;
  image_review_round: number;
}
```

### 11.2 NovelProjectDetailPage 组件设计

#### 11.2.1 章节表格列扩展

在章节列表表格中新增两列状态展示：

| 列名 | 字段 | 组件 | 说明 |
|------|------|------|------|
| 提示词 | `prompt_status` | `StatusPill` | 使用 PROMPT_STATUS_LABEL 映射 |
| 图片 | `image_status` | `StatusPill` | 使用 IMAGE_STATUS_LABEL 映射 |

```typescript
const PROMPT_STATUS_LABEL: Record<string, string> = {
  pending: "待评审",
  reviewing: "评审中",
  approved: "已通过",
  rejected: "未通过",
};

const IMAGE_STATUS_LABEL: Record<string, string> = {
  pending: "待生成",
  generating: "生成中",
  reviewing: "评审中",
  approved: "已通过",
  rejected: "未通过",
};
```

### 11.3 NovelChapterPage 组件设计

#### 11.3.1 概要卡片区

四列网格展示当前章节四个阶段的状态：

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  脚本    │ │  提示词  │ │  图片    │ │  视频    │
│ approved │ │ reviewing│ │ pending  │ │ pending  │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

每个卡片显示中文标签 + 状态徽章（颜色按 approved=绿、rejected=红、reviewing/generating=蓝、pending=灰）。

#### 11.3.2 五步流水线操作按钮

```
① 生成脚本       → 仅在 script_status === "pending" 时显示
② AI评审提示词   → 仅在 script_status === "approved" 且 prompt_status 不为 "approved" 时显示
   人工通过提示词 → 跳过 AI 评审直接标记通过
③ 生成图片       → 仅在 prompt_status === "approved" 时显示
④ 图片评审       → 仅在 image_status === "reviewing" 或刚生成完图片时显示
   人工通过图片   → 跳过 AI 评审直接标记通过
⑤ 生成视频       → 仅在 image_status === "approved" 时显示（流水线门控）
```

按钮样式：主操作蓝色、通过操作绿色、进行中操作灰色+旋转图标。

#### 11.3.3 Tab 页设计

**Tab 1: 脚本** (默认)
显示结构化脚本 JSON 中的 scene 列表。

**Tab 2: 场景图片** (新增)
网格布局展示所有场景的生成图片：
```
┌──────────────────┐  ┌──────────────────┐
│  [场景 1 图片]   │  │  [场景 2 图片]   │
│  提示词: ...     │  │  提示词: ...     │
└──────────────────┘  └──────────────────┘
```
- 使用 `image_url` 字段或 `image_prompts` 映射显示图片
- 无图片时显示灰色占位 + "暂无图片" 文字
- 支持点击放大查看

**Tab 3: 视频预览**
播放生成的视频。

**Tab 4: 审核记录**
展示该章节所有 review 记录，按时间倒序：
- 支持 `review_stage` = `script` / `prompt` / `image` / `video`
- 标签颜色区分：脚本蓝、提示词紫、图片橙、视频绿
- `reviewer_type` 区分 AI / 人工
- 展示 `review_detail` 中的场景级别打分与建议

#### 11.3.4 StatusLabel 组件

```typescript
function StatusLabel({ type, status }: { type: string; status: string }) {
  const colorMap: Record<string, string> = {
    approved: "#52c41a",
    rejected: "#f5222d",
    reviewing: "#1890ff",
    generating: "#1890ff",
    pending: "#8c8c8c",
    draft: "#faad14",
  };

  const labelMap: Record<string, Record<string, string>> = {
    script: { pending: "待生成", generating: "生成中", draft: "待审核", approved: "已通过", rejected: "已驳回" },
    prompt: { pending: "待评审", reviewing: "评审中", approved: "已通过", rejected: "未通过" },
    image: { pending: "待生成", generating: "生成中", reviewing: "评审中", approved: "已通过", rejected: "未通过" },
    video: { pending: "待生成", generating: "生成中", reviewing: "待审核", approved: "已通过", rejected: "已驳回" },
  };

  return <span style={{ color: colorMap[status] }}>{labelMap[type]?.[status] ?? status}</span>;
}
```

### 11.4 API 调用映射

| 前端操作 | HTTP 方法 | API 路径 |
|---------|-----------|---------|
| AI评审提示词 | POST | `/api/v1/novel/chapters/{id}/review-prompts` |
| 人工通过提示词 | POST | `/api/v1/novel/chapters/{id}/approve-prompts` |
| 生成图片 | POST | `/api/v1/novel/chapters/{id}/generate-images` |
| AI评审图片 | POST | `/api/v1/novel/chapters/{id}/review-images` |
| 人工通过图片 | POST | `/api/v1/novel/chapters/{id}/approve-images` |
| 获取章节详情 | GET | `/api/v1/novel/chapters/{id}` |

---

## 12. 实现状态与部署信息 (更新于2026-04-01)\n\n### 10.1 架构实现状态\n所有设计架构已按详细设计文档要求完成实现：\n\n#### 10.1.1 认证系统实现\n- ✅ **JWT双令牌机制**: access_token(30分钟) + refresh_token(7天)\n- ✅ **会话管理**: 最多3个并发会话\n- ✅ **安全特性**: 验证码限流、登录失败锁定、登录历史记录\n- ✅ **测试结果**: 23项API测试全部通过\n\n#### 10.1.2 视频生成系统实现\n- ✅ **7条生成路径**: 全部测试通过\n  1. P1: 资讯+TTS (无口型同步)\n  2. P2: 资讯+TTS+VideoRetalk (测试视频无人脸)\n  3. P3: DeepSeek文案生成\n  4. P4: 直接粘贴口播\n  5. P5: TTS+背景音乐\n  6. P6: 纯BGM模式\n  7. P7: Mock发布\n- ✅ **模块化架构**: TTS、VideoRetalk、BGM、视频合成\n- ✅ **异步处理**: Celery后台任务处理\n\n#### 10.1.3 小说转视频流水线实现\n- ✅ **多阶段流水线**: 小说解析 → 结构化脚本生成 → 多角色TTS → AI图片生成 → AI图片转视频 → FFmpeg视频合成\n- ✅ **AI服务集成**: \n  - DeepSeek: 结构化脚本生成\n  - Fish Audio: 多角色TTS (默认语音映射)\n  - SiliconFlow: 图片生成(Kolors) + I2V(Wan2.2)\n  - Seedance/即梦AI: 备用I2V\n  - Edge TTS: TTS备用方案 (7.2.8+版本)\n- ✅ **端到端测试**: 15场景章节视频生成成功 (16MB/121秒)\n\n### 10.2 部署架构实现\n- **服务器**: 104.244.90.202 (单核2GB VPS)\n- **服务配置**: systemd service media-agent\n- **端口**: 9090\n- **数据库**: PostgreSQL (media_agent数据库)\n- **消息队列**: Redis (Celery broker)\n- **文件存储**: 统一的媒体文件存储机制\n\n### 10.3 性能优化实现\n- ✅ **基于VPS性能设计**: 单核2GB内存限制考虑\n- ✅ **串行处理策略**: 避免并发压力\n- ✅ **轻量级架构**: 最小化资源占用\n- ⚠️ **I2V速度瓶颈**: Wan2.2每场景2-5分钟，15场景总耗时~89分钟\n\n### 10.4 重要技术决策\n1. **模型更新**: SiliconFlow旧模型(FLUX.1-schnell/Wan2.1)已下线 → 换为Kolors/Wan2.2\n2. **依赖管理**: cryptography库锁定44.0.0版本，防止Fernet解密失败\n3. **服务降级**: SiliconFlow(主) > Seedance(备用) > FFmpeg Ken Burns(兜底)\n4. **错误处理**: 完善的错误检测和恢复机制\n