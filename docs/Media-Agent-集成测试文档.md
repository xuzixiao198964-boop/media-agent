# Media Agent 集成测试文档

## 文档信息
- **文档编号**: IT-001
- **文档标题**: Media Agent 集成测试文档
- **项目名称**: Media Agent（资讯 → 短视频 → 发布）
- **创建日期**: 2026-03-26
- **创建人**: Media Agent Assistant
- **状态**: 📝 草稿
- **版本**: 1.0
- **依据文档**: 
  - Media-Agent-最终版需求说明书.md（版本1.3）
  - Media-Agent-概要设计文档.md（版本1.1）
  - Media-Agent-单元测试文档.md（版本1.0）

## 1. 测试概述

### 1.1 测试目标
验证Media Agent系统各模块之间的集成功能，确保基于VPS性能优化的架构在实际环境中正常工作。

### 1.2 测试环境
- **服务器**: VPS 104.244.90.202（模拟实际生产环境）
- **架构**: 单服务器部署（Nginx + FastAPI + PostgreSQL + Celery）
- **网络**: 模拟公网访问条件
- **数据**: 使用测试数据库，与生产环境隔离

### 1.3 测试原则
- **端到端验证**: 从用户操作到最终结果的全流程测试
- **VPS性能验证**: 验证串行处理和资源限制
- **轻量级架构验证**: 验证去掉Redis后的系统稳定性
- **用户体验验证**: 验证等待时间管理和进度反馈

## 2. 用户认证集成测试

### 2.1 完整注册登录流程

#### 测试场景 2.1.1: 新用户注册登录
```python
async def test_new_user_registration_login():
    """测试新用户完整注册登录流程"""
    # 1. 用户访问注册页面
    register_page = await access_register_page()
    assert register_page.status == 200
    assert "用户名" in register_page.content
    assert "密码" in register_page.content
    assert "邮箱" not in register_page.content  # 已去掉邮箱
    assert "手机" not in register_page.content  # 已去掉手机
    
    # 2. 提交注册信息
    register_response = await submit_registration({
        "username": "integration_test_user",
        "password": "IntegrationTest123!@#"
    })
    assert register_response.status == 200
    assert "access_token" in register_response.json()
    
    # 3. 使用注册的凭据登录
    login_response = await submit_login({
        "login": "integration_test_user",
        "password": "IntegrationTest123!@#"
    })
    assert login_response.status == 200
    token = login_response.json()["access_token"]
    
    # 4. 访问需要认证的接口
    profile_response = await get_user_profile(token)
    assert profile_response.status == 200
    user_data = profile_response.json()
    assert user_data["username"] == "integration_test_user"
    assert user_data["display_name"] is None  # 新用户没有设置
    assert user_data["avatar_url"] is not None  # 应该有默认头像
    
    # 5. 验证会话管理
    sessions_response = await get_active_sessions(token)
    assert sessions_response.status == 200
    assert len(sessions_response.json()) == 1  # 当前只有一个会话
```

#### 测试场景 2.1.2: 并发用户注册压力测试
```python
async def test_concurrent_user_registration():
    """测试并发用户注册（基于VPS性能限制）"""
    # 模拟多个用户同时注册
    num_users = 10
    tasks = []
    
    for i in range(num_users):
        task = asyncio.create_task(
            submit_registration({
                "username": f"concurrent_user_{i}",
                "password": f"Password123!@{i}"
            })
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 统计结果
    successes = sum(1 for r in results if isinstance(r, dict) and "access_token" in r)
    failures = sum(1 for r in results if isinstance(r, Exception))
    
    print(f"并发注册测试: {successes} 成功, {failures} 失败")
    
    # 基于VPS性能，应该能处理但可能有延迟
    assert successes > num_users * 0.8  # 至少80%成功
    assert failures < num_users * 0.2   # 最多20%失败（可能因资源限制）
```

### 2.2 登录限制集成测试

#### 测试场景 2.2.1: IP级别登录限制
```python
async def test_ip_level_login_restriction():
    """测试IP级别登录限制集成"""
    test_user = await create_test_user()
    test_ip = "192.168.100.1"
    
    # 模拟来自同一IP的多次失败登录
    failure_responses = []
    for attempt in range(5):
        response = await submit_login({
            "login": test_user.username,
            "password": "WrongPassword",
            "client_ip": test_ip
        })
        failure_responses.append(response)
    
    # 分析响应
    delays = []
    for i, resp in enumerate(failure_responses):
        if i < 2:
            # 前2次失败应该正常响应
            assert resp.status == 401
            assert resp.elapsed.total_seconds() < 0.5
        elif i < 4:
            # 第3-4次失败应该有延迟
            assert resp.status == 401
            assert resp.elapsed.total_seconds() >= 1.0
            delays.append(resp.elapsed.total_seconds())
        else:
            # 第5次失败应该被封锁
            assert resp.status == 429  # Too Many Requests
            assert "IP封锁" in resp.json().get("detail", "")
    
    # 验证IP封锁后，正确密码也无法登录
    blocked_response = await submit_login({
        "login": test_user.username,
        "password": test_user.password,  # 正确密码
        "client_ip": test_ip
    })
    assert blocked_response.status == 429
    
    # 等待封锁时间过后再测试
    await asyncio.sleep(30 * 60)  # 30分钟封锁时间
    
    recovery_response = await submit_login({
        "login": test_user.username,
        "password": test_user.password,
        "client_ip": test_ip
    })
    assert recovery_response.status == 200  # 应该可以正常登录
```

