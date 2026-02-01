# 安全配置说明

## 已实施的安全措施

### 1. 🔒 CORS 跨域保护
**保护目标：** 防止其他网站调用你的 API

**配置：**
```python
allow_origins=[
    "https://jing-command.me",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]
```

**如需添加新域名：**
在 `web_app.py` 中找到 `CORSMiddleware` 配置，添加新域名到 `allow_origins` 列表。

---

### 2. ⚡ 速率限制
**保护目标：** 防止暴力破解激活码

| 端点类型 | 限制次数 | 时间窗口 |
|---------|---------|---------|
| 激活码验证 (`/api/verify_key`) | 10次 | 1分钟 |
| 下载请求 (`/api/download`) | 5次 | 1分钟 |
| 一般请求 | 60次 | 1分钟 |

**自动封禁机制：**
- 20次失败尝试后自动封禁 IP
- 封禁时长：1小时
- 自动解封

**调整限制：**
在 `web_app.py` 的 `RateLimiter` 类中修改：
```python
self.VERIFY_KEY_LIMIT = 10    # 调整验证次数
self.DOWNLOAD_LIMIT = 5       # 调整下载次数
self.MAX_FAILED = 20          # 调整封禁阈值
self.BAN_DURATION = 3600      # 调整封禁时长（秒）
```

---

### 3. 🛡️ 敏感信息脱敏
**保护目标：** 防止日志泄露 Token/Cookies/激活码

**脱敏规则：**

| 类型 | 原始格式 | 脱敏后 |
|-----|---------|--------|
| 激活码 | `S-1234-5678-9ABC-DEF0` | `S-1234-****-****-DEF0` |
| Token | `1234567890` | `123***890` |
| Cookies | `key=longlongvalue` | `key=long...alue` |

所有通过 WebSocket 发送的日志都会自动脱敏。

---

### 4. ✅ 输入验证
**保护目标：** 防止注入攻击

**验证项：**
- ✓ Token 必须是10位数字
- ✓ 激活码必须符合格式 `[SB]-XXXX-XXXX-XXXX-XXXX`
- ✓ 下载路径禁止包含 `..`、绝对路径、盘符
- ✓ URL/Token/Cookies 不能为空

---

### 5. 🔐 安全响应头
**保护目标：** 防止 XSS、点击劫持等攻击

**已添加的响应头：**
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

---

## 安全最佳实践

### 服务器配置
1. **文件权限：**
   ```bash
   chmod 600 activation_keys.json  # 仅所有者可读写
   chmod 700 /root/WeChat_Article_Getter  # 仅所有者访问
   ```

2. **防火墙规则：**
   ```bash
   # 只允许必要的端口
   ufw allow 22/tcp   # SSH
   ufw allow 80/tcp   # HTTP (Nginx)
   ufw allow 443/tcp  # HTTPS (Nginx)
   ufw enable
   ```

3. **Nginx 安全配置：**
   ```nginx
   # 隐藏版本号
   server_tokens off;
   
   # 限制请求大小
   client_max_body_size 1M;
   
   # 防止慢速攻击
   client_body_timeout 10s;
   client_header_timeout 10s;
   ```

### 日志监控
定期检查可疑活动：
```bash
# 查看封禁日志
grep "SECURITY" app.log

# 查看失败的验证尝试
grep "ERROR.*激活码" app.log

# 查看速率限制触发
grep "429" app.log
```

### 激活码管理
1. **定期更换：** 建议每月生成新的激活码
2. **已使用清理：** 定期删除已使用的激活码记录
3. **备份：** 定期备份 `activation_keys.json`

---

## 风险等级说明

### ✅ 已解决（高风险）
- [x] 速率限制
- [x] IP 封禁
- [x] CORS 保护
- [x] 日志脱敏
- [x] 输入验证

### ⚠️ 中风险（可选）
- [ ] 会话管理（单个激活码同时只能一个用户使用）
- [ ] 激活码加密存储（当前使用 SHA256 哈希已足够）
- [ ] 更详细的审计日志

### ℹ️ 低风险（可忽略）
- [ ] HTTPS 证书钉扎
- [ ] 请求签名验证
- [ ] IP 白名单（不适合公开服务）

---

## 紧急响应

### 如果发现攻击
1. **立即封禁 IP：**
   ```python
   # 在服务器 Python 控制台中
   from web_app import rate_limiter
   rate_limiter.blacklist['攻击者IP'] = datetime.now() + timedelta(days=365)
   ```

2. **查看日志：**
   ```bash
   tail -f app.log | grep -E "ERROR|SECURITY"
   ```

3. **重启服务：**
   ```bash
   sudo systemctl restart wechat-downloader
   ```

### 如果激活码泄露
1. **标记为已使用：**
   ```bash
   python activation_key_generator.py
   # 选择 "标记激活码为已使用"
   ```

2. **生成新激活码：**
   ```bash
   python activation_key_generator.py
   # 选择 "生成新激活码"
   ```

---

## 更新日志

### 2026-02-01
- ✅ 添加速率限制系统
- ✅ 添加 CORS 保护
- ✅ 添加敏感信息脱敏
- ✅ 添加输入验证
- ✅ 添加安全响应头
- ✅ 添加失败尝试追踪
- ✅ 添加自动封禁机制

---

## 技术支持

如有安全问题或建议，请：
1. 检查本文档是否有相关说明
2. 查看 `app.log` 获取详细错误信息
3. 提交 Issue 到 GitHub 仓库
