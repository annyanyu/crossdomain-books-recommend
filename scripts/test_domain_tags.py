# -*- coding: utf-8 -*-
"""
领域标签分配系统测试脚本
用于测试领域标签分配的各种场景和边界条件

测试内容：
1. 单本书领域标签分配测试
2. 批量处理测试
3. 边界条件测试（空文本、无匹配等）
4. 领域统计功能测试

作者：系统自动生成
日期：2025-03-22
"""

import sys
import os
import pandas as pd
from assign_domain_tags import DomainTagAssigner, assign_domain_tags_batch


def test_single_book():
    """
    测试单本书的领域标签分配
    """
    print("\n" + "=" * 60)
    print("测试1: 单本书领域标签分配")
    print("=" * 60)
    
    # 初始化分配器
    assigner = DomainTagAssigner()
    
    # 测试用例1: 计算机科学类书籍
    title = "Python编程从入门到实践"
    content_intro = "本书详细介绍了Python编程语言的基础知识和高级应用，包括数据结构、算法设计、面向对象编程等内容。"
    author_intro = "作者是一名资深的软件工程师，拥有10年以上的编程经验。"
    
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    print(f"\n测试用例1 - 计算机科学类书籍:")
    print(f"  书名: {title}")
    print(f"  领域标签: {domain_tags}")
    
    # 测试用例2: 文学类书籍
    title = "红楼梦"
    content_intro = "中国古典文学四大名著之一，描写了贾宝玉、林黛玉等人的爱情悲剧和贾府的兴衰史。"
    author_intro = "曹雪芹，清代小说家，中国古典文学的代表人物。"
    
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    print(f"\n测试用例2 - 文学类书籍:")
    print(f"  书名: {title}")
    print(f"  领域标签: {domain_tags}")
    
    # 测试用例3: 心理学类书籍
    title = "心理学与生活"
    content_intro = "本书系统地介绍了心理学的基本理论和实际应用，包括认知心理学、发展心理学、社会心理学等领域。"
    author_intro = "作者是一位著名的心理学家，在心理学教育和研究领域有重要贡献。"
    
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    print(f"\n测试用例3 - 心理学类书籍:")
    print(f"  书名: {title}")
    print(f"  领域标签: {domain_tags}")
    
    # 测试用例4: 跨领域书籍
    title = "人工智能与人类未来"
    content_intro = "探讨人工智能技术对人类社会、经济、文化等方面的影响，以及人类如何应对AI带来的挑战和机遇。"
    author_intro = "作者是一位科技哲学家，专注于研究技术伦理和人类未来。"
    
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    print(f"\n测试用例4 - 跨领域书籍:")
    print(f"  书名: {title}")
    print(f"  领域标签: {domain_tags}")


def test_batch_processing():
    """
    测试批量处理功能
    """
    print("\n" + "=" * 60)
    print("测试2: 批量处理")
    print("=" * 60)
    
    # 初始化分配器
    assigner = DomainTagAssigner()
    
    # 创建测试数据
    test_data = pd.DataFrame([
        {
            '书名': 'Python编程从入门到实践',
            '作者': 'Eric Matthes',
            '出版社': '人民邮电出版社',
            '出版年': '2020',
            'ISBN': '9787115546081',
            'URL': '',
            '评分': '9.0',
            '内容简介': '本书详细介绍了Python编程语言的基础知识和高级应用，包括数据结构、算法设计、面向对象编程等内容。',
            '作者简介': '作者是一名资深的软件工程师，拥有10年以上的编程经验。'
        },
        {
            '书名': '红楼梦',
            '作者': '曹雪芹',
            '出版社': '人民文学出版社',
            '出版年': '1982',
            'ISBN': '9787020002207',
            'URL': '',
            '评分': '9.6',
            '内容简介': '中国古典文学四大名著之一，描写了贾宝玉、林黛玉等人的爱情悲剧和贾府的兴衰史。',
            '作者简介': '曹雪芹，清代小说家，中国古典文学的代表人物。'
        },
        {
            '书名': '心理学与生活',
            '作者': '理查德·格里格',
            '出版社': '人民邮电出版社',
            '出版年': '2016',
            'ISBN': '9787115428397',
            'URL': '',
            '评分': '8.9',
            '内容简介': '本书系统地介绍了心理学的基本理论和实际应用，包括认知心理学、发展心理学、社会心理学等领域。',
            '作者简介': '作者是一位著名的心理学家，在心理学教育和研究领域有重要贡献。'
        }
    ])
    
    print(f"\n测试数据包含 {len(test_data)} 本书")
    
    # 批量分配领域标签
    result_df = assigner.assign_domain_tags_batch(test_data)
    
    print("\n批量处理结果:")
    print("-" * 60)
    for idx, row in result_df.iterrows():
        print(f"{idx+1}. {row['书名']}")
        print(f"   领域标签: {', '.join(row['domain_tags'])}")
    
    # 测试领域统计功能
    print("\n领域统计:")
    print("-" * 60)
    domain_stats = assigner.get_domain_statistics(result_df)
    for domain, stats in domain_stats.items():
        print(f"{domain}: {stats['count']} 本 ({stats['percentage']}%)")


