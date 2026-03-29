# 跨领域图书推荐系统 - 推荐算法模块

## 项目结构

```
crossdomain_book_recommend/
├── recommender/              # 推荐算法模块
│   ├── cross_domain_recommender.py  # 跨领域推荐核心算法
│   ├── multi_objective_ranker.py    # 多目标排序算法
│   └── README.md                    # 本文档
├── scripts/                  # 数据处理脚本
│   ├── generate_embeddings.py       # 生成嵌入向量
│   ├── extract_keywords.py          # 提取关键词
│   └── assign_domain_tags.py        # 分配领域标签
├── test/                     # 测试文件
└── requirements.txt          # 依赖包列表
```

## 推荐算法模块说明

### 1. CrossDomainRecommender 类

**功能**：计算图书之间的相似度并生成推荐

**核心方法**：
- `calculate_similarity(book_id_a, book_id_b)`: 计算两本书之间的综合相似度
- `get_recommendations(book_id, top_k=10)`: 为指定图书生成推荐
- `get_cross_domain_recommendations(book_id, top_k=10)`: 为指定图书生成跨领域推荐

**相似度计算逻辑**：
1. **关键词相似度**：
   - 平均向量相似度 Sim_avg(A,B)
   - 最大匹配相似度 Sim_max(A,B)
   - 加权融合：关键词相似度 = α⋅Sim_avg(A,B) + (1−α)⋅Sim_max(A,B) （α=0.4）

2. **语义相似度**：基于 BAAI/bge-base-zh-v1.5 模型生成的整体嵌入向量计算余弦相似度

3. **重叠标签系数**：
   - overlap = 0 → 系数 = 1（完全跨域）
   - overlap = 1 → 系数 = 1 - β
   - overlap = 2 → 系数 = 1 - 2β （β=0.25）

4. **综合得分**：
   - 综合相似度 = a×语义相似度 + (1-a)×关键词相似度 （a=0.6）
   - FinalScore = 综合相似度 × (1−β×重叠标签数)

### 2. MultiObjectiveRanker 类

**功能**：支持前端用户按不同维度动态排序推荐结果

**支持的排序模式**：
- **综合排序 (comprehensive)**：按 FinalScore 降序
- **评分排序 (rating)**：按豆瓣评分降序
- **最新排序 (newest)**：按出版日期降序

**缺失值处理**：
- rating 缺失：视为 0.0
- publication_date 缺失：视为 1900-01-01
- final_score 缺失：视为 0.0

**核心方法**：
- `sort_recommendations(recommendations, sort_mode='comprehensive')`: 对推荐结果进行排序
- `get_supported_sort_modes()`: 获取支持的排序模式列表
- `sort_with_filter(recommendations, sort_mode='comprehensive', min_rating=None, max_price=None)`: 带过滤条件的排序

## 与前端集成指南

### 1. 后端 API 设计建议

建议实现以下 API 端点：

#### 获取推荐
```
GET /api/recommendations/{book_id}?top_k=10&sort_mode=comprehensive
```

**参数**：
- `book_id`: 目标图书ID
- `top_k`: 返回推荐数量（默认10）
- `sort_mode`: 排序模式（comprehensive/rating/newest，默认comprehensive）

**返回**：
```json
{
  "status": "success",
  "data": {
    "book_id": 1,
    "title": "深度学习入门",
    "recommendations": [
      {
        "book_id": 2,
        "title": "Python编程从入门到精通",
        "final_score": 0.85,
        "rating": 4.5,
        "publication_date": "2023-01-15",
        "semantic_similarity": 0.78,
        "keyword_similarity": 0.92,
        "overlap_coefficient": 1.0
      },
      // 更多推荐...
    ]
  }
}
```

#### 获取跨领域推荐
```
GET /api/recommendations/{book_id}/cross-domain?top_k=10&sort_mode=comprehensive
```

**参数**：与上面相同

**返回**：与上面相同，但是只返回跨领域推荐

#### 获取支持的排序模式
```
GET /api/sort-modes
```

**返回**：
```json
{
  "status": "success",
  "data": [
    {
      "key": "comprehensive",
      "name": "综合排序",
      "description": "按综合得分排序，综合考虑语义相似度、关键词相似度和跨域系数"
    },
    {
      "key": "rating",
      "name": "评分排序",
      "description": "按豆瓣评分排序，高分书籍排在前面"
    },
    {
      "key": "newest",
      "name": "最新排序",
      "description": "按出版日期排序，新出版的书籍排在前面"
    }
  ]
}
```

### 2. 前端实现建议

1. **推荐展示页面**：
   - 显示目标图书信息
   - 展示推荐列表，支持切换排序模式
   - 提供跨领域推荐选项

2. **排序模式切换**：
   - 下拉菜单或标签切换
   - 切换时无需重新请求推荐，直接在前端使用 MultiObjectiveRanker 进行排序

3. **用户交互**：
   - 点击图书查看详情
   - 支持按评分、价格等过滤

### 3. 数据流

1. **初始化**：
   - 加载图书数据到 CrossDomainRecommender
   - 计算图书之间的相似度

2. **推荐流程**：
   - 前端请求推荐
   - 后端调用 `get_recommendations()` 或 `get_cross_domain_recommendations()`
   - 后端返回推荐结果
   - 前端根据用户选择的排序模式使用 MultiObjectiveRanker 进行排序

3. **动态排序**：
   - 用户切换排序模式
   - 前端使用 MultiObjectiveRanker 对已有的推荐结果进行重新排序
   - 无需重新请求后端，提升用户体验

## 依赖包

```
# requirements.txt
pandas
numpy
scikit-learn
sentence-transformers
gensim
jieba
sqlalchemy
pymysql
modelscope
```

## 测试

运行以下命令测试推荐功能：

```bash
python recommender/cross_domain_recommender.py
python recommender/multi_objective_ranker.py
```

## 注意事项

1. **性能优化**：
   - 对于大规模图书数据，建议使用缓存机制
   - 可以考虑使用向量数据库存储嵌入向量，提高相似度计算速度

2. **数据更新**：
   - 当图书数据更新时，需要重新生成嵌入向量
   - 建议定期运行 `generate_embeddings.py` 更新向量

3. **参数调优**：
   - α、a、β 等参数可以根据实际效果进行调整
   - 建议通过A/B测试找到最优参数

4. **前端集成**：
   - 前端需要处理可能的网络延迟
   - 建议实现加载状态和错误处理

5. **扩展性**：
   - 可以根据需要添加更多排序模式
   - 可以集成用户反馈，优化推荐算法
