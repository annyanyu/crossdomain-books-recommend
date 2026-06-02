# 基于迁移学习（领域自适应）的跨领域推荐算法优化 Spec

## Why

当前跨领域推荐算法采用"余弦相似度 + 重叠标签系数"的浅层匹配策略，核心问题在于：BGE预训练模型虽然将所有书籍映射到同一768维向量空间，但不同领域书籍的向量分布存在系统性偏移——计算机书的向量聚集在一个区域，心理学书聚集在另一个区域，直接计算余弦相似度会系统性地低估跨域书籍间的语义关联。迁移学习（特别是领域自适应Domain Adaptation）通过学习领域间的向量对齐映射，消除这种分布偏移，使跨域比较在同一尺度下进行，从根本上解决"量尺不准"的问题。此外，迁移学习不依赖also_like图结构数据，在数据稀疏场景下仍能有效工作。

## 技术路线图

```
阶段1: 数据基础设施 ────────────────────────────────────────
  [1.1] 豆瓣also_like数据采集 ──→ [1.2] book_also_like关系表 ──→ [1.3] 书名→book_id映射
         │                              │                              │
         └──────────────────────────────┴──────────────────────────────┘
                                        ↓
阶段2: 领域偏移分析与CORAL对齐（青椒云GPU） ─────────────────
  [2.1] 领域偏移分析 ──→ [2.2] CORAL投影矩阵训练 ──→ [2.3] 对齐向量生成
         │                      │                          │
         │                      │                          ↓
         │                      │               [2.4] 对齐向量写入数据库
         │                      │
         └──────────────────────┴─────────────────────────────────────
                                        ↓
阶段3: 对比学习增强（青椒云GPU） ───────────────────────────
  [3.1] 跨域正负样本对构建 ──→ [3.2] InfoNCE训练 ──→ [3.3] 融合向量生成
         │                          │                       │
         │                          │                       ↓
         │                          │              [3.4] 融合向量写入数据库
         │                          │
         └──────────────────────────┴─────────────────────────────────
                                        ↓
阶段4: 推荐算法集成 ────────────────────────────────────────
  [4.1] 对齐向量加载 ──→ [4.2] 知识桥接模块 ──→ [4.3] 增强相似度公式
         │                    │                       │
         │                    │                       ↓
         │                    │              [4.4] 领域距离感知
         │                    │                       │
         └────────────────────┴───────────────────────┘
                                        ↓
阶段5: 验证与部署 ──────────────────────────────────────────
  [5.1] 离线评估 ──→ [5.2] 降级兼容验证 ──→ [5.3] 推荐理由增强
```

## What Changes

- 新增**book_also_like独立关系表**：将"喜欢这本书的人也喜欢"数据从books表JSON字段拆分为独立关系表
- 新增**豆瓣also_like数据采集**：扩展爬虫抓取"喜欢这本书的人也喜欢"区域数据
- 新增**领域自适应对齐模块**：学习各领域到统一向量空间的线性投影矩阵，消除领域间向量分布偏移
- 新增**对比学习跨域对齐模块**：利用also_like共现关系构建跨域正样本对，通过对比学习拉近跨域关联书籍的向量
- 新增**知识概念桥接模块**：基于关键词共现构建领域间桥接图谱，提供跨域推荐解释路径
- 修改**跨域推荐核心算法**：在现有相似度计算框架中融入对齐后语义相似度和共现关联度
- 修改**推荐理由生成**：融合知识图谱推理路径，提供结构化的跨域推荐解释

## Impact

- Affected code:
  - `backend/app/services/recommender.py` — 核心推荐算法重构
  - `backend/app/services/douban_scraper.py` — 新增also_like数据抓取
  - `backend/app/services/book_processor.py` — 新增领域对齐处理步骤
  - `backend/app.py` — 新增对齐模型加载/更新API端点，修改新书入库逻辑
  - `backend/init_database.py` — 数据库表结构扩展（新增book_also_like表）
