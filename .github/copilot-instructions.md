# Copilot 工作指引（WeChat_Article_Getter）

## 项目概览（核心结构）
- Web 入口：web_app.py 使用 FastAPI + WebSocket 提供下载 API 与实时日志推送。
- 业务核心：core/engine.py 的 `CrawlerEngine` 负责搜索公众号、获取文章列表、下载并本地化 HTML/图片。
- 前端：templates/index.html + static/js/main.js（WebSocket 日志、API 调用、模式切换）+ static/css/style.css（暗色主题 UI）。
- 配置集中在 config.py（接口 URL、UA、休眠、默认输出目录、浏览器驱动）。

## 关键数据流
- 用户在页面输入 Token/Cookies → /api/download → 解析 cookies → `CrawlerEngine` 初始化 → 获取文章列表或单篇元数据 → `download_articles_content()` 保存 HTML 与图片。
- 日志通过 `WebLogger` 重定向 stdout/stderr → /ws WebSocket → 前端按 `[INFO]/[WARN]/[ERROR]/[SUCCESS]` 关键字着色（见 static/js/main.js 的 `appendLog()`）。
- 暂停/恢复：web_app.py 中 `state.is_paused`，引擎通过 `pause_check_callback` 轮询；下载循环里若暂停会等待或终止。

## 运行与依赖（Web 版）
- 依赖文件：requirements-web.txt（FastAPI/Uvicorn/WebSocket/requests/bs4）。
- 入口：运行 web_app.py（内部 uvicorn 监听 0.0.0.0:8000）。
- 前端默认保存目录在页面里是 downloads；实际写入路径由请求的 `download_path` 决定。

## 项目约定/实现细节（需遵循）
- HTML 本地化：`_download_images_for_html()` 会移除脚本/iframe、内嵌外部 CSS、强制显示内容，并把图片保存到 `<标题>_files` 目录并改写 `src/data-src`。
- 视频处理：`_download_videos_for_html()` 识别视频号/公众号视频/iframe 并替换为提示文本（不下载）。
- 文件命名：`_sanitize_filename()` 过滤 Windows 非法字符，避免保存失败。
- 文章列表分页：`get_articles()`/`get_articles_by_date()` 每批 5 条，依赖 `Config.MIN_SLEEP/MAX_SLEEP` 随机延迟规避反爬。

## 集成点/外部依赖
- 微信公众平台接口：`Config.SEARCH_URL`、`Config.APPMSG_URL`，鉴权依赖用户提供的 Token/Cookies。
- HTTP 与解析：requests + BeautifulSoup4。

## 修改建议（定位代码）
- 调整下载逻辑/解析规则：core/engine.py。
- 改 Web API/日志推送/状态控制：web_app.py。
- 改 UI/交互：templates/index.html 与 static/js/main.js；样式在 static/css/style.css。
