# -*- coding: utf-8 -*-
import subprocess
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sql_file = r"d:\luxury\Documents\组长的版本\douban_books_backup.sql"

print(f"正在导入SQL文件: {sql_file}")
print("使用UTF-8编码导入...")

try:
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    process = subprocess.Popen(
        ['mysql', '-u', 'root', '-p3186732205wr', '--default-character-set=utf8mb4', 'douban_books'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8'
    )

    stdout, stderr = process.communicate(input=sql_content)

    if process.returncode == 0:
        print("\n[SUCCESS] 数据库导入成功！")
        if stdout.strip():
            print(f"输出: {stdout}")
    else:
        print(f"\n[ERROR] 导入失败！错误码: {process.returncode}")
        if stderr.strip():
            print(f"错误信息: {stderr}")

except Exception as e:
    print(f"\n[ERROR] 发生异常: {e}")
    import traceback
    traceback.print_exc()
