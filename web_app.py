"""
FastAPI Web应用 - 微信文章下载器
提供Web界面实现GUI的所有功能
"""

import os
import sys

# 禁用 Python 输出缓冲，确保日志实时输出
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
import asyncio
import json
import io
from datetime import datetime, timedelta
from typing import Optional, Dict
import base64
from contextlib import redirect_stdout, redirect_stderr
from collections import defaultdict, deque
import zipfile
import shutil
from pathlib import Path

from core.engine import CrawlerEngine
from activation_key_generator import ActivationKeyGenerator

# 初始化FastAPI应用
app = FastAPI(title="微信文章下载器")

# 启动后台清理任务
@app.on_event("startup")
async def startup_cleanup_task():
    asyncio.create_task(cleanup_sessions_task())

# 初始化激活码生成器
key_generator = ActivationKeyGenerator()

# 添加验证错误处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误"""
    print(f"[VALIDATION ERROR] {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": f"请求数据验证失败: {exc.errors()}"
        }
    )

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

# 会话状态管理
class SessionState:
    def __init__(self):
        self.is_downloading = False
        self.is_paused = False
        self.engine = None
        self.download_task = None
        self.log_buffer = deque(maxlen=5000)
        self.active_websockets = []
        self.last_active = datetime.now()
        self.current_activation_key = None  # 当前使用的激活码
        self.current_key_type = None  # 当前激活码类型
        self.last_download_path = None  # 上次下载的路径
        self.last_zip_file = None  # 上次生成的 ZIP 文件路径
        self.last_input = None  # 上次输入的链接或公众号名称

# 全局状态管理
class AppState:
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}

    def get_session(self, session_id: str) -> SessionState:
        session_id = normalize_session_id(session_id)
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        return self.sessions[session_id]

    def add_websocket(self, session_id: str, websocket):
        session = self.get_session(session_id)
        session.active_websockets.append(websocket)
        session.last_active = datetime.now()

    def remove_websocket(self, session_id: str, websocket):
        session = self.get_session(session_id)
        if websocket in session.active_websockets:
            session.active_websockets.remove(websocket)
        session.last_active = datetime.now()

    async def broadcast_log(self, session_id: str, message: str):
        """广播日志到指定会话的WebSocket"""
        # 脱敏处理
        message = sanitize_log(message)
        session = self.get_session(session_id)
        session.last_active = datetime.now()
        session.log_buffer.append(message)
        for ws in session.active_websockets:
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

def normalize_session_id(session_id: Optional[str]) -> str:
    """规范化会话ID，避免路径/注入风险"""
    import re

    if not session_id:
        return "default"

    session_id = session_id.strip()
    session_id = re.sub(r'[^a-zA-Z0-9_-]', '_', session_id)
    return session_id[:64] or "default"

def build_session_download_path(base_path: str, session_id: str) -> str:
    """按会话ID生成子目录路径"""
    safe_session = normalize_session_id(session_id)
    base = Path(base_path)
    return str(base / safe_session)

async def fail_task(session_id: str, message: str):
    """任务失败时自动停止并重置状态"""
    # 若是警告信息，不中断任务
    if "[WARN]" in message and "[ERROR]" not in message:
        await state.broadcast_log(session_id, message)
        return

    session = state.get_session(session_id)
    await state.broadcast_log(session_id, message)

    session.is_downloading = False
    session.is_paused = False

    # 通知前端重置按钮状态
    for ws in session.active_websockets:
        try:
            await ws.send_json({
                "type": "download_complete",
                "key_used": False,
                "zip_file": None
            })
        except:
            pass

async def cleanup_sessions_task():
    """定期清理不活跃会话的日志缓冲与状态"""
    while True:
        await asyncio.sleep(1800)  # 30分钟清理一次
        try:
            now = datetime.now()
            expired = []
            for session_id, session in state.sessions.items():
                # 仅清理空闲且非下载中的会话
                if session.active_websockets:
                    continue
                if session.is_downloading:
                    continue
                if now - session.last_active > timedelta(hours=6):
                    expired.append(session_id)

            for session_id in expired:
                del state.sessions[session_id]
                print(f"[CLEANUP] 已清理不活跃会话: {session_id}")
        except Exception as e:
            print(f"[ERROR] 清理会话失败: {e}")

