# 书籍数据自动入库与跨领域推荐功能实现方案

## 一、架构设计概览

### 1.1 整体数据流

```
用户搜索无结果 → 展示"未找到"提示 + 豆瓣URL输入框
    ↓
用户输入豆瓣URL → 前端验证URL格式 → POST /api/books/add
    ↓
后端爬取豆瓣页面 → 数据清洗标准化 → 去重检查
    ↓
关键词提取(jieba+TF-IDF+TextRank) → 领域标签分配(关键词匹配)
    ↓
向量生成(BAAI/bge-base-zh-v1.5) → 整体embedding + 关键词embeddings
    ↓
写入数据库 → 更新推荐器内存索引 → 返回成功
    ↓
用户可立即搜索到新书并获得跨域推荐
```

### 1.2 核心设计原则

**与现有系统完全一致**：新书入库后的关键词提取、领域标签分配、向量生成流程，必须复用 `algorithms/scripts/` 下的现有模块，确保数据处理逻辑与已有书籍完全一致。

***

## 二、功能模块详细设计

### 2.1 前端：搜索无结果触发机制

**修改文件**：`backend/static/js/main.js`

**当前行为**：`renderBooks()` 在 `books.length === 0` 时仅显示"暂无图书数据"。

**改造方案**：

```javascript
function renderBooks(books) {
    const booksGrid = document.getElementById('booksGrid');
    if (books.length === 0) {
        const searchValue = document.getElementById('searchInput').value;
        if (searchValue && searchValue.trim()) {
            booksGrid.innerHTML = `
                <div class="no-result-container">
                    <div class="no-result-icon">📚</div>
                    <div class="no-result-title">未找到"${searchValue}"相关书籍</div>
                    <div class="no-result-desc">您可以尝试其他关键词，或通过豆瓣链接添加新书</div>
                    <div class="add-book-section">
                        <input type="text" id="doubanUrlInput" 
                               placeholder="请输入豆瓣书籍详情页URL，如 https://book.douban.com/subject/1234567/"
                               class="douban-url-input">
                        <button onclick="addNewBook()" class="add-book-btn" id="addBookBtn">
                            📖 添加新书
                        </button>
                    </div>
                    <div id="addBookStatus" class="add-book-status" style="display:none;"></div>
                </div>
            `;
        } else {
            booksGrid.innerHTML = '<div class="loading">暂无图书数据</div>';
        }
        return;
    }
    // ... 原有逻辑不变
}
```

**URL验证函数**：

```javascript
function validateDoubanUrl(url) {
    const pattern = /^https?:\/\/book\.douban\.com\/subject\/\d+\/?/;
    return pattern.test(url.trim());
}

async function addNewBook() {
    const urlInput = document.getElementById('doubanUrlInput');
    const statusDiv = document.getElementById('addBookStatus');
    const btn = document.getElementById('addBookBtn');
    const url = urlInput.value.trim();

    if (!url) {
        showAddBookStatus('error', '请输入豆瓣书籍详情页URL');
        return;
    }
    if (!validateDoubanUrl(url)) {
        showAddBookStatus('error', 'URL格式不正确，请输入有效的豆瓣书籍详情页地址');
        return;
    }

    btn.disabled = true;
    showAddBookStatus('loading', '正在采集书籍信息...');

    try {
        const response = await fetch('/api/books/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ douban_url: url })
        });
        const data = await response.json();

        if (data.success) {
            showAddBookStatus('success', `《${data.data.title}》添加成功！`);
            setTimeout(() => loadBooks(1), 1500);
        } else {
            showAddBookStatus('error', data.error || '添加失败');
            btn.disabled = false;
        }
    } catch (error) {
        showAddBookStatus('error', '网络错误: ' + error.message);
        btn.disabled = false;
    }
}

function showAddBookStatus(type, message) {
    const statusDiv = document.getElementById('addBookStatus');
    statusDiv.style.display = 'block';
    const icons = { loading: '⏳', success: '✅', error: '❌' };
    statusDiv.className = `add-book-status status-${type}`;
    if (type === 'loading') {
        statusDiv.innerHTML = `<span class="reason-loading-dot"></span> ${message}`;
    } else {
        statusDiv.innerHTML = `${icons[type]} ${message}`;
    }
}
```

