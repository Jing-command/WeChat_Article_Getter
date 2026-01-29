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
    # 定义抓取结果保存的文件路径
    RESULT_FILE = os.path.join(DATA_DIR, "articles_result.json")

    # Chrome 驱动设置
    HEADLESS = False  # 是否开启无头模式（不显示浏览器界面），扫码登录时建议设为False以便人工操作
    # 模拟浏览器的User-Agent，伪装成普通用户
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # 反爬频率设置 (秒)，在请求之间随机休眠 2-5 秒
    MIN_SLEEP = 2
    MAX_SLEEP = 5