# Pydantic模型定义
class DownloadRequest(BaseModel):
    session_id: str
    url: str
    credentials: str  # 合并的凭证字段
    activation_key: str  # 新增：激活码字段
    single_mode: bool = True
    batch_mode: bool = False
    date_mode: bool = False
    count: int = 10
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    download_path: str

class SessionRequest(BaseModel):
    session_id: str

# 自定义日志输出类
class WebLogger:
    """无缓冲的 WebSocket 日志输出"""
    def __init__(self, state: AppState, session_id: str):
        self.state = state
        self.session_id = session_id
        self.loop = None
    
    def write(self, message):
        if message.strip():
            # 获取或设置事件循环
            if self.loop is None:
                try:
                    self.loop = asyncio.get_running_loop()
                except RuntimeError:
                    return len(message)
            
            # 在事件循环中调度协程（立即执行）
            if self.loop and self.loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self.state.broadcast_log(self.session_id, message.strip()),
                    self.loop
                )
                # 等待一小段时间确保发送
                try:
                    future.result(timeout=0.1)
                except:
                    pass
        return len(message)
    
    def flush(self):
        """立即刷新缓冲区"""
        pass
    
    def isatty(self):
        return False

# 辅助函数：解析凭证字符串
def parse_credentials(credentials: str) -> tuple:
    """
    自动解析凭证字符串，提取 Token 和 Cookies
    支持标准格式和EditThisCookie JSON格式
    
    Args:
        credentials: 包含 Token 和 Cookies 的字符串
        
    Returns:
        (token, cookies) 元组
    """
    import re
    
    lines = credentials.strip().split('\n')
    token = None
    cookies = None
    
    # 检测是否包含JSON格式的Cookies（EditThisCookie导出格式）
    json_content = credentials.strip()
    if json_content.startswith('[') and json_content.endswith(']'):
        try:
            cookie_list = json.loads(json_content)
            if isinstance(cookie_list, list) and len(cookie_list) > 0:
                # 转换JSON格式为标准Cookie字符串
                cookie_parts = []
                required_cookies = {'appmsg_token', 'data_bizuin', 'bizuin', 'data_ticket', 'slave_sid', 'slave_user'}
                found_cookies = set()
                
                for cookie in cookie_list:
                    if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                        name = cookie['name']
                        value = cookie['value']
                        domain = cookie.get('domain', '')
                        
                        # 只保留微信公众平台相关的Cookie
                        if 'weixin.qq.com' in domain or 'qq.com' in domain:
                            cookie_parts.append(f"{name}={value}")
                            if name in required_cookies:
                                found_cookies.add(name)
                
                if cookie_parts:
                    cookies = '; '.join(cookie_parts)
                    print(f"[SUCCESS] 自动识别EditThisCookie JSON格式，已转换为标准格式")
                    print(f"[INFO] 共解析 {len(cookie_parts)} 个Cookie字段")
                    print(f"[INFO] 关键字段: {', '.join(sorted(found_cookies))}")
                    
                    missing = required_cookies - found_cookies
                    if missing:
                        print(f"[WARN] 缺少关键Cookie: {', '.join(missing)}")
                    
                    return None, cookies  # JSON格式只包含cookies，没有token
        except json.JSONDecodeError:
            pass  # 不是有效的JSON，继续尝试其他格式
    
    # 原有的标准格式解析逻辑
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 匹配 token: 开头的行（不区分大小写，支持中英文冒号）
        token_match = re.match(r'^token[：:]\s*(.+)$', line, re.IGNORECASE)
        if token_match:
            token = token_match.group(1).strip()
            continue
        
        # 匹配 cookies: 开头的行（不区分大小写，支持中英文冒号）
        cookies_match = re.match(r'^cookies[：:]\s*(.+)$', line, re.IGNORECASE)
        if cookies_match:
            cookies = cookies_match.group(1).strip()
            continue
        
        # 如果行中包含 = 且包含 ; 可能是 cookies（没有前缀）
        if '=' in line and ';' in line and not cookies:
            cookies = line
            continue
        
        # 如果是纯数字（8-12位）可能是 token（没有前缀）
        if re.match(r'^\d{8,12}$', line) and not token:
            token = line
            continue
    
    return token, cookies

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
    session_id = normalize_session_id(websocket.query_params.get("session_id"))
    state.add_websocket(session_id, websocket)
    
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
        state.remove_websocket(session_id, websocket)

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
    session_id = normalize_session_id(request.session_id)
    session = state.get_session(session_id)
    
    if session.is_downloading:
        return {"success": False, "message": "已有下载任务在进行中"}
    
    # 输入验证
    if not request.url or not request.url.strip():
        return {"success": False, "message": "请输入公众号名称或文章链接"}
    
    if not request.credentials or not request.credentials.strip():
        return {"success": False, "message": "请输入登录凭证（Token 和 Cookies）"}
    
    # 解析凭证
    token, cookies = parse_credentials(request.credentials)
    
    if not token:
        rate_limiter.record_failure(client_ip, "/api/download")
        return {"success": False, "message": "未找到 Token，请确保输入包含 Token（8-12位数字）"}
    
    if not cookies:
        rate_limiter.record_failure(client_ip, "/api/download")
        return {"success": False, "message": "未找到 Cookies，请确保输入包含 Cookies"}
    
    # Token 格式验证（通常是8-12位数字）
    import re
    token_stripped = token.strip()
    if not re.match(r'^\d{8,12}$', token_stripped):
        rate_limiter.record_failure(client_ip, "/api/download")
        return {"success": False, "message": "Token 格式错误，应为8-12位数字"}
    
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
            await state.broadcast_log(session_id, "[ERROR] 批量下载（包括日期范围下载）需要有效的批量下载激活码 (B- 开头)")
            return {"success": False, "message": "激活码无效或已被使用，批量下载（包括日期范围下载）需要使用 B- 开头的激活码"}
        key_type = "batch"
    else:
        # 单次下载，需要单次激活码
        if not key_generator.verify_key(activation_key, "single"):
            rate_limiter.record_failure(client_ip, "/api/download")
            await state.broadcast_log(session_id, "[ERROR] 单次下载需要有效的单次下载激活码 (S- 开头)")
            return {"success": False, "message": "激活码无效或已被使用，单次下载需要使用 S- 开头的激活码"}
        key_type = "single"
    
    # 保存当前激活码信息，等下载成功后再标记为已使用
    session.current_activation_key = activation_key
    session.current_key_type = key_type
    session.last_download_path = download_path
    session.last_input = request.url.strip()
    
    # 脱敏日志（Token 脱敏，激活码不脱敏）
    safe_token = sanitize_sensitive_data(token, 3)
    await state.broadcast_log(session_id, f"[SUCCESS] 激活码验证通过 (类型: {'批量下载' if key_type == 'batch' else '单次下载'}, Key: {activation_key})")
    await state.broadcast_log(session_id, f"[INFO] Token: {safe_token}, IP: {client_ip}")
    
    # 获取当前事件循环并重定向标准输出到WebSocket
    logger = WebLogger(state, session_id)
    logger.loop = asyncio.get_running_loop()
    sys.stdout = logger
    sys.stderr = logger
    
    session.is_downloading = True
    session.is_paused = False
    session_download_path = build_session_download_path(download_path, session_id)
    session.last_download_path = session_download_path
    
    # 创建下载任务
    session.download_task = asyncio.create_task(
        run_download_async(request, token, cookies, session_id, session_download_path)
    )
    
    return {"success": True, "message": "下载任务已启动"}

