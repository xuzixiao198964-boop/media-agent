# Media Agent 发布功能过渡计划

## 文档信息
- **文档编号**: TP-001
- **文档标题**: Media Agent 发布功能过渡计划
- **项目名称**: Media Agent（资讯 → 短视频 → 发布）
- **创建日期**: 2026-03-26
- **创建人**: Media Agent Assistant
- **状态**: 📝 实施计划
- **版本**: 1.0
- **依据文档**: 
  - Media-Agent-最终版需求说明书.md（版本1.3）
  - Media-Agent-需求文档评审意见.md（版本1.0）

## 1. 过渡计划概述

### 1.1 当前状态
- **发布模式**: `publish_mode: "mock"`（模拟发布）
- **功能状态**: 仅记录发布日志，不实际调用平台API
- **风险等级**: 高（发布功能是核心业务价值）

### 1.2 目标状态
- **发布模式**: 真实API调用（抖音 + 小红书）
- **功能状态**: 完整的视频发布能力
- **时间目标**: 4-6周完成过渡

### 1.3 过渡原则
1. **渐进式过渡**: 从模拟到真实，分阶段实施
2. **风险控制**: 每个阶段都有回滚方案
3. **用户体验**: 过渡期间不影响现有功能
4. **数据安全**: 保护用户数据和账号安全

## 2. 阶段一：平台准备（第1-2周）

### 2.1 抖音开放平台准备

#### 2.1.1 账号注册和认证
```python
# 抖音开放平台申请流程
抖音开放平台申请步骤:
1. 注册企业账号（需要营业执照）
2. 完成实名认证
3. 创建应用，获取Client Key和Client Secret
4. 申请视频发布权限（需要人工审核）
5. 配置OAuth 2.0回调地址
6. 获取测试账号用于开发测试

# 预计时间: 3-7个工作日（审核时间不确定）
# 关键材料: 营业执照、法人身份证、应用描述
```

#### 2.1.2 API权限申请
```python
需要申请的API权限:
1. 视频上传接口 (video.create)
2. 视频发布接口 (video.publish)
3. 用户授权接口 (oauth)
4. 账号信息接口 (user.info)
5. 发布状态查询接口 (video.status)

# 注意事项:
# 1. 抖音API有严格的调用频率限制
# 2. 需要处理视频审核机制
# 3. 需要支持分片上传（大文件）
```

### 2.2 小红书开放平台准备

#### 2.2.1 账号注册和认证
```python
# 小红书开放平台申请流程
小红书开放平台申请步骤:
1. 注册企业账号（需要营业执照）
2. 完成企业认证
3. 创建应用，获取App Key和App Secret
4. 申请内容发布权限
5. 配置授权回调地址
6. 获取测试权限

# 预计时间: 5-10个工作日
# 关键材料: 营业执照、企业信息、应用说明
```

#### 2.2.2 API权限申请
```python
需要申请的API权限:
1. 内容创建接口 (content.create)
2. 图片上传接口 (image.upload)
3. 视频上传接口 (video.upload)
4. 用户授权接口 (oauth)
5. 发布状态接口 (content.status)

# 注意事项:
# 1. 小红书有严格的内容审核规则
# 2. 视频长度限制（≤60秒）
# 3. 图片数量限制（≤9张）
```

### 2.3 技术准备

#### 2.3.1 开发环境配置
```python
# 环境变量配置
PUBLISH_MODE = "development"  # development/staging/production
DOUYIN_ENABLED = False  # 初始为False
XIAOHONGSHU_ENABLED = False

# API密钥管理（使用环境变量或密钥管理服务）
DOUYIN_CLIENT_KEY = os.getenv("DOUYIN_CLIENT_KEY")
DOUYIN_CLIENT_SECRET = os.getenv("DOUYIN_CLIENT_SECRET")
XHS_APP_KEY = os.getenv("XHS_APP_KEY")
XHS_APP_SECRET = os.getenv("XHS_APP_SECRET")
```

#### 2.3.2 代码架构准备
```python
# 发布服务架构设计
class PublishService:
    """发布服务基类"""
    def __init__(self, mode="mock"):
        self.mode = mode
        self.platforms = self._init_platforms()
    
    def _init_platforms(self):
        """初始化发布平台"""
        platforms = {
            "mock": MockPublisher(),
        }
        
        # 根据配置动态添加真实平台
        if DOUYIN_ENABLED:
            platforms["douyin"] = DouyinPublisher()
        if XIAOHONGSHU_ENABLED:
            platforms["xiaohongshu"] = XiaohongshuPublisher()
        
        return platforms
    
    def publish(self, video_data, platform="douyin"):
        """发布视频（支持多种模式）"""
        publisher = self.platforms.get(platform)
        if not publisher:
            raise PlatformNotSupportedError(platform)
        
        return publisher.publish(video_data)
```

## 3. 阶段二：开发实现（第3-4周）

### 3.1 抖音API集成

