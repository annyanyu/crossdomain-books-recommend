# 跨领域推荐算法优化设计 Spec

## Why

当前跨领域推荐算法采用"余弦相似度 + 重叠标签系数"的浅层匹配策略，存在以下核心问题：
1. **跨域关联发现能力弱**：仅依赖向量余弦相似度，无法发现不同领域书籍间通过中间书籍形成的隐性知识关联路径
2. **also_like共现数据未利用**：数据库中"喜欢这本书的人也喜欢"字段蕴含用户跨域兴趣迁移模式，当前完全闲置
3. **领域标签分配粗糙**：基于关键词计数的标签分配无法捕捉领域间的语义边界和交叉关系
4. **跨域推荐缺乏可解释性支撑**：推荐理由仅依赖LLM生成，缺乏基于知识图谱的结构化推理路径
5. **also_like数据存储设计不合理**：当前also_like以JSON数组形式冗余存储在books表中，既不利于关系查询，也不符合数据库范式

## What Changes

- 新增**独立also_like关系表（book_also_like）**：将"喜欢这本书的人也喜欢"数据从books表的JSON字段拆分为独立关系表，通过book_id建立外键关联
- 新增**书籍关联图构建模块**：基于also_like共现关系和语义相似度构建书籍关联图，实现图结构化的跨域关联表示
- 新增**图嵌入增强模块**：在现有BGE向量基础上，融合图结构信息（Node2Vec/GraphSAGE轻量方案），增强跨域关联发现能力
- 新增**also_like数据采集与处理模块**：扩展豆瓣爬虫抓取"喜欢这本书的人也喜欢"数据，写入独立关系表
- 新增**知识概念桥接模块**：基于关键词共现和领域标签关系构建领域间知识概念桥接图谱，提供跨域推荐的结构化解释路径
- 修改**跨域推荐核心算法**：在现有相似度计算框架中融入图嵌入相似度和共现关联度，优化最终得分公式
- 修改**领域标签系统**：从硬性关键词计数升级为基于图结构的领域关系感知标签系统
- 修改**推荐理由生成**：融合知识图谱推理路径，提供结构化的跨域推荐解释

## Impact

- Affected code:
  - `backend/app/services/recommender.py` — 核心推荐算法重构
  - `backend/app/services/douban_scraper.py` — 新增also_like数据抓取
  - `backend/app/services/book_processor.py` — 新增图嵌入处理步骤
  - `backend/app.py` — 新增图构建/更新API端点，修改新书入库逻辑
  - `backend/init_database.py` — 数据库表结构扩展（新增book_also_like表）
  - `algorithms/scripts/assign_domain_tags.py` — 标签系统升级
  - `algorithms/scripts/generate_embeddings.py` — 向量生成流程扩展
- 新增文件：
  - `backend/app/services/book_graph.py` — 书籍关联图构建与图嵌入
  - `backend/app/services/knowledge_bridge.py` — 知识概念桥接模块
  - `algorithms/scripts/build_book_graph.py` — 离线图构建脚本
  - `algorithms/scripts/generate_graph_embeddings.py` — 离线图嵌入生成脚本
  - `backend/migrate_add_also_like_table.py` — 数据库迁移脚本

## ADDED Requirements

### Requirement: also_like独立关系表（book_also_like）

系统SHALL创建独立的also_like关系表，将"喜欢这本书的人也喜欢"数据从books表的JSON字段拆分为规范化的关系表，通过book_id建立外键关联。

#### Scenario: 关系表结构设计
- **WHEN** 系统初始化数据库
- **THEN** 创建`book_also_like`表，结构如下：
  ```sql
  CREATE TABLE IF NOT EXISTS book_also_like (
      relation_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '关系ID',
      source_book_id INT NOT NULL COMMENT '源书籍ID（被喜欢的书）',
      target_book_id INT COMMENT '目标书籍ID（也被喜欢的书，匹配成功时非空）',
      target_book_name VARCHAR(255) NOT NULL COMMENT '目标书籍名称（豆瓣原始书名）',
      match_type ENUM('exact', 'fuzzy', 'unmatched') NOT NULL DEFAULT 'unmatched' COMMENT '匹配类型',
      match_score FLOAT DEFAULT 0.0 COMMENT '匹配得分（0.0~1.0，精确匹配为1.0）',
      weight FLOAT DEFAULT 1.0 COMMENT '关系权重（基于共现频率）',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
      UNIQUE KEY uk_source_target (source_book_id, target_book_name),
      INDEX idx_source_book (source_book_id),
      INDEX idx_target_book (target_book_id),
      INDEX idx_match_type (match_type),
      CONSTRAINT fk_also_like_source FOREIGN KEY (source_book_id) REFERENCES books(book_id) ON DELETE CASCADE,
      CONSTRAINT fk_also_like_target FOREIGN KEY (target_book_id) REFERENCES books(book_id) ON DELETE SET NULL
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='书籍共现关系表（喜欢这本书的人也喜欢）';
  ```

