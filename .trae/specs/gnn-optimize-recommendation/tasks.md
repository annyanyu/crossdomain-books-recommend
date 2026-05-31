# Tasks — GNN优化方案

- [x] Task 1: 扩展豆瓣爬虫，采集also_like数据
  - [x] SubTask 1.1: 分析豆瓣书籍详情页HTML结构，定位"喜欢这本书的人也喜欢"区域的CSS选择器
  - [x] SubTask 1.2: 在douban_scraper.py中新增also_like解析逻辑，提取关联书名列表
  - [x] SubTask 1.3: 修改douban_scraper.py的_clean_data方法，将also_like从硬编码空列表改为实际解析结果
  - [x] SubTask 1.4: 在app.py的新书入库流程中，确保also_like数据同时写入books.also_like字段和book_also_like表

- [x] Task 2: 数据库表结构扩展（book_also_like关系表 + books新字段）
  - [x] SubTask 2.1: 在init_database.py中新增book_also_like表的CREATE TABLE语句（含外键约束和索引）
  - [x] SubTask 2.2: 在init_database.py中为books表新增gnn_embedding JSON字段
  - [x] SubTask 2.3: 编写数据库迁移脚本migrate_add_also_like_table.py
  - [x] SubTask 2.4: 更新app.py中的图书详情API和推荐API，确保新字段和关系表数据正确读取

- [x] Task 3: also_like书名到book_id的映射
  - [x] SubTask 3.1: 实现书名精确匹配函数（直接比对books.title字段）
  - [x] SubTask 3.2: 实现书名模糊匹配函数（基于编辑距离）
  - [x] SubTask 3.3: 编写批量映射脚本，查询match_type='unmatched'的记录并尝试匹配
  - [x] SubTask 3.4: 编写also_like数据批量回填脚本

- [ ] Task 4: 书籍关联图构建模块
  - [ ] SubTask 4.1: 创建backend/app/services/book_graph.py，定义BookGraph类
  - [ ] SubTask 4.2: 实现基于book_also_like表的共现边构建
  - [ ] SubTask 4.3: 实现基于语义相似度的隐式边构建（阈值过滤）
  - [ ] SubTask 4.4: 实现图的序列化存储和反序列化加载
  - [ ] SubTask 4.5: 实现图的增量更新接口add_book_to_graph
  - [ ] SubTask 4.6: 在app.py服务启动时预加载图数据

- [ ] Task 5: LightGCN模型训练（青椒云GPU环境）
  - [ ] SubTask 5.1: 编写数据导出脚本，从数据库导出图结构（邻接表）和BGE向量
  - [ ] SubTask 5.2: 创建algorithms/scripts/train_gnn_model.py，实现LightGCN模型
  - [ ] SubTask 5.3: 实现BPR损失函数和训练循环（lr=0.01, epochs=200, n_layers=2, embedding_dim=128）
  - [ ] SubTask 5.4: 实现模型验证逻辑（每10 epoch验证，保存最优模型）
  - [ ] SubTask 5.5: 编写GNN嵌入导出脚本，将训练结果导入数据库gnn_embedding字段
  - [ ] SubTask 5.6: 编写青椒云环境部署文档（依赖安装、数据传输、训练执行流程）

- [ ] Task 6: GNN嵌入推理与集成
  - [ ] SubTask 6.1: 在recommender.py的_load_books_data中新增gnn_embedding字段加载
  - [ ] SubTask 6.2: 实现新书入库时的临时GNN嵌入生成（1-hop邻居平均）
  - [ ] SubTask 6.3: 在book_processor.py中集成GNN嵌入处理步骤
  - [ ] SubTask 6.4: 更新add_book_to_index方法，支持gnn_embedding字段

- [ ] Task 7: 知识概念桥接模块
  - [ ] SubTask 7.1: 创建backend/app/services/knowledge_bridge.py，定义KnowledgeBridge类
  - [ ] SubTask 7.2: 实现关键词共现桥接图构建
  - [ ] SubTask 7.3: 实现领域关系矩阵构建（基于领域标签共现统计）
  - [ ] SubTask 7.4: 实现跨域推荐解释路径提取（BFS搜索桥接路径）
  - [ ] SubTask 7.5: 将桥接路径信息传递给LLM推荐理由生成模块

- [ ] Task 8: 跨域推荐核心算法优化（GNN版）
  - [ ] SubTask 8.1: 在recommender.py中新增GNNSim计算（GNN嵌入余弦相似度）
  - [ ] SubTask 8.2: 在recommender.py中新增CoOccurSim计算（从book_also_like表查询）
  - [ ] SubTask 8.3: 修改最终得分公式：FinalScore = EnhancedSim × OverlapCoeff
  - [ ] SubTask 8.4: 实现降级兼容逻辑（gnn_embedding为NULL时自动回退）
  - [ ] SubTask 8.5: 更新config.json，新增w1/w2/w3/gnn相关参数
  - [ ] SubTask 8.6: 更新app.py推荐API，返回GNNSim和CoOccurSim等新增指标

- [ ] Task 9: 领域关系感知标签系统升级
  - [ ] SubTask 9.1: 构建领域关系矩阵（基于书籍领域标签共现统计）
  - [ ] SubTask 9.2: 实现领域间语义距离计算
  - [ ] SubTask 9.3: 修改重叠标签系数计算，融入领域距离因子
  - [ ] SubTask 9.4: 将领域关系矩阵持久化存储

- [ ] Task 10: 推荐理由增强
  - [ ] SubTask 10.1: 修改llm_service.py的Prompt模板，融入知识桥接路径信息
  - [ ] SubTask 10.2: 在推荐API响应中新增bridge_keywords字段
  - [ ] SubTask 10.3: 前端展示桥接关键词

- [ ] Task 11: 离线数据批量处理与验证
  - [ ] SubTask 11.1: 编写完整离线处理流水线脚本
  - [ ] SubTask 11.2: 对比优化前后的推荐质量指标
  - [ ] SubTask 11.3: 验证降级兼容性

# Task Dependencies

- Task 2 depends on Task 1 (数据库字段扩展需先确定also_like数据格式)
- Task 3 depends on Task 1, Task 2 (映射需要also_like数据和book_also_like表)
- Task 4 depends on Task 3 (图构建需要book_also_like表中匹配成功的记录)
- Task 5 depends on Task 4 (GNN训练需要图结构)
- Task 6 depends on Task 5 (推理需要训练好的模型和嵌入向量)
- Task 7 depends on Task 4 (知识桥接需要图结构中的关键词信息)
- Task 8 depends on Task 6, Task 7 (算法优化需要GNN嵌入和知识桥接模块)
- Task 9 depends on Task 4 (领域关系需要图中的领域标签信息)
- Task 10 depends on Task 7, Task 8 (推荐理由增强需要知识桥接和算法优化)
- Task 11 depends on Task 8, Task 9, Task 10 (验证需要所有模块完成)
- Task 1, Task 2 可并行执行
- Task 7, Task 9 可并行执行
