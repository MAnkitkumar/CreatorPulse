"""
CreatorPulse — Module 2: PostgreSQL ETL Ingestion
==================================================
1. Creates all tables via db_schema.sql (idempotent).
2. Calls the Module 1 extraction pipeline.
3. Upserts channels → videos → comments → video_tags into Supabase PostgreSQL.

Upsert strategy: INSERT ... ON CONFLICT DO UPDATE
Re-running this script refreshes stale data without creating duplicates.
"""

import logging
from urllib.parse import quote_plus

import pandas as pd
import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text

from config import DB_URL
from extractor import run_extraction_pipeline

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Build safe DB URL (handles special chars in Supabase passwords) ───────────
def make_safe_url(raw_url: str) -> str:
    """
    Re-percent-encode the password portion of a DATABASE_URL.
    Supabase passwords often contain =, ?, +, @, $ that break URL parsers.
    Strategy: split on the rightmost '@' to isolate credentials from host.
    """
    scheme, rest = raw_url.split("://", 1)
    credentials, hostpart = rest.rsplit("@", 1)   # rightmost @ = host boundary
    user, password = credentials.split(":", 1)
    safe_pw = quote_plus(password)
    return f"{scheme}://{user}:{safe_pw}@{hostpart}"


# ── DDL ───────────────────────────────────────────────────────────────────────
def create_tables(engine):
    """Execute db_schema.sql — creates tables if they don't exist."""
    log.info("Creating tables (idempotent)...")
    with open("db_schema.sql", "r") as f:
        ddl = f.read()
    with engine.begin() as conn:
        conn.execute(text(ddl))
    log.info("  Tables ready.")


# ── Core upsert via psycopg2 execute_values ───────────────────────────────────
def upsert(conn, table: str, df: pd.DataFrame, pk_cols: list, update_cols: list):
    """
    Bulk upsert a DataFrame into `table` using:
      INSERT INTO table (...) VALUES %s
      ON CONFLICT (pk_cols) DO UPDATE SET col = EXCLUDED.col ...

    Uses psycopg2.extras.execute_values for high-throughput batch inserts.
    """
    if df.empty:
        log.warning(f"  Skipping {table} — empty DataFrame.")
        return

    cols        = list(df.columns)
    col_str     = ", ".join(cols)
    placeholders = "(" + ", ".join(["%s"] * len(cols)) + ")"

    # Build SET clause: col = EXCLUDED.col for each update column
    set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
    conflict_target = ", ".join(pk_cols)

    sql = f"""
        INSERT INTO {table} ({col_str})
        VALUES %s
        ON CONFLICT ({conflict_target})
        DO UPDATE SET {set_clause}
    """

    # Convert DataFrame rows to list of tuples, replacing pd.NaT/NaN with None
    records = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df.itertuples(index=False, name=None)
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, records, page_size=500)

    log.info(f"  Upserted {len(records):,} rows → {table}")


# ── Table loaders ─────────────────────────────────────────────────────────────
def load_channels(conn, df: pd.DataFrame):
    df = df.copy()
    df["updated_at"] = pd.Timestamp.utcnow()
    upsert(conn, "channels", df,
           pk_cols=["channel_id"],
           update_cols=["channel_name", "subscribers", "total_views", "video_count", "updated_at"])


def load_videos(conn, df: pd.DataFrame):
    # Drop the 'tags' column if still present (it belongs in video_tags)
    df = df.drop(columns=["tags"], errors="ignore").copy()
    upsert(conn, "videos", df,
           pk_cols=["video_id"],
           update_cols=["title", "published_at", "duration_seconds", "duration_bucket",
                        "views", "likes", "comments_count",
                        "engagement_rate", "idr", "vii", "vvi"])


def load_comments(conn, df: pd.DataFrame):
    df = df.dropna(subset=["comment_id"]).copy()
    upsert(conn, "comments", df,
           pk_cols=["comment_id"],
           update_cols=["comment_text", "comment_likes", "published_at"])


def load_tags(conn, df: pd.DataFrame):
    df = df.dropna().drop_duplicates(subset=["video_id", "tag"]).copy()
    upsert(conn, "video_tags", df,
           pk_cols=["video_id", "tag"],
           update_cols=["tag"])   # no-op update, but required by upsert syntax


# ── Main ──────────────────────────────────────────────────────────────────────
def run_ingestion():
    safe_url = make_safe_url(DB_URL)

    # SQLAlchemy engine used only for DDL (table creation)
    engine = create_engine(safe_url, echo=False)
    create_tables(engine)
    engine.dispose()

    # psycopg2 direct connection for bulk upserts
    log.info("Connecting to Supabase PostgreSQL via psycopg2...")
    conn = psycopg2.connect(safe_url)
    conn.autocommit = False

    try:
        # ── Extract ───────────────────────────────────────────────────────────
        log.info("Starting YouTube extraction pipeline...")
        channels_df, videos_df, comments_df, tags_df = run_extraction_pipeline()

        # ── Load (FK order: channels → videos → comments / tags) ─────────────
        log.info("Loading data into PostgreSQL...")
        load_channels(conn, channels_df)
        load_videos(conn, videos_df)
        load_comments(conn, comments_df)
        load_tags(conn, tags_df)

        conn.commit()
        log.info("=" * 60)
        log.info("Ingestion complete. Data is live in Supabase.")
        log.info(f"  channels : {len(channels_df)}")
        log.info(f"  videos   : {len(videos_df)}")
        log.info(f"  comments : {len(comments_df)}")
        log.info(f"  tags     : {len(tags_df)}")
        log.info("=" * 60)

    except Exception as e:
        conn.rollback()
        log.error(f"Ingestion failed — rolled back. Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_ingestion()
