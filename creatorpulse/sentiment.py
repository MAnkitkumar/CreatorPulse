"""
CreatorPulse — Module 3: Sentiment Analysis & Feature Engineering
=================================================================
1. Downloads VADER lexicon (one-time, auto-skips if already present).
2. Pulls all unanalyzed comments from PostgreSQL (sentiment_compound IS NULL).
3. Computes VADER compound score for each comment.
4. Labels each comment: Positive (>=0.05), Neutral (-0.05 to 0.05), Negative (<=-0.05).
5. Writes scores + labels back to the comments table in batches.
6. Aggregates per-video average sentiment and writes it to videos.avg_sentiment.
"""

import logging
from urllib.parse import quote_plus

import nltk
import pandas as pd
import psycopg2
import psycopg2.extras
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from config import DB_URL

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── VADER thresholds (industry standard) ─────────────────────────────────────
POSITIVE_THRESHOLD =  0.05
NEGATIVE_THRESHOLD = -0.05
BATCH_SIZE         = 1000   # rows per DB write batch


def download_vader():
    """Download VADER lexicon if not already present."""
    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
        log.info("VADER lexicon already present.")
    except LookupError:
        log.info("Downloading VADER lexicon...")
        nltk.download("vader_lexicon", quiet=True)
        log.info("  Done.")


def make_conn() -> psycopg2.extensions.connection:
    """Build a psycopg2 connection, safely encoding the password."""
    scheme, rest   = DB_URL.split("://", 1)
    credentials, hostpart = rest.rsplit("@", 1)
    user, password = credentials.split(":", 1)
    safe_url = f"{scheme}://{user}:{quote_plus(password)}@{hostpart}"
    return psycopg2.connect(safe_url)


# ── Sentiment label classifier ────────────────────────────────────────────────
def label(score: float) -> str:
    if score >= POSITIVE_THRESHOLD:
        return "Positive"
    elif score <= NEGATIVE_THRESHOLD:
        return "Negative"
    else:
        return "Neutral"


# ── Step 1: Pull unanalyzed comments ─────────────────────────────────────────
def fetch_unanalyzed_comments(conn) -> pd.DataFrame:
    """
    Fetch all comments where sentiment_compound is still NULL.
    On re-runs, only new comments get processed — existing ones are skipped.
    """
    query = """
        SELECT comment_id, comment_text
        FROM   comments
        WHERE  sentiment_compound IS NULL
          AND  comment_text IS NOT NULL
          AND  comment_text != ''
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    df = pd.DataFrame(rows, columns=["comment_id", "comment_text"])
    log.info(f"  {len(df):,} unanalyzed comments found.")
    return df


# ── Step 2: Score all comments ────────────────────────────────────────────────
def score_comments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply VADER SentimentIntensityAnalyzer to every comment.
    Adds two columns: sentiment_compound (float), sentiment_label (str).
    """
    sia = SentimentIntensityAnalyzer()

    compounds = []
    labels    = []

    for text in df["comment_text"]:
        try:
            score = sia.polarity_scores(str(text))["compound"]
        except Exception:
            score = 0.0   # fallback for any encoding edge cases
        compounds.append(round(score, 4))
        labels.append(label(score))

    df = df.copy()
    df["sentiment_compound"] = compounds
    df["sentiment_label"]    = labels
    return df


# ── Step 3: Write scores back to comments table ───────────────────────────────
def update_comments(conn, df: pd.DataFrame):
    """
    Batch-update comments table with compound scores and labels.
    Uses execute_values for performance on 19k+ rows.
    """
    records = list(zip(
        df["sentiment_compound"],
        df["sentiment_label"],
        df["comment_id"],
    ))

    sql = """
        UPDATE comments
        SET    sentiment_compound = data.score,
               sentiment_label   = data.label
        FROM   (VALUES %s) AS data(score, label, comment_id)
        WHERE  comments.comment_id = data.comment_id
    """

    total = len(records)
    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, batch)
        conn.commit()
        log.info(f"  Updated comments {i + 1:,} – {min(i + BATCH_SIZE, total):,} of {total:,}")


