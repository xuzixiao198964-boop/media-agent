from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON, BigInteger, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    lock_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rss_urls: Mapped[list] = mapped_column(JSON, default=list)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1024), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    category: Mapped["Category"] = relationship()


class UserVideo(Base):
    __tablename__ = "user_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    original_name: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str] = mapped_column(String(1024))
    mime: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # 资讯模式：关联文章；文案模式：可为空（由 meta.user_prompt 等驱动）
    article_id: Mapped[Optional[int]] = mapped_column(ForeignKey("articles.id"), nullable=True)
    user_video_id: Mapped[int] = mapped_column(ForeignKey("user_videos.id"))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    output_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    narration_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 成片库展示说明（用户可编辑）
    output_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generation_job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id"))
    platform: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FlowLog(Base):
    __tablename__ = "flow_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ref_type: Mapped[str] = mapped_column(String(64))
    ref_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    step: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(16), default="info")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApiSecret(Base):
    __tablename__ = "api_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), unique=True)
    value_enc: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VoicePrint(Base):
    """
    声纹/音色复刻结果缓存。

    目前实现面向腾讯云 VRS 一句话复刻（对应 TTS TextToVoice 的 FastVoiceType）。
    """

    __tablename__ = "voice_prints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # 来源：用户上传音频 或 从已上传视频提取音频
    source_type: Mapped[str] = mapped_column(String(32))  # "upload" | "video"
    source_video_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_videos.id"), nullable=True)

    # 存储的源文件路径（相对 upload_dir）
    stored_path: Mapped[str] = mapped_column(String(1024))
    original_name: Mapped[str] = mapped_column(String(512))

    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/processing/ready/failed
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 腾讯云 VRS 信息（用于后续 TTS 合成）
    provider: Mapped[str] = mapped_column(String(32), default="tencent_vrs")
    voice_gender: Mapped[int] = mapped_column(Integer, default=1)  # 1 male / 2 female
    tts_language: Mapped[str] = mapped_column(String(16), default="zh-CN")

    tencent_vrs_task_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    voice_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fast_voice_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class UserSession(Base):
    """活跃会话（每用户最多 3 个；JWT refresh token 绑定）。"""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LoginHistory(Base):
    """登录历史记录。"""

    __tablename__ = "login_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(64))
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VerificationCode(Base):
    """邮箱/短信验证码（注册、登录、找回密码）。"""

    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target: Mapped[str] = mapped_column(String(255), index=True)
    channel: Mapped[str] = mapped_column(String(16))  # email | phone
    purpose: Mapped[str] = mapped_column(String(32))  # register | login_email | login_phone | reset_password
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── 小说视频生成系统模型 ──────────────────────────────────────


class NovelProject(Base):
    __tablename__ = "novel_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    novel_slug: Mapped[str] = mapped_column(String(256), index=True)
    novel_title: Mapped[str] = mapped_column(String(512))
    novel_author: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    novel_intro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    narrator_voice_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    visual_style: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_bgm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bgm_library.id"), nullable=True)
    video_orientation: Mapped[str] = mapped_column(String(16), default="portrait")  # portrait / landscape
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    characters: Mapped[list["NovelCharacter"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    chapters: Mapped[list["NovelChapter"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class NovelCharacter(Base):
    __tablename__ = "novel_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    gender: Mapped[str] = mapped_column(String(16), default="neutral")  # male / female / neutral
    voice_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    voice_sample_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    personality: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    appearance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["NovelProject"] = relationship(back_populates="characters")


class NovelChapter(Base):
    __tablename__ = "novel_chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"), index=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(512))
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    script: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    script_status: Mapped[str] = mapped_column(String(32), default="pending")
    script_review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 图片提示词评审
    prompt_status: Mapped[str] = mapped_column(String(32), default="pending")
    prompt_review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_review_round: Mapped[int] = mapped_column(Integer, default=0)
    image_prompts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 图片评审
    image_status: Mapped[str] = mapped_column(String(32), default="pending")
    image_review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_review_round: Mapped[int] = mapped_column(Integer, default=0)
    # 视频
    video_status: Mapped[str] = mapped_column(String(32), default="pending")
    video_review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    audio_assets: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    visual_assets: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    bgm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bgm_library.id"), nullable=True)
    bgm_volume: Mapped[float] = mapped_column(Float, default=0.15)
    estimated_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["NovelProject"] = relationship(back_populates="chapters")


class ChapterReview(Base):
    __tablename__ = "chapter_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("novel_chapters.id"), index=True)
    review_stage: Mapped[str] = mapped_column(String(16))  # script / prompt / image / video
    review_round: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer_type: Mapped[str] = mapped_column(String(16), default="human")  # ai / human
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    review_detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BgmLibrary(Base):
    __tablename__ = "bgm_library"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(256))
    mood: Mapped[str] = mapped_column(String(32), default="peaceful")
    file_path: Mapped[str] = mapped_column(String(1024))
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="custom")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
