"""
会话管理模块
负责微信公众平台的登录认证、Cookie管理和会话持久化
"""

import json  # 导入JSON模块，用于cookie的序列化和反序列化
import os  # 导入操作系统接口模块
import requests  # 导入HTTP请求库
from config import Config  # 导入配置类
from utils.browser import BrowserFactory  # 导入浏览器工厂

class SessionManager:
    """
    会话管理器类
    管理微信公众平台的登录状态、Cookie和Token
    """
    
    def __init__(self):
        """
        初始化会话管理器
        """
        # 初始化存储Cookies的字典（用于HTTP请求时的身份验证）
        self.cookies = {}
        # 初始化Token（微信后台API调用的关键凭证）
        self.token = None
        # 初始化Selenium驱动对象（用于扫码登录时控制浏览器）
        self.driver = None

    def load_cookies(self):
        """
        尝试从本地文件加载已保存的Cookies和Token
        
        Returns:
            bool: 加载成功返回True，失败返回False
        """
        # 检查Cookie文件是否存在
        if os.path.exists(Config.COOKIES_FILE):
            try:
                # 以读取模式打开JSON文件
                with open(Config.COOKIES_FILE, 'r', encoding='utf-8') as f:
                    # 解析JSON数据
                    data = json.load(f)
                    # 读取cookies字段，如果不存在则使用空字典
                    self.cookies = data.get('cookies', {})
                    # 读取token字段
                    self.token = data.get('token')
                    print(f"[INFO] 本地Cookies加载成功, Token: {self.token}")
                    return True  # 加载成功
            except Exception as e:
                # 如果文件损坏或格式错误，打印错误信息
                print(f"[ERROR] Cookies加载失败: {e}")
        return False  # 文件不存在或加载失败

    def save_cookies(self):
        """
        将当前的Cookies和Token保存到本地文件
        实现会话持久化，下次可以直接使用无需重新登录
        """
        # 构造要保存的数据字典
        data = {
            'cookies': self.cookies,  # Cookie字典
            'token': self.token  # Token字符串
        }
        # 以写入模式打开文件，保存JSON数据
        with open(Config.COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)  # 将字典序列化为JSON并写入文件
        print("[INFO] 会话已保存到本地")

    def check_cookies_validity(self):
        """
        验证当前Cookies和Token是否仍然有效
        通过发送一个轻量级的API请求来测试
        
        Returns:
            bool: 有效返回True，无效返回False
        """
        # 如果cookies或token为空，直接返回无效
        if not self.cookies or not self.token:
            return False
        
        # 构造请求头（模拟浏览器请求）
        headers = {
            "User-Agent": Config.USER_AGENT,  # 用户代理
            "Referer": Config.BASE_URL  # 引用页
        }
        
        # 构造请求参数（使用搜索接口进行测试）
        params = {
            "action": "search_biz",  # 动作：搜索公众号
            "token": self.token,  # 使用当前token
            "lang": "zh_CN",  # 语言
            "f": "json",  # 返回格式
            "ajax": "1",  # Ajax请求标识
            "query": "official_account",  # 随便搜个常用词作为测试
            "begin": "0",  # 起始位置
            "count": "1"  # 只获取1条结果（减少请求开销）
        }
        
        try:
            # 发送GET请求，携带cookies和参数
            resp = requests.get(Config.SEARCH_URL, cookies=self.cookies, headers=headers, params=params)
            # 解析JSON响应
            data = resp.json()
            # 检查返回码，ret=0表示请求成功
            if data.get("base_resp", {}).get("ret") == 0:
                return True  # 会话有效
            else:
                # 返回码非0，说明会话失效
                print(f"[WARN] 验证会话失效: {data.get('base_resp')}")
                return False
        except Exception as e:
            # 请求出错（网络问题或其他异常）
            print(f"[WARN] 验证会话出错: {e}")
            return False

    def login(self):
        """
        执行登录流程
        策略：每次都启动浏览器进行扫码登录（不使用本地缓存）
        
        Returns:
            tuple: (cookies字典, token字符串)
        """
        # 启动浏览器进行扫码登录
        print("[INFO] 启动浏览器进行扫码登录...")
        # 调用浏览器工厂方法初始化防检测浏览器
        self.driver = BrowserFactory.init_driver()
        # 打开微信公众平台登录页
        self.driver.get(Config.LOGIN_URL)
        
        print("[ACTION] 请在浏览器中扫码登录，登录完成后程序将自动继续...")
        
        # 循环检测URL变化，等待用户扫码登录成功
        import time  # 导入时间模块（用于sleep）
        import re  # 导入正则表达式模块（用于提取token）
        while True:
            # 获取当前浏览器地址栏的URL
            current_url = self.driver.current_url
            # 登录成功后URL会包含token参数（格式：?token=数字）
            if "token=" in current_url:
                # 使用正则表达式提取token值
                self.token = re.findall(r"token=(\d+)", current_url)[0]
                print(f"[SUCCESS] 登录成功，获取到 Token: {self.token}")
                break  # 跳出循环
            # 每隔1秒检测一次（避免CPU占用过高）
            time.sleep(1)
        
        # 获取浏览器的所有Cookies
        selenium_cookies = self.driver.get_cookies()
        # 将Selenium格式的Cookies转换为requests库需要的字典格式 {name: value}
        self.cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
        
        # 登录流程结束，关闭浏览器释放系统资源
        self.driver.quit()
        print("[INFO] 浏览器已关闭")
        
        # 返回cookies和token供爬虫引擎使用
        return self.cookies, self.token
