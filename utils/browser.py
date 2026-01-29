from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from config import Config

class BrowserFactory:
    @staticmethod
    def init_driver():
        """初始化 Chrome 浏览器驱动，配置反爬参数"""
        options = Options()
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
        
        # 自动下载并安装匹配版本的 ChromeDriver，然后启动浏览器
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
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
