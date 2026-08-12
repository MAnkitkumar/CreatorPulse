# CreatorPulse: YouTube Content Strategy & Engagement Analytics Engine

**An industry-grade end-to-end data engineering & business intelligence project**

---

## 📊 Executive Overview

CreatorPulse is a production-ready analytics platform that extracts public YouTube data, enriches it with NLP sentiment analysis, and delivers actionable insights via SQL analytics + Power BI dashboards. Built to help content creators and agencies optimize upload strategy, identify viral patterns, and quantify audience engagement depth.

**Dataset**: 4 channels, 400 videos, 19,737 comments, 6 months of historical data  
**Stack**: Python (YouTube API v3, VADER NLP) → PostgreSQL (Supabase) → SQL Analytics → Power BI  
**Key Insight**: 68.6% positive sentiment correlates strongly with 4.8% higher virality index  

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    CREATORPULSE PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MODULE 1: DATA EXTRACTION                                       │
│  ┌──────────────────────────────────────┐                       │
│  │ YouTube Data API v3                  │                       │
│  │ • Channel stats (subscribers, views) │                       │
│  │ • 400 videos (metadata + KPIs)       │                       │
│  │ • 19.7K comments (top 200/video)     │                       │
│  │ • Exponential backoff + pagination   │                       │
│  └──────────────────────────────────────┘                       │
│              ↓ pandas DataFrames                                 │
│                                                                  │
│  MODULE 2: ETL & RELATIONAL DATABASE                             │
│  ┌──────────────────────────────────────┐                       │
│  │ PostgreSQL (Supabase - Session Pool) │                       │
│  │ • channels (4 rows)                  │                       │
│  │ • videos (400 rows) w/ 4 KPIs        │                       │
│  │ • comments (19.7K rows)              │                       │
│  │ • video_tags (4.2K rows) normalized  │                       │
│  │ Indexes on: channel_id, published_at │                       │
│  └──────────────────────────────────────┘                       │
│              ↓ psycopg2 execute_values                           │
│                                                                  │
│  MODULE 3: NLP SENTIMENT ANALYSIS                                │
│  ┌──────────────────────────────────────┐                       │
│  │ VADER SentimentIntensityAnalyzer     │                       │
│  │ • Compound scores (-1 to +1)         │                       │
│  │ • Labels: Positive/Neutral/Negative  │                       │
│  │ • Per-video avg aggregation          │                       │
│  │ Result: 395 videos scored, 68.6% pos │                       │
│  └──────────────────────────────────────┘                       │
│              ↓ batch UPDATE statements                           │
│                                                                  │
│  MODULE 4: ANALYTICS LAYER                                       │
│  ┌──────────────────────────────────────┐                       │
│  │ Production SQL Queries                │                       │
│  │ • Channel performance ranking (CTE)  │                       │
│  │ • Duration matrix optimization       │                       │
│  │ • Sentiment quartiles vs virality    │                       │
│  │ • Publishing window heatmap (NTILE)  │                       │
│  │ • Content lifecycle decay analysis   │                       │
│  └──────────────────────────────────────┘                       │
│              ↓ CSV export                                        │
│                                                                  │
│  MODULE 5: BUSINESS INTELLIGENCE                                 │
│  ┌──────────────────────────────────────┐                       │
│  │ Power BI Executive Dashboard          │                       │
│  │ • Page 1: Performance & Velocity      │                       │
│  │ • Page 2: Sentiment & Discussion      │                       │
│  │ • 6 DAX measures, 2 matrix visuals    │                       │
│  │ • Dynamic strategy recommendations   │                       │
│  └──────────────────────────────────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
creatorpulse/
├── config.py                 # API keys, channel IDs, DB URL
├── extractor.py              # Module 1 — YouTube API pipeline
├── db_schema.sql             # Module 2 — DDL (4 tables, 3NF)
├── ingestion.py              # Module 2 — ETL to Supabase
├── sentiment.py              # Module 3 — VADER sentiment scoring
├── analytics.sql             # Module 4 — 5 production queries
├── export_csv.py             # Export to Power BI
├── powerbi_spec.md           # Module 5 — Dashboard specs + DAX
├── requirements.txt          # Dependencies
├── .env                       # Credentials (git-ignored)
└── data/                      # Exported CSVs for Power BI
    ├── channels.csv
    ├── videos.csv
    ├── comments.csv
    └── video_tags.csv