#### Scenario: 数据写入流程
- **WHEN** 豆瓣爬虫抓取到某书的also_like列表
- **THEN** 为列表中的每个书名创建一条`book_also_like`记录
- **AND** `source_book_id`为当前书籍的book_id
- **AND** `target_book_name`为豆瓣页面上的原始书名
- **AND** `target_book_id`初始为NULL，待后续匹配流程填充
- **AND** `match_type`初始为'unmatched'

#### Scenario: 书名匹配流程
- **WHEN** 执行also_like书名到book_id的映射
- **THEN** 系统依次尝试精确匹配和模糊匹配
- **AND** 精确匹配成功：`target_book_id`设为匹配到的book_id，`match_type`='exact'，`match_score`=1.0
- **AND** 模糊匹配成功：`target_book_id`设为匹配到的book_id，`match_type`='fuzzy'，`match_score`为相似度分数
- **AND** 均未匹配：`target_book_id`保持NULL，`match_type`='unmatched'，`match_score`=0.0

#### Scenario: books表also_like字段兼容
- **WHEN** books表中已有also_like JSON字段
- **THEN** 保留该字段不删除，用于向后兼容
- **AND** 新数据同时写入books.also_like和book_also_like表
- **AND** 推荐算法优先从book_also_like表读取数据

### Requirement: 书籍关联图构建

系统SHALL构建以书籍为节点、以共现关系和语义相似度为边的关联图，用于增强跨领域推荐能力。

#### Scenario: 基于book_also_like构建共现边
- **WHEN** book_also_like表中存在match_type为'exact'或'fuzzy'的记录
- **THEN** 系统为每条匹配成功的记录创建共现边（source_book_id ↔ target_book_id）
- **AND** 边权重 = weight × match_score

#### Scenario: 基于语义相似度构建隐式边
- **WHEN** 两本书的语义向量余弦相似度超过阈值（默认0.7）
- **THEN** 系统在两书之间创建语义相似边，边权重为余弦相似度值

#### Scenario: 图的增量更新
- **WHEN** 新书入库
- **THEN** 系统自动计算新书与已有书籍的关联关系，将新节点和边增量添加到图中

### Requirement: 图嵌入增强

系统SHALL在现有BGE语义向量基础上，融合图结构信息生成增强向量，提升跨域关联发现能力。

#### Scenario: 图嵌入向量生成
- **WHEN** 书籍关联图构建完成
- **THEN** 系统使用Node2Vec算法在图上生成128维图嵌入向量
- **AND** 将768维BGE向量与128维图嵌入向量拼接为896维增强向量
- **AND** 图嵌入向量存入books表新字段`graph_embedding`
- **AND** 增强向量存入books表新字段`enhanced_embedding`

#### Scenario: 图嵌入与语义向量的融合
- **WHEN** 计算两本书的相似度
- **THEN** 系统使用增强向量计算综合相似度，公式为：
  `EnhancedSim = w1 × Cosine(BGE_A, BGE_B) + w2 × Cosine(GraphEmb_A, GraphEmb_B)`
  默认 w1=0.7, w2=0.3

### Requirement: also_like数据采集与处理

系统SHALL扩展豆瓣爬虫以采集"喜欢这本书的人也喜欢"数据，并写入独立关系表。

#### Scenario: 豆瓣also_like数据抓取
- **WHEN** 爬取豆瓣书籍详情页
- **THEN** 系统解析页面中"喜欢这本书的人也喜欢"区域的书籍列表
- **AND** 将书籍名称列表同时写入books.also_like字段（兼容）和book_also_like表（规范化）

#### Scenario: also_like书名到book_id的映射
- **WHEN** book_also_like表中存在match_type='unmatched'的记录
- **THEN** 系统通过精确匹配和模糊匹配将target_book_name映射到books表中的book_id
- **AND** 匹配结果更新到target_book_id和match_type字段

### Requirement: 知识概念桥接模块

系统SHALL基于关键词共现和领域标签关系构建领域间知识概念桥接图谱，提供跨域推荐的结构化解释路径。

#### Scenario: 关键词共现桥接
- **WHEN** 两个不同领域的书籍共享关键词
- **THEN** 系统在知识桥接图中创建"领域A --共享关键词--> 领域B"的桥接路径
- **AND** 桥接强度 = 共享关键词数量 × 关键词权重

#### Scenario: 跨域推荐解释路径生成
- **WHEN** 用户请求跨域推荐理由
- **THEN** 系统从知识桥接图中提取源书领域到推荐书领域的桥接路径
- **AND** 将桥接路径中的共享关键词和中间概念作为推荐理由的结构化依据

### Requirement: 优化后的跨域推荐核心算法

系统SHALL在现有相似度计算框架中融入图嵌入相似度和共现关联度，优化最终得分公式。

