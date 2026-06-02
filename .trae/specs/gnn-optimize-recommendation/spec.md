# 基于图神经网络（GNN）的跨领域推荐算法优化 Spec

## Why

当前跨领域推荐算法采用"余弦相似度 + 重叠标签系数"的浅层匹配策略，无法发现不同领域书籍间通过中间书籍形成的隐性知识关联路径。图神经网络（GNN）通过消息传递机制，让每个节点的表示融合其邻居的信息，能够建模also_like共现图中的高阶跨域关系，从而发现"源书A → 跨域桥接书C → 目标书B"这类隐性关联路径。用户可使用青椒云GPU云电脑进行GNN模型训练。

## 技术路线图

```
阶段1: 数据基础设施 ────────────────────────────────────────
  [1.1] 豆瓣also_like数据采集 ──→ [1.2] book_also_like关系表 ──→ [1.3] 书名→book_id映射
         │                              │                              │
         └──────────────────────────────┴──────────────────────────────┘
                                        ↓
阶段2: 图构建与GNN训练（青椒云GPU） ─────────────────────────
  [2.1] 书籍关联图构建 ──→ [2.2] 数据导出 ──→ [2.3] LightGCN训练（GPU）
         │                      │                    │
         │                      │                    ↓
         │                      │           [2.4] GNN嵌入导出 → 写入数据库
         │                      │
         └──────────────────────┴─────────────────────────────────────
                                        ↓
阶段3: 推荐算法集成 ────────────────────────────────────────
  [3.1] GNN嵌入加载 ──→ [3.2] 知识桥接模块 ──→ [3.3] 增强相似度公式
         │                    │                       │
         │                    │                       ↓
         │                    │              [3.4] 领域距离感知
         │                    │                       │
         └────────────────────┴───────────────────────┘
                                        ↓
阶段4: 验证与部署 ──────────────────────────────────────────
  [4.1] 离线评估 ──→ [4.2] 降级兼容验证 ──→ [4.3] 推荐理由增强
```

## What Changes

- 新增**book_also_like独立关系表**：将"喜欢这本书的人也喜欢"数据从books表JSON字段拆分为独立关系表
- 新增**豆瓣also_like数据采集**：扩展爬虫抓取"喜欢这本书的人也喜欢"区域数据
- 新增**书籍关联图构建模块**：基于also_like共现关系和语义相似度构建书籍关联图
- 新增**GNN模型训练模块**：使用LightGCN在书籍关联图上进行消息传递，生成融合图结构信息的节点嵌入
- 新增**知识概念桥接模块**：基于关键词共现构建领域间桥接图谱，提供跨域推荐解释路径
- 修改**跨域推荐核心算法**：在现有相似度计算框架中融入GNN嵌入相似度和共现关联度
- 修改**推荐理由生成**：融合知识图谱推理路径，提供结构化的跨域推荐解释

## Impact

- Affected code:
  - `backend/app/services/recommender.py` — 核心推荐算法重构
  - `backend/app/services/douban_scraper.py` — 新增also_like数据抓取
  - `backend/app/services/book_processor.py` — 新增GNN嵌入处理步骤
  - `backend/app.py` — 新增图构建/更新API端点，修改新书入库逻辑
  - `backend/init_database.py` — 数据库表结构扩展（新增book_also_like表）
- 新增文件：
  - `backend/app/services/book_graph.py` — 书籍关联图构建与图嵌入
  - `backend/app/services/knowledge_bridge.py` — 知识概念桥接模块
  - `algorithms/scripts/train_gnn_model.py` — GNN模型训练脚本（青椒云GPU环境）
  - `algorithms/scripts/generate_gnn_embeddings.py` — GNN嵌入推理脚本
  - `backend/migrate_add_also_like_table.py` — 数据库迁移脚本

## 模型架构设计

### LightGCN 模型架构