```

---

## 🔑 Core Derived Metrics & KPIs

All metrics computed at extraction time and/or SQL layer:

| KPI | Formula | Use Case |
|-----|---------|----------|
| **Engagement Rate (%)** | `((likes + comments) / views) * 100` | Measures active audience interaction |
| **Interaction Depth Ratio (IDR %)** | `(comments / likes) * 100` | Flags high-intent discussion vs passive likes |
| **Virality & Intent Index (VII)** | `((likes + comments×3) / views) * 100` | Weights comment activity 3x (higher intent) |
| **View Velocity Index (VVI)** | `views / days_since_upload` | Quantifies post-upload momentum; detects evergreen content |
| **Sentiment Score (VADER)** | Compound score (-1 to +1) | Audience emotion; aggregated to video level |
| **Duration Bucket** | Short (<3m), Medium (3-10m), Long (10-20m), Extended (>20m) | Content format optimization |

**Key Finding**: Videos in Q1 sentiment quartile (most positive, avg 0.55) achieve 4.80% VII vs Q4 (0.13) at 3.22% — confirming happy audiences drive virality.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL (Supabase free tier recommended)
- YouTube Data API v3 key
- Power BI Desktop (optional, for visualization)

### Installation

```bash
pip install -r requirements.txt
```

### Environment Setup

Copy `.env.example` → `.env` and fill in:
```
YOUTUBE_API_KEY=your_api_key_here
DATABASE_URL=postgresql://user:password@host:5432/postgres
```

### Run the Pipeline

```bash
# Module 1: Extract YouTube data
python extractor.py

# Module 2: Load into PostgreSQL
python ingestion.py

# Module 3: Score sentiment
python sentiment.py

