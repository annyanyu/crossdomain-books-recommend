# -*- coding: utf-8 -*-
"""
多目标效用排序算法模块
用于支持前端用户按不同维度动态排序推荐结果

功能说明：
1. 支持三种排序模式：
   - 综合排序 (comprehensive)：按 FinalScore 降序
   - 评分排序 (rating)：按豆瓣评分降序
   - 最新排序 (newest)：按出版日期降序
2. 处理缺失值，确保排序的健壮性
3. 提供与前端交互的接口

作者：系统自动生成
日期：2026-03-23
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime


class MultiObjectiveRanker:
    """
    多目标效用排序器类
    
    支持多种排序模式，处理缺失值，为前端提供排序功能
    """
    
    def __init__(self):
        """
        初始化排序器
        """
        # 定义排序模式配置
        self.sort_modes = {
            'comprehensive': {
                'key': 'final_score',
                'direction': 'desc',
                'name': '综合排序',
                'description': '按综合得分排序，综合考虑语义相似度、关键词相似度和跨域系数'
            },
            'rating': {
                'key': 'rating',
                'direction': 'desc',
                'name': '评分排序',
                'description': '按豆瓣评分排序，高分书籍排在前面'
            },
            'newest': {
                'key': 'publication_date',
                'direction': 'desc',
                'name': '最新排序',
                'description': '按出版日期排序，新出版的书籍排在前面'
            }
        }
    
    def _parse_publication_date(self, date_str: Optional[str]) -> datetime:
        """
        解析出版日期字符串
        
        参数:
            date_str: 出版日期字符串
            
        返回:
            解析后的datetime对象，如果解析失败返回一个早日期
        """
        if not date_str:
            # 缺失日期视为非常早的日期
            return datetime(1900, 1, 1)
        
        # 尝试不同的日期格式
        formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日', '%Y-%m', '%Y/%m', '%Y年%m月', '%Y']
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # 如果所有格式都解析失败，返回早日期
        return datetime(1900, 1, 1)
    
    def _process_missing_values(self, recommendations: List[Dict]) -> List[Dict]:
        """
        处理推荐结果中的缺失值
        
        参数:
            recommendations: 推荐结果列表
            
        返回:
            处理后的推荐结果列表
        """
        processed_recommendations = []
        
        for rec in recommendations:
            # 处理综合得分缺失值
            if 'final_score' not in rec or rec['final_score'] is None:
                rec['final_score'] = 0.0
            
            # 处理评分缺失值
            if 'rating' not in rec or rec['rating'] is None:
                rec['rating'] = 0.0
            
            # 处理出版日期缺失值
            if 'publication_date' not in rec or rec['publication_date'] is None:
                rec['publication_date'] = '1900-01-01'
            
            # 解析出版日期
            rec['_parsed_date'] = self._parse_publication_date(rec['publication_date'])
            
            processed_recommendations.append(rec)
        
        return processed_recommendations
    
    def sort_recommendations(self, recommendations: List[Dict], sort_mode: str = 'comprehensive') -> List[Dict]:
        """
        对推荐结果进行排序
        
        参数:
            recommendations: 推荐结果列表
            sort_mode: 排序模式，可选值：'comprehensive', 'rating', 'newest'
            
        返回:
            排序后的推荐结果列表
        """
        # 验证排序模式
        if sort_mode not in self.sort_modes:
            raise ValueError(f"不支持的排序模式: {sort_mode}，支持的模式: {list(self.sort_modes.keys())}")
        
        # 处理缺失值
        processed_recs = self._process_missing_values(recommendations)
        
        # 获取排序配置
        sort_config = self.sort_modes[sort_mode]
        sort_key = sort_config['key']
        direction = sort_config['direction']
        
        # 根据排序模式选择排序键
        if sort_key == 'publication_date':
            # 对于日期排序，使用解析后的日期
            sort_key = '_parsed_date'
        
        # 执行排序
        reverse = (direction == 'desc')
        sorted_recs = sorted(processed_recs, key=lambda x: x[sort_key], reverse=reverse)
        
        # 移除临时解析的日期字段
        for rec in sorted_recs:
            if '_parsed_date' in rec:
                del rec['_parsed_date']
        
        return sorted_recs
    
    def get_supported_sort_modes(self) -> List[Dict]:
        """
        获取支持的排序模式列表
        
        返回:
            排序模式配置列表
        """
        modes = []
        for mode_key, mode_config in self.sort_modes.items():
            modes.append({
                'key': mode_key,
                'name': mode_config['name'],
                'description': mode_config['description']
            })
        return modes
    
    def sort_with_filter(self, recommendations: List[Dict], sort_mode: str = 'comprehensive',
                        min_rating: Optional[float] = None, 
                        max_price: Optional[float] = None) -> List[Dict]:
        """
        带过滤条件的排序
        
        参数:
            recommendations: 推荐结果列表
            sort_mode: 排序模式
            min_rating: 最低评分过滤
            max_price: 最高价格过滤
            
        返回:
            过滤并排序后的推荐结果列表
        """
        # 先过滤
        filtered_recs = recommendations.copy()
        
        # 评分过滤
        if min_rating is not None:
            filtered_recs = [rec for rec in filtered_recs 
                           if (rec.get('rating', 0.0) or 0.0) >= min_rating]
        
        # 价格过滤
        if max_price is not None:
            filtered_recs = [rec for rec in filtered_recs 
                           if (rec.get('price', 0.0) or 0.0) <= max_price]
        
        # 再排序
        return self.sort_recommendations(filtered_recs, sort_mode)


def main():
    """
    主函数，用于测试排序器功能
    """
    # 创建测试数据
    test_recommendations = [
        {
            'book_id': 1,
            'title': '深度学习入门',
            'final_score': 0.85,
            'rating': 4.5,
            'publication_date': '2023-01-15',
            'price': 89.0
        },
        {
            'book_id': 2,
            'title': 'Python编程从入门到精通',
            'final_score': 0.78,
            'rating': 4.2,
            'publication_date': '2022-06-10',
            'price': 69.0
        },
        {
            'book_id': 3,
            'title': '数据结构与算法分析',
            'final_score': 0.92,
            'rating': None,  # 缺失评分
            'publication_date': '2021-03-20',
            'price': 79.0
        },
        {
            'book_id': 4,
            'title': '人工智能导论',
            'final_score': 0.88,
            'rating': 4.7,
            'publication_date': None,  # 缺失日期
            'price': 99.0
        },
        {
            'book_id': 5,
            'title': '机器学习实战',
            'final_score': None,  # 缺失综合分
            'rating': 4.3,
            'publication_date': '2024-02-01',
            'price': 109.0
        }
    ]
    
    # 初始化排序器
    ranker = MultiObjectiveRanker()
    
    # 测试不同排序模式
    print("支持的排序模式:")
    for mode in ranker.get_supported_sort_modes():
        print(f"- {mode['key']}: {mode['name']} - {mode['description']}")
    
    # 综合排序
    print("\n综合排序结果:")
    comprehensive_sorted = ranker.sort_recommendations(test_recommendations, 'comprehensive')
    for i, rec in enumerate(comprehensive_sorted, 1):
        print(f"{i}. {rec['title']} (综合得分: {rec.get('final_score', 'N/A'):.2f})")
    
    # 评分排序
    print("\n评分排序结果:")
    rating_sorted = ranker.sort_recommendations(test_recommendations, 'rating')
    for i, rec in enumerate(rating_sorted, 1):
        print(f"{i}. {rec['title']} (评分: {rec.get('rating', 'N/A')})")
    
    # 最新排序
    print("\n最新排序结果:")
    newest_sorted = ranker.sort_recommendations(test_recommendations, 'newest')
    for i, rec in enumerate(newest_sorted, 1):
        print(f"{i}. {rec['title']} (出版日期: {rec.get('publication_date', 'N/A')})")
    
    # 测试带过滤的排序
    print("\n带过滤的排序结果 (评分≥4.0):")
    filtered_sorted = ranker.sort_with_filter(test_recommendations, 'comprehensive', min_rating=4.0)
    for i, rec in enumerate(filtered_sorted, 1):
        print(f"{i}. {rec['title']} (评分: {rec.get('rating', 'N/A')}, 综合得分: {rec.get('final_score', 'N/A'):.2f})")


if __name__ == '__main__':
    main()