**CSS样式**：在 `backend/static/css/style.css` 中添加 `.no-result-container`、`.add-book-section`、`.douban-url-input`、`.add-book-btn`、`.add-book-status` 等样式。

***

### 2.2 后端：豆瓣数据爬取模块

**新建文件**：`backend/app/services/douban_scraper.py`

#### 2.2.1 爬取策略

使用 `requests + BeautifulSoup` 爬取豆瓣书籍页面，提取结构化数据。

**豆瓣页面URL格式**：`https://book.douban.com/subject/{book_id}/`

**提取字段映射**：

| 豆瓣页面元素 | 数据库字段             | 提取方式                                   |
| ------ | ----------------- | -------------------------------------- |
| 书名     | title             | `#wrapper h1 span`                     |
| 封面图    | cover\_image      | `#mainpic img` 的 href 属性               |
| 作者     | authors           | `#info span.pl:contains("作者")` 后的 a 标签 |
| 出版社    | publisher         | `#info span.pl:contains("出版社")` 后的文本   |
| 出版日期   | publication\_date | `#info span.pl:contains("出版年")` 后的文本   |
| 评分     | rating            | `rating_num` class                     |
| ISBN   | (辅助去重)            | `#info span.pl:contains("ISBN")` 后的文本  |
| 内容简介   | books\_intro      | `#link-report .intro` 最后一个 div         |
| 作者简介   | author\_intro     | `#link-report .intro` 相关区域             |
| 标签     | domain (辅助)       | `.indent span.tag`                     |
| 豆瓣URL  | URL               | 原始输入URL                                |

#### 2.2.2 核心类设计

```python
class DoubanScraper:
    def __init__(self, timeout=15, max_retries=3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 ...',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })

    def scrape_book(self, url: str) -> Dict:
        """主入口：爬取豆瓣页面并返回结构化数据"""
        # 1. 验证URL格式
        # 2. 发送HTTP请求（带重试）
        # 3. 解析HTML提取数据
        # 4. 数据清洗与标准化
        # 5. 返回结构化字典

    def _validate_url(self, url: str) -> bool:
        """验证URL是否符合豆瓣书籍详情页格式"""

    def _extract_book_id(self, url: str) -> str:
        """从URL中提取豆瓣book_id用于去重"""

    def _parse_html(self, html: str, url: str) -> Dict:
        """解析HTML页面，提取书籍信息"""

    def _clean_data(self, raw_data: Dict) -> Dict:
        """数据清洗：去除特殊字符、统一格式、验证完整性"""

    def _parse_publication_date(self, date_str: str) -> Optional[str]:
        """将豆瓣日期格式标准化为 YYYY-MM-DD"""
```

#### 2.2.3 数据清洗规则

* **书名**：去除首尾空白、连续空格合并

* **作者**：去除"作者:"前缀、按分隔符拆分为列表、去除"等"字

* **出版社**：去除首尾空白

* **出版日期**：支持"2023-1"、"2023年1月"、"2023/1/1"等格式，统一为"YYYY-MM-DD"

* **评分**：转为float，范围校验0-5

* **简介**：去除首尾空白、HTML标签清理

* **URL**：标准化为 `https://book.douban.com/subject/{id}/` 格式

***

### 2.3 后端：新书入库API

**修改文件**：`backend/app.py`

**新增端点**：`POST /api/books/add`