async def run_download_async(request: DownloadRequest, token: str, cookies: str, session_id: str, session_download_path: str):
    """异步下载函数"""
    session = state.get_session(session_id)
    try:
        await state.broadcast_log(session_id, f"\n[TASK] 开始处理链接: {request.url}")
        await state.broadcast_log(session_id, f"[PATH] 保存路径: {session_download_path}")
        
        if request.date_mode:
            await state.broadcast_log(session_id, f"[MODE] 日期范围下载模式: {request.start_date} 至 {request.end_date}")
        elif request.batch_mode:
            await state.broadcast_log(session_id, f"[MODE] 批量下载模式: 最近 {request.count} 篇")
        elif request.single_mode:
            await state.broadcast_log(session_id, f"[MODE] 单篇下载模式")
        
        # 解析用户提供的cookies字符串
        await state.broadcast_log(session_id, "[INFO] 正在解析登录凭证...")
        cookies_dict = {}
        try:
            # 解析cookies字符串: "name=value; name2=value2"
            cookie_pairs = cookies.split(';')
            for pair in cookie_pairs:
                if '=' in pair:
                    name, value = pair.strip().split('=', 1)
                    cookies_dict[name.strip()] = value.strip()
            
            await state.broadcast_log(session_id, f"[SUCCESS] 成功解析 {len(cookies_dict)} 个cookies")
            # Token 已在前面脱敏输出，这里不再重复
        except Exception as e:
            await fail_task(session_id, f"[ERROR] Cookies解析失败: {str(e)}")
            return
        
        if not cookies_dict or not token:
            await fail_task(session_id, "[ERROR] 登录凭证无效")
            return
        
        # 初始化引擎
        session.engine = CrawlerEngine(cookies_dict, token, output_dir=session_download_path)
        session.engine.pause_check_callback = make_pause_check(session)
        
        articles = []
        
        if request.batch_mode:
            # 批量下载
            fakeid = None
            
            if request.url.startswith('http://') or request.url.startswith('https://'):
                await state.broadcast_log(session_id, "[INFO] 检测到链接，正在从链接解析公众号信息...")
                # 在线程池中运行
                loop = asyncio.get_event_loop()
                fakeid = await loop.run_in_executor(None, state.engine.extract_fakeid_from_url, request.url)
                
                if not fakeid:
                    # Fallback: 尝试从cookies中获取（仅当格式像__biz）
                    await state.broadcast_log(session_id, "[WARN] 无法从链接中提取公众号信息，尝试从cookies中获取...")
                    cookie_fakeid = cookies_dict.get('data_bizuin') or cookies_dict.get('bizuin')
                    if cookie_fakeid:
                        import re
                        if re.match(r'^Mz[A-Za-z0-9+/=]{5,}$', cookie_fakeid):
                            fakeid = cookie_fakeid
                            await state.broadcast_log(session_id, f"[INFO] 成功从cookies中获取 FakeID: {fakeid}")
                        else:
                            await fail_task(session_id, "[ERROR] cookies中的bizuin不是有效的__biz格式，无法用于批量下载")
                            return
                    else:
                        await fail_task(session_id, "[ERROR] cookies中缺少可用的bizuin/data_bizuin字段")
                        return
            else:
                await state.broadcast_log(session_id, f"[INFO] 检测到公众号名称，正在搜索: {request.url}")
                # 在线程池中运行同步方法，避免阻塞事件循环
                loop = asyncio.get_event_loop()
                fakeid = await loop.run_in_executor(None, state.engine.search_account, request.url)
            
            if not fakeid:
                await fail_task(session_id, "[ERROR] 无法找到目标公众号")
                return
            
            await state.broadcast_log(session_id, f"[INFO] 识别到公众号 FakeID: {fakeid}")
            
            if request.date_mode:
                await state.broadcast_log(session_id, f"[INFO] 正在获取 {request.start_date} 至 {request.end_date} 期间的文章...")
                # 在线程池中运行
                loop = asyncio.get_event_loop()
                articles = await loop.run_in_executor(None, state.engine.get_articles_by_date, fakeid, request.start_date, request.end_date)
            else:
                await state.broadcast_log(session_id, f"[INFO] 正在获取最近 {request.count} 篇文章...")
                # 在线程池中运行
                loop = asyncio.get_event_loop()
                articles = await loop.run_in_executor(None, state.engine.get_articles, fakeid, request.count)
            
            if not articles:
                await fail_task(session_id, "[ERROR] 未获取到文章列表")
                return
            
            await state.broadcast_log(session_id, f"[INFO] 共获取到 {len(articles)} 篇文章")
        
        else:
            # 单篇下载
            await state.broadcast_log(session_id, "[INFO] 正在获取文章元数据...")
            # 在线程池中运行
            loop = asyncio.get_event_loop()
            article_info = await loop.run_in_executor(None, state.engine.fetch_article_metadata, request.url)
            
            if not article_info:
                await fail_task(session_id, "[ERROR] 无法解析文章信息，请检查链接是否正确")
                return
            
            await state.broadcast_log(session_id, f"[INFO] 识别到文章: {article_info['title']}")
            articles = [article_info]
        
        # 下载内容 - 在线程池中运行
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, state.engine.download_articles_content, articles)
        
        await state.broadcast_log(session_id, f"[SUCCESS] 任务完成！")
        if request.batch_mode:
            if request.date_mode:
                await state.broadcast_log(session_id, f"共下载 {len(articles)} 篇文章 ({request.start_date} 至 {request.end_date})")
            else:
                await state.broadcast_log(session_id, f"共下载 {len(articles)} 篇文章")
        else:
            await state.broadcast_log(session_id, f"文章《{articles[0]['title']}》下载完成！")
        
        # 打包成 ZIP
        await state.broadcast_log(session_id, f"[INFO] 正在打包文件...")
        zip_filename = create_zip_package(session_download_path, session_id)
        if zip_filename:
            session.last_zip_file = zip_filename
            await state.broadcast_log(session_id, f"[SUCCESS] ✅ 文件已打包完成！点击下方按钮下载到本地")
        else:
            await state.broadcast_log(session_id, f"[WARN] 打包失败，但文件已保存在服务器")
        
        # 下载成功完成，标记激活码为已使用
        if session.current_activation_key:
            key_generator.mark_as_used(session.current_activation_key)
            key_type_name = "批量下载" if session.current_key_type == "batch" else "单次下载"
            await state.broadcast_log(session_id, f"[INFO] 激活码 {session.current_activation_key} 已使用 (类型: {key_type_name})")
            await state.broadcast_log(session_id, f"[WARN] ⚠️  该激活码已失效，如需继续下载请使用新的激活码")
        
        # 广播完成状态，包含下载文件名
        for ws in session.active_websockets:
            try:
                await ws.send_json({
                    "type": "download_complete", 
                    "key_used": True,
                    "zip_file": os.path.basename(zip_filename) if zip_filename else None
                })
            except:
                pass
    
    except Exception as e:
        await fail_task(session_id, f"[ERROR] 发生未捕获异常: {e}")
        import traceback
        error_trace = traceback.format_exc()
        await state.broadcast_log(session_id, error_trace)
        
        # 下载失败，不标记激活码为已使用
        await state.broadcast_log(session_id, f"[INFO] 由于下载失败，激活码未被消耗，可以重新尝试")
    
    finally:
        # 清空当前激活码信息
        session.current_activation_key = None
        session.current_key_type = None
        session.is_downloading = False
        session.is_paused = False

