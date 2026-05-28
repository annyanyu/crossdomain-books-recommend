# -*- coding: utf-8 -*-
"""
跨领域图书推荐模块
用于计算图书之间的相似度并生成推荐

功能说明：
1. 计算关键词相似度
   - 平均向量相似度 Sim_avg(A,B)
   - 最大匹配相似度 Sim_max(A,B)
   - 加权融合（α=0.4）
2. 计算整本书的语义相似度
3. 计算两本书之间的重叠标签数
4. 综合得分计算

作者：系统自动生成
日期：2026-03-23
"""

import sys
import os
import numpy as np
import json
import logging
from typing import List, Dict, Tuple, Optional
from sqlalchemy import create_engine, text
import pandas as pd

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] [%(name)s] %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class CrossDomainRecommender:
    """
    跨领域图书推荐器类
    
    用于计算图书之间的相似度并生成推荐
    """
    
    def __init__(self, config_path: str = None, **kwargs):
        self.host = kwargs.get('host', 'localhost')
        self.port = kwargs.get('port', 3306)
        self.user = kwargs.get('user', 'root')
        self.password = kwargs.get('password', '')
        self.database = kwargs.get('database', 'test')
        self.table = kwargs.get('table', 'books')
        
        self.alpha = kwargs.get('alpha', 0.4)
        self.a = kwargs.get('a', 0.6)
        self.beta = kwargs.get('beta', 0.25)
        
        logger.info(f"推荐器初始化参数: alpha={self.alpha}, a={self.a}, beta={self.beta}")
        
        connection_str = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        self.engine = create_engine(connection_str)
        
        import time
        start_time = time.time()
        self.books_data = self._load_books_data()
        end_time = time.time()
        logger.info(f"加载了 {len(self.books_data)} 本图书数据，耗时: {end_time - start_time:.2f}秒")
    
    def _load_books_data(self) -> list:
        import time
        start_time = time.time()
        
        books = []
        
        with self.engine.connect() as conn:
            query = text(f"SELECT book_id, title, embedding, keywords_embeddings, domain_tags FROM {self.table}")
            result = conn.execute(query)
            
            for row in result:
                book_id, title, embedding_str, keywords_embeddings_str, domain_tags_str = row
                
                try:
                    embedding = json.loads(embedding_str) if embedding_str else []
                except:
                    embedding = []
                
                try:
                    keywords_embeddings = json.loads(keywords_embeddings_str) if keywords_embeddings_str else []
                except:
                    keywords_embeddings = []
                
                try:
                    domain_tags = json.loads(domain_tags_str) if domain_tags_str else []
                except:
                    domain_tags = []
                
                books.append({
                    'book_id': book_id,
                    'title': title,
                    'embedding': embedding,
                    'keywords_embeddings': keywords_embeddings,
                    'domain_tags': domain_tags
                })
        
        end_time = time.time()
        logger.info(f"加载了 {len(books)} 本图书数据，耗时: {end_time - start_time:.2f}秒")
        
        return books

    def add_book_to_index(self, book_data: dict):
        """
        将新书添加到内存索引，使其可被推荐算法即时检索

        参数:
            book_data: 包含 book_id, title, embedding, keywords_embeddings, domain_tags 的字典
        """
        new_entry = {
            'book_id': book_data['book_id'],
            'title': book_data.get('title', ''),
            'embedding': book_data.get('embedding', []),
            'keywords_embeddings': book_data.get('keywords_embeddings', []),
            'domain_tags': book_data.get('domain_tags', []),
        }
        self.books_data.append(new_entry)
        logger.info(f"[推荐器] 新书已加入索引: book_id={book_data['book_id']}, title={book_data.get('title', '')}, 当前总数={len(self.books_data)}")
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2:
            return 0.0
        
        try:
            vec1_arr = np.array(vec1, dtype=np.float64)
            vec2_arr = np.array(vec2, dtype=np.float64)
            
            if vec1_arr.shape != vec2_arr.shape:
                logger.warning(f"向量维度不匹配: {vec1_arr.shape} vs {vec2_arr.shape}")
                return 0.0
            
            dot_product = np.dot(vec1_arr, vec2_arr)
            norm1 = np.linalg.norm(vec1_arr)
            norm2 = np.linalg.norm(vec2_arr)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.warning(f"余弦相似度计算异常: {e}")
            return 0.0
    
    def _calculate_keyword_similarity(self, keywords_embeddings_a: List[List[float]], 
                                      keywords_embeddings_b: List[List[float]]) -> Tuple[float, float, float]:
        if not keywords_embeddings_a or not keywords_embeddings_b:
            return 0.0, 0.0, 0.0
        
        try:
            emb_a = np.array(keywords_embeddings_a, dtype=np.float64)
            emb_b = np.array(keywords_embeddings_b, dtype=np.float64)
            
            if emb_a.ndim != 2 or emb_b.ndim != 2:
                return 0.0, 0.0, 0.0
            
            if emb_a.shape[1] != emb_b.shape[1]:
                logger.warning(f"关键词向量维度不匹配: {emb_a.shape[1]} vs {emb_b.shape[1]}")
                return 0.0, 0.0, 0.0
            
            avg_vec_a = np.mean(emb_a, axis=0)
            avg_vec_b = np.mean(emb_b, axis=0)
            sim_avg = self._cosine_similarity(avg_vec_a.tolist(), avg_vec_b.tolist())
            
            max_sim = 0.0
            for vec_a in keywords_embeddings_a:
                for vec_b in keywords_embeddings_b:
                    sim = self._cosine_similarity(vec_a, vec_b)
                    if sim > max_sim:
                        max_sim = sim
            sim_max = max_sim
            
            keyword_similarity = self.alpha * sim_avg + (1 - self.alpha) * sim_max
            
            return keyword_similarity, sim_avg, sim_max
        except Exception as e:
            logger.warning(f"关键词相似度计算异常: {e}")
            return 0.0, 0.0, 0.0
    
    def _calculate_semantic_similarity(self, embedding_a: List[float], embedding_b: List[float]) -> float:
        if not embedding_a or not embedding_b:
            return 0.0
        
        return self._cosine_similarity(embedding_a, embedding_b)
    
    def _calculate_overlap_coefficient(self, tags_a: List[str], tags_b: List[str], beta: float = None) -> Tuple[float, int]:
        if not tags_a or not tags_b:
            return 1.0, 0
        
        b = beta if beta is not None else self.beta
        overlap = len(set(tags_a) & set(tags_b))
        
        if overlap == 0:
            coefficient = 1.0
        elif overlap == 1:
            coefficient = 1 - b
        elif overlap == 2:
            coefficient = 1 - 2 * b
        else:
            coefficient = 0.0
        
        return coefficient, overlap
    
    def calculate_similarity(self, book_id_a: int, book_id_b: int, beta: float = None) -> Dict[str, float]:
        book_a = next((book for book in self.books_data if book['book_id'] == book_id_a), None)
        book_b = next((book for book in self.books_data if book['book_id'] == book_id_b), None)
        
        if not book_a or not book_b:
            return {
                'keyword_similarity': 0.0,
                'semantic_similarity': 0.0,
                'combined_similarity': 0.0,
                'overlap_coefficient': 0.0,
                'overlap_count': 0,
                'final_score': 0.0
            }
        
        keyword_similarity, sim_avg, sim_max = self._calculate_keyword_similarity(
            book_a['keywords_embeddings'], book_b['keywords_embeddings']
        )
        
        semantic_similarity = self._calculate_semantic_similarity(
            book_a['embedding'], book_b['embedding']
        )
        
        combined_similarity = self.a * semantic_similarity + (1 - self.a) * keyword_similarity
        
        overlap_coefficient, overlap_count = self._calculate_overlap_coefficient(
            book_a['domain_tags'], book_b['domain_tags'], beta=beta
        )
        
        final_score = combined_similarity * overlap_coefficient
        
        return {
            'keyword_similarity': keyword_similarity,
            'keyword_sim_avg': sim_avg,
            'keyword_sim_max': sim_max,
            'semantic_similarity': semantic_similarity,
            'combined_similarity': combined_similarity,
            'overlap_coefficient': overlap_coefficient,
            'overlap_count': overlap_count,
            'final_score': final_score
        }
    
    def get_recommendations(self, book_id: int, top_k: int = 10, beta: float = None) -> List[Dict]:
        recommendations = []
        
        for book in self.books_data:
            if book['book_id'] == book_id:
                continue
            
            similarity_data = self.calculate_similarity(book_id, book['book_id'], beta=beta)
            
            recommendation = {
                'book_id': book['book_id'],
                'title': book['title'],
                'domain_tags': book['domain_tags'],
                'final_score': similarity_data['final_score'],
                'semantic_similarity': similarity_data['semantic_similarity'],
                'keyword_similarity': similarity_data['keyword_similarity'],
                'overlap_coefficient': similarity_data['overlap_coefficient'],
                'overlap_count': similarity_data.get('overlap_count', 0)
            }
            recommendations.append(recommendation)
        
        recommendations.sort(key=lambda x: x['final_score'], reverse=True)
        
        return recommendations[:top_k]
    
    def get_cross_domain_recommendations(self, book_id: int, top_k: int = 10, beta: float = None) -> List[Dict]:
        recommendations = []
        target_book = next((book for book in self.books_data if book['book_id'] == book_id), None)
        
        if not target_book:
            logger.warning(f"未找到目标图书: book_id={book_id}")
            return []
        
        effective_beta = beta if beta is not None else self.beta
        target_tags = target_book['domain_tags']
        logger.info(f"跨域推荐 - 目标图书: {target_book['title']} (ID={book_id}), 领域标签: {target_tags}, beta={effective_beta}")
        
        for book in self.books_data:
            if book['book_id'] == book_id:
                continue
            
            similarity_data = self.calculate_similarity(book_id, book['book_id'], beta=beta)
            
            overlap_coefficient = similarity_data['overlap_coefficient']
            overlap_count = similarity_data.get('overlap_count', 0)
            
            if overlap_coefficient > 0:
                recommendation = {
                    'book_id': book['book_id'],
                    'title': book['title'],
                    'domain_tags': book['domain_tags'],
                    'final_score': similarity_data['final_score'],
                    'semantic_similarity': similarity_data['semantic_similarity'],
                    'keyword_similarity': similarity_data['keyword_similarity'],
                    'overlap_coefficient': overlap_coefficient,
                    'overlap_count': overlap_count,
                    'combined_similarity': similarity_data['combined_similarity']
                }
                recommendations.append(recommendation)
        
        recommendations.sort(key=lambda x: x['final_score'], reverse=True)
        
        domain_distribution = {}
        for rec in recommendations[:top_k]:
            for tag in rec.get('domain_tags', []):
                domain_distribution[tag] = domain_distribution.get(tag, 0) + 1
        
        logger.info(f"跨域推荐 - 候选数: {len(recommendations)}, Top-{min(top_k, len(recommendations))}领域分布: {domain_distribution}")
        if recommendations:
            top3 = recommendations[:3]
            for i, rec in enumerate(top3):
                logger.info(f"  Top{i+1}: {rec['title']} | 领域:{rec['domain_tags']} | "
                           f"得分:{rec['final_score']:.4f} | 语义:{rec['semantic_similarity']:.4f} | "
                           f"关键词:{rec['keyword_similarity']:.4f} | 重叠系数:{rec['overlap_coefficient']:.2f} | "
                           f"重叠数:{rec['overlap_count']}")
        
        return recommendations[:top_k]