# ── Step 4: Aggregate per-video avg sentiment → videos table ──────────────────
def update_video_sentiment(conn):
    """
    Compute avg(sentiment_compound) per video from the comments table
    and write it into videos.avg_sentiment.
    Only updates videos that have at least 1 scored comment.
    """
    sql = """
        UPDATE videos v
        SET    avg_sentiment = agg.avg_score
        FROM (
            SELECT   video_id,
                     ROUND(AVG(sentiment_compound)::NUMERIC, 4) AS avg_score
            FROM     comments
            WHERE    sentiment_compound IS NOT NULL
            GROUP BY video_id
        ) agg
        WHERE v.video_id = agg.video_id
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

    # Report how many videos got updated
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM videos WHERE avg_sentiment IS NOT NULL")
        count = cur.fetchone()[0]
    log.info(f"  avg_sentiment populated for {count:,} videos.")


# ── Step 5: Quick sentiment distribution report ───────────────────────────────
def print_sentiment_report(conn):
    """Print a breakdown of sentiment labels across the entire dataset."""
    sql = """
        SELECT sentiment_label,
               COUNT(*)                                    AS count,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
        FROM   comments
        WHERE  sentiment_label IS NOT NULL
        GROUP BY sentiment_label
        ORDER BY count DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    log.info("── Sentiment Distribution ──────────────────────")
    for label_name, count, pct in rows:
        bar = "█" * int(pct // 2)
        log.info(f"  {label_name:<10} {count:>6,}  ({pct:>5.1f}%)  {bar}")
    log.info("────────────────────────────────────────────────")

    # Top 5 most positive videos
    sql2 = """
        SELECT v.title, c.channel_name, ROUND(v.avg_sentiment::NUMERIC, 4) AS sentiment
        FROM   videos v
        JOIN   channels c USING (channel_id)
        WHERE  v.avg_sentiment IS NOT NULL
        ORDER  BY v.avg_sentiment DESC
        LIMIT  5
    """
    with conn.cursor() as cur:
        cur.execute(sql2)
        rows2 = cur.fetchall()

    log.info("── Top 5 Most Positive Videos ──────────────────")
    for title, channel, score in rows2:
        log.info(f"  [{score:+.4f}] {channel} — {title[:60]}")
    log.info("────────────────────────────────────────────────")


# ── Main ──────────────────────────────────────────────────────────────────────
def run_sentiment_pipeline():
    # 1 — Ensure VADER lexicon is available
    download_vader()

    conn = make_conn()
    conn.autocommit = False

    try:
        log.info("=" * 60)
        log.info("Module 3: Sentiment Analysis Pipeline")
        log.info("=" * 60)

        # 2 — Fetch unscored comments
        log.info("Fetching unanalyzed comments from PostgreSQL...")
        comments_df = fetch_unanalyzed_comments(conn)

        if comments_df.empty:
            log.info("All comments already analyzed. Nothing to do.")
        else:
            # 3 — Score with VADER
            log.info("Running VADER sentiment scoring...")
            scored_df = score_comments(comments_df)

            pos = (scored_df["sentiment_label"] == "Positive").sum()
            neu = (scored_df["sentiment_label"] == "Neutral").sum()
            neg = (scored_df["sentiment_label"] == "Negative").sum()
            log.info(f"  Scores computed — Positive: {pos:,} | Neutral: {neu:,} | Negative: {neg:,}")

            # 4 — Write back to comments
            log.info("Writing sentiment scores to comments table...")
            update_comments(conn, scored_df)

        # 5 — Aggregate to videos
        log.info("Aggregating average sentiment per video...")
        update_video_sentiment(conn)

        # 6 — Print summary report
        print_sentiment_report(conn)

        log.info("=" * 60)
        log.info("Module 3 complete.")
        log.info("=" * 60)

    except Exception as e:
        conn.rollback()
        log.error(f"Sentiment pipeline failed — rolled back. Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_sentiment_pipeline()
