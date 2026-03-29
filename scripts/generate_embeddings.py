# -*- coding: utf-8 -*-
"""
图书向量生成模块
用于跨领域图书推荐的相似度计算

功能说明：
1. 将每本书的title、books_intro、author_intro、short_reviews、reviews、reading_notes拼接为一个文本
2. 使用BAAI/bge-base-zh-v1.5模型生成768维向量（用于粗粒度相似度）
3. 使用Word2Vec将每本书的每个关键词生成一个向量（用于细粒度关联）
4. 生成每本书的关键词向量列表
5. 将上述生成的向量存入数据库的books表的相应列和行中（若没有embedding列和keywords_embeddings列则添加）

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
from modelscope import snapshot_download
from sentence_transformers import SentenceTransformer
from gensim.models import Word2Vec, KeyedVectors
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

from config import get_config_manager


class BookEmbeddingGenerator:
    """
    图书向量生成器类
    
    使用BAAI/bge-base-zh-v1.5生成整体向量
    使用Word2Vec生成关键词向量
    """
    
    def __init__(self, model_name: str = 'BAAI/bge-base-zh-v1.5', 
                 word2vec_model_path: str = None,
                 device: str = 'cuda' if torch.cuda.is_available() else 'cpu',
                 local_model_path: str = None):
        """
        初始化向量生成器
        
        参数:
            model_name: BAAI模型名称
            word2vec_model_path: Word2Vec模型路径（如果为None则训练新模型）
            device: 运行设备（cuda或cpu）
            local_model_path: 本地模型路径（如果提供则使用本地模型）
        """
        self.model_name = model_name
        self.device = device
        self.word2vec_model_path = word2vec_model_path
        self.local_model_path = local_model_path
        
        # 加载BAAI模型
        print(f"正在加载BAAI模型: {model_name}")
        
        try:
            # 优先使用本地模型
            if local_model_path and os.path.exists(local_model_path):
                print(f"使用本地模型: {local_model_path}")
                self.bge_model = SentenceTransformer(local_model_path)
            else:
                # 从ModelScope下载
                print(f"从ModelScope下载模型: {model_name}")
                from modelscope import snapshot_download
                model_path = snapshot_download(model_name)
                self.bge_model = SentenceTransformer(model_path)
                print(f"模型已下载到: {model_path}")
            
            self.bge_model.to(self.device)
            print(f"BAAI模型加载完成！")
        except Exception as e:
            print(f"加载BAAI模型失败: {e}")
            print("将使用零向量作为fallback")
            self.bge_model = None
            self.word2vec_model = None
        
        # 定义需要拼接的字段（只包含title、books_intro、author_intro、short_reviews、reviews、reading_notes）
        self.concat_fields = ['title', 'books_intro', 'author_intro', 'short_reviews', 'reviews', 'reading_notes']
    
    def _concatenate_book_text(self, row: pd.Series) -> str:
        """
        拼接图书文本信息
        
        参数:
            row: 图书数据行
            
        返回:
            拼接后的文本
        """
        text_parts = []
        
        # 添加书名
        if pd.notna(row.get('title', '')):
            text_parts.append(str(row['title']))
        
        # 添加内容简介
        if pd.notna(row.get('books_intro', '')):
            text_parts.append(str(row['books_intro']))
        
        # 添加作者简介
        if pd.notna(row.get('author_intro', '')):
            text_parts.append(str(row['author_intro']))
        
        # 添加短评
        short_reviews_value = row.get('short_reviews', '')
        if isinstance(short_reviews_value, str):
            short_reviews = json.loads(short_reviews_value)
        elif isinstance(short_reviews_value, list):
            short_reviews = short_reviews_value
        else:
            short_reviews = []
        
        if short_reviews:
            text_parts.extend(short_reviews)
        
        # 添加书评
        reviews_value = row.get('reviews', '')
        if isinstance(reviews_value, str):
            reviews = json.loads(reviews_value)
        elif isinstance(reviews_value, list):
            reviews = reviews_value
        else:
            reviews = []
        
        if reviews:
            text_parts.extend(reviews)
        
        # 添加读书笔记
        reading_notes_value = row.get('reading_notes', '')
        if isinstance(reading_notes_value, str):
            reading_notes = json.loads(reading_notes_value)
        elif isinstance(reading_notes_value, list):
            reading_notes = reading_notes_value
        else:
            reading_notes = []
        
        if reading_notes:
            text_parts.extend(reading_notes)
        
        # 用空格拼接所有文本
        concatenated_text = ' '.join(text_parts)
        
        return concatenated_text
    
    def generate_overall_embedding(self, text: str) -> List[float]:
        """
        生成整体向量（粗粒度）
        
        参数:
            text: 拼接后的文本
            
        返回:
            768维向量列表
        """
        # 优先使用BAAI模型
        if self.bge_model is not None:
            # 使用BAAI模型生成向量
            with torch.no_grad():
                embedding = self.bge_model.encode(text, convert_to_numpy=True)
            
            # 转换为列表格式
            embedding_list = embedding.tolist()
            
            return embedding_list
        else:
            # BAAI模型未加载，使用TF-IDF + SVD作为fallback
            print("BAAI模型未加载，使用TF-IDF + SVD生成向量")
            
            # 使用TF-IDF提取特征
            vectorizer = TfidfVectorizer(max_features=768, ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform([text])
            
            # 使用SVD降维到768维
            svd = TruncatedSVD(n_components=768, random_state=42)
            embedding = svd.fit_transform(tfidf_matrix)[0]
            
            # 转换为列表格式
            embedding_list = embedding.tolist()
            
            return embedding_list
    
    def generate_keyword_embeddings(self, keywords: List[str]) -> List[List[float]]:
        """
        生成关键词向量（细粒度）
        
        参数:
            keywords: 关键词列表
            
        返回:
            关键词向量列表，每个关键词一个向量
        """
        if self.word2vec_model is None:
            print("警告：Word2Vec模型未加载，返回空列表")
            return []
        
        keyword_embeddings = []
        
        for keyword in keywords:
            # 使用jieba分词
            words = list(jieba.cut(keyword))
            
            # 对每个词生成向量
            word_vectors = []
            for word in words:
                if word in self.word2vec_model:
                    word_vectors.append(self.word2vec_model[word].tolist())
            
            # 如果有关键词的词向量，取平均
            if word_vectors:
                avg_vector = np.mean(np.array(word_vectors), axis=0).tolist()
                keyword_embeddings.append(avg_vector)
            else:
                # 如果关键词不在词汇表中，使用零向量
                keyword_embeddings.append([0.0] * self.word2vec_model.vector_size)
        
        return keyword_embeddings
    
    def train_word2vec_model(self, sentences: List[List[str]], 
                           vector_size: int = 100,
                           window: int = 5,
                           min_count: int = 1,
                           workers: int = 4,
                           pretrained_model_path: str = None):
        """
        训练Word2Vec模型或加载预训练模型
        
        参数:
            sentences: 分词后的句子列表
            vector_size: 向量维度
            window: 上下文窗口大小
            min_count: 最小词频
            workers: 训练线程数
            pretrained_model_path: 预训练模型路径（如果提供则加载，否则训练新模型）
            
        返回:
            Word2Vec的KeyedVectors对象
        """
        # 如果提供了预训练模型路径，直接加载
        if pretrained_model_path and os.path.exists(pretrained_model_path):
            print(f"加载预训练Word2Vec模型: {pretrained_model_path}")
            from gensim.models import KeyedVectors
            self.word2vec_model = KeyedVectors.load_word2vec_format(pretrained_model_path)
            print(f"Word2Vec模型加载完成！词汇表大小: {len(self.word2vec_model.key_to_index)}")
            return self.word2vec_model
        
        # 否则训练新模型
        print(f"开始训练Word2Vec模型...")
        print(f"  句子数: {len(sentences)}")
        print(f"  向量维度: {vector_size}")
        print(f"  窗口大小: {window}")
        
        # 训练Word2Vec模型
        model = Word2Vec(
            sentences=sentences,
            vector_size=vector_size,
            window=window,
            min_count=min_count,
            workers=workers,
            sg=0  # CBOW模型
        )
        
        print(f"Word2Vec模型训练完成！")
        print(f"  词汇表大小: {len(model.wv.key_to_index)}")
        
        self.word2vec_model = model.wv
        
        return model.wv
    
    def generate_embeddings_for_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        为DataFrame中的所有图书生成向量
        
        参数:
            df: 图书数据DataFrame
            
        返回:
            添加了embedding和keywords_embeddings列的DataFrame
        """
        print("=" * 80)
        print("开始生成图书向量")
        print("=" * 80)
        
        # 生成整体向量
        print("\n步骤1: 生成整体向量（粗粒度）...")
        overall_embeddings = []
        
        for idx, row in df.iterrows():
            # 拼接文本
            concatenated_text = self._concatenate_book_text(row)
            
            # 生成整体向量
            embedding = self.generate_overall_embedding(concatenated_text)
            overall_embeddings.append(embedding)
            
            # 显示进度
            if (idx + 1) % 10 == 0:
                print(f"  已处理 {idx + 1}/{len(df)} 本书")
        
        df['embedding'] = overall_embeddings
        print(f"整体向量生成完成！")
        
        # 生成关键词向量
        print("\n步骤2: 生成关键词向量（细粒度）...")
        keywords_embeddings_list = []
        
        for idx, row in df.iterrows():
            # 获取关键词列表
            keywords_json = row.get('keywords', '[]')
            keywords = json.loads(keywords_json) if isinstance(keywords_json, str) else keywords_json
            
            if keywords:
                # 生成关键词向量
                keyword_embeddings = self.generate_keyword_embeddings(keywords)
                keywords_embeddings_list.append(keyword_embeddings)
            else:
                # 如果没有关键词，使用空列表
                keywords_embeddings_list.append([])
            
            # 显示进度
            if (idx + 1) % 10 == 0:
                print(f"  已处理 {idx + 1}/{len(df)} 本书")
        
        df['keywords_embeddings'] = keywords_embeddings_list
        print(f"关键词向量生成完成！")
        
        return df