```
输入层:
  ┌─────────────────────────────────────────────────────────┐
  │  邻接矩阵 A (N×N)   — 书籍关联图（共现边+语义边）         │
  │  初始特征 E₀ (N×768) — BGE预训练向量                     │
  └─────────────────────────────────────────────────────────┘
                              ↓
消息传递层 (Layer 1):
  ┌─────────────────────────────────────────────────────────┐
  │  E₁ = D^(-1/2) · A · D^(-1/2) · E₀                    │
  │  （对称归一化邻接矩阵乘法，无特征变换，无非线性激活）       │
  └─────────────────────────────────────────────────────────┘
                              ↓
消息传递层 (Layer 2):
  ┌─────────────────────────────────────────────────────────┐
  │  E₂ = D^(-1/2) · A · D^(-1/2) · E₁                    │
  │  （2-hop邻居聚合，捕获跨域桥接路径）                       │
  └─────────────────────────────────────────────────────────┘
                              ↓
层聚合:
  ┌─────────────────────────────────────────────────────────┐
  │  E_final = α₀·E₀ + α₁·E₁ + α₂·E₂                     │
  │  （α₀=0.3, α₁=0.3, α₂=0.4，加权平均各层表示）            │
  └─────────────────────────────────────────────────────────┘
                              ↓
输出层:
  ┌─────────────────────────────────────────────────────────┐
  │  线性投影: E_out = W·E_final + b (768→128)              │
  │  输出: 每本书128维GNN嵌入向量                             │
  └─────────────────────────────────────────────────────────┘
```

**设计选择说明**：
- **LightGCN而非GCN/GAT**：去掉特征变换和非线性激活，仅保留邻居聚合，参数量极小（仅投影层约10万参数），不易过拟合，适合321本小规模数据集
- **2层消息传递**：2-hop邻居聚合足以捕获"源书→桥接书→目标书"的跨域路径，更深层次在小图上易过平滑
- **768→128投影**：从高维BGE空间压缩到低维GNN空间，减少存储和计算开销，同时保留图结构信息

## 数据预处理流程

```
步骤1: also_like数据采集
  豆瓣爬虫 → 解析"喜欢这本书的人也喜欢" → 写入book_also_like表
       ↓
步骤2: 书名映射
  book_also_like.target_book_name → 精确匹配/模糊匹配 → books.book_id
       ↓
步骤3: 图构建
  book_also_like(match_type∈{exact,fuzzy}) → 共现边（权重=weight×match_score）
  books.embedding → 语义相似度计算（阈值0.7） → 语义边
  合并 → 书籍关联图（邻接表格式）
       ↓
步骤4: 数据导出（青椒云上传）
  数据库 → 导出邻接表(adjacency.json) + BGE向量(embeddings.npy)
  打包为gnn_training_data.tar.gz
       ↓
步骤5: GNN训练（青椒云GPU）
  加载数据 → 构建PyG Data对象 → LightGCN训练 → 导出GNN嵌入
       ↓
步骤6: 嵌入导入
  GNN嵌入向量 → 写入books.gnn_embedding字段
```

## 青椒云GPU资源配置方案

### 环境配置

| 项目 | 规格 |
|------|------|
| GPU型号 | NVIDIA T4 / V100（推荐V100 16GB） |
| 显存需求 | ≥8GB（321本书×768维，LightGCN极轻量） |
| 系统环境 | Ubuntu 20.04 + CUDA 11.8 + Python 3.10 |
| PyTorch | 2.0+ (CUDA 11.8) |
| PyG | torch-geometric 2.4+ |

### 依赖安装

```bash
# 青椒云环境初始化
pip install torch==2.1.0+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
pip install torch-geometric torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-2.1.0+cu118.html
pip install numpy scikit-learn
```

### 训练资源配置

| 资源 | 配置 | 说明 |
|------|------|------|
| GPU显存 | <1GB | LightGCN参数量极小（~10万），321节点图极轻量 |
| 训练时长 | ~5分钟 | 200 epochs，321节点，T4即可 |
| 数据传输 | ~5MB | adjacency.json(~2MB) + embeddings.npy(~1MB) |
| 模型大小 | ~0.5MB | 仅投影层权重 |

### 训练与推理流程

```
[本地服务器]                         [青椒云GPU云电脑]
     │                                      │
     │── 1. 导出训练数据 ──→ 上传 ──→ 2. 解压 │
     │                                      │
     │                              3. 运行train_gnn_model.py
     │                                 - 加载数据
     │                                 - 构建PyG Data
     │                                 - LightGCN训练
     │                                 - 验证&保存最优模型
     │                                 - 导出GNN嵌入
     │                                      │
     │←── 4. 下载嵌入结果 ─────────────── 完成 │
     │                                      │
     │── 5. 导入数据库                       │
     │                                      │
     │── 6. 重启推荐服务（CPU推理）           │
```

