# 英语抽认卡学习网站 · English Flashcard Study

基于 NotebookLM 生成的抽认卡数据，构建的个人英语学习工具。

## 目录结构

```
EnglishStudy/
├── client/                 # 前端代码
│   ├── index.html          # 主页面
│   ├── css/
│   │   └── style.css       # 设计系统和样式
│   ├── js/
│   │   └── app.js          # 应用逻辑
│   └── data/
│       └── flashcards.csv  # 抽认卡数据
├── server/                 # 后端代码（待开发）
├── flashcards.csv          # 原始数据源
├── .agents/                # AI Agent Skills
└── README.md
```

## 快速开始

### 方式一：直接打开（推荐）
双击 `client/index.html` 即可在浏览器中使用。

### 方式二：本地服务器
```bash
npx serve client -l 3000
```
然后访问 http://localhost:3000

## 功能

- 🎴 3D 翻转卡片（中文题 → 英文答案）
- 📂 12 个场景分类筛选
- ✅ 自评系统（认识 / 模糊 / 不认识）
- 📊 学习进度追踪
- ⌨️ 键盘快捷键
- 🌙 暗色 / 亮色主题
- 💾 本地持久化（localStorage）

## 键盘快捷键

| 按键 | 功能 |
|------|------|
| `Space` | 翻转卡片 |
| `←` `→` | 前后切换 |
| `1` | 认识 |
| `2` | 模糊 |
| `3` | 不认识 |
