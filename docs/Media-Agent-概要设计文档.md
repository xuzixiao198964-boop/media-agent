# Media Agent 概要设计文档（基于VPS性能优化）

## 文档信息
- **文档编号**: HLD-001
- **文档标题**: Media Agent 概要设计文档（基于VPS性能优化）
- **项目名称**: Media Agent（资讯 → 短视频 → 发布）
- **创建日期**: 2026-03-26
- **更新日期**: 2026-03-26
- **创建人**: Media Agent Assistant
- **状态**: 📝 VPS优化版
- **版本**: 1.1
- **依据文档**: Media-Agent-最终版需求说明书.md（版本1.3）

## 1. 系统架构设计

### 1.1 整体架构概述

```
┌─────────────────────────────────────────────────────────────┐
│                         客户端层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Web前端   │  │   移动端    │  │   API调用   │        │
│  │   (React)   │  │  (响应式)   │  │   (第三方)  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS/JSON
┌───────────────────────────▼─────────────────────────────────┐
│                         API网关层                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                  FastAPI 后端服务                     │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ 路由层   │  │ 中间件层  │  │ 认证层   │         │  │
│  │  └──────────┘  └──────────┘  └──────────┘         │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                        业务逻辑层                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ 用户认证模块 │  │ 资讯抓取模块 │  │ 视频处理模块 │    │
│  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │    │
│  │  │ 注册   │  │  │  │ RSS解析│  │  │  │ 上传   │  │    │
│  │  │ 登录   │  │  │  │ 网页抓取│  │  │  │ 转码   │  │    │
│  │  │ 会话管理│  │  │  │ 内容清洗│  │  │  │ 合成   │  │    │
│  │  └────────┘  │  │  └────────┘  │  │  └────────┘  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐                      │
│  │ AI生成模块   │  │ 发布管理模块 │                      │
│  │  ┌────────┐  │  │  ┌────────┐  │                      │
│  │  │ 文案生成│  │  │  │ 平台管理│  │                      │
│  │  │ 语音合成│  │  │  │ 发布队列│  │                      │
│  │  │ 视频合成│  │  │  │ 状态监控│  │                      │
│  │  └────────┘  │  │  └────────┘  │                      │
│  └──────────────┘  └──────────────┘                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                        数据访问层                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  数据库ORM   │  │   缓存层     │  │  文件存储    │    │
│  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │    │
│  │  │PostgreSQL│  │  │  │ Redis │  │  │  │本地磁盘│  │    │
│  │  │ 连接池  │  │  │  │ 缓存  │  │  │  │对象存储│  │    │
│  │  │ 事务管理│  │  │  │ 队列  │  │  │  │CDN加速│  │    │
│  │  └────────┘  │  │  └────────┘  │  │  └────────┘  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈选择

#### 后端技术栈
- **Web框架**: FastAPI (Python 3.9+)
  - 选择理由: 高性能，自动生成API文档，异步支持好
- **数据库**: PostgreSQL 13+
  - 选择理由: 功能完整，事务支持好，JSONB支持
- **缓存/队列**: 轻量级内存缓存 + 数据库队列
  - 选择理由: 基于服务器实际情况（104.244.90.202），避免Redis依赖，减少资源占用
- **任务队列**: Celery + 数据库作为Broker
  - 选择理由: 基于实际服务器环境，使用数据库作为消息队列，避免额外服务依赖
- **ORM**: SQLAlchemy + Async
  - 选择理由: 功能强大，异步支持，社区活跃
- **认证**: JWT + bcrypt
  - 选择理由: 无状态，适合分布式，安全性好
- **文件处理**: FFmpeg, Pillow, moviepy
  - 选择理由: 功能完整，社区支持好
- **AI集成**: DeepSeek API
  - 选择理由: 根据需求文档要求，仅使用DeepSeek系列模型

#### 前端技术栈
- **框架**: React 18+
  - 选择理由: 生态丰富，组件化，性能好
- **语言**: TypeScript
  - 选择理由: 类型安全，减少错误，提高开发效率
- **构建工具**: Vite
  - 选择理由: 开发体验好，构建速度快
- **路由**: React Router v6
  - 选择理由: 功能完整，社区支持好
- **状态管理**: Zustand
  - 选择理由: 轻量级，API简单，性能好
- **UI组件**: Ant Design
  - 选择理由: 组件丰富，设计规范，文档完整
- **HTTP客户端**: Axios
  - 选择理由: 功能完整，拦截器支持，错误处理好

#### 运维技术栈
- **Web服务器**: Nginx
  - 选择理由: 高性能，反向代理，负载均衡
- **进程管理**: systemd (Linux) / PM2 (Node.js)
  - 选择理由: 系统集成好，管理方便
- **监控**: 自定义监控 + Prometheus + Grafana
  - 选择理由: 开源，功能完整，可视化好
- **日志**: 结构化日志 + ELK Stack (可选)
  - 选择理由: 搜索分析方便，可视化好
- **部署**: 裸机部署
  - 选择理由: 根据需求文档要求，注重程序健壮性

### 1.3 系统模块划分

#### 1.3.1 用户认证管理模块
- **核心功能**: 用户注册、登录、会话管理、密码管理
- **技术实现**: JWT令牌，bcrypt密码哈希，Redis会话存储
- **数据表**: users, user_sessions, login_history, password_history

#### 1.3.2 资讯抓取模块
- **核心功能**: RSS源管理，网页抓取，内容清洗，去重
- **技术实现**: aiohttp异步HTTP，Readability算法，BeautifulSoup解析
- **数据表**: rss_sources, articles, article_content, article_images

#### 1.3.3 视频处理模块
- **核心功能**: 视频上传，格式转换，分辨率调整，水印添加
- **技术实现**: FFmpeg视频处理，分片上传，断点续传
- **数据表**: videos, video_metadata, video_processing_tasks

#### 1.3.4 AI内容生成模块
- **核心功能**: 文案生成，语音合成，视频合成，流水线管理
- **技术实现**: DeepSeek API调用，Azure/Google TTS，视频合成引擎
- **数据表**: ai_templates, generation_tasks, generation_results

#### 1.3.5 发布管理模块
- **核心功能**: 平台管理，发布配置，任务队列，状态监控
- **技术实现**: 各平台API集成，Celery任务队列，Redis状态存储
- **数据表**: platforms, platform_accounts, publish_tasks, publish_results

#### 1.3.6 系统管理模块
- **核心功能**: 配置管理，监控告警，日志管理，备份恢复
- **技术实现**: 配置中心，监控代理，日志收集，备份脚本
- **数据表**: system_config, system_logs, backup_history

### 1.4 数据存储设计

#### 1.4.1 数据库设计原则
- **规范化设计**: 遵循第三范式，减少数据冗余
- **性能优化**: 合理使用索引，分区，分表
- **扩展性**: 考虑未来业务扩展，预留扩展字段
- **安全性**: 敏感数据加密存储，访问权限控制

#### 1.4.2 主要数据表设计

##### 用户相关表
```sql
-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(50),
    avatar_url VARCHAR(255),
    bio TEXT,
    email VARCHAR(255),
    phone VARCHAR(20),
    status VARCHAR(20) DEFAULT 'active',
    last_login_at TIMESTAMP,
    password_changed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户会话表
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    device_info JSONB,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 登录历史表
CREATE TABLE login_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    login_type VARCHAR(20),
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN,
    failure_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

