# Recap API Documentation

Base URL: `http://127.0.0.1:8000`

All recap endpoints are `POST` requests. They return JSON. On failure they return HTTP `500` with a `detail` field explaining the error.

---

## Endpoints at a Glance

| Method | Endpoint | Time Range | User |
|--------|----------|------------|------|
| POST | `/api/recap/generate` | Yesterday (local time) | Default (`USER_ID` in `.env`) |
| POST | `/api/recap/generate-all` | Since last recap | Default |
| POST | `/api/recap/generate-total` | All available messages | Default |
| POST | `/api/web/recap/generate` | Yesterday (local time) | Provided in body |
| POST | `/api/web/recap/generate-all` | Since last recap | Provided in body |
| POST | `/api/web/recap/generate-total` | All available messages | Provided in body |

---

## What Every Recap Call Does

1. **Fetches messages** from Teams chats + channels for the requested time range
2. **Runs the LangGraph AI agent** to generate a summary and extract action items
3. **Saves state** to `recap_state_{user_id}.json` for next-run continuity
4. **Creates tasks** in Microsoft To Do from the extracted action items
5. **Sends the recap** as an HTML message to the user's 1-on-1 Teams chat
6. **Saves a page** to OneNote (`Teams Recaps` notebook)

---

## Default User Endpoints

> These endpoints use the `USER_ID` defined in your `.env` file. No request body needed.

---

### `POST /api/recap/generate`

Generates a recap for **yesterday** (midnight → 23:59:59 local time).

**Request**
```http
POST /api/recap/generate
Content-Type: application/json
```
*(No body required)*

**Response `200 OK`**
```json
{
  "status": "success",
  "message": "Recap processed successfully.",
  "recap_details": {
    "current_recap": "Yesterday the team discussed the Q1 roadmap...",
    "pending_tasks": [
      "Follow up with design team on mockups",
      "Send weekly report by Friday"
    ]
  },
  "teams_response": { ... }
}
```

**Response `500`**
```json
{ "detail": "Error message explaining what went wrong" }
```

---

### `POST /api/recap/generate-all`

Generates a recap for **all messages since the last recap run**. Falls back to the last 24 hours if no previous recap exists.

**Request**
```http
POST /api/recap/generate-all
Content-Type: application/json
```
*(No body required)*

**Response** — same shape as `/api/recap/generate`

---

### `POST /api/recap/generate-total`

Generates a recap for **all available messages** (no time filter). Useful for a full historical summary.

**Request**
```http
POST /api/recap/generate-total
Content-Type: application/json
```
*(No body required)*

**Response** — same shape as `/api/recap/generate`

> [!WARNING]
> This can be slow for users with large message histories. Run it sparingly.

---

## Web Endpoints (Multi-User)

> These endpoints accept a `user_id` in the request body, enabling per-user recaps from a web frontend. `user_id` is the **Azure AD Object ID** of the target user.

---

### `POST /api/web/recap/generate`

Generates an AI-powered recap of **yesterday's** Microsoft Teams messages for a specific user, then sends the result to their Teams chat, Microsoft To Do, and OneNote.

**Time range:** Yesterday `00:00:00` → `23:59:59` in the **server's local timezone**, then converted to UTC for the Graph API query.

---

#### Request

```http
POST /api/web/recap/generate
Host: 127.0.0.1:8000
Content-Type: application/json
```

**Body**

```json
{
  "user_id": "9be5adb7-370d-44c9-9fc1-c3224d6a80d5"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | `string` | ✅ Yes | Azure AD **Object ID** of the target user. Found in Azure Portal → Users → select user → Object ID. |

> [!NOTE]
> `user_id` must be the **Object ID** (GUID format), not the UPN / email address.

---

#### How It Works (Internal Flow)

```
1. Compute Yesterday's UTC range from server local time
        ↓
2. GET access token via MSAL (app-only) or GRAPH_ACCESS_TOKEN from .env
        ↓
3. Fetch Teams messages (chats + channels) for user_id in time range
        ↓
4. Filter out bot messages ("Lila Jarvis", "Unknown") and recap messages
        ↓
5. Load previous recap from recap_state_{user_id}.json (for context)
        ↓
6. Invoke LangGraph AI agent → generates summary + extracts action items
        ↓
7. Save new recap to recap_state_{user_id}.json
        ↓
8. Create extracted tasks in Microsoft To Do ("Tasks from Teams" list)
        ↓
9. Fetch all pending To Do tasks (merge with AI-extracted)
        ↓
10. Send HTML recap message to user's 1-on-1 Teams chat
        ↓
