# -*- coding: utf-8 -*-
"""
数据库迁移脚本：添加 book_also_like 表和 books.gnn_embedding 字段

执行内容：
1. 创建 book_also_like 表（如果不存在）
2. 为 books 表新增 gnn_embedding JSON 字段（如果不存在）

使用方法：
    python migrate_add_also_like_table.py
"""

import os
import sys
import json
import pymysql
from sqlalchemy import create_engine, text

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def migrate():
    config = load_config()
    db_config = config['database']

    connection_str = (
        f"mysql+pymysql://{db_config['user']}:{db_config['password']}"
        f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        f"?charset=utf8mb4"
    )
    engine = create_engine(connection_str)

    print("=" * 60)
    print("数据库迁移：添加 book_also_like 表和 gnn_embedding 字段")
    print("=" * 60)

    with engine.begin() as conn:
        # -------------------------------------------------------
        # 1. 创建 book_also_like 表（如果不存在）
        # -------------------------------------------------------
        print("\n[迁移1] 创建 book_also_like 表...")
        create_also_like_sql = """
        CREATE TABLE IF NOT EXISTS book_also_like (
            relation_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '关系ID',
            source_book_id INT NOT NULL COMMENT '源书籍ID',
            target_book_id INT COMMENT '目标书籍ID（匹配成功时非空）',
            target_book_name VARCHAR(255) NOT NULL COMMENT '目标书籍名称（豆瓣原始书名）',
            match_type ENUM('exact', 'fuzzy', 'unmatched') NOT NULL DEFAULT 'unmatched' COMMENT '匹配类型',
            match_score FLOAT DEFAULT 0.0 COMMENT '匹配得分（0.0~1.0）',
            weight FLOAT DEFAULT 1.0 COMMENT '关系权重',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            UNIQUE KEY uk_source_target (source_book_id, target_book_name),
            INDEX idx_source_book (source_book_id),
            INDEX idx_target_book (target_book_id),
            INDEX idx_match_type (match_type),
            CONSTRAINT fk_also_like_source FOREIGN KEY (source_book_id) REFERENCES books(book_id) ON DELETE CASCADE,
            CONSTRAINT fk_also_like_target FOREIGN KEY (target_book_id) REFERENCES books(book_id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        conn.execute(text(create_also_like_sql))
        print("  -> book_also_like 表创建成功（或已存在）")

        # 验证表是否存在
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'book_also_like'"
        ), {"schema": db_config['database']})
        count = result.scalar()
        if count > 0:
            print("  -> 验证：book_also_like 表已存在于数据库中")
        else:
            print("  -> 警告：book_also_like 表未找到，请检查！")

        # -------------------------------------------------------
        # 2. 为 books 表新增 gnn_embedding JSON 字段（如果不存在）
        # -------------------------------------------------------
        print("\n[迁移2] 为 books 表添加 gnn_embedding 字段...")

        # 先检查字段是否已存在
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'books' AND column_name = 'gnn_embedding'"
        ), {"schema": db_config['database']})
        col_exists = result.scalar()

        if col_exists > 0:
            print("  -> gnn_embedding 字段已存在，跳过添加")
        else:
            conn.execute(text(
                "ALTER TABLE books ADD COLUMN gnn_embedding JSON COMMENT 'GNN嵌入向量' "
                "AFTER keywords_embeddings"
            ))
            print("  -> gnn_embedding 字段添加成功")

        # 验证字段是否存在
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'books' AND column_name = 'gnn_embedding'"
        ), {"schema": db_config['database']})
        col_exists = result.scalar()
        if col_exists > 0:
            print("  -> 验证：gnn_embedding 字段已存在于 books 表中")
        else:
            print("  -> 警告：gnn_embedding 字段未找到，请检查！")

    print("\n" + "=" * 60)
    print("迁移完成！")
    print("=" * 60)


if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"\n迁移失败，错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
