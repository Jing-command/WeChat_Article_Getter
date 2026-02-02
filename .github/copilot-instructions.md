# Copilot 工作指引（WeChat_Article_Getter）

## 项目概览（核心结构）
- Web 入口：web_app.py 使用 FastAPI + WebSocket 提供下载 API 与实时日志推送（按 session_id 分流）。
- 业务核心：core/engine.py 的 `CrawlerEngine` 负责搜索公众号、获取文章列表、下载并本地化 HTML/图片。
- 前端：templates/index.html + static/js/main.js（WebSocket 日志、API 调用、模式切换、暂停/清理）+ static/css/style.css（暗色主题 UI）。
- 扩展：static/extension/wechat-cookie-exporter（自研扩展源码）+ wechat-cookie-exporter.zip（下载包）。
- 凭证帮助页：templates/helper.html（仅保留自研扩展与 F12 手动获取）。
- 配置集中在 config.py（接口 URL、UA、休眠、默认输出目录）。

## 关键数据流
- 用户在页面输入 Token/Cookies → /api/download（携带 session_id）→ 解析 cookies → `CrawlerEngine` 初始化 → 获取文章列表或单篇元数据 → `download_articles_content()` 保存 HTML 与图片。
- 日志通过 `WebLogger` 按 session_id 重定向 stdout/stderr → /ws?session_id=xxx → 前端按 `[INFO]/[WARN]/[ERROR]/[SUCCESS]` 关键字着色（见 static/js/main.js 的 `appendLog()`）。
- 暂停/恢复：会话级 `session.is_paused`，引擎通过 `pause_check_callback` 轮询；前端可“暂停后清理并重置”。
- 并发：每个会话单独状态与下载目录（`download_path/session_id`）。
- 日志清理：每会话内存缓冲上限 + 后台定期清理不活跃会话。

## 运行与依赖（Web 版）
- 依赖文件：requirements-web.txt（FastAPI/Uvicorn/WebSocket/requests/bs4）。
- 入口：运行 web_app.py（内部 uvicorn 监听 0.0.0.0:8000）。
- 前端默认保存目录在页面里是 downloads；实际写入路径由请求的 `download_path` 决定，最终写入为 `download_path/session_id`。

## VPS 服务器部署与运行（Web 版）
- 服务器目录：/root/WeChat_Article_Getter
- 服务名：wechat-downloader（systemd）
- 对外域名：Jing-command.me
- 反向代理：Nginx（对外访问域名，通过反代到 127.0.0.1:8000）
- 启动命令（服务内使用虚拟环境）：
	- ExecStart=/root/WeChat_Article_Getter/myenv/bin/python3 /root/WeChat_Article_Getter/web_app.py
- 常用运维命令：
	- 查看状态：sudo systemctl status wechat-downloader
	- 重启服务：sudo systemctl restart wechat-downloader
	- 开机自启：sudo systemctl enable wechat-downloader
	- 查看日志：sudo journalctl -u wechat-downloader -f
- 代码更新流程：
	- cd /root/WeChat_Article_Getter
	- git pull origin web
	- sudo systemctl restart wechat-downloader
- 端口冲突处理：
	- sudo lsof -ti:8000 | xargs -r sudo kill -9
- 敏感文件：activation_keys.json 已加入 .gitignore，仅保存在服务器本地（保留已使用记录）。

## 项目约定/实现细节（需遵循）
- HTML 本地化：`_download_images_for_html()` 会移除脚本/iframe、内嵌外部 CSS、强制显示内容，并把图片保存到 `<标题>_files` 目录并改写 `src/data-src`。
- 视频处理：`_download_videos_for_html()` 识别视频号/公众号视频/iframe 并替换为提示文本（不下载）。
- 文件命名：`_sanitize_filename()` 过滤 Windows 非法字符，避免保存失败。
- 文章列表分页：`get_articles()`/`get_articles_by_date()` 每批 5 条，依赖 `Config.MIN_SLEEP/MAX_SLEEP` 随机延迟规避反爬。
- 错误处理：遇到 [ERROR] 级别日志时自动停止任务并重置状态；[WARN] 不中断任务。

## 集成点/外部依赖
- 微信公众平台接口：`Config.SEARCH_URL`、`Config.APPMSG_URL`，鉴权依赖用户提供的 Token/Cookies。
- HTTP 与解析：requests + BeautifulSoup4。

## 修改建议（定位代码）
- 调整下载逻辑/解析规则：core/engine.py。
- 改 Web API/日志推送/会话并发/清理：web_app.py。
- 改 UI/交互：templates/index.html 与 static/js/main.js；样式在 static/css/style.css。
- 改凭证获取说明与扩展入口：templates/helper.html 与 static/extension/wechat-cookie-exporter。
