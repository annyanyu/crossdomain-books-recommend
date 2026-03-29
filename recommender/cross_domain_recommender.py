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
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import json
from typing import List, Dict, Tuple, Optional
from sqlalchemy import create_engine, text
import pandas as pd

from config import get_config_manager


class CrossDomainRecommender:
    """
    跨领域图书推荐器类
    
    用于计算图书之间的相似度并生成推荐
    """
    
    def __init__(self, config_path: str = None, **kwargs):
        """
        初始化推荐器
        
        参数:
            config_path: 配置文件路径，如果为None则使用默认路径
            **kwargs: 可覆盖配置文件的参数（host, port, user, password, database, table, alpha, a, beta）
        """
        # 加载配置
        config = get_config_manager(config_path)
        db_config = config.get_database_config()
        rec_config = config.get_recommender_config()
        
        # 合并配置和传入参数
        self.host = kwargs.get('host', db_config.get('host', 'localhost'))
        self.port = kwargs.get('port', db_config.get('port', 3306))
        self.user = kwargs.get('user', db_config.get('user', 'root'))
        self.password = kwargs.get('password', db_config.get('password', ''))
        self.database = kwargs.get('database', db_config.get('database', 'test'))
        self.table = kwargs.get('table', db_config.get('table', 'books'))
        
        # 配置参数
        self.alpha = kwargs.get('alpha', rec_config.get('alpha', 0.4))
        self.a = kwargs.get('a', rec_config.get('a', 0.6))
        self.beta = kwargs.get('beta', rec_config.get('beta', 0.25))
        
        # 创建数据库连接
        connection_str = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        self.engine = create_engine(connection_str)
        
        # 加载图书数据
        self.books_data = self._load_books_data()
        print(f"加载了 {len(self.books_data)} 本图书数据")
    
    def _load_books_data(self) -> pd.DataFrame:
        """
        从数据库加载图书数据
        
        返回:
            包含图书数据的DataFrame
        """
        with self.engine.connect() as conn:
            query = text(f"SELECT book_id, title, embedding, keywords_embeddings, domain_tags FROM {self.table}")
            result = conn.execute(query)
            rows = result.fetchall()
        
        # 转换为DataFrame
        columns = ['book_id', 'title', 'embedding', 'keywords_embeddings', 'domain_tags']
        df = pd.DataFrame(rows, columns=columns)
        
        # 解析JSON列
        df['embedding'] = df['embedding'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
        df['keywords_embeddings'] = df['keywords_embeddings'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
        df['domain_tags'] = df['domain_tags'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
        
        return df
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算两个向量之间的余弦相似度
        
        参数:
            vec1: 第一个向量
            vec2: 第二个向量
            
        返回:
            余弦相似度值
        """
        if not vec1 or not vec2:
            return 0.0
        
        # 计算点积
        dot_product = np.dot(vec1, vec2)
        
        # 计算模长
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        # 避免除零错误
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _calculate_keyword_similarity(self, keywords_embeddings_a: List[List[float]], 
                                      keywords_embeddings_b: List[List[float]]) -> float:
        """
        计算两本书之间的关键词相似度
        
        参数:
            keywords_embeddings_a: 第一本书的关键词嵌入向量列表
            keywords_embeddings_b: 第二本书的关键词嵌入向量列表
            
        返回:
            关键词相似度值
        """
        if not keywords_embeddings_a or not keywords_embeddings_b:
            return 0.0
        
        # 计算平均向量相似度 Sim_avg(A,B)
        avg_vec_a = np.mean(keywords_embeddings_a, axis=0).tolist()
        avg_vec_b = np.mean(keywords_embeddings_b, axis=0).tolist()
        sim_avg = self._cosine_similarity(avg_vec_a, avg_vec_b)
        
        # 计算最大匹配相似度 Sim_max(A,B)
        max_sim = 0.0
        for vec_a in keywords_embeddings_a:
            for vec_b in keywords_embeddings_b:
                sim = self._cosine_similarity(vec_a, vec_b)
                if sim > max_sim:
                    max_sim = sim
        sim_max = max_sim
        
        # 加权融合
        keyword_similarity = self.alpha * sim_avg + (1 - self.alpha) * sim_max
        
        return keyword_similarity
    
    def _calculate_semantic_similarity(self, embedding_a: List[float], embedding_b: List[float]) -> float:
        """
        计算两本书之间的语义相似度
        
        参数:
            embedding_a: 第一本书的整体嵌入向量
            embedding_b: 第二本书的整体嵌入向量
            
        返回:
            语义相似度值
        """
        if not embedding_a or not embedding_b:
            return 0.0
        
        return self._cosine_similarity(embedding_a, embedding_b)
    
    def _calculate_overlap_coefficient(self, tags_a: List[str], tags_b: List[str]) -> float:
        """
        计算两本书之间的重叠标签系数
        
        参数:
            tags_a: 第一本书的领域标签
            tags_b: 第二本书的领域标签
            
        返回:
            重叠标签系数
        """
        if not tags_a or not tags_b:
            return 1.0  # 如果任一标签列表为空，视为完全跨域
        
        # 计算重叠标签数
        overlap = len(set(tags_a) & set(tags_b))
        
        # 根据重叠标签数计算系数
        if overlap == 0:
            coefficient = 1.0  # 完全跨域
        elif overlap == 1:
            coefficient = 1 - self.beta
        elif overlap == 2:
            coefficient = 1 - 2 * self.beta
        else:
            # 重叠标签数超过2，系数为0
            coefficient = 0.0
        
        return coefficient
    
    def calculate_similarity(self, book_id_a: int, book_id_b: int) -> Dict[str, float]:
        """
        计算两本书之间的综合相似度
        
        参数:
            book_id_a: 第一本书的ID
            book_id_b: 第二本书的ID
            
        返回:
            包含各种相似度指标的字典
        """
        # 获取两本书的数据
        book_a = self.books_data[self.books_data['book_id'] == book_id_a].iloc[0]
        book_b = self.books_data[self.books_data['book_id'] == book_id_b].iloc[0]
        
        # 计算关键词相似度
        keyword_similarity = self._calculate_keyword_similarity(
            book_a['keywords_embeddings'], book_b['keywords_embeddings']
        )
        
        # 计算语义相似度
        semantic_similarity = self._calculate_semantic_similarity(
            book_a['embedding'], book_b['embedding']
        )
        
        # 计算综合相似度
        combined_similarity = self.a * semantic_similarity + (1 - self.a) * keyword_similarity
        
        # 计算重叠标签系数
        overlap_coefficient = self._calculate_overlap_coefficient(
            book_a['domain_tags'], book_b['domain_tags']
        )
        
        # 计算最终得分
        final_score = combined_similarity * overlap_coefficient
        
        return {
            'keyword_similarity': keyword_similarity,
            'semantic_similarity': semantic_similarity,
            'combined_similarity': combined_similarity,
            'overlap_coefficient': overlap_coefficient,
            'final_score': final_score
        }
    
    def get_recommendations(self, book_id: int, top_k: int = 10) -> List[Dict]:
        """
        为指定图书生成推荐
        
        参数:
            book_id: 目标图书的ID
            top_k: 返回的推荐数量
            
        返回:
            推荐图书列表，按相似度降序排列
        """
        recommendations = []
        
        # 遍历所有图书，计算与目标图书的相似度
        for _, book in self.books_data.iterrows():
            if book['book_id'] == book_id:
                continue  # 跳过自身
            
            # 计算相似度
            similarity_data = self.calculate_similarity(book_id, book['book_id'])
            
            # 添加到推荐列表
            recommendation = {
                'book_id': book['book_id'],
                'title': book['title'],
                'final_score': similarity_data['final_score'],
                'semantic_similarity': similarity_data['semantic_similarity'],
                'keyword_similarity': similarity_data['keyword_similarity'],
                'overlap_coefficient': similarity_data['overlap_coefficient']
            }
            recommendations.append(recommendation)
        
        # 按最终得分降序排序
        recommendations.sort(key=lambda x: x['final_score'], reverse=True)
        
        # 返回前top_k个推荐
        return recommendations[:top_k]
    
    def get_cross_domain_recommendations(self, book_id: int, top_k: int = 10) -> List[Dict]:
        """
        为指定图书生成跨领域推荐
        
        参数:
            book_id: 目标图书的ID
            top_k: 返回的推荐数量
            
        返回:
            跨领域推荐图书列表，按相似度降序排列
        """
        recommendations = []
        target_book = self.books_data[self.books_data['book_id'] == book_id].iloc[0]
        target_tags = target_book['domain_tags']
        
        # 遍历所有图书，计算与目标图书的相似度
        for _, book in self.books_data.iterrows():
            if book['book_id'] == book_id:
                continue  # 跳过自身
            
            # 计算相似度
            similarity_data = self.calculate_similarity(book_id, book['book_id'])
            
            # 检查是否为跨领域（重叠标签数为0）
            book_tags = book['domain_tags']
            overlap = len(set(target_tags) & set(book_tags))
            
            if overlap == 0:  # 完全跨域
                # 添加到推荐列表
                recommendation = {
                    'book_id': book['book_id'],
                    'title': book['title'],
                    'final_score': similarity_data['final_score'],
                    'semantic_similarity': similarity_data['semantic_similarity'],
                    'keyword_similarity': similarity_data['keyword_similarity'],
                    'overlap_coefficient': similarity_data['overlap_coefficient']
                }
                recommendations.append(recommendation)
        
        # 按最终得分降序排序
        recommendations.sort(key=lambda x: x['final_score'], reverse=True)
        
        # 返回前top_k个推荐
        return recommendations[:top_k]


def main():
    """
    主函数，用于测试推荐器功能
    """
    # 初始化推荐器
    recommender = CrossDomainRecommender()
    
    # 测试单本书的推荐
    test_book_id = 1  # 测试用的图书ID
    print(f"\n为图书ID {test_book_id} 生成推荐：")
    recommendations = recommender.get_recommendations(test_book_id, top_k=5)
    
    print("\nTop 5 推荐：")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec['title']} (得分: {rec['final_score']:.4f})")
        print(f"   语义相似度: {rec['semantic_similarity']:.4f}")
        print(f"   关键词相似度: {rec['keyword_similarity']:.4f}")
        print(f"   跨域系数: {rec['overlap_coefficient']:.4f}")
        print()
    
    # 测试跨领域推荐
    print(f"\n为图书ID {test_book_id} 生成跨领域推荐：")
    cross_domain_recs = recommender.get_cross_domain_recommendations(test_book_id, top_k=5)
    
    print("\nTop 5 跨领域推荐：")
    for i, rec in enumerate(cross_domain_recs, 1):
        print(f"{i}. {rec['title']} (得分: {rec['final_score']:.4f})")
        print(f"   语义相似度: {rec['semantic_similarity']:.4f}")
        print(f"   关键词相似度: {rec['keyword_similarity']:.4f}")
        print(f"   跨域系数: {rec['overlap_coefficient']:.4f}")
        print()


if __name__ == '__main__':
    main()
