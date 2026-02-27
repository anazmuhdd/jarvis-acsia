import time
import json
import os
import threading
import schedule
from datetime import datetime
from pydantic import BaseModel

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse

from dotenv import load_dotenv

load_dotenv()

from teams_client import (
    get_access_token,
    get_all_messages,
    create_or_get_direct_chat,
    send_message_to_user_chat,
    create_or_get_todo_list,
    create_todo_task,
    get_todo_lists,
    get_tasks_for_list,
    create_or_get_onenote_notebook,
    create_onenote_section,
    create_onenote_page,
)
from datetime import timedelta, timezone
from recap_agent import build_graph

# The state file will store our previous recap for the next day's context
STATE_FILE = "recap_state.json"

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Teams Recap Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helper Models & Functions ---

class RunRecapResponse(BaseModel):
    message: str

class RecapResult(BaseModel):
    current_recap: str
    pending_tasks: list[str]

class TestMessageRequest(BaseModel):
    message_html: str


def get_state_file(user_id: str) -> str:
    """Returns the path to the state file for a specific user."""
    return f"recap_state_{user_id}.json"

def load_previous_recap(user_id: str = None) -> dict:
    state_file = get_state_file(user_id) if user_id else STATE_FILE
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
                return {
                    "previous_recap": data.get("previous_recap", ""),
                    "last_recap_at": data.get("last_recap_at", None)
                }
        except json.JSONDecodeError:
            return {"previous_recap": "", "last_recap_at": None}
    return {"previous_recap": "", "last_recap_at": None}

