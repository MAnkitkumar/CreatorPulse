# CreatorPulse — Complete Interview Guide

## Part 1: The 2-Minute Elevator Pitch

**Say this first:**

> "I built CreatorPulse, an end-to-end data engineering project that analyzes YouTube content strategy. Here's the flow: I extract data from 4 YouTube channels using the YouTube API — that's 400 videos and nearly 20,000 comments. I load that into PostgreSQL on Supabase. Then I score every single comment for sentiment using VADER NLP, and finally I run SQL analytics to answer business questions like: what video length drives the most engagement? What time of day should creators upload? 
>
> The key finding: videos with positive comment sentiment achieve 49% higher virality than negative ones. I visualize all this in a Power BI dashboard.
>
> This shows I can take raw data from an API, design a database, apply machine learning, write production SQL, and deliver business insights."

**Why this works:**
- You hit all 5 layers (API → DB → NLP → SQL → BI)
- You lead with a business outcome (49% uplift)
- You show reproducibility and technical depth
- ~90 seconds, interviewer knows exactly what you did

---

## Part 2: How It Works (Technical Deep Dive)

Answer these questions in order:

### Q1: "Walk me through the data flow."

**Answer:**

```
YouTube API v3
    ↓
[Extract 400 videos + 19.7K comments]
    ↓
pandas DataFrames (in-memory transformation)
    ↓
PostgreSQL (4 normalized tables)
    ↓
[Raw data now persisted]
    ↓
VADER NLP (score each comment for sentiment)
    ↓
[Update comments table with compound scores]
    ↓
SQL queries (aggregate, rank, analyze)
    ↓
CSV export → Power BI (visualize & present)
```

**Say:**
> "Step 1: I call the YouTube API to get channel stats and video metadata. I extract 400 videos and up to 200 comments per video using pagination and exponential backoff to handle rate limits.
>
> Step 2: I load everything into PostgreSQL. I designed a normalized schema with 4 tables — channels, videos, comments, and video_tags. I use ON CONFLICT DO UPDATE so if I re-run the script, it doesn't duplicate data.
>
> Step 3: I pull all comments from the database, score them with VADER sentiment (which gives a score from -1 to +1), and I label them as Positive, Neutral, or Negative. I aggregate those scores back up to the video level.
>
> Step 4: I write SQL queries to find patterns — which videos have the highest engagement? Which times have the best sentiment? I use window functions to rank videos within channels and NTILE to split videos into quartiles by sentiment.
>
> Step 5: I export everything to CSV and load it into Power BI where I build KPI cards, charts, and a heatmap showing the best times to upload."

---

### Q2: "Why did you choose PostgreSQL over a data warehouse like BigQuery or Snowflake?"

**Answer:**
> "For this project scope, PostgreSQL is the right choice because:
>
> 1. **Cost**: Supabase free tier is $0. BigQuery/Snowflake would cost money even for 20K rows.
> 2. **Simplicity**: I don't need distributed query. My data fits in memory.
> 3. **ACID transactions**: I need strong guarantees on data integrity during upserts.
> 4. **Window functions**: PostgreSQL has everything I need (RANK, NTILE, PARTITION BY).
>
> In production at scale (terabytes), I'd use BigQuery or Snowflake. But for a portfolio project showing I can design schema, write SQL, and handle ETL? PostgreSQL is perfect.
>
> I also used the **session pooler** instead of direct connection because my network blocked port 5432 — that's a real-world problem-solving moment."

---

### Q3: "Why VADER for sentiment instead of a transformer model like BERT?"

**Answer:**
> "Great question. I chose VADER because:
>
> 1. **Speed**: VADER runs in milliseconds, no GPU needed. I processed 19.7K comments in 4 seconds.
> 2. **Domain fit**: VADER is optimized for social media text — short, casual, emoji-heavy. YouTube comments are exactly that.
> 3. **Interpretability**: VADER gives me a compound score I understand. BERT gives embeddings — harder to explain to a business stakeholder.
> 4. **No labeled data**: VADER is zero-shot. BERT would need thousands of labeled comments to fine-tune.
>
> If I needed to detect sarcasm or nuance, I'd use BERT. But for 'is this comment happy or angry?', VADER is production-ready.
>
> The result: 68.6% positive sentiment, which is what I expected for a data/tech learning audience."

