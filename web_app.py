"""
FastAPI Web应用 - 微信文章下载器
提供Web界面实现GUI的所有功能
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import json
import os
import sys
import io
from datetime import datetime
from typing import Optional
import base64
from contextlib import redirect_stdout, redirect_stderr

from core.engine import CrawlerEngine
from activation_key_generator import ActivationKeyGenerator

# 初始化FastAPI应用
app = FastAPI(title="微信文章下载器")

# 初始化激活码生成器
key_generator = ActivationKeyGenerator()

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
    
    def add_websocket(self, websocket):
        self.active_websockets.append(websocket)
    
    def remove_websocket(self, websocket):
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)
    
    async def broadcast_log(self, message: str):
        """广播日志到所有连接的WebSocket"""
        for ws in self.active_websockets:
            try:
                await ws.send_json({"type": "log", "message": message})
            except:
                pass

state = AppState()

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
            "message": "  欢迎使用微信文章下载器 Web版 v2.0"
        })
        await websocket.send_json({
            "type": "log",
            "message": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        })
        await websocket.send_json({
            "type": "log",
            "message": "✨ 准备就绪，等待您的指令..."
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

@app.post("/api/download")
async def start_download(request: DownloadRequest):
    """开始下载"""
    if state.is_downloading:
        return {"success": False, "message": "已有下载任务在进行中"}
    
    # 验证激活码
    activation_key = request.activation_key.strip()
    
    # 判断下载模式并验证对应类型的激活码
    if request.batch_mode or request.date_mode:
        # 批量下载（包括日期范围下载），需要批量激活码
        if not key_generator.verify_key(activation_key, "batch"):
            await state.broadcast_log("[ERROR] 批量下载（包括日期范围下载）需要有效的批量下载激活码 (B- 开头)")
            return {"success": False, "message": "激活码无效或已被使用，批量下载（包括日期范围下载）需要使用 B- 开头的激活码"}
        key_type = "batch"
    else:
        # 单次下载，需要单次激活码
        if not key_generator.verify_key(activation_key, "single"):
            await state.broadcast_log("[ERROR] 单次下载需要有效的单次下载激活码 (S- 开头)")
            return {"success": False, "message": "激活码无效或已被使用，单次下载需要使用 S- 开头的激活码"}
        key_type = "single"
    
    # 保存当前激活码信息，等下载成功后再标记为已使用
    state.current_activation_key = activation_key
    state.current_key_type = key_type
    await state.broadcast_log(f"[SUCCESS] 激活码验证通过 (类型: {'批量下载' if key_type == 'batch' else '单次下载'})")
    
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
            await state.broadcast_log(f"[INFO] Token: {request.token}")
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
        
        # 下载成功完成，标记激活码为已使用
        if state.current_activation_key:
            key_generator.mark_as_used(state.current_activation_key)
            key_type_name = "批量下载" if state.current_key_type == "batch" else "单次下载"
            await state.broadcast_log(f"[INFO] 激活码 {state.current_activation_key} 已使用 (类型: {key_type_name})")
            await state.broadcast_log(f"[WARN] ⚠️  该激活码已失效，如需继续下载请使用新的激活码")
        
        # 广播完成状态
        for ws in state.active_websockets:
            try:
                await ws.send_json({"type": "download_complete", "key_used": True})
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
    return not state.is_downloading

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

if __name__ == "__main__":
    import uvicorn
    print("🚀 启动微信文章下载器 Web服务...")
    print("📱 请在浏览器中访问: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
