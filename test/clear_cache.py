# clear_cache.py
import sqlite3
from pathlib import Path

DB_PATH = Path("finance_mcp_server/database/portfolio.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Xóa toàn bộ cache giá cũ
cursor.execute("DELETE FROM price_cache")
conn.commit()

print(f"✅ Đã xóa {cursor.rowcount} records trong price_cache")
conn.close()