```python
@app.route('/api/books/add', methods=['POST'])
def add_book():
    """新书添加API"""
    try:
        data = request.get_json()
        douban_url = data.get('douban_url', '').strip()

        # 1. URL格式验证
        # 2. 爬取豆瓣数据
        # 3. 去重检查（按title + authors 或 豆瓣URL）
        # 4. 关键词提取
        # 5. 领域标签分配
        # 6. 向量生成
        # 7. 数据库写入
        # 8. 更新推荐器内存索引
        # 9. 返回成功

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

***

### 2.4 后端：数据处理管线（与现有系统一致）

**新建文件**：`backend/app/services/book_processor.py`

此模块负责将爬取的原始数据经过与现有系统完全一致的处理管线，生成可入库的完整数据。

#### 2.4.1 关键词提取（复用现有逻辑）

现有系统使用 `algorithms/scripts/extract_keywords.py` 的 `KeywordExtractor` 类。但该类设计为批量处理模式（需要跨文档计算IDF），不适合单本书处理。

**解决方案**：在 `book_processor.py` 中实现单本书关键词提取，算法逻辑与 `KeywordExtractor` 完全一致：

```python
class BookProcessor:
    def __init__(self, config: dict):
        self.config = config
        self.keyword_extractor = None  # 延迟加载
        self.domain_tag_assigner = None
        self.embedding_generator = None

    def process_new_book(self, book_data: Dict) -> Dict:
        """完整处理管线：关键词→标签→向量"""
        # Step 1: 关键词提取
        keywords = self._extract_keywords_single(book_data)
        book_data['keywords'] = keywords

        # Step 2: 领域标签分配
        domain_tags = self._assign_domain_tags(book_data)
        book_data['domain_tags'] = domain_tags
        book_data['domain'] = domain_tags  # 冗余字段，与现有数据一致

        # Step 3: 向量生成
        embedding, keywords_embeddings = self._generate_embeddings(book_data)
        book_data['embedding'] = embedding
        book_data['keywords_embeddings'] = keywords_embeddings

        return book_data
```

#### 2.4.2 单本书关键词提取（复用已有语料库IDF）

**核心问题**：TF-IDF = TF × IDF，其中IDF（逆文档频率）= `log(总文档数 / 包含该词的文档数)`，需要跨文档统计。现有系统用317本书一起 `fit_transform` 计算IDF，单本书无法独立计算。

**解决方案**：加载已有317本书的文本，与新书一起构建 `TfidfVectorizer`，这样IDF值基于完整语料库计算，与现有书籍的关键词提取完全一致。

```python
def _extract_keywords_single(self, book_data: Dict, top_k: int = 12) -> List[str]:
    """
    单本书关键词提取（与现有系统extract_keywords.py算法完全一致）
    
    关键设计：加载已有书籍文本作为语料库，使TF-IDF的IDF值与批量处理时一致。
    现有系统用317本书一起fit_transform，我们用317+1本书一起fit_transform，
    这样IDF值几乎不变（317→318，差异<0.3%），关键词提取质量与现有书籍一致。
    """
    # 1. 拼接新书文本（与现有系统_combine_book_text一致：title*2 + intro + author_intro）
    new_text = self._combine_book_text(book_data)

    # 2. 从数据库加载已有书籍的文本（仅需title, books_intro, author_intro等字段）
    existing_texts = self._load_existing_book_texts()

    # 3. 将新书文本追加到语料库末尾
    all_texts = existing_texts + [new_text]

    # 4. 对所有文本做jieba分词+词性过滤（与现有系统_segment_text一致）
    processed_texts = []
    for text in all_texts:
        processed_text = self._preprocess_text(text)
        words = self._segment_text(processed_text)
        processed_texts.append(' '.join(words))

    # 5. TF-IDF批量提取（与现有系统extract_tfidf_keywords_batch一致）
    tfidf_vectorizer = TfidfVectorizer(
        max_features=5000, min_df=2, max_df=0.85, ngram_range=(1, 1)
    )
    tfidf_matrix = tfidf_vectorizer.fit_transform(processed_texts)
    feature_names = tfidf_vectorizer.get_feature_names_out()

    # 取最后一本书（新书）的TF-IDF关键词
    new_idx = len(processed_texts) - 1
    tfidf_scores = tfidf_matrix[new_idx].toarray()[0]
    top_indices = np.argsort(tfidf_scores)[-top_k * 3:][::-1]
    tfidf_keywords = [feature_names[idx] for idx in top_indices if tfidf_scores[idx] > 0]
    tfidf_keywords = self._clean_keywords(tfidf_keywords)

    # 6. TextRank提取（与现有系统extract_textrank_keywords一致）
    textrank_keywords = self._extract_textrank_keywords(new_text, top_k * 2)

    # 7. 融合两种算法（与现有系统merge_keywords一致：TF-IDF权重x2，TextRank权重x1）
    final_keywords = self._merge_keywords(tfidf_keywords, textrank_keywords, top_k)

    return final_keywords

