# -*- coding: utf-8 -*-
"""
also_like数据批量回填脚本

功能：
1. 从数据库读取所有 also_like 字段非空的书籍
2. 对每本书的 also_like 列表中的每个书名：
   - 在 book_also_like 表中创建记录（如果不存在）
   - 调用 AlsoLikeMapper 尝试匹配
3. 输出匹配统计报告（精确匹配数、模糊匹配数、未匹配数）
4. 支持 --apply 参数（默认预览模式）

使用方法：
    预览模式（不写入数据库）：
        python backfill_also_like.py

    应用模式（写入数据库）：
        python backfill_also_like.py --apply

作者：系统自动生成
日期：2026-05-30
"""

import argparse
import json
import os
import sys

from sqlalchemy import create_engine, text

# 将backend目录添加到sys.path，以便导入app.services
# 脚本位于: algorithms/scripts/backfill_also_like.py
# 需要导入: backend/app/services/also_like_mapper.py
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_backend_dir = os.path.join(_project_root, 'backend')
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.services.also_like_mapper import AlsoLikeMapper

CONFIG_PATH = os.path.join(_backend_dir, 'config.json')


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_engine():
    config = load_config()
    db_config = config['database']
    connection_str = (
        f"mysql+pymysql://{db_config['user']}:{db_config['password']}"
        f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        f"?charset=utf8mb4"
    )
    return create_engine(connection_str)


def parse_also_like(also_like_raw):
    """
    解析also_like字段，兼容多种格式：
    1. JSON数组: '["书名1", "书名2"]'
    2. 管道符分隔字符串: '书名1 | 书名2 | 书名3'
    3. Python列表: ['书名1', '书名2']

    返回:
        书名列表
    """
    if not also_like_raw:
        return []

    if isinstance(also_like_raw, list):
        return [str(item).strip() for item in also_like_raw if str(item).strip()]

    if isinstance(also_like_raw, str):
        raw = also_like_raw.strip()
        if not raw:
            return []

        # 尝试JSON解析
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (json.JSONDecodeError, TypeError):
            pass

        # 管道符分隔格式
        if '|' in raw:
            names = [name.strip() for name in raw.split('|')]
            return [name for name in names if name]

        # 其他格式（逗号分隔等）
        return [raw] if raw else []

    return []


def backfill(apply_mode=False):
    """
    执行also_like数据回填

    参数:
        apply_mode: True=写入数据库，False=仅预览
    """
    engine = get_engine()

    print("=" * 70)
    print("also_like 数据批量回填脚本")
    print(f"模式: {'应用模式（写入数据库）' if apply_mode else '预览模式（不写入数据库）'}")
    print("=" * 70)

    # 1. 读取所有 also_like 非空的书籍
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT book_id, title, also_like FROM books WHERE also_like IS NOT NULL AND also_like != '[]' AND also_like != ''")
        )
        books = [(row[0], row[1], row[2]) for row in result]

    print(f"\n[步骤1] 读取到 {len(books)} 本 also_like 非空的书籍")

    if not books:
        print("没有需要回填的数据，退出。")
        return

    # 2. 构建书名索引
    print("[步骤2] 构建书名索引...")
    mapper = AlsoLikeMapper(engine)
    mapper.build_title_index()

    # 3. 逐书逐名匹配
    print("[步骤3] 开始匹配 also_like 书名...\n")

    stats = {
        'total_books': len(books),
        'total_names': 0,
        'exact_count': 0,
        'fuzzy_count': 0,
        'unmatched_count': 0,
        'already_exists': 0,
        'inserted': 0,
    }

    preview_lines = []

    for book_id, title, also_like_raw in books:
        # 解析 also_like（兼容JSON数组和管道符分隔格式）
        also_like_list = parse_also_like(also_like_raw)

        if not also_like_list:
            continue

        for book_name in also_like_list:
            stats['total_names'] += 1

            # 检查是否已存在记录
            with engine.connect() as conn:
                existing = conn.execute(
                    text("SELECT relation_id FROM book_also_like WHERE source_book_id = :sid AND target_book_name = :tname LIMIT 1"),
                    {'sid': book_id, 'tname': book_name}
                ).fetchone()

            if existing:
                stats['already_exists'] += 1
                continue

            # 匹配书名
            match_result = mapper.match_book_name(book_name)
            match_type = match_result['match_type']
            match_score = match_result['match_score']
            target_book_id = match_result['target_book_id']

            if match_type == 'exact':
                stats['exact_count'] += 1
            elif match_type == 'fuzzy':
                stats['fuzzy_count'] += 1
            else:
                stats['unmatched_count'] += 1

            line = (
                f"  书籍ID={book_id} 《{title}》-> "
                f"also_like《{book_name}》: "
                f"匹配类型={match_type}, "
                f"目标ID={target_book_id}, "
                f"得分={match_score}"
            )
            preview_lines.append(line)

            if apply_mode:
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                "INSERT INTO book_also_like (source_book_id, target_book_id, target_book_name, match_type, match_score) "
                                "VALUES (:sid, :tid, :tname, :mtype, :mscore)"
                            ),
                            {
                                'sid': book_id,
                                'tid': target_book_id,
                                'tname': book_name,
                                'mtype': match_type,
                                'mscore': match_score,
                            }
                        )
                    stats['inserted'] += 1
                except Exception as e:
                    print(f"  [错误] 插入失败: source_book_id={book_id}, target_book_name={book_name}, 错误={e}")

    # 4. 输出预览（最多显示前50条）
    print("--- 匹配预览（最多显示前50条）---")
    for line in preview_lines[:50]:
        print(line)
    if len(preview_lines) > 50:
        print(f"  ... 还有 {len(preview_lines) - 50} 条未显示")

    # 5. 输出统计报告
    print("\n" + "=" * 70)
    print("匹配统计报告")
    print("=" * 70)
    print(f"  处理书籍数:       {stats['total_books']}")
    print(f"  also_like书名总数: {stats['total_names']}")
    print(f"  已存在记录数:     {stats['already_exists']}")
    print(f"  新匹配书名数:     {stats['total_names'] - stats['already_exists']}")
    print(f"    - 精确匹配:     {stats['exact_count']}")
    print(f"    - 模糊匹配:     {stats['fuzzy_count']}")
    print(f"    - 未匹配:       {stats['unmatched_count']}")
    if apply_mode:
        print(f"  实际插入记录数:   {stats['inserted']}")
    else:
        print(f"  预计插入记录数:   {stats['total_names'] - stats['already_exists']}")
        print(f"\n  提示: 使用 --apply 参数执行实际写入")

    print("=" * 70)

    # 6. 匹配率
    new_matches = stats['exact_count'] + stats['fuzzy_count']
    total_new = stats['total_names'] - stats['already_exists']
    if total_new > 0:
        match_rate = new_matches / total_new * 100
        print(f"  匹配率: {match_rate:.1f}% ({new_matches}/{total_new})")
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='also_like数据批量回填脚本')
    parser.add_argument('--apply', action='store_true', help='应用模式：将匹配结果写入数据库（默认为预览模式）')
    args = parser.parse_args()

    try:
        backfill(apply_mode=args.apply)
    except Exception as e:
        print(f"\n回填失败，错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
