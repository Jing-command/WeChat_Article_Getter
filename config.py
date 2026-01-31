import os

class Config:
    # 微信公众平台的基础域名
    BASE_URL = "https://mp.weixin.qq.com"
    # 登录页面的URL
    LOGIN_URL = "https://mp.weixin.qq.com/"
    # 搜索公众号的接口地址
    SEARCH_URL = "https://mp.weixin.qq.com/cgi-bin/searchbiz"
    # 获取公众号文章列表的接口地址
    APPMSG_URL = "https://mp.weixin.qq.com/cgi-bin/appmsg"

    # 获取当前文件的目录，拼接出数据存储目录 'data'
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    # 如果数据目录不存在，则创建它
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # 定义Cookie保存的文件路径
    COOKIES_FILE = os.path.join(DATA_DIR, "cookies.json")
    
    # 定义文章HTML内容保存的目录
    HTML_DIR = os.path.join(DATA_DIR, "html")
    if not os.path.exists(HTML_DIR):
        os.makedirs(HTML_DIR)

    # 微信视频域名特征
    VIDEO_DOMAINS = [
        "v.qq.com", 
        "mp.weixin.qq.com/mp/readtemplate?t=pages/video_player_tmpl", 
        "weixin.qq.com/video",
        "finder.video.qq.com",
        "channels.weixin.qq.com"
    ]

    # Chrome 驱动设置
    HEADLESS = False  # 是否开启无头模式（不显示浏览器界面），扫码登录时建议设为False以便人工操作
    # 手动指定 ChromeDriver 路径 (如果自动下载失败，请下载对应版本的驱动并在此填写路径，例如 "e:/tools/chromedriver.exe")
    CHROMEDRIVER_PATH = ""

    # 手动指定 EdgeDriver 路径 (如果自动下载失败，请下载对应版本的驱动并在此填写路径，例如 "e:/tools/msedgedriver.exe")
    EDGEDRIVER_PATH = "E:\\VsCode\\WeChat_Article_Getter\\msedgedriver.exe"
    
    # 浏览器选择: "chrome" 或 "edge"
    # 如果 Chrome 驱动难以配置，建议改为 "edge"，Windows 系统自带 Edge 浏览器且驱动更容易自动配置
    BROWSER_TYPE = "edge"

    # 模拟浏览器的User-Agent，伪装成普通用户
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # 视频号/微信视频使用移动端UA（避免跳转到支持页）
    VIDEO_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.44"

    # 反爬频率设置 (秒)，在请求之间随机休眠 2-5 秒
    MIN_SLEEP = 2
    MAX_SLEEP = 5
