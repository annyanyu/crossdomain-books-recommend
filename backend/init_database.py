# -*- coding: utf-8 -*-
"""
数据库初始化脚本
用于创建数据库、表结构并导入测试数据

使用方法：
1. 修改config.json中的数据库配置
2. 运行此脚本：python init_database.py

作者：四人小组
日期：2026-03-25
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import pymysql

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_domain_tags():
    domain_tags_path = os.path.join(os.path.dirname(__file__), '..', 'algorithms', 'scripts', 'domain_tags.json')
    with open(domain_tags_path, 'r', encoding='utf-8') as f:
        domains = json.load(f)
    return [d['domain'] for d in domains]

def create_database():
    config = load_config()
    db_config = config['database']
    
    connection = pymysql.connect(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password']
    )
    
    cursor = connection.cursor()
    
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"数据库 '{db_config['database']}' 创建成功！")
    
    cursor.close()
    connection.close()

def create_tables(engine):
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS books (
        book_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '图书ID',
        title VARCHAR(255) NOT NULL COMMENT '书名',
        cover_image VARCHAR(500) COMMENT '封面图片URL',
        authors JSON COMMENT '作者列表',
        publisher VARCHAR(255) COMMENT '出版社',
        publication_date DATE COMMENT '出版日期',
        rating FLOAT COMMENT '评分',
        author_intro TEXT COMMENT '作者简介',
        URL VARCHAR(500) COMMENT '图书详情页网址',
        books_intro TEXT COMMENT '内容简介',
        also_like JSON COMMENT '喜欢这本书的人也喜欢的书名列表',
        short_reviews JSON COMMENT '短评列表',
        reviews JSON COMMENT '书评列表',
        reading_notes JSON COMMENT '读书笔记列表',
        keywords JSON COMMENT '关键词列表',
        domain JSON COMMENT '标签列表',
        embedding JSON COMMENT '语义向量列表',
        keywords_embeddings JSON COMMENT '关键词嵌入向量列表',
        domain_tags JSON COMMENT '领域标签列表',
        INDEX idx_title (title),
        INDEX idx_publisher (publisher),
        INDEX idx_rating (rating)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='图书信息表';
    """
    
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS books"))
        conn.execute(text(create_table_sql))
    
    print("表 'books' 创建成功！")