- 新增文件：
  - `backend/app/services/domain_aligner.py` — 领域自适应对齐模块
  - `backend/app/services/knowledge_bridge.py` — 知识概念桥接模块
  - `algorithms/scripts/analyze_domain_shift.py` — 领域偏移分析脚本
  - `algorithms/scripts/train_domain_aligner.py` — 领域对齐模型训练脚本（青椒云GPU）
  - `algorithms/scripts/train_contrastive_aligner.py` — 对比学习对齐训练脚本（青椒云GPU）
  - `backend/migrate_add_also_like_table.py` — 数据库迁移脚本

## 模型架构设计

### 整体架构：两阶段对齐

```
阶段1: CORAL线性对齐（消除分布偏移）
  ┌─────────────────────────────────────────────────────────┐
  │  输入: BGE向量 X_domain (N_domain × 768)                │
  │                                                         │
  │  步骤1: 计算源域协方差 C_s = X_s^T X_s / n_s           │
  │  步骤2: 计算目标域协方差 C_t = X_t^T X_t / n_t         │
  │  步骤3: 特征分解 C_s = U_s Σ_s U_s^T                   │
  │  步骤4: 特征分解 C_t = U_t Σ_t U_t^T                   │
  │  步骤5: 投影矩阵 A = U_s Σ_s^(-1/2) Σ_t^(1/2) U_t^T   │
  │                                                         │
  │  输出: 对齐向量 X_aligned = X_domain × A (N × 768)     │
  └─────────────────────────────────────────────────────────┘
                              ↓
阶段2: 对比学习微调（拉近跨域关联）
  ┌─────────────────────────────────────────────────────────┐
  │  输入: 对齐向量 X_aligned (N × 768)                     │
  │                                                         │
  │  投影网络 (2层MLP):                                      │
  │    Layer1: Linear(768→256) + LayerNorm + ReLU           │
  │    Layer2: Linear(256→768)                              │
  │                                                         │
  │  训练样本:                                               │
  │    正样本对: also_like跨域关联书 (源书, also_like跨域书)  │
  │    负样本对: 同领域随机采样书                             │
  │    难负样本: 不同领域但无also_like关联的书                │
  │                                                         │
  │  损失函数: InfoNCE                                       │
  │    L = -log(exp(sim(z_i,z_j)/τ) / Σ_k exp(sim(z_i,z_k)/τ)) │
  │    τ=0.07（温度参数）                                    │
  │                                                         │
  │  输出: 对比学习嵌入 X_contrastive (N × 768)             │
  └─────────────────────────────────────────────────────────┘
                              ↓
融合输出:
  ┌─────────────────────────────────────────────────────────┐
  │  final_embedding = λ × aligned + (1-λ) × contrastive   │
  │  λ = 0.7（线性投影为主，对比学习为辅）                    │
  └─────────────────────────────────────────────────────────┘
```

**设计选择说明**：
- **CORAL而非MMD/对抗训练**：CORAL是闭式解（无需迭代训练），计算高效，适合321本小数据集；MMD需要核函数选择，对抗训练需要额外判别器网络，增加过拟合风险
- **以"综合领域"为目标域**：将各专业领域对齐到所有书籍的混合分布，避免选择特定领域作为锚点带来的偏差
- **2层MLP对比学习**：参数量约20万，轻量级，CPU即可训练；对比学习作为CORAL的补充增强，而非替代
- **λ=0.7融合比例**：CORAL线性对齐提供全局分布校正（主），对比学习提供局部关联增强（辅）

## 数据预处理流程