class DatabaseEmbeddingUpdater:
    """
    数据库向量更新器
    
    将生成的向量更新到数据库
    """
    
    def __init__(self, host: str = 'localhost', port: int = 3306,
                 user: str = 'root', password: str = 'Anny0607',
                 database: str = 'test', table: str = 'books'):
        """
        初始化数据库更新器
        
        参数:
            host: 数据库主机
            port: 数据库端口
            user: 数据库用户
            password: 数据库密码
            database: 数据库名
            table: 表名
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.table = table
        
        # 创建数据库连接
        connection_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        self.engine = create_engine(connection_str)
    
    def _check_and_add_columns(self):
        """
        检查并添加embedding和keywords_embeddings列
        """
        with self.engine.connect() as conn:
            # 检查列是否存在
            result = conn.execute(text(f"SHOW COLUMNS FROM {self.table}"))
            existing_columns = [row[0] for row in result]
            
            # 添加不存在的列
            if 'embedding' not in existing_columns:
                print(f"添加embedding列...")
                conn.execute(text(f"ALTER TABLE {self.table} ADD COLUMN embedding JSON COMMENT '语义向量列表'"))
            
            if 'keywords_embeddings' not in existing_columns:
                print(f"添加keywords_embeddings列...")
                conn.execute(text(f"ALTER TABLE {self.table} ADD COLUMN keywords_embeddings JSON COMMENT '关键词向量列表'"))
            
            conn.commit()
            print("列检查完成！")
    
    def update_embeddings_to_database(self, df: pd.DataFrame):
        """
        将向量数据更新到数据库
        
        参数:
            df: 包含embedding和keywords_embeddings的DataFrame
        """
        print("\n步骤3: 更新数据库...")
        
        with self.engine.connect() as conn:
            for idx, row in df.iterrows():
                book_id = row['book_id']
                
                # 构建UPDATE语句
                update_parts = []
                update_params = {'book_id': book_id}
                
                # 更新embedding列
                if 'embedding' in df.columns:
                    embedding_list = row['embedding']
                    if isinstance(embedding_list, list) and len(embedding_list) > 0:
                        embedding_json = json.dumps(embedding_list, ensure_ascii=False)
                        update_parts.append("embedding = :embedding")
                        update_params['embedding'] = embedding_json
                
                # 更新keywords_embeddings列
                if 'keywords_embeddings' in df.columns:
                    keywords_embeddings_list = row['keywords_embeddings']
                    if isinstance(keywords_embeddings_list, list) and len(keywords_embeddings_list) > 0:
                        keywords_embeddings_json = json.dumps(keywords_embeddings_list, ensure_ascii=False)
                        update_parts.append("keywords_embeddings = :keywords_embeddings")
                        update_params['keywords_embeddings'] = keywords_embeddings_json
                
                # 执行UPDATE
                if update_parts:
                    update_sql = text(f"UPDATE {self.table} SET {', '.join(update_parts)} WHERE book_id = :book_id")
                    result = conn.execute(update_sql, update_params)
                    conn.commit()
                    
                    # 显示进度
                    if (idx + 1) % 20 == 0:
                        print(f"  已更新 {idx + 1}/{len(df)} 本书")
            
            print("数据库更新完成！")


def generate_embeddings_for_database(source_config: Dict, target_config: Dict = None,
                               bge_model_name: str = 'BAAI/bge-base-zh-v1.5',
                               word2vec_model_path: str = None,
                               train_word2vec: bool = False,
                               vector_size: int = 100):
    """
    从数据库生成图书向量并更新回数据库（主函数）
    
    参数:
        source_config: 数据源配置
        target_config: 目标配置（如果为None则与source相同）
        bge_model_name: BAAI模型名称
        word2vec_model_path: Word2Vec模型路径（如果为None则训练新模型）
        train_word2vec: 是否训练Word2Vec模型
        vector_size: Word2Vec向量维度
        
    返回:
        处理后的DataFrame
    """
    print("=" * 80)
    print("开始生成图书向量")
    print("=" * 80)
    
    # 如果没有指定目标配置，使用与源相同的配置
    if target_config is None:
        target_config = source_config
    
    # 初始化向量生成器
    generator = BookEmbeddingGenerator(
        model_name=bge_model_name,
        word2vec_model_path=word2vec_model_path
    )
    
    # 初始化数据库更新器
    updater = DatabaseEmbeddingUpdater(**source_config)
    
    # 检查并添加列
    updater._check_and_add_columns()
    
    # 从数据库加载数据
    print(f"\n正在从数据库加载数据...")
    loader = BookDataLoader(source_type='mysql', source_config=source_config)
    df = loader.load_data()
    print(f"成功加载 {len(df)} 条图书记录")
    
    # 如果需要训练Word2Vec模型
    if train_word2vec:
        print(f"\n训练Word2Vec模型...")
        
        # 收集所有关键词
        all_keywords = []
        for keywords_json in df['keywords']:
            keywords = json.loads(keywords_json) if isinstance(keywords_json, str) else keywords_json
            all_keywords.extend(keywords)
        
        # 使用jieba分词
        sentences = [list(jieba.cut(keyword)) for keyword in all_keywords]
        
        # 训练Word2Vec模型
        model = generator.train_word2vec_model(
            sentences=sentences,
            vector_size=vector_size
        )
        
        # 保存模型
        model_path = f"word2vec_model.bin"
        model.save(model_path)
        print(f"Word2Vec模型已保存到: {model_path}")
        
        # 更新生成器的Word2Vec模型
        generator.word2vec_model = model
    
    # 生成向量
    df = generator.generate_embeddings_for_dataframe(df)
    
    # 更新数据库
    updater.update_embeddings_to_database(df)
    
    # 显示统计信息
    print("\n" + "=" * 80)
    print("向量生成完成！")
    print("=" * 80)
    print(f"总计处理: {len(df)} 本书")
    print(f"整体向量维度: 768")
    print(f"关键词向量维度: {vector_size}")
    print(f"数据已保存到数据库的 {target_config['table']} 表")
    
    return df


# 从extract_keywords.py导入BookDataLoader类
class BookDataLoader:
    """
    图书数据加载器
    
    支持从数据库加载图书数据
    """
    
    def __init__(self, source_type: str = 'mysql', source_config: Dict = None):
        """
        初始化数据加载器
        
        参数:
            source_type: 数据源类型 ('mysql', 'postgresql', 'mongodb')
            source_config: 数据源配置信息
        """
        self.source_type = source_type
        self.source_config = source_config or {}
    
    def load_from_mysql(self, config: Dict) -> pd.DataFrame:
        """
        从MySQL数据库加载数据
        
        参数:
            config: 数据库配置字典，包含host, port, user, password, database, table等
            
        返回:
            图书数据DataFrame
        """
        from sqlalchemy import create_engine, text
        import pymysql
        
        # 构建数据库连接字符串
        connection_str = f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}:{config.get('port', 3306)}/{config['database']}?charset=utf8mb4"
        
        # 创建引擎
        engine = create_engine(connection_str)
        
        # 读取数据
        table_name = config.get('table', 'books')
        df = pd.read_sql_table(table_name, engine)
        
        return df
    
    def load_data(self, **kwargs) -> pd.DataFrame:
        """
        根据配置加载数据
        
        参数:
            **kwargs: 数据源配置参数
            
        返回:
            图书数据DataFrame
        """
        if self.source_type == 'mysql':
            config = {**self.source_config, **kwargs}
            return self.load_from_mysql(config)
        
        else:
            raise ValueError(f"不支持的数据源类型: {self.source_type}")


if __name__ == '__main__':
    # 从配置文件加载数据库配置
    print("正在加载配置文件...")
    config = get_config_manager()
    source_config = config.get_database_config()
    
    # 生成向量（自动训练Word2Vec模型）
    print("\n模式：自动训练Word2Vec模型并生成向量")
    df = generate_embeddings_for_database(
        source_config=source_config,
        train_word2vec=True,  # 自动训练Word2Vec模型
        vector_size=100
    )