#### Scenario: 增强版综合相似度计算
- **WHEN** 计算源书A与候选书B的推荐得分
- **THEN** 系统按以下公式计算：
  ```
  SemanticSim = Cosine(BGE_A, BGE_B)                    // 原有语义相似度
  KeywordSim = α × Sim_avg + (1-α) × Sim_max           // 原有关键词相似度
  GraphSim = Cosine(GraphEmb_A, GraphEmb_B)             // 新增图嵌入相似度
  CoOccurSim = also_like关联度（从book_also_like表计算） // 新增共现关联度
  
  CombinedSim = a × SemanticSim + (1-a) × KeywordSim    // 原有综合相似度
  EnhancedSim = w1 × CombinedSim + w2 × GraphSim + w3 × CoOccurSim  // 增强相似度
  
  FinalScore = EnhancedSim × OverlapCoeff               // 最终得分
  ```
  默认参数：a=0.6, α=0.4, w1=0.5, w2=0.3, w3=0.2

#### Scenario: also_like共现关联度计算（基于book_also_like表）
- **WHEN** 源书A和候选书B之间存在also_like关联
- **THEN** CoOccurSim从book_also_like表按以下规则计算：
  - book_also_like中存在(A→B)的记录且match_type!='unmatched' → CoOccurSim += 1.0 × match_score
  - book_also_like中存在(B→A)的记录且match_type!='unmatched' → CoOccurSim += 0.8 × match_score
  - A和B在book_also_like表中有共同的target_book_id（Jaccard系数）→ CoOccurSim += Jaccard(A.targets, B.targets)
  - 最终CoOccurSim = min(CoOccurSim, 1.0)（截断到[0,1]）
  - 无任何also_like关联 → CoOccurSim = 0.0

#### Scenario: 降级兼容
- **WHEN** 图嵌入或also_like数据不可用（book_also_like表为空或graph_embedding为NULL）
- **THEN** 系统自动降级为原有算法（w2=0, w3=0），确保推荐服务不中断

### Requirement: 领域关系感知标签系统

系统SHALL升级领域标签系统，使其能够感知领域间的语义关系和交叉边界。

#### Scenario: 领域关系矩阵构建
- **WHEN** 系统初始化
- **THEN** 基于书籍的领域标签共现统计构建领域关系矩阵
- **AND** 计算领域间的关联强度（共现频率归一化）

#### Scenario: 跨域推荐中的领域距离感知
- **WHEN** 计算重叠标签系数
- **THEN** 系统不仅考虑重叠标签数量，还考虑领域间的语义距离
- **AND** 相邻领域（如计算机科学↔自然科学）的重叠惩罚低于远距离领域（如计算机科学↔文学）

## MODIFIED Requirements

### Requirement: 跨域推荐算法核心

原有公式：
```
FinalScore = CombinedSim × OverlapCoeff
CombinedSim = a × SemanticSim + (1-a) × KeywordSim
```

修改为：
```
FinalScore = EnhancedSim × OverlapCoeff
EnhancedSim = w1 × CombinedSim + w2 × GraphSim + w3 × CoOccurSim
CombinedSim = a × SemanticSim + (1-a) × KeywordSim
```

新增参数（配置于config.json）：
| 参数 | 默认值 | 含义 |
|------|--------|------|
| w1 | 0.5 | 原有综合相似度权重 |
| w2 | 0.3 | 图嵌入相似度权重 |
| w3 | 0.2 | 共现关联度权重 |
| graph_sim_threshold | 0.7 | 语义相似度建边阈值 |
| node2vec_walk_length | 30 | Node2Vec随机游走长度 |
| node2vec_num_walks | 10 | Node2Vec每个节点游走次数 |
| node2vec_embedding_dim | 128 | 图嵌入维度 |

### Requirement: 豆瓣爬虫数据采集

原有：also_like字段硬编码为空列表`[]`

修改为：解析豆瓣页面"喜欢这本书的人也喜欢"区域，提取关联书名列表，同时写入books.also_like和book_also_like表

### Requirement: 数据库表结构

**表A（books）新增字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| graph_embedding | JSON | 128维图嵌入向量 |
| enhanced_embedding | JSON | 896维增强向量（768 BGE + 128 GraphEmb） |

**表B（book_also_like）新建表：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| relation_id | INT AUTO_INCREMENT PK | 关系ID |
| source_book_id | INT NOT NULL FK | 源书籍ID |
| target_book_id | INT FK | 目标书籍ID（匹配成功时非空） |
| target_book_name | VARCHAR(255) NOT NULL | 目标书籍名称（豆瓣原始书名） |
| match_type | ENUM('exact','fuzzy','unmatched') | 匹配类型 |
| match_score | FLOAT | 匹配得分（0.0~1.0） |
| weight | FLOAT | 关系权重 |
| created_at | TIMESTAMP | 创建时间 |

索引：uk_source_target(source_book_id, target_book_name)、idx_source_book(source_book_id)、idx_target_book(target_book_id)、idx_match_type(match_type)

外键：fk_also_like_source → books(book_id) ON DELETE CASCADE、fk_also_like_target → books(book_id) ON DELETE SET NULL

**books表保留字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| also_like | JSON | 保留原字段，向后兼容，新数据仍会同步写入 |

## REMOVED Requirements

无移除需求。所有现有功能保持向后兼容，新增模块为可选增强。