```
步骤1: also_like数据采集
  豆瓣爬虫 → 解析"喜欢这本书的人也喜欢" → 写入book_also_like表
       ↓
步骤2: 书名映射
  book_also_like.target_book_name → 精确匹配/模糊匹配 → books.book_id
       ↓
步骤3: 领域偏移分析
  按domain_tags分组 → 计算各领域BGE向量质心 → 计算领域间余弦距离
  → 计算领域内散度 → 输出偏移报告
       ↓
步骤4: CORAL对齐训练（青椒云GPU）
  导出各领域BGE向量 → 计算协方差矩阵 → 特征分解 → 生成投影矩阵
  → 批量对齐 → 写入数据库aligned_embedding字段
       ↓
步骤5: 对比学习训练（青椒云GPU）
  从book_also_like表构建跨域正负样本对 → 训练2层MLP
  → 生成对比学习嵌入 → 与CORAL对齐向量融合 → 写入数据库final_embedding字段
       ↓
步骤6: 在线推理
  新书入库 → 根据领域标签选择投影矩阵 → 生成对齐向量
  → 通过对比学习MLP → 生成融合向量 → 写入数据库
```

## 青椒云GPU资源配置方案

### 环境配置

| 项目 | 规格 |
|------|------|
| GPU型号 | NVIDIA T4 / V100（推荐T4 16GB，对比学习需GPU加速） |
| 显存需求 | ≥4GB（MLP参数量约20万，321本书×768维） |
| 系统环境 | Ubuntu 20.04 + CUDA 11.8 + Python 3.10 |
| PyTorch | 2.0+ (CUDA 11.8) |

### 依赖安装

```bash
# 青椒云环境初始化
pip install torch==2.1.0+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
pip install numpy scikit-learn scipy
```

### 训练资源配置

| 资源 | CORAL对齐 | 对比学习 | 说明 |
|------|-----------|----------|------|
| GPU需求 | 可选（矩阵运算CPU也可） | 推荐（加速MLP训练） | CORAL是闭式解 |
| 显存占用 | <1GB | <2GB | MLP参数量约20万 |
| 训练时长 | <1分钟 | ~5分钟 | CORAL无迭代，对比学习50 epochs |
| 数据传输 | ~3MB | ~3MB | BGE向量embeddings.npy |
| 模型大小 | ~4.5MB/领域 | ~0.8MB | 投影矩阵768×768 vs MLP权重 |

### 训练与推理流程

```
[本地服务器]                              [青椒云GPU云电脑]
     │                                         │
     │── 1. 导出BGE向量+领域标签 ──→ 上传 ──→ 2. 解压 │
     │                                         │
     │                                 3. 运行analyze_domain_shift.py
     │                                    - 计算领域质心
     │                                    - 计算领域间距离
     │                                    - 输出偏移报告
     │                                         │
     │                                 4. 运行train_domain_aligner.py
     │                                    - CORAL对齐（闭式解）
     │                                    - 生成各领域投影矩阵
     │                                    - 批量对齐向量
     │                                    - 导出aligned_embeddings.npy
     │                                         │
     │── 5. 导入对齐向量 ←── 下载 ────────────── │
     │                                         │
     │── 6. 导出also_like+对齐向量 ──→ 上传 ──→ 7. 解压 │
     │                                         │
     │                                 8. 运行train_contrastive_aligner.py
     │                                    - 构建正负样本对
     │                                    - 训练2层MLP
     │                                    - 生成融合向量
     │                                    - 导出final_embeddings.npy
     │                                         │
     │── 9. 导入融合向量 ←── 下载 ────────────── 完成 │
     │                                         │
     │── 10. 重启推荐服务（CPU推理）             │
```

**关键点**：
- CORAL对齐是闭式解，无需GPU迭代训练，但GPU可加速矩阵运算
- 对比学习MLP训练推荐使用GPU加速，但CPU也可完成（约15分钟 vs 5分钟）
- 推理阶段直接从数据库读取预计算向量，无需GPU
- 两阶段可独立执行：仅CORAL对齐即可获得显著提升，对比学习为可选增强

## 性能评估指标

### 离线评估指标

