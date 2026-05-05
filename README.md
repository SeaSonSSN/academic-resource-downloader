# 学术资源下载器

一个简洁好用的学术资源下载工具，支持搜索和下载书籍、论文等学术资源。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特点

- 🌐 **Web界面** - 简洁直观的网页界面，非技术人员也能轻松使用
- 📖 **多类型支持** - 书籍、论文等学术资源
- 🔌 **插件架构** - 轻松添加新的下载源
- 🔒 **隐私友好** - 账号密码保存在本地，不上传任何服务器
- ⚡ **异步下载** - 后台下载，不阻塞界面

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动

```bash
python main.py
```

然后打开浏览器访问 **http://localhost:8000**

### 3. 配置（可选）

首次使用建议在设置页面填写：
- **Z-Library 账号**：用于下载书籍
- **代理地址**：如果搜索/下载失败，可能需要配置代理

## 📖 支持的下载源

| 下载源 | 类型 | 说明 |
|--------|------|------|
| **Z-Library** | 书籍 | 需要账号 |
| **arXiv** | 论文 | 免费，无需账号 |
| **Crossref** | 论文 | 免费，依赖 Unpaywall 获取PDF |
| **Semantic Scholar** | 论文 | 免费API（可能限流） |

## 🏗️ 项目结构

```
├── backend/
│   ├── main.py              # FastAPI 后端入口
│   ├── downloaders/
│   │   ├── __init__.py
│   │   ├── base.py           # 下载器基类
│   │   ├── zlibrary.py       # Z-Library 下载器
│   │   ├── arxiv.py          # arXiv 下载器
│   │   ├── crossref.py       # Crossref 下载器
│   │   └── semantic_scholar.py
│   └── static/               # Web 前端文件
│       ├── index.html
│       └── style.css (merged into index.html)
├── legacy/                   # 旧的脚本（仅供参考）
├── main.py                   # 启动入口
└── requirements.txt          # Python 依赖
```

## 🛠️ 添加新的下载源

创建一个新的下载器，继承 `BaseDownloader`：

```python
from backend.downloaders import BaseDownloader, SearchResult, DownloadTask, ResourceType

class MyDownloader(BaseDownloader):
    def supports(self, resource_type):
        return resource_type == ResourceType.JOURNAL

    async def search(self, query, resource_type):
        return [SearchResult(...)]

    async def download(self, result, save_dir):
        return DownloadTask(...)
```

然后在 `backend/main.py` 中注册即可。

## ❓ 常见问题

**Q: 搜索不到结果？**
- 检查网络连接
- 尝试配置代理
- 某些付费内容需要对应账号

**Q: Z-Library 下载失败？**
- 检查账号密码是否正确
- 检查代理是否配置正确
- 每日下载限额可能用完

**Q: 论文下载不了？**
- 部分论文是付费期刊，没有免费版本
- 尝试其他来源或搜索预印本

## ⚠️ 免责声明

本工具仅供学习研究使用。请尊重版权，合理使用资源。

## 📝 License

MIT