#### 3.1.1 OAuth 2.0授权流程实现
```python
class DouyinOAuth:
    """抖音OAuth授权管理"""
    
    async def get_auth_url(self, user_id, redirect_uri):
        """获取授权URL"""
        # 构建授权链接
        params = {
            "client_key": self.client_key,
            "response_type": "code",
            "scope": "video.create,video.data",
            "redirect_uri": redirect_uri,
            "state": self._generate_state(user_id)
        }
        
        auth_url = f"https://open.douyin.com/platform/oauth/connect/?{urlencode(params)}"
        return auth_url
    
    async def exchange_token(self, code):
        """用code交换access_token"""
        token_url = "https://open.douyin.com/oauth/access_token/"
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code"
        }
        
        response = await self._post(token_url, data)
        return response.json()
    
    async def refresh_token(self, refresh_token):
        """刷新access_token"""
        refresh_url = "https://open.douyin.com/oauth/refresh_token/"
        data = {
            "client_key": self.client_key,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        response = await self._post(refresh_url, data)
        return response.json()
```

#### 3.1.2 视频上传和发布实现
```python
class DouyinPublisher:
    """抖音发布器"""
    
    async def upload_video(self, video_file, access_token):
        """上传视频到抖音"""
        # 1. 初始化上传
        init_url = "https://open.douyin.com/api/video/upload/init/"
        init_data = {
            "access_token": access_token,
            "video_size": os.path.getsize(video_file),
            "chunk_size": 1024 * 1024 * 5,  # 5MB分片
        }
        
        init_resp = await self._post(init_url, init_data)
        upload_id = init_resp.json()["upload_id"]
        
        # 2. 分片上传
        with open(video_file, "rb") as f:
            chunk_index = 0
            while chunk_data := f.read(5 * 1024 * 1024):
                chunk_url = "https://open.douyin.com/api/video/upload/part/"
                chunk_data = {
                    "access_token": access_token,
                    "upload_id": upload_id,
                    "part_number": chunk_index,
                    "video": chunk_data
                }
                await self._post(chunk_url, chunk_data)
                chunk_index += 1
        
        # 3. 完成上传
        complete_url = "https://open.douyin.com/api/video/upload/complete/"
        complete_data = {
            "access_token": access_token,
            "upload_id": upload_id
        }
        
        complete_resp = await self._post(complete_url, complete_data)
        return complete_resp.json()["video_id"]
    
    async def publish_video(self, video_id, video_info, access_token):
        """发布视频"""
        publish_url = "https://open.douyin.com/api/video/create/"
        publish_data = {
            "access_token": access_token,
            "video_id": video_id,
            "text": video_info["description"],
            "poi_id": video_info.get("poi_id", ""),
            "cover_tsp": video_info.get("cover_time", 0.5),
            "at_users": video_info.get("at_users", []),
            "disable_comment": video_info.get("disable_comment", False),
            "disable_share": video_info.get("disable_share", False),
        }
        
        response = await self._post(publish_url, publish_data)
        return response.json()
```

### 3.2 小红书API集成

#### 3.2.1 授权和内容创建
```python
class XiaohongshuPublisher:
    """小红书发布器"""
    
    async def upload_image(self, image_file, access_token):
        """上传图片到小红书"""
        upload_url = "https://open.xiaohongshu.com/api/upload/image"
        
        with open(image_file, "rb") as f:
            files = {"file": (os.path.basename(image_file), f, "image/jpeg")}
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = await self._post(upload_url, files=files, headers=headers)
            return response.json()["image_id"]
    
    async def upload_video(self, video_file, access_token):
        """上传视频到小红书"""
        # 小红书视频上传流程
        # 1. 获取上传凭证
        # 2. 上传到COS
        # 3. 确认上传完成
        
        credential_url = "https://open.xiaohongshu.com/api/upload/video/credential"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        credential_resp = await self._get(credential_url, headers=headers)
        credential = credential_resp.json()
        
        # 使用凭证上传到COS
        cos_url = credential["upload_url"]
        cos_headers = credential["headers"]
        
        with open(video_file, "rb") as f:
            await self._put(cos_url, data=f, headers=cos_headers)
        
        # 确认上传
        confirm_url = "https://open.xiaohongshu.com/api/upload/video/confirm"
        confirm_data = {
            "upload_id": credential["upload_id"],
            "video_name": os.path.basename(video_file)
        }
        
        confirm_resp = await self._post(confirm_url, json=confirm_data, headers=headers)
        return confirm_resp.json()["video_id"]
    
    async def create_content(self, content_data, access_token):
        """创建小红书内容"""
        create_url = "https://open.xiaohongshu.com/api/content/create"
        
        data = {
            "title": content_data["title"],
            "desc": content_data["description"],
            "type": "video" if content_data.get("video_id") else "image",
            "video_id": content_data.get("video_id"),
            "image_ids": content_data.get("image_ids", []),
            "at_users": content_data.get("at_users", []),
            "topic_ids": content_data.get("topic_ids", []),
            "location": content_data.get("location", {}),
            "visible": content_data.get("visible", 0),  # 0-公开，1-私密
        }
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self._post(create_url, json=data, headers=headers)
        return response.json()
```

### 3.3 统一发布接口

