# -*- coding: utf-8 -*-
import sys
import os
import json
import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from assign_domain_tags import DomainTagAssigner

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           'backend', 'config.json')


def load_db_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    db = config['database']
    return {
        'host': db['host'],
        'port': db.get('port', 3306),
        'user': db['user'],
        'password': db['password'],
        'database': db['database'],
        'charset': 'utf8mb4',
    }


def fetch_all_books(conn):
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT book_id, title, book_intro, author_intro, domain_tags FROM books ORDER BY book_id")
        return cursor.fetchall()


def reassign_tags(books, assigner):
    results = []
    for book in books:
        book_id = book['book_id']
        title = book['title'] or ''
        intro = book['book_intro'] or ''
        author_intro = book['author_intro'] or ''
        old_tags = book['domain_tags']

        if isinstance(old_tags, str):
            try:
                old_tags = json.loads(old_tags)
            except (json.JSONDecodeError, TypeError):
                old_tags = []

        new_tags = assigner.assign_domain_tags(title, intro, author_intro, max_domains=2)

        changed = old_tags != new_tags

        results.append({
            'book_id': book_id,
            'title': title,
            'old_tags': old_tags,
            'new_tags': new_tags,
            'changed': changed,
        })

    return results


def update_database(conn, results):
    updated = 0
    with conn.cursor() as cursor:
        for r in results:
            if r['changed']:
                new_tags_json = json.dumps(r['new_tags'], ensure_ascii=False)
                sql = "UPDATE books SET domain_tags = %s WHERE book_id = %s"
                cursor.execute(sql, (new_tags_json, r['book_id']))
                updated += 1
    conn.commit()
    return updated


def print_report(results):
    total = len(results)
    changed = [r for r in results if r['changed']]
    unchanged = total - len(changed)

    print("\n" + "=" * 80)
    print("标签修正报告")
    print("=" * 80)
    print(f"总书籍数: {total}")
    print(f"标签变更数: {len(changed)}")
    print(f"标签不变数: {unchanged}")

    cs_wrong_before = 0
    cs_wrong_after = 0
    other_before = 0
    other_after = 0

    for r in results:
        if '计算机科学' in r['old_tags']:
            cs_wrong_before += 1
        if '计算机科学' in r['new_tags']:
            cs_wrong_after += 1
        if '其他' in r['old_tags']:
            other_before += 1
        if '其他' in r['new_tags']:
            other_after += 1

    print(f"\n--- 关键指标变化 ---")
    print(f"'计算机科学'标签出现次数: {cs_wrong_before} → {cs_wrong_after}")
    print(f"'其他'标签出现次数: {other_before} → {other_after}")

    print(f"\n--- 变更详情（前30条）---")
    for r in changed[:30]:
        old_str = json.dumps(r['old_tags'], ensure_ascii=False)
        new_str = json.dumps(r['new_tags'], ensure_ascii=False)
        print(f"  [{r['book_id']}] 《{r['title']}》: {old_str} → {new_str}")

    if len(changed) > 30:
        print(f"  ... 还有 {len(changed) - 30} 条变更未显示")

    tag_count = {}
    for r in results:
        for tag in r['new_tags']:
            tag_count[tag] = tag_count.get(tag, 0) + 1

    print(f"\n--- 新标签分布 ---")
    for tag, count in sorted(tag_count.items(), key=lambda x: x[1], reverse=True):
        pct = count / total * 100
        print(f"  {tag}: {count} 本 ({pct:.1f}%)")


def main():
    dry_run = '--apply' not in sys.argv

    db_config = load_db_config()
    conn = pymysql.connect(**db_config)

    try:
        print("正在从数据库加载书籍数据...")
        books = fetch_all_books(conn)
        print(f"加载了 {len(books)} 本书")

        assigner = DomainTagAssigner()

        import pandas as pd
        df = pd.DataFrame(books)
        assigner.compute_idf(df)

        print("正在重新分配标签...")
        results = reassign_tags(books, assigner)

        print_report(results)

        if dry_run:
            print("\n" + "!" * 80)
            print("这是预览模式，数据库未修改。")
            print("如需实际更新数据库，请运行: python fix_domain_tags.py --apply")
            print("!" * 80)
        else:
            updated = update_database(conn, results)
            print(f"\n[OK] 数据库已更新，共修改 {updated} 条记录")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