---

### Q4: "Show me the schema. Why did you normalize it?"

**Answer:**

**Show this diagram:**
```
channels (PK: channel_id)
├── channel_name
├── subscribers
├── total_views
└── video_count
        ↓ (1:many relationship)
    videos (PK: video_id, FK: channel_id)
    ├── title
    ├── published_at
    ├── duration_seconds
    ├── views, likes, comments_count
    ├── engagement_rate (derived)
    ├── idr (derived)
    ├── vii (derived)
    ├── vvi (derived)
    └── avg_sentiment (derived)
            ↓ (1:many)
        comments (PK: comment_id, FK: video_id)
        ├── comment_text
        ├── sentiment_compound
        └── sentiment_label
            ↓ (1:many)
        video_tags (FK: video_id, tag)
```

**Say:**
> "I designed this in third normal form (3NF). Why?
>
> **Channels table**: One row per channel. No repetition.
>
> **Videos table**: One row per video. If I stored channel_name here too, I'd repeat it 100+ times (once per video). That's data redundancy. With 3NF, I store channel_name once in the channels table and join via foreign key.
>
> **Comments table**: One row per comment. Same logic — don't repeat video_id.
>
> **video_tags table**: Separate table because a video can have multiple tags. If I stored tags as a comma-separated string in videos, I couldn't query 'find all videos tagged with Python'. By normalizing to a separate table, I can do easy JOINs.
>
> **Result**: No data anomalies, efficient storage, fast queries with proper indexes."

---

### Q5: "What are these 'derived' KPIs? Why compute them at ingest time?"

**Answer:**
> "These are business metrics I calculate at ETL time:
>
> - **Engagement Rate**: (likes + comments) / views × 100. Is this video generating interaction?
> - **IDR (Interaction Depth Ratio)**: comments / likes × 100. Are people discussing deeply or just thumbs-upping?
> - **VII (Virality Intent Index)**: (likes + comments×3) / views × 100. Comments weighted 3x because discussion is high-intent.
> - **VVI (View Velocity Index)**: views / days_since_upload. Is this video still pulling views, or is it dead?
> - **Duration bucket**: Short/Medium/Long/Extended. Which format wins?
>
> I compute these at ingest because:
> 1. They're immutable (video metrics don't change after upload; I'm just analyzing post-hoc).
> 2. Queries run faster if the math is already done.
> 3. In a real pipeline, analysts would expect these metrics to be pre-calculated.
>
> In production, I'd keep raw metrics in a fact table and computed metrics in a separate analytics table for auditability."

---

### Q6: "Walk me through one SQL query. Why do you use CTEs and window functions?"

**Answer:**

**Show this query:**
```sql
WITH ranked_videos AS (
    SELECT
        c.channel_name,
        v.title,
        v.engagement_rate,
        RANK() OVER (
            PARTITION BY v.channel_id
            ORDER BY v.engagement_rate DESC
        ) AS er_rank,
        NTILE(4) OVER (
            PARTITION BY v.channel_id
            ORDER BY v.engagement_rate DESC
        ) AS er_quartile
    FROM videos v
    JOIN channels c USING (channel_id)
)
SELECT * FROM ranked_videos WHERE er_rank <= 5;
```

**Say:**
> "This query finds the top 5 videos per channel by engagement rate.
>
> **CTE (WITH clause)**: I use a CTE instead of nesting subqueries because it's readable. I call the intermediate result 'ranked_videos' and build on it.
>
> **RANK() OVER (PARTITION BY)**: This is a window function. It ranks videos within each channel independently. So channel A's top video gets rank 1, channel B's top video also gets rank 1 — they don't compete against each other.
>
> **ORDER BY engagement_rate DESC**: Within each partition (channel), sort by engagement descending, so highest engagement gets rank 1.
>
> **NTILE(4)**: Divides videos into 4 quartiles. Top 25% of videos = quartile 1. This lets me compare top performers vs bottom performers.
>
> **Why this pattern**: Window functions are perfect for 'ranking within groups'. Without them, I'd need a subquery for each channel — messy. With PARTITION BY, I do it in one pass.
>
> Result: I see 'Luke Barousse's top video has 8.4% engagement, rank 1 in his channel, and is in the top quartile overall.'"

