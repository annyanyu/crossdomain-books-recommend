# Tasks — 迁移学习优化方案

- [x] Task 1: 扩展豆瓣爬虫，采集also_like数据
  - [x] SubTask 1.1: 分析豆瓣书籍详情页HTML结构，定位"喜欢这本书的人也喜欢"区域的CSS选择器
  - [x] SubTask 1.2: 在douban_scraper.py中新增also_like解析逻辑，提取关联书名列表
  - [x] SubTask 1.3: 修改douban_scraper.py的_clean_data方法，将also_like从硬编码空列表改为实际解析结果
  - [x] SubTask 1.4: 在app.py的新书入库流程中，确保also_like数据同时写入books.also_like字段和book_also_like表

- [x] Task 2: 数据库表结构扩展（book_also_like关系表 + books新字段）
  - [x] SubTask 2.1: 在init_database.py中新增book_also_like表的CREATE TABLE语句（含外键约束和索引）
  - [x] SubTask 2.2: 在init_database.py中为books表新增aligned_embedding和final_embedding两个JSON字段
  - [x] SubTask 2.3: 编写数据库迁移脚本migrate_add_also_like_table.py
  - [x] SubTask 2.4: 更新app.py中的图书详情API和推荐API，确保新字段和关系表数据正确读取

- [x] Task 3: also_like书名到book_id的映射
  - [x] SubTask 3.1: 实现书名精确匹配函数（直接比对books.title字段）
  - [x] SubTask 3.2: 实现书名模糊匹配函数（基于编辑距离）
  - [x] SubTask 3.3: 编写批量映射脚本，查询match_type='unmatched'的记录并尝试匹配
  - [x] SubTask 3.4: 编写also_like数据批量回填脚本

- [ ] Task 4: 领域分布偏移分析
  - [ ] SubTask 4.1: 创建algorithms/scripts/analyze_domain_shift.py脚本
  - [ ] SubTask 4.2: 实现各领域BGE向量质心计算
  - [ ] SubTask 4.3: 实现领域间质心余弦距离计算
  - [ ] SubTask 4.4: 实现领域内类内散度计算
  - [ ] SubTask 4.5: 输出领域偏移报告（识别偏移最严重的领域对）

- [ ] Task 5: CORAL领域自适应对齐训练
  - [ ] SubTask 5.1: 创建algorithms/scripts/train_domain_aligner.py，实现CORAL对齐算法
  - [ ] SubTask 5.2: 实现源域和目标域协方差矩阵计算
  - [ ] SubTask 5.3: 实现白化和重新着色步骤，生成768×768投影矩阵
  - [ ] SubTask 5.4: 以"综合领域"为目标域，为每个领域学习投影矩阵
  - [ ] SubTask 5.5: 将投影矩阵保存到algorithms/models/domain_projections.json
  - [ ] SubTask 5.6: 批量生成所有书籍的对齐向量，写入数据库aligned_embedding字段

- [ ] Task 6: 对比学习跨域对齐训练
  - [ ] SubTask 6.1: 创建algorithms/scripts/train_contrastive_aligner.py
  - [ ] SubTask 6.2: 实现跨域正负样本对构建（基于book_also_like表）
  - [ ] SubTask 6.3: 实现2层MLP投影网络（768→256→768，带LayerNorm和ReLU）
  - [ ] SubTask 6.4: 实现InfoNCE损失函数和训练循环（lr=1e-4, epochs=50, τ=0.07）
  - [ ] SubTask 6.5: 保存模型到algorithms/models/contrastive_model.pt
  - [ ] SubTask 6.6: 批量生成对比学习嵌入，与CORAL对齐向量融合，写入数据库final_embedding字段

- [ ] Task 7: 领域对齐推理与集成
  - [ ] SubTask 7.1: 创建backend/app/services/domain_aligner.py，定义DomainAligner类
  - [ ] SubTask 7.2: 实现投影矩阵加载和在线对齐推理
  - [ ] SubTask 7.3: 实现对比学习模型加载和在线推理
  - [ ] SubTask 7.4: 在recommender.py的_load_books_data中新增aligned_embedding和final_embedding字段加载
  - [ ] SubTask 7.5: 实现新书入库时的实时对齐处理（根据领域标签选择投影矩阵）
  - [ ] SubTask 7.6: 在book_processor.py中集成对齐处理步骤
  - [ ] SubTask 7.7: 更新add_book_to_index方法，支持对齐向量字段

