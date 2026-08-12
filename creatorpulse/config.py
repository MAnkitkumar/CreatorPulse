"""
CreatorPulse — Central Configuration
Loads API keys and target channel IDs from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── YouTube Data API v3 ──────────────────────────────────────────────────────
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# ── Target Channels (Channel IDs, not handles) ───────────────────────────────
# Find a channel ID: go to channel page → View Source → search "channelId"
CHANNEL_IDS = [
    "UCWr0mx597DnSGLFk1WfvSkQ",  # Alex The Analyst
    "UCLLw7jmFsvfIVaUFsLs8mlQ",  # Luke Barousse
    "UCiT9RITQ9PW6BhXK0y2jaeg",  # Ken Jee
    "UCtYLUTtgS3k1Fg4y5tAhLbw",  # StatQuest (Josh Starmer)
    "UC2UXDak6o7rBm23x3jGpu3A",  # Tina Huang
]

# ── Extraction Limits ────────────────────────────────────────────────────────
MAX_VIDEOS_PER_CHANNEL = 100   # YouTube API max per playlistItems call is 50 (paginated)
MAX_COMMENTS_PER_VIDEO = 200   # Top-level comments per video

# ── PostgreSQL Connection (Supabase / Railway) ───────────────────────────────
DB_URL = os.getenv("DATABASE_URL")  # e.g. postgresql://user:pass@host:port/dbname