#### 3.3.1 发布服务抽象层
```python
class UnifiedPublishService:
    """统一发布服务"""
    
    def __init__(self):
        self.platforms = {
            "mock": MockPublisher(),
            "douyin": DouyinPublisher() if DOUYIN_ENABLED else None,
            "xiaohongshu": XiaohongshuPublisher() if XIAOHONGSHU_ENABLED else None,
        }
    
    async def publish_to_platforms(self, video_data, platform_list):
        """发布到多个平台"""
        results = {}
        
        for platform in platform_list:
            publisher = self.platforms.get(platform)
            if not publisher:
                results[platform] = {
                    "success": False,
                    "error": f"平台 {platform} 未启用或不存在"
                }
                continue
            
            try:
                # 获取用户授权
                user_token = await self._get_user_token(video_data["user_id"], platform)
                if not user_token:
                    results[platform] = {
                        "success": False,
                        "error": f"用户未授权 {platform} 平台"
                    }
                    continue
                
                # 执行发布
                result = await publisher.publish(video_data, user_token)
                results[platform] = {
                    "success": True,
                    "data": result,
                    "platform": platform
                }
                
            except Exception as e:
                results[platform] = {
                    "success": False,
                    "error": str(e),
                    "platform": platform
                }
                # 记录错误日志
                await self._log_publish_error(video_data["user_id"], platform, str(e))
        
        return results
    
    async def get_publish_status(self, user_id, publish_id):
        """获取发布状态"""
        # 查询各平台发布状态
        status = {}
        
        for platform_name, publisher in self.platforms.items():
            if publisher:
                try:
                    platform_status = await publisher.get_status(publish_id)
                    status[platform_name] = platform_status
                except Exception as e:
                    status[platform_name] = {"error": str(e)}
        
        return status
```

## 4. 阶段三：测试验证（第5周）

### 4.1 测试环境配置

#### 4.1.1 沙箱环境
```python
# 测试环境配置
TEST_CONFIG = {
    "douyin": {
        "enabled": True,
        "mode": "sandbox",  # sandbox/production
        "client_key": "test_client_key",
        "client_secret": "test_client_secret",
        "redirect_uri": "http://localhost:8000/auth/callback/douyin",
        "test_accounts": ["test_user_1", "test_user_2"]
    },
    "xiaohongshu": {
        "enabled": True,
        "mode": "sandbox",
        "app_key": "test_app_key",
        "app_secret": "test_app_secret",
        "redirect_uri": "http://localhost:8000/auth/callback/xhs",
        "test_accounts": ["test_user_1", "test_user_2"]
    }
}
```

#### 4.1.2 测试数据准备
```python
# 测试视频数据
TEST_VIDEOS = [
    {
        "id": "test_video_1",
        "title": "测试视频1 - 短内容",
        "description": "这是一个测试视频，用于验证发布功能",
        "file_path": "/data/test/videos/short_test.mp4",
        "duration": 15,  # 15秒
        "size_mb": 10,
        "tags": ["测试", "技术", "短视频"],
        "expected_platforms": ["douyin", "xiaohongshu"]
    },
    {
        "id": "test_video_2",
        "title": "测试视频2 - 长内容",
        "description": "这是一个较长的测试视频，用于验证大文件上传",
        "file_path": "/data/test/videos/long_test.mp4",
        "duration": 180,  # 3分钟
        "size_mb": 150,
        "tags": ["测试", "长视频", "内容"],
        "expected_platforms": ["douyin"]  # 小红书只支持60秒
    }
]
```

### 4.2 功能测试

#### 4.2.1 单元测试
```python
async def test_douyin_oauth():
    """测试抖音OAuth流程"""
    oauth = DouyinOAuth()
    
    # 测试获取授权URL
    auth_url = await oauth.get_auth_url("test_user", "http://test.com/callback")
    assert "open.douyin.com" in auth_url
    assert "client_key" in auth_url
    
    # 测试token交换（模拟）
    mock_code = "test_auth_code"
    token_data = await oauth.exchange_token(mock_code)
    assert "access_token" in token_data
    assert "expires_in" in token_data
    
    # 测试token刷新
    refresh_data = await oauth.refresh_token(token_data["refresh_token"])
    assert "access_token" in refresh_data

async def test_douyin_video_upload():
    """测试抖音视频上传"""
    publisher = DouyinPublisher()
    test_video = TEST_VIDEOS[0]
    
    # 模拟上传
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "upload_id": "test_upload_123",
            "video_id": "test_video_456"
        }
        
        video_id = await publisher.upload_video(
            test_video["file_path"],
            "test_access_token"
        )
        
        assert video_id == "test_video_456"
```

#### 4.2.2 集成测试
```python
async def test_end_to_end_publish():
    """测试端到端发布流程"""
    publish_service = UnifiedPublishService()
    test_video = TEST_VIDEOS[0]
    
    # 模拟用户授权
    await mock_user_auth("test_user", ["douyin", "xiaohongshu"])
    
    # 执行发布
    results = await publish_service.publish_to_platforms(
        video_data=test_video,
        platform_list=["douyin", "xiaohongshu"]
    )
    
    # 验证结果
    assert "douyin" in results
    assert "xiaohongshu" in results
    assert results["douyin"]["success"] == True
    assert results["xiaohongshu"]["success"] == True
    
    # 验证发布记录
    publish_record = await get_publish_record(results["douyin"]["data"]["publish_id"])
    assert publish_record["status"] == "published"
    assert publish_record["platform"] == "douyin"
```

