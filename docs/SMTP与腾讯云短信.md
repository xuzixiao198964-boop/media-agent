# 邮件（SMTP）与腾讯云短信

## 一、QQ 邮箱发信（SMTP）

验证码邮件由后端 `send_email()` 发出，需在环境变量中配置 SMTP（与 `app/config.py` 中字段对应）。

### 1. 在 QQ 邮箱开启 SMTP

1. 登录 [QQ 邮箱](https://mail.qq.com) → **设置** → **账号**。
2. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务**。
3. 开启 **IMAP/SMTP 服务**（或按页面提示开启发信服务）。
4. 按提示发送短信后，会得到 **授权码**（不是 QQ 密码），请单独保存。

### 2. 服务端环境变量示例

写入 `backend/.env` 或服务器 `/opt/media-agent/media-agent.env` 后重启 `media-agent-api`：

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=你的QQ号@qq.com
SMTP_PASSWORD=上面拿到的授权码
SMTP_FROM=你的QQ号@qq.com
SMTP_USE_TLS=true
```

- **SMTP_FROM** 一般与 **SMTP_USER** 一致（发件人显示地址）。
- 若 587 不通，可尝试 **465** 且将 `SMTP_USE_TLS` 按你方邮件商说明调整（部分环境需 SSL 而非 STARTTLS）。

### 3. 生效方式

```bash
sudo systemctl restart media-agent-api.service
```

---

## 二、腾讯云短信（国内手机验证码）

### 官方入口（请收藏）

| 说明 | 地址 |
|------|------|
| **短信控制台（国内短信）** | [https://console.cloud.tencent.com/smsv2](https://console.cloud.tencent.com/smsv2) |
| **产品文档首页** | [https://cloud.tencent.com/document/product/382](https://cloud.tencent.com/document/product/382) |
| **新手入门 / 快速接入** | [https://cloud.tencent.com/document/product/382/37745](https://cloud.tencent.com/document/product/382/37745) |
| **创建签名与模板** | [https://cloud.tencent.com/document/product/382/55981](https://cloud.tencent.com/document/product/382/55981) |

### 开通与接入步骤（概要）

1. **注册/登录** [腾讯云控制台](https://console.cloud.tencent.com/)。
2. **实名认证**：个人或企业认证（短信业务通常要求完成认证）。
3. 进入 **短信** → [短信控制台](https://console.cloud.tencent.com/smsv2)。
4. **创建应用**（若控制台要求先建应用/SDKAppID，按向导操作）。
5. **申请短信签名**：如公司名/产品名（需与资质一致，审核约数小时～1 个工作日）。
6. **申请短信正文模板**：模板中需包含验证码变量（如 `{1}`），示例含义为「验证码为 xxx」类文案，**审核通过**后方可使用。
7. **购买套餐包**（按条计费，控制台有说明）。
8. 在 **访问管理** 创建 **API 密钥**（SecretId / SecretKey），用于服务端调用 [发送短信 API](https://cloud.tencent.com/document/product/382/55981)。

> 说明：当前仓库内 `send_sms()` 在 `sms_provider` 非空时仍为**占位日志**，需你自行对接腾讯云短信 SDK（或后续在项目中接入 `tencentcloud-sdk-python` 与模板 ID）。配置好 SMTP 后，**邮箱验证码**可先正常使用；**短信**需完成腾讯云模板审核并编写对接代码。

---

## 三、仅测试时从日志查看验证码

未配置 SMTP/SMS 时，验证码会写入数据库表 `flow_logs`（`email_stub` / `sms_stub`），便于联调。