def test_edge_cases():
    """
    测试边界条件
    """
    print("\n" + "=" * 60)
    print("测试3: 边界条件")
    print("=" * 60)
    
    # 初始化分配器
    assigner = DomainTagAssigner()
    
    # 测试用例1: 空文本
    print("\n测试用例1 - 空文本:")
    domain_tags = assigner.assign_domain_tags('', '', '')
    print(f"  输入: 空文本")
    print(f"  输出: {domain_tags}")
    assert domain_tags == ["其他"], "空文本应返回 ['其他']"
    
    # 测试用例2: 无匹配关键词
    print("\n测试用例2 - 无匹配关键词:")
    title = "测试书籍"
    content_intro = "这是一本关于日常生活的普通读物，内容简单易懂。"
    author_intro = "作者是一位普通写作者。"
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    print(f"  输入: {title}")
    print(f"  输出: {domain_tags}")
    # 注意：如果关键词列表中有"生活"、"普通"等词，可能会匹配到生活健康领域
    
    # 测试用例3: 只有一个匹配领域
    print("\n测试用例3 - 只有一个匹配领域:")
    title = "Python编程实战"
    content_intro = "本书介绍Python编程语言的实际应用，包括Web开发、数据分析等内容。"
    author_intro = "作者是一位资深程序员。"
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    print(f"  输入: {title}")
    print(f"  输出: {domain_tags}")
    # 注意：可能匹配到多个领域，因为关键词可能有重叠
    
    # 测试用例4: 多个匹配领域
    print("\n测试用例4 - 多个匹配领域:")
    title = "科技哲学导论"
    content_intro = "本书探讨科学技术与哲学的关系，包括科学哲学、技术哲学、科学史等内容。"
    author_intro = "作者是一位科技哲学研究者。"
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    print(f"  输入: {title}")
    print(f"  输出: {domain_tags}")
    assert len(domain_tags) <= 2, "最多应返回2个标签"
    
    # 测试用例5: 包含NaN值
    print("\n测试用例5 - 包含NaN值:")
    title = "测试书名"
    content_intro = None
    author_intro = float('nan')
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    print(f"  输入: 标题={title}, 内容简介=None, 作者简介=NaN")
    print(f"  输出: {domain_tags}")
    
    print("\n所有边界条件测试通过！")


def test_with_csv_file():
    """
    使用真实的CSV文件进行测试
    """
    print("\n" + "=" * 60)
    print("测试4: 使用真实CSV文件")
    print("=" * 60)
    
    csv_path = '../test/books_test.csv'
    output_path = '../test/books_test_with_domain_tags.csv'
    
    # 检查文件是否存在
    if not os.path.exists(csv_path):
        print(f"\n警告: 测试文件 {csv_path} 不存在，跳过此测试")
        return
    
    print(f"\n正在处理文件: {csv_path}")
    
    try:
        # 批量分配领域标签
        df = assign_domain_tags_batch(
            csv_path=csv_path,
            output_path=output_path,
            max_domains=2
        )
        
        print(f"\n测试成功！结果已保存到: {output_path}")
        
    except Exception as e:
        print(f"\n测试失败: {e}")


def test_domain_score_calculation():
    """
    测试领域分数计算
    """
    print("\n" + "=" * 60)
    print("测试5: 领域分数计算")
    print("=" * 60)
    
    # 初始化分配器
    assigner = DomainTagAssigner()
    
    # 测试用例: 包含多个领域关键词的文本
    text = "这是一本关于计算机科学和人工智能的书，介绍了算法、数据结构、机器学习、深度学习等内容。"
    
    print(f"\n测试文本: {text}")
    print("\n各领域匹配分数:")
    print("-" * 60)
    
    # 计算每个领域的分数
    for domain_name, keywords in assigner.domain_keywords.items():
        score = assigner._calculate_domain_score(text.lower(), keywords)
        if score > 0:
            print(f"{domain_name}: {score} 分")
    
    # 分配标签
    title = "计算机科学与人工智能"
    content_intro = text
    author_intro = "作者是一位AI研究员。"
    domain_tags = assigner.assign_domain_tags(title, content_intro, author_intro)
    
    print(f"\n最终分配的标签: {domain_tags}")


def run_all_tests():
    """
    运行所有测试
    """
    print("\n" + "=" * 60)
    print("开始运行所有测试")
    print("=" * 60)
    
    try:
        test_single_book()
        test_batch_processing()
        test_edge_cases()
        test_domain_score_calculation()
        test_with_csv_file()
        
        print("\n" + "=" * 60)
        print("所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    # 运行所有测试
    run_all_tests()
    
    # 也可以单独运行某个测试
    # test_single_book()
    # test_batch_processing()
    # test_edge_cases()
    # test_domain_score_calculation()
    # test_with_csv_file()
