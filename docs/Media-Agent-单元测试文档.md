# Media Agent 单元测试文档

## 文档信息
- **文档编号**: UT-001
- **文档标题**: Media Agent 单元测试文档
- **项目名称**: Media Agent（资讯 → 短视频 → 发布）
- **创建日期**: 2026-03-26
- **创建人**: Media Agent Assistant
- **状态**: 📝 草稿
- **版本**: 1.0
- **依据文档**: 
  - Media-Agent-最终版需求说明书.md（版本1.3）
  - Media-Agent-概要设计文档.md（版本1.1）

## 1. 测试概述

### 1.1 测试目标
基于VPS性能优化的Media Agent系统，确保各模块功能正确、性能达标、安全可靠。

### 1.2 测试原则
- **VPS性能意识**: 测试需考虑VPS服务器（104.244.90.202）的资源限制
- **串行处理验证**: 验证视频生成任务的串行处理逻辑
- **轻量级架构**: 验证去掉Redis依赖后的功能正确性
- **简化认证**: 验证去掉短信邮箱后的认证流程

### 1.3 测试环境
- **服务器**: VPS 104.244.90.202（2-4核CPU，4-8GB内存）
- **数据库**: PostgreSQL（作为Celery Broker和缓存）
- **测试框架**: pytest + pytest-asyncio
- **覆盖率目标**: > 80%

## 2. 用户认证管理模块测试

### 2.1 用户注册测试

#### 测试用例 2.1.1: 用户名验证
```python
def test_username_validation():
    """测试用户名验证规则"""
    # 有效用户名
    assert validate_username("user123") == (True, "用户名格式正确")
    assert validate_username("test_user") == (True, "用户名格式正确")
    
    # 无效用户名
    assert validate_username("ab") == (False, "用户名至少3个字符")
    assert validate_username("user-with-dash") == (False, "用户名只能包含字母、数字和下划线")
    assert validate_username("a" * 65) == (False, "用户名不能超过64个字符")
```

#### 测试用例 2.1.2: 密码强度验证
```python
def test_password_strength():
    """测试密码强度验证规则"""
    # 强密码
    assert validate_password_strength("SecurePass123!@#") == (True, "密码强度符合要求")
    
    # 弱密码
    assert validate_password_strength("weak") == (False, "密码长度至少12个字符")
    assert validate_password_strength("Short1!") == (False, "密码长度至少12个字符")
    assert validate_password_strength("NoSpecialChar123") == (False, "密码必须包含大写字母、小写字母、数字和特殊字符")
```

#### 测试用例 2.1.3: 用户注册流程
```python
async def test_user_registration():
    """测试用户注册完整流程"""
    # 1. 发送注册请求
    register_data = {
        "username": "testuser",
        "password": "SecurePassword123!@#"
    }
    
    # 2. 验证用户名唯一性
    assert await check_username_unique("testuser") == True
    
    # 3. 创建用户
    user = await create_user(register_data)
    assert user.username == "testuser"
    assert user.is_active == True
    
    # 4. 验证密码哈希
    assert verify_password("SecurePassword123!@#", user.hashed_password) == True
    assert verify_password("WrongPassword", user.hashed_password) == False
```

### 2.2 用户登录测试

#### 测试用例 2.2.1: 用户名密码登录
```python
async def test_username_password_login():
    """测试用户名密码登录"""
    # 1. 准备测试用户
    user = await create_test_user()
    
    # 2. 正确登录
    token = await login_with_password(user.username, "TestPassword123!")
    assert token is not None
    assert validate_token(token) == True
    
    # 3. 错误密码
    with pytest.raises(AuthenticationError):
        await login_with_password(user.username, "WrongPassword")
    
    # 4. 不存在的用户
    with pytest.raises(UserNotFoundError):
        await login_with_password("nonexistent", "TestPassword123!")
```

#### 测试用例 2.2.2: 登录限制规则
```python
async def test_login_limitation():
    """测试登录限制规则"""
    user = await create_test_user()
    test_ip = "192.168.1.100"
    
    # 1. 正常登录（1-2次失败）
    for i in range(2):
        with pytest.raises(AuthenticationError):
            await login_with_password(user.username, "WrongPassword", ip=test_ip)
    
    # 2. 增加延迟（3-4次失败）
    start_time = time.time()
    with pytest.raises(AuthenticationError):
        await login_with_password(user.username, "WrongPassword", ip=test_ip)
    elapsed = time.time() - start_time
    assert elapsed >= 1.0  # 应该有1秒延迟
    
    # 3. IP封锁（5次失败）
    with pytest.raises(IPBlockedError):
        await login_with_password(user.username, "WrongPassword", ip=test_ip)
    
    # 4. 用户级别限制
    user_failures = await get_user_failure_count(user.id)
    if user_failures >= 3:
        with pytest.raises(UserLockedError):
            await login_with_password(user.username, "TestPassword123!")
```

