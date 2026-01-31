import json
import time
import os
import re
import requests
from config import Config
from utils.browser import BrowserFactory

class SessionManager:
    def __init__(self):
        # 初始化存储 Cookies 的字典
        self.cookies = {}
        # 初始化 Token（微信后台的关键凭证）
        self.token = None
        # 初始化 Selenium 驱动对象
        self.driver = None

    def load_cookies(self):
        """尝试从本地文件加载 Cookies 和 Token"""
        # 检查 Cookies 文件是否存在
        if os.path.exists(Config.COOKIES_FILE):
            try:
                # 以读取模式打开 JSON 文件
                with open(Config.COOKIES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 读取 cookies 字段，默认为空字典
                    self.cookies = data.get('cookies', {})
                    # 读取 token 字段
                    self.token = data.get('token')
                    print(f"[INFO] 本地Cookies加载成功, Token: {self.token}")
                    return True
            except Exception as e:
                # 如果文件损坏或格式错误，打印错误信息
                print(f"[ERROR] Cookies加载失败: {e}")
        return False

    def save_cookies(self):
        """将当前的 Cookies 和 Token 保存到本地文件"""
        data = {
            'cookies': self.cookies,
            'token': self.token
        }
        # 以写入模式打开文件，保存 JSON 数据
        with open(Config.COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        print("[INFO]会话已保存到本地")

    def check_cookies_validity(self):
        """验证当前 Cookies 和 Token 是否有效"""
        if not self.cookies or not self.token:
            return False
        
        # 构造一个轻量级的请求来测试连通性
        headers = {
            "User-Agent": Config.USER_AGENT,
            "Referer": Config.BASE_URL
        }
        params = {
            "action": "search_biz",
            "token": self.token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": "1",
            "query": "official_account", # 随便搜个常用词
            "begin": "0",
            "count": "1"
        }
        
        try:
            resp = requests.get(Config.SEARCH_URL, cookies=self.cookies, headers=headers, params=params)
            data = resp.json()
            if data.get("base_resp", {}).get("ret") == 0:
                return True
            else:
                print(f"[WARN] 验证会话失效: {data.get('base_resp')}")
                return False
        except Exception as e:
            print(f"[WARN] 验证会话出错: {e}")
            return False

    def login(self):
        """执行登录流程（优先复用本地会话，失败则扫码）"""
        # 1. 尝试使用本地 Cookie 和 Token
        if self.load_cookies():
            # 验证 Cookies 是否有效
            print("[INFO] 正在验证本地会话有效性...")
            if self.check_cookies_validity():
                print("[INFO] 会话有效，直接复用")
                return self.cookies, self.token
            else:
                print("[INFO] 会话已过期，需要重新登录")
        
        # 2. 本地无有效会话，启动浏览器进行扫码登录
        print("[INFO] 启动浏览器进行扫码登录...")
        # 调用工厂方法初始化防检测浏览器
        self.driver = BrowserFactory.init_driver()
        # 打开微信公众平台登录页
        self.driver.get(Config.LOGIN_URL)
        
        print("[ACTION] 请在浏览器中扫码登录，登录完成后程序将自动继续...")
        
        # 循环检测 URL 变化，等待登录成功
        while True:
            # 获取当前浏览器地址栏 URL
            current_url = self.driver.current_url
            # 登录成功后 URL 会包含 token 参数
            if "token=" in current_url:
                # 使用正则提取 token 值
                self.token = re.findall(r"token=(\d+)", current_url)[0]
                break
            # 每隔 1 秒检测一次
            time.sleep(1)
        
        # 获取 Selenium 浏览器的所有 Cookies
        selenium_cookies = self.driver.get_cookies()
        # 将 Selenium 格式的 Cookies 转换为 requests 库需要的字典格式 {name: value}
        self.cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
        
        # 保存新的会话信息到本地
        self.save_cookies()
        
        # 登录流程结束，关闭浏览器释放资源
        self.driver.quit()
        # 返回 cookies 和 token 供引擎使用
        return self.cookies, self.token
