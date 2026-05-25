# -*- coding: utf-8 -*-
"""
图书领域标签自动标注模块
基于关键词匹配为图书自动分配领域标签

功能说明：
1. 支持从CSV文件读取图书数据
2. 支持从数据库读取图书数据（预留接口）
3. 使用关键词匹配算法为图书分配领域标签
4. 支持批量处理和单本书处理
5. 复用extract_keywords.py的数据加载和保存功能

核心规则：
- 输入：书名 + 内容简介 + 作者简介（合并为文本）
- 输出：领域标签列表（最多2个），按匹配分数降序排序
- 匹配分数：统计每个领域关键词在文本中的出现次数
- 标签选取：选择分数 > 0 的前1-2个领域，全部为0则返回 ["其他"]

作者：系统自动生成
日期：2025-03-22
"""

import pandas as pd
import numpy as np
import re
import json
import os
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

# 从extract_keywords模块导入数据加载器和保存器
from extract_keywords import BookDataLoader, BookDataSaver


class DomainTagAssigner:
    """
    领域标签分配器类
    
    基于关键词匹配为图书自动分配领域标签
    """
    
    def __init__(self, domain_config_path: str = None):
        """
        初始化领域标签分配器
        
        参数:
            domain_config_path: 领域标签配置文件路径，如果为None则使用默认路径
        """
        self.domain_config = self._load_domain_config(domain_config_path)
        self.domain_keywords = self._build_domain_keywords()
        
    def _load_domain_config(self, domain_config_path: str = None) -> Dict:
        """
        加载领域标签配置文件
        
        参数:
            domain_config_path: 配置文件路径
            
        返回:
            领域标签配置字典
        """
        if domain_config_path is None:
            domain_config_path = os.path.join(os.path.dirname(__file__), 'domain_tags.json')
        
        if not os.path.exists(domain_config_path):
            raise FileNotFoundError(f"领域标签配置文件不存在: {domain_config_path}")
        
        with open(domain_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return config
    
    def _build_domain_keywords(self) -> Dict[str, List[str]]:
        """
        构建领域关键词字典
        
        返回:
            领域名称到关键词列表的映射字典
        """
        domain_keywords = {}
        
        for domain_info in self.domain_config:
            domain_name = domain_info['domain']
            keywords = domain_info.get('keywords', [])
            domain_keywords[domain_name] = keywords
        
        return domain_keywords
    
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
        
        # 去除标点符号和特殊字符（保留中文、英文、数字）
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', text)
        
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text.lower()  # 转为小写以便匹配
    
    def _calculate_domain_score(self, text: str, keywords: List[str]) -> int:
        """
        计算领域匹配分数
        
        参数:
            text: 预处理后的文本
            keywords: 领域关键词列表
            
        返回:
            匹配分数（关键词出现次数总和）
        """
        score = 0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # 统计关键词在文本中的出现次数
            count = text.count(keyword_lower)
            score += count
        
        return score
    
    def _get_top_domains(self, scores: Dict[str, int], max_domains: int = 2) -> List[str]:
        """
        获取分数最高的领域标签
        
        参数:
            scores: 领域分数字典 {领域名: 分数}
            max_domains: 最多返回的领域数量
            
        返回:
            领域标签列表，按分数降序排序
        """
        # 按分数降序排序
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 筛选分数 > 0 的领域
        valid_domains = [(domain, score) for domain, score in sorted_domains if score > 0]
        
        # 取前max_domains个领域
        top_domains = [domain for domain, score in valid_domains[:max_domains]]
        
        # 如果没有匹配的领域，返回 ["其他"]
        if not top_domains:
            return ["其他"]
        
        return top_domains
    
    def assign_domain_tags(self, title: str, content_intro: str, author_intro: str, 
                          max_domains: int = 2) -> List[str]:
        """
        为单本书分配领域标签
        
        参数:
            title: 书名
            content_intro: 内容简介
            author_intro: 作者简介
            max_domains: 最多分配的领域标签数量
            
        返回:
            领域标签列表，按匹配分数降序排序
        """
        # 合并书名、内容简介和作者简介
        combined_text = f"{title} {content_intro} {author_intro}"
        
        # 预处理文本
        processed_text = self._preprocess_text(combined_text)
        
        # 如果文本为空，返回 ["其他"]
        if not processed_text:
            return ["其他"]
        
        # 计算每个领域的匹配分数
        scores = {}
        for domain_name, keywords in self.domain_keywords.items():
            score = self._calculate_domain_score(processed_text, keywords)
            scores[domain_name] = score
        
        # 获取分数最高的领域标签
        domain_tags = self._get_top_domains(scores, max_domains)
        
        return domain_tags
    
    def assign_domain_tags_batch(self, df: pd.DataFrame, max_domains: int = 2) -> pd.DataFrame:
        """
        批量为图书分配领域标签
        
        参数:
            df: 图书数据DataFrame，必须包含 'title', 'book_intro', 'author_intro' 列
            max_domains: 每本书最多分配的领域标签数量
            
        返回:
            添加了 'domain' 列的DataFrame
        """
        # 检查必要的列是否存在
        required_columns = ['title', 'book_intro', 'author_intro']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"DataFrame缺少必要的列: {missing_columns}")
        
        # 批量分配领域标签
        domain_tags_list = []
        
        for idx, row in df.iterrows():
            title = row.get('title', '')
            content_intro = row.get('book_intro', '')
            author_intro = row.get('author_intro', '')
            
            # 分配领域标签
            domain_tags = self.assign_domain_tags(
                title,
                content_intro,
                author_intro,
                max_domains=max_domains
            )
            
            domain_tags_list.append(domain_tags)
        
        # 添加领域标签列
        df = df.copy()
        df['domain'] = domain_tags_list
        
        return df
    
    def get_domain_statistics(self, df: pd.DataFrame) -> Dict:
        """
        统计领域标签分布情况
        
        参数:
            df: 包含 'domain' 列的DataFrame
            
        返回:
            领域统计信息字典
        """
        if 'domain' not in df.columns:
            raise ValueError("DataFrame缺少 'domain' 列")
        
        # 统计每个领域出现的次数
        domain_count = defaultdict(int)
        
        for domain_tags in df['domain']:
            for domain in domain_tags:
                domain_count[domain] += 1
        
        # 计算百分比
        total_books = len(df)
        domain_stats = {}
        
        for domain, count in sorted(domain_count.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_books) * 100
            domain_stats[domain] = {
                'count': count,
                'percentage': round(percentage, 2)
            }
        
        return domain_stats


