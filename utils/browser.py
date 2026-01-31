"""
浏览器工厂模块
提供自动化浏览器驱动的初始化功能，支持Chrome和Edge浏览器
"""

import os  # 导入操作系统接口模块
import sys  # 导入系统相关的参数和函数
from selenium import webdriver  # 导入Selenium的WebDriver模块（用于浏览器自动化）
from selenium.webdriver.chrome.options import Options as ChromeOptions  # Chrome浏览器选项
from selenium.webdriver.chrome.service import Service as ChromeService  # Chrome驱动服务
from webdriver_manager.chrome import ChromeDriverManager  # Chrome驱动自动下载管理器
from selenium.webdriver.edge.options import Options as EdgeOptions  # Edge浏览器选项
from selenium.webdriver.edge.service import Service as EdgeService  # Edge驱动服务
from webdriver_manager.microsoft import EdgeChromiumDriverManager  # Edge驱动自动下载管理器
from config import Config  # 导入配置类
from requests.exceptions import ConnectionError, SSLError  # 导入网络异常类

class BrowserFactory:
    """
    浏览器工厂类
    提供静态方法来初始化不同类型的浏览器驱动
    """
    
    @staticmethod
    def init_driver():
        """
        初始化浏览器驱动（根据配置选择Chrome或Edge）
        
        Returns:
            WebDriver: 初始化好的浏览器驱动实例
        """
        # 设置环境变量：忽略SSL验证（针对某些代理环境）
        os.environ['WDM_SSL_VERIFY'] = '0'
        
        # 根据配置文件中的浏览器类型选择对应的初始化方法
        if Config.BROWSER_TYPE == "edge":
            return BrowserFactory.init_edge_driver()  # 初始化Edge浏览器
        else:
            return BrowserFactory.init_chrome_driver()  # 初始化Chrome浏览器

    @staticmethod
    def init_edge_driver():
        """
        初始化Edge浏览器驱动
        
        Returns:
            WebDriver: Edge浏览器驱动实例
        """
        print("[INFO] 正在初始化 Edge 浏览器...")
        
        # 创建Edge浏览器选项对象
        options = EdgeOptions()
        
        # 如果配置了无头模式（不显示浏览器窗口）
        if Config.HEADLESS:
            options.add_argument("--headless")  # 添加无头模式参数
            
        # 禁用GPU加速（提高某些环境下的稳定性）
        options.add_argument("--disable-gpu")
        
        # 设置User-Agent（模拟真实用户浏览器）
        options.add_argument(f"user-agent={Config.USER_AGENT}")
        
        # 移除"自动化测试"标志（避免被网站检测为机器人）
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # 禁用自动化扩展（进一步降低被检测的风险）
        options.add_experimental_option('useAutomationExtension', False)
        
        # 初始化驱动路径变量
        driver_path = None
        
        # 策略1: 优先使用配置文件中指定的本地驱动路径
        if Config.EDGEDRIVER_PATH and os.path.exists(Config.EDGEDRIVER_PATH):
            print(f"[INFO] 使用本地 EdgeDriver: {Config.EDGEDRIVER_PATH}")
            driver_path = Config.EDGEDRIVER_PATH  # 使用配置的本地路径
        else:
            # 策略2: 尝试自动下载驱动（如果本地路径未配置或不存在）
            try:
                print("[INFO] 正在尝试自动下载/更新 EdgeDriver...")
                # 使用webdriver_manager自动下载匹配的驱动
                driver_path = EdgeChromiumDriverManager().install()
            except Exception as e:
                # 如果自动下载失败，打印详细的错误提示和解决方案
                print("\n" + "="*60)
                print("[ERROR] 自动下载 EdgeDriver 失败！")
                print("错误详情:", e)
                print("-" * 60)
                print("【解决方案】:")
                print("1. 请查看你的 Edge 浏览器版本 (在浏览器地址栏输入 edge://settings/help)")
                print("2. 手动下载对应版本的 EdgeDriver:")
                print("   下载地址: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
                print("3. 下载解压后，将 msedgedriver.exe 的完整路径填写到 config.py 的 EDGEDRIVER_PATH 变量中")
                print("   例如: EDGEDRIVER_PATH = 'e:\\tools\\msedgedriver.exe'")
                print("="*60 + "\n")
                sys.exit(1)  # 退出程序

        # 尝试启动Edge浏览器
        try:
            # 创建Edge WebDriver实例
            driver = webdriver.Edge(service=EdgeService(driver_path), options=options)
            
            # 使用CDP (Chrome DevTools Protocol) 注入JavaScript脚本
            # 在页面加载前执行，将navigator.webdriver属性设为undefined
            # 这可以绕过大多数网站对Selenium的检测
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                })
                """
            })
            return driver  # 返回初始化好的驱动实例
        except Exception as e:
            # 如果驱动初始化失败，打印错误并退出
            print(f"[ERROR] Edge 驱动初始化失败: {e}")
            sys.exit(1)

    @staticmethod
    def init_chrome_driver():
        """
        初始化Chrome浏览器驱动
        配置反爬虫检测参数
        
        Returns:
            WebDriver: Chrome浏览器驱动实例
        """
        # 创建Chrome浏览器选项对象
        options = ChromeOptions()
        
        # 根据配置文件决定是否开启无头模式（不显示浏览器窗口）
        if Config.HEADLESS:
            options.add_argument("--headless")
        
        # 禁用GPU加速，某些环境下可提高稳定性
        options.add_argument("--disable-gpu")
        
        # 禁用沙盒模式，解决部分Linux环境下的权限问题
        options.add_argument("--no-sandbox")
        
        # 设置User-Agent请求头（模拟真实用户浏览器）
        options.add_argument(f"user-agent={Config.USER_AGENT}")
        
        # 规避检测：移除自动化测试标志 ('enable-automation')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # 禁止使用自动化扩展（进一步降低被检测风险）
        options.add_experimental_option('useAutomationExtension', False)
        
        # 初始化驱动路径变量
        driver_path = None
        
        # 策略1: 优先使用配置文件中指定的本地驱动路径
        if Config.CHROMEDRIVER_PATH and os.path.exists(Config.CHROMEDRIVER_PATH):
            print(f"[INFO] 使用本地 ChromeDriver: {Config.CHROMEDRIVER_PATH}")
            driver_path = Config.CHROMEDRIVER_PATH  # 使用配置的本地路径
        else:
            # 策略2: 尝试自动下载驱动（如果本地路径未配置或不存在）
            try:
                print("[INFO] 正在尝试自动下载/更新 ChromeDriver...")
                # 使用webdriver_manager自动下载匹配的驱动
                driver_path = ChromeDriverManager().install()
            except (ConnectionError, SSLError) as e:
                # 如果因为网络问题导致下载失败，打印详细的解决方案
                print("\n" + "="*60)
                print("[ERROR] 自动下载 ChromeDriver 失败！")
                print("原因: 无法连接到 Google 下载服务器 (可能是网络限制/GFW导致)")
                print("错误详情:", e)
                print("-" * 60)
                print("【解决方案】:")
                print("1. 请手动下载对应版本的 ChromeDriver:")
                print("   下载地址1 (国内镜像): https://npmmirror.com/mirrors/chromedriver/")
                print("   下载地址2 (官方): https://googlechromelabs.github.io/chrome-for-testing/")
                print("2. 下载解压后，将 chromedriver.exe 的完整路径填写到 config.py 的 CHROMEDRIVER_PATH 变量中")
                print("   例如: CHROMEDRIVER_PATH = 'e:\\tools\\chromedriver.exe'")
                print("="*60 + "\n")
                sys.exit(1)  # 退出程序
            except Exception as e:
                # 其他未知错误
                print(f"[ERROR] 初始化驱动发生未知错误: {e}")
                sys.exit(1)

        # 尝试启动Chrome浏览器
        try:
            # 创建Chrome WebDriver实例
            driver = webdriver.Chrome(service=ChromeService(driver_path), options=options)
        except Exception as e:
            # 如果启动失败，打印错误提示
            print(f"[ERROR] 启动浏览器失败: {e}")
            print("请检查安装的 Chrome 浏览器版本与 ChromeDriver 是否匹配。")
            sys.exit(1)
        
        # 使用CDP (Chrome DevTools Protocol) 协议动态修改JavaScript环境
        # 这里的脚本会在新文档加载前执行，将navigator.webdriver属性设为undefined
        # 这是绕过很多网站检测Selenium的关键步骤
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined
            })
            """
        })
        
        return driver  # 返回初始化好的驱动实例
