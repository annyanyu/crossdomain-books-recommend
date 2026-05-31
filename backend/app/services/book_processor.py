# -*- coding: utf-8 -*-
"""
书籍数据处理管线
将爬取的原始数据经过与现有系统完全一致的处理流程，生成可入库的完整数据

处理步骤：
1. 关键词提取（jieba + TF-IDF + TextRank 融合，复用已有语料库IDF）
2. 领域标签分配（关键词匹配，与assign_domain_tags.py逻辑一致）
3. 向量生成（BAAI/bge-base-zh-v1.5，与generate_embeddings.py逻辑一致）
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

import jieba
import jieba.analyse
import jieba.posseg as pseg
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

ALLOWED_POS = {
    'n', 'nr', 'ns', 'nt', 'nz', 'ng',
    'vn', 'v', 'vd', 'vi', 'vl', 'vu',
    'a', 'ad', 'an', 'ag', 'al', 'eng'
}


class BookProcessor:
    """
    书籍数据处理管线

    将爬取的原始书籍数据经过关键词提取、领域标签分配、向量生成，
    产出与现有数据库书籍格式完全一致的完整数据。
    """

    def __init__(self, db_config: dict, domain_tags_path: str = None):
        self.db_config = db_config
        self._domain_keywords = None
        self._domain_tags_path = domain_tags_path
        self._corpus_texts_cache = None
        self._embedding_generator = None
        self._title_match_rules = None
        self._idf_cache = {}

        self._level_weights = {'core': 5.0, 'feature': 2.0, 'general': 0.5, 'core_en': 5.0}
        self._title_weight = 3.0
        self._min_score_threshold = 3.0
        self._second_tag_ratio = 0.3

    def process_new_book(self, book_data: Dict) -> Dict:
        """
        完整处理管线：关键词 → 标签 → 向量

        参数:
            book_data: 爬取的原始书籍数据（需包含 title, books_intro, author_intro 等）

        返回:
            处理后的完整书籍数据（含 keywords, domain_tags, embedding, keywords_embeddings）
        """
        logger.info(f"[书籍处理] 开始处理: 《{book_data.get('title', '未知')}》")

        keywords = self._extract_keywords(book_data)
        book_data['keywords'] = json.dumps(keywords, ensure_ascii=False)
        logger.info(f"[书籍处理] 关键词提取完成: {keywords[:5]}... (共{len(keywords)}个)")

        domain_tags = self._assign_domain_tags(book_data)
        book_data['domain_tags'] = json.dumps(domain_tags, ensure_ascii=False)
        book_data['domain'] = json.dumps(domain_tags, ensure_ascii=False)
        logger.info(f"[书籍处理] 领域标签分配完成: {domain_tags}")

        embedding, keywords_embeddings = self._generate_embeddings(book_data, keywords)
        book_data['embedding'] = json.dumps(embedding, ensure_ascii=False)
        book_data['keywords_embeddings'] = json.dumps(keywords_embeddings, ensure_ascii=False)
        logger.info(f"[书籍处理] 向量生成完成: 整体向量768维, 关键词向量{len(keywords_embeddings)}个")

        return book_data

    # ==================== 关键词提取（复用已有语料库IDF） ====================

    def _extract_keywords(self, book_data: Dict, top_k: int = 12) -> List[str]:
        """
        单本书关键词提取（与现有系统 extract_keywords.py 算法完全一致）

        关键设计：加载已有书籍文本作为语料库，使TF-IDF的IDF值与批量处理时一致。
        现有系统用317本书一起fit_transform，我们用317+1本书一起fit_transform，
        IDF值几乎不变（317→318，差异<0.3%），关键词提取质量与现有书籍一致。
        """
        new_text = self._combine_book_text(book_data)
        existing_texts = self._load_existing_book_texts()
        all_texts = existing_texts + [new_text]

        processed_texts = []
        for text in all_texts:
            processed = self._preprocess_text(text)
            words = self._segment_text(processed)
            processed_texts.append(' '.join(words))

        tfidf_keywords = self._extract_tfidf_keywords(processed_texts, top_k * 3)

        textrank_keywords = self._extract_textrank_keywords(new_text, top_k * 2)

        final_keywords = self._merge_keywords(tfidf_keywords, textrank_keywords, top_k)

        return final_keywords

    @staticmethod
    def _combine_book_text(book_data: Dict) -> str:
        """
        拼接书籍文本（与 extract_keywords.py 的 _combine_book_text 一致）
        title*2 + book_intro + author_intro + short_reviews[:5] + reviews[:3] + reading_notes[:3]
        """
        parts = []

        title = book_data.get('title', '')
        if title:
            parts.append(str(title).strip())
            parts.append(str(title).strip())

        for field in ['books_intro', 'book_intro']:
            intro = book_data.get(field, '')
            if intro and str(intro).strip():
                parts.append(str(intro).strip())

        author_intro = book_data.get('author_intro', '')
        if author_intro and str(author_intro).strip():
            parts.append(str(author_intro).strip())

        for json_field, limit in [('short_reviews', 5), ('reviews', 3), ('reading_notes', 3)]:
            items = BookProcessor._safe_parse_json_list(book_data.get(json_field, ''))
            for item in items[:limit]:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())

        return ' '.join(parts)

    def _load_existing_book_texts(self) -> List[str]:
        """
        从数据库加载已有书籍的拼接文本，用于构建TF-IDF语料库
        结果会被缓存，新增书籍后追加到缓存
        """
        if self._corpus_texts_cache is not None:
            return self._corpus_texts_cache

        from sqlalchemy import create_engine, text as sql_text

        connection_str = (
            f"mysql+pymysql://{self.db_config['user']}:{self.db_config['password']}"
            f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
            f"?charset=utf8mb4"
        )
        engine = create_engine(connection_str)

        texts = []
        with engine.connect() as conn:
            query = sql_text(
                "SELECT title, book_intro, author_intro, short_reviews, reviews, reading_notes "
                f"FROM {self.db_config.get('table', 'books')}"
            )
            result = conn.execute(query)
            for row in result:
                row_dict = {
                    'title': row[0],
                    'books_intro': row[1],
                    'author_intro': row[2],
                    'short_reviews': row[3],
                    'reviews': row[4],
                    'reading_notes': row[5],
                }
                combined = self._combine_book_text(row_dict)
                texts.append(combined)

        self._corpus_texts_cache = texts
        logger.info(f"[书籍处理] 加载语料库: {len(texts)}本书")
        return texts

    def add_to_corpus_cache(self, book_data: Dict):
        """新增书籍后，将其文本追加到语料库缓存"""
        if self._corpus_texts_cache is not None:
            new_text = self._combine_book_text(book_data)
            self._corpus_texts_cache.append(new_text)

    @staticmethod
    def _safe_parse_json_list(value) -> List[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    @staticmethod
    def _preprocess_text(text: str) -> str:
        if not text:
            return ''
        text = str(text)
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _segment_text(text: str) -> List[str]:
        if not text:
            return []
        words = pseg.cut(text)
        result = []
        for word, flag in words:
            word = word.strip()
            if not word or len(word) <= 1 or word.isdigit():
                continue
            if flag in ALLOWED_POS or flag.startswith('n') or flag.startswith('v') or flag.startswith('a'):
                result.append(word)
        return result

    @staticmethod
    def _extract_tfidf_keywords(processed_texts: List[str], top_k: int) -> List[str]:
        """
        TF-IDF关键词提取（与 extract_keywords.py 的 extract_tfidf_keywords_batch 一致）
        取最后一本书（新书）的TF-IDF关键词
        """
        if len(processed_texts) < 2:
            return []

        vectorizer = TfidfVectorizer(
            max_features=5000,
            min_df=2,
            max_df=0.85,
            ngram_range=(1, 1)
        )

        tfidf_matrix = vectorizer.fit_transform(processed_texts)
        feature_names = vectorizer.get_feature_names_out()

        new_idx = len(processed_texts) - 1
        tfidf_scores = tfidf_matrix[new_idx].toarray()[0]
        top_indices = np.argsort(tfidf_scores)[-top_k:][::-1]
        keywords = [feature_names[idx] for idx in top_indices if tfidf_scores[idx] > 0]

        return BookProcessor._clean_keywords(keywords)

    @staticmethod
    def _extract_textrank_keywords(text: str, top_k: int) -> List[str]:
        """
        TextRank关键词提取（与 extract_keywords.py 的 extract_textrank_keywords 一致）
        """
        if not text:
            return []

        processed_text = BookProcessor._preprocess_text(text)
        if not processed_text:
            return []

        keywords = jieba.analyse.textrank(
            processed_text,
            topK=top_k,
            withWeight=False,
            allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'ng', 'vn', 'v', 'a', 'an', 'ad', 'eng')
        )

        return BookProcessor._clean_keywords(list(keywords))

    @staticmethod
    def _merge_keywords(tfidf_keywords: List[str], textrank_keywords: List[str],
                        top_k: int = 12) -> List[str]:
        """
        融合TF-IDF和TextRank关键词（与 extract_keywords.py 的 merge_keywords 一致）
        TF-IDF权重x2，TextRank权重x1
        """
        keyword_scores = {}

        for idx, keyword in enumerate(tfidf_keywords):
            score = (len(tfidf_keywords) - idx) * 2
            keyword_scores[keyword] = keyword_scores.get(keyword, 0) + score

        for idx, keyword in enumerate(textrank_keywords):
            score = len(textrank_keywords) - idx
            keyword_scores[keyword] = keyword_scores.get(keyword, 0) + score

        sorted_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
        final_keywords = [keyword for keyword, score in sorted_keywords[:top_k]]
        final_keywords = BookProcessor._clean_keywords(final_keywords)

        return final_keywords

    @staticmethod
    def _clean_keywords(keywords: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for kw in keywords:
            kw = str(kw).strip()
            if not kw or len(kw) <= 1 or kw.isdigit():
                continue
            if re.match(r'^[a-zA-Z]$', kw):
                continue
            if re.match(r'^\d+$', kw):
                continue
            if kw in seen:
                continue
            seen.add(kw)
            cleaned.append(kw)
        return cleaned

    # ==================== 领域标签分配（与 assign_domain_tags.py 一致） ====================

    def _assign_domain_tags(self, book_data: Dict, max_domains: int = 2) -> List[str]:
        domain_keywords = self._get_domain_keywords()
        title_match = self._check_title_match(book_data.get('title', ''))
        if title_match is not None:
            return title_match

        title = book_data.get('title', '')
        intro = book_data.get('books_intro', '') or book_data.get('book_intro', '')
        author_intro = book_data.get('author_intro', '')

        title_processed = self._preprocess_text(title).lower()
        intro_processed = self._preprocess_text(intro).lower()
        author_processed = self._preprocess_text(author_intro).lower()

        combined_text = f"{intro_processed} {author_processed}"

        if not combined_text.strip() and not title_processed.strip():
            return ["其他"]

        is_english = self._is_english_text(f"{title_processed} {combined_text}")

        scores = {}
        for domain_name, kw_dict in domain_keywords.items():
            score = self._calculate_domain_score(combined_text, title_processed, kw_dict, is_english)
            scores[domain_name] = score

        return self._get_top_domains(scores, max_domains)

    def _calculate_domain_score(self, text: str, title_text: str,
                                kw_dict: Dict, is_english: bool) -> float:
        score = 0.0
        levels = ['core_en', 'feature'] if is_english else ['core', 'feature', 'general']

        for level in levels:
            keywords = kw_dict.get(level, [])
            if not keywords:
                continue
            weight = self._level_weights.get(level, 1.0)
            for keyword in keywords:
                kw_lower = keyword.lower()
                count_title = title_text.count(kw_lower)
                count_body = text.count(kw_lower)
                title_boost = count_title * (self._title_weight - 1.0)
                body_count = count_body + count_title
                idf = self._idf_cache.get(kw_lower, 1.0)
                score += weight * idf * (body_count + title_boost)
        return score

    def _is_english_text(self, text: str) -> bool:
        latin = len(re.findall(r'[a-zA-Z]', text))
        chinese = len(re.findall(r'[\u4e00-\u9fa5]', text))
        total = latin + chinese
        if total == 0:
            return False
        return latin / total > 0.6

    def _check_title_match(self, title: str) -> Optional[List[str]]:
        rules = self._get_title_match_rules()
        if not rules:
            return None
        for pattern, tags in rules.items():
            if pattern in title.strip():
                return tags
        return None

    def _get_title_match_rules(self) -> Dict:
        if self._title_match_rules is not None:
            return self._title_match_rules
        rules_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            'algorithms', 'scripts', 'title_match_rules.json'
        )
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                self._title_match_rules = json.load(f)
        else:
            self._title_match_rules = {}
        return self._title_match_rules

    def _get_top_domains(self, scores: Dict[str, float], max_domains: int = 2) -> List[str]:
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        valid_domains = [(d, s) for d, s in sorted_domains if s > 0]
        if not valid_domains:
            return ["其他"]
        top_domain, top_score = valid_domains[0]
        if top_score < self._min_score_threshold:
            return ["其他"]
        threshold = max(self._min_score_threshold, self._second_tag_ratio * top_score)
        result = [top_domain]
        for domain, score in valid_domains[1:max_domains]:
            if score >= threshold:
                result.append(domain)
        return result

    def _get_domain_keywords(self) -> Dict[str, Dict[str, List[str]]]:
        if self._domain_keywords is not None:
            return self._domain_keywords

        config_path = self._domain_tags_path
        if not config_path:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                'algorithms', 'scripts', 'domain_tags.json'
            )

        if not os.path.exists(config_path):
            logger.warning(f"[书籍处理] 领域标签配置文件不存在: {config_path}，使用默认标签")
            self._domain_keywords = {"其他": {"core": ["图书", "书籍"], "feature": [], "general": [], "core_en": []}}
            return self._domain_keywords

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        domain_keywords = {}
        for domain_info in config:
            domain_name = domain_info['domain']
            kw = domain_info.get('keywords', {})
            if isinstance(kw, list):
                domain_keywords[domain_name] = {'core': kw, 'feature': [], 'general': [], 'core_en': []}
            elif isinstance(kw, dict):
                domain_keywords[domain_name] = {
                    'core': kw.get('core', []),
                    'feature': kw.get('feature', []),
                    'general': kw.get('general', []),
                    'core_en': kw.get('core_en', []),
                }

        self._domain_keywords = domain_keywords
        return domain_keywords

    # ==================== 向量生成（与 generate_embeddings.py 一致） ====================

    def _generate_embeddings(self, book_data: Dict, keywords: List[str]) -> Tuple[List[float], List[List[float]]]:
        """
        向量生成（与 generate_embeddings.py 逻辑完全一致）
        使用 BAAI/bge-base-zh-v1.5 模型生成768维向量
        BGE模型不可用时使用TF-IDF+SVD降级方案
        """
        generator = self._get_embedding_generator()

        concatenated_text = self._concatenate_book_text_for_embedding(book_data)

        if not concatenated_text or not concatenated_text.strip():
            zero_embedding = [0.0] * 768
            zero_kw_embeddings = [[0.0] * 768 for _ in keywords] if keywords else []
            return zero_embedding, zero_kw_embeddings

        overall_embedding = generator.generate_overall_embedding(concatenated_text)

        if keywords:
            parsed_keywords = self._safe_parse_json_list(keywords) if isinstance(keywords, str) else keywords
            keywords_embeddings = generator.generate_keyword_embeddings_batch(parsed_keywords)
        else:
            keywords_embeddings = []

        return overall_embedding, keywords_embeddings

    def _get_embedding_generator(self):
        """获取向量生成器（单例模式，延迟加载BGE模型）"""
        if self._embedding_generator is not None:
            return self._embedding_generator

        sys_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        algorithms_path = os.path.join(os.path.dirname(sys_path), 'algorithms', 'scripts')
        import sys
        if algorithms_path not in sys.path:
            sys.path.insert(0, algorithms_path)

        try:
            from generate_embeddings import BookEmbeddingGenerator
            self._embedding_generator = BookEmbeddingGenerator()
            logger.info("[书籍处理] BGE向量生成器创建成功")
        except ImportError as e:
            logger.warning(f"[书籍处理] 无法导入BookEmbeddingGenerator: {e}，将使用TF-IDF降级方案")
            self._embedding_generator = BookEmbeddingGenerator()
        except Exception as e:
            logger.warning(f"[书籍处理] 向量生成器初始化失败: {e}，将使用降级方案")
            self._embedding_generator = _FallbackEmbeddingGenerator()

        return self._embedding_generator

    @staticmethod
    def _concatenate_book_text_for_embedding(book_data: Dict) -> str:
        """
        拼接文本用于整体向量生成（与 generate_embeddings.py 的 _concatenate_book_text 一致）
        title + book_intro + author_intro + short_reviews + reviews + reading_notes
        """
        text_parts = []

        title = book_data.get('title', '')
        if title:
            text_parts.append(str(title))

        for field in ['books_intro', 'book_intro']:
            intro = book_data.get(field, '')
            if intro and str(intro).strip():
                text_parts.append(str(intro).strip())

        author_intro = book_data.get('author_intro', '')
        if author_intro and str(author_intro).strip():
            text_parts.append(str(author_intro).strip())

        for json_field in ['short_reviews', 'reviews', 'reading_notes']:
            items = BookProcessor._safe_parse_json_list(book_data.get(json_field, ''))
            for item in items:
                if isinstance(item, str) and item.strip():
                    text_parts.append(item.strip())

        return ' '.join(text_parts)


class _FallbackEmbeddingGenerator:
    """TF-IDF+SVD降级向量生成器"""

    def generate_overall_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * 768

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD

        vectorizer = TfidfVectorizer(max_features=768)
        tfidf_matrix = vectorizer.fit_transform([text])

        if tfidf_matrix.shape[1] < 768:
            padding = np.zeros((1, 768 - tfidf_matrix.shape[1]))
            embedding = np.hstack([tfidf_matrix.toarray(), padding])[0]
        else:
            svd = TruncatedSVD(n_components=768, random_state=42)
            embedding = svd.fit_transform(tfidf_matrix)[0]

        return embedding.tolist()

    def generate_keyword_embeddings_batch(self, keywords: List[str]) -> List[List[float]]:
        if not keywords:
            return []
        return [self.generate_overall_embedding(kw) for kw in keywords if kw and kw.strip()]
