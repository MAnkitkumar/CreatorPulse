# CreatorPulse — Power BI Dashboard Specification
## Module 5: Executive Dashboard (2-Page Report)

---

## DAX MEASURES
Create these in a dedicated "Measures" table (Home → Enter Data → name it _Measures).

```dax
-- ── Core KPI Measures ────────────────────────────────────────────────────────

Avg Engagement Rate =
ROUND(AVERAGE(videos[engagement_rate]), 2)

Total Views =
SUM(videos[views])

Total Videos =
COUNTROWS(videos)

Avg VVI =
ROUND(AVERAGE(videos[vvi]), 2)

Total Virality Index =
ROUND(SUMX(videos, (videos[likes] + videos[comments_count] * 3) / NULLIF(videos[views], 0) * 100), 2)

Avg IDR =
ROUND(AVERAGE(videos[idr]), 2)

-- ── Sentiment Measures ───────────────────────────────────────────────────────

Avg Sentiment Score =
ROUND(AVERAGE(videos[avg_sentiment]), 4)

Sentiment Ratio =
VAR pos = CALCULATE(COUNTROWS(comments), comments[sentiment_label] = "Positive")
VAR total = CALCULATE(COUNTROWS(comments), comments[sentiment_label] <> BLANK())
RETURN
DIVIDE(pos, total, 0)

Positive Comment % =
FORMAT(DIVIDE(
    CALCULATE(COUNTROWS(comments), comments[sentiment_label] = "Positive"),
    CALCULATE(COUNTROWS(comments), comments[sentiment_label] <> BLANK())
), "0.0%")

-- ── Rolling / Time Intelligence ──────────────────────────────────────────────

Rolling 7-Day View Velocity =
VAR lastDate = MAX(videos[published_at])
VAR startDate = lastDate - 7
RETURN
CALCULATE(
    AVERAGE(videos[vvi]),
    FILTER(videos, videos[published_at] >= startDate && videos[published_at] <= lastDate)
)

Views Per Video =
DIVIDE([Total Views], [Total Videos], 0)

Top Channel by ER =
CALCULATE(
    SELECTEDVALUE(channels[channel_name]),
    TOPN(1, ALL(channels), [Avg Engagement Rate], DESC)
)
```

---

## PAGE 1: Content Performance & Velocity

### Layout (1280 × 720 canvas)

