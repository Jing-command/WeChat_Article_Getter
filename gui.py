import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
import sv_ttk
import sys
import threading
import queue
import time
import os
from datetime import datetime
from core.session import SessionManager
from core.engine import CrawlerEngine
from config import Config

class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str):
        self.widget.config(state="normal")
        self.widget.insert("end", str, (self.tag,))
        self.widget.see("end")
        self.widget.config(state="disabled")

    def flush(self):
        pass

class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str):
        self.widget.config(state="normal")
        self.widget.insert("end", str, (self.tag,))
        self.widget.see("end")
        self.widget.config(state="disabled")

    def flush(self):
        pass

class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("微信文章下载器")
        self.root.geometry("900x650")
        
        # 应用Sun Valley主题（深色模式）
        sv_ttk.set_theme("dark")
        
        # 创建主容器
        main_container = ttk.Frame(root, padding=20)
        main_container.pack(fill="both", expand=True)
        
        # 标题栏
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill="x", pady=(0, 20))
        
        title_label = ttk.Label(title_frame, text="微信文章下载器", 
                               font=('Microsoft YaHei UI', 18, 'bold'))
        title_label.pack(side="left")
        
        subtitle_label = ttk.Label(title_frame, text="WeChat Article Getter", 
                                   font=('Microsoft YaHei UI', 9))
        subtitle_label.pack(side="left", padx=(10, 0))
        
        # 1. 输入区域
        input_labelframe = ttk.LabelFrame(main_container, text="文章链接", padding=15)
        input_labelframe.pack(fill="x", pady=(0, 15))
        
        url_frame = ttk.Frame(input_labelframe)
        url_frame.pack(fill="x")
        
        self.url_entry = ttk.Entry(url_frame, font=('Microsoft YaHei UI', 10))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.start_btn = ttk.Button(url_frame, text="开始下载", 
                                    command=self.start_download_thread, width=12)
        self.start_btn.pack(side="left")
        
        # 2. 批量下载选项
        option_labelframe = ttk.LabelFrame(main_container, text="下载选项", padding=15)
        option_labelframe.pack(fill="x", pady=(0, 15))
        
        self.batch_var = tk.BooleanVar(value=False)
        batch_check = ttk.Checkbutton(option_labelframe, text="批量下载该公众号文章", 
                                     variable=self.batch_var, command=self.toggle_batch_mode)
        batch_check.pack(anchor="w", pady=(0, 10))
        
        count_frame = ttk.Frame(option_labelframe)
        count_frame.pack(fill="x")
        
        ttk.Label(count_frame, text="下载数量:").pack(side="left", padx=(0, 10))
        
        self.count_entry = ttk.Entry(count_frame, width=12, font=('Microsoft YaHei UI', 10))
        self.count_entry.insert(0, "10")
        self.count_entry.pack(side="left")
        
        # 动态提示标签
        self.count_hint_label = ttk.Label(count_frame, text="(将下载最近的10篇文章)", 
                                         font=('Microsoft YaHei UI', 9), foreground="gray")
        self.count_hint_label.pack(side="left", padx=(10, 0))
        
        # 绑定数量输入框的变化事件
        self.count_entry.bind('<KeyRelease>', self.update_count_hint)
        
        # 3. 日期范围选项
        date_separator = ttk.Separator(option_labelframe, orient='horizontal')
        date_separator.pack(fill='x', pady=15)
        
        self.date_mode_var = tk.BooleanVar(value=False)
        date_check = ttk.Checkbutton(option_labelframe, text="按日期范围下载", 
                                    variable=self.date_mode_var, command=self.toggle_date_mode)
        date_check.pack(anchor="w", pady=(0, 10))
        
        date_input_frame = ttk.Frame(option_labelframe)
        date_input_frame.pack(fill="x")
        
        ttk.Label(date_input_frame, text="开始日期:").pack(side="left", padx=(0, 8))
        
        self.start_date_entry = ttk.Entry(date_input_frame, width=12, 
                                         font=('Microsoft YaHei UI', 10))
        self.start_date_entry.insert(0, "2025-10-01")
        self.start_date_entry.pack(side="left")
        self.start_date_entry.config(state="disabled")
        
        ttk.Label(date_input_frame, text="至").pack(side="left", padx=10)
        
        ttk.Label(date_input_frame, text="结束日期:").pack(side="left", padx=(0, 8))
        
        self.end_date_entry = ttk.Entry(date_input_frame, width=12, 
                                        font=('Microsoft YaHei UI', 10))
        self.end_date_entry.insert(0, "2025-11-30")
        self.end_date_entry.pack(side="left")
        self.end_date_entry.config(state="disabled")
        
        ttk.Label(date_input_frame, text="格式: YYYY-MM-DD", 
                 font=('Microsoft YaHei UI', 9), foreground="gray").pack(side="left", padx=(15, 0))

        # 4. 下载路径设置
        path_labelframe = ttk.LabelFrame(main_container, text="下载路径", padding=15)
        path_labelframe.pack(fill="x", pady=(0, 15))
        
        path_frame = ttk.Frame(path_labelframe)
        path_frame.pack(fill="x")
        
        self.path_entry = ttk.Entry(path_frame, font=('Microsoft YaHei UI', 10))
        # 默认路径为当前目录下的downloads文件夹
        default_path = os.path.join(os.path.dirname(__file__), "downloads")
        self.path_entry.insert(0, default_path)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        browse_btn = ttk.Button(path_frame, text="浏览...", command=self.browse_path, width=10)
        browse_btn.pack(side="left")
        
        ttk.Label(path_labelframe, text="文章将保存到此目录，如果不存在会自动创建", 
                 font=('Microsoft YaHei UI', 9), foreground="gray").pack(anchor="w", pady=(8, 0))

        # 5. 日志显示区域
        log_labelframe = ttk.LabelFrame(main_container, text="运行日志", padding=10)
        log_labelframe.pack(expand=True, fill="both")
        
        self.log_text = scrolledtext.ScrolledText(log_labelframe, 
                                                 font=('Consolas', 9),
                                                 wrap='word', state="disabled")
        self.log_text.pack(expand=True, fill="both")
        
        # 6. 状态栏
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill="x", pady=(10, 0))
        
        self.status_var = tk.StringVar()
        self.status_var.set("● 就绪")
        status_bar = ttk.Label(status_frame, textvariable=self.status_var, 
                             font=('Microsoft YaHei UI', 9))
        status_bar.pack(anchor="w")

        # 重定向输出
        sys.stdout = TextRedirector(self.log_text, "stdout")
        sys.stderr = TextRedirector(self.log_text, "stderr")
        
        # 打印欢迎信息
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  欢迎使用微信文章下载器 v2.0")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("📋 使用说明:")
        print("  1. 输入任意微信文章链接")
        print("  2. 选择下载模式:")
        print("     • 单篇下载:不勾选批量选项")
        print("     • 批量下载:勾选批量选项,输入数量")
        print("     • 日期范围:勾选日期选项,输入起止日期")
        print("  3. 选择保存路径(可选)")
        print()
        print("✨ 准备就绪,等待您的指令...")
        print()

    def browse_path(self):
        """浏览选择下载路径"""
        initial_dir = self.path_entry.get() or os.path.dirname(__file__)
        folder_selected = filedialog.askdirectory(
            title="选择文章保存路径",
            initialdir=initial_dir
        )
        if folder_selected:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder_selected)
            print(f"[INFO] 下载路径已设置为: {folder_selected}")

    def update_count_hint(self, event=None):
        """更新数量提示文本"""
        if self.date_mode_var.get():
            # 日期模式下隐藏提示
            self.count_hint_label.config(text="")
        else:
            try:
                count = int(self.count_entry.get().strip())
                if count > 0:
                    self.count_hint_label.config(text=f"(将下载最近的{count}篇文章)")
                else:
                    self.count_hint_label.config(text="(请输入正整数)")
            except:
                self.count_hint_label.config(text="(请输入有效数字)")
    
    def toggle_batch_mode(self):
        """切换批量模式时的UI更新"""
        if self.batch_var.get() and self.date_mode_var.get():
            # 如果启用批量且启用日期，禁用数量输入
            self.count_entry.config(state="disabled")
        else:
            self.count_entry.config(state="normal")
        self.update_count_hint()
    
    def toggle_date_mode(self):
        """切换日期模式时的UI更新"""
        if self.date_mode_var.get():
            self.start_date_entry.config(state="normal")
            self.end_date_entry.config(state="normal")
            # 启用日期模式时自动勾选批量下载
            self.batch_var.set(True)
            self.count_entry.config(state="disabled")
        else:
            self.start_date_entry.config(state="disabled")
            self.end_date_entry.config(state="disabled")
            self.count_entry.config(state="normal")
        self.update_count_hint()

    def start_download_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入有效的文章链接")
            return
        
        # 获取并验证下载路径
        download_path = self.path_entry.get().strip()
        if not download_path:
            messagebox.showwarning("提示", "请设置下载路径")
            return
        
        # 如果路径不存在，创建它
        try:
            if not os.path.exists(download_path):
                os.makedirs(download_path)
                print(f"[INFO] 已创建下载目录: {download_path}")
        except Exception as e:
            messagebox.showerror("错误", f"无法创建下载目录:\n{str(e)}")
            return
        
        batch_mode = self.batch_var.get()
        date_mode = self.date_mode_var.get()
        count = 10
        start_date = None
        end_date = None
        
        if batch_mode and not date_mode:
            # 按数量模式
            try:
                count = int(self.count_entry.get().strip())
                if count <= 0:
                    raise ValueError
            except:
                messagebox.showwarning("提示", "请输入有效的文章数量（正整数）")
                return
        
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
            
        self.start_btn.config(state="disabled")
        self.status_var.set("正在运行...")
        
        # 开启线程运行
        thread = threading.Thread(target=self.run_download, args=(url, batch_mode, date_mode, count, start_date, end_date, download_path))
        thread.daemon = True
        thread.start()

    def run_download(self, url, batch_mode, date_mode, count, start_date, end_date, download_path):
        try:
            print(f"\n[TASK] 开始处理链接: {url}")
            print(f"[PATH] 保存路径: {download_path}")
            if date_mode:
                print(f"[MODE] 日期范围下载模式: {start_date} 至 {end_date}")
            elif batch_mode:
                print(f"[MODE] 批量下载模式: 最近 {count} 篇")
            else:
                print(f"[MODE] 单篇下载模式")
            
            # 1. 登录/Session
            session_mgr = SessionManager()
            cookies, token = session_mgr.login()
            
            if not cookies or not token:
                print("[FATAL] 登录失败，请检查网络或重新扫码")
                return
            
            # 2. 初始化引擎，传递自定义输出目录
            engine = CrawlerEngine(cookies, token, output_dir=download_path)
            
            articles = []
            
            if batch_mode:
                # 批量下载模式：从URL提取公众号信息，然后获取文章列表
                print("[INFO] 正在从链接解析公众号信息...")
                fakeid = engine.extract_fakeid_from_url(url)
                
                if not fakeid:
                    print("[ERROR] 无法从链接解析公众号信息")
                    return
                
                print(f"[INFO] 识别到公众号 FakeID: {fakeid}")
                
                if date_mode:
                    # 按日期范围获取
                    print(f"[INFO] 正在获取 {start_date} 至 {end_date} 期间的文章...")
                    articles = engine.get_articles_by_date(fakeid, start_date, end_date)
                else:
                    # 按数量获取
                    print(f"[INFO] 正在获取最近 {count} 篇文章...")
                    articles = engine.get_articles(fakeid, count)
                
                if not articles:
                    print("[ERROR] 未获取到文章列表")
                    return
                    
                print(f"[INFO] 共获取到 {len(articles)} 篇文章")
                
            else:
                # 单篇下载模式
                print("[INFO] 正在获取文章元数据...")
                article_info = engine.fetch_article_metadata(url)
                
                if not article_info:
                    print("[ERROR] 无法解析文章信息，请检查链接是否正确")
                    return
                    
                print(f"[INFO] 识别到文章: {article_info['title']}")
                articles = [article_info]
            
            # 4. 下载内容
            engine.download_articles_content(articles)
            
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

    def reset_ui(self):
        self.start_btn.config(state="normal")
        self.status_var.set("就绪")

if __name__ == "__main__":
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()
