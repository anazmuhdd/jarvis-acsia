# Teams Recap Assistant

The Teams Recap Assistant is a FastAPI-based application that leverages Microsoft Graph API and AI (via NVIDIA-hosted Llama models and LangGraph) to periodically summarize Microsoft Teams chat history and extract actionable tasks.

## 🚀 Features

- **Automated Daily Recaps**: Scheduled summarization of yesterday's activity sent directly to your Teams chat.
- **On-Demand Recaps**:
    - `Yesterday`: Recap of the previous day's activity.
    - `Generate All`: Recap of all messages since the last successful execution.
    - `Generate Total`: Full history recap ignoring all time filters.
- **Dynamic User Support**: Web endpoints allow specifying any `user_id` for on-the-fly recap generation with per-user state isolation.
- **AI-Powered Task Extraction**: Intelligent identification of tasks, action items, and reminders from chat logs.
- **External Integrations**:
    - **Microsoft To Do**: Extracted tasks are automatically created in a dedicated "Tasks from Teams" list.
    - **OneNote**: Summaries are archived into a "Teams Recaps" notebook.
- **Mock Mode**: Local testing capability without requiring production API credentials.

## 🛠️ Setup

### Prerequisites
- Python 3.10+
- Microsoft Azure AD Application (with `Chat.Read`, `Tasks.ReadWrite`, `Notes.ReadWrite.All`, etc. permissions)
- NVIDIA AI API Key

### Installation
1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables in a `.env` file (see Configuration section).

### Configuration
Create a `.env` file with the following keys:
```env
# Microsoft Graph API
TENANT_ID=your_tenant_id
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
USER_ID=default_user_id
USER_NAME=Your Name (for personal to-do context)

# NVIDIA AI API
NVIDIA_API_KEY=your_nvidia_api_key

# Optional
MOCK_MODE=false # Set to true to use mock data
RECAP_TIME="09:00" # Daily schedule time
```

## 📡 API Reference

### Default Endpoints (Uses `.env` USER_ID)
- `POST /api/recap/generate`: Generates recap for yesterday.
- `POST /api/recap/generate-all`: Generates recap since the last run.
- `POST /api/recap/generate-total`: Generates recap for all history.
- `GET /api/messages`: Diagnostic view of yesterday's messages.

### Web Endpoints (Dynamic User Support)
Expected JSON Payload: `{ "user_id": "..." }`
- `POST /api/web/recap/generate`: Yesterday's recap for the given user.
- `POST /api/web/recap/generate-all`: Recap since last run for the given user.
- `POST /api/web/recap/generate-total`: Full history recap for the given user.

## 🧠 System Architecture

The application uses **LangGraph** to manage the recap logic:
1. **Fetch**: Retrieves messages from Teams via Microsoft Graph.
2. **Refine**: Filters out bot messages and system notifications.
3. **Analyze**: passes context and messages to a Llama-3.1-70B model with a specialized prompt for summarization and task extraction.
4. **Distribute**: Results are sent to Teams Chat, archived in OneNote, and tasks are pushed to Microsoft To Do.

## 🧪 Testing

Use `MOCK_MODE=true` in `.env` to test the pipeline with pre-defined chat data in `mock_chat_data.json` without hitting live Microsoft APIs.