def assign_domain_tags_from_database(source_type: str, source_config: Dict,
                                    target_type: str = None, target_config: Dict = None,
                                    max_domains: int = 2, domain_config_path: str = None) -> pd.DataFrame:
    """
    从数据库分配图书领域标签（主函数）
    
    参数:
        source_type: 数据源类型 ('mysql', 'postgresql', 'mongodb')
        source_config: 数据源配置字典
        target_type: 目标类型（如果为None，则与source_type相同）
        target_config: 目标配置字典（如果为None，则与source_config相同）
        max_domains: 每本书最多分配的领域标签数量
        domain_config_path: 领域标签配置文件路径
        
    返回:
        包含领域标签的DataFrame
        
    使用示例:
        # 从MySQL分配领域标签并保存回MySQL
        source_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': 'password',
            'database': 'book_db',
            'table': 'books'
        }
        df = assign_domain_tags_from_database('mysql', source_config)
        
        # 从MySQL分配领域标签并保存到PostgreSQL
        target_config = {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': 'password',
            'database': 'book_db',
            'table': 'books'
        }
        df = assign_domain_tags_from_database('mysql', source_config, 'postgresql', target_config)
    """
    print("=" * 60)
    print(f"开始从数据库分配图书领域标签")
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
    
    # 初始化领域标签分配器
    assigner = DomainTagAssigner(domain_config_path=domain_config_path)
    
    # 批量分配领域标签
    print(f"\n正在分配领域标签（每本书最多 {max_domains} 个标签）...")
    df = assigner.assign_domain_tags_batch(df, max_domains=max_domains)
    
    # 保存结果
    saver = BookDataSaver(target_type=target_type, target_config=target_config)
    saver.save_data(df, **target_config)
    
    # 统计领域分布
    print("\n正在统计领域标签分布...")
    domain_stats = assigner.get_domain_statistics(df)
    
    # 显示统计信息
    print("\n" + "=" * 60)
    print("领域标签分配完成！")
    print("=" * 60)
    print(f"总计处理: {len(df)} 本书")
    print(f"每本书标签数: {max_domains}")
    print(f"数据已保存到 {target_type} 数据库")
    
    print("\n领域标签分布:")
    print("-" * 60)
    for domain, stats in domain_stats.items():
        print(f"{domain}: {stats['count']} 本 ({stats['percentage']}%)")
    
    return df


if __name__ == '__main__':
    # 从MySQL数据库分配领域标签
    print("\n从MySQL数据库分配领域标签")
    print("-" * 60)
    
    source_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'Anny0607',
        'database': 'test',
        'table': 'books'
    }
    
    df = assign_domain_tags_from_database(
        source_type='mysql',
        source_config=source_config,
        max_domains=2
    )
