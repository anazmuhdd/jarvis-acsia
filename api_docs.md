# Pulse AI - Intelligence Backend

Pulse AI is a high-performance intelligence backend that generates role-specific search queries and aggregates professional news articles. Use this backend to keep professionals at the cutting edge of their industry.

## Technology Stack

- **Framework**: FastAPI
- **LLM Integration**: Ollama (via OpenAI Python Client)
- **News Source**: Google News (RSS)
- **Scraping**: BeautifulSoup4 & httpx

---

## API Reference

### 1. News Articles Aggregator

`GET /api/news`

Fetches the top 5 most recent articles for multiple search queries.

**Query Parameters:**
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `q` | `string` | Yes | Comma-separated search queries. |
| `role` | `string` | No | Professional role for context enrichment. |

**Response Schema:**

```typescript
interface NewsResponse {
  articles: Article[];
}

interface Article {
  title: string;
  description: string;
  url: string;
  urlToImage: string | null; // Null if no high-quality image found
  source: {
    name: string;
  };
  publishedAt: string; // Format: "Wed, 25 Feb 2026 14:00:00 GMT"
}
```

---

### 2. Search Query Generator

`POST /api/generate-topics`

Uses AI to generate 5 high-quality, trend-focused search queries based on a user profile.

**Request Body Schema:**

```typescript
interface ProfileRequest {
  role: string;
  department: string;
  teams: string[];
}
```

**Response Schema:**

```typescript
interface TopicsResponse {
  queries: string[];
}
```

---

## Operational Details

### Image Handling

The backend attempts to scrape the best possible image from the source article. If it fails or encounters a meta-redirect, the `urlToImage` field returns `null`. The frontend should skip image rendering or use a local placeholder when `null` is received.

### News Aggregation Logic

1.  **Parallel Fetching**: Each query in `q` is fetched concurrently.
2.  **Recency First**: Articles are sorted by date, and only the top 5 per query are selected.
3.  **Deduplication**: Results are aggregated and deduplicated by URL.
4.  **Final Sort**: The entire collection is sorted chronologically (latest first).

---

## Setup & Running

1.  **Environment Setup**:
    Ensure your `.env` file contains the correct Ollama configuration:

    ```env
    OLLAMA_HOST=http://localhost:11434
    OLLAMA_MODEL=qwen3:14b
    ```

2.  **Start Server**:

    ```bash
    python3 main.py
    ```

3.  **Verification**:
    Use the provided test scripts:
    ```bash
    python3 test_multi_query.py   # Tests news aggregation
    python3 test_query_gen.py     # Tests AI query generation
    ```
