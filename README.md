# 个人论文文献管理工具

一个面向 Windows 的桌面端论文文献管理工具，帮助用户管理本地 PDF 论文、生成参考文献、记录阅读进度和笔记。

## 技术栈

- 桌面壳：Electron
- 前端：Vue 3 + Vite
- 后端：Python + FastAPI
- 数据库：SQLite
- PDF 解析：PyMuPDF / pypdf

## 目录结构

```text
.
├── backend/                 # Python 后端
│   ├── app/main.py          # FastAPI 入口
│   └── requirements.txt     # Python 依赖
├── electron/
│   ├── main.js              # Electron 主进程
│   └── preload.js           # 预加载脚本
├── src/                     # Vue 前端源码
│   ├── App.vue
│   ├── main.js
│   └── style.css
├── index.html
├── package.json
└── 产品设计文档.md
```

## 开发运行

### 前端

```bash
npm install
npm run dev
```

### 桌面窗口

需要先启动前端开发服务器，再运行 Electron：

```bash
npm run electron:dev
```

### 打包 Windows 安装包

```bash
npm run dist
```

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Git 回滚

提交前先查看状态：

```bash
git status
```

提交一次版本：

```bash
git add .
git commit -m "描述本次修改"
```

回滚到上一个提交：

```bash
git reset --soft HEAD~1
```

回滚单个文件：

```bash
git checkout -- <文件路径>
```