def _load_existing_book_texts(self) -> List[str]:
    """从数据库加载已有书籍的拼接文本，用于构建TF-IDF语料库"""
    from sqlalchemy import create_engine, text
    engine = create_engine(self._get_db_connection_str())
    texts = []
    with engine.connect() as conn:
        query = text("SELECT title, books_intro, author_intro, short_reviews, reviews, reading_notes FROM books")
        result = conn.execute(query)
        for row in result:
            row_dict = {
                'title': row[0], 'books_intro': row[1], 'author_intro': row[2],
                'short_reviews': row[3], 'reviews': row[4], 'reading_notes': row[5]
            }
            combined = self._combine_book_text_from_row(row_dict)
            texts.append(combined)
    return texts
```

**性能优化**：语料库文本可在服务启动时预加载并缓存，避免每次添加新书都查询数据库。当新增书籍后，将新文本追加到缓存中即可。

**与现有系统的一致性保证**：
- 文本拼接方式：`title*2 + book_intro + author_intro + short_reviews[:5] + reviews[:3] + reading_notes[:3]` → 与 `_combine_book_text()` 一致
- 分词+词性过滤：`ALLOWED_POS` 集合 → 与 `KeywordExtractor.ALLOWED_POS` 一致
- TF-IDF参数：`max_features=5000, min_df=2, max_df=0.85` → 与 `extract_tfidf_keywords_batch()` 一致
- 融合权重：TF-IDF排名分×2 + TextRank排名分×1 → 与 `merge_keywords()` 一致

#### 2.4.3 领域标签分配（完全复用现有模块）

```python
def _assign_domain_tags(self, book_data: Dict) -> List[str]:
    """
    领域标签分配（与assign_domain_tags.py逻辑完全一致）
    """
    # 加载领域标签配置（domain_tags.json）
    # 合并文本：title + books_intro + author_intro
    # 关键词匹配计分
    # 取前2个分数>0的领域，全部为0返回["其他"]
```

直接复用 `algorithms/scripts/assign_domain_tags.py` 的 `DomainTagAssigner` 类，或将其核心逻辑提取为可被后端直接调用的服务。

#### 2.4.4 向量生成（完全复用现有模型）

```python
def _generate_embeddings(self, book_data: Dict) -> Tuple[List[float], List[List[float]]]:
    """
    向量生成（与generate_embeddings.py逻辑完全一致）
    使用 BAAI/bge-base-zh-v1.5 模型
    """
    # 1. 拼接文本（与现有系统一致）
    #    title + book_intro + author_intro + short_reviews + reviews + reading_notes
    # 2. 生成整体768维向量
    # 3. 为每个关键词生成768维向量
    # 4. BGE模型不可用时使用TF-IDF+SVD降级方案
```

直接复用 `algorithms/scripts/generate_embeddings.py` 的 `BookEmbeddingGenerator` 类。

***

### 2.5 后端：推荐器实时索引更新

**修改文件**：`backend/app/services/recommender.py`

**当前问题**：推荐器在启动时一次性加载所有数据到内存，后续新增书籍不会自动更新。

**解决方案**：在 `CrossDomainRecommender` 类中新增 `add_book_to_index()` 方法：

```python
def add_book_to_index(self, book_data: Dict):
    """将新书添加到内存索引"""
    new_entry = {
        'book_id': book_data['book_id'],
        'title': book_data['title'],
        'embedding': book_data['embedding'],
        'keywords_embeddings': book_data['keywords_embeddings'],
        'domain_tags': book_data['domain_tags']
    }
    self.books_data.append(new_entry)
    logger.info(f"[推荐器] 新书已加入索引: book_id={book_data['book_id']}, title={book_data['title']}")
