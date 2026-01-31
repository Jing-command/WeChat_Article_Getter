"""
配置文件模块
存储项目的所有配置项，包括URL、路径、浏览器设置等
"""

import os  # 导入操作系统接口模块，用于文件路径操作

class Config:
    """
    配置类
    集中管理项目的所有配置参数
    """
    
    # ==================== URL配置 ====================
    # 微信公众平台的基础域名
    BASE_URL = "https://mp.weixin.qq.com"
    # 登录页面的URL（用于扫码登录）
    LOGIN_URL = "https://mp.weixin.qq.com/"
    # 搜索公众号的接口地址（用于通过昵称查找公众号）
    SEARCH_URL = "https://mp.weixin.qq.com/cgi-bin/searchbiz"
    # 获取公众号文章列表的接口地址（用于获取历史文章）
    APPMSG_URL = "https://mp.weixin.qq.com/cgi-bin/appmsg"

    # ==================== 路径配置 ====================
    # 获取当前文件的目录，拼接出数据存储目录 'data'
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    # 如果数据目录不存在，则创建它（用于存储cookies等数据）
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # 定义Cookie保存的文件路径（登录后的cookie会持久化到此文件）
    COOKIES_FILE = os.path.join(DATA_DIR, "cookies.json")
    
    # 定义文章HTML内容保存的目录（下载的文章默认保存位置）
    HTML_DIR = os.path.join(DATA_DIR, "html")
    # 如果HTML目录不存在，则创建它
    if not os.path.exists(HTML_DIR):
        os.makedirs(HTML_DIR)

    # ==================== 视频相关配置 ====================
    # 微信视频域名特征列表（用于识别视频内容）
    VIDEO_DOMAINS = [
        "v.qq.com",  # 腾讯视频域名
        "mp.weixin.qq.com/mp/readtemplate?t=pages/video_player_tmpl",  # 微信视频播放器
        "weixin.qq.com/video",  # 微信视频域名
        "finder.video.qq.com",  # 视频号域名
        "channels.weixin.qq.com"  # 视频号频道域名
    ]

    # ==================== 浏览器配置 ====================
    # 是否开启无头模式（不显示浏览器界面）
    # False: 显示浏览器窗口，扫码登录时需要人工操作
    HEADLESS = False
    
    # 手动指定 ChromeDriver 路径
    # 如果自动下载失败，请下载对应版本的驱动并在此填写路径
    # 例如: "e:/tools/chromedriver.exe"
    CHROMEDRIVER_PATH = ""

    # 手动指定 EdgeDriver 路径
    # 如果自动下载失败，请下载对应版本的驱动并在此填写路径
    # 例如: "e:/tools/msedgedriver.exe"
    EDGEDRIVER_PATH = "E:\\VsCode\\WeChat_Article_Getter\\msedgedriver.exe"
    
    # 浏览器选择: "chrome" 或 "edge"
    # 推荐使用 "edge"，因为Windows系统自带Edge浏览器且驱动更容易自动配置
    BROWSER_TYPE = "edge"

    # ==================== User-Agent配置 ====================
    # 模拟浏览器的User-Agent，伪装成普通用户访问（避免被识别为爬虫）
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # 视频号/微信视频使用移动端User-Agent
    # 使用移动端UA可以避免跳转到不支持的页面
    VIDEO_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.44"

    # ==================== 反爬虫配置 ====================
    # 最小休眠时间（秒），请求之间会随机休眠，模拟人工操作
    MIN_SLEEP = 2
    # 最大休眠时间（秒）
    MAX_SLEEP = 5