def make_pause_check(session: SessionState):
    """生成会话级同步暂停检查函数"""
    def _check():
        if session.is_paused:
            import time
            while session.is_paused and session.is_downloading:
                time.sleep(0.5)
    return _check

def create_zip_package(download_path: str, session_id: str) -> Optional[str]:
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
        safe_session = normalize_session_id(session_id)
        zip_filename = f"wechat_articles_{safe_session}_{timestamp}.zip"
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
            # 静默删除，不输出日志
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

def clear_downloaded_files(download_path: Optional[str], zip_file: Optional[str]) -> Dict[str, str]:
    """清理已下载文件与打包zip"""
    result = {"deleted_path": "", "deleted_zip": ""}

    # 删除下载目录
    if download_path:
        try:
            download_dir = Path(download_path)
            base_dir = Path.cwd().resolve()
            resolved = download_dir.resolve()

            # 安全限制：必须在当前项目目录下
            if base_dir in resolved.parents or resolved == base_dir:
                if download_dir.exists():
                    shutil.rmtree(download_dir, ignore_errors=True)
                    result["deleted_path"] = str(download_dir)
        except Exception as e:
            print(f"[ERROR] 删除下载目录失败: {e}")

    # 删除zip
    if zip_file:
        try:
            zip_path = Path(zip_file)
            if not zip_path.is_absolute():
                zip_path = Path("temp_zips") / zip_file

            if zip_path.exists():
                zip_path.unlink()
                result["deleted_zip"] = zip_path.name
        except Exception as e:
            print(f"[ERROR] 删除ZIP失败: {e}")

    return result

