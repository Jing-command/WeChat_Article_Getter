import requests
import random
import time
import json
from config import Config

class CrawlerEngine:
    def __init__(self, cookies, token):
        # 保存会话需要的 Cookies
        self.cookies = cookies
        # 保存接口调用需要的 Token
        self.token = token
        # 设置通用的请求头，包含 User-Agent 和 Referer
        self.headers = {
            "User-Agent": Config.USER_AGENT,
            "Referer": Config.BASE_URL
        }

    def _random_sleep(self):
        """随机延时，模拟真人操作频率，避免触发反爬机制"""
        sleep_time = random.uniform(Config.MIN_SLEEP, Config.MAX_SLEEP)
        print(f"[WAIT] 随机等待 {sleep_time:.2f} 秒...")
        time.sleep(sleep_time)

    def search_account(self, nickname):
        """通过昵称搜索公众号，获取其对应的 FakeID"""
        print(f"[SEARCH] 正在搜索公众号: {nickname}")
        # 构造搜索接口的查询参数
        params = {
            "action": "search_biz",  # 动作：搜索公众号
            "token": self.token,     # 鉴权 Token
            "lang": "zh_CN",         # 语言
            "f": "json",             # 返回格式
            "ajax": "1",             # 异步请求标识
            "query": nickname,       # 搜索关键词
            "begin": "0",            # 起始页码
            "count": "5"             # 每页数量
        }
        
        # 请求前随机休眠
        self._random_sleep()
        # 发送 GET 请求
        resp = requests.get(Config.SEARCH_URL, cookies=self.cookies, headers=self.headers, params=params)
        # 解析 JSON 响应
        data = resp.json()
        
        # 检查返回码，非 0 表示请求失败（如 Session 过期或被封禁）
        if data.get("base_resp", {}).get("ret") != 0:
            print("[ERROR] 搜索失败，可能是Session过期或频率过高")
            return None

        # 获取搜索结果列表
        biz_list = data.get("list", [])
        if biz_list:
            # 提取第一个匹配公众号的 fakeid (全平台唯一标识)
            fakeid = biz_list[0].get("fakeid")
            print(f"[SUCCESS] 找到目标: {biz_list[0].get('nickname')} (FakeID: {fakeid})")
            return fakeid
        else:
            print("[ERROR] 未找到相关公众号")
            return None

    def get_articles(self, fakeid, count=5):
        """根据 FakeID 获取公众号的文章列表"""
        print(f"[CRAWL] 开始抓取文章...")
        # 构造获取文章列表的参数
        params = {
            "token": self.token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": "1",
            "action": "list_ex",  # 动作：获取文章列表
            "begin": "0",         # 起始位置（翻页用）
            "count": str(count),  # 获取数量
            "query": "",
            "fakeid": fakeid,     # 目标公众号 ID
            "type": "9"           # 类型: 9 代表图文消息
        }
        
        # 请求前随机休眠
        self._random_sleep()
        # 发送 GET 请求
        resp = requests.get(Config.APPMSG_URL, cookies=self.cookies, headers=self.headers, params=params)
        data = resp.json()
        
        # 检查响应状态
        if data.get("base_resp", {}).get("ret") != 0:
            print(f"[ERROR] 获取文章失败: {data}")
            return []
            
        # 解析并返回数据
        return self._parse_articles(data)

    def _parse_articles(self, data):
        """清洗原始 JSON 数据，提取关键字段"""
        results = []
        # 获取文章消息列表
        msg_list = data.get("app_msg_list", [])
        for msg in msg_list:
            item = {
                "title": msg.get("title"),   # 文章标题
                "link": msg.get("link"),     # 文章链接
                # 将时间戳转换为可读的时间格式
                "create_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(msg.get("create_time"))),
                "digest": msg.get("digest")  # 文章摘要
            }
            results.append(item)
        return results

    def save_results(self, articles):
        """将抓取结果保存到 JSON 文件"""
        if not articles:
            return
            
        # 这里使用 ensure_ascii=False 保证中文字符正常显示
        with open(Config.RESULT_FILE, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=4)
        print(f"[SAVE] 已保存 {len(articles)} 篇文章到 {Config.RESULT_FILE}")
