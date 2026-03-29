from typing import Optional

from pydantic import BaseModel, Field


class TokenOut(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 1800


class UserOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class CaptchaOut(BaseModel):
    captcha_id: str
    image_base64: str


class SendCodesOut(BaseModel):
    ok: bool = True
    message: str = "验证码已发送（若未配置邮件/短信网关，请查看服务器日志或 flow_logs）"
    dev_codes: Optional[dict[str, str]] = None
    sms_enabled: bool = False


class AuthFeaturesOut(BaseModel):
    sms_enabled: bool = False


class SendCodesRegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")


class RegisterCompleteIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)


class LoginPasswordIn(BaseModel):
    login: str = Field(..., description="用户名")
    password: str
    captcha_id: Optional[str] = None
    captcha_answer: Optional[str] = None


class RefreshTokenIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=10, max_length=128)


class PasswordResetIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    new_password: str = Field(min_length=10, max_length=128)


class SessionOut(BaseModel):
    id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: str
    is_current: bool = False


class LoginHistoryOut(BaseModel):
    id: int
    username: str
    ip_address: Optional[str] = None
    success: bool
    reason: Optional[str] = None
    created_at: str
