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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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


def load_previous_recap() -> str:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return data.get("previous_recap", "")
        except json.JSONDecodeError:
            return ""
    return ""

def save_current_recap(recap: str):
    with open(STATE_FILE, "w") as f:
        json.dump({"previous_recap": recap}, f)

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
        previous_recap = load_previous_recap()
        
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
        save_current_recap(current_recap)
        
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
    """Run the AI Recap generation flow AND send the results via Teams for YESTERDAY (Local Time)."""
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
        
        # Filter out bot messages and system messages to avoid confusing the LLM
        filtered_messages = [
            m for m in messages 
            if m["sender"] not in ["Lila Jarvis", "Unknown"] 
            and "Daily Recap" not in m["content"]
        ]
        
        previous_recap = load_previous_recap()
        
        graph = build_graph()
        result = graph.invoke({
            "messages": filtered_messages,
            "previous_recap": previous_recap,
            "current_recap": "",
            "pending_tasks": []
        })
        
        current_recap = result["current_recap"]
        ai_extracted_tasks = result["pending_tasks"]
        
        # Save state for tomorrow
        save_current_recap(current_recap)
        
        # Add AI tasks to To Do
        todo_list_id = create_or_get_todo_list(token)
        if ai_extracted_tasks:
            for task_title in ai_extracted_tasks:
                try:
                    create_todo_task(token, todo_list_id, task_title)
                    print(f"[{datetime.now()}] Task created in To-Do: {task_title}")
                except Exception as task_err:
                    print(f"[{datetime.now()}] Error creating task '{task_title}': {task_err}")
        
        # Fetch actual tasks from To-Do list
        final_pending_tasks = list(ai_extracted_tasks)
        try:
            actual_tasks = get_tasks_for_list(token, todo_list_id)
            fetched_tasks = [t["title"] for t in actual_tasks]
            
            # Merge and deduplicate
            for t in fetched_tasks:
                if t not in final_pending_tasks:
                    final_pending_tasks.append(t)
            print(f"[{datetime.now()}] Successfully fetched {len(fetched_tasks)} tasks from To-Do.")
        except Exception as fetch_err:
            print(f"[{datetime.now()}] Error fetching tasks from To-Do via endpoint: {fetch_err}")

        # Format message for Teams Chat using HTML
        tasks_html = "".join([f"<li>{task}</li>" for task in final_pending_tasks])
        if not tasks_html:
            tasks_html = "<li>No pending tasks in your To-Do list.</li>"
            
        message_html = f"<h3>Daily Recap</h3><p>{current_recap}</p><h3>Your To-Do List</h3><ul>{tasks_html}</ul>"
        
        # Get Chat ID and Send message
        chat_id = create_or_get_direct_chat(token)
        send_resp = send_message_to_user_chat(token, chat_id, message_html)
                    
        # Send Recap to OneNote
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        try:
            notebook_id = create_or_get_onenote_notebook(token, "Teams Recaps")
            section_id = create_onenote_section(token, notebook_id, current_date_str)
            create_onenote_page(token, section_id, message_html, title=f"Recap for {current_date_str}")
        except Exception as onenote_err:
            print(f"[{datetime.now()}] Error pushing to OneNote via endpoint: {onenote_err}")
        
        return {
            "status": "success",
            "message": "Recap generated and sent to Teams successfully.",
            "recap_details": {
                "current_recap": current_recap,
                "pending_tasks": final_pending_tasks
            },
            "teams_response": send_resp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def test():
    return "Hello World"
if __name__ == "__main__":
    import uvicorn
    # Allow running directly via python main.py
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
