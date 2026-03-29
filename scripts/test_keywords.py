#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
关键词提取测试脚本

功能说明：
1. 测试CSV文件关键词提取
2. 测试单本书关键词提取
3. 测试数据库关键词提取（需要配置）
4. 测试不同参数组合
5. 生成测试报告

使用方法：
    python test_keywords.py

作者：系统自动生成
日期：2025-03-22
"""

import sys
import os
import time
from typing import List, Dict

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.extract_keywords import (
    KeywordExtractor,
    BookDataLoader,
    BookDataSaver,
    extract_keywords_batch,
    extract_keywords_from_database
)


class TestRunner:
    """
    测试运行器类
    """
    
    def __init__(self):
        self.test_results = []
        self.start_time = time.time()
    
    def run_test(self, test_name: str, test_func):
        """
        运行单个测试
        
        参数:
            test_name: 测试名称
            test_func: 测试函数
        """
        print(f"\n{'='*60}")
        print(f"运行测试: {test_name}")
        print(f"{'='*60}")
        
        test_start = time.time()
        result = {
            'test_name': test_name,
            'start_time': test_start,
            'success': False,
            'error': None,
            'duration': 0
        }
        
        try:
            test_func()
            result['success'] = True
            print(f"✓ 测试通过: {test_name}")
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
            print(f"✗ 测试失败: {test_name}")
            print(f"  错误信息: {e}")
        
        result['duration'] = time.time() - test_start
        self.test_results.append(result)
        
        return result['success']
    
    def print_summary(self):
        """
        打印测试摘要
        """
        print(f"\n{'='*60}")
        print("测试摘要")
        print(f"{'='*60}")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"成功率: {passed_tests/total_tests*100:.2f}%")
        print(f"总耗时: {time.time() - self.start_time:.2f}秒")
        
        if failed_tests > 0:
            print(f"\n失败的测试:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test_name']}: {result['error']}")
        
        print(f"{'='*60}\n")


def test_csv_extraction():
    """
    测试CSV文件关键词提取
    """
    csv_path = '../test/books_test.csv'
    output_path = '../test/books_test_with_keywords.csv'
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"测试文件不存在: {csv_path}")
    
    # 提取关键词
    df = extract_keywords_batch(
        csv_path=csv_path,
        output_path=output_path,
        top_k=10
    )
    
    # 验证结果
    assert df is not None, "返回的DataFrame为None"
    assert 'keywords' in df.columns, "缺少keywords列"
    assert len(df) > 0, "没有数据被处理"
    
    # 验证关键词格式
    for idx in range(min(5, len(df))):
        keywords = df.iloc[idx]['keywords']
        assert isinstance(keywords, list), f"关键词应该是列表类型，但得到: {type(keywords)}"
        assert len(keywords) <= 10, f"关键词数量超过10: {len(keywords)}"
        assert all(isinstance(k, str) for k in keywords), "关键词应该都是字符串"
    
    print(f"成功处理 {len(df)} 本书")
    print(f"输出文件: {output_path}")


def test_single_book_extraction():
    """
    测试单本书关键词提取
    """
    extractor = KeywordExtractor()
    
    # 测试文本
    content_intro = "这是一部关于爱情的长篇小说，通过2021的视角，描绘了延津的众生相。温情的文字既知识分子又刘震云，令人深思。"
    author_intro = "刘震云，生于1970年，延津作家。长期从事文学创作，著有《秦腔》等多部作品。"
    
    # 提取关键词
    keywords = extractor.extract_keywords_for_book(
        content_intro=content_intro,
        author_intro=author_intro,
        top_k=10
    )
    
    # 验证结果
    assert isinstance(keywords, list), "关键词应该是列表类型"
    assert len(keywords) <= 10, f"关键词数量超过10: {len(keywords)}"
    assert all(isinstance(k, str) for k in keywords), "关键词应该都是字符串"
    assert all(len(k) > 1 for k in keywords), "关键词长度应该大于1"
    
    print(f"提取的关键词: {', '.join(keywords)}")


def test_tfidf_extraction():
    """
    测试TF-IDF关键词提取
    """
    extractor = KeywordExtractor()
    
    # 测试文本列表
    texts = [
        "这是一部关于爱情的长篇小说，通过2021的视角，描绘了延津的众生相。",
        "命运的作品延续了2022的创作底色，用高密的笔调，书写了朴实的日常与小人物的困境。",
        "本书讲述了尊严在2023年代的一段成都故事。作者以犀利的笔触，展现了农民的悲欢离合。"
    ]
    
    # 提取关键词
    keywords_list = extractor.extract_tfidf_keywords(texts=texts, top_k=5)
    
    # 验证结果
    assert len(keywords_list) == len(texts), "关键词数量应该与文本数量一致"
    
    for i, keywords in enumerate(keywords_list):
        assert isinstance(keywords, list), f"第{i}个关键词应该是列表类型"
        assert len(keywords) <= 5, f"第{i}个关键词数量超过5: {len(keywords)}"
        print(f"文本{i+1}的TF-IDF关键词: {', '.join(keywords)}")


def test_textrank_extraction():
    """
    测试TextRank关键词提取
    """
    extractor = KeywordExtractor()
    
    # 测试文本
    text = "这是一部关于爱情的长篇小说，通过2021的视角，描绘了延津的众生相。温情的文字既知识分子又刘震云，令人深思。"
    
    # 提取关键词
    keywords = extractor.extract_textrank_keywords(text=text, top_k=5)
    
    # 验证结果
    assert isinstance(keywords, list), "关键词应该是列表类型"
    assert len(keywords) <= 5, f"关键词数量超过5: {len(keywords)}"
    assert all(isinstance(k, str) for k in keywords), "关键词应该都是字符串"
    
    print(f"TextRank关键词: {', '.join(keywords)}")


def test_keyword_merge():
    """
    测试关键词融合
    """
    extractor = KeywordExtractor()
    
    # 模拟两种算法的关键词
    tfidf_keywords = ["爱情", "长篇小说", "延津", "众生相", "温情", "知识分子"]
    textrank_keywords = ["长篇小说", "延津", "知识分子", "刘震云", "温情"]
    
    # 融合关键词
    merged_keywords = extractor.merge_keywords(
        tfidf_keywords=tfidf_keywords,
        textrank_keywords=textrank_keywords,
        top_k=5
    )
    
    # 验证结果
    assert isinstance(merged_keywords, list), "融合后的关键词应该是列表类型"
    assert len(merged_keywords) <= 5, f"融合后的关键词数量超过5: {len(merged_keywords)}"
    
    print(f"TF-IDF关键词: {', '.join(tfidf_keywords)}")
    print(f"TextRank关键词: {', '.join(textrank_keywords)}")
    print(f"融合后关键词: {', '.join(merged_keywords)}")


def test_data_loader_csv():
    """
    测试CSV数据加载器
    """
    csv_path = '../test/books_test.csv'
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"测试文件不存在: {csv_path}")
    
    loader = BookDataLoader(source_type='csv', source_config={'csv_path': csv_path})
    df = loader.load_data()
    
    # 验证结果
    assert df is not None, "加载的DataFrame为None"
    assert len(df) > 0, "没有数据被加载"
    assert '书名' in df.columns, "缺少'书名'列"
    assert '作者' in df.columns, "缺少'作者'列"
    
    print(f"成功加载 {len(df)} 条记录")


def test_data_saver_csv():
    """
    测试CSV数据保存器
    """
    import pandas as pd
    
    # 创建测试数据
    test_data = pd.DataFrame({
        '书名': ['测试书籍1', '测试书籍2'],
        '作者': ['测试作者1', '测试作者2'],
        'keywords': [['关键词1', '关键词2'], ['关键词3', '关键词4']]
    })
    
    output_path = '../test/test_output.csv'
    
    # 保存数据
    saver = BookDataSaver(target_type='csv', target_config={'csv_path': output_path})
    saver.save_data(test_data)
    
    # 验证结果
    assert os.path.exists(output_path), "输出文件不存在"
    
    # 读取并验证
    loaded_df = pd.read_csv(output_path, encoding='utf-8-sig')
    assert len(loaded_df) == 2, "保存的数据数量不正确"
    
    print(f"成功保存数据到 {output_path}")
    
    # 清理测试文件
    if os.path.exists(output_path):
        os.remove(output_path)
        print("已清理测试文件")


def test_different_top_k():
    """
    测试不同的top_k参数
    """
    extractor = KeywordExtractor()
    
    content_intro = "这是一部关于爱情的长篇小说，通过2021的视角，描绘了延津的众生相。温情的文字既知识分子又刘震云，令人深思。"
    author_intro = "刘震云，生于1970年，延津作家。长期从事文学创作，著有《秦腔》等多部作品。"
    
    # 测试不同的top_k值
    for top_k in [5, 10, 15, 20]:
        keywords = extractor.extract_keywords_for_book(
            content_intro=content_intro,
            author_intro=author_intro,
            top_k=top_k
        )
        
        assert len(keywords) <= top_k, f"关键词数量超过{top_k}: {len(keywords)}"
        print(f"top_k={top_k}: 提取了 {len(keywords)} 个关键词")


def test_empty_text():
    """
    测试空文本处理
    """
    extractor = KeywordExtractor()
    
    # 测试空文本
    keywords = extractor.extract_keywords_for_book(
        content_intro="",
        author_intro="",
        top_k=10
    )
    
    assert keywords == [], "空文本应该返回空列表"
    print("空文本处理正确")


def test_stopwords():
    """
    测试停用词过滤
    """
    extractor = KeywordExtractor()
    
    # 包含停用词的文本
    content_intro = "这是一部关于爱情的长篇小说，在2021年的视角下，描绘了延津的众生相。"
    
    keywords = extractor.extract_keywords_for_book(
        content_intro=content_intro,
        author_intro="",
        top_k=10
    )
    
    # 验证停用词被过滤
    stopwords = ['的', '是', '在', '了', '和', '就', '不', '人', '都', '一']
    for keyword in keywords:
        assert keyword not in stopwords, f"停用词未被过滤: {keyword}"
    
    print(f"提取的关键词（已过滤停用词）: {', '.join(keywords)}")


def test_performance():
    """
    测试性能
    """
    csv_path = '../test/books_test.csv'
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"测试文件不存在: {csv_path}")
    
    print("开始性能测试...")
    
    start_time = time.time()
    
    # 提取关键词
    df = extract_keywords_batch(
        csv_path=csv_path,
        output_path='../test/books_test_perf.csv',
        top_k=10
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 计算性能指标
    total_books = len(df)
    books_per_second = total_books / duration if duration > 0 else 0
    
    print(f"处理书籍数量: {total_books}")
    print(f"总耗时: {duration:.2f}秒")
    print(f"处理速度: {books_per_second:.2f} 本/秒")
    
    # 清理测试文件
    if os.path.exists('../test/books_test_perf.csv'):
        os.remove('../test/books_test_perf.csv')


def main():
    """
    主函数
    """
    print("="*60)
    print("关键词提取系统测试")
    print("="*60)
    
    # 创建测试运行器
    runner = TestRunner()
    
    # 运行所有测试
    tests = [
        ("CSV文件关键词提取", test_csv_extraction),
        ("单本书关键词提取", test_single_book_extraction),
        ("TF-IDF关键词提取", test_tfidf_extraction),
        ("TextRank关键词提取", test_textrank_extraction),
        ("关键词融合", test_keyword_merge),
        ("CSV数据加载器", test_data_loader_csv),
        ("CSV数据保存器", test_data_saver_csv),
        ("不同top_k参数", test_different_top_k),
        ("空文本处理", test_empty_text),
        ("停用词过滤", test_stopwords),
        ("性能测试", test_performance)
    ]
    
    for test_name, test_func in tests:
        runner.run_test(test_name, test_func)
    
    # 打印测试摘要
    runner.print_summary()
    
    # 返回退出码
    failed_tests = sum(1 for r in runner.test_results if not r['success'])
    return 0 if failed_tests == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