## 3. 资讯抓取集成测试

### 3.1 完整资讯处理流程

#### 测试场景 3.1.1: RSS抓取到文章存储
```python
async def test_rss_to_article_pipeline():
    """测试从RSS抓取到文章存储的完整流程"""
    # 1. 配置RSS源
    category_id = await create_test_category({
        "name": "测试分类",
        "rss_urls": ["https://example-test.com/feed.xml"],
        "fetch_interval_minutes": 5
    })
    
    # 2. 触发定时抓取任务
    trigger_response = await trigger_fetch_task(category_id)
    assert trigger_response.status == 202  # Accepted
    task_id = trigger_response.json()["task_id"]
    
    # 3. 等待任务完成
    task_result = await wait_for_task_result(task_id, timeout=300)
    assert task_result["status"] == "completed"
    assert task_result["articles_fetched"] > 0
    
    # 4. 验证文章已存储
    articles_response = await get_category_articles(category_id)
    assert articles_response.status == 200
    articles = articles_response.json()
    assert len(articles) == task_result["articles_fetched"]
    
    # 5. 验证文章内容
    for article in articles:
        assert article["title"]
        assert article["source_url"]
        assert article["content_hash"]
        assert article["status"] == "active"
        
        # 验证去重功能
        duplicate_check = await check_article_duplicate(article["content_hash"])
        assert duplicate_check["is_duplicate"] == True
```

#### 测试场景 3.1.2: 并发抓取任务管理
```python
async def test_concurrent_fetch_tasks():
    """测试并发抓取任务管理（基于VPS性能）"""
    # 创建多个分类
    categories = []
    for i in range(3):  # 基于VPS性能，允许2-3个并发抓取
        category = await create_test_category({
            "name": f"并发测试分类{i}",
            "rss_urls": [f"https://test{i}.com/feed.xml"],
            "fetch_interval_minutes": 1
        })
        categories.append(category)
    
    # 同时触发所有抓取任务
    tasks = []
    for category in categories:
        task = asyncio.create_task(trigger_fetch_task(category["id"]))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    # 验证任务状态
    active_tasks = await get_active_fetch_tasks()
    print(f"活跃抓取任务数: {len(active_tasks)}")
    
    # 基于VPS性能，应该允许2-3个并发抓取
    assert 1 <= len(active_tasks) <= 3
    
    # 监控系统资源
    system_metrics = await get_system_metrics()
    print(f"系统负载: CPU={system_metrics['cpu_percent']}%, Memory={system_metrics['memory_percent']}%")
    
    # 应该保持在合理范围内
    assert system_metrics["cpu_percent"] < 80
    assert system_metrics["memory_percent"] < 80
```

## 4. 视频生成集成测试

### 4.1 完整视频生成流程

#### 测试场景 4.1.1: 文章到视频的完整转换
```python
async def test_article_to_video_pipeline():
    """测试从文章到视频的完整生成流程"""
    # 1. 准备测试文章
    article = await create_test_article({
        "title": "人工智能改变世界",
        "content": "人工智能正在深刻改变我们的生活和工作方式...",
        "category_id": 1
    })
    
    # 2. 提交视频生成任务
    generation_response = await submit_video_generation({
        "article_id": article["id"],
        "template": "news_report",
        "voice": "zh-CN-Female",
        "background_music": "light"
    })
    
    assert generation_response.status == 202
    task_id = generation_response.json()["task_id"]
    
    # 3. 获取任务状态（验证进度反馈）
    progress_updates = []
    for _ in range(10):  # 轮询10次
        status_response = await get_task_status(task_id)
        assert status_response.status == 200
        
        status_data = status_response.json()
        progress_updates.append(status_data["progress"])
        
        print(f"任务进度: {status_data['progress']}% - {status_data['message']}")
        
        if status_data["status"] == "completed":
            break
            
        await asyncio.sleep(10)  # 每10秒检查一次
    
    # 4. 验证进度更新
    assert len(progress_updates) > 1
    assert progress_updates[0] < progress_updates[-1]  # 进度应该增加
    assert 100 in progress_updates  # 应该达到100%
    
    # 5. 获取生成结果
    result_response = await get_task_result(task_id)
    assert result_response.status == 200
    
    result_data = result_response.json()
    assert result_data["video_url"] is not None
    assert result_data["duration"] > 0
    assert result_data["file_size"] > 0
    
    # 6. 验证视频文件可访问
    video_response = await download_video(result_data["video_url"])
    assert video_response.status == 200
    assert len(video_response.content) == result_data["file_size"]
```

