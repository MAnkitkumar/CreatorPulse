-- =============================================================================
-- CreatorPulse — Module 2: PostgreSQL Relational Schema (3NF)
-- Run this once against your Supabase database to create all tables.
-- =============================================================================

-- ── 1. channels ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS channels (
    channel_id    VARCHAR(64)  PRIMARY KEY,
    channel_name  VARCHAR(255) NOT NULL,
    subscribers   BIGINT       DEFAULT 0,
    total_views   BIGINT       DEFAULT 0,
    video_count   INTEGER      DEFAULT 0,
    updated_at    TIMESTAMPTZ  DEFAULT NOW()
);

-- ── 2. videos ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS videos (
    video_id          VARCHAR(64)    PRIMARY KEY,
    channel_id        VARCHAR(64)    NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    title             TEXT           NOT NULL,
    published_at      TIMESTAMPTZ    NOT NULL,
    duration_seconds  INTEGER        DEFAULT 0,
    duration_bucket   VARCHAR(16)    CHECK (duration_bucket IN ('Short','Medium','Long','Extended')),
    views             BIGINT         DEFAULT 0,
    likes             BIGINT         DEFAULT 0,
    comments_count    INTEGER        DEFAULT 0,
    -- Derived KPIs (computed at extraction, updated by sentiment module)
    engagement_rate   NUMERIC(10,4)  DEFAULT 0.0,   -- ((likes+comments)/views)*100
    idr               NUMERIC(10,4)  DEFAULT 0.0,   -- (comments/likes)*100
    vii               NUMERIC(10,4)  DEFAULT 0.0,   -- ((likes+comments*3)/views)*100
    vvi               NUMERIC(10,2)  DEFAULT 0.0,   -- views/days_since_upload
    avg_sentiment     NUMERIC(6,4)   DEFAULT NULL   -- populated by Module 3
);

-- ── 3. comments ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS comments (
    comment_id         VARCHAR(128)  PRIMARY KEY,
    video_id           VARCHAR(64)   NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    comment_text       TEXT,
    comment_likes      INTEGER       DEFAULT 0,
    sentiment_compound NUMERIC(6,4)  DEFAULT NULL,  -- VADER score, populated by Module 3
    sentiment_label    VARCHAR(16)   CHECK (sentiment_label IN ('Positive','Neutral','Negative') OR sentiment_label IS NULL),
    published_at       TIMESTAMPTZ
);

-- ── 4. video_tags ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS video_tags (
    video_id  VARCHAR(64)  NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    tag       VARCHAR(255) NOT NULL,
    PRIMARY KEY (video_id, tag)   -- composite PK prevents duplicate tag rows
);

-- =============================================================================
-- INDEXES — on high-cardinality / frequently filtered columns
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_videos_channel_id     ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_videos_published_at   ON videos(published_at);
CREATE INDEX IF NOT EXISTS idx_videos_duration_bucket ON videos(duration_bucket);
CREATE INDEX IF NOT EXISTS idx_comments_video_id     ON comments(video_id);
CREATE INDEX IF NOT EXISTS idx_comments_sentiment    ON comments(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_tags_tag              ON video_tags(tag);