#### 4.2.3 性能测试
```python
async def test_publish_performance():
    """测试发布性能"""
    publish_service = UnifiedPublishService()
    
    # 测试并发发布
    start_time = time.time()
    tasks = []
    
    for i in range(5):  # 5个并发发布
        video_data = {
            **TEST_VIDEOS[0],
            "id": f"concurrent_test_{i}"
        }
        task = asyncio.create_task(
            publish_service.publish_to_platforms(video_data, ["douyin"])
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    # 验证性能
    total_time = end_time - start_time
    print(f"5个并发发布总时间: {total_time:.2f}秒")
    print(f"平均每个发布: {total_time/5:.2f}秒")
    
    # 基于VPS性能，应该有合理的时间
    assert total_time < 300  # 5分钟以内
    assert all(r["douyin"]["success"] for r in results)
```

### 4.3 错误处理测试

#### 4.3.1 网络错误测试
```python
async def test_network_failure():
    """测试网络错误处理"""
    publisher = DouyinPublisher()
    
    # 模拟网络超时
    with patch('aiohttp.ClientSession.post', side_effect=asyncio.TimeoutError):
        try:
            await publisher.upload_video("test.mp4", "test_token")
            assert False, "应该抛出异常"
        except PublishError as e:
            assert "网络超时" in str(e)
            assert e.retryable == True  # 可重试
    
    # 模拟API错误
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.status = 400
        mock_post.return_value.json.return_value = {
            "error_code": 10010,
            "description": "无效的access_token"
        }
        
        try:
            await publisher.publish_video("video_123", {}, "invalid_token")
            assert False, "应该抛出异常"
        except PublishError as e:
            assert "无效的access_token" in str(e)
            assert e.retryable == False  # 不可重试
```

#### 4.3.2 平台限制测试
```python
async def test_platform_limits():
    """测试平台限制"""
    # 测试视频长度限制
    long_video = {
        **TEST_VIDEOS[1],
        "duration": 300  # 5分钟，超过小红书限制
    }
    
    publish_service = UnifiedPublishService()
    
    # 小红书应该拒绝
    results = await publish_service.publish_to_platforms(
        long_video,
        ["xiaohongshu"]
    )
    
    assert results["xiaohongshu"]["success"] == False
    assert "视频长度超过限制" in results["xiaohongshu"]["error"]
    
    # 抖音应该接受（支持15分钟）
    results = await publish_service.publish_to_platforms(
        long_video,
        ["douyin"]
    )
    
    assert results["douyin"]["success"] == True
```

## 5. 阶段四：灰度发布（第6周）

### 5.1 发布策略

#### 5.1.1 用户分组
```python
# 用户分组策略
USER_GROUPS = {
    "internal": {  # 内部测试用户
        "size": 5,
        "criteria": "user_role == 'admin' or user_role == 'tester'",
        "features": ["douyin", "xiaohongshu"]
    },
    "alpha": {  # Alpha测试用户
        "size": 50,
        "criteria": "user_id % 100 < 10",  # 10%用户
        "features": ["douyin"]  # 先只开放抖音
    },
    "beta": {  # Beta测试用户
        "size": 200,
        "criteria": "user_id % 100 < 30",  # 30%用户
        "features": ["douyin", "xiaohongshu"]
    },
    "all": {  # 所有用户
        "size": "100%",
        "criteria": "True",
        "features": ["douyin", "xiaohongshu"]
    }
}
```

#### 5.1.2 功能开关
```python
# 功能开关配置
FEATURE_FLAGS = {
    "publish_douyin": {
        "enabled": True,
        "rollout_percentage": 10,  # 10%用户
        "user_groups": ["internal", "alpha"],
        "fallback": "mock"  # 失败时回退到模拟模式
    },
    "publish_xiaohongshu": {
        "enabled": True,
        "rollout_percentage": 5,  # 5%用户
        "user_groups": ["internal"],
        "fallback": "mock"
    }
}

def should_enable_feature(user_id, feature_name):
    """判断是否对用户启用功能"""
    flag = FEATURE_FLAGS.get(feature_name)
    if not flag or not flag["enabled"]:
        return False
    
    # 检查用户分组
    user_group = get_user_group(user_id)
    if user_group not in flag["user_groups"]:
        return False
    
    # 检查 rollout 百分比
    if user_id % 100 < flag["rollout_percentage"]:
        return True
    
    return False
```

### 5.2 监控和告警

#### 5.2.1 监控指标
```python
# 发布功能监控指标
PUBLISH_METRICS = {
    # 成功率指标
    "publish_success_rate": {
        "description": "发布成功率",
        "calculation": "success_count / total_count",
        "threshold": 0.95,  # 低于95%告警
        "window": "5m"  # 5分钟窗口
    },
    
    # 性能指标
    "publish_latency_p95": {
        "description": "发布延迟P95",
        "calculation": "histogram_quantile(0.95, rate(publish_duration_seconds_bucket[5m]))",
        "threshold": 300,  # 超过5分钟告警
        "window": "5m"
    },
    
    # 错误率指标
    "publish_error_rate": {
        "description": "发布错误率",
        "calculation": "error_count / total_count",
        "threshold": 0.05,  # 超过5%告警
        "window": "5m"
    },
    
    # 平台特定指标
    "douyin_api_error_rate": {
        "description": "抖音API错误率",
        "calculation": "douyin_error_count / douyin_total_count",
        "threshold": 0.1,  # 超过10%告警
        "window": "5m"
    }
}
```