- [ ] Task 8: 知识概念桥接模块
  - [ ] SubTask 8.1: 创建backend/app/services/knowledge_bridge.py，定义KnowledgeBridge类
  - [ ] SubTask 8.2: 实现关键词共现桥接图构建
  - [ ] SubTask 8.3: 实现领域关系矩阵构建（基于领域标签共现统计）
  - [ ] SubTask 8.4: 实现跨域推荐解释路径提取（BFS搜索桥接路径）
  - [ ] SubTask 8.5: 将桥接路径信息传递给LLM推荐理由生成模块

- [ ] Task 9: 跨域推荐核心算法优化（迁移学习版）
  - [ ] SubTask 9.1: 在recommender.py中用AlignedSim替代SemanticSim（对齐后语义相似度）
  - [ ] SubTask 9.2: 在recommender.py中新增CoOccurSim计算（从book_also_like表查询）
  - [ ] SubTask 9.3: 修改最终得分公式：FinalScore = EnhancedSim × OverlapCoeff
  - [ ] SubTask 9.4: 实现降级兼容逻辑（aligned_embedding为NULL时使用原始BGE向量）
  - [ ] SubTask 9.5: 更新config.json，新增w1/w2/coral/contrastive相关参数
  - [ ] SubTask 9.6: 更新app.py推荐API，返回AlignedSim和CoOccurSim等新增指标

- [ ] Task 10: 领域关系感知标签系统升级
  - [ ] SubTask 10.1: 构建领域关系矩阵（基于书籍领域标签共现统计）
  - [ ] SubTask 10.2: 实现领域间语义距离计算
  - [ ] SubTask 10.3: 修改重叠标签系数计算，融入领域距离因子
  - [ ] SubTask 10.4: 将领域关系矩阵持久化存储

- [ ] Task 11: 推荐理由增强
  - [ ] SubTask 11.1: 修改llm_service.py的Prompt模板，融入知识桥接路径信息
  - [ ] SubTask 11.2: 在推荐API响应中新增bridge_keywords字段
  - [ ] SubTask 11.3: 前端展示桥接关键词

- [ ] Task 12: 离线数据批量处理与验证
  - [ ] SubTask 12.1: 编写完整离线处理流水线脚本（also_like回填 → 映射 → CORAL对齐 → 对比学习 → 算法验证）
  - [ ] SubTask 12.2: 对比优化前后的推荐质量指标（Hit Rate、NDCG、多样性）
  - [ ] SubTask 12.3: 验证降级兼容性（对齐向量不可用时推荐结果与原算法一致）
  - [ ] SubTask 12.4: 对比领域偏移分析前后跨域相似度分布变化

# Task Dependencies

- Task 2 depends on Task 1 (数据库字段扩展需先确定also_like数据格式)
- Task 3 depends on Task 1, Task 2 (映射需要also_like数据和book_also_like表)
- Task 4 depends on nothing (领域偏移分析只需现有BGE向量，可最先执行)
- Task 5 depends on Task 4 (CORAL训练需要领域偏移分析结果确定目标域)
- Task 6 depends on Task 3, Task 5 (对比学习需要also_like正样本对和CORAL预对齐向量)
- Task 7 depends on Task 5, Task 6 (推理需要训练好的投影矩阵和对比学习模型)
- Task 8 depends on nothing (知识桥接只需关键词和领域标签，可独立执行)
- Task 9 depends on Task 7, Task 8 (算法优化需要对齐向量和知识桥接模块)
- Task 10 depends on nothing (领域关系只需领域标签，可独立执行)
- Task 11 depends on Task 8, Task 9 (推荐理由增强需要知识桥接和算法优化)
- Task 12 depends on Task 9, Task 10, Task 11 (验证需要所有模块完成)
- Task 1, Task 2, Task 4, Task 8, Task 10 可并行执行
- Task 5, Task 6 需顺序执行（对比学习依赖CORAL预对齐）
