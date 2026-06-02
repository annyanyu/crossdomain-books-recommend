# 一键自动导入多本图书功能模块 — 实施计划

## 一、功能概述

在管理页面新增"一键导入"功能，从豆瓣"新书速递"板块（`https://book.douban.com/latest`）自动抓取图书列表，批量导入到系统中。支持分类筛选、页数选择、进度显示、错误跳过与失败记录。

## 二、技术方案

### 2.1 数据流

```
用户点击"一键导入" → 选择分类/页数 → 前端调用批量导入API
    ↓
后端抓取新书速递列表页 → 解析出每本书的豆瓣详情页URL
    ↓
逐本调用现有单本添加管线（爬取→去重→处理→入库→索引）
    ↓
通过 SSE（Server-Sent Events）实时推送每本的处理进度
    ↓
前端实时更新进度条和状态列表
```

### 2.2 为什么选择 SSE 而非 WebSocket

- 单向推送（服务端→客户端），无需双向通信
- 基于HTTP，无需额外依赖，与现有Flask架构天然兼容
- 自动重连机制，网络抖动更健壮
- 实现简单，无需引入 Socket.IO 等库

## 三、实施步骤

### Step 1：DoubanScraper 新增新书速递列表抓取方法

**文件**：`backend/app/services/douban_scraper.py`

新增方法 `scrape_latest_books(subcat=None, page=1)`：

- 请求 `https://book.douban.com/latest`（可带 `subcat` 和 `p` 参数）
- 解析列表页HTML，提取每本书的：
  - `detail_url`：详情页URL（如 `https://book.douban.com/subject/37422259/`）
  - `title`：书名（列表页可见）
  - `cover_image`：封面缩略图URL
  - `rating`：评分（如"8.7"）
  - `authors`：作者
  - `publisher`：出版社
  - `publication_date`：出版日期
- 返回结构：`{"total": int, "books": [{detail_url, title, ...}, ...]}`
- 复用现有的 `_fetch_page`、`_get_headers`、`_is_captcha_page` 方法
- 列表页解析使用 BeautifulSoup，选择器基于实际页面结构：
  - 每本书在 `.media` 或 `#content .grid-16-8 .info` 区域
  - 书名链接 `a.fleft` 或 `h2 a`
  - 评分 `.rating-value` 或 `.rating_nums`
  - 元信息 `.meta` 或 `.color-gray`

### Step 2：后端新增批量导入 SSE API

**文件**：`backend/app.py`

新增路由 `GET /api/books/batch-import`（SSE流式响应）：

**请求参数**（Query String）：
- `subcat`（可选）：分类名称，如"文学"、"小说"、"科学新知"，空=全部
- `pages`（可选）：抓取页数，默认1，最大5（每页约20本，5页约100本）

**SSE事件格式**：
```
event: progress
data: {"current": 3, "total": 20, "title": "察金", "status": "success", "book_id": 322}

event: progress
data: {"current": 4, "total": 20, "title": "xxx", "status": "duplicate", "message": "该书籍已在系统中存在"}

event: progress
data: {"current": 5, "total": 20, "title": "yyy", "status": "error", "message": "请求超时"}

event: complete
data: {"total": 20, "success": 15, "duplicate": 3, "error": 2, "errors": [{"title": "yyy", "message": "请求超时"}]}
```

**核心逻辑**：
1. 调用 `scraper.scrape_latest_books()` 获取列表
2. 逐本处理：
   - 调用现有 `_check_duplicate()` 检查重复 → 跳过并推送 `duplicate` 事件
   - 调用现有 `scraper.scrape_book(detail_url)` 爬取详情
   - 调用现有 `processor.process_new_book()` 处理数据
   - 写入数据库 + 更新索引（复用 `/api/books/add` 中的逻辑）
   - 推送 `progress` 事件
3. 每本之间随机延迟 3-6 秒（防反爬）
4. 全部完成后推送 `complete` 事件

**错误处理**：
- 单本爬取失败：捕获异常，推送 `error` 事件，继续下一本
- 列表页抓取失败：推送 `complete` 事件（total=0, error=1）
- 验证码触发：推送 `complete` 事件，附带提示信息

**提取公共方法**：
将 `add_book()` 路由中的"爬取→去重→处理→入库→索引"逻辑提取为 `_process_and_add_book(book_data_or_url, engine)` 内部函数，供单本添加和批量导入共用。

### Step 3：前端新增批量导入UI

**文件**：`backend/templates/manage.html`

在工具栏的"添加图书"按钮旁新增"一键导入"按钮，点击打开批量导入弹窗。

