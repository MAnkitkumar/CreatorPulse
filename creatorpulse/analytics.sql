-- =============================================================================
-- CreatorPulse — Module 4: Production SQL Analytics Queries
-- Run these in Supabase SQL Editor or any PostgreSQL client.
-- Each query is self-contained and uses CTEs + Window Functions.
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 1: Channel Performance Benchmarking
-- Ranks every video within its own channel by Engagement Rate AND VVI.
-- Use this to identify each channel's top performers vs. dead weight.
-- ─────────────────────────────────────────────────────────────────────────────
WITH ranked_videos AS (
    SELECT
        c.channel_name,
        v.title,
        v.published_at::DATE                                        AS published_date,
        v.duration_bucket,
        v.views,
        v.likes,
        v.comments_count,
        v.engagement_rate,
        v.vvi,
        v.avg_sentiment,

        -- Rank within channel by Engagement Rate (1 = best)
        RANK() OVER (
            PARTITION BY v.channel_id
            ORDER BY v.engagement_rate DESC
        )                                                           AS er_rank,

        -- Rank within channel by View Velocity Index (1 = fastest growing)
        RANK() OVER (
            PARTITION BY v.channel_id
            ORDER BY v.vvi DESC
        )                                                           AS vvi_rank,

        -- Percentile bucket: top 25% vs bottom 25%
        NTILE(4) OVER (
            PARTITION BY v.channel_id
            ORDER BY v.engagement_rate DESC
        )                                                           AS er_quartile

    FROM videos v
    JOIN channels c USING (channel_id)
)
SELECT
    channel_name,
    title,
    published_date,
    duration_bucket,
    views,
    engagement_rate,
    vvi,
    ROUND(avg_sentiment, 4)                                         AS sentiment,
    er_rank,
    vvi_rank,
    CASE er_quartile
        WHEN 1 THEN 'Top Performer'
        WHEN 2 THEN 'Above Average'
        WHEN 3 THEN 'Below Average'
        WHEN 4 THEN 'Underperformer'
    END                                                             AS performance_tier
FROM ranked_videos
ORDER BY channel_name, er_rank;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 2: Content Duration Matrix
-- Finds the optimal video length by comparing avg Views, Engagement Rate,
-- and IDR across all duration buckets.
-- Key insight: which length format drives the most discussion vs passive views?
-- ─────────────────────────────────────────────────────────────────────────────
WITH duration_stats AS (
    SELECT
        v.duration_bucket,
        COUNT(*)                                                    AS video_count,
        ROUND(AVG(v.views))                                         AS avg_views,
        ROUND(AVG(v.engagement_rate), 4)                            AS avg_engagement_rate,
        ROUND(AVG(v.idr), 4)                                        AS avg_idr,
        ROUND(AVG(v.vii), 4)                                        AS avg_vii,
        ROUND(AVG(v.vvi), 2)                                        AS avg_vvi,
        ROUND(AVG(v.avg_sentiment), 4)                              AS avg_sentiment,
        ROUND(STDDEV(v.engagement_rate), 4)                         AS er_stddev   -- consistency metric
    FROM videos v
    WHERE v.duration_bucket IS NOT NULL
    GROUP BY v.duration_bucket
),
ranked_buckets AS (
    SELECT *,
        -- Rank buckets by avg engagement rate
        RANK() OVER (ORDER BY avg_engagement_rate DESC)             AS er_rank,
        -- Rank by pure view volume
        RANK() OVER (ORDER BY avg_views DESC)                       AS views_rank
    FROM duration_stats
)
SELECT
    CASE duration_bucket
        WHEN 'Short'    THEN '1. Short    (<3 min)'
        WHEN 'Medium'   THEN '2. Medium   (3-10 min)'
        WHEN 'Long'     THEN '3. Long     (10-20 min)'
        WHEN 'Extended' THEN '4. Extended (>20 min)'
    END                                                             AS duration_bucket,
    video_count,
    avg_views,
    avg_engagement_rate,
    avg_idr,
    avg_vii,
    avg_vvi,
    avg_sentiment,
    er_stddev,
    er_rank                                                         AS engagement_rank,
    views_rank