#### 5.2.2 告警规则
```python
# 告警规则配置
ALERT_RULES = {
    "publish_success_rate_low": {
        "condition": "publish_success_rate < 0.95",
        "duration": "5m",
        "severity": "warning",
        "message": "发布成功率低于95%",
        "action": ["slack_alert", "auto_switch_to_mock"]
    },
    
    "douyin_api_unavailable": {
        "condition": "douyin_api_error_rate > 0.3",
        "duration": "2m",
        "severity": "critical",
        "message": "抖音API错误率超过30%",
        "action": ["slack_alert", "phone_call", "auto_disable_douyin"]
    },
    
    "high_publish_latency": {
        "condition": "publish_latency_p95 > 300",
        "duration": "5m",
        "severity": "warning",
        "message": "发布延迟P95超过5分钟",
        "action": ["slack_alert", "scale_up_workers"]
    }
}
```

### 5.3 自动回滚机制

#### 5.3.1 健康检查
```python
class PublishHealthChecker:
    """发布健康检查器"""
    
    async def check_health(self):
        """检查发布功能健康状态"""
        checks = {
            "douyin": await self._check_douyin_health(),
            "xiaohongshu": await self._check_xiaohongshu_health(),
            "database": await self._check_database_health(),
            "storage": await self._check_storage_health()
        }
        
        # 计算总体健康状态
        all_healthy = all(check["healthy"] for check in checks.values())
        
        return {
            "overall_healthy": all_healthy,
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _check_douyin_health(self):
        """检查抖音API健康状态"""
        try:
            # 测试API连通性
            test_url = "https://open.douyin.com/api/test/connect"
            response = await self._get(test_url, timeout=10)
            
            return {
                "healthy": response.status == 200,
                "latency": response.elapsed.total_seconds(),
                "details": response.json() if response.status == 200 else None
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "latency": None
            }
```

#### 5.3.2 自动切换
```python
class AutoFallbackManager:
    """自动回退管理器"""
    
    def __init__(self):
        self.current_mode = "mixed"  # mixed/mock/real
        self.fallback_history = []
    
    async def evaluate_and_switch(self):
        """评估并切换模式"""
        health_check = await self.health_checker.check_health()
        
        if not health_check["overall_healthy"]:
            # 系统不健康，切换到模拟模式
            await self.switch_to_mock()
            return "mock"
        
        # 检查各平台健康状态
        platform_health = {
            "douyin": health_check["checks"]["douyin"]["healthy"],
            "xiaohongshu": health_check["checks"]["xiaohongshu"]["healthy"]
        }
        
        # 根据平台健康状态决定模式
        if all(platform_health.values()):
            # 所有平台健康，使用真实模式
            await self.switch_to_real()
            return "real"
        elif any(platform_health.values()):
            # 部分平台健康，使用混合模式
            await self.switch_to_mixed(platform_health)
            return "mixed"
        else:
            # 所有平台不健康，使用模拟模式
            await self.switch_to_mock()
            return "mock"
    
    async def switch_to_mock(self):
        """切换到模拟模式"""
        self.current_mode = "mock"
        FEATURE_FLAGS["publish_douyin"]["enabled"] = False
        FEATURE_FLAGS["publish_xiaohongshu"]["enabled"] = False
        
        # 记录切换
        self.fallback_history.append({
            "timestamp": datetime.utcnow(),
            "from": self.current_mode,
            "to": "mock",
            "reason": "system_unhealthy"
        })
        
        # 发送通知
        await self.send_notification("切换到模拟发布模式")
    
    async def switch_to_mixed(self, healthy_platforms):
        """切换到混合模式"""
        self.current_mode = "mixed"
        
        # 只启用健康的平台
        for platform, is_healthy in healthy_platforms.items():
            feature_key = f"publish_{platform}"
            if feature_key in FEATURE_FLAGS:
                FEATURE_FLAGS[feature_key]["enabled"] = is_healthy
        
        # 记录切换
        self.fallback_history.append({
            "timestamp": datetime.utcnow(),
            "from": self.current_mode,
            "to": "mixed",
            "reason": "partial_platform_unhealthy",
            "healthy_platforms": healthy_platforms
        })
```

## 6. 阶段五：全面上线（第7-8周）

### 6.1 用户引导和教育

#### 6.1.1 新功能引导
```python
# 用户引导流程
USER_ONBOARDING = {
    "step1_auth": {
        "title": "连接你的社交账号",
        "description": "为了发布视频，需要先授权连接你的抖音/小红书账号",
        "actions": [
            {
                "type": "button",
                "text": "连接抖音账号",
                "action": "connect_douyin",
                "platform": "douyin"
            },
            {
                "type": "button",
                "text": "连接小红书账号",
                "action": "connect_xiaohongshu",
                "platform": "xiaohongshu"
            }
        ],
        "required": True
    },
    
    "step2_tutorial": {
        "title": "发布功能教程",
        "description": "学习如何使用发布功能",
        "content": [
            "1. 选择要发布的视频",
            "2. 编辑标题和描述",
            "3. 选择发布平台",
            "4. 设置发布时间",
            "5. 确认并发布"
        ],
        "video_url": "/tutorials/publish_tutorial.mp4",
        "required": False
    },
    
    "step3_first_publish": {
        "title": "发布第一个视频",
        "description": "尝试发布你的第一个视频",
        "incentive": "完成首次发布可获得7天VIP体验",
        "required": True
    }
}
```

