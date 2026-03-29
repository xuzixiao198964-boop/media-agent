# Media Agent（资讯 → 短视频 → 发布）
项目位于 `d:\work\media-agent`，提供：
- **RSS 资讯抓取**（可配置栏目与源，定时 + 手动触发）
- **真人视频上传**（多格式、预览、与栏目可选关联）
- **生成流水线**：DeepSeek（可选）撰稿 → OpenAI TTS 或 Edge TTS（失败则静音兜底）→ FFmpeg 合成 9:16 成片
- **发布适配器**：默认 `mock`（验证状态与日志）；真实平台需各开放平台资质后在 `backend/app/services/publisher.py` 扩展
- **响应式 Web**：PC/浏览器可用
- **流程日志**：`FlowLog` 表 + 前端查看
详细 **API 选型与官方开通地址** 见 [docs/API-SELECTION.md](docs/API-SELECTION.md)。
## 前端单元测试
在 `frontend` 目录：
```bash
cd frontend
npm install
npm test
```
使用 Vitest + Testing Library，覆盖会话超时、`api()` 行为、路由守卫与公共头组件等。
### 登录自测（与 `scripts/verify_login_http.py` 一致）
服务器上若已跑过 `verify_e2e.py`，会存在种子账号（密码强度符合策略）：
- 用户名：`e2e_verify`
- 密码：`E2e_test_pass_1`
也可用「注册」页自行注册。若多次输错密码，需按页面提示完成图形后再登录。
## 本地 / 服务器一键编排
本项目当前使用裸机部署方式（不依赖 Docker）。
- API：默认监听 `9090`（`http://服务器IP:9090/health`）
- Web：由 nginx 提供静态与反代，默认 `8080`（`http://服务器IP:8080`）
如果需要重新部署，可以直接运行裸机脚本（密钥请通过环境变量传入）：
```bash
$env:MEDIA_AGENT_SSH_PASS='你的SSH密码'
python scripts/bare_deploy_steps.py
```
## 端到端验证（裸机）
在服务器上：
```bash
cd /opt/media-agent/backend
PYTHONPATH=/opt/media-agent/backend MEDIA_AGENT_BASE=http://127.0.0.1:9090 /opt/media-agent/venv/bin/python scripts/verify_e2e.py
```
脚本将：注册账号 → 触发 RSS → 生成测试 MP4 并上传 → 创建生成任务 → 等待完成 → mock 发布 → 检查日志。
## 环境变量（节选）
见 `backend` 目录下可自建 `.env`（也可通过 systemd 环境变量注入）；常用变量：
- `SECRET_KEY`：JWT 与 Fernet 加密根密钥（**生产务必更换**）
- `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`：可选
- `PUBLISH_MODE`：默认 `mock`
## 安全说明
- **切勿**在仓库或聊天中明文保存服务器密码与 API 密钥；部署脚本仅通过环境变量读取 SSH 密码。
- 若密钥曾泄露，请立即**轮换**。
