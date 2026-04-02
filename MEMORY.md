# MEMORY.md（本仓库：media-agent）

## 项目概述

**media-agent** 是一个集成媒体资讯处理和小说转视频的全栈系统，基于 React + FastAPI 架构。

### 核心功能
- 用户认证与权限管理（JWT 双令牌）
- 资讯抓取 → AI 文案 → TTS → 视频合成流水线
- 小说转视频流水线（脚本生成 → 提示词评审 → 图片生成 → 图片评审 → 视频合成）
- 图片提示词 AI 评审（DeepSeek Chat）
- 图片质量 AI 评审（Gemini Vision / DeepSeek / 规则三级降级）
- 任务调度与监控（Celery + PostgreSQL Broker）

### 技术栈
- **前端**: React 18 + TypeScript + Vite
- **后端**: FastAPI (Python) + SQLAlchemy + Celery
- **数据库**: PostgreSQL（主存 + Celery Broker，无 Redis）
- **AI 服务**: DeepSeek（文案/评审）、Fish Audio（TTS）、SiliconFlow（图片/I2V）、Edge TTS（备用）
- **部署**: 裸机 VPS，systemd 服务管理

---

## 当前部署状态（2026-04-01 最新）

### 生产环境
- **服务器**: 104.244.90.202（单核 2GB VPS）
- **端口**: **80**（唯一对外端口，旧 9000/9090 已停）
- **服务**: systemd `media-agent`，3 个 Celery workers
- **目录**: `/opt/media-agent`
- **数据库**: PostgreSQL (postgres:media_agent_pg@localhost/media_agent)
- **磁盘**: 19G 总计，使用率 95%（需注意清理）

### 访问地址
- 前端: `http://104.244.90.202/`
- API 文档: `http://104.244.90.202/docs`
- 健康检查: `http://104.244.90.202/health`

### 旧服务（已停止）
- ~~ai-novel-agent: 端口 9000~~ 已停
- ~~media-agent-old: 端口 9090~~ 已停
- 所有服务器资源独属 media-agent

---

## v1.1 图片评审流水线（2026-04-01 新增）

### 流水线顺序
```
脚本生成 → 脚本审核 → 提示词评审(AI) → 图片生成 → 图片评审(AI) → 视频生成 → 成片审核
```

### 后端 API 端点
- `POST /api/v1/novel/chapters/{id}/review-prompts` — AI 评审提示词
- `POST /api/v1/novel/chapters/{id}/approve-prompts` — 人工通过提示词
- `POST /api/v1/novel/chapters/{id}/generate-images` — 生成场景图片
- `POST /api/v1/novel/chapters/{id}/review-images` — AI 评审图片
- `POST /api/v1/novel/chapters/{id}/approve-images` — 人工通过图片

### 数据库新字段
- `novel_chapters`: prompt_status, prompt_review_notes, prompt_review_round, image_status, image_review_notes, image_review_round, image_prompts
- `chapter_reviews`: reviewer_type, review_detail

### 前端适配
- `NovelChapterPage.tsx`: 五步流水线按钮、四状态卡片、场景图片 Tab、审核记录支持 prompt/image
- `NovelProjectDetailPage.tsx`: 章节表格增加提示词/图片状态列
- `StatusLabel` 组件支持 script/prompt/image/video 四种类型

---

## 认证系统

- **简化认证**: 仅用户名 + 密码
- **双令牌**: access_token (30分钟) + refresh_token (7天)
- **会话限制**: 最多 3 个并发会话
- **安全**: 验证码限流、登录失败锁定

---

## 视频生成系统

### 7 条生成路径（资讯类）
1. P1: 资讯+TTS ✅
2. P2: 资讯+TTS+VideoRetalk ⚠️（需人脸视频）
3. P3: DeepSeek 文案 ✅
4. P4: 直接粘贴口播 ✅
5. P5: TTS+BGM ✅
6. P6: 纯 BGM ✅
7. P7: Mock 发布 ✅

### 小说转视频流水线
- 多阶段：解析 → 脚本 → TTS → 图片 → I2V → 合成
- AI 服务：DeepSeek(脚本) + Fish Audio(TTS) + SiliconFlow Kolors(图) + Wan2.2(I2V)
- 降级：SiliconFlow → Seedance → FFmpeg Ken Burns

---

## 测试状态

### 后端单元测试: 21/21 PASSED
- test_image_review: 8 项（规则评审、调度逻辑、视频门控）
- test_models: 7 项（新字段、默认值）
- test_prompt_review: 6 项（评审通过/失败/API错误/重生成）

### E2E 验证: 通过
- 微小说 chapter 223 全流程
- 资讯视频生成

---

## 重要经验

1. **SFTP 中文文件名**: paramiko SFTP 支持 UTF-8 中文路径，但需确保远程目录存在
2. **PostgreSQL 作为 Celery Broker**: 省 Redis 内存，适合小 VPS
3. **图片评审三级降级**: Gemini Vision → DeepSeek(文本对比) → 规则(文件大小/分辨率)
4. **前端门控**: 视频生成按钮仅在 image_status=approved 时显示
5. **服务器磁盘告急**: 95% 使用率，生成视频后需及时清理
6. **PowerShell 语法**: 不支持 `&&`，用 `;` 代替

---

## API Keys（已配置在服务器 .env）
- DeepSeek: sk-9fcc8f6d0ce94fdbbe66b152b7d3e485
- 服务器 SSH: root@104.244.90.202:22 / v9wSxMxg92dp

---

## 文档体系
- 需求文档 v1.1
- 概要设计文档 v1.1（含前端 UI 设计）
- 详细设计文档（含第 11 节前端详细设计）
- 单元测试文档 v1.1（含前端组件测试）
- 集成测试文档 v1.1（含前端 E2E 测试）
- 全部在 `docs/` 目录，已提交 Git

---

## 更新记录
- 2026-03-28: 首次创建，整合项目历史与状态
- 2026-03-28 晚: 同步全路径视频生成测试结果
- 2026-03-29: 记忆同步验证
- 2026-04-01: **重大更新** — 同步 v1.1 图片评审流水线、端口迁移至 80、前端适配、旧服务停止、文档体系全面更新
