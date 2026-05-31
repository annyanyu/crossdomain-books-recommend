# -*- coding: utf-8 -*-
import re

sql_file = r"d:\luxury\Documents\组长的版本\douban_books_backup.sql"

with open(sql_file, 'rb') as f:
    content = f.read()

print(f"File size: {len(content)} bytes")
print(f"First 50 bytes (hex): {content[:50].hex()}")

# Try to find INSERT statement
insert_pos = content.find(b'INSERT INTO')
if insert_pos > 0:
    print(f"\nFound INSERT at position: {insert_pos}")
    # Show some data around the first title
    sample = content[insert_pos:insert_pos+300]
    print("\nSample data (raw bytes):")
    print(sample)
    
    # Try to decode as UTF-8
    try:
        decoded = sample.decode('utf-8')
        print("\nDecoded as UTF-8:")
        print(decoded)
    except:
        print("\nFailed to decode as UTF-8")
        
    # Check for 3F (question mark) which indicates corruption
    if b'\x3f\x3f\x3f' in content[insert_pos:insert_pos+10000]:
        print("\n[WARNING] Found '???' in data - file may be corrupted!")
    else:
        print("\n[OK] No '???' found in initial data")
