# Tasks

- [ ] Task 1: 扩展豆瓣爬虫，采集also_like数据
  - [ ] SubTask 1.1: 分析豆瓣书籍详情页HTML结构，定位"喜欢这本书的人也喜欢"区域的CSS选择器
  - [ ] SubTask 1.2: 在douban_scraper.py中新增also_like解析逻辑，提取关联书名列表
  - [ ] SubTask 1.3: 修改douban_scraper.py的cleaned数据字典，将also_like从硬编码空列表改为实际解析结果
  - [ ] SubTask 1.4: 在book_processor.py和app.py的新书入库流程中，确保also_like数据同时写入books.also_like字段和book_also_like表

- [ ] Task 2: 数据库表结构扩展（book_also_like关系表 + books新字段）
  - [ ] SubTask 2.1: 在init_database.py中新增book_also_like表的CREATE TABLE语句（含外键约束）
  - [ ] SubTask 2.2: 在init_database.py中为books表新增graph_embedding和enhanced_embedding两个JSON字段
  - [ ] SubTask 2.3: 编写数据库迁移脚本migrate_add_also_like_table.py，为已有数据库执行ALTER TABLE添加新表和新字段
  - [ ] SubTask 2.4: 更新app.py中的图书详情API和推荐API，确保新字段和关系表数据正确读取和返回

- [ ] Task 3: also_like书名到book_id的映射（基于book_also_like表）
  - [ ] SubTask 3.1: 实现书名精确匹配函数（直接比对books.title字段）
  - [ ] SubTask 3.2: 实现书名模糊匹配函数（基于编辑距离或关键词包含关系）
  - [ ] SubTask 3.3: 编写批量映射脚本，查询book_also_like表中match_type='unmatched'的记录，尝试匹配并更新target_book_id、match_type、match_score
  - [ ] SubTask 3.4: 编写also_like数据批量回填脚本，为已有书籍从豆瓣补充also_like数据到book_also_like表

- [ ] Task 4: 书籍关联图构建模块
  - [ ] SubTask 4.1: 创建backend/app/services/book_graph.py，定义BookGraph类
  - [ ] SubTask 4.2: 实现基于book_also_like表的共现边构建（查询match_type IN ('exact','fuzzy')的记录，边权重=weight×match_score）
  - [ ] SubTask 4.3: 实现基于语义相似度的隐式边构建（阈值过滤，边权重=余弦相似度）
  - [ ] SubTask 4.4: 实现图的序列化存储（邻接表格式，存入JSON或pickle文件）
  - [ ] SubTask 4.5: 实现图的增量更新接口（add_book_to_graph），新书入库时自动更新
  - [ ] SubTask 4.6: 在app.py服务启动时预加载图数据，新书入库时调用增量更新

- [ ] Task 5: 图嵌入生成模块
  - [ ] SubTask 5.1: 安装node2vec依赖（node2vec或自行实现简化版）
  - [ ] SubTask 5.2: 创建algorithms/scripts/generate_graph_embeddings.py离线脚本
  - [ ] SubTask 5.3: 实现Node2Vec图嵌入生成（128维，walk_length=30, num_walks=10）
  - [ ] SubTask 5.4: 实现增强向量拼接逻辑（768维BGE + 128维GraphEmb → 896维enhanced_embedding）
  - [ ] SubTask 5.5: 将graph_embedding和enhanced_embedding写入books表
  - [ ] SubTask 5.6: 在book_processor.py中集成图嵌入生成，新书入库时实时生成图嵌入

- [ ] Task 6: 知识概念桥接模块
  - [ ] SubTask 6.1: 创建backend/app/services/knowledge_bridge.py，定义KnowledgeBridge类
  - [ ] SubTask 6.2: 实现关键词共现桥接图构建（不同领域书籍共享关键词 → 桥接边）
  - [ ] SubTask 6.3: 实现领域关系矩阵构建（基于领域标签共现统计）
  - [ ] SubTask 6.4: 实现跨域推荐解释路径提取（BFS搜索源领域到目标领域的桥接路径）
  - [ ] SubTask 6.5: 将桥接路径信息传递给LLM推荐理由生成模块，增强推荐可解释性

- [ ] Task 7: 跨域推荐核心算法优化
  - [ ] SubTask 7.1: 在recommender.py中新增GraphSim计算（图嵌入余弦相似度）
  - [ ] SubTask 7.2: 在recommender.py中新增CoOccurSim计算（从book_also_like表查询共现关联度）
  - [ ] SubTask 7.3: 修改最终得分公式：FinalScore = EnhancedSim × OverlapCoeff
  - [ ] SubTask 7.4: 实现降级兼容逻辑（book_also_like表为空或graph_embedding为NULL时自动回退）
  - [ ] SubTask 7.5: 更新config.json，新增w1/w2/w3等算法参数
  - [ ] SubTask 7.6: 更新app.py推荐API，返回GraphSim和CoOccurSim等新增指标

- [ ] Task 8: 领域关系感知标签系统升级
  - [ ] SubTask 8.1: 构建领域关系矩阵（10×10，基于书籍领域标签共现统计）
  - [ ] SubTask 8.2: 实现领域间语义距离计算（基于关系矩阵的归一化距离）
  - [ ] SubTask 8.3: 修改重叠标签系数计算，融入领域距离因子
  - [ ] SubTask 8.4: 将领域关系矩阵持久化存储（JSON配置文件）

- [ ] Task 9: 推荐理由增强
  - [ ] SubTask 9.1: 修改llm_service.py的Prompt模板，融入知识桥接路径信息
  - [ ] SubTask 9.2: 在推荐API响应中新增bridge_keywords字段（桥接关键词列表）
  - [ ] SubTask 9.3: 前端展示桥接关键词，增强推荐可解释性

- [ ] Task 10: 离线数据批量处理与验证
  - [ ] SubTask 10.1: 编写完整离线处理流水线脚本（also_like回填 → book_also_like映射 → 图构建 → 图嵌入 → 增强向量 → 算法验证）
  - [ ] SubTask 10.2: 在测试数据集上对比优化前后的推荐质量指标（Hit Rate、NDCG、多样性）
  - [ ] SubTask 10.3: 验证降级兼容性（book_also_like表为空时推荐结果与原算法一致）

# Task Dependencies

- Task 2 depends on Task 1 (数据库表和字段扩展需先确定also_like数据格式)
- Task 3 depends on Task 1, Task 2 (映射需要also_like数据和book_also_like表)
- Task 4 depends on Task 3 (图构建需要book_also_like表中匹配成功的记录)
- Task 5 depends on Task 4 (图嵌入需要图结构)
- Task 6 depends on Task 4 (知识桥接需要图结构中的关键词信息)
- Task 7 depends on Task 5, Task 6 (算法优化需要图嵌入和知识桥接模块)
- Task 8 depends on Task 4 (领域关系需要图中的领域标签信息)
- Task 9 depends on Task 6, Task 7 (推荐理由增强需要知识桥接和算法优化)
- Task 10 depends on Task 7, Task 8, Task 9 (验证需要所有模块完成)
- Task 1, Task 2 可并行执行
- Task 6, Task 8 可并行执行