#### 6.1.2 帮助文档
```python
# 帮助文档结构
HELP_DOCUMENTS = {
    "publish_basics": {
        "title": "发布功能基础",
        "sections": [
            {
                "title": "如何授权账号",
                "content": "详细说明如何连接抖音和小红书账号"
            },
            {
                "title": "视频格式要求",
                "content": "各平台的视频格式、大小、时长限制"
            },
            {
                "title": "发布最佳实践",
                "content": "提高视频曝光率的技巧和建议"
            }
        ]
    },
    
    "troubleshooting": {
        "title": "问题排查",
        "sections": [
            {
                "title": "发布失败怎么办",
                "content": "常见发布失败原因和解决方法"
            },
            {
                "title": "视频审核问题",
                "content": "平台审核规则和注意事项"
            },
            {
                "title": "联系客服",
                "content": "如何获取技术支持"
            }
        ]
    }
}
```

### 6.2 数据迁移和清理

#### 6.2.1 模拟数据迁移
```python
async def migrate_mock_publishes():
    """迁移模拟发布数据"""
    # 获取所有模拟发布记录
    mock_publishes = await get_mock_publish_records()
    
    migration_results = {
        "total": len(mock_publishes),
        "migrated": 0,
        "failed": 0,
        "errors": []
    }
    
    for record in mock_publishes:
        try:
            # 检查是否满足迁移条件
            if await can_migrate_record(record):
                # 执行真实发布
                real_result = await republish_to_real(record)
                
                # 更新记录状态
                await update_publish_record(record["id"], {
                    "status": "migrated",
                    "real_publish_id": real_result["publish_id"],
                    "migrated_at": datetime.utcnow()
                })
                
                migration_results["migrated"] += 1
            else:
                # 标记为需要用户操作
                await update_publish_record(record["id"], {
                    "status": "needs_user_action",
                    "migration_note": "需要用户重新授权"
                })
                
        except Exception as e:
            migration_results["failed"] += 1
            migration_results["errors"].append({
                "record_id": record["id"],
                "error": str(e)
            })
    
    return migration_results
```

#### 6.2.2 数据清理
```python
async def cleanup_old_data():
    """清理旧数据"""
    cleanup_tasks = [
        # 清理过期的模拟发布记录（保留30天）
        {
            "table": "mock_publishes",
            "condition": "created_at < NOW() - INTERVAL '30 days'",
            "action": "archive_then_delete"
        },
        # 清理失败的重试记录（保留7天）
        {
            "table": "publish_retries",
            "condition": "status = 'failed' AND created_at < NOW() - INTERVAL '7 days'",
            "action": "delete"
        },
        # 压缩历史日志
        {
            "table": "publish_logs",
            "condition": "created_at < NOW() - INTERVAL '90 days'",
            "action": "compress_and_archive"
        }
    ]
    
    results = []
    for task in cleanup_tasks:
        result = await execute_cleanup_task(task)
        results.append(result)
    
    return results
```

### 6.3 性能优化

#### 6.3.1 发布队列优化
```python
class OptimizedPublishQueue:
    """优化后的发布队列"""
    
    def __init__(self):
        # 基于VPS性能的队列配置
        self.config = {
            "max_concurrent_douyin": 2,  # 抖音并发数
            "max_concurrent_xhs": 2,     # 小红书并发数
            "queue_capacity": 100,       # 队列容量
            "retry_strategy": {
                "max_retries": 3,
                "backoff_factor": 2,
                "max_delay": 300  # 5分钟
            }
        }
        
        self.queues = {
            "douyin": asyncio.Queue(maxsize=self.config["queue_capacity"]),
            "xiaohongshu": asyncio.Queue(maxsize=self.config["queue_capacity"])
        }
        
        self.workers = self._start_workers()
    
    def _start_workers(self):
        """启动工作线程"""
        workers = []
        
        # 抖音发布 workers
        for i in range(self.config["max_concurrent_douyin"]):
            worker = asyncio.create_task(self._douyin_worker(f"douyin_worker_{i}"))
            workers.append(worker)
        
        # 小红书发布 workers
        for i in range(self.config["max_concurrent_xhs"]):
            worker = asyncio.create_task(self._xhs_worker(f"xhs_worker_{i}"))
            workers.append(worker)
        
        return workers
    
    async def _douyin_worker(self, worker_id):
        """抖音发布工作线程"""
        while True:
            try:
                task = await self.queues["douyin"].get()
                await self._process_douyin_task(task, worker_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"抖音worker {worker_id} 错误: {e}")
                await asyncio.sleep(1)
```

#### 6.3.2 缓存优化
```python
class PublishCache:
    """发布缓存优化"""
    
    def __init__(self):
        # 多级缓存策略
        self.caches = {
            "memory": MemoryCache(max_size=1000),  # 内存缓存
            "database": DatabaseCache(),           # 数据库缓存
            "redis": RedisCache() if REDIS_AVAILABLE else None
        }
        
        # 缓存配置
        self.ttl_config = {
            "user_tokens": 3600,      # 1小时
            "platform_config": 86400,  # 24小时
            "publish_status": 300,     # 5分钟
            "video_info": 1800         # 30分钟
        }
    
    async def get_with_cache(self, key, fetch_func, cache_type="memory", ttl=None):
        """带缓存的获取"""
        cache = self.caches.get(cache_type)
        if not cache:
            # 没有指定缓存，直接获取
            return await fetch_func()
        
        # 尝试从缓存获取
        cached = await cache.get(key)
        if cached is not None:
            return cached
        
        # 缓存未命中，获取数据
        data = await fetch_func()
        if data is not None:
            ttl = ttl or self.ttl_config.get(key.split(":")[0], 300)
            await cache.set(key, data, ttl)
        
        return data
```

