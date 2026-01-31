"""
图形用户界面（GUI）模块
使用tkinter构建的现代化桌面应用程序界面
支持单篇下载、批量下载和按日期范围下载三种模式
"""

import tkinter as tk  # 导入tkinter GUI库（基础模块）
from tkinter import scrolledtext, messagebox, ttk, filedialog  # 导入额外的tkinter组件
import sv_ttk  # 导入Sun Valley主题（现代化深色主题）
import sys  # 导入系统模块（用于输出重定向）
import threading  # 导入线程模块（用于后台执行下载任务）
import os  # 导入操作系统接口模块
from datetime import datetime  # 导入日期时间处理模块
from core.session import SessionManager  # 导入会话管理器
from core.engine import CrawlerEngine  # 导入爬虫引擎

class TextRedirector(object):
    """
    文本重定向器类
    将标准输出（print）重定向到GUI的文本框组件
    """
    
    def __init__(self, widget, tag="stdout"):
        """
        初始化重定向器
        
        Args:
            widget: 目标文本框组件（通常是ScrolledText）
            tag (str): 输出标签，可用于区分stdout和stderr
        """
        self.widget = widget  # 保存目标文本框组件
        self.tag = tag  # 保存标签

    def write(self, str):
        """
        写入方法
        当程序执行print()时，会调用此方法将文本输出到GUI
        
        Args:
            str: 要输出的文本内容
        """
        self.widget.config(state="normal")  # 设置文本框为可编辑状态
        self.widget.insert("end", str, (self.tag,))  # 在末尾插入文本
        self.widget.see("end")  # 滚动到末尾（自动显示最新内容）
        self.widget.config(state="disabled")  # 设置文本框为只读状态

    def flush(self):
        """
        刷新方法
        sys.stdout需要此方法，这里留空即可
        """
        pass

