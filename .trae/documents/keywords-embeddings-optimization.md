# 关键词质量提升与关键词嵌入修复计划

## 问题诊断

### 问题1：keywords 列质量低
**现象**：
- 317本书中有46本关键词为空或近空
- 大量无意义词被提取为关键词，如："成为"、"作者"、"精神"、"大篇幅"、"首度"、"称得上"、"有史以来"、"不想"、"只能"、"进行"、"任何人"
- 部分关键词含前导空格：" 称得上"、" 进 行"
- 英文停用词被提取：如 "the"、"is"、"that"、"changed"

**根因分析**（[extract_keywords.py](file:///f:/大一年度项目/crossdomain-books-recommend/books-recommend-system/algorithms/scripts/extract_keywords.py)）：
1. **输入源不足**：`extract_keywords_for_book()` 仅使用 `books_intro` + `author_intro`，未利用 `title`、`short_reviews`、`reviews`、`reading_notes`
2. **TF-IDF实现错误**：单本书处理时用简单词频代替真正的TF-IDF（需要语料库），导致高频通用词被误选
3. **停用词表过小**：仅162个词，缺少大量中文常用动词/形容词（"成为"、"进行"、"了解"等）
4. **TF-IDF部分无词性过滤**：TextRank有 `allowPOS` 过滤，但词频统计部分没有
5. **ngram问题**：`TfidfVectorizer` 使用 `ngram_range=(1,2)` 产生含空格的2-gram

### 问题2：keywords_embeddings 列所有行内容相同
**现象**：
- `SELECT COUNT(DISTINCT keywords_embeddings) FROM books` 返回 1
- 所有317行的 keywords_embeddings 完全一致

**根因分析**（[generate_embeddings.py](file:///f:/大一年度项目/crossdomain-books-recommend/books-recommend-system/algorithms/scripts/generate_embeddings.py)）：
1. **Word2Vec训练语料不当**：训练语料是每个关键词经jieba分词后的结果（每个"句子"仅1-3个词），无法学到有意义的词关系
2. **训练语料规模过小**：仅317本书×10个关键词≈3170个极短"句子"，远不足以训练有效的Word2Vec
3. **结果**：所有词映射到几乎相同的向量空间位置，导致所有书的关键词嵌入向量列表完全一致

---

## 优化方案

### 步骤1：优化关键词提取算法

修改 `algorithms/scripts/extract_keywords.py` 中的 `KeywordExtractor` 类：

1. **扩展输入源**：`extract_keywords_for_book()` 增加 `title`、`short_reviews`、`reviews`、`reading_notes` 参数，将所有可用文本拼接
2. **扩充停用词表**：在 `stopwords.txt` 中增加至少200个中文常用无意义词（通用动词、形容词、副词、代词等）
3. **实现真正的TF-IDF**：在 `extract_keywords_for_book()` 中，先批量构建语料库计算TF-IDF，而非使用简单词频
4. **添加词性过滤**：对词频统计部分也添加词性过滤（仅保留名词、动名词、形容词）
5. **添加关键词清洗**：去除前导/尾随空格、过滤纯数字、过滤单字、过滤英文停用词
6. **增加候选词数量**：先提取 top_k*3 个候选词，再经清洗和过滤后取 top_k

### 步骤2：修复关键词嵌入生成

修改 `algorithms/scripts/generate_embeddings.py` 中的 `BookEmbeddingGenerator` 类：

1. **使用BGE模型生成关键词嵌入**：对每个关键词，直接使用 `bge_model.encode(keyword)` 生成768维向量，替代Word2Vec
2. **移除Word2Vec训练逻辑**：删除 `train_word2vec_model()` 方法和相关调用，因为BGE模型已能提供高质量语义向量
3. **确保每本书独立生成**：每本书根据自己的 keywords 列表独立生成嵌入，保证唯一性
4. **Fallback方案**：若BGE模型不可用，使用TF-IDF+SVD为每本书的关键词独立生成向量

### 步骤3：重新执行数据预处理流水线

按顺序执行：
1. 运行优化后的 `extract_keywords.py` → 更新 `keywords` 列
2. 运行 `assign_domain_tags.py` → 更新 `domain_tags` 列（基于新关键词）
3. 运行优化后的 `generate_embeddings.py` → 更新 `embedding` 和 `keywords_embeddings` 列

### 步骤4：验证结果

1. 检查 `keywords` 列：确认无空值、无通用无意义词、关键词与内容主题相关
2. 检查 `keywords_embeddings` 列：确认 `COUNT(DISTINCT keywords_embeddings) > 1`，每本书有唯一嵌入
3. 检查 `domain_tags` 列：确认基于新关键词的领域标签合理
4. 启动服务验证推荐功能正常

---

## 涉及文件

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `algorithms/scripts/extract_keywords.py` | 修改 | 优化关键词提取算法 |
| `algorithms/scripts/stopwords.txt` | 修改 | 扩充停用词表 |
| `algorithms/scripts/generate_embeddings.py` | 修改 | 修复关键词嵌入生成逻辑 |

## 不涉及的文件

- `backend/` 下所有文件不做修改
- `algorithms/scripts/assign_domain_tags.py` 不做修改（逻辑正确，依赖新关键词即可）
- `algorithms/scripts/domain_tags.json` 不做修改
- `algorithms/recommenders/` 下文件不做修改