**弹窗内容**：
1. **分类选择**：下拉框，选项=全部/文学/小说/历史文化/社会纪实/科学新知/艺术设计/商业经管/绘本漫画
2. **页数选择**：数字输入框，1-5，默认1
3. **开始导入按钮**
4. **进度区域**（导入过程中显示）：
   - 总进度条：`已完成 12/20`
   - 实时日志列表：每本一行，显示书名+状态图标（✅成功/⚠️重复/❌失败）
   - 日志区域可滚动，新条目自动滚动到底部
5. **完成摘要**（导入完成后显示）：
   - 成功 N 本 / 重复 N 本 / 失败 N 本
   - 失败列表（可展开查看详细原因）
   - 关闭按钮

**文件**：`backend/static/js/manage.js`

新增函数：
- `openBatchImportModal()`：打开弹窗，重置状态
- `closeBatchImportModal()`：关闭弹窗
- `startBatchImport()`：发起SSE连接，处理事件流
- `appendBatchLog(title, status, message)`：追加日志条目
- `updateBatchProgress(current, total)`：更新进度条
- `showBatchSummary(summary)`：显示完成摘要

### Step 4：样式文件更新

**文件**：`backend/static/css/manage.css`

新增样式：
- `.batch-import-btn`：一键导入按钮样式（与"添加图书"按钮风格一致，使用不同颜色区分）
- `.batch-import-modal`：批量导入弹窗（比普通弹窗更宽，约560px）
- `.batch-import-options`：选项区域布局
- `.batch-progress`：进度条容器
- `.batch-progress-bar`：进度条填充
- `.batch-log`：日志列表区域（固定高度200px，可滚动）
- `.batch-log-item`：单条日志样式（状态图标+书名+消息）
- `.batch-log-item.success` / `.duplicate` / `.error`：三种状态颜色
- `.batch-summary`：完成摘要区域

## 四、文件修改清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `backend/app/services/douban_scraper.py` | 修改 | 新增 `scrape_latest_books()` 方法 |
| `backend/app.py` | 修改 | 提取公共方法 `_process_and_add_book()`；新增 `GET /api/books/batch-import` SSE路由 |
| `backend/templates/manage.html` | 修改 | 工具栏新增"一键导入"按钮；新增批量导入弹窗HTML |
| `backend/static/js/manage.js` | 修改 | 新增批量导入相关JS函数 |
| `backend/static/css/manage.css` | 修改 | 新增批量导入相关样式 |

## 五、关键实现细节

### 5.1 列表页解析策略

豆瓣新书速递页面 `https://book.douban.com/latest` 的HTML结构：
- 每本书在 `#content .grid-168` 或 `.media` 容器中
- 书名链接：`a.fleft`（含详情页URL）
- 评分：`.rating-value` 或 `.rating_nums`
- 元信息（作者/出版社/日期）：`.meta` 或 `.color-gray`
- 分类标签页通过 `subcat` URL参数切换

解析时需兼容多种可能的CSS选择器，设置降级策略。

### 5.2 防反爬策略

- 列表页请求间隔：2-4秒随机延迟
- 详情页请求间隔：3-6秒随机延迟（复用现有scraper的重试+延迟机制）
- UA轮换：复用现有3个UA
- 验证码检测：复用现有 `_is_captcha_page()`
- 单次批量导入上限：5页×20本=100本

### 5.3 SSE实现要点

Flask原生支持SSE，使用 `Response(generate(), mimetype='text/event-stream')`：
- 设置 `X-Accel-Buffering: no` 头，防止Nginx缓冲
- 设置 `Cache-Control: no-cache`
- 每条消息后 `yield` 空行分隔
- 客户端使用 `EventSource` API 接收

### 5.4 并发安全

- 批量导入过程中，单本添加功能仍可正常使用（两者互不阻塞）
- 批量导入使用独立的scraper实例，不与单本添加共用session
- 数据库写入使用独立事务，每本书单独提交

### 5.5 进度状态定义

| 状态 | 含义 | 图标 | 颜色 |
|------|------|------|------|
| `success` | 成功导入 | ✅ | 绿色 |
| `duplicate` | 已存在跳过 | ⚠️ | 橙色 |
| `error` | 导入失败 | ❌ | 红色 |
| `processing` | 正在处理 | 🔄 | 蓝色 |

## 六、实施顺序

1. **Step 1**：`douban_scraper.py` 新增列表抓取方法
2. **Step 2**：`app.py` 提取公共方法 + 新增SSE API
3. **Step 3**：`manage.html` 新增UI元素
4. **Step 4**：`manage.js` 新增交互逻辑
5. **Step 5**：`manage.css` 新增样式
6. **Step 6**：端到端测试验证
