import os
import json
import requests
import base64
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TENANT_ID = os.getenv("TENANT_ID", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
USER_ID = os.getenv("USER_ID", "")


# Flag to use mock data for local testing without API permissions
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

GRAPH_ACCESS_TOKEN = os.getenv("GRAPH_ACCESS_TOKEN", "")

def get_access_token():
    """
    Fetches the access token. 
    1. Prioritizes GRAPH_ACCESS_TOKEN from .env (for manual overrides).
    2. Falls back to Client Credentials flow.
    """
    # 1. Check for manual token override
    if GRAPH_ACCESS_TOKEN and GRAPH_ACCESS_TOKEN != "your_token_here":
        return GRAPH_ACCESS_TOKEN
            
    # 2. Fall back to oauth flow
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

def get_all_pages(url, headers):
    """Helper function to handle pagination for Graph API requests."""
    results = []
    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            results.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        else:
            print(f"Error fetching data from {url}: {resp.status_code} - {resp.text}")
            break
    return results

def get_all_messages_for_url(url, headers):
    """
    Helper function to get all messages without time filtering.
    Also handles 403 Forbidden gracefully.
    """
    results = []
    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get("value", [])
            results.extend(messages)
            url = data.get("@odata.nextLink")
        elif resp.status_code in [401, 403]:
            # Gracefully ignore if we lack permissions for a channel/chat
            print(f"Skipping (Permission Denied): {url.split('?')[0]}")
            break
        else:
            print(f"Error fetching data from {url}: {resp.status_code} - {resp.text}")
            break
    return results

def get_all_messages(token, start_time=None, end_time=None, user_id=None):
    """
    Gets all messages from the specified user's chats, teams, and channels.
    If start_time and end_time are provided (as datetime objects), filters messages accordingly.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        print(f"MOCK_MODE Enabled for user {target_user_id}: Loading complex mock data from mock_chat_data.json...")
        now = datetime.now(timezone.utc)
        
        try:
            with open("mock_chat_data.json", "r") as f:
                raw_mock_data = json.load(f)
                
            mock_messages = []
            for item in raw_mock_data:
                # Calculate the dynamically shifted relative date
                target_date = now + timedelta(days=item["relative_day"])
                # Extract the HH:MM:SS from the json and inject it into the target date
                t_parts = item["time"].split(":")
                target_time = target_date.replace(
                    hour=int(t_parts[0]), 
                    minute=int(t_parts[1]), 
                    second=int(t_parts[2]), 
                    microsecond=0
                ).replace(tzinfo=timezone.utc) # Ensure UTC
                
                # Filter mock data if range is provided
                if start_time and end_time:
                    if not (start_time <= target_time <= end_time):
                        continue

                mock_messages.append({
                    "sender": item["sender"],
                    "content": item["content"],
                    "time": target_time.isoformat().replace("+00:00", "Z"),
                    "source": "Mock Data"
                })
            return mock_messages
        except FileNotFoundError:
            print("ERROR: mock_chat_data.json not found! Ensure it is in the same directory.")
            return []

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    all_messages = []
    
    # Common filter string for API optimization
    filter_query = ""
    if start_time and end_time:
        # User feedback: createdDateTime doesn't support ge filter.
        # lastModifiedDateTime only supports gt (greater than) and lt (less than) for chat messages.
        # We adjust the range by 1 second to ensure we capture the full day with gt/lt.
        api_start = start_time - timedelta(seconds=1)
        api_end = end_time + timedelta(seconds=1)
        
        start_iso = api_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_iso = api_end.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        filter_query = f"?$filter=lastModifiedDateTime gt {start_iso} and lastModifiedDateTime lt {end_iso}"
    elif start_time:
        api_start = start_time - timedelta(seconds=1)
        start_iso = api_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        filter_query = f"?$filter=lastModifiedDateTime gt {start_iso}"
    
    def parse_time(t_str):
        try:
            return datetime.fromisoformat(t_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    # 1. Get all 1-on-1 and group chats for the user
    chats_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/chats"
    chats = get_all_pages(chats_url, headers)
    
    # Extract messages for each chat
    for chat in chats:
        chat_id = chat["id"]
        msgs_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/chats/{chat_id}/messages{filter_query}"
        
        msgs = get_all_messages_for_url(msgs_url, headers)
        for msg in msgs:
            created_at_str = msg.get("createdDateTime")
            if not created_at_str:
                continue
                
            created_at = parse_time(created_at_str)
            # Precise client-side filtering by createdDateTime
            if start_time and end_time:
                if not created_at or not (start_time <= created_at <= end_time):
                    continue

            body = msg.get("body") or {}
            content = body.get("content")
            if content:
                from_field = msg.get("from") or {}
                user_field = from_field.get("user") or {}
                sender = user_field.get("displayName", "Unknown")
                all_messages.append({
                    "sender": sender,
                    "content": content,
                    "time": created_at_str,
                    "source": "Chat"
                })

    # 2. Get all teams the user is a member of
    teams_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/joinedTeams"
    teams = get_all_pages(teams_url, headers)

    for team in teams:
        team_id = team["id"]
        # Get all channels for the team
        channels_url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels"
        channels = get_all_pages(channels_url, headers)

        for channel in channels:
            # Extract messages for each channel
            channel_id = channel["id"]
            msgs_url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages{filter_query}"
            
            msgs = get_all_messages_for_url(msgs_url, headers)
            for msg in msgs:
                created_at_str = msg.get("createdDateTime")
                if not created_at_str:
                    continue
                    
                created_at = parse_time(created_at_str)
                # Precise client-side filtering
                if start_time and end_time:
                    if not created_at or not (start_time <= created_at <= end_time):
                        continue

                body = msg.get("body") or {}
                content = body.get("content")
                if content:
                    from_field = msg.get("from") or {}
                    user_field = from_field.get("user") or {}
                    sender = user_field.get("displayName", "Unknown")
                    
                    team_name = (team or {}).get("displayName", "Unknown")
                    channel_name = (channel or {}).get("displayName", "Unknown")
                    
                    all_messages.append({
                        "sender": sender,
                        "content": content,
                        "time": created_at_str,
                        "source": f"Team: {team_name} - Channel: {channel_name}"
                    })
    
    # Sort messages chronologically
    all_messages.sort(key=lambda x: x["time"])
    return all_messages

def create_or_get_direct_chat(token, user_id=None):
    """
    Creates a 1-on-1 chat with the user so the bot can send direct messages.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        return f"mock_chat_id_{target_user_id}"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = "https://graph.microsoft.com/v1.0/chats"
    
    payload = {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{target_user_id}')"
            }
        ]
    }
    
    create_resp = requests.post(url, headers=headers, json=payload)
    if create_resp.status_code == 201:
        return create_resp.json()["id"]
    elif create_resp.status_code == 400:
        # Fallback to fetching existing 1-on-1 chats
        chats_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/chats?$filter=chatType eq 'oneOnOne'"
        chats_resp = requests.get(chats_url, headers=headers)
        if chats_resp.status_code == 200:
            chats = chats_resp.json().get("value", [])
            for chat in chats:
                return chat["id"]
                
    create_resp.raise_for_status()
    