##### 资讯相关表
```sql
-- RSS源表
CREATE TABLE rss_sources (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    url VARCHAR(500) NOT NULL,
    title VARCHAR(255),
    description TEXT,
    category VARCHAR(50),
    tags TEXT[],
    fetch_interval INTEGER DEFAULT 1800, -- 秒
    last_fetch_at TIMESTAMP,
    fetch_status VARCHAR(20),
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文章表
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES rss_sources(id),
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(500) NOT NULL,
    url VARCHAR(500),
    content_hash VARCHAR(64) UNIQUE,
    publish_date TIMESTAMP,
    fetch_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_length INTEGER,
    read_status VARCHAR(20) DEFAULT 'unread',
    quality_score INTEGER,
    review_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文章内容表
CREATE TABLE article_content (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) UNIQUE,
    content TEXT,
    clean_content TEXT,
    images JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

##### 视频相关表
```sql
-- 视频表
CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    file_size BIGINT,
    duration INTEGER, -- 秒
    resolution VARCHAR(20),
    video_codec VARCHAR(50),
    audio_codec VARCHAR(50),
    format VARCHAR(20),
    thumbnail_url VARCHAR(500),
    storage_path VARCHAR(500),
    status VARCHAR(20) DEFAULT 'uploading',
    privacy VARCHAR(20) DEFAULT 'private',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 视频元数据表
CREATE TABLE video_metadata (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) UNIQUE,
    title VARCHAR(100),
    description TEXT,
    tags TEXT[],
    category VARCHAR(50),
    author VARCHAR(50),
    copyright TEXT,
    custom_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 视频处理任务表
CREATE TABLE video_processing_tasks (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id),
    task_type VARCHAR(50),
    parameters JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    result_url VARCHAR(500),
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

##### AI生成相关表
```sql
-- AI模板表
CREATE TABLE ai_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    template_type VARCHAR(50),
    prompt_template TEXT,
    parameters JSONB,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 生成任务表
CREATE TABLE generation_tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    task_type VARCHAR(50),
    template_id INTEGER REFERENCES ai_templates(id),
    input_data JSONB,
    parameters JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    result_data JSONB,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 生成结果表
CREATE TABLE generation_results (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES generation_tasks(id) UNIQUE,
    content_type VARCHAR(50),
    content_url VARCHAR(500),
    content_metadata JSONB,
    quality_score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

##### 发布相关表
```sql
-- 平台表
CREATE TABLE platforms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    code VARCHAR(20) UNIQUE NOT NULL,
    api_config JSONB,
    limits JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 平台账号表
CREATE TABLE platform_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    platform_id INTEGER REFERENCES platforms(id),
    account_name VARCHAR(100),
    api_key VARCHAR(500),
    api_secret VARCHAR(500),
    access_token VARCHAR(500),
    refresh_token VARCHAR(500),
    token_expires_at TIMESTAMP,
    is_valid BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 发布任务表