## 7. 风险管理计划

### 7.1 风险识别和评估

| 风险类型 | 风险描述 | 概率 | 影响 | 风险等级 | 缓解措施 |
|---------|---------|------|------|----------|----------|
| 技术风险 | 抖音/小红书API变更 | 中 | 高 | 高 | 1. 监控API文档变更 2. 设计适配层 3. 准备降级方案 |
| 技术风险 | 平台审核规则变化 | 高 | 中 | 高 | 1. 实时监控审核结果 2. 建立规则库 3. 自动调整策略 |
| 业务风险 | 用户授权率低 | 中 | 高 | 高 | 1. 优化授权流程 2. 提供激励措施 3. 教育用户价值 |
| 业务风险 | 发布成功率低 | 中 | 高 | 高 | 1. 完善的错误处理 2. 自动重试机制 3. 实时监控告警 |
| 运营风险 | 内容合规问题 | 高 | 高 | 极高 | 1. 内容审核机制 2. 敏感词过滤 3. 人工审核流程 |

### 7.2 应急预案

#### 7.2.1 平台API故障应急预案
```python
PLATFORM_FAILURE_PLAN = {
    "level1": {  # 轻微故障（错误率<10%）
        "actions": [
            "启用自动重试机制",
            "增加监控频率",
            "记录详细错误日志"
        ],
        "notification": "内部通知"
    },
    
    "level2": {  # 中等故障（错误率10-30%）
        "actions": [
            "降低发布频率",
            "切换到备用API端点",
            "启用降级发布模式"
        ],
        "notification": "用户通知+内部告警"
    },
    
    "level3": {  # 严重故障（错误率>30%）
        "actions": [
            "暂停发布功能",
            "自动切换到模拟模式",
            "启动人工干预流程"
        ],
        "notification": "紧急告警+用户公告"
    }
}
```

#### 7.2.2 数据丢失应急预案
```python
DATA_RECOVERY_PLAN = {
    "prevention": [
        "实时数据备份",
        "事务日志记录",
        "定期完整性检查"
    ],
    
    "recovery": {
        "partial_loss": [
            "从备份恢复缺失数据",
            "重新同步平台状态",
            "验证数据一致性"
        ],
        
        "complete_loss": [
            "切换到灾备系统",
            "从最新备份恢复",
            "重新授权用户账号"
        ]
    },
    
    "testing": [
        "每月进行恢复演练",
        "验证备份完整性",
        "测试恢复流程"
    ]
}
```

## 8. 成功指标和验收标准

### 8.1 技术指标

| 指标 | 目标值 | 测量方法 | 验收标准 |
|------|--------|----------|----------|
| 发布成功率 | >95% | 成功发布数/总发布数 | 连续7天达标 |
| 平均发布延迟 | <3分钟 | 从提交到完成的平均时间 | P95 < 5分钟 |
| 系统可用性 | >99.5% | 正常运行时间/总时间 | 月度达标 |
| API错误率 | <5% | API错误数/总请求数 | 连续30天达标 |
| 用户授权率 | >60% | 授权用户数/总用户数 | 上线后30天达标 |

### 8.2 业务指标

| 指标 | 目标值 | 测量周期 | 验收标准 |
|------|--------|----------|----------|
| 日活跃发布用户 | >100 | 每日 | 上线后30天达标 |
| 月发布视频数 | >1000 | 每月 | 上线后90天达标 |
| 用户满意度 | >4/5 | 每月调查 | 季度达标 |
| 平台覆盖度 | 抖音+小红书 | 实时 | 双平台稳定运行 |
| 内容审核通过率 | >90% | 每周 | 连续4周达标 |

### 8.3 验收测试用例

```python
ACCEPTANCE_TEST_CASES = [
    {
        "id": "ATC-001",
        "description": "用户授权抖音账号",
        "steps": [
            "1. 用户点击'连接抖音'按钮",
            "2. 跳转到抖音授权页面",
            "3. 用户同意授权",
            "4. 返回系统，显示授权成功"
        ],
        "expected": "用户抖音账号成功连接，可以发布视频",
        "priority": "高"
    },
    
    {
        "id": "ATC-002",
        "description": "发布视频到抖音",
        "steps": [
            "1. 用户选择视频文件",
            "2. 编辑标题和描述",
            "3. 选择发布到抖音",
            "4. 点击发布按钮",
            "5. 等待发布完成"
        ],
        "expected": "视频成功发布到抖音，用户可以看到发布结果",
        "priority": "高"
    },
    
    {
        "id": "ATC-003",
        "description": "多平台同时发布",
        "steps": [
            "1. 用户选择视频文件",
            "2. 同时勾选抖音和小红书",
            "3. 点击发布",
            "4. 等待两个平台都完成"
        ],
        "expected": "视频同时发布到抖音和小红书，分别显示发布状态",
        "priority": "中"
    },
    
    {
        "id": "ATC-004",
        "description": "发布失败处理",
        "steps": [
            "1. 模拟网络故障",
            "2. 尝试发布视频",
            "3. 观察错误处理",
            "4. 检查重试机制"
        ],
        "expected": "系统正确处理失败，提供错误信息，支持重试",
        "priority": "高"
    }
]
```