```

在 `app.py` 中，新书入库成功后调用此方法：

```python
recommender.add_book_to_index(processed_book_data)
```

***

### 2.6 异常处理设计

| 异常场景     | 处理策略                        | 用户提示             |
| -------- | --------------------------- | ---------------- |
| URL格式错误  | 前端+后端双重验证，拒绝请求              | "URL格式不正确"       |
| 豆瓣页面请求失败 | 重试3次，每次间隔2s                 | "无法访问豆瓣页面，请稍后重试" |
| 豆瓣反爬拦截   | 检测验证码页面，提示用户                | "豆瓣暂时限制访问，请稍后重试" |
| 数据提取不完整  | 必填字段(title)缺失则拒绝，可选字段设为null | "书籍信息不完整，缺少书名"   |
| 书籍已存在    | 按title+authors或豆瓣URL去重      | "该书籍已在系统中存在"     |
| 向量模型加载失败 | 使用TF-IDF+SVD降级方案            | 不影响用户，后台日志记录     |
| 数据库写入失败  | 事务回滚，返回错误                   | "系统错误，请稍后重试"     |
| 处理超时     | 总超时60s，各步骤有独立超时             | "处理超时，请稍后重试"     |

***

### 2.7 去重机制

**两级去重**：

1. **豆瓣URL去重**：提取URL中的 `subject_id`，查询数据库 `URL` 字段是否已存在
2. **书名+作者去重**：查询 `title` + `authors` 组合是否已存在（处理同一本书不同来源的情况）

```python
def _check_duplicate(self, book_data: Dict, engine) -> Tuple[bool, Optional[int]]:
    """检查书籍是否已存在，返回(是否重复, 已有book_id)"""
    with engine.connect() as conn:
        # 1. 豆瓣URL去重
        if book_data.get('URL'):
            result = conn.execute(
                text("SELECT book_id FROM books WHERE URL = :url LIMIT 1"),
                {'url': book_data['URL']}
            ).fetchone()
            if result:
                return True, result[0]

        # 2. 书名+作者去重
        authors_json = json.dumps(book_data.get('authors', []), ensure_ascii=False)
        result = conn.execute(
            text("SELECT book_id FROM books WHERE title = :title AND authors = :authors LIMIT 1"),
            {'title': book_data['title'], 'authors': authors_json}
        ).fetchone()
        if result:
            return True, result[0]

    return False, None
