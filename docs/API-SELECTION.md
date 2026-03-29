# MediaAgent 项目需求与 API 选择

本文档对应 **MediaAgent** 的「资讯处理、配音、字幕、剪辑、特效、发布」能力，给出**建议接入的 API 类型**、**如何创建密钥/应用**以及**官方文档地址**。  
**安全提示**：任何密钥只应保存在服务器环境变量或加密存储中，勿提交到 Git，勿在聊天中明文发送。

---

## 一、建议接入的 API 种类（与需求映射）

| 能力 | 建议 API / 产品 | 说明 |
|------|-----------------|------|
| 资讯理解、脚本、要点提取、标题标签 | **DeepSeek**（已有） | 中文与长文本性价比高，适合摘要、口播稿、话题词。 |
| 多模态（图文理解、部分视频理解）、批量推理 | **Google Gemini**（AI Studio） | 与 DeepSeek 互补，适合配图说明、多模态理解与结构化输出。 |
| 高质量配音 / 语音识别 | **OpenAI GPT-4o 系列 TTS / Transcribe** | TTS 可控性强，适合短视频口播；需合规使用与区域政策考量。 |
| （可选）文生/图生视频、高画质镜头 | **Google Veo** / **OpenAI Sora** / **快手可灵** | 成本高、审核与配额严，适合作为「高质量片段」备选而非唯一路径。 |
| 剪辑、比例、时长、字幕烧录、简单转场 | **本地 FFmpeg**（非云 API） | 成本低、可控；本项目流水线以 FFmpeg 为主实现「平台规则适配」中的画幅与时长。 |
| 抖音、快手、视频号、TikTok 自动发布 | **各平台开放平台** | 均需企业/开发者资质、应用审核与 OAuth；无统一「一键全网」官方接口，需分平台对接。 |

**综合选型结论（与需求文档一致、可落地）：**

1. **必留**：DeepSeek — 文本侧主力。  
2. **建议补充**：Google Gemini（AI Studio Key）— 多模态与结构化。  
3. **建议补充**：OpenAI — TTS/STT 提升口播与字幕体验。  
4. **可选高成本**：Veo / Sora / 可灵 — 按单条预算启用。  
5. **发布**：在取得各平台正式权限前，使用本项目的**模拟发布**完成联调；真发布再逐个接开放平台 SDK/API。

---

## 二、各厂家：密钥创建方式与官方地址

### 1. DeepSeek（已有）

- **控制台**： [DeepSeek 开放平台](https://platform.deepseek.com/)  
- **创建方式**：注册/登录 → API Keys → 创建密钥。  
- **文档**： [DeepSeek API 文档](https://api-docs.deepseek.com/)

### 2. Google Gemini（推荐补充）

- **申请 API Key**： [Google AI Studio](https://aistudio.google.com/apikey)  
- **文档**： [Gemini API 文档](https://ai.google.dev/gemini-api/docs)  
- **说明**：AI Studio Key 适合开发与中小规模；大规模与合规可迁移 [Vertex AI](https://cloud.google.com/vertex-ai/docs/start/introduction-unified-platform)。

### 3. Google Veo（可选，视频生成）

- **通常路径**：通过 Google Cloud / Vertex AI 等产品线开通（以官方当前说明为准）。  
- **文档入口**：关注 [Google AI for Developers](https://ai.google.dev/) 中视频生成相关更新。

### 4. OpenAI（Sora / GPT-4o 语音等）

- **控制台**： [OpenAI Platform](https://platform.openai.com/)  
- **API Keys**： [API keys](https://platform.openai.com/api-keys)  
- **文档**： [OpenAI API Reference](https://platform.openai.com/docs/api-reference)  
- **说明**：Sora 是否对你的账号开放以控制台为准；TTS/ASR 可优先用于配音与字幕。

### 5. 快手可灵（可选）

- **产品与文档**： [可灵 / Kling 开发者文档（国际站示例）](https://app.klingai.com/global/dev/document-api)  
- **国内品牌站**： [可灵 Kling](https://kling.kuaishou.com/)（按页面指引进入开发者/API 入口）。  
- **创建方式**：一般为企业/开发者认证后在控制台创建 **AccessKey / Secret**（以官方最新流程为准）。

### 6. 短视频平台「自动发布」（需单独对接）

以下为**官方生态入口**（实际发视频接口权限以审核结果为准）：

| 平台 | 开放平台入口（示例） |
|------|----------------------|
| 抖音 | [抖音开放平台](https://open.douyin.com/) |
| TikTok | [TikTok for Developers](https://developers.tiktok.com/) |
| 快手 | [快手开放平台](https://open.kuaishou.com/) |
| 微信视频号 | 通常通过微信公众平台 / 服务商体系接入，无简单公开「个人上传短视频」统一 API |

本项目已实现 **Mock 发布器**（验证流程与状态回写）；接入真实平台时在 `backend/app/services/publisher.py` 扩展即可。

---

## 三、环境变量命名（与本项目 `.env` 对齐）

| 变量 | 用途 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek 文本生成 |
| `GEMINI_API_KEY` | Google Gemini（若未配置则跳过多模态增强） |
| `OPENAI_API_KEY` | OpenAI TTS（若未配置则回退 Edge TTS 或仅字幕） |
| `OPENAI_TTS_MODEL` | 可选，默认 `gpt-4o-mini-tts` |
| `PUBLISH_MODE` | `mock`（默认）或后续扩展 `douyin` 等 |

---

## 四、成本与风险（简要）

- **DeepSeek + Gemini Flash 级模型**：适合高频摘要与结构化，成本相对可控。  
- **OpenAI TTS**：按字符/分钟计费，建议加缓存与同文案复用。  
- **Veo / Sora / 可灵**：按秒或按条计费高，建议任务级配额与失败重试。  
- **平台自动发布**：政策与版权风险高，务必做**发布前合规检测**（本项目保留钩子，默认规则可配置）。
