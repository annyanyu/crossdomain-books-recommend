# 图书推荐系统

一个基于跨领域推荐算法的图书推荐系统，支持多目标排序和跨领域推荐。

## 功能特点

- 📚 图书浏览与搜索
- 🎯 基于内容的推荐算法
- 🔄 跨领域图书推荐
- 📊 多目标排序（综合/评分/最新）
- 💡 美观的Web界面

## 系统架构

```
图书推荐系统/
├── app.py                 # Flask后端服务
├── config.json            # 配置文件
├── init_database.py       # 数据库初始化脚本
├── requirements.txt       # Python依赖
├── templates/
│   └── index.html         # 前端页面模板
└── static/
    ├── css/
    │   └── style.css      # 样式文件
    └── js/
        └── main.js        # 前端交互脚本
```

## 快速开始

### 1. 环境要求

- Python 3.8+
- MySQL 5.7+

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库

编辑 `config.json` 文件，修改数据库连接信息：

```json
{
    "database": {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "你的密码",
        "database": "book_recommend",
        "table": "books"
    }
}
```

### 4. 初始化数据库

```bash
python init_database.py
```

### 5. 启动服务

```bash
python app.py
```

### 6. 访问系统

打开浏览器访问：http://localhost:5000

## API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/books` | GET | 获取图书列表 |
| `/api/books/<id>` | GET | 获取图书详情 |
| `/api/recommend/<id>` | GET | 获取推荐图书 |
| `/api/sort-modes` | GET | 获取排序模式 |
| `/api/stats` | GET | 获取统计数据 |

## 推荐算法

系统使用跨领域推荐算法，主要特点：

1. **关键词相似度计算**
   - 平均向量相似度
   - 最大匹配相似度
   - 加权融合

2. **语义相似度计算**
   - 基于图书嵌入向量的余弦相似度

3. **跨领域系数**
   - 根据领域标签重叠数计算

4. **综合得分**
   - 结合语义相似度、关键词相似度和跨领域系数

## 开发团队

四人小组 - 2026年3月

## 许可证

MIT License