## 9. 时间计划和里程碑

### 9.1 详细时间计划

| 阶段 | 时间 | 主要任务 | 交付物 | 负责人 |
|------|------|----------|--------|--------|
| 平台准备 | 第1-2周 | 1. 注册开放平台账号<br>2. 申请API权限<br>3. 配置开发环境 | 1. 平台账号<br>2. API密钥<br>3. 开发环境 | 开发团队 |
| 开发实现 | 第3-4周 | 1. OAuth授权实现<br>2. 视频上传实现<br>3. 发布接口实现 | 1. 授权模块<br>2. 上传模块<br>3. 发布模块 | 开发团队 |
| 测试验证 | 第5周 | 1. 单元测试<br>2. 集成测试<br>3. 性能测试 | 1. 测试报告<br>2. 性能报告<br>3. Bug列表 | QA团队 |
| 灰度发布 | 第6周 | 1. 内部测试<br>2. Alpha测试<br>3. Beta测试 | 1. 用户反馈<br>2. 监控数据<br>3. 优化建议 | 产品团队 |
| 全面上线 | 第7-8周 | 1. 用户引导<br>2. 数据迁移<br>3. 性能优化 | 1. 上线报告<br>2. 运营数据<br>3. 优化方案 | 全体团队 |

### 9.2 关键里程碑

1. **M1: 平台准备完成** (第2周末)
   - ✅ 抖音开放平台账号就绪
   - ✅ 小红书开放平台账号就绪
   - ✅ 开发环境配置完成

2. **M2: 核心功能完成** (第4周末)
   - ✅ OAuth授权流程实现
   - ✅ 视频上传功能实现
   - ✅ 发布接口实现

3. **M3: 测试验证通过** (第5周末)
   - ✅ 所有测试用例通过
   - ✅ 性能指标达标
   - ✅ 安全审查通过

4. **M4: 灰度发布完成** (第6周末)
   - ✅ 内部测试完成
   - ✅ Alpha测试完成
   - ✅ Beta测试完成

5. **M5: 全面上线成功** (第8周末)
   - ✅ 所有用户可用
   - ✅ 运营数据达标
   - ✅ 用户反馈积极

## 10. 资源需求

### 10.1 人力资源

| 角色 | 数量 | 职责 | 参与阶段 |
|------|------|------|----------|
| 后端开发 | 2人 | API集成、服务开发 | 全程 |
| 前端开发 | 1人 | 用户界面、交互优化 | 阶段2-5 |
| QA工程师 | 1人 | 测试设计、执行 | 阶段3-5 |
| 产品经理 | 1人 | 需求管理、用户引导 | 全程 |
| 运维工程师 | 1人 | 部署、监控、维护 | 阶段3-5 |

### 10.2 技术资源

| 资源 | 规格 | 数量 | 用途 |
|------|------|------|------|
| 测试服务器 | 4核8GB | 1台 | 开发和测试环境 |
| 生产服务器 | 4核8GB | 1台 | 生产环境（VPS 104.244.90.202） |
| 数据库 | PostgreSQL 13+ | 1套 | 数据存储和队列 |
| 监控工具 | Prometheus+Grafana | 1套 | 系统监控 |
| 日志服务 | ELK Stack | 1套 | 日志收集分析 |

### 10.3 第三方服务

| 服务 | 用途 | 成本 | 备注 |
|------|------|------|------|
| 抖音开放平台 | 视频发布 | 免费（有限额） | 需要企业认证 |
| 小红书开放平台 | 内容发布 | 免费（有限额） | 需要企业认证 |
| 对象存储 | 视频临时存储 | 按使用量 | 可选，可用本地存储 |
| CDN服务 | 视频分发 | 按流量 | 可选，初期可用直连 |

## 11. 总结

### 11.1 计划优势

1. **渐进式过渡**: 从模拟到真实，风险可控
2. **完善的风险管理**: 识别了所有关键风险并提供缓解措施
3. **明确的成功指标**: 可量化的验收标准
4. **详细的实施步骤**: 每周都有明确的任务和交付物
5. **灵活的调整机制**: 根据测试结果可以调整计划

### 11.2 关键成功因素

1. **平台合作**: 顺利获得抖音和小红书的API权限
2. **技术实现**: 稳定可靠的API集成和错误处理
3. **用户体验**: 简洁流畅的授权和发布流程
4. **系统稳定性**: 高可用性和快速故障恢复
5. **用户接受度**: 用户愿意授权并使用发布功能

### 11.3 后续工作建议

1. **持续优化**: 根据用户反馈和数据分析持续改进
2. **平台扩展**: 在稳定运行后考虑扩展更多平台
3. **功能增强**: 增加定时发布、批量发布等高级功能
4. **数据分析**: 深入分析发布效果，提供优化建议
5. **生态建设**: 与平台合作，获取更多资源和支持

---

**计划制定时间**: 2026-03-26  
**计划版本**: 1.0  
**下次评审时间**: 第2周末（平台准备完成后）  
**负责人**: Media Agent Assistant