---

## Part 3: How to Demo It Live (Step by Step)

### Demo Setup (5 minutes before interview)

**Have these files open in VS Code:**
1. `config.py` — show the channel IDs
2. `extractor.py` — scroll to the main function, show the pipeline
3. `db_schema.sql` — show the 4 tables + indexes
4. `sentiment.py` — show the VADER scoring
5. `analytics.sql` — show Query 1 (ranking query)
6. Power BI report (if built) or screenshot of the dashboard

**Have terminal ready:**
- Navigate to the project folder
- Show that `data/` folder has the CSVs

---

### Demo Script (Live)

**"Let me show you the code and results:"**

#### Step 1: Show the extraction (1 min)

```bash
cat config.py
```

**Point out:**
- 4 channel IDs (Luke Barousse, StatQuest, Ken Jee, Hallden)
- `MAX_VIDEOS_PER_CHANNEL = 100` and `MAX_COMMENTS_PER_VIDEO = 200`

**Say:**
> "I configured it to pull 100 videos from each channel with up to 200 comments per video. In production, I'd parameterize this."

---

#### Step 2: Show the schema (1 min)

```bash
cat db_schema.sql | head -50
```

**Point out:**
- `channels` table with PK on `channel_id`
- `videos` table with FK to channels
- Indexes on `channel_id`, `published_at`

**Say:**
> "I created 4 tables with proper relationships. The indexes on channel_id and published_at make queries fast even with 19K rows."

---

#### Step 3: Show ingestion stats (1 min)

```bash
python ingestion.py
```

**Show the output:**
```
[OK] Channels : 4
[OK] Videos   : 400
[OK] Comments : 19,737
[OK] Tags     : 4,215
```

**Say:**
> "In about 2 minutes, I extracted and loaded all data. The ON CONFLICT logic means I can re-run this and it won't duplicate."

---

#### Step 4: Show sentiment analysis (1 min)

```bash
python sentiment.py
```

**Show the output:**
```
Positive   13,541  (68.6%)  ████████████████████████
Neutral     4,560  (23.1%)  ██████
Negative    1,628  ( 8.2%)  ███
```

**Say:**
> "VADER scored all 19.7K comments in 4 seconds. The distribution shows 68.6% positive — expected for a learning audience. Now I'll show you what these insights reveal in SQL."

---

#### Step 5: Show SQL query results (2 min)

Open Supabase, run Query 1:

```bash
# Or run this locally:
psql "postgresql://postgres.fkqwjbjbmkymdfypldkm:CreatorPulse2024@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres" \
  -c "SELECT channel_name, title, engagement_rate, vvi, avg_sentiment FROM videos ORDER BY engagement_rate DESC LIMIT 5;"
```

**Show the results:**
```
Ken Jee      | Giving Back...              | 8.43%  | 15.2  | 0.5102
Ken Jee      | These 3 Things Make...      | 7.82%  | 12.1  | 0.4834
StatQuest    | Luis Serrano Q&A            | 6.51%  | 8.9   | 0.7203
Luke Barousse| Excel for Data Analytics    | 5.92%  | 4980  | 0.6541
Hallden      | Native development vs cross | 5.41%  | 2.1   | 0.9349
```

**Say:**
> "Here are the top 5 videos by engagement rate. Notice Ken Jee and Luke Barousse dominate. Also look at VVI — Luke's Excel course has VVI of 4,980, meaning it's pulling 4,980 views per day even though it's 2 years old. That's evergreen content."

---

#### Step 6: Show the heatmap query (1 min)

```bash
psql ... -c "
SELECT 
  TRIM(TO_CHAR(published_at, 'Day')) AS day,
  EXTRACT(HOUR FROM published_at)::INT AS hour,
  COUNT(*) AS uploads,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY engagement_rate), 4) AS median_er
FROM videos 
GROUP BY day, hour 
HAVING COUNT(*) >= 2
ORDER BY median_er DESC LIMIT 5;"
```

**Show results:**
```
Friday      | 15 | 2 | 6.5886
Thursday    | 16 | 5 | 6.5194
Wednesday   | 10 | 3 | 5.9834
Monday      | 14 | 4 | 5.2104
```