def send_message_to_user_chat(token, chat_id, message_html):
    """
    Sends the generated HTML formatted message to the specified chat.
    """
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages"
    payload = {
        "body": {
            "contentType": "html",
            "content": message_html
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()

def create_or_get_todo_list(token, list_name="Tasks from Teams", user_id=None):
    """
    Creates or retrieves a Microsoft To Do list.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        return f"mock_todo_list_id_{target_user_id}"
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 1. Fetch existing lists to see if it already exists
    lists_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/todo/lists"
    resp = requests.get(lists_url, headers=headers)
    
    if resp.status_code == 200:
        todo_lists = resp.json().get("value", [])
        for lst in todo_lists:
            if lst.get("displayName") == list_name:
                return lst["id"]
                
    # 2. If it doesn't exist, create it
    payload = {
        "displayName": list_name
    }
    create_resp = requests.post(lists_url, headers=headers, json=payload)
    create_resp.raise_for_status()
    return create_resp.json()["id"]


def create_todo_task(token, list_id, title, user_id=None):
    """
    Creates a new task in the specified Microsoft To Do list.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        print(f"\n--- MOCK MODE: Created To-Do Task [{title}] in list [{list_id}] for user [{target_user_id}] ---")
        return {"id": "mock_task_id_456"}
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    tasks_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/todo/lists/{list_id}/tasks"
    
    payload = {
        "title": title
    }
    
    resp = requests.post(tasks_url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()

def get_todo_lists(token, user_id=None):
    """
    Fetches all Microsoft To Do lists for the user.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        return [{"id": f"mock_todo_list_id_{target_user_id}", "displayName": "Tasks from Teams"}]
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    lists_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/todo/lists"
    return get_all_pages(lists_url, headers)

def get_tasks_for_list(token, list_id, user_id=None):
    """
    Fetches pending (not completed) tasks from a specific Microsoft To Do list.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        return [
            {"id": "mock_task_1", "title": "Buy milk", "status": "notStarted"},
            {"id": "mock_task_2", "title": "Finish report", "status": "inProgress"}
        ]
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # Filter for non-completed tasks
    tasks_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/todo/lists/{list_id}/tasks?$filter=status ne 'completed'"
    return get_all_pages(tasks_url, headers)

def create_or_get_onenote_notebook(token, notebook_name="Teams Recaps", user_id=None):
    """
    Creates or retrieves a Microsoft OneNote notebook by name.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        return f"mock_notebook_id_{target_user_id}"
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    notebooks_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/onenote/notebooks"
    
    # 1. Fetch existing notebooks
    resp = requests.get(notebooks_url, headers=headers)
    if resp.status_code == 200:
        for nb in resp.json().get("value", []):
            if nb.get("displayName") == notebook_name:
                return nb["id"]
                
    # 2. If it doesn't exist, create it
    payload = {"displayName": notebook_name}
    create_resp = requests.post(notebooks_url, headers=headers, json=payload)
    create_resp.raise_for_status()
    return create_resp.json()["id"]

def create_onenote_section(token, notebook_id, section_name, user_id=None):
    """
    Creates or retrieves a Microsoft OneNote section within a notebook by name.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        return f"mock_section_id_{target_user_id}"
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    sections_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/onenote/notebooks/{notebook_id}/sections"
    
    # 1. Fetch existing sections
    list_resp = requests.get(sections_url, headers=headers)
    if list_resp.status_code == 200:
        for sec in list_resp.json().get("value", []):
            if sec.get("displayName") == section_name:
                return sec["id"]
                
    # 2. If not found, create it
    payload = {"displayName": section_name}
    create_resp = requests.post(sections_url, headers=headers, json=payload)
    create_resp.raise_for_status()
    return create_resp.json()["id"]

def create_onenote_page(token, section_id, html_content, title="Daily Recap", user_id=None):
    """
    Creates a new page in the specified Microsoft OneNote section.
    """
    target_user_id = user_id or USER_ID
    if MOCK_MODE:
        print(f"\n--- MOCK MODE: Created OneNote Page '{title}' in section [{section_id}] for user [{target_user_id}] ---")
        return {"id": "mock_page_id_345"}
        
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "text/html"
    }
    pages_url = f"https://graph.microsoft.com/v1.0/users/{target_user_id}/onenote/sections/{section_id}/pages"
    
    # OneNote requires a valid HTML document with a <title> tag to set the page name
    full_html = f"<!DOCTYPE html><html><head><title>{title}</title></head><body>{html_content}</body></html>"
    
    resp = requests.post(pages_url, headers=headers, data=full_html.encode('utf-8'))
    resp.raise_for_status()
    return resp.json()