```

***

## 三、可替代方案评估

### 3.1 方案对比

| 维度        | 当前方案（豆瓣URL爬取）            | 方案A（+手动表单）        | 方案B（+多源API）              |
| --------- | ------------------------ | ----------------- | ------------------------ |
| **技术可行性** | ⭐⭐⭐⭐ 豆瓣页面结构稳定，爬取可行但有反爬风险 | ⭐⭐⭐⭐⭐ 纯表单提交，无外部依赖 | ⭐⭐ 豆瓣API已关闭公开访问，当当无公开API |
| **开发成本**  | 中等（爬取+清洗+验证）             | 低（前端表单+后端校验）      | 高（多源适配+数据融合）             |
| **用户体验**  | ⭐⭐⭐⭐⭐ 只需粘贴URL，一键添加       | ⭐⭐⭐ 需手动填写多个字段     | ⭐⭐⭐⭐⭐ 粘贴URL即可，数据更全面      |
| **数据质量**  | ⭐⭐⭐⭐ 豆瓣数据较完整             | ⭐⭐ 用户填写可能不规范      | ⭐⭐⭐⭐⭐ 多源交叉验证，数据最准确       |
| **维护成本**  | 中等（豆瓣页面改版需更新解析规则）        | 低                 | 高（多源维护）                  |
| **稳定性**   | 中等（受反爬影响）                | 高                 | 低（依赖外部API可用性）            |

### 3.2 推荐实施方案

**推荐：当前方案 + 方案A（豆瓣URL爬取为主，手动表单为备选）**

理由：

1. 豆瓣API已关闭公开访问，方案B的核心前提不成立
2. 手动表单作为降级方案，当爬取失败时用户仍可添加书籍
3. 开发成本可控，用户体验最优
4. 实现方式：在"添加新书"区域增加一个"手动填写"切换按钮

***

## 四、关键技术难点与解决方案

### 4.1 豆瓣反爬机制

**难点**：豆瓣对频繁请求有IP封禁和验证码机制。

**解决方案**：

* 请求间隔随机化（2-5秒）

* 使用随机User-Agent池

* 设置合理的超时和重试策略

* 检测验证码页面，遇到时立即返回友好提示

* 不做批量爬取，仅单本按需爬取，频率极低

### 4.2 单本书关键词提取的TF-IDF问题

**难点**：现有系统使用跨文档TF-IDF计算IDF值，单本书无法独立计算。

**解决方案**：加载已有317本书的文本作为语料库，与新书一起构建 `TfidfVectorizer`。317→318本书的IDF值变化极小（<0.3%），关键词提取质量与现有书籍完全一致。语料库文本在服务启动时预加载并缓存，新增书籍后追加到缓存中，避免每次查询数据库。

### 4.3 BGE模型加载耗时与内存

**难点**：BAAI/bge-base-zh-v1.5 模型约400MB，加载需5-10秒，占用约1GB内存。

**解决方案**：

* 模型延迟加载：首次添加新书时才加载，之后常驻内存

* 使用 `BookEmbeddingGenerator` 的单例模式，避免重复加载

* 降级方案：模型不可用时使用TF-IDF+SVD生成768维向量

### 4.4 推荐器内存索引一致性

**难点**：推荐器在启动时加载数据到内存，新增书籍需同步更新。

**解决方案**：

* 在 `CrossDomainRecommender` 中新增 `add_book_to_index()` 方法

* 新书入库成功后立即调用，保证内存索引与数据库一致

* 无需重启服务即可推荐新书

***

## 五、系统性能优化建议

1. **模型预加载**：在服务启动时预加载BGE模型到内存，避免首次添加新书时的等待
2. **异步处理**：向量生成耗时较长（约3-5秒/本），可考虑异步任务队列，但当前单本处理量下同步即可
3. **缓存豆瓣数据**：对同一URL的爬取结果做短期缓存（5分钟），避免重复爬取
4. **数据库连接池**：使用SQLAlchemy连接池，避免频繁创建连接
5. **向量生成批优化**：关键词向量使用 `encode()` 的批量模式，而非逐个编码

***

## 六、功能测试用例

### 6.1 前端交互测试

| 用例ID  | 测试场景         | 操作步骤                                          | 预期结果               |
| ----- | ------------ | --------------------------------------------- | ------------------ |
| FE-01 | 搜索无结果触发      | 搜索"不存在的书名"                                    | 显示"未找到"提示+豆瓣URL输入框 |
| FE-02 | URL格式验证-有效   | 输入 `https://book.douban.com/subject/1234567/` | 验证通过，按钮可点击         |
| FE-03 | URL格式验证-无效   | 输入 `https://www.baidu.com`                    | 显示"URL格式不正确"       |
| FE-04 | URL格式验证-非书籍页 | 输入 `https://book.douban.com/author/123/`      | 显示"URL格式不正确"       |
| FE-05 | 添加成功流程       | 输入有效URL，点击添加                                  | 显示进度→"添加成功"→自动刷新列表 |
| FE-06 | 重复添加         | 添加已存在的书籍                                      | 显示"该书籍已在系统中存在"     |
| FE-07 | 网络错误         | 断网情况下点击添加                                     | 显示"网络错误"提示         |

### 6.2 后端API测试