```
┌─────────────────────────────────────────────────────────────────────┐
│  CREATORPULSE                    [Channel ▼] [Duration ▼] [Date ▼]  │
│  Content Performance & Velocity                                      │
├───────────┬───────────┬───────────┬───────────┬─────────────────────┤
│ Total     │ Avg       │ Avg VVI   │ Avg        │ Top Channel        │
│ Videos    │ Eng Rate  │           │ Sentiment  │ by Engagement      │
│ [KPI]     │ [KPI]     │ [KPI]     │ [KPI]      │ [KPI]              │
├───────────┴───────────┴───────────┴────────────┴────────────────────┤
│                                          │                           │
│   Duration Bucket vs Avg Views           │  Upload Timing Heatmap   │
│   (Clustered Bar Chart)                  │  (Matrix: Day × Hour)    │
│   X: duration_bucket                    │  Rows: Day of Week        │
│   Y: Average of views                   │  Cols: Hour of Day        │
│   Color: Avg Engagement Rate            │  Values: Avg Eng Rate     │
│   (gradient: low=blue, high=orange)     │  Color scale: white→red   │
│                                          │                           │
├──────────────────────────────────────────┴───────────────────────────┤
│                                                                       │
│   Video Performance Ranking Matrix (Table)                           │
│   Columns: Channel | Title | Views | Eng Rate | VVI | IDR |          │
│            Avg Sentiment | Duration | Published Date                 │
│   Sort: Eng Rate DESC by default                                     │
│   Conditional formatting on Eng Rate column (data bars, orange)     │
│   Conditional formatting on VVI column (color scale green→red)      │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### Visual Specifications

**KPI Cards (row of 5)**
- Visual: Card
- Fields: [Total Videos], [Avg Engagement Rate], [Avg VVI], [Avg Sentiment Score], [Top Channel by ER]
- Format: Bold title, large value font (28pt), subtle border

**Duration Bucket vs Avg Views (Clustered Bar)**
- Visual: Clustered bar chart
- X-axis: `videos[duration_bucket]` (sort order: Short→Medium→Long→Extended)
- Y-axis: `Average of videos[views]`
- Secondary Y: `[Avg Engagement Rate]` as line (combo chart)
- Legend: duration_bucket
- Colors: Short=teal, Medium=orange, Long=purple, Extended=steel blue

**Upload Timing Heatmap (Matrix)**
- Visual: Matrix
- Rows: `FORMAT(videos[published_at], "dddd")` — Day of week
- Columns: `HOUR(videos[published_at])` — 0–23
- Values: `[Avg Engagement Rate]`
- Conditional formatting: Color scale (white = low, dark red = high)
- Sort rows: Mon→Tue→Wed→Thu→Fri→Sat→Sun

**Video Ranking Matrix (Table)**
- Visual: Table
- Columns: channel_name, title (truncated 40 chars), views, engagement_rate, vvi, idr, avg_sentiment, duration_bucket, published_at
- Conditional formatting:
  - engagement_rate → data bars (orange)
  - avg_sentiment → background color (red → white → green, -1 to +1)
  - vvi → font color (green if > channel avg)

**Slicers**
- Channel Name (dropdown, multi-select)
- Duration Bucket (tile/button style)
- Published Date (date range picker)

---

## PAGE 2: Audience Sentiment & Discussion Depth

### Layout (1280 × 720 canvas)

```
┌─────────────────────────────────────────────────────────────────────┐
│  CREATORPULSE                    [Channel ▼] [Sentiment ▼]          │
│  Audience Sentiment & Discussion Depth                               │
├───────────┬───────────┬───────────┬───────────────────────────────  │
│ Positive  │ Neutral   │ Negative  │  Sentiment                      │
│ Comment % │ Comment % │ Comment % │  Ratio (Pos/Total)              │
│ [KPI]     │ [KPI]     │ [KPI]     │  [KPI]                          │
├───────────┴───────────┴───────────┴─────────────────────────────────┤
│                              │                                        │
│  Sentiment Distribution      │  IDR vs Views Scatter Plot            │
│  (Donut Chart)               │  X: views (log scale)                 │
│  Legend: Pos/Neu/Neg         │  Y: idr                               │
│  Colors:                     │  Size: engagement_rate                │
│   Positive = #2ECC71 green   │  Color: avg_sentiment (red→green)    │
│   Neutral  = #95A5A6 gray    │  Tooltip: title, channel, VII        │
│   Negative = #E74C3C red     │                                       │
│                              │                                        │
├──────────────────────────────┼────────────────────────────────────── │
│                              │                                        │
│  Top Tags Bar Chart          │  Strategy Recommendation Card         │
│  (Horizontal bar)            │  (Text box / Card visual)             │
│  Y: tag                      │                                       │
│  X: COUNT of video_id        │  Content: Auto-text based on slicers  │
│  Top 15 tags only            │  (see DAX below)                      │
│  Color: by frequency rank    │                                       │
│                              │                                        │
└──────────────────────────────┴───────────────────────────────────────┘
```

### Visual Specifications

**Sentiment Donut Chart**
- Visual: Donut chart
- Legend: `comments[sentiment_label]`
- Values: Count of `comments[comment_id]`
- Colors: Positive=#2ECC71, Neutral=#95A5A6, Negative=#E74C3C
- Detail labels: show percentage
- Center label: `[Sentiment Ratio]` measure

**IDR vs Views Scatter Plot**
- Visual: Scatter chart
- X-axis: `videos[views]` — enable log scale
- Y-axis: `videos[idr]`
- Size: `videos[engagement_rate]`
- Color saturation: `videos[avg_sentiment]`
- Play axis: none
- Tooltip fields: title, channel_name, vii, avg_sentiment
- Reference line on Y-axis at IDR=10 (avg baseline) — dotted

**Top Tags Bar Chart**
- Visual: Horizontal bar chart
- Y-axis: `video_tags[tag]`
- X-axis: Count of `video_tags[video_id]`
- Filter: Top N = 15 (using visual-level filter on count DESC)
- Color: single color #3498DB, gradient by rank
- Data labels: on

**Strategy Recommendation Card**
- Visual: Card or multi-row card
- Use this DAX measure for dynamic text:

```dax
Strategy Recommendation =
VAR topDuration =
    CALCULATE(
        SELECTEDVALUE(videos[duration_bucket]),
        TOPN(1, ALL(videos[duration_bucket]),
             CALCULATE(AVERAGE(videos[engagement_rate])), DESC)
    )
VAR topDay =
    CALCULATE(
        SELECTEDVALUE(FORMAT(videos[published_at], "dddd")),
        TOPN(1,
             SUMMARIZE(ALL(videos), FORMAT(videos[published_at], "dddd"), "er", AVERAGE(videos[engagement_rate])),
             [er], DESC)
    )
VAR sentimentScore = [Avg Sentiment Score]
VAR sentLabel =
    IF(sentimentScore >= 0.3, "highly positive",
       IF(sentimentScore >= 0.05, "moderately positive", "mixed or negative"))
RETURN
"Optimal format: " & topDuration &
" videos. Best upload day: " & topDay &
". Audience sentiment is " & sentLabel &
" (score: " & FORMAT(sentimentScore, "0.00") & ")."
```

**Slicers**
- Channel Name (dropdown)
- Sentiment Label (tile: Positive / Neutral / Negative)
- Duration Bucket (dropdown)

---

## REPORT FORMATTING

**Theme colors**
- Background: #1A1A2E (dark navy)
- Card background: #16213E
- Accent: #E94560 (red-orange)
- Text: #EAEAEA
- Positive: #2ECC71
- Negative: #E74C3C
- Neutral: #95A5A6

**Fonts**
- Title: Segoe UI Semibold, 14pt
- KPI values: Segoe UI Bold, 28pt
- Body/labels: Segoe UI, 10pt

**Page navigation**
- Add two buttons at top right of each page
- Button 1: "Performance" → navigates to Page 1
- Button 2: "Sentiment" → navigates to Page 2
- Action type: Page Navigation

---

## PUBLISHING (Optional)
Once built locally:
1. File → Publish → Publish to Power BI
2. Sign in with a Microsoft/work account (free Power BI account works)
3. Share the report link for your portfolio
