# -*- coding: utf-8 -*-
import subprocess
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sql_file = r"d:\luxury\Documents\组长的版本\douban_books_backup.sql"

print("Starting import...")

# Read SQL file as binary to preserve exact bytes
with open(sql_file, 'rb') as f:
    sql_bytes = f.read()

print(f"SQL file size: {len(sql_bytes)} bytes")

# Use mysql command with proper encoding
process = subprocess.Popen(
    ['mysql', '-u', 'root', '-p3186732205wr',
     '--default-character-set=utf8mb4',
     'douban_books'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

try:
    stdout, stderr = process.communicate(input=sql_bytes, timeout=300)
    
    if process.returncode == 0:
        print("\n[SUCCESS] Import completed!")
        print(f"Output length: {len(stdout)} bytes")
    else:
        print(f"\n[ERROR] Import failed with code {process.returncode}")
        if stderr:
            print(f"Error (decoded): {stderr.decode('utf-8', errors='replace')}")
except subprocess.TimeoutExpired:
    process.kill()
    print("[ERROR] Import timed out!")
except Exception as e:
    print(f"[ERROR] Exception: {e}")