11. Save recap page to OneNote ("Teams Recaps" → YYYY-MM-DD section)
```

---

#### Response `200 OK`

```json
{
  "status": "success",
  "message": "Recap processed successfully.",
  "recap_details": {
    "current_recap": "Yesterday the team discussed the Q1 roadmap. Alice proposed moving the release date to March 15th. Bob was assigned to finalize the budget report.",
    "pending_tasks": [
      "Finalize budget report - Bob",
      "Follow up with design on mockups",
      "Send weekly status update by Friday"
    ]
  },
  "teams_response": {
    "id": "1234567890",
    "createdDateTime": "2026-02-27T07:00:00Z",
    "body": {
      "contentType": "html",
      "content": "<h3>Recap</h3><p>...</p>"
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | Always `"success"` on HTTP 200 |
| `message` | `string` | Human-readable confirmation |
| `recap_details.current_recap` | `string` | AI-generated summary of yesterday's conversations |
| `recap_details.pending_tasks` | `string[]` | Merged list of AI-extracted tasks + existing To Do items |
| `teams_response` | `object` | Raw Graph API response from sending the Teams message |

---

#### Error Responses

| HTTP Status | When It Happens | `detail` Example |
|-------------|-----------------|------------------|
| `422 Unprocessable Entity` | `user_id` is missing or not a string | `"field required"` |
| `500 Internal Server Error` | Graph API auth failure | `"[MSAL] Failed to acquire token: ..."` |
| `500 Internal Server Error` | Graph API permissions missing | `"Forbidden: Missing role permissions..."` |
| `500 Internal Server Error` | AI agent error | `"Error invoking LangGraph agent: ..."` |

**Error body shape:**
```json
{ "detail": "string describing the error" }
```

---

#### Side Effects

| System | What Happens |
|--------|-------------|
| **State file** | `recap_state_{user_id}.json` is created/updated with the new recap and timestamp |
| **Microsoft To Do** | New tasks are created in the `"Tasks from Teams"` list |
| **Teams Chat** | An HTML-formatted recap is sent to the user's 1-on-1 chat |
| **OneNote** | A page is added to `"Teams Recaps"` notebook under today's `YYYY-MM-DD` section |

> [!NOTE]
> To Do and OneNote failures are caught silently — the endpoint returns `200` even if those steps fail. Only Teams message send failure will cause a `500`.

---

#### Example — curl

```bash
curl -X POST http://127.0.0.1:8000/api/web/recap/generate \
  -H "Content-Type: application/json" \
  -d '{"user_id": "9be5adb7-370d-44c9-9fc1-c3224d6a80d5"}'
```

#### Example — JavaScript (fetch)

```javascript
const response = await fetch("http://127.0.0.1:8000/api/web/recap/generate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ user_id: "9be5adb7-370d-44c9-9fc1-c3224d6a80d5" })
});

const data = await response.json();
console.log(data.recap_details.current_recap);
console.log(data.recap_details.pending_tasks);
```

#### Example — Python (requests)

```python
import requests

resp = requests.post(
    "http://127.0.0.1:8000/api/web/recap/generate",
    json={"user_id": "9be5adb7-370d-44c9-9fc1-c3224d6a80d5"}
)
resp.raise_for_status()
data = resp.json()
print(data["recap_details"]["current_recap"])
```

---

#### Required Azure AD Permissions

The app must have these **Application permissions** granted (with admin consent) for this endpoint to succeed:

| Permission | Used For |
|-----------|----------|
| `Chat.Read.All` | Fetch user's chats |
| `Chat.ReadWrite.All` | Send recap message to Teams chat |
| `ChannelMessage.Read.All` | Fetch team/channel messages |
| `Team.ReadBasic.All` | List user's joined teams |
| `Tasks.ReadWrite.All` | Create/read Microsoft To Do tasks |
| `Notes.ReadWrite.All` | Create OneNote pages |

---

### `POST /api/web/recap/generate-all`

Generates a recap **since the last recap** for a specific user.

**Request**
```http
POST /api/web/recap/generate-all
Content-Type: application/json

{
  "user_id": "9be5adb7-370d-44c9-9fc1-c3224d6a80d5"
}
```

**Response** — same shape as `/api/recap/generate`

---

### `POST /api/web/recap/generate-total`

Generates a **full historical recap** for a specific user.

**Request**
```http
POST /api/web/recap/generate-total
Content-Type: application/json

{
  "user_id": "9be5adb7-370d-44c9-9fc1-c3224d6a80d5"
}
```

**Response** — same shape as `/api/recap/generate`

> [!WARNING]
> This can be slow for users with large message histories. Run it sparingly.

---

## Response Schema

```json
{
  "status": "string",           // always "success" on 200
  "message": "string",          // human-readable status
  "recap_details": {
    "current_recap": "string",  // AI-generated summary paragraph
    "pending_tasks": ["string"] // extracted + existing To-Do tasks
  },
  "teams_response": {}          // raw Graph API response from sending the Teams message
}
```

---

## Side Effects Summary

| Action | Where |
|--------|-------|
| Saves recap state | `recap_state.json` / `recap_state_{user_id}.json` |
| Creates tasks | Microsoft To Do → "Tasks from Teams" list |
| Sends chat message | User's 1-on-1 Teams chat |
| Creates note page | OneNote → "Teams Recaps" notebook → `YYYY-MM-DD` section |

---

## Scheduler

`POST /api/recap/generate` also runs automatically every day at **09:00 AM** (server local time), configured via the `schedule` library on startup.

To change the time, update this line in `main.py`:
```python
schedule.every().day.at("09:00").do(perform_daily_recap)
```

---

## Quick Test (curl)

```bash
# Default user — yesterday's recap
curl -X POST http://127.0.0.1:8000/api/recap/generate

# Specific user — yesterday's recap
curl -X POST http://127.0.0.1:8000/api/web/recap/generate \
  -H "Content-Type: application/json" \
  -d '{"user_id": "9be5adb7-370d-44c9-9fc1-c3224d6a80d5"}'
```
