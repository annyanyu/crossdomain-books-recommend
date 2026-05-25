# 跨域图书推荐理由生成 — 实施计划

## 一、需求分析

### 1.1 核心目标

在推荐系统生成书籍推荐结果时，为每本推荐书籍调用大模型生成简洁易懂的推荐理由，提升推荐结果的可解释性。

### 1.2 推荐理由需包含的内容

1. **推荐书籍的核心内容与价值** — 该书讲了什么，有何独特价值
2. **与用户已选书籍的知识关联** — 主题相关性、知识体系延续性、观点互补性、应用场景关联性
3. **对用户的参考价值** — 为何认为该书籍对用户具有参考价值

### 1.3 当前系统可用的数据资源

| 数据来源        | 可用字段                                                                                                  | 用途           |
| ----------- | ----------------------------------------------------------------------------------------------------- | ------------ |
| 源图书（用户选中的书） | title, authors, domain\_tags, book\_intro, keywords                                                   | 构建源书上下文      |
| 推荐图书        | title, authors, domain\_tags, book\_intro, keywords, rating                                           | 构建推荐书上下文     |
| 推荐算法        | semantic\_similarity, keyword\_similarity, overlap\_count, overlap\_coefficient, combined\_similarity | 提供关联性量化依据    |
| 数据库         | short\_reviews, reviews, also\_like                                                                   | 补充读者评价视角（可选） |

***

## 二、大模型选型分析

### 2.1 候选方案对比

| 方案                      | 模型            | 中文能力  | 成本             | 延迟     | 部署难度   | 推荐理由生成质量 |
| ----------------------- | ------------- | ----- | -------------- | ------ | ------ | -------- |
| **DeepSeek API**        | deepseek-chat | ★★★★★ | 极低（1元/百万token） | \~1-2s | 低      | 优秀，推理能力强 |
| **智谱 GLM-4-Flash**      | glm-4-flash   | ★★★★★ | 免费             | \~1-2s | 低      | 良好，中文原生  |
| **OpenAI GPT-4o-mini**  | gpt-4o-mini   | ★★★★☆ | 中等             | \~1-3s | 中（需代理） | 优秀       |
| **本地 Ollama + Qwen2.5** | qwen2.5:7b    | ★★★★☆ | 免费（需GPU）       | \~3-8s | 高      | 良好       |

### 2.2 推荐方案：DeepSeek API

**选择理由：**

1. **中文理解与生成能力极强** — DeepSeek在中文文本生成任务上表现优异，尤其擅长结构化推理
2. **成本极低** — 输入1元/百万token，输出2元/百万token，6本推荐书的理由生成单次成本约0.01元
3. **API兼容OpenAI格式** — 可使用 `openai` SDK，代码迁移成本低
4. **无需代理** — 国内直连，延迟低
5. **推理能力强** — 能根据相似度分数和领域标签进行合理的关联性推理

**备选方案：** 智谱 GLM-4-Flash（免费额度充足，作为降级备选）

### 2.3 架构设计原则

采用**策略模式**设计LLM调用层，支持多后端切换：

* 主力：DeepSeek API

* 备选：智谱 GLM-4-Flash

* 本地：Ollama（离线场景）

* 降级：基于模板的规则生成（无LLM可用时）

***

## 三、系统架构设计

### 3.1 整体流程

```
用户选择图书 → 推荐算法生成候选 → 排序截取top_k
                                          ↓
                              并行调用LLM生成推荐理由
                              （每本推荐书一个请求）
                                          ↓
                              推荐理由写入响应 → 前端展示
```

### 3.2 异步优化策略

由于LLM调用存在延迟（1-3s/本），采用**两阶段响应**策略：

**方案A：异步流式返回（推荐）**

1. 推荐API先返回基础推荐结果（无推荐理由），前端立即渲染
2. 前端对每本推荐书发起独立的推荐理由请求（`/api/recommend-reason`）
3. 推荐理由逐条返回，前端动态插入DOM

**优点：** 用户无需等待所有理由生成完毕，体验流畅
**缺点：** 请求次数增多

**方案B：同步批量返回**

1. 推荐API等待所有推荐理由生成完毕后一次性返回
2. 前端等待时间较长（6本×2s ≈ 12s）

**选择方案A**，因为用户体验优先。

### 3.3 缓存策略

* 对同一 `(source_book_id, recommended_book_id, beta)` 组合的推荐理由进行缓存

* 缓存存储：内存字典（项目规模小，无需Redis）

* 缓存失效：服务重启时清空

***

## 四、详细实施步骤

### 步骤1：创建LLM服务模块

**文件：** `backend/app/services/llm_service.py`

功能：

* 定义 `LLMService` 基类和 `DeepSeekLLM`、`ZhipuLLM`、`OllamaLLM` 实现类

* 定义 `TemplateLLM` 降级实现（基于模板规则生成理由，无需API调用）

* 统一接口：`generate_reason(source_book, recommended_book, similarity_data) -> str`

* 支持通过 `config.json` 配置LLM后端和API Key

**Prompt设计：**

```
你是一位专业的图书推荐顾问。请根据以下信息，为推荐书籍生成一段简洁的推荐理由（80-120字）。

【用户选中的书籍】
书名：《{source_title}》
作者：{source_authors}
领域：{source_domain_tags}
简介：{source_intro_snippet}

【推荐书籍】
书名：《{rec_title}》
作者：{rec_authors}
领域：{rec_domain_tags}
简介：{rec_intro_snippet}
评分：{rec_rating}

【关联分析数据】
语义相似度：{semantic_similarity}
关键词相似度：{keyword_similarity}
领域重叠数：{overlap_count}
跨域类型：{"完全跨域" if overlap_count == 0 else "部分跨域"}

请从以下三个角度阐述推荐理由：
1. 推荐书籍的核心内容与价值
2. 两本书之间的知识关联（主题相关性/知识延续/观点互补/场景关联）
3. 对用户的参考价值

要求：语言简洁专业，避免空洞表述，直接点明关联点。
```

