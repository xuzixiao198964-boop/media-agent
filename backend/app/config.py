from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Media Agent"
    secret_key: str = "change-me-in-production-use-long-random"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    max_sessions_per_user: int = 3
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://media:media@localhost:5432/media_agent"
    cors_origins: str = "*"

    redis_url: str = "redis://localhost:6379/0"

    upload_dir: str = "/data/uploads"
    output_dir: str = "/data/outputs"
    # 留空则自动使用「项目根/frontend/dist」（裸机 /opt/media-agent 布局）；仅 API 时可不构建前端
    frontend_dist_dir: str = ""
    # 可选：背景音乐文件路径（用于「口播+BGM」「纯 BGM」模式混音/铺底）
    default_bgm_path: str = "/data/default_bgm.mp3"

    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
    tencent_tts_secret_id: str = ""
    tencent_tts_secret_key: str = ""
    tencent_tts_region: str = "ap-guangzhou"
    tencent_tts_voice_type: int = 101001

    # TRTC 声音克隆（VoiceClone）/ TRTC 语音合成（TextToSpeech）
    trtc_sdk_app_id: str = ""  # TRTC SdkAppID（整数也可用字符串存）
    trtc_secret_id: str = ""
    trtc_secret_key: str = ""
    trtc_region: str = "ap-guangzhou"

    # 阿里云百炼 Model Studio（VideoRetalk / 声动人像口型替换）API Key
    dashscope_api_key: str = ""
    # 默认使用更低成本的分辨率
    videoretalk_resolution: str = "480P"

    # 给阿里云抓取 input.video_url/input.audio_url 用的公网访问基址
    # 你的站点前端/静态文件由 Nginx 监听在 8080
    public_base_url: str = "http://104.244.90.202"

    publish_mode: str = "mock"

    rss_fetch_interval_seconds: int = 300
    status_poll_hint_seconds: int = 15
    # 关闭后必须登录（注册/验证码流程）；开发可临时 True 免登录
    single_user_mode: bool = False
    # 开发调试用：在接口响应中返回验证码（生产务必 False）
    auth_dev_expose_codes: bool = False
    # 连续密码登录失败达到此次数后，必须完成图形验证码（算术题）
    login_fail_captcha_threshold: int = 3

    # ── 小说视频生成 ──
    # ai-novel-agent 服务地址
    novel_agent_base_url: str = "http://104.244.90.202:9000"
    # Fish Audio 多角色 TTS
    fish_audio_api_key: str = ""
    fish_audio_base_url: str = "https://api.fish.audio"
    # 硅基流动 AI 图片生成
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn"
    siliconflow_model: str = "Kwai-Kolors/Kolors"
    # Seedance 图生视频（字节跳动 · 火山引擎方舟）
    seedance_access_key: str = ""
    seedance_secret_key: str = ""
    # 小说素材存储目录
    novel_assets_dir: str = "/data/novel_assets"

    # 邮件（找回密码/注册验证码）；留空则仅写 flow_logs
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    # 短信网关标识；留空则仅写 flow_logs
    sms_provider: str = ""
    # 是否启用短信验证码（注册/登录/找回）；False 时仅邮箱验证码
    sms_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