| 用例ID  | 测试场景    | 请求参数                        | 预期结果                      |
| ----- | ------- | --------------------------- | ------------------------- |
| BE-01 | 正常添加    | 有效豆瓣URL                     | 200, success=true, 返回书籍信息 |
| BE-02 | URL为空   | `{douban_url: ""}`          | 400, "请输入豆瓣URL"           |
| BE-03 | URL格式错误 | `{douban_url: "not_a_url"}` | 400, "URL格式不正确"           |
| BE-04 | 重复添加    | 已存在书籍的URL                   | 409, "该书籍已存在"             |
| BE-05 | 豆瓣页面不存在 | 404的豆瓣URL                   | 400, "无法获取书籍信息"           |

### 6.3 数据处理测试

| 用例ID  | 测试场景    | 验证点                   |
| ----- | ------- | --------------------- |
| DP-01 | 关键词提取   | 提取10-15个关键词，词性正确      |
| DP-02 | 领域标签分配  | 分配1-2个标签，与书籍内容匹配      |
| DP-03 | 整体向量生成  | 768维向量，非全零            |
| DP-04 | 关键词向量生成 | 每个关键词768维向量，数量与关键词数一致 |
| DP-05 | 数据库写入   | 所有字段正确存储，JSON字段可解析    |
| DP-06 | 推荐器索引更新 | 新书可被推荐算法检索到           |
| DP-07 | 跨域推荐    | 新书可出现在其他书籍的跨域推荐列表中    |

***

## 七、分阶段实施计划

### 第一阶段：基础框架（核心功能）

| 步骤  | 内容                             | 涉及文件                                        |
| --- | ------------------------------ | ------------------------------------------- |
| 1.1 | 创建豆瓣爬取模块 `douban_scraper.py`   | 新建 `backend/app/services/douban_scraper.py` |
| 1.2 | 创建书籍处理管线 `book_processor.py`   | 新建 `backend/app/services/book_processor.py` |
| 1.3 | 新增 `POST /api/books/add` API端点 | 修改 `backend/app.py`                         |
| 1.4 | 推荐器新增 `add_book_to_index()` 方法 | 修改 `backend/app/services/recommender.py`    |

### 第二阶段：前端交互

| 步骤  | 内容                                           | 涉及文件                              |
| --- | -------------------------------------------- | --------------------------------- |
| 2.1 | 修改 `renderBooks()` 添加"未找到"提示和URL输入框          | 修改 `backend/static/js/main.js`    |
| 2.2 | 实现 `addNewBook()` 和 `validateDoubanUrl()` 函数 | 修改 `backend/static/js/main.js`    |
| 2.3 | 添加相关CSS样式                                    | 修改 `backend/static/css/style.css` |

### 第三阶段：异常处理与优化

| 步骤  | 内容             | 涉及文件                   |
| --- | -------------- | ---------------------- |
| 3.1 | 实现去重检查逻辑       | 修改 `backend/app.py`    |
| 3.2 | 添加超时控制和重试机制    | 修改 `douban_scraper.py` |
| 3.3 | 实现状态反馈机制（进度展示） | 修改前端JS + 后端API         |
| 3.4 | 添加手动填写表单备选方案   | 修改前端JS + CSS + 后端API   |

### 第四阶段：测试与验证

| 步骤  | 内容                    |
| --- | --------------------- |
| 4.1 | 执行前端交互测试用例            |
| 4.2 | 执行后端API测试用例           |
| 4.3 | 执行数据处理测试用例            |
| 4.4 | 端到端测试：添加新书→搜索→推荐→推荐理由 |

***

## 八、文件变更清单

| 操作 | 文件路径                                     | 说明                            |
| -- | ---------------------------------------- | ----------------------------- |
| 新建 | `backend/app/services/douban_scraper.py` | 豆瓣数据爬取模块                      |
| 新建 | `backend/app/services/book_processor.py` | 书籍数据处理管线                      |
| 修改 | `backend/app.py`                         | 新增 `/api/books/add` 端点        |
| 修改 | `backend/app/services/recommender.py`    | 新增 `add_book_to_index()` 方法   |
| 修改 | `backend/static/js/main.js`              | 搜索无结果UI + 添加新书交互              |
| 修改 | `backend/static/css/style.css`           | 新增相关样式                        |
| 修改 | `requirements.txt`                       | 新增 `beautifulsoup4`、`lxml` 依赖 |