FROM ranked_buckets
ORDER BY er_rank;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 3: Sentiment Quartile vs. Performance
-- Splits videos into 4 sentiment quartiles (Q1 = most positive)
-- then compares their avg VII, engagement rate, and view count.
-- Tests the hypothesis: do happier comment sections drive more virality?
-- ─────────────────────────────────────────────────────────────────────────────
WITH sentiment_quartiles AS (
    SELECT
        v.video_id,
        v.title,
        c.channel_name,
        v.avg_sentiment,
        v.vii,
        v.engagement_rate,
        v.views,
        v.idr,

        -- Divide into 4 equal sentiment buckets (1 = most positive)
        NTILE(4) OVER (ORDER BY v.avg_sentiment DESC)               AS sentiment_quartile

    FROM videos v
    JOIN channels c USING (channel_id)
    WHERE v.avg_sentiment IS NOT NULL
),
quartile_summary AS (
    SELECT
        sentiment_quartile,
        COUNT(*)                                                     AS video_count,
        ROUND(MIN(avg_sentiment)::NUMERIC,  4)                       AS min_sentiment,
        ROUND(MAX(avg_sentiment)::NUMERIC,  4)                       AS max_sentiment,
        ROUND(AVG(avg_sentiment)::NUMERIC,  4)                       AS avg_sentiment,
        ROUND(AVG(vii)::NUMERIC,            4)                       AS avg_vii,
        ROUND(AVG(engagement_rate)::NUMERIC,4)                       AS avg_engagement_rate,
        ROUND(AVG(views)::NUMERIC,          0)                       AS avg_views,
        ROUND(AVG(idr)::NUMERIC,            4)                       AS avg_idr
    FROM sentiment_quartiles
    GROUP BY sentiment_quartile
)
SELECT
    CASE sentiment_quartile
        WHEN 1 THEN 'Q1 — Most Positive'
        WHEN 2 THEN 'Q2 — Positive'
        WHEN 3 THEN 'Q3 — Neutral/Mixed'
        WHEN 4 THEN 'Q4 — Most Negative'
    END                                                              AS sentiment_tier,
    video_count,
    min_sentiment,
    max_sentiment,
    avg_sentiment,
    avg_vii,
    avg_engagement_rate,
    avg_views,
    avg_idr
FROM quartile_summary
ORDER BY sentiment_quartile;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 4: Optimal Publishing Window
-- Extracts day-of-week and hour-of-day from published_at to find
-- which upload slots drive the highest median engagement rates.
-- Use this to advise channels on *when* to publish for maximum reach.
-- ─────────────────────────────────────────────────────────────────────────────
WITH upload_timing AS (
    SELECT
        v.video_id,
        c.channel_name,
        -- Day 0=Sunday, 1=Monday ... 6=Saturday in PostgreSQL EXTRACT
        EXTRACT(DOW  FROM v.published_at)::INT                      AS day_of_week_num,
        TO_CHAR(v.published_at, 'Day')                              AS day_of_week,
        EXTRACT(HOUR FROM v.published_at)::INT                      AS hour_of_day,
        v.engagement_rate,
        v.views,
        v.vvi
    FROM videos v
    JOIN channels c USING (channel_id)
),
window_stats AS (
    SELECT
        day_of_week_num,
        TRIM(day_of_week)                                           AS day_of_week,
        hour_of_day,
        COUNT(*)                                                     AS videos_uploaded,

        -- Use PERCENTILE_CONT for median (more robust than AVG against outliers)
        ROUND(
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY engagement_rate)::NUMERIC
        , 4)                                                         AS median_engagement_rate,

        ROUND(AVG(engagement_rate)::NUMERIC, 4)                     AS avg_engagement_rate,
        ROUND(AVG(views)::NUMERIC, 0)                               AS avg_views,
        ROUND(AVG(vvi)::NUMERIC, 2)                                 AS avg_vvi
    FROM upload_timing
    GROUP BY day_of_week_num, day_of_week, hour_of_day
    HAVING COUNT(*) >= 2   -- filter slots with at least 2 data points
)
SELECT
    day_of_week,
    hour_of_day,
    TO_CHAR(hour_of_day, 'FM00') || ':00'                           AS time_slot,
    videos_uploaded,
    median_engagement_rate,
    avg_engagement_rate,
    avg_views,
    avg_vvi,
    -- Flag the top 20% engagement windows
    CASE WHEN PERCENT_RANK() OVER (ORDER BY median_engagement_rate DESC) <= 0.20
         THEN 'Peak Window'
         ELSE 'Standard'
    END                                                              AS window_type
