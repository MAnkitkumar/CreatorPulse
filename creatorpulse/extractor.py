"""
CreatorPulse — Module 1: YouTube Data Extraction Pipeline
=========================================================
Extracts channel stats, video metadata, and top comments
from the YouTube Data API v3 for a list of target channels.

Handles:
  - Pagination via nextPageToken
  - ISO 8601 duration → seconds conversion
  - Exponential backoff on quota / rate-limit errors (HTTP 403/429)
  - Returns three clean DataFrames: channels_df, videos_df, comments_df
"""

import time
import math
import logging
import isodate
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import YOUTUBE_API_KEY, CHANNEL_IDS, MAX_VIDEOS_PER_CHANNEL, MAX_COMMENTS_PER_VIDEO

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── YouTube client factory ────────────────────────────────────────────────────
def build_youtube_client() -> object:
    """Build and return an authenticated YouTube Data API v3 service object."""
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


# ── Exponential backoff wrapper ───────────────────────────────────────────────
def api_call_with_backoff(request_fn, max_retries: int = 5):
    """
    Execute a YouTube API request with exponential backoff.
    Retries on transient 500/503 errors and quota exhaustion (403).
    Raises immediately on unrecoverable errors (e.g., 400 bad request).
    """
    for attempt in range(max_retries):
        try:
            return request_fn().execute()
        except HttpError as e:
            status = e.resp.status
            if status in (403, 429, 500, 503):
                wait = math.pow(2, attempt)  # 1s, 2s, 4s, 8s, 16s
                log.warning(f"HTTP {status} — retrying in {wait:.0f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                raise  # Non-retryable error, surface immediately
    raise RuntimeError("Max retries exceeded. Check API quota or network.")


# ── ISO 8601 duration → seconds ───────────────────────────────────────────────
def parse_duration_seconds(iso_duration: str) -> int:
    """
    Convert ISO 8601 duration string (e.g., 'PT12M34S') to total seconds.
    Returns 0 if parsing fails (e.g., live streams with 'P0D').
    """
    try:
        return int(isodate.parse_duration(iso_duration).total_seconds())
    except Exception:
        return 0


# ── Duration bucket classifier ────────────────────────────────────────────────
def classify_duration(seconds: int) -> str:
    """
    Map duration in seconds to a human-readable content bucket.
    Short: <3 min | Medium: 3-10 min | Long: 10-20 min | Extended: >20 min
    """
    minutes = seconds / 60
    if minutes < 3:
        return "Short"
    elif minutes < 10:
        return "Medium"
    elif minutes < 20:
        return "Long"
    else:
        return "Extended"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Channel-level statistics
# ─────────────────────────────────────────────────────────────────────────────
def fetch_channel_stats(youtube, channel_ids: list) -> pd.DataFrame:
    """
    Fetch top-level channel statistics for a list of channel IDs.

    API cost: 1 unit per call, batches up to 50 IDs.
    Returns columns: channel_id, channel_name, subscribers, total_views, video_count
    """
    log.info(f"Fetching stats for {len(channel_ids)} channels...")
    records = []

    # Batch into groups of 50 (API limit per request)
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        response = api_call_with_backoff(
            lambda: youtube.channels().list(
                part="snippet,statistics",
                id=",".join(batch),
                maxResults=50,
            )
        )

        for item in response.get("items", []):
            stats = item["statistics"]
            records.append({
                "channel_id":    item["id"],
                "channel_name":  item["snippet"]["title"],
                "subscribers":   int(stats.get("subscriberCount", 0)),
                "total_views":   int(stats.get("viewCount", 0)),
                "video_count":   int(stats.get("videoCount", 0)),
            })

    df = pd.DataFrame(records)
    log.info(f"  → {len(df)} channels retrieved.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Video IDs via uploads playlist
# ─────────────────────────────────────────────────────────────────────────────
def fetch_video_ids(youtube, channel_id: str, max_videos: int) -> list:
    """
    Retrieve up to `max_videos` video IDs from a channel's uploads playlist.
    Uses pagination (nextPageToken) to go beyond the 50-result page limit.

    API cost: 1 unit per page (50 items).
    """
    # Get the uploads playlist ID for this channel
    channel_resp = api_call_with_backoff(
        lambda: youtube.channels().list(
            part="contentDetails",
            id=channel_id,
        )
    )
    uploads_playlist_id = (
        channel_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )

    video_ids = []
    next_page_token = None

    while len(video_ids) < max_videos:
        fetch_count = min(50, max_videos - len(video_ids))

        response = api_call_with_backoff(
            lambda: youtube.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=fetch_count,
                pageToken=next_page_token,
            )
        )

        for item in response.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break  # No more pages

    return video_ids


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Video metadata (batched by 50)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_video_details(youtube, video_ids: list, channel_id: str) -> pd.DataFrame:
    """
    Fetch full metadata for a list of video IDs (batched at 50 per request).
    Computes duration_seconds, duration_bucket, and all 5 derived KPIs.

    Derived metrics computed here:
      - engagement_rate: ((likes + comments) / views) * 100
      - idr:             (comments / likes) * 100
      - vii:             ((likes + comments * 3) / views) * 100
      - vvi:             views / days_since_upload
    """
    log.info(f"  Fetching details for {len(video_ids)} videos...")
    records = []
    now = pd.Timestamp.utcnow().tz_localize(None)

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        response = api_call_with_backoff(
            lambda: youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch),
            )
        )

        for item in response.get("items", []):
            snippet = item["snippet"]
            stats   = item["statistics"]
            content = item["contentDetails"]

            views    = int(stats.get("viewCount", 0))
            likes    = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))

            duration_sec    = parse_duration_seconds(content.get("duration", "PT0S"))
            duration_bucket = classify_duration(duration_sec)

            published_at = pd.to_datetime(snippet["publishedAt"]).tz_localize(None)
            days_since   = max((now - published_at).days, 1)  # floor at 1 to avoid division by zero

            # ── Derived KPIs ────────────────────────────────────────────────
            engagement_rate = round(((likes + comments) / views * 100), 4) if views > 0 else 0.0
            idr             = round((comments / likes * 100), 4)           if likes > 0 else 0.0
            vii             = round(((likes + comments * 3) / views * 100), 4) if views > 0 else 0.0
            vvi             = round(views / days_since, 2)

            records.append({
                "video_id":        item["id"],
                "channel_id":      channel_id,
                "title":           snippet["title"],
                "published_at":    published_at,
                "duration_seconds": duration_sec,
                "duration_bucket": duration_bucket,
                "views":           views,
                "likes":           likes,
                "comments_count":  comments,
                "tags":            snippet.get("tags", []),  # list, flattened in video_tags table
                "engagement_rate": engagement_rate,
                "idr":             idr,
                "vii":             vii,
                "vvi":             vvi,
            })

    df = pd.DataFrame(records)
    log.info(f"    → {len(df)} video records built.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Top comments per video
# ─────────────────────────────────────────────────────────────────────────────
def fetch_comments(youtube, video_id: str, max_comments: int) -> list:
    """
    Fetch top-level comments for a single video, sorted by relevance.
    Paginates until `max_comments` is reached or the thread is exhausted.

    Returns a list of dicts ready for DataFrame construction.
    API cost: 1 unit per page (100 comments).
    """
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        fetch_count = min(100, max_comments - len(comments))
        try:
            # Call API directly (no backoff) so commentsDisabled 403 exits immediately
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=fetch_count,
                order="relevance",
                pageToken=next_page_token,
            ).execute()
        except HttpError as e:
            status = e.resp.status
            try:
                reason = e.error_details[0].get("reason", "") if e.error_details else ""
            except Exception:
                reason = str(e.content)
            if status == 403 and reason == "commentsDisabled":
                log.warning(f"    Comments disabled for video {video_id}. Skipping.")
                break
            # For other transient errors, use backoff via a simple retry
            elif status in (429, 500, 503):
                log.warning(f"    HTTP {status} on comments for {video_id}, retrying once...")
                time.sleep(2)
                continue
            else:
                log.warning(f"    HTTP {status} on comments for {video_id}. Skipping.")
                break

        for item in response.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "comment_id":        item["id"],
                "video_id":          video_id,
                "comment_text":      top.get("textOriginal", ""),
                "comment_likes":     int(top.get("likeCount", 0)),
                "published_at":      pd.to_datetime(top["publishedAt"]).tz_localize(None),
                # sentiment fields populated later by Module 3
                "sentiment_compound": None,
                "sentiment_label":    None,
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return comments


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
def run_extraction_pipeline() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Full pipeline entry point.
    Returns: (channels_df, videos_df, comments_df, tags_df)
    """
    youtube = build_youtube_client()

    # ── Step 1: Channel stats ─────────────────────────────────────────────────
    channels_df = fetch_channel_stats(youtube, CHANNEL_IDS)

    all_videos   = []
    all_comments = []
    all_tags     = []

    for _, channel_row in channels_df.iterrows():
        channel_id   = channel_row["channel_id"]
        channel_name = channel_row["channel_name"]
        log.info(f"Processing channel: {channel_name} ({channel_id})")

        # ── Step 2: Video IDs ─────────────────────────────────────────────────
        video_ids = fetch_video_ids(youtube, channel_id, MAX_VIDEOS_PER_CHANNEL)
        log.info(f"  Found {len(video_ids)} video IDs.")

        # ── Step 3: Video metadata + KPIs ─────────────────────────────────────
        videos_df = fetch_video_details(youtube, video_ids, channel_id)
        all_videos.append(videos_df)

        # ── Step 3b: Explode tags into video_tags rows ────────────────────────
        for _, vrow in videos_df.iterrows():
            for tag in vrow["tags"]:
                all_tags.append({"video_id": vrow["video_id"], "tag": tag.lower().strip()})

        # ── Step 4: Comments ──────────────────────────────────────────────────
        for video_id in video_ids:
            log.info(f"    Fetching comments for video {video_id}...")
            comments = fetch_comments(youtube, video_id, MAX_COMMENTS_PER_VIDEO)
            all_comments.extend(comments)
            log.info(f"      → {len(comments)} comments retrieved.")

    # ── Assemble final DataFrames ─────────────────────────────────────────────
    videos_df_final   = pd.concat(all_videos, ignore_index=True).drop(columns=["tags"])
    comments_df_final = pd.DataFrame(all_comments)
    tags_df_final     = pd.DataFrame(all_tags).drop_duplicates()

    log.info("=" * 60)
    log.info(f"Extraction complete.")
    log.info(f"  Channels : {len(channels_df)}")
    log.info(f"  Videos   : {len(videos_df_final)}")
    log.info(f"  Comments : {len(comments_df_final)}")
    log.info(f"  Tags     : {len(tags_df_final)}")
    log.info("=" * 60)

    return channels_df, videos_df_final, comments_df_final, tags_df_final


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    channels, videos, comments, tags = run_extraction_pipeline()

    # Quick sanity check — print first few rows of each dataset
    print("\n── Channels ──")
    print(channels.to_string(index=False))

    print("\n── Videos (first 5) ──")
    print(videos.head().to_string(index=False))

    print("\n── Comments (first 3) ──")
    print(comments.head(3).to_string(index=False))

    print("\n── Tags (first 5) ──")
    print(tags.head().to_string(index=False))