### 2.3 会话管理测试

#### 测试用例 2.3.1: JWT令牌验证
```python
def test_jwt_token():
    """测试JWT令牌功能"""
    user_id = 123
    
    # 1. 生成令牌
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    
    # 2. 验证令牌
    assert validate_token(access_token) == True
    assert get_user_id_from_token(access_token) == user_id
    
    # 3. 令牌过期
    expired_token = create_access_token(user_id, expires_delta=timedelta(seconds=-1))
    assert validate_token(expired_token) == False
    
    # 4. 令牌刷新
    new_token = refresh_access_token(refresh_token)
    assert validate_token(new_token) == True
```

#### 测试用例 2.3.2: 并发会话控制
```python
async def test_concurrent_sessions():
    """测试并发会话控制"""
    user = await create_test_user()
    
    # 1. 创建3个会话（允许的最大值）
    sessions = []
    for i in range(3):
        token = await login_with_password(user.username, "TestPassword123!")
        sessions.append(token)
        assert validate_token(token) == True
    
    # 2. 创建第4个会话，应该踢出最早的
    new_token = await login_with_password(user.username, "TestPassword123!")
    
    # 3. 验证最早的会话已失效
    assert validate_token(sessions[0]) == False
    assert validate_token(new_token) == True
    
    # 4. 获取活跃会话列表
    active_sessions = await get_active_sessions(user.id)
    assert len(active_sessions) == 3
```

## 3. 资讯抓取模块测试

### 3.1 RSS解析测试

#### 测试用例 3.1.1: RSS feed解析
```python
def test_rss_parsing():
    """测试RSS feed解析"""
    rss_url = "https://example.com/feed.xml"
    
    # 1. 解析RSS
    articles = parse_rss_feed(rss_url)
    assert len(articles) > 0
    
    # 2. 验证文章结构
    for article in articles:
        assert "title" in article
        assert "link" in article
        assert "published" in article
        assert len(article["title"]) > 0
        assert article["link"].startswith("http")
    
    # 3. 处理空或无效RSS
    empty_result = parse_rss_feed("https://example.com/invalid.xml")
    assert empty_result == []
```

#### 测试用例 3.1.2: 内容去重
```python
async def test_content_deduplication():
    """测试内容去重功能"""
    # 1. 创建测试文章
    article_data = {
        "title": "测试文章",
        "content": "这是一篇测试文章",
        "source_url": "https://example.com/article1",
        "content_hash": hashlib.md5("这是一篇测试文章".encode()).hexdigest()
    }
    
    # 2. 第一次保存
    article1 = await save_article(article_data)
    assert article1 is not None
    
    # 3. 尝试保存相同内容（应该检测到重复）
    article2 = await save_article(article_data)
    assert article2 is None  # 应该返回None，表示重复
    
    # 4. 不同内容应该保存成功
    article_data["content"] = "这是另一篇测试文章"
    article_data["content_hash"] = hashlib.md5("这是另一篇测试文章".encode()).hexdigest()
    article3 = await save_article(article_data)
    assert article3 is not None
```

### 3.2 网页内容提取测试

#### 测试用例 3.2.1: 网页正文提取
```python
def test_web_content_extraction():
    """测试网页正文提取"""
    html_content = """
    <html>
        <head><title>测试页面</title></head>
        <body>
            <div class="header">导航栏</div>
            <article>
                <h1>文章标题</h1>
                <p>这是文章的第一段。</p>
                <p>这是文章的第二段。</p>
            </article>
            <div class="footer">页脚</div>
        </body>
    </html>
    """
    
    # 提取正文
    extracted = extract_article_content(html_content)
    
    assert extracted["title"] == "文章标题"
    assert "这是文章的第一段" in extracted["content"]
    assert "这是文章的第二段" in extracted["content"]
    assert "导航栏" not in extracted["content"]  # 应该过滤掉导航
    assert "页脚" not in extracted["content"]    # 应该过滤掉页脚
```

## 4. 视频处理模块测试

### 4.1 串行任务队列测试

#### 测试用例 4.1.1: 串行任务处理
```python
async def test_serial_task_processing():
    """测试串行任务处理（基于VPS性能限制）"""
    # 1. 提交多个视频生成任务
    task_ids = []
    for i in range(3):
        task_id = await submit_video_generation_task({
            "article_id": i + 1,
            "template": "default"
        })
        task_ids.append(task_id)
    
    # 2. 验证任务状态
    queue_status = await get_task_queue_status()
    assert queue_status["video_generation"]["queue_length"] == 3
    
    # 3. 验证串行处理（同一时间只有一个任务在处理）
    active_tasks = await get_active_tasks()
    assert len(active_tasks) <= 1  # 串行处理，最多一个活跃任务
    
    # 4. 验证任务完成顺序
    completed_tasks = []
    for task_id in task_ids:
        await wait_for_task_completion(task_id, timeout=300)
        completed_tasks.append(task_id)
    
    # 应该按提交顺序完成
    assert completed_tasks == task_ids
```