# Module 4: Export for BI
python export_csv.py
```

All data is now live in Supabase and ready for Power BI import.

---

## 📊 Analytics Queries (Module 4)

Five production-grade SQL queries included:

### Q1: Channel Performance Benchmarking
Ranks videos within each channel by Engagement Rate and VVI using window functions.  
**Use**: Identify top/bottom performers per creator.

### Q2: Content Duration Matrix
Compares avg Views, Engagement Rate, and IDR across duration buckets.  
**Key Finding**: Short videos win engagement (4.78%) but Medium drives volume (57.7k avg views).

### Q3: Sentiment Quartile vs Performance
Groups videos into 4 sentiment quartiles; compares VII and engagement.  
**Use**: Validate sentiment-to-virality correlation.

### Q4: Optimal Publishing Window
Extracts day-of-week + hour-of-day to find peak engagement windows.  
**Key Finding**: Friday 3 PM and Thursday 4 PM are top upload slots.

### Q5: Content Lifecycle Decay Analysis
Compares each video's VVI against channel baseline; classifies as Evergreen/Viral/Decaying.  
**Key Finding**: Luke Barousse's Excel course (667 days old) still pulls 4,980 views/day — textbook evergreen.

---

## 📈 Power BI Dashboard (Module 5)

**Page 1: Content Performance & Velocity**
- 5 KPI cards (Total Videos, Avg ER, Avg VVI, etc.)
- Duration bucket vs avg views (combo chart)
- Upload timing heatmap (matrix: day × hour)
- Video ranking table with conditional formatting

**Page 2: Audience Sentiment & Discussion Depth**
- Sentiment distribution donut (Pos/Neu/Neg breakdown)
- IDR vs Views scatter (bubble size = engagement rate)
- Top 15 tags bar chart
- Dynamic strategy recommendation card (DAX formula)

**DAX Measures**:
- `Avg Engagement Rate`, `Total Views`, `Total Videos`
- `Avg VVI`, `Avg Sentiment Score`, `Sentiment Ratio`
- `Rolling 7-Day View Velocity` (time intelligence)
- `Strategy Recommendation` (narrative generation)

---

## 💡 Key Insights

1. **Sentiment Matters**: Positive comment sections correlate with 4.8% higher virality — a 49% uplift vs negative quartile.
2. **Duration Sweet Spot**: Medium videos (3-10 min) drive the most views; short videos win engagement rate.
3. **Evergreen Gold**: Full-course videos (Excel, Power BI) sustain 2,900+ views/day 400+ days post-upload.
4. **Optimal Timing**: Friday 3–4 PM is the golden window across all 4 channels.
5. **Discussion Depth**: IDR varies 0–25%; high-IDR videos attract serious learners, not casual viewers.

---

## 🔧 Tech Stack Breakdown

| Layer | Technology | Why |
|-------|-----------|-----|
| **Data Extraction** | YouTube Data API v3 + Python | Official, rate-limit aware, exponential backoff |
| **Database** | PostgreSQL (Supabase) | Relational, 3NF normalization, session pooler for reliability |
| **ETL** | SQLAlchemy + psycopg2 | Type-safe, batch execute_values for 19K+ row throughput |
| **NLP** | NLTK VADER | Domain-optimized for social media, no GPU required |
| **Analytics** | PostgreSQL SQL | CTEs, window functions (RANK, NTILE), aggregate binning |
| **BI** | Power BI Desktop | DAX measures, dynamic narrative, publishable to cloud |

---

## 📋 Data Quality & Validation

- **Pagination**: Handled YouTube API's 50-item page limit via `nextPageToken` loops
- **Rate Limits**: Exponential backoff (1–16s) on HTTP 403/429/500/503
- **Comments Disabled**: Gracefully skipped (2 videos) without data loss
- **Sentiment Coverage**: 395 of 400 videos scored (98.75%) — 5 had <1 comment
- **Duplicates**: ON CONFLICT DO UPDATE prevents re-ingestion on re-runs
- **Nulls**: Handled via COALESCE (duration parsing), DIVIDE (division by zero), NULLIF (baseline calc)

---

## 🎯 Portfolio Highlights

✅ **End-to-End Pipeline**: Extract → Transform → Load → Analyze → Visualize  
✅ **Production SQL**: CTEs, window functions, aggregate binning, NTILE quartiling  
✅ **NLP Integration**: VADER sentiment with per-video aggregation  
✅ **Database Design**: 3NF schema, foreign keys, composite PKs (video_tags), indexes on cardinality  
✅ **API Mastery**: Pagination, quota management, error handling (commentsDisabled edge case)  
✅ **Business Metrics**: 6 derived KPIs with business justification  
✅ **DAX Measures**: Dynamic text generation for strategy cards  
✅ **Reproducibility**: `.env` config, modular scripts, full documentation

---

## 🤝 Contributing & Extension Ideas

- Add **real-time streaming** via Kafka + Delta Lake
- Integrate **competitor benchmarking** (multi-channel comparison)
- Build **recommendation engine** (content clustering, next-video suggestions)
- Deploy as **FastAPI microservice** with Swagger docs
- Add **monthly email digest** with anomaly detection

---

## 📄 License

MIT — Use freely for portfolio/commercial projects.

---

## 👤 Author

Built as an industry-grade portfolio project targeting Data Analyst & Data Engineer roles.

**Contact**: [Your Email] | [Your GitHub]

---

## 🔗 Resources

- [YouTube Data API Docs](https://developers.google.com/youtube/v3)
- [Supabase PostgreSQL Guide](https://supabase.com/docs/guides/database)
- [VADER Sentiment Analysis](https://github.com/cjhutto/vaderSentiment)
- [Power BI DAX Functions](https://dax.guide/)
- [SQL Window Functions](https://www.postgresql.org/docs/current/functions-window.html)