#### 测试场景 4.1.2: 串行任务队列验证
```python
async def test_serial_task_queue_integration():
    """测试串行任务队列集成（基于VPS性能限制）"""
    # 提交多个视频生成任务
    task_ids = []
    for i in range(5):  # 超过最大排队数
        response = await submit_video_generation({
            "article_id": i + 100,
            "template": "default"
        })
        
        if response.status == 202:
            task_ids.append(response.json()["task_id"])
        elif response.status == 429:  # 队列满
            print(f"任务{i}被拒绝: 队列已满")
            break
    
    print(f"成功提交 {len(task_ids)} 个任务")
    
    # 验证队列状态
    queue_status = await get_queue_status()
    print(f"队列状态: {queue_status}")
    
    # 基于VPS性能，最大10个排队任务
    assert queue_status["video_generation"]["queue_length"] <= 10
    
    # 验证串行处理
    active_tasks = 0
    completed_tasks = 0
    
    # 监控任务执行
    for task_id in task_ids:
        for _ in range(30):  # 最多等待5分钟
            status = await get_task_status(task_id)
            status_data = status.json()
            
            if status_data["status"] == "processing":
                active_tasks += 1
            elif status_data["status"] == "completed":
                completed_tasks += 1
                break
                
            await asyncio.sleep(10)
    
    print(f"活跃任务: {active_tasks}, 完成任务: {completed_tasks}")
    
    # 验证串行处理原则
    assert active_tasks <= 1  # 同一时间最多一个任务在处理
    assert completed_tasks > 0  # 至少完成一个任务
```

### 4.2 用户等待时间管理

#### 测试场景 4.2.1: 等待时间估算和反馈
```python
async def test_wait_time_management():
    """测试用户等待时间管理集成"""
    # 1. 获取当前队列状态
    queue_status = await get_queue_status()
    
    # 2. 提交新任务前获取预计等待时间
    estimate_response = await estimate_wait_time({
        "task_type": "video_generation",
        "priority": "normal"
    })
    
    assert estimate_response.status == 200
    estimate_data = estimate_response.json()
    
    print(f"预计等待时间: {estimate_data['estimated_wait']}")
    print(f"当前排队任务: {estimate_data['queue_position']}")
    
    # 3. 提交任务
    submit_response = await submit_video_generation({
        "article_id": 999,
        "template": "test"
    })
    
    if submit_response.status == 202:
        task_id = submit_response.json()["task_id"]
        
        # 4. 获取实时进度反馈
        progress_messages = []
        
        async for progress_update in stream_task_progress(task_id):
            progress_messages.append(progress_update)
            print(f"进度更新: {progress_update}")
            
            # 验证进度消息格式
            assert "progress" in progress_update
            assert "message" in progress_update
            assert "estimated_remaining" in progress_update
            
            if progress_update["progress"] == 100:
                break
        
        # 5. 验证进度反馈完整性
        assert len(progress_messages) >= 4  # 至少应该有4个阶段更新
        
        stages = [msg["message"] for msg in progress_messages]
        expected_stages = ["任务排队中", "AI生成文案中", "语音合成中", "视频合成中", "视频生成完成"]
        
        # 检查是否包含关键阶段
        for expected in expected_stages:
            assert any(expected in stage for stage in stages)
    
    elif submit_response.status == 429:  # 队列满
        error_data = submit_response.json()
        assert "当前任务队列已满" in error_data["detail"]
        assert "请稍后再试" in error_data["detail"]
```

## 5. 系统性能集成测试

### 5.1 VPS性能边界测试

#### 测试场景 5.1.1: 系统负载监控和调整
```python
async def test_system_load_monitoring():
    """测试系统负载监控和动态调整"""
    # 1. 获取初始系统状态
    initial_metrics = await get_system_metrics()
    print(f"初始状态: CPU={initial_metrics['cpu_percent']}%, Memory={initial_metrics['memory_percent']}%")
    
    # 2. 创建负载测试任务
    load_tasks = []
    for i in range(5):  # 创建多个视频生成任务
        task = asyncio.create_task(
            submit_video_generation({
                "article_id": 1000 + i,
                "template": "stress_test"
            })
        )
        load_tasks.append(task)
    
    await asyncio.gather(*load_tasks)
    
    # 3. 监控系统负载变化
    metrics_history = []
    for _ in range(10):  # 监控1分钟
        metrics = await get_system_metrics()
        metrics_history.append(metrics)
        
        print(f"监控点: CPU={metrics['cpu_percent']}%, Memory={metrics['memory_percent']}%")
        
        # 验证动态调整
        if metrics["cpu_percent"] > 80 or metrics["memory_percent"] > 80:
            print("⚠️ 高负载警告触发")
            
            # 检查是否降低了并发
            queue_config = await get_queue_config()
            assert queue_config["video_generation"]["concurrency"] == 1  # 应该保持串行
            
            # 检查是否有任务被暂停或延迟
            active_count = await get_active_task_count()
            assert active_count <= 1  # 串行处理
        
        await asyncio.sleep(6)  # 每6