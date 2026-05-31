# -*- coding: utf-8 -*-
"""
also_like书名到book_id的映射器

功能：
1. 从数据库构建书名索引（小写书名 -> book_id）
2. 精确匹配：直接比对title字段
3. 模糊匹配：基于编辑距离相似度（difflib.SequenceMatcher）
4. 综合匹配：先精确匹配，再模糊匹配

作者：系统自动生成
日期：2026-05-30
"""

import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class AlsoLikeMapper:
    """also_like书名到book_id的映射器"""

    def __init__(self, engine):
        """
        初始化映射器

        参数:
            engine: SQLAlchemy数据库引擎
        """
        self.engine = engine
        self._title_index = None  # {title_lower: book_id}

    def build_title_index(self):
        """从数据库构建书名索引（小写书名 -> book_id的映射）"""
        from sqlalchemy import text

        self._title_index = {}
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT book_id, title FROM books WHERE title IS NOT NULL")
            )
            for row in result:
                book_id = row[0]
                title = row[1]
                if title and str(title).strip():
                    key = str(title).strip().lower()
                    # 如果有重复的小写书名，保留第一个（book_id较小的）
                    if key not in self._title_index:
                        self._title_index[key] = book_id

        logger.info(f"[AlsoLikeMapper] 书名索引构建完成: {len(self._title_index)}条记录")

    def exact_match(self, book_name: str) -> tuple:
        """
        精确匹配：直接比对title字段

        参数:
            book_name: 待匹配的书名

        返回:
            (book_id, match_score) 或 (None, 0.0)
        """
        if not self._title_index:
            logger.warning("[AlsoLikeMapper] 书名索引未构建，请先调用build_title_index()")
            return None, 0.0

        if not book_name or not str(book_name).strip():
            return None, 0.0

        key = str(book_name).strip().lower()
        if key in self._title_index:
            return self._title_index[key], 1.0

        return None, 0.0

    def fuzzy_match(self, book_name: str, threshold: float = 0.6) -> tuple:
        """
        模糊匹配：基于编辑距离相似度
        使用 difflib.SequenceMatcher 计算相似度

        参数:
            book_name: 待匹配的书名
            threshold: 最低相似度阈值（默认0.6）

        返回:
            (book_id, match_score) 或 (None, 0.0)
        """
        if not self._title_index:
            logger.warning("[AlsoLikeMapper] 书名索引未构建，请先调用build_title_index()")
            return None, 0.0

        if not book_name or not str(book_name).strip():
            return None, 0.0

        query = str(book_name).strip().lower()
        best_score = 0.0
        best_book_id = None

        for title_lower, book_id in self._title_index.items():
            # 跳过完全相同的（已经由精确匹配处理）
            if title_lower == query:
                continue

            score = SequenceMatcher(None, query, title_lower).ratio()
            if score > best_score:
                best_score = score
                best_book_id = book_id

        if best_score >= threshold and best_book_id is not None:
            return best_book_id, round(best_score, 4)

        return None, 0.0

    def match_book_name(self, book_name: str) -> dict:
        """
        综合匹配：先精确匹配，再模糊匹配

        参数:
            book_name: 待匹配的书名

        返回:
            {
                'target_book_id': int or None,
                'match_type': 'exact' | 'fuzzy' | 'unmatched',
                'match_score': float
            }
        """
        if not book_name or not str(book_name).strip():
            return {
                'target_book_id': None,
                'match_type': 'unmatched',
                'match_score': 0.0
            }

        # 1. 先尝试精确匹配
        book_id, score = self.exact_match(book_name)
        if book_id is not None:
            return {
                'target_book_id': book_id,
                'match_type': 'exact',
                'match_score': score
            }

        # 2. 再尝试模糊匹配
        book_id, score = self.fuzzy_match(book_name)
        if book_id is not None:
            return {
                'target_book_id': book_id,
                'match_type': 'fuzzy',
                'match_score': score
            }

        # 3. 未匹配
        return {
            'target_book_id': None,
            'match_type': 'unmatched',
            'match_score': 0.0
        }
