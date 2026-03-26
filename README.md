# Media Agent 项目

## 项目概述
Media Agent 是一个自动化内容生成和发布平台，能够将资讯自动转换为短视频并发布到多个平台。

## 核心功能
1. **用户认证管理** - 简化的注册登录（仅用户名+密码）
2. **资讯抓取** - RSS源管理，网页内容抓取和清洗
3. **视频处理** - 视频上传、转码、编辑、合成
4. **AI内容生成** - 使用DeepSeek模型生成文案、语音、视频
5. **发布管理** - 多平台内容发布和监控

## 技术栈
### 后端
- **框架**: FastAPI (Python 3.9+)
- **数据库**: PostgreSQL 13+
- **缓存/队列**: Redis 6+
- **任务队列**: Celery
- **ORM**: SQLAlchemy + Async
- **认证**: JWT + bcrypt

### 前端
- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **路由**: React Router v6
- **状态管理**: Zustand
- **UI组件**: Ant Design
- **HTTP客户端**: Axios

## 项目结构
```
media-agent/
├── docs/                    # 项目文档
├── backend/               # 后端代码（FastAPI）
├── frontend/             # 前端代码（React + TypeScript）
├── README.md            # 项目说明
└── .gitignore          # Git忽略配置
```

## 文档说明
- **需求文档**: 完整的功能性能需求说明
- **设计文档**: 系统架构和详细设计
- **部署指南**: 完整的部署步骤和配置

## 最新更新
### 2026-03-26
1. **需求文档更新**：
   - 创建最终版需求说明书
   - 明确AI模型仅使用DeepSeek系列
   - 性能要求根据服务器性能动态确定
   - 增加任务队列总等待时间要求

2. **设计文档完成**：
   - 完成概要设计文档
   - 完成详细设计文档

3. **代码更新**：
   - 简化认证功能（移除邮箱、手机号、验证码）
   - 更新前端注册登录页面
   - 更新后端认证API

## 快速开始
```bash
# 克隆项目
git clone https://github.com/xuzixiao198964-boop/media-agent.git
cd media-agent

# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

## 开发进度
- [x] 需求分析文档
- [x] 概要设计文档
- [x] 详细设计文档
- [x] 认证功能简化实现
- [ ] AI内容生成模块
- [ ] 发布管理模块
- [ ] 系统测试和部署

## 许可证
MIT License

## 联系方式
项目仓库: https://github.com/xuzixiao198964-boop/media-agent.git
创建日期: 2026-03-26