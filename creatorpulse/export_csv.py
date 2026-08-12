"""
CreatorPulse — Export all tables to CSV for Power BI import.
Produces 4 files in a /data folder ready to load directly into Power BI.
"""

import pandas as pd
import psycopg2
import os

DB_URL = "postgresql://postgres.fkqwjbjbmkymdfypldkm:CreatorPulse2024@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

os.makedirs("data", exist_ok=True)

conn = psycopg2.connect(DB_URL)

tables = {
    "channels": "SELECT * FROM channels",
    "videos":   "SELECT v.*, c.channel_name FROM videos v JOIN channels c USING (channel_id)",
    "comments": "SELECT comment_id, video_id, comment_text, comment_likes, sentiment_compound, sentiment_label, published_at FROM comments",
    "video_tags": "SELECT * FROM video_tags",
}

for name, query in tables.items():
    df = pd.read_sql(query, conn)
    path = f"data/{name}.csv"
    df.to_csv(path, index=False)
    print(f"  Exported {len(df):,} rows → {path}")

conn.close()
print("Done. Open Power BI → Get Data → Text/CSV → select each file in /data")
