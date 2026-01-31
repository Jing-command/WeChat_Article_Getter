# 微信文章下载器 (WeChat Article Getter)

一个简单易用的微信公众号文章下载工具，支持单篇下载、批量下载和日期范围下载。

![](https://img.shields.io/badge/Python-3.10+-blue.svg)
![](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特点

- 🎨 **现代化界面**：基于 Sun Valley 主题的美观 GUI
- 📝 **单篇下载**：输入文章链接即可下载
- 📦 **批量下载**：一键下载指定数量的最新文章
- 📅 **日期范围**：按时间段筛选下载文章
- 📂 **自定义路径**：自由选择文章保存位置
- 🖼️ **完整保存**：自动下载文章中的图片资源
- 🎬 **视频占位**：自动跳过视频并添加占位符

## 🚀 快速开始

### 方法一：使用可执行文件（推荐）

1. 从 [Releases](https://github.com/Jing-command/WeChat_Article_Getter/releases) 下载最新版本的 `WeChat_Article_Getter.exe`
2. 下载 `msedgedriver.exe` 并放在同一目录
3. 双击运行 `WeChat_Article_Getter.exe`

### 方法二：从源码运行

1. **克隆项目**
```bash
git clone https://github.com/Jing-command/WeChat_Article_Getter.git
cd WeChat_Article_Getter
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **运行程序**
```bash
python gui.py
```

## 📖 使用说明

1. **首次登录**：启动后会打开浏览器，使用微信扫码登录公众平台
2. **输入链接**：复制任意微信文章链接到输入框
3. **选择模式**：
   - 单篇下载：直接点击"开始下载"
   - 批量下载：勾选"批量下载"，输入数量
   - 日期范围：勾选"按日期范围下载"，设置起止日期
4. **设置路径**：点击"浏览"选择保存位置（可选）
5. **开始下载**：点击"开始下载"按钮

## 🛠️ 系统要求

- Windows 10/11
- Python 3.10+ (源码运行)
- Microsoft Edge 浏览器
- 微信公众平台账号（用于登录）

## 📦 依赖库

- `requests` - HTTP 请求
- `beautifulsoup4` - HTML 解析
- `selenium` - 浏览器自动化
- `sv-ttk` - Sun Valley 主题
- `webdriver-manager` - 驱动管理
- `yt-dlp` - 视频处理
- `imageio-ffmpeg` - 媒体处理

## 🔧 配置说明

编辑 `config.py` 可以修改：
- 浏览器类型（Chrome/Edge）
- 驱动路径
- 延迟时间
- 其他高级选项

## 📝 注意事项

- ⚠️ 需要有微信公众平台账号
- ⚠️ 首次使用需要扫码登录
- ⚠️ Cookie有效期内可直接使用
- ⚠️ 视频内容无法下载（会显示占位符）
- ⚠️ 请遵守相关法律法规，仅用于个人学习研究

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## ⚠️ 免责声明

本工具仅供学习交流使用，请勿用于商业用途。使用本工具产生的任何法律责任由使用者自行承担。

---

**注意**：本项目仅用于技术学习和研究，请尊重原创作者的版权。