@app.post("/api/pause")
async def pause_download(request: SessionRequest):
    """暂停下载"""
    session_id = normalize_session_id(request.session_id)
    session = state.get_session(session_id)

    if not session.is_downloading:
        return {"success": False, "message": "当前没有下载任务"}
    
    session.is_paused = True
    await state.broadcast_log(session_id, "\n[ACTION] 下载已暂停，点击'恢复'按钮继续\n")
    return {"success": True, "message": "已暂停"}

@app.post("/api/resume")
async def resume_download(request: SessionRequest):
    """恢复下载"""
    session_id = normalize_session_id(request.session_id)
    session = state.get_session(session_id)

    if not session.is_downloading:
        return {"success": False, "message": "当前没有下载任务"}
    
    if not session.is_paused:
        return {"success": False, "message": "当前未暂停"}
    
    await state.broadcast_log(session_id, "\n[ACTION] 正在恢复下载...")
    await state.broadcast_log(session_id, "[INFO] 继续下载中...")
    
    session.is_paused = False
    await state.broadcast_log(session_id, "[INFO] 已恢复下载\n")
    return {"success": True, "message": "已恢复"}

@app.post("/api/clear_downloads")
async def clear_downloads(request: SessionRequest):
    """暂停后清理已下载文件并重置状态"""
    session_id = normalize_session_id(request.session_id)
    session = state.get_session(session_id)

    if not session.is_downloading:
        return {"success": False, "message": "当前没有下载任务"}

    if not session.is_paused:
        return {"success": False, "message": "请先暂停下载"}

    # 尝试终止任务
    if session.download_task and not session.download_task.done():
        session.download_task.cancel()

    deleted = clear_downloaded_files(session.last_download_path, session.last_zip_file)

    # 重置状态
    session.is_downloading = False
    session.is_paused = False
    session.engine = None
    session.download_task = None
    session.last_download_path = None
    session.last_zip_file = None
    session.current_activation_key = None
    session.current_key_type = None
    session.last_input = None

    await state.broadcast_log(session_id, "[ACTION] 已清理已下载文件，任务已重置，可重新开始下载")
    return {"success": True, "message": "已清理并重置", "deleted": deleted}

@app.get("/api/status")
async def get_status(session_id: str = "default"):
    """获取当前状态"""
    session_id = normalize_session_id(session_id)
    session = state.get_session(session_id)
    return {
        "is_downloading": session.is_downloading,
        "is_paused": session.is_paused
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
    import sys
    
    # 设置控制台输出编码为 UTF-8，避免中文乱码
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    
    print("启动微信文章下载器 Web服务...")
    print("请在浏览器中访问: http://localhost:8000")
    
    # 启动时清理旧ZIP文件
    cleanup_old_zips()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