CREATE TABLE publish_tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    content_id INTEGER, -- 视频ID或生成结果ID
    content_type VARCHAR(50),
    platform_ids INTEGER[], -- 多平台发布
    publish_config JSONB,
    schedule_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    results JSONB, -- 各平台发布结果
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 发布结果表
CREATE TABLE publish_results (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES publish_tasks(id),
    platform_id INTEGER REFERENCES platforms(id),
    platform_account_id INTEGER REFERENCES platform_accounts(id),
    platform_content_id VARCHAR(100),
    platform_url VARCHAR(500),
    status VARCHAR(20),
    metrics JSONB,
    error_message TEXT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 1.4.3 缓存设计
- **用户会话缓存**: Redis存储JWT令牌和会话信息
- **API响应缓存**: Redis缓存频繁查询的API响应
- **文件元数据缓存**: Redis缓存文件处理状态和元数据
- **任务队列**: Redis作为Celery的消息代理
- **限流计数器**: Redis实现API限流和登录限制

#### 1.4.4 文件存储设计
- **上传文件存储**: 本地磁盘存储，按用户ID分目录
- **处理中间文件**: 临时目录存储，处理完成后清理
- **生成结果文件**: 永久存储目录，支持CDN加速
- **备份文件**: 定期备份到备份存储

### 1.5 接口设计

#### 1.5.1 API设计原则
- **RESTful风格**: 使用HTTP方法表示操作，资源导向
- **版本控制**: API版本在URL中体现，如`/api/v1/`
- **认证授权**: 所有API需要JWT令牌认证
- **错误处理**: 统一错误响应格式，包含错误码和描述
- **文档自动生成**: 使用FastAPI自动生成OpenAPI文档

#### 1.5.2 主要API接口

##### 认证相关接口
```
POST   /api/v1/auth/register     用户注册
POST   /api/v1/auth/login        用户登录
POST   /api/v1/auth/refresh      刷新令牌
POST   /api/v1/auth/logout       用户登出
GET    /api/v1/auth/profile      获取用户信息
PUT    /api/v1/auth/profile      更新用户信息
POST   /api/v1/auth/password     修改密码
GET    /api/v1/auth/sessions     获取活跃会话
DELETE /api/v1/auth/sessions/{id} 终止会话
GET    /api/v1/auth/history      登录历史
```

##### 资讯抓取接口
```
GET    /api/v1/sources          获取RSS源列表
POST   /api/v1/sources          添加RSS源
GET    /api/v1/sources/{id}     获取RSS源详情
PUT    /api/v1/sources/{id}     更新RSS源
DELETE /api/v1/sources/{id}     删除RSS源
POST   /api/v1/sources/{id}/fetch 手动抓取
GET    /api/v1/articles         获取文章列表
GET    /api/v1/articles/{id}    获取文章详情
POST   /api/v1/articles/search  搜索文章
PUT    /api/v1/articles/{id}    更新文章状态
DELETE /api/v1/articles/{id}    删除文章
POST   /api/v1/articles/batch   批量操作
```

##### 视频处理接口
```
POST   /api/v1/videos/upload    上传视频（分片）
GET    /api/v1/videos           获取视频列表
GET    /api/v1/videos/{id}      获取视频详情
PUT    /api/v1/videos/{id}      更新视频信息
DELETE /api/v1/videos/{id}      删除视频
POST   /api/v1/videos/{id}/process 视频处理
GET    /api/v1/videos/{id}/progress 处理进度
GET    /api/v1/videos/{id}/preview 视频预览
POST   /api/v1/videos/batch     批量操作
```

##### AI生成接口
```
GET    /api/v1/ai/templates     获取模板列表
POST   /api/v1/ai/generate/text 生成文案
POST   /api/v1/ai/generate/voice 生成语音
POST   /api/v1/ai/generate/video 生成视频
GET    /api/v1/ai/tasks         获取生成任务列表
GET    /api/v1/ai/tasks/{id}    获取任务详情
POST   /api/v1/ai/workflows     创建工作流
POST   /api/v1/ai/workflows/{id}/execute 执行工作流
GET    /api/v1/ai/workflows/{id}/progress 工作流进度
```

##### 发布管理接口
```
GET    /api/v1/platforms        获取平台列表
POST   /api/v1/platforms/accounts 添加平台账号
GET    /api/v1/platforms/accounts 获取账号列表
PUT    /api/v1/platforms/accounts/{id} 更新账号
DELETE /api/v1/platforms/accounts/{id} 删除账号
POST   /api/v1/publish/tasks    创建发布任务
GET    /api/v1/publish/tasks    获取任务列表
GET    /api/v1/publish/tasks/{id} 获取任务详情
PUT    /api/v1/publish/tasks/{id} 更新任务
DELETE /api/v1/publish/tasks/{id} 取消任务
GET    /api/v1/publish/results  发布结果统计
```

#### 1.5.3 接口安全设计
- **HTTPS强制**: 所有接口必须使用HTTPS
- **JWT认证**: 使用JWT令牌进行身份验证
- **权限控制**: 基于角色的访问控制（RBAC）
- **API限流**: 基于IP和用户的API调用频率限制
- **输入验证**: 所有输入参数严格验证
- **输出过滤**: 敏感数据输出时过滤

### 1.6 基于VPS性能的任务队列设计

#### 1.6.1 核心设计原则：串行任务处理
基于远程VPS服务器（104.244.90.202）的性能限制，采用串行任务处理策略：

**设计背景**:
- 服务器类型: 远程VPS（典型配置：2-4核CPU，4-8GB内存）
- 性能限制: 视频处理是CPU/内存密集型，并发处理易导致系统崩溃
- 核心策略: **视频生成任务严格串行处理**，确保系统稳定性

#### 1.6.2 串行任务队列架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   任务生产者     │───▶│   Redis队列     │───▶│   串行消费者     │
│  (API服务)      │    │  (消息代理)     │    │  (Celery Worker)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │              ┌───────┘
         ▼                       ▼              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  任务状态更新    │    │  任务结果存储   │    │  进度反馈系统    │
│  (数据库)       │    │  (数据库/Redis) │    │  (WebSocket)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  用户等待时间    │
                    │     管理        │
                    └─────────────────┘
```

#### 1.6.3 任务类型和串行处理策略

**1. 严格串行处理的任务**（同一时间只处理一个）:
- **视频生成任务** (优先级: 高)
  - 包含: AI文案生成 + TTS语音合成 + 视频处理合成
  - 处理时间: 2-5分钟/视频（明确告知用户）
  - 队列限制: 最大10个排队任务
  - 用户提示: "预计等待时间: X分钟"

**2. 有限并发处理的任务**（允许2-3个并发）:
- **资讯抓取任务** (优先级: 中)
  - 网络I/O为主，CPU占用低
  - 并发限制: 2-3个任务同时执行
  - 监控: 网络带宽使用情况

**3. 外部API调用任务**（受外部限制）:
- **AI文案生成** (优先级: 高)
  - 受DeepSeek API速率限制
  - 建议并发: 2-3个请求
  - 超时设置: 60秒

**4. 后台维护任务**（低优先级串行）:
- **数据清理任务** (优先级: 低)
  - 系统空闲时执行
  - 不影响用户任务处理
  - 可随时中断

#### 1.6.4 基于实际服务器的轻量级任务队列配置

基于服务器104.244.90.202的实际情况，采用轻量级方案，避免Redis依赖：

```python
# Celery配置 - 使用数据库作为Broker（避免Redis依赖）
CELERY_BROKER_URL = 'db+postgresql://mediaagent:secure_password@localhost/media_agent'
CELERY_RESULT_BACKEND = 'db+postgresql://mediaagent:secure_password@localhost/media_agent'

# 串行处理配置 - 关键优化（基于VPS有限资源）
CELERYD_CONCURRENCY = 1  # 视频生成任务串行处理（必须）
CELERYD_MAX_TASKS_PER_CHILD = 5  # 每处理5个任务重启worker（内存有限）
CELERY_ACKS_LATE = True  # 任务执行完成后才确认
CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True  # 存储错误信息

# 任务超时配置（基于实际处理时间）
CELERY_TASK_TIME_LIMIT = 600  # 单个任务最长10分钟
CELERY_TASK_SOFT_TIME_LIMIT = 540  # 软超时9分钟
CELERY_TASK_ALWAYS_EAGER = False  # 生产环境必须为False

# 序列化配置（简化）
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'Asia/Shanghai'
CELERY_ENABLE_UTC = True

# 数据库Broker表结构（Celery自动创建）
# 1. celery_taskmeta - 任务结果存储
# 2. celery_tasksetmeta - 任务集存储
# 3. celery_worker - Worker状态
# 4. 其他相关表

# 轻量级队列管理（不使用复杂路由，简化处理）
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'default'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'

# 内存缓存替代方案（不使用Redis）
CACHE_CONFIG = {
    'backend': 'app.cache.database_cache.DatabaseCache',
    'default_ttl': 300,  # 默认5分钟缓存
    'max_entries': 100,  # 最大缓存条目数
}

# 数据库缓存实现示例
class DatabaseCache:
    """使用数据库表实现的简单缓存"""
    def __init__(self):
        self.table_name = 'system_cache'
        
    def get(self, key):
        # 从数据库缓存表查询
        pass
        
    def set(self, key, value, ttl=300):
        # 存储到数据库缓存表
        pass
        
    def delete(self, key):
        # 从数据库缓存表删除
        pass
```

#### 1.6.5 数据库队列表设计

```sql
-- Celery任务表（Celery自动管理）
-- 1. celery_taskmeta - 任务元数据
-- 2. celery_tasksetmeta - 任务集元数据

-- 自定义任务队列管理表
CREATE TABLE task_queue (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,  -- 任务类型: video_generation, publish, fetch
    task_data JSONB NOT NULL,        -- 任务数据
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
    priority INTEGER DEFAULT 0,      -- 优先级（0-高，1-中，2-低）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    result_data JSONB
);

-- 系统缓存表（替代Redis缓存）
CREATE TABLE system_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    cache_value TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引优化查询
CREATE INDEX idx_task_queue_status ON task_queue(status);
CREATE INDEX idx_task_queue_priority ON task_queue(priority, created_at);
CREATE INDEX idx_system_cache_expires ON system_cache(expires_at);
CREATE INDEX idx_system_cache_key ON system_cache(cache_key);
```

#### 1.6.6 轻量级任务调度器

```python
# 基于数据库的简单任务调度器
class DatabaseTaskScheduler:
    """使用数据库实现的轻量级任务调度器"""
    
    def __init__(self, db_session):
        self.db = db_session
        
    def enqueue_task(self, task_type, task_data, priority=0):
        """将任务加入队列"""
        task = TaskQueue(
            task_type=task_type,
            task_data=task_data,
            status='pending',
            priority=priority
        )
        self.db.add(task)
        self.db.commit()
        return task.id
    
    def get_next_task(self):
        """获取下一个待处理任务（串行处理）"""
        # 查找pending状态的任务，按优先级和创建时间排序
        task = self.db.query(TaskQueue).filter(
            TaskQueue.status == 'pending'
        ).order_by(
            TaskQueue.priority.asc(),
            TaskQueue.created_at.asc()
        ).first()
        
        if task:
            task.status = 'processing'
            task.started_at = datetime.utcnow()
            self.db.commit()
            
        return task
    
    def complete_task(self, task_id, result_data=None):
        """标记任务完成"""
        task = self.db.query(TaskQueue).get(task_id)
        if task:
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            task.result_data = result_data
            self.db.commit()
    
    def fail_task(self, task_id, error_message):
        """标记任务失败"""
        task = self.db.query(TaskQueue).get(task_id)
        if task:
            task.status = 'failed'
            task.completed_at = datetime.utcnow()
            task.error_message = error_message
            self.db.commit()
    
    def get_queue_stats(self):
        """获取队列统计信息"""
        stats = self.db.query(
            TaskQueue.status,
            func.count(TaskQueue.id).label('count')
        ).group_by(TaskQueue.status).all()
        
        return {status: count for status, count in stats}
```

#### 1.6.5 用户等待时间管理设计

**等待时间预估算法**:
```python
def estimate_wait_time(queue_position, avg_task_time=180):
    """
    估算用户等待时间
    queue_position: 在队列中的位置（0表示正在处理）
    avg_task_time: 平均任务处理时间（秒），默认3分钟
    """
    if queue_position == 0:
        return "正在处理中，预计剩余时间: 2-4分钟"
    elif queue_position == 1:
        return "下一个处理，预计等待: 0-2分钟"
    else:
        wait_minutes = (queue_position - 1) * avg_task_time / 60
        return f"排队中，当前有{queue_position-1}个任务在前，预计等待: {wait_minutes:.1f}分钟"
```

**进度反馈系统**:
```python
# 视频生成进度反馈
GENERATION_PROGRESS_STAGES = {
    'queued': {'progress': 0, 'message': '任务排队中...'},
    'ai_generating': {'progress': 10, 'message': 'AI生成文案中...'},
    'tts_processing': {'progress': 40, 'message': '语音合成中...'},
    'video_rendering': {'progress': 80, 'message': '视频合成中...'},
    'completed': {'progress': 100, 'message': '视频生成完成！'},
    'failed': {'progress': 0, 'message': '任务失败，请重试'},
}
```

**队列管理接口**:
```python
@router.get("/queue/status")
async def get_queue_status():
    """获取任务队列状态"""
    return {
        "video_generation": {
            "queue_length": get_queue_length("video_generation"),
            "current_task": get_current_task_info(),
            "estimated_wait_times": calculate_wait_times(),
            "system_load": get_system_load(),  # CPU,内存使用率
        }
    }
```
CELERY_TASK_ROUTES = {
    'tasks.high_priority.*': {'queue': 'high_priority'},
    'tasks.normal_priority.*': {'queue': 'normal_priority'},
    'tasks.low_priority.*': {'queue': 'low_priority'},
}

# 队列配置
CELERY_TASK_QUEUES = (
    Queue('high_priority', routing_key='high_priority'),
    Queue('normal_priority', routing_key='normal_priority'),
    Queue('low_priority', routing_key='low_priority'),
)
```

#### 1.6.4 任务监控和管理
- **任务状态跟踪**: 实时跟踪任务状态（pending, running, success, failed）
- **进度报告**: 长时间任务定期报告进度
- **失败重试**: 失败任务自动重试，可配置重试次数和间隔
- **超时处理**: 任务执行超时自动终止
- **资源限制**: 控制并发任务数量，防止资源耗尽

### 1.7 基于VPS性能的性能设计

#### 1.7.1 性能设计原则（VPS优化版）
- **串行处理优先**: 视频生成任务严格串行，确保系统稳定性
- **用户等待时间透明**: 明确告知用户预计等待时间，管理用户期望
- **资源使用保守**: 基于VPS有限资源，优化CPU、内存、磁盘使用
- **渐进式扩展**: 从串行开始，根据实际需求逐步扩展
- **监控驱动优化**: 基于系统监控数据动态调整性能参数

#### 1.7.2 基于VPS性能的关键指标

**1. 任务队列性能指标**:
- **视频生成串行处理**: 同一时间只处理一个视频生成任务
- **队列容量限制**: 最大10个排队任务，避免无限等待
- **用户等待时间预期**:
  - 单视频生成: 2-5分钟（明确告知用户）
  - 排队等待: 实时计算并显示预计等待时间
  - 超时处理: 10分钟自动取消，释放资源
- **进度反馈实时性**: 每个阶段完成立即更新进度（WebSocket推送）

**2. 系统响应性能指标**:
- **API响应时间**:
  - 认证接口: < 500ms（保证登录体验）
  - 数据查询: < 1s（简单查询），< 3s（复杂查询）
  - 文件上传: 立即响应，后台异步处理
- **页面加载时间**:
  - 首屏加载: < 2s（优化静态资源）
  - 操作响应: < 300ms（感知流畅）
  - 进度更新: 实时（WebSocket推送）
- **并发处理能力**:
  - 并发用户数: 20-50个同时在线用户
  - 并发任务: 视频生成串行，资讯抓取2-3个并发
  - 连接数限制: Nginx worker_connections: 512

**3. 资源使用性能指标**:
- **CPU使用**:
  - 正常负载: < 70%（保留系统响应能力）
  - 视频处理期间: 可能达到80-90%（短期）
  - 警戒线: > 80%持续5分钟告警
- **内存使用**:
  - 基础服务: PostgreSQL 1-2GB，Redis 500MB-1GB
  - 视频处理: 1-2GB缓冲区
  - 警戒线: > 80%内存使用率告警
- **磁盘I/O**:
  - 存储空间: 监控使用率，< 90%为安全线
  - 临时文件: 任务完成后立即清理
  - 视频文件: 定期归档或清理过期文件
- **网络I/O**:
  - 带宽监控: 避免视频上传/下载占用全部带宽
  - API调用: 优化请求频率，避免被限流

#### 1.7.3 针对VPS的性能优化策略

**1. 数据库优化（针对VPS有限资源）**:
```sql
-- PostgreSQL配置优化（VPS环境）
shared_buffers = 256MB        -- 共享缓冲区，建议系统内存的25%
work_mem = 16MB              -- 每个查询工作内存
maintenance_work_mem = 64MB   -- 维护操作内存
effective_cache_size = 1GB    -- 查询规划器假设的缓存大小

-- 关键表索引设计
CREATE INDEX idx_articles_created_at ON articles(created_at DESC);
CREATE INDEX idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX idx_user_videos_user_id ON user_videos(user_id);
```

**2. 缓存优化（轻量级内存缓存 + 数据库缓存）**:
```python
# 多级缓存策略（不使用Redis）
CACHE_CONFIG = {
    'user_sessions': {'ttl': 3600, 'max_size': 100},      # 用户会话1小时（内存缓存）
    'api_responses': {'ttl': 300, 'max_size': 50},        # API响应5分钟（内存缓存）
    'task_results': {'ttl': 1800, 'storage': 'database'}, # 任务结果30分钟（数据库存储）
    'system_config': {'ttl': 86400, 'storage': 'database'}, # 系统配置24小时（数据库存储）
}

# 内存缓存实现（简单LRU缓存）
import threading
from collections import OrderedDict
from datetime import datetime, timedelta

class MemoryCache:
    """简单的内存缓存实现（LRU策略）"""
    def __init__(self, max_size=100):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.lock = threading.RLock()
        
    def get(self, key):
        with self.lock:
            if key not in self.cache:
                return None
                
            value, expires_at = self.cache[key]
            if expires_at and datetime.now() > expires_at:
                del self.cache[key]
                return None
                
            # 移动到最近使用位置
            self.cache.move_to_end(key)
            return value
    
    def set(self, key, value, ttl=None):
        with self.lock:
            expires_at = None
            if ttl:
                expires_at = datetime.now() + timedelta(seconds=ttl)
                
            self.cache[key] = (value, expires_at)
            self.cache.move_to_end(key)
            
            # 如果超过最大大小，删除最旧的条目
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    def delete(self, key):
        with self.lock:
            if key in self.cache:
                del self.cache[key]

# 数据库缓存实现
class DatabaseCache:
    """使用数据库实现的持久化缓存"""
    def __init__(self, db_session):
        self.db = db_session
        
    def get(self, key):
        from app.models import SystemCache
        from sqlalchemy import and_
        
        cache_entry = self.db.query(SystemCache).filter(
            and_(
                SystemCache.cache_key == key,
                SystemCache.expires_at > datetime.utcnow()
            )
        ).first()
        
        return cache_entry.cache_value if cache_entry else None
    
    def set(self, key, value, ttl=300):
        from app.models import SystemCache
        
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        # 更新或插入
        cache_entry = self.db.query(SystemCache).filter(
            SystemCache.cache_key == key
        ).first()
        
        if cache_entry:
            cache_entry.cache_value = value
            cache_entry.expires_at = expires_at
            cache_entry.updated_at = datetime.utcnow()
        else:
            cache_entry = SystemCache(
                cache_key=key,
                cache_value=value,
                expires_at=expires_at
            )
            self.db.add(cache_entry)
        
        self.db.commit()
    
    def delete(self, key):
        from app.models import SystemCache
        
        self.db.query(SystemCache).filter(
            SystemCache.cache_key == key
        ).delete()
        self.db.commit()

# 缓存穿透防护（使用数据库缓存）
def get_with_penetration_protection(key, fetch_func, ttl=300, cache_type='database'):
    """带缓存穿透防护的获取函数（不使用Redis）"""
    if cache_type == 'memory':
        cache = memory_cache
    else:
        cache = database_cache
        
    value = cache.get(key)
    if value is not None:
        return value if value != '__NULL__' else None
    
    # 缓存未命中，获取数据
    value = fetch_func()
    if value is None:
        cache.set(key, '__NULL__', ttl)  # 缓存空值
    else:
        cache.set(key, value, ttl)
    return value
```

**3. 视频处理优化（FFmpeg配置优化）**:
```bash
# FFmpeg优化配置 - 限制资源使用
# 视频转码（限制CPU使用）
ffmpeg -threads 2 -i input.mp4 -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k output.mp4

# 视频合成（优化内存使用）
ffmpeg -max_muxing_queue_size 1024 -i audio.mp3 -i video.mp4 -c:v copy -c:a aac -shortest output.mp4

# 分辨率调整（减少处理负载）
ffmpeg -i input.mp4 -vf "scale=1280:720" -c:v libx264 -preset faster -c:a copy output_720p.mp4
```

**4. 网络请求优化**:
```python
# HTTP客户端配置优化
HTTP_CLIENT_CONFIG = {
    'timeout': 30,           # 请求超时30秒
    'max_retries': 3,        # 最大重试3次
    'backoff_factor': 0.5,   # 退避因子
    'pool_connections': 10,  # 连接池大小
    'pool_maxsize': 20,      # 最大连接数
}

# DeepSeek API调用优化
DEEPSEEK_API_CONFIG = {
    'timeout': 60,           # AI生成可能较慢
    'max_tokens': 500,       # 限制生成长度
    'temperature': 0.7,      # 平衡创意与稳定性
    'retry_on_failure': True,
}
```

**5. 前端性能优化**:
```nginx
# Nginx配置优化（VPS环境）
worker_processes 2;                     # 根据CPU核心数设置
worker_connections 512;                 # 每个worker最大连接数
keepalive_timeout 65;                   # 保持连接超时
client_max_body_size 500M;              # 最大上传文件大小

# 静态资源优化
location ~* \.(js|css|png|jpg|jpeg|gif|ico)$ {
    expires 1h;
    add_header Cache-Control "public, immutable";
}

# Gzip压缩
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;
```

**6. 系统监控与自动调整**:
```python
# 系统负载监控
def monitor_system_load():
    """监控系统负载，动态调整任务处理"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent
    
    if cpu_percent > 80 or memory_percent > 80:
        # 高负载，降低并发
        celery_app.conf.update(CELERYD_CONCURRENCY=1)
        log_warning(f"高负载告警: CPU={cpu_percent}%, 内存={memory_percent}%")
    elif cpu_percent < 30 and memory_percent < 50:
        # 低负载，可适当增加并发
        celery_app.conf.update(CELERYD_CONCURRENCY=2)
    
    return {'cpu': cpu_percent, 'memory': memory_percent}
```

### 1.8 安全设计

#### 1.8.1 认证安全
- **密码安全**: bcrypt加盐哈希，密码强度验证
- **会话安全**: JWT签名验证，令牌定期刷新
- **登录安全**: 登录失败限制，异地登录检测
- **多因素认证**: 支持二次验证（可选）

#### 1.8.2 授权安全
- **RBAC模型**: 基于角色的访问控制
- **权限验证**: 所有操作权限实时验证
- **数据权限**: 行级和列级数据访问控制
- **操作审计**: 敏感操作完整记录

#### 1.8.3 数据安全
- **传输安全**: HTTPS强制使用，TLS 1.2+
- **存储安全**: 敏感数据加密存储
- **数据脱敏**: 日志和导出数据自动脱敏
- **备份安全**: 备份数据加密存储

#### 1.8.4 应用安全
- **输入验证**: SQL注入防护，XSS防护
- **输出编码**: 输出数据适当编码
- **CSRF防护**: Token验证防护
- **文件上传**: 文件类型验证，病毒扫描

### 1.9 基于VPS服务器的部署设计

#### 1.9.1 VPS部署架构（单服务器部署）
基于远程VPS服务器（104.244.90.202）的单服务器部署架构：

```
┌─────────────────────────────────────────────────────────────┐
│                    VPS服务器 (104.244.90.202)                │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                 Web服务层 (Nginx)                    │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │ 前端静态服务 (端口:8001)                      │  │  │
│  │  │ • React应用部署                              │  │  │
│  │  │ • 静态资源服务                               │  │  │
│  │  │ • Gzip压缩，缓存优化                         │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │ 反向代理服务 (端口:9090)                      │  │  │
│  │  │ • FastAPI应用代理                            │  │  │
│  │  │ • WebSocket支持                              │  │  │
│  │  │ • 负载均衡（未来扩展）                        │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                 应用服务层                           │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │ FastAPI后端服务 (systemd: media-agent-backend) │  │  │
│  │  │ • RESTful API接口                            │  │  │
│  │  │ • WebSocket实时通信                          │  │  │
│  │  │ • 用户认证和授权                             │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │ Celery任务队列 (systemd: media-agent-worker)  │  │  │
│  │  │ • 视频生成任务（串行处理）                    │  │  │
│  │  │ • 资讯抓取任务（有限并发）                    │  │  │
│  │  │ • 任务状态监控                               │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                 数据服务层                           │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │ PostgreSQL数据库 (端口:5432)                 │  │  │
│  │  │ • 用户数据、内容数据、任务数据               │  │  │
│  │  │ • 连接池优化（max_connections=50）           │  │  │
│  │  │ • 定期备份（pg_dump + cron）                 │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │ 轻量级缓存服务                               │  │  │
│  │  │ • 内存缓存（LRU策略，最大100条目）            │  │  │
│  │  │ • 数据库缓存（system_cache表）                │  │  │
│  │  │ • Celery使用数据库作为Broker                  │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                 存储服务层                           │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │ 文件存储系统                                 │  │  │
│  │  │ • 上传目录: /data/uploads                    │  │  │
│  │  │ • 输出目录: /data/outputs                    │  │  │
│  │  │ • 临时目录: /data/temp                       │  │  │
│  │  │ • 定期清理（find + cron）                    │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### 1.9.2 VPS部署要求
基于实际服务器 104.244.90.202 的部署要求：

**1. 服务器规格要求**:
- **VPS配置**: 最低2核CPU，4GB内存，50GB SSD（推荐4核8GB 100GB SSD）
- **操作系统**: Ubuntu 20.04/22.04 LTS（已部署）
- **网络环境**: 公网IP，开放端口22(SSH)、8001(前端)、9090(API)
- **域名解析**: 可选，建议配置域名和SSL证书

**2. 软件依赖要求**:
```bash
# 系统工具
sudo apt update
sudo apt install -y python3.9 python3-pip postgresql redis-server nginx
sudo apt install -y ffmpeg imagemagick ghostscript  # 多媒体处理

# Python依赖（通过requirements.txt安装）
pip3 install -r requirements.txt

# 系统服务配置
sudo systemctl enable postgresql redis-server nginx
```

**3. 目录结构要求**:
```
/opt/media-agent/           # 项目根目录
├── backend/               # 后端代码
├── frontend/              # 前端代码
├── docs/                  # 文档
├── scripts/               # 部署脚本
└── data/                  # 数据目录（需要额外创建）
    ├── uploads/           # 用户上传文件
    ├── outputs/           # 生成输出文件
    └── temp/              # 临时文件
```

**4. 安全要求**:
- **防火墙配置**: `ufw allow 22,8001,9090`
- **SSH安全**: 禁用root登录，使用密钥认证
- **服务隔离**: 使用非root用户运行应用服务
- **定期更新**: 系统安全更新，依赖包更新
- **日志监控**: 系统日志和应用日志监控

#### 1.9.3 VPS部署流程（针对104.244.90.202）

**阶段一：服务器环境准备**
```bash
# 1. 系统更新和基础工具安装
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git htop tmux

# 2. 创建应用用户和目录
sudo useradd -m -s /bin/bash mediaagent
sudo mkdir -p /opt/media-agent
sudo chown -R mediaagent:mediaagent /opt/media-agent

# 3. 配置数据目录
sudo mkdir -p /data/{uploads,outputs,temp}
sudo chown -R mediaagent:mediaagent /data
sudo chmod 755 /data
```

**阶段二：依赖服务安装（简化版，避免Redis）**
```bash
# 1. 安装PostgreSQL（必需）
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql -c "CREATE USER mediaagent WITH PASSWORD 'secure_password';"
sudo -u postgres psql -c "CREATE DATABASE media_agent OWNER mediaagent;"

# 2. 安装Nginx（必需）
sudo apt install -y nginx
sudo systemctl enable nginx

# 3. 安装FFmpeg（必需，视频处理）
sudo apt install -y ffmpeg

# 注意：不安装Redis，使用数据库作为Celery Broker
# 注意：不安装额外缓存服务，使用内存缓存+数据库缓存
```

**阶段三：应用部署配置**
```bash
# 1. 克隆项目代码
cd /opt/media-agent
git clone https://github.com/xuzixiao198964-boop/media-agent.git .

# 2. Python环境配置
sudo apt install -y python3.9 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 3. 环境变量配置
cp backend/.env.example backend/.env
# 编辑backend/.env，配置数据库连接、API密钥等

# 4. 数据库迁移
cd backend
alembic upgrade head
```

**阶段四：服务配置和启动**
```bash
# 1. Nginx配置
sudo cp /opt/media-agent/scripts/nginx.conf /etc/nginx/sites-available/media-agent
sudo ln -s /etc/nginx/sites-available/media-agent /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 2. Systemd服务配置
# backend服务
sudo cp /opt/media-agent/scripts/media-agent-backend.service /etc/systemd/system/
# worker服务（串行处理配置）
sudo cp /opt/media-agent/scripts/media-agent-worker.service /etc/systemd/system/

# 3. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable media-agent-backend media-agent-worker
sudo systemctl start media-agent-backend media-agent-worker

# 4. 前端构建和部署
cd /opt/media-agent/frontend
npm install
npm run build
sudo cp -r dist/* /var/www/html/media-agent/
```

**阶段五：监控和备份配置**
```bash
# 1. 系统监控脚本
sudo cp /opt/media-agent/scripts/monitor.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/monitor.sh

# 2. 日志轮转配置
sudo cp /opt/media-agent/scripts/logrotate.conf /etc/logrotate.d/media-agent

# 3. 数据库备份（每日凌晨2点）
sudo crontab -e
# 添加：0 2 * * * pg_dump -U mediaagent media_agent > /backup/media_agent_$(date +\%Y\%m\%d).sql

# 4. 临时文件清理（每小时）
# 添加：0 * * * * find /data/temp -type f -mmin +60 -delete
```

**阶段六：健康检查和验证**
```bash
# 1. 服务状态检查（简化，不检查Redis）
sudo systemctl status media-agent-backend
sudo systemctl status media-agent-worker
sudo systemctl status nginx
sudo systemctl status postgresql

# 2. 端口监听检查（简化，不检查6379）
sudo netstat -tlnp | grep -E '8001|9090|5432'

# 3. API健康检查
curl http://localhost:9090/health
curl http://localhost:9090/api/v1/status

# 4. 前端访问测试
curl -I http://localhost:8001

# 5. 任务队列测试（使用数据库作为Broker）
# 创建测试任务，验证串行处理功能
# 检查数据库中的task_queue表状态

# 6. 数据库缓存测试
# 检查system_cache表功能是否正常
```

#### 1.9.4 部署验证清单（简化版，无Redis）
- [ ] 所有服务正常运行（systemctl status检查）
- [ ] 端口监听正常（8001前端, 9090API, 5432数据库）
- [ ] API接口可访问（/health, /api/v1/status）
- [ ] 前端页面可访问（http://104.244.90.202:8001）
- [ ] 数据库连接正常（可执行简单查询）
- [ ] 数据库缓存功能正常（system_cache表可读写）
- [ ] 任务队列功能正常（task_queue表可操作）
- [ ] 文件上传功能正常（可上传测试文件）
- [ ] 视频生成任务可提交（串行处理验证）
- [ ] 用户等待时间提示正常（进度反馈测试）
- [ ] 内存缓存功能正常（简单键值存取测试）
- [ ] 系统监控脚本运行正常（资源使用监控）

### 1.10 监控和运维设计

#### 1.10.1 监控指标
- **系统监控**: CPU，内存，磁盘，网络
- **服务监控**: 服务状态，端口监听，进程状态
- **业务监控**: 用户活跃度，任务处理量，成功率
- **性能监控**: 响应时间，并发数，错误率

#### 1.10.2 日志管理
- **访问日志**: 记录所有API访问
- **业务日志**: 记录关键业务操作
- **错误日志**: 记录系统错误和异常
- **审计日志**: 记录敏感操作

#### 1.10.3 告警策略
- **紧急告警**: 服务不可用，数据丢失
- **重要告警**: 性能下降，错误率升高
- **警告告警**: 资源使用率高，队列积压

#### 1.10.4 备份恢复
- **数据备份**: 定期全量和增量备份
- **配置备份**: 配置文件备份
- **恢复测试**: 定期恢复演练
- **灾难恢复**: 完整的灾难恢复方案

## 2. 模块设计

### 2.1 用户认证管理模块设计

#### 2.1.1 模块架构
```
┌─────────────────────────────────────────┐
│          用户认证管理模块                 │
├─────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ 注册服务 │  │ 登录服务 │  │ 会话服务 │ │
│  └─────────┘  └─────────┘  └─────────┘ │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │密码服务 │  │权限服务 │  │审计服务 │ │
│  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────┘
         │               │               │
         ▼               ▼               ▼
┌─────────────────────────────────────────┐
│           数据访问层                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ 用户表  │  │会话表   │  │历史表   │ │
│  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────┘
```

#### 2.1.2 核心类设计
```python
# 用户服务类
class UserService:
    def register(username: str, password: str) -> User
    def login(username: str, password: str) -> AuthToken
    def logout(user_id: int, session_token: str)
    def change_password(user_id: int, old_password: str, new_password: str)
    def update_profile(user_id: int, profile_data: dict)
    def get_active_sessions(user_id: int) -> List[Session]
    def terminate_session(user_id: int, session_id: int)

# 认证服务类
class AuthService:
    def validate_credentials(username: str, password: str) -> bool
    def generate_token(user_id: int) -> AuthToken
    def refresh_token(refresh_token: str) -> AuthToken
    def validate_token(token: str) -> bool
    def revoke_token(token: str)

# 密码服务类
class PasswordService:
    def hash_password(password: str) -> str
    def verify_password(password: str, hashed: str) -> bool
    def validate_password_strength(password: str) -> bool
    def check_password_history(user_id: int, password: str) -> bool
```

---

## 文档总结

### 文档更新说明
本概要设计文档已根据需求文档（版本1.3）和实际服务器情况进行更新，主要调整包括：

#### 1. 核心架构调整
- **服务器环境**: 从通用服务器调整为远程VPS服务器（104.244.90.202）
- **性能策略**: 从并发处理调整为**串行任务处理**策略
- **用户期望**: 增加**用户等待时间管理**和预期设置
- **技术栈简化**: **去掉Redis依赖**，使用轻量级替代方案

#### 2. 关键设计优化
- **任务队列设计**: 视频生成任务严格串行，避免CPU/内存过载
- **性能指标**: 基于VPS性能重新定义关键性能指标
- **部署架构**: 针对单VPS服务器的优化部署方案
- **配置优化**: 提供具体的FFmpeg、Nginx、数据库优化配置
- **架构简化**: **使用数据库作为Celery Broker**，避免Redis依赖
- **缓存优化**: **内存缓存 + 数据库缓存**替代Redis缓存

#### 3. 实际实施建议
- **串行处理配置**: Celery `CELERYD_CONCURRENCY = 1`
- **等待时间算法**: 基于队列位置和平均处理时间估算
- **进度反馈系统**: 分阶段实时进度更新
- **资源监控**: 基于系统负载动态调整任务处理
- **轻量级缓存**: 实现内存缓存和数据库缓存
- **数据库队列**: 使用数据库作为任务队列存储

#### 4. 部署实施指导
- **VPS环境准备**: 针对104.244.90.202的具体部署步骤
- **服务配置**: systemd服务配置，Nginx反向代理
- **健康检查**: 完整的部署验证清单（简化版，无Redis）
- **监控备份**: 系统监控和数据库备份方案
- **依赖简化**: **不安装Redis**，减少资源占用和部署复杂度

### 设计原则总结
1. **稳定性优先**: 在VPS有限资源下，确保系统稳定运行
2. **用户体验透明**: 明确告知用户等待时间，管理用户期望
3. **资源优化**: 基于监控数据动态调整资源使用
4. **渐进扩展**: 从串行开始，根据需求逐步扩展能力

### 后续工作建议
1. **详细设计**: 基于本概要设计进行各模块详细设计
2. **代码实现**: 按照串行处理策略实现任务队列
3. **部署测试**: 在104.244.90.202服务器上进行部署测试
4. **性能调优**: 基于实际运行数据进行性能优化
5. **监控完善**: 完善系统监控和告警机制

**本概要设计文档为Media Agent项目在VPS环境下的实施提供了完整的技术指导，确保项目在有限资源下的稳定运行和良好用户体验。**

####