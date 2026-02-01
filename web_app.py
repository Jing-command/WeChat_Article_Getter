"""
FastAPI Web应用 - 微信文章下载器
提供Web界面实现GUI的所有功能
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import os
import sys
import io
from datetime import datetime, timedelta
from typing import Optional, Dict
import base64
from contextlib import redirect_stdout, redirect_stderr
from collections import defaultdict
import zipfile
import shutil
from pathlib import Path

from core.engine import CrawlerEngine
from activation_key_generator import ActivationKeyGenerator

# 初始化FastAPI应用
app = FastAPI(title="微信文章下载器")

# 初始化激活码生成器
key_generator = ActivationKeyGenerator()

# 配置CORS - 只允许你的域名访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://jing-command.me",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 速率限制配置
class RateLimiter:
    def __init__(self):
        # IP访问记录: {ip: {endpoint: [(timestamp, count)]}}
        self.requests: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        # 失败尝试记录: {ip: [(timestamp, endpoint)]}
        self.failed_attempts: Dict[str, list] = defaultdict(list)
        # 黑名单: {ip: block_until_timestamp}
        self.blacklist: Dict[str, datetime] = {}
        
        # 限制规则
        self.VERIFY_KEY_LIMIT = 10  # 10次/分钟
        self.DOWNLOAD_LIMIT = 5     # 5次/分钟
        self.GENERAL_LIMIT = 60     # 60次/分钟（一般请求）
        self.WINDOW = 60            # 时间窗口（秒）
        self.MAX_FAILED = 20        # 20次失败后封禁
        self.BAN_DURATION = 3600    # 封禁时长（秒）
    
    def _clean_old_records(self, ip: str, endpoint: str):
        """清理过期记录"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.WINDOW)
        
        if ip in self.requests and endpoint in self.requests[ip]:
            self.requests[ip][endpoint] = [
                (ts, count) for ts, count in self.requests[ip][endpoint]
                if ts > cutoff
            ]
    
    def _clean_failed_attempts(self, ip: str):
        """清理过期失败记录"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.WINDOW * 10)  # 保留10分钟内的失败记录
        
        if ip in self.failed_attempts:
            self.failed_attempts[ip] = [
                (ts, ep) for ts, ep in self.failed_attempts[ip]
                if ts > cutoff
            ]
    
    def is_blocked(self, ip: str) -> bool:
        """检查IP是否被封禁"""
        if ip in self.blacklist:
            if datetime.now() < self.blacklist[ip]:
                return True
            else:
                del self.blacklist[ip]
        return False
    
    def check_rate_limit(self, ip: str, endpoint: str) -> bool:
        """检查是否超过速率限制"""
        # 检查黑名单
        if self.is_blocked(ip):
            return False
        
        # 清理过期记录
        self._clean_old_records(ip, endpoint)
        self._clean_failed_attempts(ip)
        
        # 确定限制
        if "verify_key" in endpoint:
            limit = self.VERIFY_KEY_LIMIT
        elif "download" in endpoint:
            limit = self.DOWNLOAD_LIMIT
        else:
            limit = self.GENERAL_LIMIT
        
        # 统计当前窗口内的请求数
        current_count = sum(count for _, count in self.requests[ip][endpoint])
        
        if current_count >= limit:
            return False
        
        # 记录本次请求
        now = datetime.now()
        self.requests[ip][endpoint].append((now, 1))
        return True
    
    def record_failure(self, ip: str, endpoint: str):
        """记录失败尝试"""
        now = datetime.now()
        self.failed_attempts[ip].append((now, endpoint))
        
        # 检查是否需要封禁
        if len(self.failed_attempts[ip]) >= self.MAX_FAILED:
            self.blacklist[ip] = now + timedelta(seconds=self.BAN_DURATION)
            print(f"[SECURITY] IP {ip} 已被封禁 {self.BAN_DURATION}秒（失败尝试过多）")
    
    def get_remaining_time(self, ip: str) -> int:
        """获取封禁剩余时间"""
        if ip in self.blacklist:
            remaining = (self.blacklist[ip] - datetime.now()).total_seconds()
            return max(0, int(remaining))
        return 0

rate_limiter = RateLimiter()

# 速率限制中间件
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """全局速率限制中间件"""
    client_ip = request.client.host
    endpoint = request.url.path
    
    # 跳过静态文件检查
    if endpoint.startswith("/static/"):
        return await call_next(request)
    
    # 检查是否被封禁
    if rate_limiter.is_blocked(client_ip):
        remaining = rate_limiter.get_remaining_time(client_ip)
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": f"请求过于频繁，已被暂时封禁。请在 {remaining} 秒后重试。"
            }
        )
    
    # 检查速率限制
    if not rate_limiter.check_rate_limit(client_ip, endpoint):
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": "请求过于频繁，请稍后再试。"
            }
        )
    
    response = await call_next(request)
    
    # 添加安全响应头
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response

# 静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 全局状态管理
class AppState:
    def __init__(self):
        self.is_downloading = False
        self.is_paused = False
        self.engine = None
        self.download_task = None
        self.log_buffer = io.StringIO()
        self.active_websockets = []
        self.current_activation_key = None  # 当前使用的激活码
        self.current_key_type = None  # 当前激活码类型
        self.last_download_path = None  # 上次下载的路径
        self.last_zip_file = None  # 上次生成的 ZIP 文件路径
    
    def add_websocket(self, websocket):
        self.active_websockets.append(websocket)
    
    def remove_websocket(self, websocket):
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)
    
    async def broadcast_log(self, message: str):
        """广播日志到所有连接的WebSocket"""
        # 脱敏处理
        message = sanitize_log(message)
        for ws in self.active_websockets:
            try:
                await ws.send_json({"type": "log", "message": message})
            except:
                pass

state = AppState()

# 敏感信息脱敏工具
def sanitize_sensitive_data(data: str, show_chars: int = 4) -> str:
    """脱敏敏感数据，只显示前几位和后几位"""
    if not data or len(data) <= show_chars * 2:
        return "***"
    return f"{data[:show_chars]}...{data[-show_chars:]}"

def sanitize_log(message: str) -> str:
    """脱敏日志中的敏感信息"""
    import re
    
    # 脱敏 Token（10位数字）
    message = re.sub(
        r'\b(\d{3})\d{4}(\d{3})\b',
        r'\1***\2',
        message
    )
    
    # 脱敏 Cookies（长字符串）
    if 'cookie' in message.lower() or 'token' in message.lower():
        # 脱敏长字符串（可能是cookie值）
        message = re.sub(
            r'=([a-zA-Z0-9+/=]{20,})',
            lambda m: f"={sanitize_sensitive_data(m.group(1), 4)}",
            message
        )
    
    return message

# Pydantic模型定义
class DownloadRequest(BaseModel):
    url: str
    token: str
    cookies: str
    activation_key: str  # 新增：激活码字段
    single_mode: bool = True
    batch_mode: bool = False
    date_mode: bool = False
    count: int = 10
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    download_path: str

# 自定义日志输出类
class WebLogger(io.StringIO):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
    
    def write(self, message):
        if message.strip():
            asyncio.create_task(self.state.broadcast_log(message.strip()))
        return len(message)
    
    def flush(self):
        pass

# 路由定义
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/helper", response_class=HTMLResponse)
async def helper(request: Request):
    """凭证获取辅助页面"""
    return templates.TemplateResponse("helper.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接 - 用于实时日志推送"""
    await websocket.accept()
    state.add_websocket(websocket)
    
    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "log",
            "message": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        })
        await websocket.send_json({
            "type": "log",
            "message": "  🎉 欢迎使用微信文章下载器 Web版 v2.0"
        })
        await websocket.send_json({
            "type": "log",
            "message": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        await websocket.send_json({
            "type": "log",
            "message": "[SUCCESS] ✅ 系统初始化完成！"
        })
        await websocket.send_json({
            "type": "log",
            "message": "[INFO] 📡 WebSocket 连接已建立，日志推送就绪"
        })
        await websocket.send_json({
            "type": "log",
            "message": "[INFO] 🔐 激活码验证系统已加载"
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        await websocket.send_json({
            "type": "log",
            "message": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        })
        await websocket.send_json({
            "type": "log",
            "message": "📋 使用步骤："
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        await websocket.send_json({
            "type": "log",
            "message": "  1️⃣  输入激活码"
        })
        await websocket.send_json({
            "type": "log",
            "message": "      • S- 开头：单次下载"
        })
        await websocket.send_json({
            "type": "log",
            "message": "      • B- 开头：批量下载（包括日期范围）"
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        await websocket.send_json({
            "type": "log",
            "message": "  2️⃣  获取登录凭证"
        })
        await websocket.send_json({
            "type": "log",
            "message": "      • 点击蓝色按钮查看【一键复制工具】"
        })
        await websocket.send_json({
            "type": "log",
            "message": "      • 登录微信公众平台获取 Token 和 Cookies"
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        await websocket.send_json({
            "type": "log",
            "message": "  3️⃣  输入链接或公众号名称"
        })
        await websocket.send_json({
            "type": "log",
            "message": "      • 单次：输入文章链接"
        })
        await websocket.send_json({
            "type": "log",
            "message": "      • 批量：输入公众号名称或任意文章链接"
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        await websocket.send_json({
            "type": "log",
            "message": "  4️⃣  选择下载模式并点击【开始下载】"
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        await websocket.send_json({
            "type": "log",
            "message": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        await websocket.send_json({
            "type": "log",
            "message": "✨ 系统就绪，请按照上述步骤开始使用"
        })
        await websocket.send_json({
            "type": "log",
            "message": "💡 提示：下载完成后激活码会自动失效，请准备新的激活码继续使用"
        })
        await websocket.send_json({
            "type": "log",
            "message": ""
        })
        
        # 保持连接
        while True:
            data = await websocket.receive_text()
            # 处理客户端消息（如果需要）
            
    except WebSocketDisconnect:
        state.remove_websocket(websocket)

@app.post("/api/login")
async def login():
    """登录接口 - 已废弃，保留用于兼容"""
    return {"success": False, "message": "请使用手动输入Token和Cookies的方式"}

@app.post("/api/verify_key")
async def verify_activation_key(request: dict, req: Request):
    """验证激活码有效性"""
    client_ip = req.client.host
    activation_key = request.get("activation_key", "").strip()
    
    if not activation_key:
        return {"valid": False, "message": "请输入激活码"}
    
    # 验证格式
    import re
    if not re.match(r'^[SB]-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$', activation_key):
        rate_limiter.record_failure(client_ip, "/api/verify_key")
        return {"valid": False, "message": "格式错误", "type": None}
    
    # 判断类型
    key_type = "single" if activation_key.startswith("S-") else "batch"
    type_name = "单次下载" if key_type == "single" else "批量下载"
    
    # 验证有效性
    is_valid = key_generator.verify_key(activation_key, key_type)
    
    if is_valid:
        return {
            "valid": True, 
            "message": f"有效 ({type_name})", 
            "type": key_type,
            "type_name": type_name
        }
    else:
        # 记录失败尝试
        rate_limiter.record_failure(client_ip, "/api/verify_key")
        return {
            "valid": False, 
            "message": "无效或已使用", 
            "type": key_type,
            "type_name": type_name
        }

@app.post("/api/download")
async def start_download(request: DownloadRequest, req: Request):
    """开始下载"""
    client_ip = req.client.host
    
    if state.is_downloading:
        return {"success": False, "message": "已有下载任务在进行中"}
    
    # 输入验证
    if not request.url or not request.url.strip():
        return {"success": False, "message": "请输入公众号名称或文章链接"}
    
    if not request.token or not request.token.strip():
        return {"success": False, "message": "请输入 Token"}
    
    if not request.cookies or not request.cookies.strip():
        return {"success": False, "message": "请输入 Cookies"}
    
    # Token 格式验证（应该是10位数字）
    import re
    if not re.match(r'^\d{10}$', request.token.strip()):
        rate_limiter.record_failure(client_ip, "/api/download")
        return {"success": False, "message": "Token 格式错误，应为10位数字"}
    
    # 路径验证（防止路径注入）
    download_path = request.download_path.strip()
    if '..' in download_path or download_path.startswith('/') or ':' in download_path[1:]:
        rate_limiter.record_failure(client_ip, "/api/download")
        return {"success": False, "message": "下载路径格式错误"}
    
    # 验证激活码
    activation_key = request.activation_key.strip()
    
    # 判断下载模式并验证对应类型的激活码
    if request.batch_mode or request.date_mode:
        # 批量下载（包括日期范围下载），需要批量激活码
        if not key_generator.verify_key(activation_key, "batch"):
            rate_limiter.record_failure(client_ip, "/api/download")
            await state.broadcast_log("[ERROR] 批量下载（包括日期范围下载）需要有效的批量下载激活码 (B- 开头)")
            return {"success": False, "message": "激活码无效或已被使用，批量下载（包括日期范围下载）需要使用 B- 开头的激活码"}
        key_type = "batch"
    else:
        # 单次下载，需要单次激活码
        if not key_generator.verify_key(activation_key, "single"):
            rate_limiter.record_failure(client_ip, "/api/download")
            await state.broadcast_log("[ERROR] 单次下载需要有效的单次下载激活码 (S- 开头)")
            return {"success": False, "message": "激活码无效或已被使用，单次下载需要使用 S- 开头的激活码"}
        key_type = "single"
    
    # 保存当前激活码信息，等下载成功后再标记为已使用
    state.current_activation_key = activation_key
    state.current_key_type = key_type
    
    # 脱敏日志（Token 脱敏，激活码不脱敏）
    safe_token = sanitize_sensitive_data(request.token, 3)
    await state.broadcast_log(f"[SUCCESS] 激活码验证通过 (类型: {'批量下载' if key_type == 'batch' else '单次下载'}, Key: {activation_key})")
    await state.broadcast_log(f"[INFO] Token: {safe_token}, IP: {client_ip}")
    
    # 重定向标准输出到WebSocket
    sys.stdout = WebLogger(state)
    sys.stderr = WebLogger(state)
    
    state.is_downloading = True
    state.is_paused = False
    
    # 创建下载任务
    state.download_task = asyncio.create_task(
        run_download_async(request)
    )
    
    return {"success": True, "message": "下载任务已启动"}

async def run_download_async(request: DownloadRequest):
    """异步下载函数"""
    try:
        await state.broadcast_log(f"\n[TASK] 开始处理链接: {request.url}")
        await state.broadcast_log(f"[PATH] 保存路径: {request.download_path}")
        
        if request.date_mode:
            await state.broadcast_log(f"[MODE] 日期范围下载模式: {request.start_date} 至 {request.end_date}")
        elif request.batch_mode:
            await state.broadcast_log(f"[MODE] 批量下载模式: 最近 {request.count} 篇")
        elif request.single_mode:
            await state.broadcast_log(f"[MODE] 单篇下载模式")
        
        # 解析用户提供的cookies字符串
        await state.broadcast_log("[INFO] 正在解析登录凭证...")
        cookies_dict = {}
        try:
            # 解析cookies字符串: "name=value; name2=value2"
            cookie_pairs = request.cookies.split(';')
            for pair in cookie_pairs:
                if '=' in pair:
                    name, value = pair.strip().split('=', 1)
                    cookies_dict[name.strip()] = value.strip()
            
            await state.broadcast_log(f"[SUCCESS] 成功解析 {len(cookies_dict)} 个cookies")
            # Token 已在前面脱敏输出，这里不再重复
        except Exception as e:
            await state.broadcast_log(f"[ERROR] Cookies解析失败: {str(e)}")
            return
        
        if not cookies_dict or not request.token:
            await state.broadcast_log("[ERROR] 登录凭证无效")
            return
        
        # 初始化引擎
        state.engine = CrawlerEngine(cookies_dict, request.token, output_dir=request.download_path)
        state.engine.pause_check_callback = check_pause_sync
        
        articles = []
        
        if request.batch_mode:
            # 批量下载
            fakeid = None
            
            if request.url.startswith('http://') or request.url.startswith('https://'):
                await state.broadcast_log("[INFO] 检测到链接，正在从链接解析公众号信息...")
                fakeid = state.engine.extract_fakeid_from_url(request.url)
                
                if not fakeid:
                    await state.broadcast_log("[WARN] 无法从链接中提取公众号信息")
                    return
            else:
                await state.broadcast_log(f"[INFO] 检测到公众号名称，正在搜索: {request.url}")
                fakeid = state.engine.search_account(request.url)
            
            if not fakeid:
                await state.broadcast_log("[ERROR] 无法找到目标公众号")
                return
            
            await state.broadcast_log(f"[INFO] 识别到公众号 FakeID: {fakeid}")
            
            if request.date_mode:
                await state.broadcast_log(f"[INFO] 正在获取 {request.start_date} 至 {request.end_date} 期间的文章...")
                articles = state.engine.get_articles_by_date(fakeid, request.start_date, request.end_date)
            else:
                await state.broadcast_log(f"[INFO] 正在获取最近 {request.count} 篇文章...")
                articles = state.engine.get_articles(fakeid, request.count)
            
            if not articles:
                await state.broadcast_log("[ERROR] 未获取到文章列表")
                return
            
            await state.broadcast_log(f"[INFO] 共获取到 {len(articles)} 篇文章")
        
        else:
            # 单篇下载
            await state.broadcast_log("[INFO] 正在获取文章元数据...")
            article_info = state.engine.fetch_article_metadata(request.url)
            
            if not article_info:
                await state.broadcast_log("[ERROR] 无法解析文章信息，请检查链接是否正确")
                return
            
            await state.broadcast_log(f"[INFO] 识别到文章: {article_info['title']}")
            articles = [article_info]
        
        # 下载内容
        state.engine.download_articles_content(articles)
        
        await state.broadcast_log(f"[SUCCESS] 任务完成！")
        if request.batch_mode:
            if request.date_mode:
                await state.broadcast_log(f"共下载 {len(articles)} 篇文章 ({request.start_date} 至 {request.end_date})")
            else:
                await state.broadcast_log(f"共下载 {len(articles)} 篇文章")
        else:
            await state.broadcast_log(f"文章《{articles[0]['title']}》下载完成！")
        
        # 打包成 ZIP
        await state.broadcast_log(f"[INFO] 正在打包文件...")
        zip_filename = create_zip_package(request.download_path)
        if zip_filename:
            state.last_zip_file = zip_filename
            await state.broadcast_log(f"[SUCCESS] ✅ 文件已打包完成！点击下方按钮下载到本地")
        else:
            await state.broadcast_log(f"[WARN] 打包失败，但文件已保存在服务器")
        
        # 下载成功完成，标记激活码为已使用
        if state.current_activation_key:
            key_generator.mark_as_used(state.current_activation_key)
            key_type_name = "批量下载" if state.current_key_type == "batch" else "单次下载"
            await state.broadcast_log(f"[INFO] 激活码 {state.current_activation_key} 已使用 (类型: {key_type_name})")
            await state.broadcast_log(f"[WARN] ⚠️  该激活码已失效，如需继续下载请使用新的激活码")
        
        # 广播完成状态，包含下载文件名
        for ws in state.active_websockets:
            try:
                await ws.send_json({
                    "type": "download_complete", 
                    "key_used": True,
                    "zip_file": os.path.basename(zip_filename) if zip_filename else None
                })
            except:
                pass
    
    except Exception as e:
        await state.broadcast_log(f"[ERROR] 发生未捕获异常: {e}")
        import traceback
        error_trace = traceback.format_exc()
        await state.broadcast_log(error_trace)
        
        # 下载失败，不标记激活码为已使用
        await state.broadcast_log(f"[INFO] 由于下载失败，激活码未被消耗，可以重新尝试")
    
    finally:
        # 清空当前激活码信息
        state.current_activation_key = None
        state.current_key_type = None
        state.is_downloading = False
        state.is_paused = False

def check_pause_sync():
    """同步暂停检查函数"""
    if state.is_paused:
        import time
        while state.is_paused and state.is_downloading:
            time.sleep(0.5)

def create_zip_package(download_path: str) -> Optional[str]:
    """
    将下载的文件打包成 ZIP
    
    Args:
        download_path: 下载目录路径
        
    Returns:
        ZIP文件的绝对路径，失败返回 None
    """
    try:
        # 创建临时ZIP目录
        zip_dir = Path("temp_zips")
        zip_dir.mkdir(exist_ok=True)
        
        # 生成ZIP文件名（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"wechat_articles_{timestamp}.zip"
        zip_path = zip_dir / zip_filename
        
        # 检查下载目录是否存在
        download_dir = Path(download_path)
        if not download_dir.exists():
            print(f"[ERROR] 下载目录不存在: {download_path}")
            return None
        
        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 遍历下载目录中的所有文件
            for file_path in download_dir.rglob('*'):
                if file_path.is_file():
                    # 计算相对路径
                    arcname = file_path.relative_to(download_dir)
                    zipf.write(file_path, arcname)
        
        print(f"[SUCCESS] ZIP打包完成: {zip_path}")
        
        # 打包成功后删除原文件
        try:
            shutil.rmtree(download_dir)
            print(f"[CLEANUP] 已删除原始下载目录: {download_path}")
        except Exception as e:
            print(f"[WARN] 删除原始文件失败: {e}")
        
        return str(zip_path)
    
    except Exception as e:
        print(f"[ERROR] ZIP打包失败: {e}")
        return None

def cleanup_old_zips():
    """清理超过24小时的ZIP文件"""
    try:
        zip_dir = Path("temp_zips")
        if not zip_dir.exists():
            return
        
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for zip_file in zip_dir.glob("*.zip"):
            file_time = datetime.fromtimestamp(zip_file.stat().st_mtime)
            if file_time < cutoff_time:
                zip_file.unlink()
                print(f"[CLEANUP] 已删除过期ZIP: {zip_file.name}")
    
    except Exception as e:
        print(f"[ERROR] 清理ZIP文件失败: {e}")

@app.post("/api/pause")
async def pause_download():
    """暂停下载"""
    if not state.is_downloading:
        return {"success": False, "message": "当前没有下载任务"}
    
    state.is_paused = True
    await state.broadcast_log("\n[ACTION] 下载已暂停，点击'恢复'按钮继续\n")
    return {"success": True, "message": "已暂停"}

@app.post("/api/resume")
async def resume_download():
    """恢复下载"""
    if not state.is_downloading:
        return {"success": False, "message": "当前没有下载任务"}
    
    if not state.is_paused:
        return {"success": False, "message": "当前未暂停"}
    
    await state.broadcast_log("\n[ACTION] 正在恢复下载...")
    await state.broadcast_log("[INFO] 继续下载中...")
    
    state.is_paused = False
    await state.broadcast_log("[INFO] 已恢复下载\n")
    return {"success": True, "message": "已恢复"}

@app.get("/api/status")
async def get_status():
    """获取当前状态"""
    return {
        "is_downloading": state.is_downloading,
        "is_paused": state.is_paused
    }

@app.get("/api/download_file/{filename}")
async def download_zip_file(filename: str):
    """下载ZIP文件"""
    try:
        # 安全检查：只允许下载temp_zips目录下的zip文件
        if not filename.endswith('.zip') or '..' in filename or '/' in filename:
            raise HTTPException(status_code=400, detail="无效的文件名")
        
        zip_path = Path("temp_zips") / filename
        
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在或已过期")
        
        # 清理旧文件
        cleanup_old_zips()
        
        return FileResponse(
            path=str(zip_path),
            filename=filename,
            media_type='application/zip'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("🚀 启动微信文章下载器 Web服务...")
    print("📱 请在浏览器中访问: http://localhost:8000")
    
    # 启动时清理旧ZIP文件
    cleanup_old_zips()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