**关键点**：GNN训练仅在青椒云GPU上执行，推理阶段直接从数据库读取预计算的gnn_embedding向量，无需GPU。

## 性能评估指标

### 离线评估指标

| 指标 | 计算方式 | 目标 |
|------|----------|------|
| Hit Rate@10 | 推荐列表Top10中命中also_like关联书的比例 | ≥ 基线+15% |
| NDCG@10 | 推荐列表归一化折损累积增益 | ≥ 基线+10% |
| 跨域推荐覆盖率 | 被推荐的跨域书籍占全部跨域书籍的比例 | ≥ 基线+20% |
| 跨域推荐多样性 | 推荐列表中不同领域的数量 | ≥ 基线+1个领域 |
| 隐性路径发现率 | 通过GNN发现的2-hop跨域关联占全部跨域推荐的比例 | ≥ 30% |

### 在线评估指标

| 指标 | 计算方式 | 目标 |
|------|----------|------|
| 推荐响应时间 | P95延迟 | ≤ 200ms（CPU推理） |
| 降级切换时间 | GNN不可用时回退原算法的耗时 | ≤ 0ms（自动降级） |

### 评估方法

1. **基线**：当前算法 `FinalScore = CombinedSim × OverlapCoeff`
2. **实验组**：GNN增强算法 `FinalScore = EnhancedSim × OverlapCoeff`
3. **数据集**：从book_also_like表中提取跨域关联对作为ground truth
4. **对比维度**：同域推荐质量、跨域推荐质量、推荐多样性

## 与现有系统的集成方案

### 集成架构

```
                    ┌─────────────────────────────────────┐
                    │         现有推荐系统                  │
                    │  recommender.py (核心算法)            │
                    │  book_processor.py (图书处理)         │
                    │  douban_scraper.py (数据采集)         │
                    └──────────┬──────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ↓                ↓                ↓
     ┌────────────┐  ┌────────────┐  ┌────────────────┐
     │ book_graph │  │ knowledge  │  │  gnn_embedding │
     │   .py      │  │ _bridge.py │  │  (数据库字段)   │
     │ (图构建)   │  │ (知识桥接)  │  │  (预计算向量)   │
     └────────────┘  └────────────┘  └────────────────┘
```

### 集成原则

1. **非侵入式增强**：GNN模块作为可选增强层，不影响现有算法逻辑
2. **降级兼容**：gnn_embedding为NULL时自动回退为原算法（w2=0, w3=0）
3. **离线训练+在线查表**：GNN训练在青椒云GPU离线执行，推理仅需读取数据库向量
4. **增量更新**：新书入库时使用1-hop邻居平均生成临时GNN嵌入，定期重训模型

### 新书入库流程变更

```
原流程: 爬取 → 关键词 → 领域标签 → BGE向量 → 入库
新流程: 爬取 → 关键词 → 领域标签 → BGE向量 → 临时GNN嵌入 → 入库
                                                  ↑
                                        1-hop邻居平均（无需GPU）
```

## ADDED Requirements

### Requirement: book_also_like独立关系表

系统SHALL创建独立的also_like关系表，将"喜欢这本书的人也喜欢"数据从books表的JSON字段拆分为规范化的关系表。

#### Scenario: 关系表结构设计
- **WHEN** 系统初始化数据库
- **THEN** 创建`book_also_like`表，结构如下：
  ```sql
  CREATE TABLE IF NOT EXISTS book_also_like (
      relation_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '关系ID',
      source_book_id INT NOT NULL COMMENT '源书籍ID',
      target_book_id INT COMMENT '目标书籍ID（匹配成功时非空）',
      target_book_name VARCHAR(255) NOT NULL COMMENT '目标书籍名称（豆瓣原始书名）',
      match_type ENUM('exact', 'fuzzy', 'unmatched') NOT NULL DEFAULT 'unmatched' COMMENT '匹配类型',
      match_score FLOAT DEFAULT 0.0 COMMENT '匹配得分（0.0~1.0）',
      weight FLOAT DEFAULT 1.0 COMMENT '关系权重',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
      UNIQUE KEY uk_source_target (source_book_id, target_book_name),
      INDEX idx_source_book (source_book_id),
      INDEX idx_target_book (target_book_id),
      INDEX idx_match_type (match_type),
      CONSTRAINT fk_also_like_source FOREIGN KEY (source_book_id) REFERENCES books(book_id) ON DELETE CASCADE,
      CONSTRAINT fk_also_like_target FOREIGN KEY (target_book_id) REFERENCES books(book_id) ON DELETE SET NULL
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
  ```

