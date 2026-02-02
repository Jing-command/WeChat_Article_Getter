"""
爬虫引擎模块
核心业务逻辑：搜索公众号、获取文章列表、下载文章内容（含图片）
"""

import requests  # 导入HTTP请求库
import random  # 导入随机数模块（用于随机延时）
import time  # 导入时间模块（用于延时和时间戳处理）
import os  # 导入操作系统接口模块（用于文件和目录操作）
import re  # 导入正则表达式模块（用于文本匹配和提取）
from bs4 import BeautifulSoup  # 导入HTML解析库（用于解析和修改HTML内容）
from config import Config  # 导入配置类

class CrawlerEngine:
    """
    爬虫引擎类
    负责与微信公众平台API交互，实现文章搜索、获取和下载功能
    """
    
    def __init__(self, cookies, token, output_dir=None):
        """
        初始化爬虫引擎
        
        Args:
            cookies (dict): 登录后获取的cookies字典（用于身份验证）
            token (str): 微信公众平台接口调用token（API鉴权凭证）
            output_dir (str, optional): 自定义输出目录路径，默认使用配置文件中的路径
        """
        # 保存会话需要的Cookies（每次HTTP请求都需要携带）
        self.cookies = cookies
        # 保存接口调用需要的Token（微信API的鉴权参数）
        self.token = token
        # 设置输出目录（用户自定义路径优先，否则使用配置文件的默认路径）
        self.output_dir = output_dir if output_dir else Config.HTML_DIR
        # 确保输出目录存在（如果不存在则创建）
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"[INFO] 已创建输出目录: {self.output_dir}")
        
        # 暂停检查回调函数（由GUI设置，用于支持暂停/恢复功能）
        self.pause_check_callback = None
        
        # 设置通用的HTTP请求头（模拟真实浏览器）
        self.headers = {
            "User-Agent": Config.USER_AGENT,  # 浏览器标识
            "Referer": Config.BASE_URL,  # 来源页面（微信公众平台首页）
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "X-Requested-With": "XMLHttpRequest"
        }

    def _random_sleep(self):
        """
        随机延时方法
        在MIN_SLEEP和MAX_SLEEP之间随机休眠，模拟人工操作频率，避免触发反爬机制
        """
        # 生成随机休眠时间（秒）
        sleep_time = random.uniform(Config.MIN_SLEEP, Config.MAX_SLEEP)
        print(f"[WAIT] 随机等待 {sleep_time:.2f} 秒...")
        # 休眠指定时间
        time.sleep(sleep_time)

    def search_account(self, nickname):
        """
        通过公众号昵称搜索公众号，获取其FakeID
        FakeID是微信公众平台内部的公众号唯一标识，用于后续获取文章列表
        
        Args:
            nickname (str): 公众号昵称（支持模糊搜索）
            
        Returns:
            str: 找到的公众号的FakeID，未找到返回None
        """
        print(f"[SEARCH] 正在搜索公众号: {nickname}")
        
        # 调试：显示关键Cookie字段（用于诊断）
        key_cookies = ['data_bizuin', 'bizuin', 'data_ticket', 'slave_sid', 'slave_user']
        present_cookies = [k for k in key_cookies if k in self.cookies]
        print(f"[DEBUG] 关键Cookie字段: {', '.join(present_cookies) if present_cookies else '无'}")
        print(f"[DEBUG] 总Cookie数量: {len(self.cookies)}")
        
        # 构造搜索接口的查询参数
        params = {
            "action": "search_biz",  # 动作类型：搜索公众号
            "token": self.token,     # 鉴权Token（从登录后获取）
            "lang": "zh_CN",         # 语言设置：简体中文
            "f": "json",             # 返回格式：JSON
            "ajax": "1",             # 异步请求标识
            "query": nickname,       # 搜索关键词（公众号昵称）
            "begin": "0",            # 起始页码（从0开始）
            "count": "3"             # 每页返回数量（最多3个结果）
        }
        
        # 请求前随机休眠（模拟人工操作，避免触发反爬）
        self._random_sleep()
        
        try:
            # 发送GET请求到搜索接口
            resp = requests.get(Config.SEARCH_URL, cookies=self.cookies, headers=self.headers, params=params, timeout=15)
            
            # 检查HTTP状态码
            if resp.status_code != 200:
                print(f"[ERROR] HTTP请求失败，状态码: {resp.status_code}")
                return None
            
            # 解析JSON响应数据
            try:
                data = resp.json()
            except Exception as e:
                print(f"[ERROR] JSON解析失败: {e}")
                print(f"[DEBUG] 响应内容前200字符: {resp.text[:200]}")
                return None
            
            # 检查返回码，ret=0表示成功，非0表示失败（如Session过期或被封禁）
            base_resp = data.get("base_resp", {})
            ret_code = base_resp.get("ret", -1)
            err_msg = base_resp.get("err_msg", "未知错误")
            
            if ret_code != 0:
                print(f"[ERROR] 搜索接口返回错误")
                print(f"[ERROR] 错误码: {ret_code}")
                print(f"[ERROR] 错误信息: {err_msg}")
                
                # 针对常见错误码给出提示
                if ret_code == 200013:
                    print("[HINT] Cookie已过期，请重新获取登录凭证")
                elif ret_code == -1:
                    print("[HINT] 接口参数可能有误或接口已变更")
                elif ret_code == 200003:
                    if "invalid session" in err_msg.lower():
                        print("[HINT] Cookie无效或不完整！")
                        print("[HINT] 常见原因：")
                        print("       1. Cookie已过期（最常见） - 需要重新登录")
                        print("       2. Cookie复制不完整 - 确保复制了所有Cookie字段")
                        print("       3. Token与Cookie不匹配 - 确保来自同一次登录")
                        print("[HINT] 解决方案：")
                        print("       1. 重新登录微信公众平台 https://mp.weixin.qq.com")
                        print("       2. 使用【一键复制工具】获取完整凭证")
                        print("       3. 运行 'python check_cookies.py' 检查Cookie完整性")
                    else:
                        print("[HINT] 操作频繁，请稍后再试")
                else:
                    print("[HINT] 建议检查Token和Cookies是否正确，或尝试重新登录")
                
                return None

            # 获取搜索结果列表
            biz_list = data.get("list", [])
            if biz_list:
                # 提取第一个匹配公众号的 fakeid (全平台唯一标识)
                fakeid = biz_list[0].get("fakeid")
                nickname_found = biz_list[0].get("nickname")
                print(f"[SUCCESS] 找到目标: {nickname_found} (FakeID: {fakeid})")
                return fakeid
            else:
                print("[ERROR] 未找到相关公众号")
                print(f"[HINT] 请检查公众号名称是否正确: '{nickname}'")
                print("[HINT] 建议使用文章链接进行下载（更稳定）")
                return None
                
        except requests.Timeout:
            print("[ERROR] 请求超时，请检查网络连接")
            return None
        except requests.RequestException as e:
            print(f"[ERROR] 网络请求异常: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] 未预期的错误: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_articles(self, fakeid, count=5):
        """根据 FakeID 获取公众号的文章列表（支持分页）"""
        print(f"[CRAWL] 开始抓取文章...")

        results = []
        begin = 0
        # 微信接口单次返回数量常有上限，采用分页抓取
        while len(results) < count:
            batch_count = min(5, count - len(results))
            params = {
                "token": self.token,
                "lang": "zh_CN",
                "f": "json",
                "ajax": "1",
                "action": "list_ex",  # 动作：获取文章列表
                "begin": str(begin),   # 起始位置（翻页用）
                "count": str(batch_count),  # 获取数量（单次）
                "query": "",
                "fakeid": fakeid,     # 目标公众号 ID
                "type": "9"           # 类型: 9 代表图文消息
            }

            self._random_sleep()
            resp = requests.get(Config.APPMSG_URL, cookies=self.cookies, headers=self.headers, params=params)
            data = resp.json()

            if data.get("base_resp", {}).get("ret") != 0:
                print(f"[ERROR] 获取文章失败: {data}")
                break

            batch = self._parse_articles(data)
            if not batch:
                break

            results.extend(batch)
            begin += len(batch)

            # 如果返回数量小于本次请求，说明已到末尾
            if len(batch) < batch_count:
                break

        return results[:count]

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
                "create_timestamp": msg.get("create_time"),  # 保留原始时间戳用于日期过滤
                "digest": msg.get("digest")  # 文章摘要
            }
            results.append(item)
        return results
    
    def get_articles_by_date(self, fakeid, start_date, end_date):
        """根据日期范围获取公众号文章"""
        from datetime import datetime
        
        print(f"[CRAWL] 开始按日期范围抓取文章: {start_date} 至 {end_date}")
        
        # 转换日期字符串为时间戳
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
        end_ts = int(datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').timestamp())
        
        results = []
        begin = 0
        max_fetch = 500  # 最多获取500篇（防止无限循环）
        found_older = False  # 标记是否找到更早的文章
        
        # 持续获取直到超出日期范围
        while begin < max_fetch:
            batch_count = 5
            params = {
                "token": self.token,
                "lang": "zh_CN",
                "f": "json",
                "ajax": "1",
                "action": "list_ex",
                "begin": str(begin),
                "count": str(batch_count),
                "query": "",
                "fakeid": fakeid,
                "type": "9"
            }

            self._random_sleep()
            resp = requests.get(Config.APPMSG_URL, cookies=self.cookies, headers=self.headers, params=params)
            data = resp.json()

            if data.get("base_resp", {}).get("ret") != 0:
                print(f"[ERROR] 获取文章失败: {data}")
                break

            batch = self._parse_articles(data)
            if not batch:
                print(f"[INFO] 没有更多文章了")
                break

            # 过滤日期范围内的文章
            for article in batch:
                ts = article.get("create_timestamp", 0)
                if start_ts <= ts <= end_ts:
                    results.append(article)
                elif ts < start_ts:
                    # 标记找到了更早的文章
                    found_older = True

            begin += len(batch)
            
            # 如果这一批全部都早于开始日期，说明后续都更早，可以停止
            if found_older and all(a.get("create_timestamp", 0) < start_ts for a in batch):
                print(f"[INFO] 已到达日期范围之前的文章，停止获取")
                break
            
            # 如果返回数量小于请求数量，说明已到末尾
            if len(batch) < batch_count:
                print(f"[INFO] 已获取所有文章")
                break
        
        print(f"[INFO] 在指定日期范围内找到 {len(results)} 篇文章")
        return results
    
    def fetch_article_metadata(self, url):
        """获取单个文章的元数据(主要是标题)"""
        print(f"[INFO] 正在解析链接: {url}")
        try:
            headers = self.headers.copy()
            # 简单的请求获取标题
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[ERROR] 无法访问链接，状态码: {resp.status_code}")
                return None
            
            resp.encoding = 'utf-8' # 微信通常是utf-8
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 尝试获取标题
            # 微信文章通常在 og:title meta中，或者 id="activity-name"
            title = None
            
            # 方法1: meta og:title
            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content')
                
            # 方法2: id="activity-name"
            if not title:
                activity_name = soup.find(id="activity-name")
                if activity_name:
                    title = activity_name.get_text(strip=True)
                    
            # 方法3: title 标签
            if not title and soup.title:
                title = soup.title.string
                
            if not title:
                title = f"未命名文章_{int(time.time())}"
                
            return {
                "title": title,
                "link": url,
                "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "digest": ""
            }
            
        except Exception as e:
            print(f"[ERROR] 解析链接失败: {e}")
            return None
    
    def extract_fakeid_from_url(self, url):
        """从微信文章URL中提取公众号的fakeid"""
        print(f"[INFO] 正在从URL提取公众号信息...")
        try:
            # 方法1: 从URL参数中提取__biz
            # 微信文章URL格式: https://mp.weixin.qq.com/s?__biz=MzA...&mid=...
            biz_match = re.search(r'__biz=([^&]+)', url)
            biz = biz_match.group(1) if biz_match else None
            if biz:
                print(f"[INFO] 提取到__biz: {biz[:20]}...")
            else:
                print("[WARN] 无法从URL中提取__biz参数，尝试从页面内容解析...")
            
            # 方法2: 通过搜索接口查找该公众号
            # 先获取文章标题，然后通过文章内容找到公众号名称
            headers = self.headers.copy()
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[ERROR] 无法访问链接")
                return None
            
            resp.encoding = 'utf-8'
            html_text = resp.text
            soup = BeautifulSoup(html_text, 'html.parser')

            # 方法2: 从页面脚本中提取 biz
            if not biz:
                biz_patterns = [
                    r'var\s+biz\s*=\s*"([^"]+)"',
                    r'"biz"\s*:\s*"([^"]+)"',
                    r'__biz=([^&"\\]+)'
                ]
                for pattern in biz_patterns:
                    m = re.search(pattern, html_text)
                    if m:
                        biz = m.group(1)
                        break

                if biz:
                    print(f"[INFO] 从页面内容提取到__biz: {biz[:20]}...")
                    return biz
            
            # 提取公众号名称
            account_name = None
            
            # 方法A: id="js_name"
            js_name = soup.find(id="js_name")
            if js_name:
                account_name = js_name.get_text(strip=True)
            
            # 方法B: meta property="og:article:author"
            if not account_name:
                og_author = soup.find('meta', property='og:article:author')
                if og_author:
                    account_name = og_author.get('content')
            
            # 方法C: class="rich_media_meta rich_media_meta_nickname"
            if not account_name:
                meta_nickname = soup.find(class_="rich_media_meta_nickname")
                if meta_nickname:
                    account_name = meta_nickname.get_text(strip=True)
                    
            if not account_name:
                print("[ERROR] 无法从文章页面提取公众号名称")
                return None
            
            print(f"[INFO] 识别到公众号: {account_name}")
            
            # 通过名称搜索获取fakeid
            fakeid = self.search_account(account_name)
            
            return fakeid
            
        except Exception as e:
            print(f"[ERROR] 提取公众号信息失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _sanitize_filename(self, filename):
        """处理文件名中的非法字符"""
        return re.sub(r'[\\/:*?"<>|]', '_', filename).strip()

    def _download_videos_for_html(self, soup, save_folder_name, article_url):
        """
        处理文章中的视频：
        识别所有视频 (视频号、公众号视频、Iframe) -> 替换为提示文本 (不下载)
        """
        
        # 定义一个通用的替换函数
        def replace_with_notice(tag, text="【视频无法下载】"):
            if not tag: return
            msg_div = soup.new_tag("div")
            msg_div['style'] = (
                "padding: 20px; text-align: center; background-color: #f0f0f0; "
                "color: #666; border: 1px dashed #999; margin: 10px 0; font-size: 14px;"
            )
            msg_div.string = text
            tag.replace_with(msg_div)

        # 1. 视频号 (Channels/Finder)
        channels_tags = []
        channels_tags.extend(soup.find_all('mp-common-videosnap'))
        channels_tags.extend(soup.find_all(class_='js_wechannel_video_card'))
        channels_tags.extend(soup.find_all(class_="js_finder_card"))
        channels_tags.extend(soup.find_all(attrs={"data-finder-feed-id": True}))
        
        # 去重
        seen_ids = set()
        for tag in channels_tags:
            if id(tag) not in seen_ids:
                replace_with_notice(tag, "【视频号视频不支持下载】")
                seen_ids.add(id(tag))

        # 2. 公众号视频 (mp-video)
        mp_videos = soup.find_all('mp-video')
        for tag in mp_videos:
             replace_with_notice(tag, "【文章内嵌视频不支持下载】")

        # 3. Iframe 视频
        for iframe in soup.find_all('iframe'):
            src = iframe.get('data-src') or iframe.get('src') or ""
            classes = iframe.get('class') or []
            if isinstance(classes, str): classes = [classes]
            
            is_video = False
            if 'video_iframe' in classes:
                is_video = True
            elif any(d in src for d in Config.VIDEO_DOMAINS):
                is_video = True
            elif iframe.has_attr('data-vid') or iframe.has_attr('data-mpvid'):
                is_video = True
                
            if is_video:
                replace_with_notice(iframe, "【文章内嵌视频不支持下载】")

        print(f"    [VIDEO] 已跳过所有视频下载，替换为提示文本")                    
        return True

    def _download_images_for_html(self, html_content, save_folder_name, article_url):
        """解析HTML，下载图片并替换链接，同时清理无用脚本和外部资源"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. 下载并处理视频 (新增)
        # 注意：这必须在移除 iframe 之前执行
        self._download_videos_for_html(soup, save_folder_name, article_url)

        # 2. 移除所有 script 标签，防止JS阻塞
        for script in soup.find_all('script'):
            script.decompose()

        # 3. 移除剩余的 iframe (视频组件)，因为断网无法加载且会拖慢速度
        # 已经处理过的 iframe 已经被 video 标签替换了，这里移除的是其他的（如广告、特定插件）
        for iframe in soup.find_all('iframe'):
            iframe.decompose()

        # 3. 处理外部 CSS 链接
        # 策略：尝试下载 CSS 内容并内嵌到 HTML 中，如果下载失败则移除链接，防止转圈
        css_links = soup.find_all('link', rel='stylesheet')
        print(f"    [CSS] 发现 {len(css_links)} 个外部CSS，尝试本地化...")
        
        for link in css_links:
            href = link.get('href')
            if not href:
                link.decompose()
                continue
            
            # 修复无协议头的 URL (如 //res.wx.qq.com...)
            if href.startswith('//'):
                href = 'https:' + href
                
            try:
                # 尝试下载 CSS 内容
                headers_css = self.headers.copy()
                headers_css['Accept'] = 'text/css,*/*;q=0.1'
                res = requests.get(href, headers=headers_css, timeout=5)
                
                if res.status_code == 200:
                    # 创建新的 style 标签
                    new_style = soup.new_tag("style")
                    new_style.string = res.text
                    # 插入到 head 中
                    if not soup.head:
                        soup.insert(0, soup.new_tag("head"))
                    soup.head.append(new_style)
                    print(f"    [CSS] 成功内嵌: {href[:30]}...")
                else:
                    print(f"    [WARN] CSS下载失败 {res.status_code}: {href[:30]}...")
            except Exception as e:
                print(f"    [WARN] CSS处理出错: {e}")
            
            # 无论是否下载成功，都移除原 link 标签，防止浏览器再次请求导致转圈
            link.decompose()
            
        # 4. 保留内联样式，但处理 visibility 问题
        # 微信文章正文 div 带有 style="visibility: hidden;"，需要覆盖它
        # 移除 onerror 防止循环报错
        for tag in soup.find_all(True):
            if tag.has_attr('onerror'):
                del tag['onerror']
            # 注意：此处不再删除 style 属性，以保留文章原本的排版（颜色、字体等）
        
        # 5. 注入覆盖样式，强制显示内容
        # 使用 !important 覆盖掉内联样式中的 visibility: hidden
        style_content = """
        <style>
            /* 强制覆盖微信的隐藏逻辑，但保留其他内联样式 */
            .rich_media_area_primary_inner, #js_content, body, .rich_media_content {
                visibility: visible !important;
                opacity: 1 !important;
            }
            /* 修复可能的图片显示问题 */
            img { 
                max-width: 100% !important; 
                height: auto !important; 
            }
             /* 隐藏原本需要JS加载的 loading 提示 */
            #js_loading { display: none !important; }
            
            body { 
                font-family: -apple-system, system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; 
                line-height: 1.8; 
                padding: 20px; 
                background-color: #f6f6f6;
                color: #333;
            }
            /* 模拟微信文章容器 */
            #js_content, #img-content, .rich_media_area_primary_inner { 
                max-width: 677px; /* 微信经典宽度 */
                margin: 0 auto; 
                background-color: #fff; 
                padding: 40px;
                border: 1px solid #e7e7eb;
            }
            /* 标题样式 */
            .rich_media_title {
                font-size: 22px;
                font-weight: 700;
                margin-bottom: 20px;
                line-height: 1.4;
            }
            /* 图片样式 */
            img { 
                max-width: 100% !important; 
                height: auto !important; 
                display: block; 
                margin: 20px auto; 
                border-radius: 4px;
            }
            /* 段落 */
            p {
                margin-bottom: 1.5em;
                text-align: justify;
                font-size: 16px;
            }
        </style>
        """ 
        # 插入 meta charset
        if not soup.head.find("meta", attrs={"charset": True}):
            meta_charset = soup.new_tag("meta", charset="utf-8")
            soup.head.insert(0, meta_charset)
            
        # 插入自定义样式
        soup.head.append(BeautifulSoup(style_content, 'html.parser'))
        
        # 创建该文章对应的图片存放目录
        # 结构: output_dir/文章标题_files/
        images_dir_rel = f"{save_folder_name}_files"
        # 使用实例的output_dir而不是Config.HTML_DIR
        images_dir_abs = os.path.join(self.output_dir, images_dir_rel)
        
        if not os.path.exists(images_dir_abs):
            os.makedirs(images_dir_abs)
            
        # 查找所有图片标签
        imgs = soup.find_all('img')
        print(f"    [IMG] 发现 {len(imgs)} 张图片，开始下载...")
        
        for idx, img in enumerate(imgs):
            # 获取图片链接 (微信通常放在 data-src 中)
            img_url = img.get('data-src')
            if not img_url:
                continue
                
            # 获取图片格式 (data-type)
            img_type = img.get('data-type', 'jpg')
            # 简单的格式修正
            if img_type == 'jpeg': img_type = 'jpg'
            if img_type == 'png': img_type = 'png'
            if img_type == 'gif': img_type = 'gif'
            
            # 生成本地文件名 (自增序号)
            img_filename = f"{idx}_{int(time.time())}.{img_type}"
            img_path_abs = os.path.join(images_dir_abs, img_filename)
            
            try:
                # 下载图片
                # 注意：这里不需要 random_sleep，因为图片资源服务器通常没有严格频率限制，且图片很多，sleep太慢
                # 但为了安全起见，可以极其微小的sleep或者不做
                res = requests.get(img_url, headers=self.headers, timeout=10)
                if res.status_code == 200:
                    with open(img_path_abs, 'wb') as f:
                        f.write(res.content)
                    
                    # 修改 HTML 中的标签
                    # 将 data-src 和 src 都指向本地相对路径
                    # 相对路径应该是: ./文章标题_files/图片名.jpg
                    local_src = f"./{images_dir_rel}/{img_filename}"
                    img['src'] = local_src
                    img['data-src'] = local_src # 覆盖 data-src 以防 JS 再次修改
                else:
                   print(f"    [WARN] 图片下载失败 Status {res.status_code}: {img_url[:30]}...")
            except Exception as e:
                print(f"    [WARN] 图片下载出错: {e}")
                
        return str(soup)

    def download_articles_content(self, articles):
        """下载文章HTML内容到本地"""
        print(f"[DOWNLOAD] 开始下载 {len(articles)} 篇文章的HTML内容...")
        for i, article in enumerate(articles):
            # 检查是否需要暂停或停止
            if self.pause_check_callback and self.pause_check_callback():
                print("[INFO] 下载已取消")
                return articles
            
            url = article['link']
            title = article['title']
            
            # 简单的防重名处理
            safe_title = self._sanitize_filename(title)
            file_name = f"{safe_title}.html"
            # 使用实例的output_dir而不是Config.HTML_DIR
            file_path = os.path.join(self.output_dir, file_name)
            
            # 如果文件已存在，跳过 (或者可以选择覆盖)
            if os.path.exists(file_path):
                print(f"  [SKIP] {title} (文件已存在)")
                article['local_path'] = file_path
                continue

            try:
                self._random_sleep()
                print(f"  [DOWN] 正在下载: {title}")
                resp = requests.get(url, headers=self.headers)
                
                # 处理图片并替换链接
                html_content = self._download_images_for_html(resp.text, safe_title, url)
                
                # 写入文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # 更新文章信息，加入本地路径
                article['local_path'] = file_path
                print(f"  [OK] 保存成功")
                
            except Exception as e:
                print(f"  [ERROR] 下载失败 {title}: {e}")
                import traceback
                traceback.print_exc()
                article['local_path'] = None

        return articles