class AppGUI:
    """
    应用程序GUI主类
    负责构建界面、处理用户交互和调用后台下载逻辑
    """
    
    def __init__(self, root):
        """
        初始化GUI界面
        
        Args:
            root: tkinter的根窗口对象
        """
        self.root = root  # 保存根窗口引用
        self.root.title("微信文章下载器")  # 设置窗口标题
        self.root.geometry("900x650")  # 设置窗口大小（宽x高）
        
        # ==================== 下载控制标志 ====================
        self.is_paused = False  # 暂停标志
        self.is_downloading = False  # 下载中标志
        self.session_mgr = None  # SessionManager引用（用于恢复时验证）
        self.engine = None  # CrawlerEngine引用（用于传递暂停检查回调）
        
        # ==================== 主题设置 ====================
        # 应用Sun Valley主题（深色模式，Windows 11风格）
        sv_ttk.set_theme("dark")
        
        # ==================== 布局结构 ====================
        # 创建主容器（padding=20表示四周留白20像素）
        main_container = ttk.Frame(root, padding=20)
        main_container.pack(fill="both", expand=True)  # fill填充，expand自动扩展
        
        # ==================== 标题栏 ====================
        # 创建标题容器
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill="x", pady=(0, 20))  # 底部留白20像素
        
        # 主标题标签（大字体，粗体）
        title_label = ttk.Label(title_frame, text="微信文章下载器", 
                               font=('Microsoft YaHei UI', 18, 'bold'))
        title_label.pack(side="left")  # 左对齐
        
        # 副标题标签（英文名称）
        subtitle_label = ttk.Label(title_frame, text="WeChat Article Getter", 
                                   font=('Microsoft YaHei UI', 9))
        subtitle_label.pack(side="left", padx=(10, 0))  # 左侧留白10像素
        
        # ==================== 输入区域（横跨两列）====================
        # 创建输入区域容器（带边框和标题）
        input_labelframe = ttk.LabelFrame(main_container, text="公众号名称或文章链接", padding=15)
        input_labelframe.pack(fill="x", pady=(0, 15))  # 水平填充，底部留白
        
        # 创建URL输入框容器
        url_frame = ttk.Frame(input_labelframe)
        url_frame.pack(fill="x")
        
        # URL输入框（自动扩展填充）
        self.url_entry = ttk.Entry(url_frame, font=('Microsoft YaHei UI', 10))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # 开始下载按钮
        self.start_btn = ttk.Button(url_frame, text="开始下载", 
                                    command=self.start_download_thread, width=12)
        self.start_btn.pack(side="left")
        
        # 暂停/恢复按钮（初始禁用）
        self.pause_btn = ttk.Button(url_frame, text="⏸ 暂停", 
                                    command=self.toggle_pause, width=12)
        self.pause_btn.pack(side="left", padx=(10, 0))
        self.pause_btn.config(state="disabled")  # 初始禁用
        
        # 添加输入提示标签
        ttk.Label(input_labelframe, text="💡 提示：单篇下载请输入文章链接；批量下载可输入公众号名称或任意文章链接", 
                 font=('Microsoft YaHei UI', 9), foreground="gray").pack(anchor="w", pady=(8, 0))
        
        # ==================== 两列布局容器 ====================
        # 创建两列容器（左侧选项，右侧日志）
        columns_frame = ttk.Frame(main_container)
        columns_frame.pack(fill="both", expand=True)
        
        # 左列：可滚动的设置区域（固定宽度480px）
        left_frame = ttk.Frame(columns_frame, width=480)
        left_frame.pack(side="left", fill="y", padx=(0, 10))  # 右侧留白10px
        left_frame.pack_propagate(False)  # 防止子组件改变框架大小
        
        # 创建Canvas和Scrollbar实现滚动功能
        self.left_canvas = tk.Canvas(left_frame, width=480, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.left_canvas.yview)
        self.scrollable_left_frame = ttk.Frame(self.left_canvas)
        
        # 在Canvas中创建窗口来放置scrollable_left_frame
        self.left_canvas_window = self.left_canvas.create_window((0, 0), window=self.scrollable_left_frame, anchor="nw")
        
        # 配置Canvas的滚动命令
        self.left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        # 布局Canvas和Scrollbar
        self.left_canvas.pack(side="left", fill="both", expand=True)
        left_scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮事件（只在鼠标悬停在左侧区域时生效）
        def _on_mousewheel(event):
            self.left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # 递归绑定所有子组件的滚轮事件
        def _bind_to_mousewheel(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                _bind_to_mousewheel(child)
        
        # 递归解绑所有子组件的滚轮事件
        def _unbind_from_mousewheel(widget):
            widget.unbind("<MouseWheel>")
            for child in widget.winfo_children():
                _unbind_from_mousewheel(child)
        
        # 初始绑定Canvas和scrollable_left_frame
        _bind_to_mousewheel(self.left_canvas)
        _bind_to_mousewheel(self.scrollable_left_frame)
        
        # 绑定配置事件，更新滚动区域
        def _on_frame_configure(event):
            self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
            # 重新绑定新添加的子组件
            _bind_to_mousewheel(self.scrollable_left_frame)
        
        self.scrollable_left_frame.bind("<Configure>", _on_frame_configure)
        
        # left_column现在指向scrollable_left_frame，后续代码不需要改动
        left_column = self.scrollable_left_frame
        
        # 右列：日志显示区域（自动扩展）
        right_column = ttk.Frame(columns_frame)
        right_column.pack(side="left", fill="both", expand=True)
        
        # ==================== 下载选项区域（左列）====================
        # 创建下载选项容器
        option_labelframe = ttk.LabelFrame(left_column, text="下载选项", padding=15)
        option_labelframe.pack(fill="x", pady=(0, 15))
        
        # --- 单篇下载选项 ---
        # 创建布尔变量（绑定到复选框，用于获取勾选状态）
        self.single_var = tk.BooleanVar(value=True)  # 默认勾选单篇下载
        # 单篇下载复选框
        single_check = ttk.Checkbutton(option_labelframe, text="单篇下载", 
                                      variable=self.single_var, command=self.toggle_single_mode)
        single_check.pack(anchor="w", pady=(0, 10))  # 左对齐，底部留白
        
        # --- 批量下载选项 ---
        # 创建布尔变量（绑定到复选框，用于获取勾选状态）
        self.batch_var = tk.BooleanVar(value=False)
        # 批量下载复选框
        batch_check = ttk.Checkbutton(option_labelframe, text="批量下载该公众号文章", 
                                     variable=self.batch_var, command=self.toggle_batch_mode)
        batch_check.pack(anchor="w", pady=(0, 10))  # 左对齐，底部留白
        
        # 创建下载数量输入框容器
        count_frame = ttk.Frame(option_labelframe)
        count_frame.pack(fill="x")
        
        # 数量标签
        ttk.Label(count_frame, text="下载数量:").pack(side="left", padx=(0, 10))
        
        # 数量输入框（默认值为10）
        self.count_entry = ttk.Entry(count_frame, width=12, font=('Microsoft YaHei UI', 10))
        self.count_entry.insert(0, "10")  # 插入默认值
        self.count_entry.pack(side="left")
        self.count_entry.config(state="disabled")  # 初始状态禁用（因为默认是单篇下载模式）
        
        # 动态提示标签（显示"将下载最近的N篇文章"）
        self.count_hint_label = ttk.Label(count_frame, text="(将下载最近的10篇文章)", 
                                         font=('Microsoft YaHei UI', 9), foreground="gray")
        self.count_hint_label.pack(side="left", padx=(10, 0))
        
        # 绑定数量输入框的键盘释放事件（实时更新提示文本）
        self.count_entry.bind('<KeyRelease>', self.update_count_hint)
        
        # --- 日期范围选项 ---
        # 创建分隔线（视觉分隔不同选项组）
        date_separator = ttk.Separator(option_labelframe, orient='horizontal')
        date_separator.pack(fill='x', pady=15)
        
        # 创建布尔变量（绑定到日期模式复选框）
        self.date_mode_var = tk.BooleanVar(value=False)
        # 日期模式复选框
        date_check = ttk.Checkbutton(option_labelframe, text="按日期范围下载", 
                                    variable=self.date_mode_var, command=self.toggle_date_mode)
        date_check.pack(anchor="w", pady=(0, 10))
        
        # 创建日期输入框容器
        date_input_frame = ttk.Frame(option_labelframe)
        date_input_frame.pack(fill="x")
        
        # 开始日期标签
        ttk.Label(date_input_frame, text="开始日期:").pack(side="left", padx=(0, 8))
        
        # 开始日期输入框（默认禁用）
        self.start_date_entry = ttk.Entry(date_input_frame, width=12, 
                                         font=('Microsoft YaHei UI', 10))
        self.start_date_entry.insert(0, "2025-10-01")  # 插入默认日期
        self.start_date_entry.pack(side="left")
        self.start_date_entry.config(state="disabled")  # 初始状态为禁用
        
        # "至"标签
        ttk.Label(date_input_frame, text="至").pack(side="left", padx=10)
        
        # 结束日期标签
        ttk.Label(date_input_frame, text="结束日期:").pack(side="left", padx=(0, 8))
        
        # 结束日期输入框（默认禁用）
        self.end_date_entry = ttk.Entry(date_input_frame, width=12, 
                                        font=('Microsoft YaHei UI', 10))
        self.end_date_entry.insert(0, "2025-11-30")  # 插入默认日期
        self.end_date_entry.pack(side="left")
        self.end_date_entry.config(state="disabled")  # 初始状态为禁用
        
        # 日期格式提示（单独一行显示）
        ttk.Label(option_labelframe, text="格式: YYYY-MM-DD", 
                 font=('Microsoft YaHei UI', 9), foreground="gray").pack(anchor="w", pady=(8, 0))

        # ==================== 下载路径设置（左列）====================
        # 创建路径设置容器
        path_labelframe = ttk.LabelFrame(left_column, text="下载路径", padding=15)
        path_labelframe.pack(fill="x", pady=(0, 15))
        
        # 创建路径输入框容器
        path_frame = ttk.Frame(path_labelframe)
        path_frame.pack(fill="x")
        
        # 路径输入框
        self.path_entry = ttk.Entry(path_frame, font=('Microsoft YaHei UI', 10))
        # 默认路径为当前目录下的downloads文件夹
        default_path = os.path.join(os.path.dirname(__file__), "downloads")
        self.path_entry.insert(0, default_path)  # 插入默认路径
        self.path_entry.pack(fill="x", pady=(0, 8))
        
        # 浏览按钮（打开文件夹选择对话框）
        browse_btn = ttk.Button(path_frame, text="浏览...", command=self.browse_path, width=10)
        browse_btn.pack()
        
        # 路径说明文本
        ttk.Label(path_labelframe, text="文章将保存到此目录，\n如果不存在会自动创建", 
                 font=('Microsoft YaHei UI', 9), foreground="gray").pack(anchor="w", pady=(8, 0))

        # ==================== 日志显示区域（右列）====================
        # 创建日志容器
        log_labelframe = ttk.LabelFrame(right_column, text="运行日志", padding=10)
        log_labelframe.pack(expand=True, fill="both")  # 自动扩展填充
        
        # 创建滚动文本框（用于显示日志）
        self.log_text = scrolledtext.ScrolledText(log_labelframe, 
                                                 font=('Consolas', 9),  # 等宽字体
                                                 wrap='word',  # 按单词换行
                                                 state="disabled")  # 只读状态
        self.log_text.pack(expand=True, fill="both")
        
        # ==================== 状态栏 ====================
        # 创建状态栏容器
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill="x", pady=(10, 0))  # 顶部留白10px
        
        # 创建状态文本变量（用于动态更新状态显示）
        self.status_var = tk.StringVar()
        self.status_var.set("● 就绪")  # 设置初始状态
        # 状态标签
        status_bar = ttk.Label(status_frame, textvariable=self.status_var, 
                             font=('Microsoft YaHei UI', 9))
        status_bar.pack(anchor="w")  # 左对齐

        # ==================== 输出重定向 ====================
        # 将标准输出重定向到GUI的日志文本框
        sys.stdout = TextRedirector(self.log_text, "stdout")
        # 将标准错误重定向到GUI的日志文本框
        sys.stderr = TextRedirector(self.log_text, "stderr")
        
        # ==================== 打印欢迎信息 ====================
        # 打印装饰性分隔线
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  欢迎使用微信文章下载器 v2.0")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("📋 使用说明:")
        print("  1. 输入内容:")
        print("     • 单篇下载: 输入文章链接")
        print("     • 批量下载: 输入公众号名称或任意文章链接")
        print("  2. 选择下载模式:")
        print("     • 单篇下载: 不勾选批量选项")
        print("     • 批量下载: 勾选批量选项,输入数量")
        print("     • 日期范围: 勾选日期选项,输入起止日期")
        print("  3. 选择保存路径(可选)")
        print()
        print("✨ 准备就绪,等待您的指令...")
        print()
    def toggle_pause(self):
        """
        切换暂停/恢复状态
        """
        if self.is_paused:
            # 当前是暂停状态，现在要恢复
            print("\n[ACTION] 正在恢复下载...")
            print("[INFO] 验证会话有效性...")
            
            # 检查会话是否过期
            if self.session_mgr and not self.session_mgr.check_cookies_validity():
                print("[WARN] 会话已过期，需要重新登录")
                messagebox.showwarning("会话过期", "登录会话已过期，请重新扫码登录")
                
                # 重新登录
                try:
                    cookies, token = self.session_mgr.login()
                    if cookies and token:
                        print("[SUCCESS] 重新登录成功")
                        # 更新engine的cookies和token
                        if self.engine:
                            self.engine.cookies = cookies
                            self.engine.token = token
                            self.engine.headers['Cookie'] = '; '.join([f"{k}={v}" for k, v in cookies.items()])
                    else:
                        print("[ERROR] 重新登录失败")
                        messagebox.showerror("错误", "重新登录失败，请重试")
                        return
                except Exception as e:
                    print(f"[ERROR] 登录异常: {e}")
                    messagebox.showerror("错误", f"登录失败: {e}")
                    return
            else:
                print("[INFO] 会话有效，继续下载")
            
            self.is_paused = False
            self.pause_btn.config(text="⏸ 暂停")
            self.status_var.set("● 下载中...")
            print("[INFO] 已恢复下载\n")
        else:
            # 当前是运行状态，现在要暂停
            self.is_paused = True
            self.pause_btn.config(text="▶ 恢复")
            self.status_var.set("⏸ 已暂停")
            print("\n[ACTION] 下载已暂停，点击'恢复'按钮继续\n")
    
    def browse_path(self):
        """
        打开文件夹选择对话框
        让用户选择文章保存路径
        """
        # 获取当前输入框中的路径作为初始目录
        initial_dir = self.path_entry.get() or os.path.dirname(__file__)
        # 打开文件夹选择对话框
        folder_selected = filedialog.askdirectory(
            title="选择文章保存路径",
            initialdir=initial_dir
        )
        # 如果用户选择了文件夹（未取消）
        if folder_selected:
            # 清空输入框
            self.path_entry.delete(0, tk.END)
            # 插入选择的路径
            self.path_entry.insert(0, folder_selected)
            # 打印日志
            print(f"[INFO] 下载路径已设置为: {folder_selected}")

    def update_count_hint(self, event=None):
        """
        更新数量提示文本
        根据用户输入的数量动态更新提示信息
        
        Args:
            event: 键盘事件对象（由bind自动传递，这里不使用）
        """
        # 如果当前是日期模式，隐藏提示
        if self.date_mode_var.get():
            self.count_hint_label.config(text="")
        else:
            try:
                # 尝试将输入转换为整数
                count = int(self.count_entry.get().strip())
                if count > 0:
                    # 有效的正整数，显示提示
                    self.count_hint_label.config(text=f"(将下载最近的{count}篇文章)")
                else:
                    # 非正整数，显示错误提示
                    self.count_hint_label.config(text="(请输入正整数)")
            except:
                # 转换失败（非数字），显示错误提示
                self.count_hint_label.config(text="(请输入有效数字)")
    
    def toggle_single_mode(self):
        """
        切换单篇下载模式时的UI更新
        处理单篇下载复选框的状态变化，实现与批量下载的互斥
        """
        if self.single_var.get():
            # 勾选单篇下载时，自动取消批量下载
            self.batch_var.set(False)
            # 禁用数量输入
            self.count_entry.config(state="disabled")
            # 禁用日期模式
            self.date_mode_var.set(False)
            self.start_date_entry.config(state="disabled")
            self.end_date_entry.config(state="disabled")
        else:
            # 如果用户尝试取消单篇下载，自动勾选批量下载（保证至少有一个勾选）
            self.batch_var.set(True)
            self.count_entry.config(state="normal")
        # 更新提示文本
        self.update_count_hint()
    
    def toggle_batch_mode(self):
        """
        切换批量模式时的UI更新
        处理批量下载复选框的状态变化，实现与单篇下载的互斥
        """
        if self.batch_var.get():
            # 勾选批量下载时，自动取消单篇下载
            self.single_var.set(False)
            # 启用数量输入（如果不是日期模式）
            if not self.date_mode_var.get():
                self.count_entry.config(state="normal")
        else:
            # 如果用户尝试取消批量下载，自动勾选单篇下载（保证至少有一个勾选）
            self.single_var.set(True)
            self.count_entry.config(state="disabled")
            # 同时取消日期模式
            self.date_mode_var.set(False)
            self.start_date_entry.config(state="disabled")
            self.end_date_entry.config(state="disabled")
        # 更新提示文本
        self.update_count_hint()
    
    def toggle_date_mode(self):
        """
        切换日期模式时的UI更新
        处理日期范围复选框的状态变化
        """
        if self.date_mode_var.get():
            # 启用日期模式时
            self.start_date_entry.config(state="normal")  # 启用开始日期输入
            self.end_date_entry.config(state="normal")  # 启用结束日期输入
            # 自动勾选批量下载（日期模式必须是批量模式）
            self.batch_var.set(True)
            self.single_var.set(False)  # 取消单篇下载
            # 禁用数量输入（日期模式不需要指定数量）
            self.count_entry.config(state="disabled")
        else:
            # 禁用日期模式时
            self.start_date_entry.config(state="disabled")  # 禁用开始日期输入
            self.end_date_entry.config(state="disabled")  # 禁用结束日期输入
            # 启用数量输入
            self.count_entry.config(state="normal")
        # 更新提示文本
        self.update_count_hint()

    def start_download_thread(self):
        """
        启动下载线程
        验证用户输入，获取参数，创建后台线程执行下载任务
        """
        # ==================== 输入验证 ====================
        # 获取并验证URL
        url = self.url_entry.get().strip()  # 去除首尾空格
        if not url:
            # URL为空，显示警告对话框
            messagebox.showwarning("提示", "请输入有效的文章链接")
            return  # 终止执行
        
        # 获取并验证下载路径
        download_path = self.path_entry.get().strip()
        if not download_path:
            # 路径为空，显示警告对话框
            messagebox.showwarning("提示", "请设置下载路径")
            return
        
        # 如果路径不存在，尝试创建
        try:
            if not os.path.exists(download_path):
                os.makedirs(download_path)  # 递归创建目录
                print(f"[INFO] 已创建下载目录: {download_path}")
        except Exception as e:
            # 创建目录失败，显示错误对话框
            messagebox.showerror("错误", f"无法创建下载目录:\n{str(e)}")
            return
        
        # ==================== 获取下载参数 ====================
        # 获取下载模式的勾选状态
        single_mode = self.single_var.get()  # True表示单篇下载
        batch_mode = self.batch_var.get()  # True表示批量下载
        date_mode = self.date_mode_var.get()  # True表示按日期范围下载
        count = 10  # 默认下载数量
        start_date = None  # 开始日期
        end_date = None  # 结束日期
        
        # 如果是按数量的批量模式
        if batch_mode and not date_mode:
            try:
                # 尝试获取并验证数量
                count = int(self.count_entry.get().strip())
                if count <= 0:
                    raise ValueError  # 数量必须是正整数
            except:
                # 数量无效，显示警告
                messagebox.showwarning("提示", "请输入有效的文章数量（正整数）")
                return
        
        # 如果是按日期范围模式
        if date_mode:
            # 按日期模式
            try:
                start_date = self.start_date_entry.get().strip()
                end_date = self.end_date_entry.get().strip()
                
                # 验证日期格式
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
                
                # 验证日期范围
                if start_date > end_date:
                    messagebox.showwarning("提示", "开始日期不能晚于结束日期")
                    return
            except Exception as e:
                messagebox.showwarning("提示", f"日期格式错误，请使用 YYYY-MM-DD 格式\n例如: 2025-10-01")
                return
            
        # 重置暂停状态
        self.is_paused = False
        self.is_downloading = True
        
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")  # 启用暂停按钮
        self.pause_btn.config(text="⏸ 暂停")  # 重置按钮文本
        self.status_var.set("● 下载中...")
        
        # 开启线程运行（传递single_mode参数）
        thread = threading.Thread(target=self.run_download, 
                                 args=(url, single_mode, batch_mode, date_mode, count, start_date, end_date, download_path))
        thread.daemon = True
        thread.start()

    def run_download(self, url, single_mode, batch_mode, date_mode, count, start_date, end_date, download_path):
        try:
            print(f"\n[TASK] 开始处理链接: {url}")
            print(f"[PATH] 保存路径: {download_path}")
            if date_mode:
                print(f"[MODE] 日期范围下载模式: {start_date} 至 {end_date}")
            elif batch_mode:
                print(f"[MODE] 批量下载模式: 最近 {count} 篇")
            elif single_mode:
                print(f"[MODE] 单篇下载模式")
            
            # 1. 登录/Session
            self.session_mgr = SessionManager()
            cookies, token = self.session_mgr.login()
            
            if not cookies or not token:
                print("[FATAL] 登录失败，请检查网络或重新扫码")
                return
            
            # 2. 初始化引擎，传递自定义输出目录
            self.engine = CrawlerEngine(cookies, token, output_dir=download_path)
            # 设置暂停检查回调
            self.engine.pause_check_callback = self.check_pause
            
            articles = []
            
            if batch_mode:
                # 批量下载模式：支持输入公众号名称或文章链接
                fakeid = None
                
                # 判断输入是否为URL（包含http或https）
                if url.startswith('http://') or url.startswith('https://'):
                    # 输入的是链接，尝试从链接中提取公众号信息
                    print("[INFO] 检测到链接，正在从链接解析公众号信息...")
                    fakeid = self.engine.extract_fakeid_from_url(url)
                    
                    if not fakeid:
                        print("[WARN] 无法从链接中提取公众号信息，尝试作为公众号名称搜索...")
                        # 如果链接解析失败，提示用户可以直接输入公众号名称
                        messagebox.showinfo("提示", 
                                          "无法从该链接提取公众号信息\n\n"
                                          "建议操作：\n"
                                          "1. 请输入有效的微信文章链接（包含__biz参数）\n"
                                          "2. 或直接输入公众号名称进行搜索")
                        return
                else:
                    # 输入的是公众号名称，直接搜索
                    print(f"[INFO] 检测到公众号名称，正在搜索: {url}")
                    fakeid = self.engine.search_account(url)
                
                # 检查是否成功获取到fakeid
                if not fakeid:
                    print("[ERROR] 无法找到目标公众号")
                    messagebox.showerror("错误", 
                                       "无法找到目标公众号\n\n"
                                       "请检查：\n"
                                       "1. 公众号名称是否正确\n"
                                       "2. 文章链接是否有效")
                    return
                
                print(f"[INFO] 识别到公众号 FakeID: {fakeid}")
                
                if date_mode:
                    # 按日期范围获取
                    print(f"[INFO] 正在获取 {start_date} 至 {end_date} 期间的文章...")
                    articles = self.engine.get_articles_by_date(fakeid, start_date, end_date)
                else:
                    # 按数量获取
                    print(f"[INFO] 正在获取最近 {count} 篇文章...")
                    articles = self.engine.get_articles(fakeid, count)
                
                if not articles:
                    print("[ERROR] 未获取到文章列表")
                    return
                    
                print(f"[INFO] 共获取到 {len(articles)} 篇文章")
                
            else:
                # 单篇下载模式
                print("[INFO] 正在获取文章元数据...")
                article_info = self.engine.fetch_article_metadata(url)
                
                if not article_info:
                    print("[ERROR] 无法解析文章信息，请检查链接是否正确")
                    return
                    
                print(f"[INFO] 识别到文章: {article_info['title']}")
                articles = [article_info]
            
            # 4. 下载内容
            self.engine.download_articles_content(articles)
            
            print(f"[SUCCESS] 任务完成！")
            if batch_mode:
                if date_mode:
                    messagebox.showinfo("完成", f"日期范围下载完成！\n共下载 {len(articles)} 篇文章\n({start_date} 至 {end_date})")
                else:
                    messagebox.showinfo("完成", f"批量下载完成！共下载 {len(articles)} 篇文章")
            else:
                messagebox.showinfo("完成", f"文章《{articles[0]['title']}》下载完成！")

        except Exception as e:
            print(f"[ERROR] 发生未捕获异常: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"发生错误: {e}")
        finally:
            self.root.after(0, lambda: self.reset_ui())

    def check_pause(self):
        """
        检查是否需要暂停
        在下载循环中被调用
        
        Returns:
            bool: True表示需要暂停，False表示继续
        """
        if self.is_paused:
            # 暂停时等待恢复
            while self.is_paused and self.is_downloading:
                import time
                time.sleep(0.5)  # 每0.5秒检查一次
        return not self.is_downloading  # 如果停止下载则返回True
    
    def reset_ui(self):
        """重置UI状态"""
        self.is_downloading = False
        self.is_paused = False
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self.pause_btn.config(text="⏸ 暂停")
        self.status_var.set("● 就绪")

if __name__ == "__main__":
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()