#### Scenario: 数据写入流程
- **WHEN** 豆瓣爬虫抓取到某书的also_like列表
- **THEN** 为列表中的每个书名创建一条`book_also_like`记录
- **AND** `target_book_id`初始为NULL，`match_type`初始为'unmatched'

#### Scenario: 书名匹配流程
- **WHEN** 执行also_like书名到book_id的映射
- **THEN** 精确匹配成功：`match_type`='exact'，`match_score`=1.0
- **AND** 模糊匹配成功：`match_type`='fuzzy'，`match_score`为相似度分数
- **AND** 均未匹配：`match_type`='unmatched'，`match_score`=0.0

#### Scenario: books表also_like字段兼容
- **WHEN** books表中已有also_like JSON字段
- **THEN** 保留该字段不删除，新数据同时写入books.also_like和book_also_like表

### Requirement: 豆瓣also_like数据采集

系统SHALL扩展豆瓣爬虫以采集"喜欢这本书的人也喜欢"数据。

#### Scenario: 豆瓣also_like数据抓取
- **WHEN** 爬取豆瓣书籍详情页
- **THEN** 系统解析页面中"喜欢这本书的人也喜欢"区域的书籍列表
- **AND** 将书籍名称列表同时写入books.also_like字段和book_also_like表

### Requirement: 书籍关联图构建

系统SHALL构建以书籍为节点、以共现关系和语义相似度为边的关联图。

#### Scenario: 基于book_also_like构建共现边
- **WHEN** book_also_like表中存在match_type为'exact'或'fuzzy'的记录
- **THEN** 系统为每条匹配成功的记录创建共现边
- **AND** 边权重 = weight × match_score

#### Scenario: 基于语义相似度构建隐式边
- **WHEN** 两本书的BGE语义向量余弦相似度超过阈值（默认0.7）
- **THEN** 系统在两书之间创建语义相似边，边权重为余弦相似度值

#### Scenario: 图的增量更新
- **WHEN** 新书入库
- **THEN** 系统自动计算新书与已有书籍的关联关系，将新节点和边增量添加到图中

### Requirement: GNN模型训练与嵌入生成

系统SHALL使用LightGCN在书籍关联图上进行消息传递，生成融合图结构信息的节点嵌入。GNN模型训练在青椒云GPU云电脑上执行，推理可在CPU上执行。

#### Scenario: LightGCN模型架构
- **WHEN** 启动GNN模型训练
- **THEN** 系统使用LightGCN架构，模型参数如下：
  ```
  输入：书籍关联图（邻接矩阵）+ 初始节点特征（768维BGE向量）
  层数：2层（2-hop邻居聚合）
  消息传递：E_l+1 = (D^(-1/2) A D^(-1/2)) E_l，无特征变换和非线性
  层聚合：E_final = α₀·E₀ + α₁·E₁ + α₂·E₂（α₀=0.3, α₁=0.3, α₂=0.4）
  输出投影：线性层 768→128
  输出：每本书的128维GNN嵌入向量
  ```
- **AND** LightGCN去掉特征变换和非线性激活，仅保留邻居聚合，参数量极小，不易过拟合

#### Scenario: 训练策略
- **WHEN** 在青椒云GPU云电脑上执行训练脚本
- **THEN** 训练参数和策略如下：
  ```
  损失函数：BPR Loss（推荐系统标准损失）
    L = -Σ ln σ(ŷ_pos - ŷ_neg) + λ||Θ||²
    其中 ŷ = e_u · e_i（用户/物品内积，此处简化为书籍对相似度）
  
  优化器：Adam
  学习率：0.01
  学习率调度：StepLR，每50 epoch衰减为0.5倍
  权重衰减：1e-5（L2正则化）
  训练轮数：200 epochs
  批次大小：256（书籍对）
  早停策略：验证集NDCG@10连续20 epoch不提升则停止
  ```