#### 测试用例 4.1.2: 用户等待时间估算
```python
async def test_wait_time_estimation():
    """测试用户等待时间估算"""
    # 1. 空队列
    wait_time = estimate_wait_time(0, avg_task_time=180)
    assert wait_time == "正在处理中，预计剩余时间: 2-4分钟"
    
    # 2. 第一个排队
    wait_time = estimate_wait_time(1, avg_task_time=180)
    assert wait_time == "下一个处理，预计等待: 0-2分钟"
    
    # 3. 多个排队
    wait_time = estimate_wait_time(3, avg_task_time=180)
    assert "排队中，当前有2个任务在前" in wait_time
    assert "预计等待:" in wait_time
    
    # 4. 队列满提示
    queue_status = await get_queue_status()
    if queue_status["queue_length"] >= 10:  # 最大排队任务数
        assert "当前任务队列已满" in queue_status["message"]
```

### 4.2 FFmpeg处理测试

#### 测试用例 4.2.1: 视频转码
```python
def test_video_transcoding():
    """测试FFmpeg视频转码"""
    input_file = "test_input.mp4"
    output_file = "test_output.mp4"
    
    # 1. 转码命令（限制CPU使用）
    cmd = [
        "ffmpeg",
        "-threads", "2",  # 限制CPU线程数
        "-i", input_file,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_file
    ]
    
    # 2. 执行转码
    result = run_ffmpeg_command(cmd, timeout=300)
    
    assert result["success"] == True
    assert os.path.exists(output_file)
    assert result["duration"] > 0
    
    # 3. 清理测试文件
    if os.path.exists(output_file):
        os.remove(output_file)
```

#### 测试用例 4.2.2: 视频合成
```python
def test_video_composition():
    """测试视频合成（图片+音频）"""
    image_file = "test_image.jpg"
    audio_file = "test_audio.mp3"
    output_file = "test_composition.mp4"
    
    # 合成命令
    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", image_file,
        "-i", audio_file,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_file
    ]
    
    result = run_ffmpeg_command(cmd, timeout=180)
    
    assert result["success"] == True
    assert os.path.exists(output_file)
    
    # 验证输出文件属性
    video_info = get_video_info(output_file)
    assert video_info["duration"] > 0
    assert video_info["has_audio"] == True
    
    # 清理
    if os.path.exists(output_file):
        os.remove(output_file)
```

## 5. AI内容生成模块测试

### 5.1 DeepSeek API测试

#### 测试用例 5.1.1: 文案生成
```python
async def test_ai_copywriting():
    """测试AI文案生成"""
    article_content = "这是一篇关于人工智能的新闻报道..."
    
    # 1. 生成新闻口播文案
    script = await generate_news_script(article_content)
    
    assert len(script) > 100  # 应该有足够长度
    assert "【口播文案】" in script or "大家好" in script  # 检查口播格式
    
    # 2. 生成用户需求文案
    user_request = "帮我写一个关于环保的短视频文案"
    user_script = await generate_user_script(user_request)
    
    assert len(user_script) > 50
    assert "环保" in user_script.lower()  # 应该包含关键词
    
    # 3. 测试API错误处理
    with pytest.raises(APIError):
        await generate_news_script("", max_tokens=10000)  # 超过限制
```

#### 测试用例 5.1.2: API速率限制
```python
async def test_api_rate_limiting():
    """测试API速率限制"""
    # 模拟并发请求（基于VPS性能，应该有限制）
    tasks = []
    for i in range(5):  # 超过建议的2-3个并发
        task = asyncio.create_task(
            generate_news_script(f"测试内容{i}")
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 应该有些请求被限制
    rate_limited = sum(1 for r in results if isinstance(r, RateLimitError))
    assert rate_limited > 0  # 应该有被限制的请求
```

### 5.2 TTS语音合成测试

#### 测试用例 5.2.1: 三级TTS备选方案
```python
async def test_tts_fallback():
    """测试TTS三级备选方案"""
    text = "这是一个测试文本，用于语音合成。"
    
    # 1. 尝试腾讯云TTS（第一级）
    try:
        audio1 = await tts_tencent(text, voice="zh-CN-Female")
        assert audio1 is not None
        assert len(audio1) > 1000  # 应该有足够的数据
    except TTSProviderError:
        # 2. 尝试Edge TTS（第二级）
        try:
            audio2 = await tts_edge(text, voice="zh-CN-XiaoxiaoNeural")
            assert audio2 is not None
        except TTSProviderError:
            # 3. 尝试OpenAI TTS（第三级）