FROM window_stats
ORDER BY median_engagement_rate DESC
LIMIT 20;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 5: Content Fatigue & Evergreen Decay Analysis
-- Compares each video's VVI against its channel baseline.
-- Evergreen: VVI still above channel avg 30+ days after upload.
-- Decaying:  VVI significantly below channel avg, age > 30 days.
-- ─────────────────────────────────────────────────────────────────────────────
WITH channel_baseline AS (
    -- Per-channel avg VVI across all videos (the "normal" velocity)
    SELECT
        channel_id,
        ROUND(AVG(vvi)::NUMERIC, 2)                                  AS channel_avg_vvi,
        ROUND(STDDEV(vvi)::NUMERIC, 2)                               AS channel_stddev_vvi
    FROM videos
    GROUP BY channel_id
),
video_age AS (
    SELECT
        v.video_id,
        c.channel_name,
        v.title,
        v.published_at::DATE                                         AS published_date,
        (CURRENT_DATE - v.published_at::DATE)                        AS days_old,
        v.views,
        v.vvi,
        v.engagement_rate,
        v.avg_sentiment,
        v.duration_bucket,
        b.channel_avg_vvi,
        b.channel_stddev_vvi,

        -- How far above/below the channel baseline is this video?
        ROUND((v.vvi - b.channel_avg_vvi)::NUMERIC, 2)               AS vvi_vs_baseline,

        -- Z-score: how many std deviations from the mean
        CASE WHEN b.channel_stddev_vvi > 0
             THEN ROUND(((v.vvi - b.channel_avg_vvi) / b.channel_stddev_vvi)::NUMERIC, 2)
             ELSE 0
        END                                                           AS vvi_zscore

    FROM videos v
    JOIN channels c USING (channel_id)
    JOIN channel_baseline b USING (channel_id)
)
SELECT
    channel_name,
    title,
    published_date,
    days_old,
    duration_bucket,
    views,
    ROUND(vvi::NUMERIC, 2)                                           AS vvi,
    channel_avg_vvi,
    vvi_vs_baseline,
    vvi_zscore,
    ROUND(avg_sentiment::NUMERIC, 4)                                 AS avg_sentiment,

    -- Content classification
    CASE
        WHEN days_old >= 30 AND vvi >= channel_avg_vvi
            THEN 'Evergreen'           -- old but still pulling views
        WHEN days_old < 30 AND vvi > channel_avg_vvi * 1.5
            THEN 'Viral Spike'         -- new and dramatically outperforming
        WHEN days_old >= 30 AND vvi < channel_avg_vvi * 0.5
            THEN 'Decaying'            -- old and well below baseline
        WHEN days_old < 30
            THEN 'Recent Upload'       -- too new to classify
        ELSE 'Stable'
    END                                                              AS content_lifecycle

FROM video_age
ORDER BY
    CASE
        WHEN days_old >= 30 AND vvi >= channel_avg_vvi THEN 1
        WHEN days_old < 30 AND vvi > channel_avg_vvi * 1.5 THEN 2
        ELSE 3
    END,
    vvi_vs_baseline DESC;