#### Scenario: 训练流程（青椒云GPU环境）
- **WHEN** 在青椒云GPU云电脑上执行训练脚本
- **THEN** 训练流程如下：
  1. 从数据库导出书籍关联图数据（邻接表 + BGE向量）
  2. 打包上传至青椒云（gnn_training_data.tar.gz）
  3. 在青椒云解压并构建PyTorch Geometric的Data对象
  4. 使用BPR损失函数训练LightGCN
  5. 每10个epoch验证一次，保存最优模型
  6. 导出所有节点的GNN嵌入向量
  7. 下载嵌入结果并导入数据库

#### Scenario: CPU推理模式
- **WHEN** 在本地CPU服务器上运行推荐服务
- **THEN** 系统直接从数据库读取预计算的GNN嵌入向量，无需实时推理
- **AND** 新书入库时，使用简化的1-hop邻居平均作为临时GNN嵌入（无需重训模型）

#### Scenario: GNN嵌入与BGE向量的融合
- **WHEN** 计算两本书的相似度
- **THEN** 系统使用融合公式：
  `EnhancedSim = w1 × Cosine(BGE_A, BGE_B) + w2 × Cosine(GNN_A, GNN_B)`
  默认 w1=0.6, w2=0.4

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

### Requirement: 优化后的跨域推荐核心算法（GNN版）

系统SHALL在现有相似度计算框架中融入GNN嵌入相似度和共现关联度，优化最终得分公式。

#### Scenario: 增强版综合相似度计算
- **WHEN** 计算源书A与候选书B的推荐得分
- **THEN** 系统按以下公式计算：
  ```
  SemanticSim = Cosine(BGE_A, BGE_B)                    // 原有语义相似度
  KeywordSim = α × Sim_avg + (1-α) × Sim_max           // 原有关键词相似度
  GNNSim = Cosine(GNN_A, GNN_B)                         // GNN嵌入相似度
  CoOccurSim = also_like关联度（从book_also_like表计算） // 共现关联度

  CombinedSim = a × SemanticSim + (1-a) × KeywordSim    // 原有综合相似度
  EnhancedSim = w1 × CombinedSim + w2 × GNNSim + w3 × CoOccurSim  // 增强相似度

  FinalScore = EnhancedSim × OverlapCoeff               // 最终得分
  ```
  默认参数：a=0.6, α=0.4, w1=0.4, w2=0.4, w3=0.2

#### Scenario: also_like共现关联度计算
- **WHEN** 源书A和候选书B之间存在also_like关联
- **THEN** CoOccurSim从book_also_like表按以下规则计算：
  - 存在(A→B)且match_type!='unmatched' → CoOccurSim += 1.0 × match_score
  - 存在(B→A)且match_type!='unmatched' → CoOccurSim += 0.8 × match_score
  - A和B有共同的target_book_id（Jaccard系数）→ CoOccurSim += Jaccard
  - 最终CoOccurSim = min(CoOccurSim, 1.0)
  - 无任何关联 → CoOccurSim = 0.0

#### Scenario: 降级兼容
- **WHEN** GNN嵌入或also_like数据不可用
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
- **AND** 相邻领域的重叠惩罚低于远距离领域

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
EnhancedSim = w1 × CombinedSim + w2 × GNNSim + w3 × CoOccurSim
CombinedSim = a × SemanticSim + (1-a) × KeywordSim
```

新增参数（配置于config.json）：
| 参数 | 默认值 | 含义 |
|------|--------|------|
| w1 | 0.4 | 原有综合相似度权重 |
| w2 | 0.4 | GNN嵌入相似度权重 |
| w3 | 0.2 | 共现关联度权重 |
| graph_sim_threshold | 0.7 | 语义相似度建边阈值 |
| gnn_embedding_dim | 128 | GNN嵌入维度 |
| gnn_n_layers | 2 | GNN消息传递层数 |
| gnn_lr | 0.01 | GNN训练学习率 |
| gnn_epochs | 200 | GNN训练轮数 |
| gnn_layer_weights | [0.3, 0.3, 0.4] | 各层聚合权重 |

### Requirement: 豆瓣爬虫数据采集

原有：also_like字段硬编码为空列表`[]`

修改为：解析豆瓣页面"喜欢这本书的人也喜欢"区域，提取关联书名列表，同时写入books.also_like和book_also_like表

### Requirement: 数据库表结构

**表A（books）新增字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| gnn_embedding | JSON | 128维GNN嵌入向量 |

**表B（book_also_like）新建表**（结构见上方Requirement）

## REMOVED Requirements

无移除需求。所有现有功能保持向后兼容，新增模块为可选增强。
