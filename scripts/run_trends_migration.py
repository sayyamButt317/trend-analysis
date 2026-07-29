import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or ""
if not url:
    print("Set DATABASE_URL or SUPABASE_DB_URL in .env")
    sys.exit(1)

migration = Path(__file__).resolve().parents[1] / "db" / "migrations" / "003_trends.sql"
sql = migration.read_text(encoding="utf-8")

import psycopg2

conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()
cur.execute(sql)
cur.execute(
    """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'trends'
    ORDER BY ordinal_position
    """
)
cols = [row[0] for row in cur.fetchall()]
print("Migration applied successfully.")
print("trends columns:", ", ".join(cols))
cur.close()
conn.close()