def save_current_recap(recap: str, last_recap_at: str = None, user_id: str = None):
    state_file = get_state_file(user_id) if user_id else STATE_FILE
    data = {"previous_recap": recap}
    if last_recap_at:
        data["last_recap_at"] = last_recap_at
    else:
        # Default to now if not provided
        data["last_recap_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
    with open(state_file, "w") as f:
        json.dump(data, f)

# --- Web Recap Cache (per-user, per-day) ---

def _web_cache_file(user_id: str) -> str:
    return f"web_recap_cache_{user_id}.json"

def load_web_recap_cache(user_id: str, date_str: str) -> dict | None:
    """Returns cached recap_details if a recap for `date_str` already exists, else None."""
    cache_file = _web_cache_file(user_id)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            if data.get("date") == date_str:
                return data.get("recap_details")
        except (json.JSONDecodeError, KeyError):
            pass
    return None

def save_web_recap_cache(user_id: str, date_str: str, recap_details: dict):
    """Persists the recap for `date_str` so subsequent calls return it immediately."""
    cache_file = _web_cache_file(user_id)
    with open(cache_file, "w") as f:
        json.dump({"date": date_str, "recap_details": recap_details}, f)

def perform_daily_recap() -> None:
    """The core daily recap workflow (can be run in the background)."""
    print(f"[{datetime.now()}] Starting daily recap workflow...")
    try:
        # Calculate Yesterday's range in LOCAL time, then convert to UTC for API
        now_local = datetime.now().astimezone()
        yesterday_local = now_local - timedelta(days=1)
        
        start_local = yesterday_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = yesterday_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        
        print(f"[{datetime.now()}] Local Yesterday: {start_local} to {end_local}")
        print(f"[{datetime.now()}] Fetching messages (UTC): {start_utc} to {end_utc}...")

        # 1. Fetch token and messages
        token = get_access_token()
        messages = get_all_messages(token, start_time=start_utc, end_time=end_utc)
        
        # Filter out bot messages and system messages
        filtered_messages = [
            m for m in messages 
            if m["sender"] not in ["Lila Jarvis", "Unknown"] 
            and "Daily Recap" not in m["content"]
        ]
        
        # 2. Get previous recap from state file
        state = load_previous_recap()
        previous_recap = state["previous_recap"]
        
        # 3. Initialize and invoke LangGraph Agent
        graph = build_graph()
        result = graph.invoke({
            "messages": filtered_messages,
            "previous_recap": previous_recap,
            "current_recap": "",
            "pending_tasks": []
        })
        
        current_recap = result["current_recap"]
        ai_extracted_tasks = result["pending_tasks"]
        
        # 4. Save state for tomorrow
        save_current_recap(current_recap, last_recap_at=end_utc.isoformat().replace("+00:00", "Z"))
        
        # 5. Add AI Extracted Tasks to Microsoft To Do
        todo_list_id = create_or_get_todo_list(token)
        if ai_extracted_tasks:
            for task_title in ai_extracted_tasks:
                try:
                    create_todo_task(token, todo_list_id, task_title)
                    print(f"[{datetime.now()}] Task created in To-Do: {task_title}")
                except Exception as task_err:
                    print(f"[{datetime.now()}] Error creating task '{task_title}': {task_err}")
        
        # 6. Fetch ALL pending tasks from the To-Do list to provide a fresh view
        final_pending_tasks = list(ai_extracted_tasks)
        try:
            actual_tasks = get_tasks_for_list(token, todo_list_id)
            fetched_tasks = [t["title"] for t in actual_tasks]
            
            # Merge and deduplicate (preserving order of new tasks)
            for t in fetched_tasks:
                if t not in final_pending_tasks:
                    final_pending_tasks.append(t)
            print(f"[{datetime.now()}] Successfully fetched {len(fetched_tasks)} tasks from To-Do.")
        except Exception as fetch_err:
            print(f"[{datetime.now()}] Error fetching tasks from To-Do: {fetch_err}")

        # 7. Format message for Teams Chat using HTML
        tasks_html = "".join([f"<li>{task}</li>" for task in final_pending_tasks])
        if not tasks_html:
            tasks_html = "<li>No pending tasks in your To-Do list.</li>"
            
        message_html = f"<h3>Daily Recap</h3><p>{current_recap}</p><h3>Your To-Do List</h3><ul>{tasks_html}</ul>"
        
        # 8. Get Chat ID and Send message
        chat_id = create_or_get_direct_chat(token)
        send_message_to_user_chat(token, chat_id, message_html)
        
        # 9. Send Recap to OneNote
        try:
            current_date_str = datetime.now().strftime("%Y-%m-%d")
            notebook_id = create_or_get_onenote_notebook(token, "Teams Recaps")
            section_id = create_onenote_section(token, notebook_id, current_date_str)
            create_onenote_page(token, section_id, message_html, title=f"Recap for {current_date_str}")
            print(f"[{datetime.now()}] Recap pushed to OneNote successfully.")
        except Exception as onenote_err:
            print(f"[{datetime.now()}] Error pushing to OneNote: {onenote_err}")
            
        print(f"[{datetime.now()}] Daily recap sent successfully.")

    except Exception as e:
        print(f"[{datetime.now()}] Error during daily recap: {e}")

# --- Scheduler Setup ---

def run_scheduler():
    """Continuously check for scheduled tasks in a background thread."""
    print(f"[{datetime.now()}] Background scheduler started.")
    while True:
        schedule.run_pending()
        time.sleep(60) # Check every minute

# Schedule the recap for 9:00 AM daily
schedule.every().day.at("09:00").do(perform_daily_recap)

@app.on_event("startup")
def startup_event():
    """Start the background scheduler thread on app startup."""
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Teams Recap Assistant API is running"}

@app.get("/api/token")
def auth_token():
    """Verify that we can obtain an access token internally."""
    try:
        token = get_access_token()
        return {"status": "success", "token_prefix": token[:10] + "..." if token else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/messages")
def check_messages():
    """Fetch messages for YESTERDAY (Local Time) without running the AI recap."""
    try:
        # Calculate Yesterday's range in LOCAL time
        now_local = datetime.now().astimezone()
        yesterday_local = now_local - timedelta(days=1)
        
        start_local = yesterday_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = yesterday_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)

        token = get_access_token()
        messages = get_all_messages(token, start_time=start_utc, end_time=end_utc)
        
        # Filter out bot messages for a cleaner diagnostic view
        filtered = [
            m for m in messages 
            if m["sender"] not in ["Lila Jarvis", "Unknown"] 
            and "Daily Recap" not in m["content"]
        ]
        
        return {
            "count": len(filtered), 
            "messages": filtered, 
            "raw_count": len(messages),
            "date_range_local": {"start": start_local, "end": end_local},
            "date_range_utc": {"start": start_utc, "end": end_utc}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def get_or_create_chat():
    """Retrieve or create the 1-on-1 Teams chat ID for the configured user."""
    try:
        token = get_access_token()
        chat_id = create_or_get_direct_chat(token)
        return {"chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send-message")
def send_test_message(req: TestMessageRequest):
    """Sends a formatted HTML message to the user test chat."""
    try:
        token = get_access_token()
        chat_id = create_or_get_direct_chat(token)
        resp = send_message_to_user_chat(token, chat_id, req.message_html)
        return {"status": "success", "response": resp}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recap/generate")
def generate_and_send_recap():
    """Run the AI Recap generation flow AND send the results via Teams for YESTERDAY (Local Time) for DEFAULT USER."""
    return run_recap_flow_internal(None, yesterday_only=True)

def run_recap_flow_internal(user_id: str = None, start_time: datetime = None, end_time: datetime = None, yesterday_only: bool = False, send_to_teams: bool = True, update_todo: bool = True):
    """Internal helper to run the recap flow for any user and any time range."""
    try:
        # 1. Determine time range if not provided
        if yesterday_only:
            now_local = datetime.now().astimezone()
            yesterday_local = now_local - timedelta(days=1)
            start_local = yesterday_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end_local = yesterday_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            start_utc = start_local.astimezone(timezone.utc)
            end_utc = end_local.astimezone(timezone.utc)
        else:
            start_utc = start_time
            end_utc = end_time or datetime.now(timezone.utc)

        # 2. Fetch token and messages
        token = get_access_token()
        messages = get_all_messages(token, start_time=start_utc, end_time=end_utc, user_id=user_id)
        
        filtered_messages = [
            m for m in messages 
            if m["sender"] not in ["Lila Jarvis", "Unknown"] 
            and "Daily Recap" not in m["content"]
        ]
        
        # 3. Load state
        state = load_previous_recap(user_id)
        previous_recap = state["previous_recap"]
        
        # 4. Invoke Agent
        graph = build_graph()
        result = graph.invoke({
            "messages": filtered_messages,
            "previous_recap": previous_recap,
            "current_recap": "",
            "pending_tasks": []
        })
        
        current_recap = result["current_recap"]
        ai_extracted_tasks = result["pending_tasks"]
        
        # 5. Save state
        save_current_recap(current_recap, last_recap_at=end_utc.isoformat().replace("+00:00", "Z"), user_id=user_id)
        
        # 6. Integrations
        final_pending_tasks = list(ai_extracted_tasks)
        if update_todo:
            todo_list_id = create_or_get_todo_list(token, user_id=user_id)
            for task_title in ai_extracted_tasks:
                try:
                    create_todo_task(token, todo_list_id, task_title, user_id=user_id)
                except Exception: pass

            try:
                actual_tasks = get_tasks_for_list(token, todo_list_id, user_id=user_id)
                fetched_tasks = [t["title"] for t in actual_tasks]
                for t in fetched_tasks:
                    if t not in final_pending_tasks:
                        final_pending_tasks.append(t)
            except Exception: pass

        tasks_html = "".join([f"<li>{task}</li>" for task in final_pending_tasks])
        if not tasks_html: tasks_html = "<li>No pending tasks.</li>"
        message_html = f"<h3>Recap</h3><p>{current_recap}</p><h3>To-Do List</h3><ul>{tasks_html}</ul>"
        
        send_resp = None
        if send_to_teams:
            chat_id = create_or_get_direct_chat(token, user_id=user_id)
            send_resp = send_message_to_user_chat(token, chat_id, message_html)

            # OneNote
            current_date_str = datetime.now().strftime("%Y-%m-%d")
            try:
                notebook_id = create_or_get_onenote_notebook(token, "Teams Recaps", user_id=user_id)
                section_id = create_onenote_section(token, notebook_id, current_date_str, user_id=user_id)
                create_onenote_page(token, section_id, message_html, title=f"Recap for {current_date_str}", user_id=user_id)
            except Exception: pass

        return {
            "status": "success",
            "message": "Recap processed successfully.",
            "recap_details": {
                "current_recap": current_recap,
                "pending_tasks": final_pending_tasks
            },
            "teams_response": send_resp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recap/generate-all")
def generate_all_recap():
    """Run recap for all messages since the last successful recap execution for DEFAULT USER."""
    state = load_previous_recap(None)
    last_recap_at_str = state["last_recap_at"]
    now_utc = datetime.now(timezone.utc)
    if last_recap_at_str:
        start_utc = datetime.fromisoformat(last_recap_at_str.replace("Z", "+00:00"))
    else:
        start_utc = now_utc - timedelta(days=1)
    
    return run_recap_flow_internal(None, start_time=start_utc, end_time=now_utc)

@app.post("/api/recap/generate-total")
def generate_total_recap():
    """Run recap for ALL available messages for DEFAULT USER."""
    return run_recap_flow_internal(None, start_time=None, end_time=None)

# --- Web Endpoints (Accept user_id in payload) ---

class WebRecapRequest(BaseModel):
    user_id: str

@app.post("/api/web/recap/generate")
def web_generate_recap(req: WebRecapRequest):
    # Yesterday's local date is the cache key (one recap per user per day)
    yesterday_date = (datetime.now().astimezone() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Return instantly if a recap for this user+date was already generated
    cached = load_web_recap_cache(req.user_id, yesterday_date)
    if cached:
        return {
            "status": "success",
            "message": "Recap retrieved from cache.",
            "recap_details": cached,
            "teams_response": None,
            "cached": True,
        }

    # Cache miss — run the full generation (no Teams send, no To-Do update)
    result = run_recap_flow_internal(
        user_id=req.user_id,
        yesterday_only=True,
        send_to_teams=False,
        update_todo=False,
    )
    save_web_recap_cache(req.user_id, yesterday_date, result["recap_details"])
    return result

@app.post("/api/web/recap/generate-all")
def web_generate_all_recap(req: WebRecapRequest):
    state = load_previous_recap(req.user_id)
    last_recap_at_str = state["last_recap_at"]
    now_utc = datetime.now(timezone.utc)
    if last_recap_at_str:
        start_utc = datetime.fromisoformat(last_recap_at_str.replace("Z", "+00:00"))
    else:
        start_utc = now_utc - timedelta(days=1)
    return run_recap_flow_internal(user_id=req.user_id, start_time=start_utc, end_time=now_utc)

@app.post("/api/web/recap/generate-total")
def web_generate_total_recap(req: WebRecapRequest):
    return run_recap_flow_internal(user_id=req.user_id, start_time=None, end_time=None)


@app.get("/")
def test():
    return "Hello World"
if __name__ == "__main__":
    import uvicorn
    # Allow running directly via python main.py
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
