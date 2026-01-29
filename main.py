from core.session import SessionManager
from core.engine import CrawlerEngine
import sys

def main():
    # 获取用户输入的目标公众号名称
    target_name = input("请输入要抓取的公众号名称: ").strip()
    if not target_name:
        print("未输入名称，退出。")
        return

    # 1. 会话管理（自动登录/复用）
    # 初始化会话管理器
    session_mgr = SessionManager()
    # 执行登录逻辑，获取有效的 cookies 和 token
    cookies, token = session_mgr.login()
    
    # 如果登录失败，终止程序
    if not cookies or not token:
        print("[FATAL] 登录失败，无法继续")
        sys.exit(1)

    # 2. 初始化爬虫引擎
    # 将登录凭证传入引擎
    engine = CrawlerEngine(cookies, token)

    # 3. 搜索并获取FakeID
    # 调用搜索接口，查找公众号对应的唯一 ID
    fakeid = engine.search_account(target_name)
    if not fakeid:
        print("[FATAL] 获取FakeID失败")
        sys.exit(1)

    # 4. 抓取文章
    # 根据 FakeID 抓取最新的 10 篇文章
    articles = engine.get_articles(fakeid, count=10) 
    
    # 5. 存储结果
    # 将抓取到的数据以 JSON 格式保存到本地文件
    engine.save_results(articles)
    
    print("\n任务完成!")

if __name__ == "__main__":
    main()