| 指标 | 计算方式 | 目标 |
|------|----------|------|
| Hit Rate@10 | 推荐列表Top10中命中also_like关联书的比例 | ≥ 基线+12% |
| NDCG@10 | 推荐列表归一化折损累积增益 | ≥ 基线+8% |
| 跨域推荐覆盖率 | 被推荐的跨域书籍占全部跨域书籍的比例 | ≥ 基线+25% |
| 跨域推荐多样性 | 推荐列表中不同领域的数量 | ≥ 基线+1个领域 |
| 领域偏移消除度 | 对齐前后跨域相似度分布的KL散度变化 | 对齐后KL散度降低≥50% |
| 对齐质量 | 对齐后同领域书籍类内散度变化 | 散度增幅≤10%（不过度压缩） |

### 在线评估指标

| 指标 | 计算方式 | 目标 |
|------|----------|------|
| 推荐响应时间 | P95延迟 | ≤ 200ms（CPU推理） |
| 降级切换时间 | 对齐向量不可用时回退原算法的耗时 | ≤ 0ms（自动降级） |
| 新书对齐延迟 | 新书入库到对齐向量生成完成 | ≤ 500ms（单次矩阵乘法） |

### 评估方法

1. **基线**：当前算法 `FinalScore = CombinedSim × OverlapCoeff`
2. **实验组A**：仅CORAL对齐 `FinalScore = EnhancedSim × OverlapCoeff`（w2=0.2）
3. **实验组B**：CORAL+对比学习 `FinalScore = EnhancedSim × OverlapCoeff`（w2=0.2）
4. **数据集**：从book_also_like表中提取跨域关联对作为ground truth
5. **对比维度**：同域推荐质量、跨域推荐质量、推荐多样性、领域偏移消除效果
6. **消融实验**：分别评估CORAL单独贡献和对比学习增量贡献

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
     │  domain    │  │ knowledge  │  │ aligned/       │
     │ _aligner   │  │ _bridge.py │  │ final_embedding│
     │  .py       │  │ (知识桥接)  │  │ (数据库字段)    │
     │ (领域对齐) │  │            │  │ (预计算向量)    │
     └────────────┘  └────────────┘  └────────────────┘
```

### 集成原则

1. **非侵入式增强**：迁移学习模块作为可选增强层，不影响现有算法逻辑
2. **降级兼容**：aligned_embedding为NULL时自动回退为原算法（使用原始BGE向量，w2=0）
3. **离线训练+在线查表**：CORAL和对比学习训练在青椒云GPU离线执行，推理仅需读取数据库向量
4. **新书实时对齐**：新书入库时根据领域标签选择投影矩阵实时生成对齐向量（单次矩阵乘法，<1ms）
5. **渐进式部署**：可先仅启用CORAL对齐，验证效果后再叠加对比学习

### 新书入库流程变更

```
原流程: 爬取 → 关键词 → 领域标签 → BGE向量 → 入库
新流程: 爬取 → 关键词 → 领域标签 → BGE向量 → CORAL对齐 → 对比学习MLP → 入库
                                                  ↑              ↑
                                          投影矩阵查表     MLP前向推理
                                          (<1ms)          (<10ms, CPU)
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

#### Scenario: 数据写入与匹配流程
- **WHEN** 豆瓣爬虫抓取到某书的also_like列表
- **THEN** 为列表中的每个书名创建一条`book_also_like`记录
- **AND** 后续通过精确匹配和模糊匹配填充target_book_id

#### Scenario: books表also_like字段兼容
- **WHEN** books表中已有also_like JSON字段
- **THEN** 保留该字段不删除，新数据同时写入books.also_like和book_also_like表

### Requirement: 豆瓣also_like数据采集

系统SHALL扩展豆瓣爬虫以采集"喜欢这本书的人也喜欢"数据。

#### Scenario: 豆瓣also_like数据抓取
- **WHEN** 爬取豆瓣书籍详情页
- **THEN** 系统解析页面中"喜欢这本书的人也喜欢"区域的书籍列表
- **AND** 将书籍名称列表同时写入books.also_like字段和book_also_like表

### Requirement: 领域自适应对齐模块

