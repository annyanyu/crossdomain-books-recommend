# -*- coding: utf-8 -*-
"""
图书向量生成模块
用于跨领域图书推荐的相似度计算

功能说明：
1. 将每本书的title、books_intro、author_intro、short_reviews、reviews、reading_notes拼接为一个文本
2. 使用BAAI/bge-base-zh-v1.5模型生成768维向量（用于粗粒度相似度）
3. 使用BAAI/bge-base-zh-v1.5模型为每个关键词生成768维向量（用于细粒度关联）
4. 生成每本书的关键词向量列表
5. 将上述生成的向量存入数据库的books表的相应列和行中

作者：系统自动生成
日期：2025-03-22
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import json
from typing import List, Dict, Tuple
from sqlalchemy import create_engine, text
import torch
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

from config import get_config_manager


class BookEmbeddingGenerator:
    """
    图书向量生成器类
    
    使用BAAI/bge-base-zh-v1.5生成整体向量和关键词向量
    """

    def __init__(self, model_name: str = 'BAAI/bge-base-zh-v1.5',
                 device: str = 'cuda' if torch.cuda.is_available() else 'cpu',
                 local_model_path: str = None):
        self.model_name = model_name
        self.device = device
        self.local_model_path = local_model_path
        self.bge_model = None
        self._model_loaded = False

        self.concat_fields = ['title', 'book_intro', 'author_intro', 'short_reviews', 'reviews', 'reading_notes']

    def _load_model(self):
        if self._model_loaded:
            return self.bge_model is not None

        print(f"正在加载BAAI模型: {self.model_name}")

        try:
            if self.local_model_path and os.path.exists(self.local_model_path):
                print(f"使用本地模型: {self.local_model_path}")
                self.bge_model = SentenceTransformer(self.local_model_path)
            else:
                try:
                    from modelscope import snapshot_download
                    print(f"从ModelScope下载模型: {self.model_name}")
                    model_path = snapshot_download(self.model_name)
                    self.bge_model = SentenceTransformer(model_path)
                    print(f"模型已下载到: {model_path}")
                except Exception as e:
                    print(f"从ModelScope下载失败: {e}")
                    print(f"尝试从HuggingFace加载模型: {self.model_name}")
                    self.bge_model = SentenceTransformer(self.model_name)

            self.bge_model.to(self.device)
            print(f"BAAI模型加载完成！")
            self._model_loaded = True
            return True
        except Exception as e:
            print(f"加载BAAI模型失败: {e}")
            print("将使用TF-IDF+SVD作为fallback")
            self.bge_model = None
            self._model_loaded = True
            return False

    def _concatenate_book_text(self, row: pd.Series) -> str:
        text_parts = []

        if pd.notna(row.get('title', '')):
            text_parts.append(str(row['title']))

        if pd.notna(row.get('book_intro', '')):
            text_parts.append(str(row['book_intro']))

        if pd.notna(row.get('author_intro', '')):
            text_parts.append(str(row['author_intro']))

        short_reviews_value = row.get('short_reviews', '')
        try:
            if isinstance(short_reviews_value, str):
                short_reviews = json.loads(short_reviews_value)
            elif isinstance(short_reviews_value, list):
                short_reviews = short_reviews_value
            else:
                short_reviews = []
        except json.JSONDecodeError:
            short_reviews = []

        if short_reviews:
            text_parts.extend([r for r in short_reviews if isinstance(r, str)])

        reviews_value = row.get('reviews', '')
        try:
            if isinstance(reviews_value, str):
                reviews = json.loads(reviews_value)
            elif isinstance(reviews_value, list):
                reviews = reviews_value
            else:
                reviews = []
        except json.JSONDecodeError:
            reviews = []

        if reviews:
            text_parts.extend([r for r in reviews if isinstance(r, str)])

        reading_notes_value = row.get('reading_notes', '')
        try:
            if isinstance(reading_notes_value, str):
                reading_notes = json.loads(reading_notes_value)
            elif isinstance(reading_notes_value, list):
                reading_notes = reading_notes_value
            else:
                reading_notes = []
        except json.JSONDecodeError:
            reading_notes = []

        if reading_notes:
            text_parts.extend([r for r in reading_notes if isinstance(r, str)])

        concatenated_text = ' '.join(text_parts)
        return concatenated_text

    def _safe_parse_keywords(self, keywords_value) -> List[str]:
        if isinstance(keywords_value, list):
            return keywords_value
        if isinstance(keywords_value, str):
            try:
                parsed = json.loads(keywords_value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    def generate_overall_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * 768

        if self.bge_model is not None:
            with torch.no_grad():
                embedding = self.bge_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        else:
            return self._fallback_embedding(text)

    def generate_keyword_embedding(self, keyword: str) -> List[float]:
        if not keyword or not keyword.strip():
            return [0.0] * 768

        if self.bge_model is not None:
            with torch.no_grad():
                embedding = self.bge_model.encode(keyword, convert_to_numpy=True)
            return embedding.tolist()
        else:
            return self._fallback_embedding(keyword)

    def generate_keyword_embeddings_batch(self, keywords: List[str]) -> List[List[float]]:
        if not keywords:
            return []

        valid_keywords = [kw for kw in keywords if kw and kw.strip()]
        if not valid_keywords:
            return []

        if self.bge_model is not None:
            with torch.no_grad():
                embeddings = self.bge_model.encode(valid_keywords, convert_to_numpy=True)
            return embeddings.tolist()
        else:
            return [self._fallback_embedding(kw) for kw in valid_keywords]

    def _fallback_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * 768

        vectorizer = TfidfVectorizer(max_features=768)
        tfidf_matrix = vectorizer.fit_transform([text])

        if tfidf_matrix.shape[1] < 768:
            padding = np.zeros((1, 768 - tfidf_matrix.shape[1]))
            embedding = np.hstack([tfidf_matrix.toarray(), padding])[0]
        else:
            svd = TruncatedSVD(n_components=768, random_state=42)
            embedding = svd.fit_transform(tfidf_matrix)[0]

        return embedding.tolist()

    def generate_embeddings_for_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        print("=" * 80)
        print("开始生成图书向量")
        print("=" * 80)

        model_available = self._load_model()

        print("\n步骤1: 生成整体向量（粗粒度）...")
        overall_embeddings = []

        if model_available:
            all_texts = []
            for idx, row in df.iterrows():
                concatenated_text = self._concatenate_book_text(row)
                all_texts.append(concatenated_text if concatenated_text else "")

            print(f"  批量编码 {len(all_texts)} 本书...")
            with torch.no_grad():
                all_embeddings = self.bge_model.encode(all_texts, convert_to_numpy=True, batch_size=32, show_progress_bar=True)
            overall_embeddings = all_embeddings.tolist()
        else:
            for idx, row in df.iterrows():
                concatenated_text = self._concatenate_book_text(row)
                embedding = self.generate_overall_embedding(concatenated_text)
                overall_embeddings.append(embedding)
                if (idx + 1) % 20 == 0:
                    print(f"  已处理 {idx + 1}/{len(df)} 本书")

        df['embedding'] = overall_embeddings
        print(f"整体向量生成完成！")

        print("\n步骤2: 生成关键词向量（细粒度）...")
        keywords_embeddings_list = []

        if model_available:
            all_keywords_flat = []
            book_keyword_indices = []
            current_idx = 0

            for idx, row in df.iterrows():
                keywords = self._safe_parse_keywords(row.get('keywords', '[]'))
                if keywords:
                    book_keyword_indices.append((current_idx, current_idx + len(keywords)))
                    all_keywords_flat.extend(keywords)
                    current_idx += len(keywords)
                else:
                    book_keyword_indices.append(None)

            if all_keywords_flat:
                print(f"  批量编码 {len(all_keywords_flat)} 个关键词...")
                with torch.no_grad():
                    all_kw_embeddings = self.bge_model.encode(all_keywords_flat, convert_to_numpy=True, batch_size=64, show_progress_bar=True)

                kw_idx = 0
                for i, indices in enumerate(book_keyword_indices):
                    if indices is not None:
                        start, end = indices
                        keywords_embeddings_list.append(all_kw_embeddings[start:end].tolist())
                    else:
                        keywords_embeddings_list.append([])
            else:
                keywords_embeddings_list = [[] for _ in range(len(df))]
        else:
            for idx, row in df.iterrows():
                keywords = self._safe_parse_keywords(row.get('keywords', '[]'))
                if keywords:
                    keyword_embeddings = self.generate_keyword_embeddings_batch(keywords)
                    keywords_embeddings_list.append(keyword_embeddings)
                else:
                    keywords_embeddings_list.append([])

                if (idx + 1) % 20 == 0:
                    print(f"  已处理 {idx + 1}/{len(df)} 本书")

        df['keywords_embeddings'] = keywords_embeddings_list
        print(f"关键词向量生成完成！")

        return df


class DatabaseEmbeddingUpdater:
    def __init__(self, host: str = 'localhost', port: int = 3306,
                 user: str = 'root', password: str = 'Anny0607',
                 database: str = 'test', table: str = 'books'):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.table = table

        connection_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        self.engine = create_engine(connection_str)

    def _check_and_add_columns(self):
        import pymysql

        conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4'
        )

        with conn.cursor() as cursor:
            cursor.execute(f"SHOW COLUMNS FROM {self.table}")
            existing_columns = [row[0] for row in cursor.fetchall()]

            if 'embedding' not in existing_columns:
                print(f"添加embedding列...")
                cursor.execute(f"ALTER TABLE {self.table} ADD COLUMN embedding JSON COMMENT '语义向量列表'")

            if 'keywords_embeddings' not in existing_columns:
                print(f"添加keywords_embeddings列...")
                cursor.execute(f"ALTER TABLE {self.table} ADD COLUMN keywords_embeddings JSON COMMENT '关键词向量列表'")

            conn.commit()
            print("列检查完成！")

        conn.close()

    def update_embeddings_to_database(self, df: pd.DataFrame):
        print("\n步骤3: 更新数据库...")

        import pymysql

        conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4'
        )

        with conn.cursor() as cursor:
            for idx, row in df.iterrows():
                book_id = row['book_id']

                update_parts = []
                update_values = []

                if 'embedding' in df.columns:
                    embedding_list = row['embedding']
                    if isinstance(embedding_list, list) and len(embedding_list) > 0:
                        embedding_json = json.dumps(embedding_list, ensure_ascii=False)
                        update_parts.append("embedding = %s")
                        update_values.append(embedding_json)

                if 'keywords_embeddings' in df.columns:
                    keywords_embeddings_list = row['keywords_embeddings']
                    if isinstance(keywords_embeddings_list, list) and len(keywords_embeddings_list) > 0:
                        keywords_embeddings_json = json.dumps(keywords_embeddings_list, ensure_ascii=False)
                        update_parts.append("keywords_embeddings = %s")
                        update_values.append(keywords_embeddings_json)

                if update_parts:
                    update_sql = f"UPDATE {self.table} SET {', '.join(update_parts)} WHERE book_id = %s"
                    update_values.append(book_id)
                    cursor.execute(update_sql, update_values)

                    if (idx + 1) % 20 == 0:
                        print(f"  已更新 {idx + 1}/{len(df)} 本书")

            conn.commit()
            print("数据库更新完成！")

        conn.close()


class BookDataLoader:
    def __init__(self, source_type: str = 'mysql', source_config: Dict = None):
        self.source_type = source_type
        self.source_config = source_config or {}

    def load_from_mysql(self, config: Dict) -> pd.DataFrame:
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

    def load_data(self, **kwargs) -> pd.DataFrame:
        if self.source_type == 'mysql':
            config = {**self.source_config, **kwargs}
            return self.load_from_mysql(config)
        else:
            raise ValueError(f"不支持的数据源类型: {self.source_type}")


def generate_embeddings_for_database(source_config: Dict, target_config: Dict = None,
                               bge_model_name: str = 'BAAI/bge-base-zh-v1.5',
                               local_model_path: str = None):
    print("=" * 80)
    print("开始生成图书向量")
    print("=" * 80)

    if target_config is None:
        target_config = source_config

    generator = BookEmbeddingGenerator(
        model_name=bge_model_name,
        local_model_path=local_model_path
    )

    updater = DatabaseEmbeddingUpdater(**source_config)

    updater._check_and_add_columns()

    print(f"\n正在从数据库加载数据...")
    loader = BookDataLoader(source_type='mysql', source_config=source_config)
    df = loader.load_data()
    print(f"成功加载 {len(df)} 条图书记录")

    df = generator.generate_embeddings_for_dataframe(df)

    updater.update_embeddings_to_database(df)

    distinct_ke = df['keywords_embeddings'].apply(lambda x: json.dumps(x) if isinstance(x, list) else '').nunique()
    print("\n" + "=" * 80)
    print("向量生成完成！")
    print("=" * 80)
    print(f"总计处理: {len(df)} 本书")
    print(f"整体向量维度: 768")
    print(f"关键词向量维度: 768")
    print(f"不同keywords_embeddings数量: {distinct_ke}")
    print(f"数据已保存到数据库的 {target_config['table']} 表")

    return df


if __name__ == '__main__':
    print("正在加载配置文件...")
    config = get_config_manager()
    source_config = config.get_database_config()

    print("\n模式：使用BGE模型生成向量")
    df = generate_embeddings_for_database(
        source_config=source_config
    )