### 步骤2：修改配置文件

**文件：** `backend/config.json`

新增 `llm` 配置段：

```json
{
    "llm": {
        "provider": "deepseek",
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "max_tokens": 200,
        "temperature": 0.7,
        "timeout": 10,
        "fallback_provider": "template"
    }
}
```

### 步骤3：添加推荐理由API端点

**文件：** `backend/app.py`

新增端点 `POST /api/recommend-reason`：

* 请求体：`{ source_book_id, recommended_book_id, similarity_data }`

* 响应：`{ success, data: { reason, source_book_id, recommended_book_id } }`

* 从数据库查询两本书的详细信息（title, authors, domain\_tags, book\_intro, keywords）

* 调用 LLM 服务生成推荐理由

* 返回推荐理由文本

### 步骤4：修改推荐API响应结构

**文件：** `backend/app.py`

在 `/api/recommend/<book_id>` 的响应中，为每条推荐结果额外返回以下字段：

* `has_reason_support: true` — 标记支持推荐理由功能

* 前端据此判断是否显示"查看推荐理由"入口

### 步骤5：前端推荐理由展示

**文件：** `backend/static/js/main.js`

1. 在 `renderRecommendationItem()` 中为每本推荐书添加"推荐理由"展开区域
2. 新增 `loadRecommendReason(sourceBookId, recommendedBookId, similarityData)` 函数
3. 点击"查看推荐理由"按钮时：

   * 显示加载动画

   * 调用 `/api/recommend-reason` API

   * 将返回的理由文本插入DOM
4. 推荐理由展示样式：在推荐卡片下方展开，带渐入动画

**文件：** `backend/static/css/style.css`

1. 新增 `.recommendation-reason` 样式区域
2. 推荐理由文字样式：浅色背景、左侧竖线装饰、适当字号
3. 加载状态动画
4. 展开/收起过渡动画

### 步骤6：模板降级方案实现

**文件：** `backend/app/services/llm_service.py`

当LLM API不可用时，基于规则模板生成推荐理由：

* 根据 `overlap_count` 判断跨域类型

* 根据 `semantic_similarity` 和 `keyword_similarity` 判断关联程度

* 根据 `domain_tags` 差集判断知识拓展方向

* 组合模板生成基本可读的推荐理由

### 步骤7：安装依赖与测试

1. 在 `requirements.txt` 中添加 `openai>=1.0.0`
2. 配置 `config.json` 中的 API Key
3. 端到端测试：选书 → 获取推荐 → 查看推荐理由
4. 降级测试：断开API → 验证模板降级

***

## 五、文件修改清单

| 文件                                    | 操作   | 说明                            |
| ------------------------------------- | ---- | ----------------------------- |
| `backend/app/services/llm_service.py` | 新建   | LLM服务模块（多后端+模板降级）             |
| `backend/app.py`                      | 修改   | 新增 `/api/recommend-reason` 端点 |
| `backend/config.json`                 | 修改   | 新增 `llm` 配置段                  |
| `backend/static/js/main.js`           | 修改   | 推荐理由加载与展示交互                   |
| `backend/static/css/style.css`        | 修改   | 推荐理由样式                        |
| `backend/templates/index.html`        | 无需修改 | 推荐理由区域由JS动态生成                 |
| `requirements.txt`                    | 修改   | 添加 `openai>=1.0.0`            |

***

## 六、智能体能力评估

### 6.1 可用智能体分析

| 智能体                         | 自然语言生成 | 知识关联分析 | 跨书籍内容理解 | 适合度    |
| --------------------------- | ------ | ------ | ------- | ------ |
| **ai-integration-engineer** | ★★★★★  | ★★★★☆  | ★★★★☆   | **最佳** |
| backend-architect           | ★★☆☆☆  | ★★★★★  | ★★☆☆☆   | 适合架构设计 |
| frontend-architect          | ★★☆☆☆  | ★☆☆☆☆  | ★☆☆☆☆   | 仅适合前端  |
| search                      | ★☆☆☆☆  | ★☆☆☆☆  | ★☆☆☆☆   | 仅适合检索  |

### 6.2 推荐智能体

**ai-integration-engineer** 是最适合执行此任务的智能体，原因：

1. **核心任务是LLM集成** — 需要设计Prompt、调用API、处理响应，这正是AI集成工程师的专长
2. **需要理解推荐算法** — 将相似度数据转化为Prompt中的关联分析依据
3. **需要设计降级策略** — 当LLM不可用时提供基于规则的替代方案
4. **需要处理异步交互** — 前端异步请求推荐理由的交互设计

***

## 七、风险与应对

| 风险         | 影响       | 应对措施                |
| ---------- | -------- | ------------------- |
| LLM API不可用 | 推荐理由无法生成 | 模板降级方案，基于规则生成基本理由   |
| LLM响应延迟高   | 用户体验差    | 异步加载，先展示推荐结果再加载理由   |
| API Key泄露  | 安全风险     | 配置文件不纳入版本控制，环境变量覆盖  |
| 生成内容质量不稳定  | 推荐理由不可靠  | Prompt工程优化 + 温度参数调优 |
| 并发请求过多     | API限流    | 缓存机制 + 请求合并         |