系统SHALL学习各领域到统一向量空间的线性投影矩阵，消除不同领域书籍BGE向量间的分布偏移，使跨域比较在同一尺度下进行。

#### Scenario: 领域分布偏移分析
- **WHEN** 系统初始化
- **THEN** 系统分析各领域书籍BGE向量的分布特征：
  1. 计算每个领域向量的质心（centroid）
  2. 计算领域间质心的余弦距离（衡量领域偏移程度）
  3. 计算每个领域向量的类内散度（衡量领域内一致性）
  4. 输出领域偏移报告，识别偏移最严重的领域对

#### Scenario: 线性投影矩阵学习（CORAL方法）
- **WHEN** 执行领域对齐训练
- **THEN** 系统使用CORAL（Correlation Alignment）方法学习投影矩阵：
  ```
  目标：对齐源域和目标域的二阶统计量（协方差矩阵）
  
  步骤：
  1. 计算源域协方差矩阵 C_s 和目标域协方差矩阵 C_t
  2. 对 C_s 做特征分解：C_s = U_s Σ_s U_s^T
  3. 对 C_t 做特征分解：C_t = U_t Σ_t U_t^T
  4. 白化源域：X_s' = X_s U_s Σ_s^(-1/2)
  5. 重新着色到目标域：X_s'' = X_s' Σ_t^(1/2) U_t^T
  
  投影矩阵 A = U_s Σ_s^(-1/2) Σ_t^(1/2) U_t^T
  ```
- **AND** 以"综合领域"（所有书籍的混合分布）作为目标域，各专业领域对齐到综合域
- **AND** 每个领域学习一个768×768的投影矩阵

#### Scenario: 对齐后向量生成
- **WHEN** 需要计算跨域相似度
- **THEN** 系统将书籍的BGE向量通过其所属领域的投影矩阵变换：
  `aligned_embedding = A_domain × BGE_embedding`
- **AND** 对齐后的向量存入数据库新字段`aligned_embedding`

#### Scenario: 新书对齐处理
- **WHEN** 新书入库
- **THEN** 系统根据新书的领域标签，使用对应领域的投影矩阵生成对齐向量
- **AND** 若新书领域无对应投影矩阵，则对齐向量 = 原始BGE向量（不做变换）

### Requirement: 对比学习跨域对齐模块

系统SHALL利用also_like共现关系构建跨域正样本对，通过对比学习进一步拉近跨域关联书籍的向量，作为线性投影的补充增强。

#### Scenario: 跨域正负样本对构建
- **WHEN** book_also_like表中存在跨域关联（源书和目标书领域标签不同）
- **THEN** 系统构建训练样本：
  - 正样本对：(源书, also_like中的跨域目标书)，标签=1
  - 负样本对：(源书, 同领域随机采样书)，标签=0
  - 难负样本对：(源书, 不同领域但无also_like关联的书)，标签=0

#### Scenario: 对比学习训练
- **WHEN** 执行对比学习对齐训练
- **THEN** 系统使用InfoNCE损失函数训练投影网络：
  ```
  模型：2层MLP，768 → 256 → 768，带LayerNorm和ReLU
  损失：InfoNCE Loss
    L = -log(exp(sim(z_i, z_j)/τ) / Σ_k exp(sim(z_i, z_k)/τ))
    其中 τ=0.07（温度参数），sim为余弦相似度
  
  优化器：Adam
  学习率：1e-4
  学习率调度：CosineAnnealingLR，T_max=50
  权重衰减：1e-5
  训练轮数：50 epochs
  批次大小：64
  早停策略：验证集Loss连续10 epoch不降低则停止
  ```
- **AND** 训练推荐在GPU上执行（青椒云T4即可），CPU也可完成但较慢

#### Scenario: 对比学习嵌入融合
- **WHEN** 对比学习训练完成
- **THEN** 系统生成对比学习增强向量：
  `final_embedding = λ × aligned_embedding + (1-λ) × contrastive_embedding`
  默认 λ=0.7（线性投影为主，对比学习为辅）
