# 图书统计展示与信息管理功能开发计划

## 一、架构决策：集成到现有页面 vs 独立新页面

**结论：采用独立新页面方案**

理由：

1. 现有首页（index.html）已承载推荐浏览核心功能，布局紧凑（左-图书网格 / 右-推荐面板），再嵌入统计和管理模块会导致页面臃肿、信息过载
2. 统计展示需要大面积的可视化空间（图表、数据面板），与推荐浏览的交互模式完全不同
3. 图书管理（CRUD）属于后台操作，与前台推荐体验分离更符合用户心智模型
4. 独立页面可通过导航栏无缝切换，保持各页面功能聚焦、交互流畅

**方案**：在顶部紫色导航栏添加页面切换导航，创建两个新页面：

* `/stats` — 图书统计展示页

* `/manage` — 图书信息管理页

***

## 二、功能模块一：图书统计展示（/stats）

### 2.1 后端 API

**新增接口**：`GET /api/stats/detail`

在现有 `/api/stats` 基础上扩展，返回更丰富的统计数据：

```json
{
  "success": true,
  "data": {
    "total_books": 321,
    "avg_rating": 7.8,
    "total_domains": 11,
    "domain_distribution": {
      "计算机科学": 45,
      "心理学": 32,
      "经济学": 28,
      ...
    },
    "rating_distribution": {
      "0-2": 5,
      "2-4": 12,
      "4-6": 45,
      "6-8": 156,
      "8-10": 103
    },
    "recent_books": 15,
    "top_rated_books": [...]
  }
}
```

实现要点：

* 查询 `domain_tags` JSON 字段，统计各领域图书数量

* 按评分区间统计评分分布

* 统计最近30天新增图书数量

* 获取评分 Top 5 图书

### 2.2 前端页面

**新建文件**：`backend/templates/stats.html`

页面布局（自上而下）：

1. **概览卡片区**（4列网格）

   * 📚 图书总量 | 💡 平均评分 | 🏷️ 领域数量 | 🆕 近期新增

   * 每张卡片：大号数字 + 描述文字 + 渐变图标背景

   * 风格：白色卡片 + 圆角 + 轻阴影，与现有 UI 一致

2. **领域分布可视化区**（左右两栏）

   * 左侧：水平条形图 — 各领域图书数量，按数量降序排列

     * 纯 CSS 实现（div 宽度百分比），无需引入图表库

     * 每行：领域名称 | 进度条（渐变色） | 数量

   * 右侧：评分分布直方图

     * 纯 CSS 实现，5个评分区间的柱状图

     * 每列：区间标签 | 柱状条 | 数量

3. **高评分图书展示区**

   * 横向滚动卡片列表，展示 Top 10 高评分图书

   * 每张卡片：封面缩略图 + 书名 + 评分 + 领域标签

   * 复用现有 `.book-card` 样式体系

**新建文件**：`backend/static/css/stats.css`（统计页专用样式）

**新建文件**：`backend/static/js/stats.js`（统计页专用逻辑）

***

## 三、功能模块二：图书信息管理（/manage）

### 3.1 后端 API

**新增接口**：

| 方法     | 路径                  | 功能              |
| ------ | ------------------- | --------------- |
| GET    | `/api/books/manage` | 管理列表（含分页、搜索、排序） |
| PUT    | `/api/books/<id>`   | 编辑图书信息          |
| DELETE | `/api/books/<id>`   | 删除图书            |

**GET /api/books/manage**：复用现有 `/api/books` 逻辑，增加返回更多字段（book\_intro, author\_intro, URL 等）

**PUT /api/books/<id>**：

* 接收 JSON body，支持修改：title, authors, publisher, publication\_date, rating, domain\_tags, book\_intro

* 使用 SQLAlchemy `UPDATE` 语句部分更新

* 同步更新推荐索引

**DELETE /api/books/<id>**：

* 删除数据库记录

* 同步从推荐索引中移除

* 级联删除 `book_also_like` 中的关联记录

### 3.2 前端页面

**新建文件**：`backend/templates/manage.html`

页面布局：

1. **操作工具栏**

   * 搜索框（按标题/作者搜索）

   * 排序下拉框（按ID/评分/书名/出版日期）

   * "添加图书"按钮（跳转豆瓣URL输入弹窗，复用现有添加逻辑）

2. **图书管理表格**

   * 列：ID | 封面缩略图 | 书名 | 作者 | 出版社 | 评分 | 领域标签 | 操作

   * 操作列：编辑按钮 | 删除按钮

   * 行样式：斑马纹 + hover 高亮

   * 分页控件

3. **编辑弹窗（Modal）**

   * 表单字段：书名、作者（逗号分隔）、出版社、出版日期、评分、领域标签、简介

   * 底部：保存 / 取消 按钮

   * 保存后刷新表格

4. **删除确认弹窗**

   * 显示书名，确认/取消

   * 删除后刷新表格

5. **添加图书弹窗**

   * 复用现有豆瓣URL爬取逻辑

   * 输入豆瓣URL → 爬取 → 自动填充 → 确认添加

**新建文件**：`backend/static/css/manage.css`（管理页专用样式）

**新建文件**：`backend/static/js/manage.js`（管理页专用逻辑）

***

## 四、导航栏改造

修改 `index.html` 的 header 区域，添加页面导航：

```
📚 跨域图书推荐  |  首页  统计  管理  |                    哈工大logo
```

* 当前页面导航项高亮显示（下划线 + 加粗）

* 导航项使用现有紫色渐变主题

* 三个页面共享相同的 header 结构（提取为模板片段或各自独立维护）

***

## 五、文件变更清单

### 新增文件

| 文件                              | 说明         |
| ------------------------------- | ---------- |
| `backend/templates/stats.html`  | 统计展示页 HTML |
| `backend/templates/manage.html` | 图书管理页 HTML |
| `backend/static/css/stats.css`  | 统计页样式      |
| `backend/static/css/manage.css` | 管理页样式      |
| `backend/static/js/stats.js`    | 统计页逻辑      |
| `backend/static/js/manage.js`   | 管理页逻辑      |

### 修改文件

| 文件                             | 变更内容                                                                                           |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| `backend/app.py`               | 新增3个路由（/stats, /manage）+ 3个API（/api/stats/detail, PUT /api/books/<id>, DELETE /api/books/<id>） |
| `backend/templates/index.html` | header 添加导航链接                                                                                  |

***

## 六、实施步骤

### 步骤1：后端 API 开发

1. 在 `app.py` 中新增 `/api/stats/detail` 接口
2. 新增 `PUT /api/books/<id>` 编辑接口
3. 新增 `DELETE /api/books/<id>` 删除接口
4. 新增 `/stats` 和 `/manage` 页面路由

### 步骤2：导航栏改造

1. 修改 `index.html` header，添加导航链接
2. 确保三个页面 header 一致

### 步骤3：统计展示页开发

1. 创建 `stats.html` 页面结构
2. 创建 `stats.css` 样式（概览卡片 + 条形图 + 直方图 + 高评分列表）
3. 创建 `stats.js` 逻辑（数据加载 + 渲染）

### 步骤4：图书管理页开发

1. 创建 `manage.html` 页面结构（表格 + 弹窗）
2. 创建 `manage.css` 样式（表格 + 弹窗 + 工具栏）
3. 创建 `manage.js` 逻辑（CRUD操作 + 搜索排序 + 分页）

### 步骤5：联调测试

1. 启动项目，验证三个页面导航切换
2. 验证统计数据准确性
3. 验证 CRUD 操作完整性
4. 验证删除后推荐索引同步更新