def generate_sample_data(num_books=100):
    all_domains = load_domain_tags()
    print(f"加载了 {len(all_domains)} 个领域标签: {all_domains}")
    
    np.random.seed(42)
    
    titles_main = ['深度学习', '机器学习', '数据科学', '人工智能', 'Python编程', 
                   '算法导论', '计算机网络', '操作系统', '数据库系统', '软件工程',
                   '设计模式', '代码整洁之道', '重构', '敏捷开发', '测试驱动开发',
                   '云计算', '大数据', '区块链', '物联网', '网络安全',
                   '自然语言处理', '计算机视觉', '推荐系统', '搜索引擎', '分布式系统',
                   '心理学导论', '认知心理学', '社会心理学', '发展心理学', '心理咨询',
                   '经济学原理', '宏观经济学', '微观经济学', '金融学', '投资学',
                   '中国历史', '世界历史', '古代文明', '近代史', '现代史',
                   '哲学导论', '西方哲学史', '中国哲学史', '伦理学', '逻辑学',
                   '文学概论', '小说创作', '诗歌鉴赏', '散文选集', '世界名著',
                   '艺术史', '绘画技法', '音乐欣赏', '建筑设计', '摄影艺术',
                   '物理学', '化学原理', '生物学', '天文学', '地理学',
                   '社会学', '政治学', '法学概论', '人类学', '传播学',
                   '健康生活', '养生之道', '健身指南', '美食烹饪', '旅行游记']
    titles_suffixes = ['入门', '实战', '原理', '指南', '从入门到精通', '进阶', '核心概念', '最佳实践']
    
    authors = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十',
               '刘明', '陈华', '杨光', '黄伟', '周杰', '林峰', '徐涛',
               '莫言', '余华', '苏童', '格非', '贾平凹', '王安忆', '迟子建',
               '刘震云', '麦家', '阿来', '李洱', '毕飞宇', '陈忠实', '路遥']
    
    publishers = ['清华大学出版社', '人民邮电出版社', '机械工业出版社', '电子工业出版社', 
                  '科学出版社', '高等教育出版社', '北京大学出版社', '中国铁道出版社',
                  '中信出版社', '理想国', '新星出版社', '上海译文出版社']
    
    books = []
    for i in range(num_books):
        title_main = np.random.choice(titles_main)
        title_suffix = np.random.choice(titles_suffixes)
        title = f"《{title_main}{title_suffix}》"
        
        num_authors = np.random.randint(1, 3)
        book_authors = list(np.random.choice(authors, num_authors, replace=False))
        
        publisher = np.random.choice(publishers)
        year = np.random.randint(2015, 2026)
        publication_date = f"{year}-{np.random.randint(1, 13):02d}-{np.random.randint(1, 29):02d}"
        
        rating = round(np.random.uniform(3.0, 9.9), 1)
        
        num_tags = np.random.randint(1, 3)
        domain_tags = list(np.random.choice(all_domains, num_tags, replace=False))
        
        embedding = list(np.random.randn(128))
        embedding = [round(x / np.linalg.norm(embedding), 6) for x in embedding]
        
        num_keywords = np.random.randint(3, 8)
        keywords = [f"关键词{j+1}" for j in range(num_keywords)]
        keywords_embeddings = [[round(x, 6) for x in np.random.randn(64).tolist()] for _ in range(num_keywords)]
        
        book = {
            'title': title,
            'cover_image': None,
            'authors': book_authors,
            'publisher': publisher,
            'publication_date': publication_date,
            'rating': rating,
            'author_intro': f"本书作者{', '.join(book_authors)}是知名专家，在相关领域有多年研究和实践经验。",
            'URL': f"https://book.douban.com/subject/{np.random.randint(1000000, 9999999)}/",
            'books_intro': f"本书全面介绍了{title_main}的相关知识，从基础概念到高级应用，适合初学者和进阶读者阅读。",
            'also_like': [],
            'short_reviews': [],
            'reviews': [],
            'reading_notes': [],
            'keywords': keywords,
            'domain': domain_tags,
            'embedding': embedding,
            'keywords_embeddings': keywords_embeddings,
            'domain_tags': domain_tags
        }
        books.append(book)
    
    return books

def import_data(engine, books):
    df = pd.DataFrame(books)
    
    for col in ['authors', 'also_like', 'short_reviews', 'reviews', 'reading_notes', 
                'keywords', 'domain', 'embedding', 'keywords_embeddings', 'domain_tags']:
        df[col] = df[col].apply(lambda x: json.dumps(x, ensure_ascii=False))
    
    df.to_sql('books', engine, if_exists='append', index=False)
    print(f"成功导入 {len(books)} 条图书数据！")

def main():
    print("=" * 60)
    print("图书推荐系统 - 数据库初始化")
    print("=" * 60)
    
    try:
        print("\n步骤1: 创建数据库...")
        create_database()
        
        config = load_config()
        db_config = config['database']
        connection_str = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}?charset=utf8mb4"
        engine = create_engine(connection_str)
        
        print("\n步骤2: 创建数据表...")
        create_tables(engine)
        
        print("\n步骤3: 生成数据...")
        books = generate_sample_data(100)
        
        if len(books) == 0:
            print("没有数据可导入！")
            return
        
        print("\n步骤4: 导入数据...")
        import_data(engine, books)
        
        print("\n步骤5: 验证数据...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM books"))
            count = result.scalar()
            print(f"books表中当前共有 {count} 条记录")
            
            result = conn.execute(text("SELECT book_id, title, rating, domain_tags FROM books LIMIT 3"))
            print("\n数据预览:")
            for row in result:
                print(f"  ID: {row[0]}, 标题: {row[1]}, 评分: {row[2]}, 标签: {row[3]}")
            
            result = conn.execute(text("SELECT domain_tags FROM books WHERE domain_tags IS NOT NULL AND domain_tags != '[]' LIMIT 100"))
            all_tags = set()
            for row in result:
                try:
                    tags = json.loads(row[0])
                    all_tags.update(tags)
                except:
                    pass
            print(f"\n领域标签总数: {len(all_tags)}")
            print(f"标签列表: {sorted(all_tags)}")
        
        print("\n" + "=" * 60)
        print("数据库初始化完成！")
        print("=" * 60)
        print("\n接下来请运行以下命令启动系统:")
        print("  1. pip install -r requirements.txt")
        print("  2. python app.py")
        print("  3. 访问 http://localhost:5000")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
