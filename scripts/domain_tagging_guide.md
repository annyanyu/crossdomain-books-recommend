# 图书领域标签自动标注系统使用指南

## 目录

1. [系统概述](#系统概述)
2. [核心规则](#核心规则)
3. [快速开始](#快速开始)
4. [详细使用说明](#详细使用说明)
5. [数据库接入指南](#数据库接入指南)
6. [常见问题解答](#常见问题解答)

---

## 系统概述

本系统用于为图书自动分配领域标签，基于关键词匹配算法，能够识别图书所属的学术或专业领域。

### 主要功能

- 支持从CSV文件和数据库读取图书数据
- 基于关键词匹配自动分配领域标签
- 每本书最多分配2个领域标签
- 支持批量处理和单本书处理
- 提供领域标签统计功能

### 支持的领域

系统支持以下10个领域：

1. 计算机科学
2. 心理学
3. 经济学
4. 历史文化
5. 哲学
6. 文学
7. 艺术
8. 自然科学
9. 社会科学
10. 生活健康

---

## 核心规则

### 输入规则

- **数据来源**：CSV文件或数据库（MySQL/PostgreSQL/MongoDB）
- **必需字段**：
  - `书名`：图书的标题
  - `内容简介`：图书的内容介绍
  - `作者简介`：作者的背景介绍
- **文本处理**：将书名、内容简介、作者简介合并为单一文本字符串

### 输出规则

- **输出字段**：`domain_tags`（领域标签列表）
- **标签数量**：最多2个
- **排序方式**：按匹配分数降序排序
- **默认标签**：无匹配时返回 `["其他"]`

### 匹配分数计算

1. **文本预处理**：
   - 去除标点符号和特殊字符
   - 保留中文、英文、数字
   - 转换为小写

2. **关键词匹配**：
   - 统计每个领域的关键词在文本中的出现次数
   - 领域分数 = 所有关键词出现次数总和

3. **标签选取**：
   - 按分数降序排序所有领域
   - 选择分数 > 0 的前1-2个领域
   - 全部为0则返回 `["其他"]`

### 示例

**输入**：
```
书名: Python编程从入门到实践
内容简介: 本书详细介绍了Python编程语言的基础知识和高级应用，包括数据结构、算法设计、面向对象编程等内容。
作者简介: 作者是一名资深的软件工程师，拥有10年以上的编程经验。
```

**处理过程**：
1. 合并文本：`"Python编程从入门到实践 本书详细介绍了Python编程语言的基础知识和高级应用，包括数据结构、算法设计、面向对象编程等内容。 作者是一名资深的软件工程师，拥有10年以上的编程经验。"`
2. 预处理：去除标点符号，转换为小写
3. 匹配关键词：
   - 计算机科学关键词：`python`、`编程`、`数据结构`、`算法`、`软件` 等
   - 匹配次数：假设匹配了5次
4. 计算分数：
   - 计算机科学：5分
   - 其他领域：0分
5. 选取标签：`["计算机科学"]`

**输出**：
```
domain_tags: ["计算机科学"]
```

---

## 快速开始

### 安装依赖

```bash
pip install pandas numpy
```

### 基本使用

#### 1. 从CSV文件分配领域标签

```python
from assign_domain_tags import assign_domain_tags_batch

# 批量分配领域标签
df = assign_domain_tags_batch(
    csv_path='../test/books_test.csv',
    output_path='../test/books_test_with_domain_tags.csv',
    max_domains=2
)
```

#### 2. 单本书分配领域标签

```python
from assign_domain_tags import DomainTagAssigner

# 初始化分配器
assigner = DomainTagAssigner()

# 为单本书分配标签
domain_tags = assigner.assign_domain_tags(
    title='Python编程从入门到实践',
    content_intro='本书详细介绍了Python编程语言的基础知识和高级应用...',
    author_intro='作者是一名资深的软件工程师...',
    max_domains=2
)

print(domain_tags)  # 输出: ['计算机科学']
```

#### 3. 运行测试

```bash
cd scripts
python test_domain_tags.py
```

---

## 详细使用说明

### DomainTagAssigner 类

#### 初始化

```python
assigner = DomainTagAssigner(domain_config_path=None)
```

**参数**：
- `domain_config_path`（可选）：领域标签配置文件路径，默认为 `scripts/domain_tags.json`

#### 方法

##### 1. assign_domain_tags()

为单本书分配领域标签。

```python
domain_tags = assigner.assign_domain_tags(
    title='书名',
    content_intro='内容简介',
    author_intro='作者简介',
    max_domains=2
)
```

**参数**：
- `title`：书名
- `content_intro`：内容简介
- `author_intro`：作者简介
- `max_domains`：最多分配的领域标签数量，默认为2

**返回**：
- 领域标签列表，按匹配分数降序排序

##### 2. assign_domain_tags_batch()

批量为图书分配领域标签。

```python
df = assigner.assign_domain_tags_batch(
    df=book_dataframe,
    max_domains=2
)
```

**参数**：
- `df`：图书数据DataFrame，必须包含 `书名`、`内容简介`、`作者简介` 列
- `max_domains`：每本书最多分配的领域标签数量，默认为2

**返回**：
- 添加了 `domain_tags` 列的DataFrame

##### 3. get_domain_statistics()

统计领域标签分布情况。

```python
domain_stats = assigner.get_domain_statistics(df)
```

**参数**：
- `df`：包含 `domain_tags` 列的DataFrame

**返回**：
- 领域统计信息字典，格式为：
  ```python
  {
      '领域名称': {
          'count': 出现次数,
          'percentage': 百分比
      },
      ...
  }
  ```

### 主函数

#### assign_domain_tags_batch()

从CSV文件批量分配领域标签。

```python
df = assign_domain_tags_batch(
    csv_path='../test/books_test.csv',
    output_path='../test/books_test_with_domain_tags.csv',
    max_domains=2,
    domain_config_path=None
)
```

**参数**：
- `csv_path`：输入CSV文件路径
- `output_path`：输出CSV文件路径（如果为None，则覆盖原文件）
- `max_domains`：每本书最多分配的领域标签数量，默认为2
- `domain_config_path`：领域标签配置文件路径

**返回**：
- 包含领域标签的DataFrame

#### assign_domain_tags_from_database()

从数据库批量分配领域标签。

```python
df = assign_domain_tags_from_database(
    source_type='mysql',
    source_config={
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'password',
        'database': 'book_db',
        'table': 'books'
    },
    target_type=None,
    target_config=None,
    max_domains=2,
    domain_config_path=None
)
```

**参数**：
- `source_type`：数据源类型（'mysql'、'postgresql'、'mongodb'）
- `source_config`：数据源配置字典
- `target_type`：目标类型（如果为None，则与source_type相同）
- `target_config`：目标配置字典（如果为None，则与source_config相同）
- `max_domains`：每本书最多分配的领域标签数量，默认为2
- `domain_config_path`：领域标签配置文件路径

**返回**：
- 包含领域标签的DataFrame

---

## 数据库接入指南

### MySQL

#### 安装依赖

```bash
pip install pymysql sqlalchemy
```

#### 配置示例

```python
from assign_domain_tags import assign_domain_tags_from_database

# MySQL配置
source_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'your_password',
    'database': 'book_db',
    'table': 'books'
}

# 从MySQL分配领域标签并保存回MySQL
df = assign_domain_tags_from_database(
    source_type='mysql',
    source_config=source_config,
    max_domains=2
)
```

#### 数据库表结构要求

```sql
CREATE TABLE books (
    id INT PRIMARY KEY AUTO_INCREMENT,
    书名 VARCHAR(255),
    作者 VARCHAR(255),
    出版社 VARCHAR(255),
    出版年 VARCHAR(10),
    ISBN VARCHAR(20),
    URL VARCHAR(500),
    评分 VARCHAR(10),
    内容简介 TEXT,
    作者简介 TEXT
);
```

### PostgreSQL

#### 安装依赖

```bash
pip install psycopg2-binary sqlalchemy
```

#### 配置示例

```python
from assign_domain_tags import assign_domain_tags_from_database

# PostgreSQL配置
source_config = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'your_password',
    'database': 'book_db',
    'table': 'books'
}

# 从PostgreSQL分配领域标签并保存回PostgreSQL
df = assign_domain_tags_from_database(
    source_type='postgresql',
    source_config=source_config,
    max_domains=2
)
```

### MongoDB

#### 安装依赖

```bash
pip install pymongo
```

#### 配置示例

```python
from assign_domain_tags import assign_domain_tags_from_database

# MongoDB配置
source_config = {
    'host': 'localhost',
    'port': 27017,
    'user': 'username',
    'password': 'password',
    'database': 'book_db',
    'collection': 'books'
}

# 从MongoDB分配领域标签并保存回MongoDB
df = assign_domain_tags_from_database(
    source_type='mongodb',
    source_config=source_config,
    max_domains=2
)
```

### 跨数据库操作

可以从一个数据库读取数据，处理完成后保存到另一个数据库：

```python
# 从MySQL读取，保存到PostgreSQL
source_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'mysql_password',
    'database': 'book_db',
    'table': 'books'
}

target_config = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'postgres_password',
    'database': 'book_db',
    'table': 'books'
}

df = assign_domain_tags_from_database(
    source_type='mysql',
    source_config=source_config,
    target_type='postgresql',
    target_config=target_config,
    max_domains=2
)
```

---

## 常见问题解答

### Q1: 如何提高领域标签的准确性？

**A**: 可以通过以下方式提高准确性：

1. **优化关键词列表**：编辑 `domain_tags.json`，添加更多相关关键词
2. **调整匹配策略**：修改 `_calculate_domain_score()` 方法，引入权重机制
3. **使用更复杂的算法**：可以结合TF-IDF或机器学习算法

### Q2: 为什么有些书被标记为"其他"？

**A**: 可能的原因：

1. 书的文本中没有包含任何领域的关键词
2. 关键词列表不够完善，需要补充
3. 书的内容确实不属于任何预定义的领域

### Q3: 如何添加新的领域？

**A**: 编辑 `domain_tags.json` 文件，添加新的领域配置：

```json
{
    "domain": "新领域名称",
    "keywords": [
        "关键词1",
        "关键词2",
        "关键词3"
    ]
}
```

### Q4: 如何调整每本书的标签数量？

**A**: 修改 `max_domains` 参数：

```python
# 每本书最多3个标签
df = assign_domain_tags_batch(
    csv_path='../test/books_test.csv',
    max_domains=3
)
```

### Q5: 如何处理大型数据集？

**A**: 对于大型数据集，建议：

1. 使用数据库而不是CSV文件
2. 分批处理数据
3. 使用更高效的数据处理库（如Dask）

### Q6: 系统支持哪些编码格式？

**A**: 系统使用UTF-8编码，支持中文、英文等多种语言。CSV文件建议使用 `utf-8-sig` 编码。

### Q7: 如何查看每本书的匹配分数？

**A**: 可以修改代码以输出详细分数信息：

```python
# 在DomainTagAssigner类中添加方法
def get_domain_scores(self, title, content_intro, author_intro):
    combined_text = f"{title} {content_intro} {author_intro}"
    processed_text = self._preprocess_text(combined_text)
    
    scores = {}
    for domain_name, keywords in self.domain_keywords.items():
        score = self._calculate_domain_score(processed_text, keywords)
        scores[domain_name] = score
    
    return scores

# 使用示例
assigner = DomainTagAssigner()
scores = assigner.get_domain_scores('书名', '内容简介', '作者简介')
print(scores)
```

### Q8: 如何与关键词提取系统集成？

**A**: 可以先提取关键词，再分配领域标签：

```python
from extract_keywords import KeywordExtractor
from assign_domain_tags import DomainTagAssigner

# 提取关键词
keyword_extractor = KeywordExtractor()
keywords = keyword_extractor.extract_keywords_for_book(
    content_intro='内容简介',
    author_intro='作者简介',
    top_k=10
)

# 分配领域标签
domain_assigner = DomainTagAssigner()
domain_tags = domain_assigner.assign_domain_tags(
    title='书名',
    content_intro='内容简介',
    author_intro='作者简介',
    max_domains=2
)

print(f"关键词: {keywords}")
print(f"领域标签: {domain_tags}")
```

### Q9: 系统的性能如何？

**A**: 性能取决于：

- 数据集大小
- 关键词数量
- 文本长度

一般来说，处理1000本书大约需要几秒钟。对于更大的数据集，建议使用数据库并考虑分批处理。

### Q10: 如何处理缺失的数据？

**A**: 系统会自动处理缺失的数据：

- `NaN` 值会被转换为空字符串
- 空文本会导致返回 `["其他"]`
- 建议在处理前清理数据，填充缺失值

---

## 技术支持

如有问题或建议，请联系开发团队。
