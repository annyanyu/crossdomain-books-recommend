# -*- coding: utf-8 -*-
"""
图书关键词提取模块
基于TF-IDF和TextRank算法提取图书文本关键词

功能说明：
1. 支持从数据库读取图书数据
2. 使用TF-IDF算法提取关键词
3. 使用TextRank算法提取关键词
4. 融合两种算法结果，生成最终关键词列表
5. 支持批量处理和单本书处理

作者：系统自动生成
日期：2025-03-22
"""

import pandas as pd
import numpy as np
import jieba
import jieba.analyse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx
import re
from typing import List, Dict, Tuple, Optional
import json
import os


class KeywordExtractor:
    """
    关键词提取器类
    
    使用TF-IDF和TextRank两种算法提取关键词，并融合结果
    """
    
    def __init__(self, stopwords_path: str = None):
        """
        初始化关键词提取器
        
        参数:
            stopwords_path: 停用词表文件路径，如果为None则使用默认路径
        """
        self.stopwords = self._load_stopwords(stopwords_path)
        self.tfidf_vectorizer = None
        
    def _load_stopwords(self, stopwords_path: str = None) -> set:
        """
        加载停用词表
        
        参数:
            stopwords_path: 停用词表文件路径
            
        返回:
            停用词集合
        """
        if stopwords_path is None:
            stopwords_path = os.path.join(os.path.dirname(__file__), 'stopwords.txt')
        
        stopwords = set()
        if os.path.exists(stopwords_path):
            with open(stopwords_path, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip()
                    if word:
                        stopwords.add(word)
        else:
            print(f"警告：停用词表文件 {stopwords_path} 不存在，使用空停用词表")
        
        return stopwords
    
    def _preprocess_text(self, text: str) -> str:
        """
        文本预处理
        
        参数:
            text: 原始文本
            
        返回:
            预处理后的文本
        """
        if pd.isna(text) or text is None:
            return ""
        
        text = str(text)
        
        # 去除标点符号和特殊字符
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', text)
        
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _segment_text(self, text: str) -> List[str]:
        """
        中文分词
        
        参数:
            text: 预处理后的文本
            
        返回:
            分词结果列表
        """
        if not text:
            return []
        
        # 使用jieba分词
        words = jieba.cut(text)
        
        # 过滤停用词和短词
        filtered_words = [
            word for word in words 
            if word not in self.stopwords 
            and len(word) > 1  # 过滤单字
            and not word.isdigit()  # 过滤纯数字
        ]
        
        return filtered_words
    
    def extract_tfidf_keywords(self, texts: List[str], top_k: int = 10) -> List[List[str]]:
        """
        使用TF-IDF算法提取关键词
        
        参数:
            texts: 文本列表
            top_k: 每个文本提取的关键词数量
            
        返回:
            每个文本的关键词列表
        """
        if not texts:
            return []
        
        # 预处理和分词
        processed_texts = []
        for text in texts:
            processed_text = self._preprocess_text(text)
            words = self._segment_text(processed_text)
            processed_texts.append(' '.join(words))
        
        # 创建TF-IDF向量化器
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            min_df=1,
            max_df=0.95,
            ngram_range=(1, 2)  # 使用1-gram和2-gram
        )
        
        # 计算TF-IDF矩阵
        tfidf_matrix = self.tfidf_vectorizer.fit_transform(processed_texts)
        feature_names = self.tfidf_vectorizer.get_feature_names_out()
        
        # 提取每个文档的关键词
        all_keywords = []
        for i in range(len(texts)):
            # 获取当前文档的TF-IDF分数
            tfidf_scores = tfidf_matrix[i].toarray()[0]
            
            # 获取top-k关键词
            top_indices = np.argsort(tfidf_scores)[-top_k:][::-1]
            keywords = [feature_names[idx] for idx in top_indices if tfidf_scores[idx] > 0]
            
            all_keywords.append(keywords)
        
        return all_keywords
    
    def extract_textrank_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """
        使用TextRank算法提取关键词
        
        参数:
            text: 输入文本
            top_k: 提取的关键词数量
            
        返回:
            关键词列表
        """
        if not text:
            return []
        
        # 使用jieba的TextRank实现
        keywords = jieba.analyse.textrank(
            text,
            topK=top_k,
            withWeight=False,
            allowPOS=('n', 'vn', 'v', 'a', 'an')  # 只提取名词、动词、形容词等有意义的词
        )
        
        return keywords
    
    def merge_keywords(self, tfidf_keywords: List[str], textrank_keywords: List[str], 
                      top_k: int = 10) -> List[str]:
        """
        融合TF-IDF和TextRank的关键词
        
        参数:
            tfidf_keywords: TF-IDF提取的关键词
            textrank_keywords: TextRank提取的关键词
            top_k: 最终返回的关键词数量
            
        返回:
            融合后的关键词列表
        """
        # 创建关键词字典，记录每个关键词在两种算法中的排名
        keyword_scores = {}
        
        # TF-IDF关键词（排名靠前的权重更高）
        for idx, keyword in enumerate(tfidf_keywords):
            score = (len(tfidf_keywords) - idx) * 2  # TF-IDF权重设为2倍
            keyword_scores[keyword] = keyword_scores.get(keyword, 0) + score
        
        # TextRank关键词
        for idx, keyword in enumerate(textrank_keywords):
            score = len(textrank_keywords) - idx
            keyword_scores[keyword] = keyword_scores.get(keyword, 0) + score
        
        # 按分数排序，取top-k
        sorted_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
        final_keywords = [keyword for keyword, score in sorted_keywords[:top_k]]
        
        return final_keywords
    
    def extract_keywords_for_book(self, content_intro: str, author_intro: str, 
                                  top_k: int = 10) -> List[str]:
        """
        为单本书提取关键词
        
        参数:
            content_intro: 内容简介
            author_intro: 作者简介
            top_k: 提取的关键词数量
            
        返回:
            关键词列表
        """
        # 合并内容简介和作者简介
        combined_text = f"{content_intro} {author_intro}"
        
        # 预处理文本
        processed_text = self._preprocess_text(combined_text)
        
        # 使用TextRank提取关键词
        textrank_keywords = self.extract_textrank_keywords(processed_text, top_k * 2)
        
        # 使用TF-IDF提取关键词（需要构建文档集）
        # 这里使用简单的词频统计模拟TF-IDF
        words = self._segment_text(processed_text)
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # 按词频排序
        tfidf_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        tfidf_keywords = [word for word, freq in tfidf_keywords[:top_k * 2]]
        
        # 融合两种算法结果
        final_keywords = self.merge_keywords(tfidf_keywords, textrank_keywords, top_k)
        
        return final_keywords


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
            
        注意: 需要安装 pymysql 和 sqlalchemy
        """
        try:
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
            
        except ImportError as e:
            print(f"错误：缺少必要的依赖包。请安装: pip install pymysql sqlalchemy")
            raise e
        except Exception as e:
            print(f"从MySQL加载数据时出错: {e}")
            raise e
    
    def load_from_postgresql(self, config: Dict) -> pd.DataFrame:
        """
        从PostgreSQL数据库加载数据
        
        参数:
            config: 数据库配置字典，包含host, port, user, password, database, table等
            
        返回:
            图书数据DataFrame
            
        注意: 需要安装 psycopg2 和 sqlalchemy
        """
        try:
            from sqlalchemy import create_engine
            import psycopg2
            
            # 构建数据库连接字符串
            connection_str = f"postgresql+psycopg2://{config['user']}:{config['password']}@{config['host']}:{config.get('port', 5432)}/{config['database']}?charset=utf8mb4"
            
            # 创建引擎
            engine = create_engine(connection_str)
            
            # 读取数据
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
        """
        从MongoDB数据库加载数据
        
        参数:
            config: 数据库配置字典，包含host, port, user, password, database, collection等
            
        返回:
            图书数据DataFrame
            
        注意: 需要安装 pymongo
        """
        try:
            from pymongo import MongoClient
            
            # 创建MongoDB客户端
            client = MongoClient(
                host=config['host'],
                port=config.get('port', 27017),
                username=config.get('user'),
                password=config.get('password')
            )
            
            # 获取数据库和集合
            db = client[config['database']]
            collection = db[config.get('collection', 'books')]
            
            # 读取数据
            data = list(collection.find())
            df = pd.DataFrame(data)
            
            # 删除MongoDB的_id字段
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
        
        elif self.source_type == 'postgresql':
            config = {**self.source_config, **kwargs}
            return self.load_from_postgresql(config)
        
        elif self.source_type == 'mongodb':
            config = {**self.source_config, **kwargs}
            return self.load_from_mongodb(config)
        
        else:
            raise ValueError(f"不支持的数据源类型: {self.source_type}")


class BookDataSaver:
    """
    图书数据保存器
    
    支持将数据保存到数据库
    """
    
    def __init__(self, target_type: str = 'mysql', target_config: Dict = None):
        """
        初始化数据保存器
        
        参数:
            target_type: 目标类型 ('mysql', 'postgresql', 'mongodb')
            target_config: 目标配置信息
        """
        self.target_type = target_type
        self.target_config = target_config or {}
    
    def save_to_mysql(self, df: pd.DataFrame, config: Dict):
        """
        保存数据到MySQL数据库
        
        参数:
            df: 要保存的DataFrame
            config: 数据库配置字典
            
        注意: 需要安装 pymysql 和 sqlalchemy
        """
        try:
            from sqlalchemy import create_engine, text
            import pymysql
            
            # 构建数据库连接字符串
            connection_str = f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}:{config.get('port', 3306)}/{config['database']}?charset=utf8mb4"
            
            # 创建引擎
            engine = create_engine(connection_str)
            
            # 只更新keywords和domain列
            table_name = config.get('table', 'books')
            
            with engine.connect() as conn:
                for idx, row in df.iterrows():
                    book_id = row['book_id']
                    
                    # 构建UPDATE语句
                    update_parts = []
                    update_params = {'book_id': book_id}
                    
                    # 如果有keywords列，更新keywords
                    if 'keywords' in df.columns:
                        keywords = row['keywords']
                        if isinstance(keywords, list):
                            update_parts.append("keywords = :keywords")
                            update_params['keywords'] = json.dumps(keywords, ensure_ascii=False)
                    
                    # 如果有domain列，更新domain
                    if 'domain' in df.columns:
                        domain = row['domain']
                        if isinstance(domain, list):
                            update_parts.append("domain = :domain")
                            update_params['domain'] = json.dumps(domain, ensure_ascii=False)
                    
                    # 如果有需要更新的列，执行UPDATE
                    if update_parts:
                        update_sql = text(f"UPDATE {table_name} SET {', '.join(update_parts)} WHERE book_id = :book_id")
                        result = conn.execute(update_sql, update_params)
                        
                        # 提交事务
                        conn.commit()
                        
                        # 显示前3条的更新信息
                        if idx < 3:
                            print(f"更新记录 {book_id}: {', '.join(update_parts)}")
                            print(f"  keywords: {update_params.get('keywords', 'N/A')[:50]}...")
                            print(f"  domain: {update_params.get('domain', 'N/A')}")
            
            print(f"数据已保存到MySQL数据库的 {table_name} 表")
            
        except ImportError as e:
            print(f"错误：缺少必要的依赖包。请安装: pip install pymysql sqlalchemy")
            raise e
        except Exception as e:
            print(f"保存数据到MySQL时出错: {e}")
            raise e
    
    def save_to_postgresql(self, df: pd.DataFrame, config: Dict):
        """
        保存数据到PostgreSQL数据库
        
        参数:
            df: 要保存的DataFrame
            config: 数据库配置字典
            
        注意: 需要安装 psycopg2 和 sqlalchemy
        """
        try:
            from sqlalchemy import create_engine
            import psycopg2
            
            # 构建数据库连接字符串
            connection_str = f"postgresql+psycopg2://{config['user']}:{config['password']}@{config['host']}:{config.get('port', 5432)}/{config['database']}?charset=utf8mb4"
            
            # 创建引擎
            engine = create_engine(connection_str)
            
            # 保存数据
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
        """
        保存数据到MongoDB数据库
        
        参数:
            df: 要保存的DataFrame
            config: 数据库配置字典
            
        注意: 需要安装 pymongo
        """
        try:
            from pymongo import MongoClient
            
            # 创建MongoDB客户端
            client = MongoClient(
                host=config['host'],
                port=config.get('port', 27017),
                username=config.get('user'),
                password=config.get('password')
            )
            
            # 获取数据库和集合
            db = client[config['database']]
            collection = db[config.get('collection', 'books')]
            
            # 清空集合
            collection.delete_many({})
            
            # 插入数据
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
        """
        根据配置保存数据
        
        参数:
            df: 要保存的DataFrame
            **kwargs: 目标配置参数
        """
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
    """
    从数据库提取图书关键词（主函数）
    
    参数:
        source_type: 数据源类型 ('mysql', 'postgresql', 'mongodb')
        source_config: 数据源配置字典
        target_type: 目标类型（如果为None，则与source_type相同）
        target_config: 目标配置字典（如果为None，则与source_config相同）
        top_k: 每本书提取的关键词数量
        stopwords_path: 停用词表文件路径
        
    返回:
        包含关键词的DataFrame
        
    使用示例:
        # 从MySQL提取关键词并保存回MySQL
        source_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': 'password',
            'database': 'book_db',
            'table': 'books'
        }
        df = extract_keywords_from_database('mysql', source_config)
        
        # 从MySQL提取关键词并保存到PostgreSQL
        target_config = {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': 'password',
            'database': 'book_db',
            'table': 'books'
        }
        df = extract_keywords_from_database('mysql', source_config, 'postgresql', target_config)
    """
    print("=" * 60)
    print(f"开始从数据库提取图书关键词")
    print(f"数据源类型: {source_type}")
    print("=" * 60)
    
    # 如果没有指定目标，则使用与源相同的配置
    if target_type is None:
        target_type = source_type
    if target_config is None:
        target_config = source_config
    
    # 初始化数据加载器
    loader = BookDataLoader(source_type=source_type, source_config=source_config)
    
    # 加载数据
    print(f"\n正在从 {source_type} 数据库加载数据...")
    df = loader.load_data()
    print(f"成功加载 {len(df)} 条图书记录")
    
    # 初始化关键词提取器
    extractor = KeywordExtractor(stopwords_path=stopwords_path)
    
    # 批量提取关键词
    print(f"\n正在提取关键词（每本书提取 {top_k} 个关键词）...")
    keywords_list = []
    
    for idx, row in df.iterrows():
        content_intro = row.get('books_intro', '')
        author_intro = row.get('author_intro', '')
        
        # 提取关键词
        keywords = extractor.extract_keywords_for_book(
            content_intro, 
            author_intro, 
            top_k=top_k
        )
        
        keywords_list.append(keywords)
        
        # 显示进度
        if (idx + 1) % 10 == 0:
            print(f"已处理 {idx + 1}/{len(df)} 本书")
    
    # 添加关键词列
    df['keywords'] = keywords_list
    
    # 保存结果
    saver = BookDataSaver(target_type=target_type, target_config=target_config)
    saver.save_data(df, **target_config)
    
    # 显示统计信息
    print("\n" + "=" * 60)
    print("关键词提取完成！")
    print("=" * 60)
    print(f"总计处理: {len(df)} 本书")
    print(f"每本书关键词数: {top_k}")
    print(f"数据已保存到 {target_type} 数据库")
    
    return df


if __name__ == '__main__':
    # 从MySQL数据库提取关键词
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
