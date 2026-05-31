# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import re
import json
import os
import math
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from extract_keywords import BookDataLoader, BookDataSaver


TITLE_WEIGHT = 3.0
INTRO_WEIGHT = 1.0
AUTHOR_WEIGHT = 0.5

LEVEL_WEIGHTS = {
    'core': 5.0,
    'feature': 2.0,
    'general': 0.5,
    'core_en': 5.0,
}

MIN_SCORE_THRESHOLD = 3.0
SECOND_TAG_RATIO = 0.3

TITLE_MATCH_FILE = 'title_match_rules.json'


class DomainTagAssigner:

    def __init__(self, domain_config_path: str = None):
        self.domain_config = self._load_domain_config(domain_config_path)
        self.domain_keywords = self._build_domain_keywords()
        self.title_match_rules = self._load_title_match_rules()
        self.idf_cache = {}

    def _load_domain_config(self, domain_config_path: str = None) -> List[Dict]:
        if domain_config_path is None:
            domain_config_path = os.path.join(os.path.dirname(__file__), 'domain_tags.json')

        if not os.path.exists(domain_config_path):
            raise FileNotFoundError(f"领域标签配置文件不存在: {domain_config_path}")

        with open(domain_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return config

    def _build_domain_keywords(self) -> Dict[str, Dict[str, List[str]]]:
        domain_keywords = {}

        for domain_info in self.domain_config:
            domain_name = domain_info['domain']
            kw = domain_info.get('keywords', {})

            if isinstance(kw, list):
                domain_keywords[domain_name] = {
                    'core': kw,
                    'feature': [],
                    'general': [],
                    'core_en': [],
                }
            elif isinstance(kw, dict):
                domain_keywords[domain_name] = {
                    'core': kw.get('core', []),
                    'feature': kw.get('feature', []),
                    'general': kw.get('general', []),
                    'core_en': kw.get('core_en', []),
                }

        return domain_keywords

    def _load_title_match_rules(self) -> Dict[str, List[str]]:
        rules_path = os.path.join(os.path.dirname(__file__), TITLE_MATCH_FILE)
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _preprocess_text(self, text: str) -> str:
        if pd.isna(text) or text is None:
            return ""

        text = str(text)
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text.lower()

    def _is_english_text(self, text: str) -> bool:
        latin_chars = len(re.findall(r'[a-zA-Z]', text))
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', text))
        total = latin_chars + chinese_chars
        if total == 0:
            return False
        return latin_chars / total > 0.6

    def _calculate_domain_score(self, text: str, title_text: str,
                                keywords_dict: Dict[str, List[str]],
                                is_english: bool) -> float:
        score = 0.0

        levels_to_use = ['core', 'feature', 'general']
        if is_english:
            levels_to_use = ['core_en', 'feature']

        for level in levels_to_use:
            keywords = keywords_dict.get(level, [])
            if not keywords:
                continue

            weight = LEVEL_WEIGHTS.get(level, 1.0)

            for keyword in keywords:
                keyword_lower = keyword.lower()
                count_title = title_text.count(keyword_lower)
                count_body = text.count(keyword_lower)

                title_boost = count_title * (TITLE_WEIGHT - 1.0)
                body_count = count_body + count_title

                idf = self.idf_cache.get(keyword_lower, 1.0)

                score += weight * idf * (body_count + title_boost)

        return score

    def compute_idf(self, df: pd.DataFrame):
        n = len(df)
        doc_freq = defaultdict(int)

        for idx, row in df.iterrows():
            title = str(row.get('title', ''))
            intro = str(row.get('book_intro', ''))
            author = str(row.get('author_intro', ''))

            combined = self._preprocess_text(f"{title} {intro} {author}")

            seen = set()
            for domain_name, kw_dict in self.domain_keywords.items():
                for level, keywords in kw_dict.items():
                    for keyword in keywords:
                        kw_lower = keyword.lower()
                        if kw_lower not in seen and kw_lower in combined:
                            doc_freq[kw_lower] += 1
                            seen.add(kw_lower)

        for keyword, df_count in doc_freq.items():
            self.idf_cache[keyword] = math.log((n + 1) / (df_count + 1)) + 1.0

    def _check_title_match(self, title: str) -> Optional[List[str]]:
        if not self.title_match_rules:
            return None

        title_clean = title.strip()

        for pattern, tags in self.title_match_rules.items():
            if pattern in title_clean:
                return tags

        return None

    def _get_top_domains(self, scores: Dict[str, float], max_domains: int = 2) -> List[str]:
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        valid_domains = [(domain, score) for domain, score in sorted_domains if score > 0]

        if not valid_domains:
            return ["其他"]

        top_domain, top_score = valid_domains[0]

        if top_score < MIN_SCORE_THRESHOLD:
            return ["其他"]

        threshold = max(MIN_SCORE_THRESHOLD, SECOND_TAG_RATIO * top_score)

        result = [top_domain]

        for domain, score in valid_domains[1:max_domains]:
            if score >= threshold:
                result.append(domain)

        return result

    def assign_domain_tags(self, title: str, content_intro: str, author_intro: str,
                          max_domains: int = 2) -> List[str]:
        title_match = self._check_title_match(title)
        if title_match is not None:
            return title_match

        title_processed = self._preprocess_text(title)
        intro_processed = self._preprocess_text(content_intro)
        author_processed = self._preprocess_text(author_intro)

        combined_text = f"{intro_processed} {author_processed}"

        if not combined_text.strip() and not title_processed.strip():
            return ["其他"]

        is_english = self._is_english_text(f"{title_processed} {combined_text}")

        scores = {}
        for domain_name, keywords_dict in self.domain_keywords.items():
            score = self._calculate_domain_score(
                combined_text, title_processed, keywords_dict, is_english
            )
            scores[domain_name] = score

        domain_tags = self._get_top_domains(scores, max_domains)

        return domain_tags

    def assign_domain_tags_batch(self, df: pd.DataFrame, max_domains: int = 2) -> pd.DataFrame:
        required_columns = ['title', 'book_intro', 'author_intro']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(f"DataFrame缺少必要的列: {missing_columns}")

        self.compute_idf(df)

        domain_tags_list = []

        for idx, row in df.iterrows():
            title = row.get('title', '')
            content_intro = row.get('book_intro', '')
            author_intro = row.get('author_intro', '')

            domain_tags = self.assign_domain_tags(
                title,
                content_intro,
                author_intro,
                max_domains=max_domains
            )

            domain_tags_list.append(domain_tags)

        df = df.copy()
        df['domain'] = domain_tags_list

        return df

    def get_domain_statistics(self, df: pd.DataFrame) -> Dict:
        if 'domain' not in df.columns:
            raise ValueError("DataFrame缺少 'domain' 列")

        domain_count = defaultdict(int)

        for domain_tags in df['domain']:
            for domain in domain_tags:
                domain_count[domain] += 1

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
    print("=" * 60)
    print(f"开始从数据库分配图书领域标签")
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

    assigner = DomainTagAssigner(domain_config_path=domain_config_path)

    print(f"\n正在分配领域标签（每本书最多 {max_domains} 个标签）...")
    df = assigner.assign_domain_tags_batch(df, max_domains=max_domains)

    saver = BookDataSaver(target_type=target_type, target_config=target_config)
    saver.save_data(df, **target_config)

    print("\n正在统计领域标签分布...")
    domain_stats = assigner.get_domain_statistics(df)

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