- **AND** 融合向量存入数据库新字段`final_embedding`

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

### Requirement: 优化后的跨域推荐核心算法（迁移学习版）

系统SHALL在现有相似度计算框架中融入对齐后语义相似度和共现关联度，优化最终得分公式。

#### Scenario: 增强版综合相似度计算
- **WHEN** 计算源书A与候选书B的推荐得分
- **THEN** 系统按以下公式计算：
  ```
  AlignedSim = Cosine(Aligned_A, Aligned_B)              // 对齐后语义相似度
  KeywordSim = α × Sim_avg + (1-α) × Sim_max            // 原有关键词相似度
  CoOccurSim = also_like关联度（从book_also_like表计算）  // 共现关联度

  CombinedSim = a × AlignedSim + (1-a) × KeywordSim      // 综合相似度（用AlignedSim替代SemanticSim）
  EnhancedSim = w1 × CombinedSim + w2 × CoOccurSim       // 增强相似度

  FinalScore = EnhancedSim × OverlapCoeff                // 最终得分
  ```
  默认参数：a=0.6, α=0.4, w1=0.8, w2=0.2

#### Scenario: also_like共现关联度计算
- **WHEN** 源书A和候选书B之间存在also_like关联
- **THEN** CoOccurSim从book_also_like表按以下规则计算：
  - 存在(A→B)且match_type!='unmatched' → CoOccurSim += 1.0 × match_score
  - 存在(B→A)且match_type!='unmatched' → CoOccurSim += 0.8 × match_score
  - A和B有共同的target_book_id（Jaccard系数）→ CoOccurSim += Jaccard
  - 最终CoOccurSim = min(CoOccurSim, 1.0)
  - 无任何关联 → CoOccurSim = 0.0

#### Scenario: 降级兼容
- **WHEN** 对齐向量或also_like数据不可用
- **THEN** 系统自动降级为原有算法（使用原始BGE向量，w2=0），确保推荐服务不中断

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
EnhancedSim = w1 × CombinedSim + w2 × CoOccurSim
CombinedSim = a × AlignedSim + (1-a) × KeywordSim
AlignedSim = Cosine(Aligned_A, Aligned_B)
```

核心变化：用对齐后的语义相似度AlignedSim替代原始SemanticSim，解决"量尺不准"问题。

新增参数（配置于config.json）：
| 参数 | 默认值 | 含义 |
|------|--------|------|
| w1 | 0.8 | 综合相似度权重 |
| w2 | 0.2 | 共现关联度权重 |
| coral_target | 'union' | CORAL目标域（'union'=综合域） |
| contrastive_lambda | 0.7 | 线性投影与对比学习融合比例 |
| contrastive_temperature | 0.07 | InfoNCE温度参数 |
| contrastive_lr | 1e-4 | 对比学习学习率 |
| contrastive_epochs | 50 | 对比学习训练轮数 |
| contrastive_batch_size | 64 | 对比学习批次大小 |
| contrastive_patience | 10 | 对比学习早停耐心值 |

### Requirement: 豆瓣爬虫数据采集

原有：also_like字段硬编码为空列表`[]`

修改为：解析豆瓣页面"喜欢这本书的人也喜欢"区域，提取关联书名列表，同时写入books.also_like和book_also_like表

### Requirement: 数据库表结构

**表A（books）新增字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| aligned_embedding | JSON | 768维对齐后向量（CORAL投影后） |
| final_embedding | JSON | 768维融合向量（λ×对齐 + (1-λ)×对比学习） |

**表B（book_also_like）新建表**（结构见上方Requirement）

**新增配置文件：**
| 文件 | 说明 |
|------|------|
| `algorithms/models/domain_projections.json` | 各领域的768×768投影矩阵 |
| `algorithms/models/contrastive_model.pt` | 对比学习MLP模型权重 |

## REMOVED Requirements

无移除需求。所有现有功能保持向后兼容，新增模块为可选增强。