**Say:**
> "Friday at 3 PM is the golden upload window across all 4 channels. This is the kind of actionable insight a content agency would pay for."

---

#### Step 7: Show Power BI (1 min) — Optional

**If you built the dashboard:**
- Open Power BI → show the 5 KPI cards
- Show the heatmap visual
- Show the sentiment donut chart
- Click on a slicer and show how the dashboard updates dynamically

**Say:**
> "I built a Power BI dashboard with 6 DAX measures and 5 interactive visuals. Slicers let you filter by channel, duration, or sentiment. The strategy recommendation card updates in real-time based on your selections."

**If you haven't built it:**
- Show the `powerbi_spec.md` file
- Say: "I have the full spec here with DAX formulas. Building it takes ~30 min of UI work, but the architecture and SQL are already done and tested."

---

## Part 4: Expected Interview Questions & Answers

### Q: "What would you do differently if you had to scale this to 1M videos?"

**Answer:**
> "Good question. Today I'm using PostgreSQL because the data fits in memory. At 1M videos scale:
>
> 1. **Switch to BigQuery/Snowflake**: Petabyte-scale analytics. I'd load via batch jobs.
> 2. **Add Kafka**: Instead of batch extraction, stream comments in real-time.
> 3. **Partition by date**: Split large tables into time partitions for faster queries.
> 4. **Add caching**: Use Redis to cache popular queries (top videos by channel).
> 5. **Parallelization**: Extract from multiple channels concurrently using Airflow/Dagster.
>
> The core logic stays the same — just infrastructure changes."

---

### Q: "How would you handle duplicate data?"

**Answer:**
> "I handle this two ways:
>
> 1. **ON CONFLICT DO UPDATE** in SQL: If I re-run ingestion, it won't duplicate. It just updates existing rows.
> 2. **Idempotency**: I run the script twice in production to verify it produces the same output.
>
> If I were streaming data (e.g., comments come in real-time), I'd use a **deduplication layer** — track comment_id in a bloom filter or use Kafka's deduplication window.
>
> At YouTube scale, duplicate detection is critical because if I score the same comment twice, my aggregates are wrong."

---

### Q: "Why is sentiment important for a content creator?"

**Answer:**
> "Because engagement isn't just volume. A video could have 100K views and 10 likes/comments (passive). Or 10K views and 500 comments (engaged). Sentiment tells you *whether* that engagement is positive.
>
> My data shows: videos with avg sentiment 0.55 (most positive quartile) achieve 4.8% VII vs. 3.2% for the most negative quartile — a 49% uplift. So creators should optimize for positive audience emotion, not just clicks.
>
> In product terms: if I'm YouTube, I can use sentiment to surface videos that build community, not just clickbait."

---

### Q: "What did you learn building this?"

**Answer:**
> "Three big lessons:
>
> 1. **API reality**: The YouTube API has edge cases — comments disabled, rate limits, pagination. Production systems need defensive code and exponential backoff. Tutorials don't teach this.
>
> 2. **Schema design matters**: A poorly normalized database makes analytics queries slow and redundant. Spending time upfront on 3NF saves hours debugging later.
>
> 3. **Metrics need context**: Raw numbers (8.4% engagement) mean nothing without a baseline. Window functions (RANK, NTILE) let me compare videos within context — top 5 per channel, not globally. This is what SQL window functions were made for.
>
> It's the kind of project that bridges the gap between 'I know SQL' and 'I can ship production analytics.'"

---

### Q: "What's your weakest area in this project?"

**Answer (be honest):**
> "The Power BI dashboard is incomplete — I have the spec and DAX formulas but haven't finished the UI. In a real project, I'd have done this first for stakeholder feedback. It taught me that analytics isn't just about data; it's about communication.
>
> Also, I didn't implement automated testing or CI/CD. In production, I'd add pytest for ingestion validation and GitHub Actions to re-run the pipeline weekly and alert on failures.
>
> These are things I'm actively learning right now."

---

## Part 5: How to Position This for Different Roles

### If Interviewing for Data Engineer Role:

Focus on:
- Database design (3NF, indexes, foreign keys)
- ETL pipeline (pagination, error handling, batch inserts)
- API integration (exponential backoff, rate limiting)
- Production patterns (ON CONFLICT, idempotency, logging)

