# -*- coding: utf-8 -*-
"""
图书关键词提取模块
基于TF-IDF和TextRank算法提取图书文本关键词

功能说明：
1. 支持从数据库读取图书数据
2. 使用批量TF-IDF算法提取关键词（跨文档计算IDF）
3. 使用TextRank算法提取关键词（含词性过滤）
4. 融合两种算法结果，生成最终关键词列表
5. 支持批量处理和单本书处理
6. 扩展输入源：title + books_intro + author_intro + short_reviews + reviews + reading_notes

作者：系统自动生成
日期：2025-03-22
"""

import pandas as pd
import numpy as np
import jieba
import jieba.analyse
import jieba.posseg as pseg
from sklearn.feature_extraction.text import TfidfVectorizer
import re
from typing import List, Dict, Tuple, Optional
import json
import os


class KeywordExtractor:
    """
    关键词提取器类
    
    使用TF-IDF和TextRank两种算法提取关键词，并融合结果
    """

    ALLOWED_POS = {'n', 'nr', 'ns', 'nt', 'nz', 'ng', 'vn', 'v', 'vd', 'vi', 'vl', 'vu', 'a', 'ad', 'an', 'ag', 'al', 'eng'}

    def __init__(self, stopwords_path: str = None):
        if stopwords_path is None:
            stopwords_path = os.path.join(os.path.dirname(__file__), 'stopwords.txt')
        self.stopwords = self._load_stopwords(stopwords_path)
        self.tfidf_vectorizer = None

    def _load_stopwords(self, stopwords_path: str = None) -> set:
        stopwords = set()
        if os.path.exists(stopwords_path):
            with open(stopwords_path, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip()
                    if word:
                        stopwords.add(word.lower())
                        stopwords.add(word)
        else:
            print(f"警告：停用词表文件 {stopwords_path} 不存在，使用空停用词表")
        return stopwords

    def _preprocess_text(self, text) -> str:
        if pd.isna(text) or text is None:
            return ""
        text = str(text)
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _segment_with_pos(self, text: str) -> List[Tuple[str, str]]:
        if not text:
            return []
        words = pseg.cut(text)
        result = []
        for word, flag in words:
            word = word.strip()
            if not word:
                continue
            if word.lower() in self.stopwords or word in self.stopwords:
                continue
            if len(word) <= 1:
                continue
            if word.isdigit():
                continue
            if re.match(r'^[a-zA-Z]$', word):
                continue
            result.append((word, flag))
        return result

    def _segment_text(self, text: str) -> List[str]:
        pos_words = self._segment_with_pos(text)
        return [word for word, flag in pos_words if flag in self.ALLOWED_POS or flag.startswith('n') or flag.startswith('v') or flag.startswith('a')]

    def _safe_parse_json_list(self, value) -> List[str]:
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

    def _combine_book_text(self, row: pd.Series) -> str:
        parts = []

        if pd.notna(row.get('title', '')):
            title = str(row['title']).strip()
            if title:
                parts.append(title)
                parts.append(title)

        if pd.notna(row.get('book_intro', '')):
            intro = str(row['book_intro']).strip()
            if intro:
                parts.append(intro)

        if pd.notna(row.get('author_intro', '')):
            author_intro = str(row['author_intro']).strip()
            if author_intro:
                parts.append(author_intro)

        short_reviews = self._safe_parse_json_list(row.get('short_reviews', ''))
        if short_reviews:
            for review in short_reviews[:5]:
                if isinstance(review, str) and review.strip():
                    parts.append(review.strip())

        reviews = self._safe_parse_json_list(row.get('reviews', ''))
        if reviews:
            for review in reviews[:3]:
                if isinstance(review, str) and review.strip():
                    parts.append(review.strip())

        reading_notes = self._safe_parse_json_list(row.get('reading_notes', ''))
        if reading_notes:
            for note in reading_notes[:3]:
                if isinstance(note, str) and note.strip():
                    parts.append(note.strip())

        return ' '.join(parts)

    def extract_tfidf_keywords_batch(self, texts: List[str], top_k: int = 10) -> List[List[str]]:
        if not texts:
            return []

        processed_texts = []
        for text in texts:
            processed_text = self._preprocess_text(text)
            words = self._segment_text(processed_text)
            processed_texts.append(' '.join(words))

        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=5000,
            min_df=2,
            max_df=0.85,
            ngram_range=(1, 1)
        )

        tfidf_matrix = self.tfidf_vectorizer.fit_transform(processed_texts)
        feature_names = self.tfidf_vectorizer.get_feature_names_out()

        all_keywords = []
        for i in range(len(texts)):
            tfidf_scores = tfidf_matrix[i].toarray()[0]
            top_indices = np.argsort(tfidf_scores)[-top_k * 3:][::-1]
            keywords = [feature_names[idx] for idx in top_indices if tfidf_scores[idx] > 0]
            keywords = self._clean_keywords(keywords)
            all_keywords.append(keywords[:top_k])

        return all_keywords

    def extract_textrank_keywords(self, text: str, top_k: int = 10) -> List[str]:
        if not text:
            return []

        processed_text = self._preprocess_text(text)
        if not processed_text:
            return []

        keywords = jieba.analyse.textrank(
            processed_text,
            topK=top_k * 2,
            withWeight=False,
            allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'ng', 'vn', 'v', 'a', 'an', 'ad', 'eng')
        )

        keywords = self._clean_keywords(list(keywords))
        return keywords[:top_k]

    def _clean_keywords(self, keywords: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for kw in keywords:
            kw = kw.strip()
            if not kw:
                continue
            if kw.lower() in self.stopwords or kw in self.stopwords:
                continue
            if len(kw) <= 1:
                continue
            if kw.isdigit():
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

    def merge_keywords(self, tfidf_keywords: List[str], textrank_keywords: List[str],
                      top_k: int = 10) -> List[str]:
        keyword_scores = {}

        for idx, keyword in enumerate(tfidf_keywords):
            score = (len(tfidf_keywords) - idx) * 2
            keyword_scores[keyword] = keyword_scores.get(keyword, 0) + score

        for idx, keyword in enumerate(textrank_keywords):
            score = len(textrank_keywords) - idx
            keyword_scores[keyword] = keyword_scores.get(keyword, 0) + score

        sorted_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
        final_keywords = [keyword for keyword, score in sorted_keywords[:top_k]]
        final_keywords = self._clean_keywords(final_keywords)

        return final_keywords

    def extract_keywords_for_book(self, content_intro: str, author_intro: str,
                                  top_k: int = 10, **kwargs) -> List[str]:
        combined_text = f"{content_intro} {author_intro}"

        if kwargs.get('title'):
            combined_text = f"{kwargs['title']} {combined_text}"

        processed_text = self._preprocess_text(combined_text)

        textrank_keywords = self.extract_textrank_keywords(processed_text, top_k * 2)

        words = self._segment_text(processed_text)
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        tfidf_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        tfidf_keywords = [word for word, freq in tfidf_keywords[:top_k * 2]]

        final_keywords = self.merge_keywords(tfidf_keywords, textrank_keywords, top_k)

        return final_keywords

    def extract_keywords_batch(self, df: pd.DataFrame, top_k: int = 10) -> pd.DataFrame:
        print(f"正在为 {len(df)} 本书批量提取关键词...")

        combined_texts = []
        for idx, row in df.iterrows():
            combined = self._combine_book_text(row)
            combined_texts.append(combined)

        print("步骤1: 批量TF-IDF关键词提取...")
        tfidf_keywords_list = self.extract_tfidf_keywords_batch(combined_texts, top_k=top_k)

        print("步骤2: TextRank关键词提取...")
        textrank_keywords_list = []
        for i, text in enumerate(combined_texts):
            tr_kw = self.extract_textrank_keywords(text, top_k=top_k)
            textrank_keywords_list.append(tr_kw)
            if (i + 1) % 50 == 0:
                print(f"  TextRank已处理 {i + 1}/{len(combined_texts)} 本书")

        print("步骤3: 融合关键词...")
        final_keywords_list = []
        for i in range(len(df)):
            merged = self.merge_keywords(tfidf_keywords_list[i], textrank_keywords_list[i], top_k)
            final_keywords_list.append(merged)

        df = df.copy()
        df['keywords'] = final_keywords_list

        return df


class BookDataLoader:
    def __init__(self, source_type: str = 'mysql', source_config: Dict = None):
        self.source_type = source_type
        self.source_config = source_config or {}

    def load_from_mysql(self, config: Dict) -> pd.DataFrame:
        try:
            import pymysql

            conn = pymysql.connect(
                host=config['host'],
                port=config.get('port', 3306),
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset='utf8mb4'
            )

            table_name = config.get('table', 'books')
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql(query, conn)

            conn.close()
            return df

        except ImportError as e:
            print(f"错误：缺少必要的依赖包。请安装: pip install pymysql pandas")
            raise e
        except Exception as e:
            print(f"从MySQL加载数据时出错: {e}")
            raise e

    def load_from_postgresql(self, config: Dict) -> pd.DataFrame:
        try:
            from sqlalchemy import create_engine
            import psycopg2

            connection_str = f"postgresql+psycopg2://{config['user']}:{config['password']}@{config['host']}:{config.get('port', 5432)}/{config['database']}?charset=utf8mb4"
            engine = create_engine(connection_str)
            query = f"SELECT * FROM {config.get('table', 'books')}"
            df = pd.read_sql(query, engine)
            return df

        except ImportError as e:
            print(f"错误：缺少必要的依赖包。请安装: pip install psycopg2-binary sqlalchemy")
            raise e
        except Exception as e:
            print(f"从PostgreSQL加载数据时出错: {e}")
            raise e

    def load_from_mongodb(self, config: Dict) -> pd.DataFrame:
        try:
            from pymongo import MongoClient

            client = MongoClient(
                host=config['host'],
                port=config.get('port', 27017),
                username=config.get('user'),
                password=config.get('password')
            )

            db = client[config['database']]
            collection = db[config.get('collection', 'books')]
            data = list(collection.find())
            df = pd.DataFrame(data)

            if '_id' in df.columns:
                df = df.drop('_id', axis=1)

            return df

        except ImportError as e:
            print(f"错误：缺少必要的依赖包。请安装: pip install pymongo")
            raise e
        except Exception as e:
            print(f"从MongoDB加载数据时出错: {e}")
            raise e

    def load_data(self, **kwargs) -> pd.DataFrame:
        if self.source_type == 'mysql':
            config = {**self.source_config, **kwargs}
            return self.load_from_mysql(config)
        elif self.source_type == 'postgresql':
            config = {**self.source_config, **kwargs}
            return self.load_from_postgresql(config)
        elif self.source_type == 'mongodb':
            config = {**self.source_config, **kwargs}
            return self.load_from_mongodb(config)
        else:
            raise ValueError(f"不支持的数据源类型: {self.source_type}")


class BookDataSaver:
    def __init__(self, target_type: str = 'mysql', target_config: Dict = None):
        self.target_type = target_type
        self.target_config = target_config or {}

    def save_to_mysql(self, df: pd.DataFrame, config: Dict):
        try:
            import pymysql

            conn = pymysql.connect(
                host=config['host'],
                port=config.get('port', 3306),
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset='utf8mb4'
            )

            table_name = config.get('table', 'books')

            with conn.cursor() as cursor:
                for idx, row in df.iterrows():
                    book_id = row['book_id']

                    update_parts = []
                    update_values = []

                    if 'keywords' in df.columns:
                        keywords = row['keywords']
                        if isinstance(keywords, list):
                            update_parts.append("keywords = %s")
                            update_values.append(json.dumps(keywords, ensure_ascii=False))

                    if 'domain' in df.columns:
                        domain = row['domain']
                        if isinstance(domain, list):
                            update_parts.append("domain_tags = %s")
                            update_values.append(json.dumps(domain, ensure_ascii=False))

                    if update_parts:
                        update_sql = f"UPDATE {table_name} SET {', '.join(update_parts)} WHERE book_id = %s"
                        update_values.append(book_id)
                        cursor.execute(update_sql, update_values)

                        if idx < 3:
                            print(f"更新记录 {book_id}: {', '.join(update_parts)}")
                            if 'keywords' in df.columns:
                                print(f"  keywords: {json.dumps(keywords, ensure_ascii=False)[:80]}...")
                            if 'domain' in df.columns:
                                print(f"  domain: {json.dumps(domain, ensure_ascii=False)}")

                conn.commit()

            conn.close()
            print(f"数据已保存到MySQL数据库的 {table_name} 表")

        except ImportError as e:
            print(f"错误：缺少必要的依赖包。请安装: pip install pymysql")
            raise e
        except Exception as e:
            print(f"保存数据到MySQL时出错: {e}")
            raise e

    def save_to_postgresql(self, df: pd.DataFrame, config: Dict):
        try:
            from sqlalchemy import create_engine
            import psycopg2

            connection_str = f"postgresql+psycopg2://{config['user']}:{config['password']}@{config['host']}:{config.get('port', 5432)}/{config['database']}?charset=utf8mb4"
            engine = create_engine(connection_str)
            table_name = config.get('table', 'books')
            df.to_sql(table_name, engine, if_exists='replace', index=False)
            print(f"数据已保存到PostgreSQL数据库的 {table_name} 表")

        except ImportError as e:
            print(f"错误：缺少必要的依赖包。请安装: pip install psycopg2-binary sqlalchemy")
            raise e
        except Exception as e:
            print(f"保存数据到PostgreSQL时出错: {e}")
            raise e

    def save_to_mongodb(self, df: pd.DataFrame, config: Dict):
        try:
            from pymongo import MongoClient

            client = MongoClient(
                host=config['host'],
                port=config.get('port', 27017),
                username=config.get('user'),
                password=config.get('password')
            )

            db = client[config['database']]
            collection = db[config.get('collection', 'books')]
            collection.delete_many({})
            data = df.to_dict('records')
            collection.insert_many(data)
            print(f"数据已保存到MongoDB数据库的 {config.get('collection', 'books')} 集合")

        except ImportError as e:
            print(f"错误：缺少必要的依赖包。请安装: pip install pymongo")
            raise e
        except Exception as e:
            print(f"保存数据到MongoDB时出错: {e}")
            raise e

    def save_data(self, df: pd.DataFrame, **kwargs):
        if self.target_type == 'mysql':
            config = {**self.target_config, **kwargs}
            self.save_to_mysql(df, config)
        elif self.target_type == 'postgresql':
            config = {**self.target_config, **kwargs}
            self.save_to_postgresql(df, config)
        elif self.target_type == 'mongodb':
            config = {**self.target_config, **kwargs}
            self.save_to_mongodb(df, config)
        else:
            raise ValueError(f"不支持的目标类型: {self.target_type}")


def extract_keywords_from_database(source_type: str, source_config: Dict,
                                    target_type: str = None, target_config: Dict = None,
                                    top_k: int = 10, stopwords_path: str = None) -> pd.DataFrame:
    print("=" * 60)
    print(f"开始从数据库提取图书关键词")
    print(f"数据源类型: {source_type}")
    print("=" * 60)

    if target_type is None:
        target_type = source_type
    if target_config is None:
        target_config = source_config

    loader = BookDataLoader(source_type=source_type, source_config=source_config)

    print(f"\n正在从 {source_type} 数据库加载数据...")
    df = loader.load_data()
    print(f"成功加载 {len(df)} 条图书记录")

    extractor = KeywordExtractor(stopwords_path=stopwords_path)

    print(f"\n正在批量提取关键词（每本书提取 {top_k} 个关键词）...")
    df = extractor.extract_keywords_batch(df, top_k=top_k)

    saver = BookDataSaver(target_type=target_type, target_config=target_config)
    saver.save_data(df, **target_config)

    empty_count = sum(1 for kw in df['keywords'] if not kw or len(kw) == 0)
    avg_kw_count = np.mean([len(kw) for kw in df['keywords']])

    print("\n" + "=" * 60)
    print("关键词提取完成！")
    print("=" * 60)
    print(f"总计处理: {len(df)} 本书")
    print(f"每本书关键词数: {top_k}")
    print(f"平均关键词数: {avg_kw_count:.1f}")
    print(f"空关键词书籍数: {empty_count}")
    print(f"数据已保存到 {target_type} 数据库")

    print("\n前5本书的关键词示例:")
    for i, (idx, row) in enumerate(df.head(5).iterrows()):
        title = str(row.get('title', ''))[:20]
        keywords = row.get('keywords', [])
        print(f"  {i+1}. {title}: {keywords}")

    return df


if __name__ == '__main__':
    print("\n从MySQL数据库提取关键词")
    print("-" * 60)

    source_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'Anny0607',
        'database': 'test',
        'table': 'books'
    }

    df = extract_keywords_from_database(
        source_type='mysql',
        source_config=source_config,
        top_k=10
    )
