# 数据库接入指南

本文档详细说明如何将关键词提取系统从CSV文件切换到数据库。

## 目录
1. [系统架构](#系统架构)
2. [支持的数据源](#支持的数据源)
3. [MySQL数据库接入](#mysql数据库接入)
4. [PostgreSQL数据库接入](#postgresql数据库接入)
5. [MongoDB数据库接入](#mongodb数据库接入)
6. [配置示例](#配置示例)
7. [常见问题](#常见问题)

---

## 系统架构

关键词提取系统采用工厂模式设计，支持多种数据源：

```
extract_keywords.py
├── KeywordExtractor          # 关键词提取核心类
│   ├── extract_tfidf_keywords()     # TF-IDF算法
│   ├── extract_textrank_keywords()   # TextRank算法
│   └── merge_keywords()              # 算法融合
│
├── BookDataLoader            # 数据加载器
│   ├── load_from_csv()       # CSV文件加载
│   ├── load_from_mysql()     # MySQL数据库加载
│   ├── load_from_postgresql() # PostgreSQL数据库加载
│   └── load_from_mongodb()   # MongoDB数据库加载
│
└── BookDataSaver             # 数据保存器
    ├── save_to_csv()         # 保存到CSV文件
    ├── save_to_mysql()       # 保存到MySQL
    ├── save_to_postgresql()  # 保存到PostgreSQL
    └── save_to_mongodb()     # 保存到MongoDB
```

---

## 支持的数据源

| 数据源类型 | 状态 | 必需依赖 |
|-----------|------|---------|
| CSV文件 | ✅ 默认支持 | pandas |
| MySQL | ✅ 支持 | pymysql, sqlalchemy |
| PostgreSQL | ✅ 支持 | psycopg2-binary, sqlalchemy |
| MongoDB | ✅ 支持 | pymongo |

---

## MySQL数据库接入

### 1. 安装依赖

```bash
pip install pymysql sqlalchemy
```

### 2. 数据库表结构

确保你的MySQL数据库中有以下表结构：

```sql
CREATE TABLE books (
    id INT AUTO_INCREMENT PRIMARY KEY,
    书名 VARCHAR(255),
    作者 VARCHAR(100),
    出版社 VARCHAR(100),
    出版年 INT,
    ISBN VARCHAR(20),
    URL VARCHAR(255),
    评分 DECIMAL(3,1),
    内容简介 TEXT,
    作者简介 TEXT,
    keywords TEXT  -- 新增字段，用于存储关键词
);
```

### 3. 配置数据库连接

```python
from extract_keywords import extract_keywords_from_database

# MySQL数据库配置
mysql_config = {
    'host': 'localhost',        # 数据库主机地址
    'port': 3306,               # 端口号
    'user': 'root',              # 用户名
    'password': 'your_password', # 密码
    'database': 'book_db',       # 数据库名
    'table': 'books'            # 表名
}

# 从MySQL提取关键词并保存回MySQL
df = extract_keywords_from_database(
    source_type='mysql',
    source_config=mysql_config,
    top_k=10
)
```

### 4. 完整示例

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySQL数据库关键词提取示例
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.extract_keywords import extract_keywords_from_database

def main():
    # MySQL数据库配置
    mysql_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'your_password',
        'database': 'book_db',
        'table': 'books'
    }
    
    try:
        # 从MySQL提取关键词
        print("开始从MySQL数据库提取关键词...")
        df = extract_keywords_from_database(
            source_type='mysql',
            source_config=mysql_config,
            top_k=10
        )
        
        print(f"成功处理 {len(df)} 本书")
        print("\n前5本书的关键词:")
        for i in range(min(5, len(df))):
            book_title = df.iloc[i]['书名']
            keywords = df.iloc[i]['keywords']
            print(f"{i+1}. {book_title}: {', '.join(keywords)}")
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

---

## PostgreSQL数据库接入

### 1. 安装依赖

```bash
pip install psycopg2-binary sqlalchemy
```

### 2. 数据库表结构

```sql
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    书名 VARCHAR(255),
    作者 VARCHAR(100),
    出版社 VARCHAR(100),
    出版年 INTEGER,
    ISBN VARCHAR(20),
    URL VARCHAR(255),
    评分 NUMERIC(3,1),
    内容简介 TEXT,
    作者简介 TEXT,
    keywords TEXT  -- 新增字段
);
```

### 3. 配置数据库连接

```python
from extract_keywords import extract_keywords_from_database

# PostgreSQL数据库配置
postgresql_config = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'your_password',
    'database': 'book_db',
    'table': 'books'
}

# 从PostgreSQL提取关键词
df = extract_keywords_from_database(
    source_type='postgresql',
    source_config=postgresql_config,
    top_k=10
)
```

### 4. 完整示例

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PostgreSQL数据库关键词提取示例
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.extract_keywords import extract_keywords_from_database

def main():
    # PostgreSQL数据库配置
    postgresql_config = {
        'host': 'localhost',
        'port': 5432,
        'user': 'postgres',
        'password': 'your_password',
        'database': 'book_db',
        'table': 'books'
    }
    
    try:
        print("开始从PostgreSQL数据库提取关键词...")
        df = extract_keywords_from_database(
            source_type='postgresql',
            source_config=postgresql_config,
            top_k=10
        )
        
        print(f"成功处理 {len(df)} 本书")
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

---

## MongoDB数据库接入

### 1. 安装依赖

```bash
pip install pymongo
```

### 2. 数据库集合结构

MongoDB使用文档结构，确保你的集合包含以下字段：

```json
{
    "_id": ObjectId("..."),
    "书名": "《雨时代》",
    "作者": "刘震云",
    "出版社": "新星出版社",
    "出版年": 2022,
    "ISBN": "978-7-33-21819-60",
    "URL": "https://book.douban.com/subject/1358b262/",
    "评分": 3.2,
    "内容简介": "这是一部关于爱情的长篇小说...",
    "作者简介": "刘震云，生于1970年...",
    "keywords": ["爱情", "长篇小说", "延津", "众生相", "温情", "知识分子", "刘震云", "深思"]
}
```

### 3. 配置数据库连接

```python
from extract_keywords import extract_keywords_from_database

# MongoDB数据库配置
mongodb_config = {
    'host': 'localhost',
    'port': 27017,
    'user': 'mongo_user',           # 可选，如果需要认证
    'password': 'mongo_password',   # 可选
    'database': 'book_db',
    'collection': 'books'
}

# 从MongoDB提取关键词
df = extract_keywords_from_database(
    source_type='mongodb',
    source_config=mongodb_config,
    top_k=10
)
```

### 4. 完整示例

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MongoDB数据库关键词提取示例
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.extract_keywords import extract_keywords_from_database

def main():
    # MongoDB数据库配置
    mongodb_config = {
        'host': 'localhost',
        'port': 27017,
        'user': None,              # 如果不需要认证，设置为None
        'password': None,
        'database': 'book_db',
        'collection': 'books'
    }
    
    try:
        print("开始从MongoDB数据库提取关键词...")
        df = extract_keywords_from_database(
            source_type='mongodb',
            source_config=mongodb_config,
            top_k=10
        )
        
        print(f"成功处理 {len(df)} 本书")
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

---

## 配置示例

### 1. 使用配置文件

创建 `config.py` 文件：

```python
# config.py

# MySQL配置
MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'your_password',
    'database': 'book_db',
    'table': 'books'
}

# PostgreSQL配置
POSTGRESQL_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'your_password',
    'database': 'book_db',
    'table': 'books'
}

# MongoDB配置
MONGODB_CONFIG = {
    'host': 'localhost',
    'port': 27017,
    'user': None,
    'password': None,
    'database': 'book_db',
    'collection': 'books'
}
```

### 2. 使用环境变量

```bash
# 设置环境变量
export DB_TYPE=mysql
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=your_password
export DB_NAME=book_db
export DB_TABLE=books
```

```python
import os
from extract_keywords import extract_keywords_from_database

# 从环境变量读取配置
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'book_db'),
    'table': os.getenv('DB_TABLE', 'books')
}

# 提取关键词
df = extract_keywords_from_database(
    source_type=os.getenv('DB_TYPE', 'mysql'),
    source_config=db_config,
    top_k=10
)
```

### 3. 跨数据库迁移

从MySQL提取关键词，保存到PostgreSQL：

```python
from extract_keywords import extract_keywords_from_database

# MySQL源配置
mysql_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'mysql_password',
    'database': 'book_db',
    'table': 'books'
}

# PostgreSQL目标配置
postgresql_config = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'postgres_password',
    'database': 'book_db',
    'table': 'books'
}

# 从MySQL提取，保存到PostgreSQL
df = extract_keywords_from_database(
    source_type='mysql',
    source_config=mysql_config,
    target_type='postgresql',
    target_config=postgresql_config,
    top_k=10
)
```

---

## 常见问题

### Q1: 如何处理数据库连接超时？

**A:** 可以在数据库配置中添加连接超时参数：

```python
# MySQL
mysql_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'password',
    'database': 'book_db',
    'table': 'books',
    'connect_timeout': 30  # 连接超时时间（秒）
}

# PostgreSQL
postgresql_config = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'password',
    'database': 'book_db',
    'table': 'books',
    'connect_timeout': 30
}
```

### Q2: 如何批量处理大量数据？

**A:** 系统已经支持批量处理，但可以通过以下方式优化：

```python
# 分批处理
def batch_process(config, batch_size=1000):
    offset = 0
    while True:
        query = f"SELECT * FROM books LIMIT {batch_size} OFFSET {offset}"
        # 处理当前批次
        # ...
        if len(current_batch) < batch_size:
            break
        offset += batch_size
```

### Q3: 如何处理数据库字段名不匹配？

**A:** 可以在SQL查询中使用别名：

```python
# 修改SQL查询以匹配字段名
query = """
SELECT 
    title as 书名,
    author as 作者,
    publisher as 出版社,
    publish_year as 出版年,
    isbn as ISBN,
    url as URL,
    rating as 评分,
    content_intro as 内容简介,
    author_intro as 作者简介
FROM books
"""
```

### Q4: 如何处理中文编码问题？

**A:** 确保数据库和连接使用UTF-8编码：

```python
# MySQL
mysql_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'password',
    'database': 'book_db',
    'table': 'books',
    'charset': 'utf8mb4'  # 使用utf8mb4编码
}

# PostgreSQL
postgresql_config = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'password',
    'database': 'book_db',
    'table': 'books',
    'client_encoding': 'utf8'
}
```

### Q5: 如何调试数据库连接问题？

**A:** 使用以下调试代码：

```python
import traceback

try:
    df = extract_keywords_from_database(
        source_type='mysql',
        source_config=mysql_config,
        top_k=10
    )
except Exception as e:
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {e}")
    print("\n详细错误信息:")
    traceback.print_exc()
```

### Q6: keywords字段如何存储？

**A:** 系统会将关键词列表转换为字符串存储：

```python
# 存储格式
keywords = ["爱情", "长篇小说", "延津", "众生相"]

# 在数据库中存储为字符串
"爱情,长篇小说,延津,众生相"

# 读取时自动转换回列表
df['keywords'] = df['keywords'].apply(lambda x: x.split(',') if isinstance(x, str) else x)
```

### Q7: 如何更新现有数据而不是覆盖？

**A:** 修改保存逻辑：

```python
from extract_keywords import BookDataSaver

saver = BookDataSaver(target_type='mysql', target_config=mysql_config)

# 更新现有记录
for idx, row in df.iterrows():
    update_query = f"""
    UPDATE books 
    SET keywords = '{','.join(row['keywords'])}' 
    WHERE id = {row['id']}
    """
    # 执行更新
    # ...
```

---

## 性能优化建议

### 1. 数据库索引

```sql
-- 为常用查询字段创建索引
CREATE INDEX idx_book_title ON books(书名);
CREATE INDEX idx_book_author ON books(作者);
CREATE INDEX idx_book_year ON books(出版年);
```

### 2. 连接池配置

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# 创建带连接池的引擎
engine = create_engine(
    'mysql+pymysql://user:password@localhost/db',
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=3600
)
```

### 3. 批量操作

```python
# 使用批量插入
df.to_sql('books', engine, if_exists='append', chunksize=1000)
```

---

## 安全建议

1. **不要在代码中硬编码密码**
   - 使用环境变量
   - 使用配置文件（不要提交到版本控制）
   - 使用密钥管理服务

2. **使用最小权限原则**
   - 为应用创建专用数据库用户
   - 只授予必要的权限

3. **加密敏感数据**
   - 使用SSL/TLS连接数据库
   - 加密存储的密码

---

## 总结

关键词提取系统已经完整支持多种数据源，只需修改配置即可轻松切换：

1. **CSV文件** → 使用 `extract_keywords_batch()`
2. **MySQL** → 使用 `extract_keywords_from_database(source_type='mysql')`
3. **PostgreSQL** → 使用 `extract_keywords_from_database(source_type='postgresql')`
4. **MongoDB** → 使用 `extract_keywords_from_database(source_type='mongodb')`

系统设计灵活，易于扩展，可以根据需要添加更多数据源支持。

---

## 联系方式

如有问题或建议，请联系开发团队或提交Issue。