**Lead with:** "I designed a 3NF schema that handles edge cases like comments-disabled videos gracefully. I used exponential backoff to manage YouTube API rate limits. The ON CONFLICT logic ensures the pipeline is re-runnable without duplicates."

### If Interviewing for Data Analyst Role:

Focus on:
- Derived metrics (VI, IDR, VVI, engagement rate)
- SQL analytics (window functions, CTEs, quartile analysis)
- Insights (49% virality uplift, Friday 3 PM peak)
- Business impact (evergreen content discovery)

**Lead with:** "I discovered that positive-sentiment videos achieve 49% higher virality. I used NTILE to identify the top-performing content format. Friday at 3 PM is the optimal upload window."

### If Interviewing for Full-Stack Data Role:

Hit all 5 layers equally:
- API extraction (YouTube)
- ETL (PostgreSQL + Python)
- NLP (VADER)
- SQL Analytics (5 queries)
- BI (Power BI + DAX)

**Lead with:** "I built the entire stack from API to dashboard. This shows I can own projects end-to-end — from raw data to business dashboard."

---

## Part 6: Handling Tough Questions

### Q: "Why didn't you use a cloud data warehouse like Redshift?"

**Answer:**
> "Good catch. Redshift would be overkill here — I don't need distributed processing. My data is 20K rows. Redshift shines at terabytes of data with complex joins across many tables. For this project, PostgreSQL on Supabase is simpler and free. If I were working at a company already using Redshift, I'd use it for consistency."

---

### Q: "Your sentiment analysis is too simple — real NLP uses transformers."

**Answer:**
> "You're right that transformers like BERT are more powerful. But they're not always the right tool. VADER is optimized for social media, trained on Twitter/Reddit, which is similar to YouTube comments. It runs in milliseconds with no GPU.
>
> If I needed to detect 'I love this video but it's boring' (sarcasm), I'd use BERT. But for 'is this comment happy or angry?', VADER is 95% accurate and 1000x faster.
>
> It's about picking the right tool for the job, not the most sophisticated one."

---

### Q: "This is just a portfolio project. How does it relate to production?"

**Answer:**
> "Great point. This project embodies production patterns:
>
> 1. **Idempotency**: The pipeline can be re-run without data corruption.
> 2. **Error handling**: It gracefully skips videos with disabled comments.
> 3. **Logging**: Every step logs progress and errors.
> 4. **Testability**: Each module (extraction, sentiment, SQL) is independent and can be tested.
> 5. **Documentation**: README, comments, and schemas explain every decision.
>
> In a real job, I'd add unit tests, CI/CD, monitoring, and alerting. But the fundamentals are all there. This project shows I understand the difference between 'code that works' and 'code that can be maintained.'"

---

## Part 7: After the Interview

**Send a follow-up email:**

> Hi [Interviewer Name],
>
> Thanks for the great conversation about CreatorPulse. I enjoyed discussing how the sentiment analysis revealed the 49% virality uplift — that insight really drives home the business value of combining NLP with analytics.
>
> I wanted to share a couple follow-ups:
> 1. The full code is at [GitHub link]. Feel free to run the extraction yourself — it takes about 2 minutes.
> 2. I'm actively working on [one of the gaps you discussed], which I think would be a great addition.
>
> Looking forward to hearing more. Happy to discuss any technical questions or do a deeper dive into any layer of the stack.
>
> Best,
> [Your name]

---

## TL;DR: The Cheat Sheet

**Elevator Pitch (2 min):**
"I built an end-to-end YouTube analytics platform. Extract → PostgreSQL → VADER sentiment → SQL analytics → Power BI. Key finding: positive sentiment drives 49% higher virality."

**Architecture (3 min):**
YouTube API → Python extraction → PostgreSQL 3NF schema → VADER NLP → 5 SQL queries → Power BI dashboard.

**Why this matters:**
- Shows full-stack data skills
- Demonstrates production patterns
- Leads with business insight (49% uplift)
- Reproducible and extendable

**Demo (5 min):**
Run extraction → show schema → run sentiment → show top SQL results → show Power BI (or spec).

**Common trap:**
Don't get bogged down in the code. Focus on: "What problem does this solve? What did you learn? What would you do differently?"

---

Good luck. You've got this. 🚀
