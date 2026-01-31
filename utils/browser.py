import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from config import Config
from requests.exceptions import ConnectionError, SSLError

class BrowserFactory:
    @staticmethod
    def init_driver():
        """初始化浏览器驱动 (支持 Chrome 和 Edge)"""
        # 尝试忽略 SSL 验证（针对某些代理环境）
        os.environ['WDM_SSL_VERIFY'] = '0'
        
        if Config.BROWSER_TYPE == "edge":
            return BrowserFactory.init_edge_driver()
        else:
            return BrowserFactory.init_chrome_driver()

    @staticmethod
    def init_edge_driver():
        print("[INFO] 正在初始化 Edge 浏览器...")
        options = EdgeOptions()
        if Config.HEADLESS:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument(f"user-agent={Config.USER_AGENT}")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver_path = None
        
        # 1. 优先使用配置文件中指定的本地驱动路径
        if Config.EDGEDRIVER_PATH and os.path.exists(Config.EDGEDRIVER_PATH):
            print(f"[INFO] 使用本地 EdgeDriver: {Config.EDGEDRIVER_PATH}")
            driver_path = Config.EDGEDRIVER_PATH
        else:
            # 2. 尝试自动下载驱动
            try:
                print("[INFO] 正在尝试自动下载/更新 EdgeDriver...")
                driver_path = EdgeChromiumDriverManager().install()
            except Exception as e:
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
                sys.exit(1)

        try:
            driver = webdriver.Edge(service=EdgeService(driver_path), options=options)
            
            # CDP 设置反爬
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                })
                """
            })
            return driver
        except Exception as e:
             print(f"[ERROR] Edge 驱动初始化失败: {e}")
             sys.exit(1)

    @staticmethod
    def init_chrome_driver():
        """初始化 Chrome 浏览器驱动，配置反爬参数"""
        options = ChromeOptions()
        # 根据配置文件决定是否开启无头模式
        if Config.HEADLESS:
            options.add_argument("--headless")
        
        # 禁用 GPU 加速，某些环境下可提高稳定性
        options.add_argument("--disable-gpu")
        # 禁用沙盒模式，解决部分 Linux 环境下的权限问题
        options.add_argument("--no-sandbox")
        # 设置 User-Agent 请求头
        options.add_argument(f"user-agent={Config.USER_AGENT}")
        
        # 规避检测：移除自动化测试标志 ('enable-automation')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # 禁止使用自动化扩展
        options.add_experimental_option('useAutomationExtension', False)
        
        driver_path = None
        
        # 1. 优先使用配置文件中指定的本地驱动路径
        if Config.CHROMEDRIVER_PATH and os.path.exists(Config.CHROMEDRIVER_PATH):
            print(f"[INFO] 使用本地 ChromeDriver: {Config.CHROMEDRIVER_PATH}")
            driver_path = Config.CHROMEDRIVER_PATH
        else:
            # 2. 尝试自动下载驱动
            try:
                print("[INFO] 正在尝试自动下载/更新 ChromeDriver...")
                driver_path = ChromeDriverManager().install()
            except (ConnectionError, SSLError) as e:
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
                sys.exit(1)
            except Exception as e:
                print(f"[ERROR] 初始化驱动发生未知错误: {e}")
                sys.exit(1)

        # 启动浏览器
        try:
            driver = webdriver.Chrome(service=ChromeService(driver_path), options=options)
        except Exception as e:
             print(f"[ERROR] 启动浏览器失败: {e}")
             print("请检查安装的 Chrome 浏览器版本与 ChromeDriver 是否匹配。")
             sys.exit(1)
        
        # 使用 CDP (Chrome DevTools Protocol) 协议动态修改 JS 环境
        # 这里的脚本会在新文档加载前执行，将 navigator.webdriver 属性设为 undefined
        # 这是绕过很多网站检测 Selenium 的关键步骤
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined
            })
            """
        })
        
        return driver
