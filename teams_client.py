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

TOKEN_KEY_FILE = ".graph_token_key"
TOKEN_CACHE_FILE = ".graph_token_cache.json"

def _get_or_create_aes_key() -> bytes:
    if os.path.exists(TOKEN_KEY_FILE):
        with open(TOKEN_KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = AESGCM.generate_key(bit_length=256)
        with open(TOKEN_KEY_FILE, "wb") as f:
            f.write(key)
        return key

def _encrypt_token(token: str) -> str:
    key = _get_or_create_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    # Encrypt token, add nonce at start, then encode to base64 string
    ciphertext = aesgcm.encrypt(nonce, token.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")

def _decrypt_token(encrypted_b64: str) -> str:
    key = _get_or_create_aes_key()
    aesgcm = AESGCM(key)
    encrypted_data = base64.b64decode(encrypted_b64)
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

def inject_raw_token(token: str):
    """
    Encrypts and caches a raw Graph API token (e.g. from Graph Explorer) for ~1 hour.
    """
    encrypted = _encrypt_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=55)
    
    with open(TOKEN_CACHE_FILE, "w") as f:
        json.dump({
            "encrypted_token": encrypted,
            "expires_at": expires_at.isoformat()
        }, f)

def get_access_token():
    """
    Fetches the access token, first checking for an injected token, then falling back to Client Credentials.
    """
    # 1. Check if we have a valid cached token
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, "r") as f:
                data = json.load(f)
            expires_at = datetime.fromisoformat(data["expires_at"])
            if datetime.now(timezone.utc) < expires_at:
                return _decrypt_token(data["encrypted_token"])
        except Exception as e:
            print(f"Failed to load/decrypt cached token: {e}")
            
    # 2. Fall back to oauth flow
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    # ... (rest of get_access_token implementation remains the same)
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

def get_all_messages(token):
    """
    Gets all messages from the specified user's chats, teams, and channels.
    """
    if MOCK_MODE:
        print("MOCK_MODE Enabled: Loading complex mock data from mock_chat_data.json...")
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
                )
                
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
    
    # 1. Get all 1-on-1 and group chats for the user
    chats_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/chats"
    chats = get_all_pages(chats_url, headers)
    
    # Extract messages for each chat
    for chat in chats:
        chat_id = chat["id"]
        msgs_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/chats/{chat_id}/messages"
        
        msgs = get_all_messages_for_url(msgs_url, headers)
        for msg in msgs:
            body = msg.get("body") or {}
            content = body.get("content")
            if content:
                from_field = msg.get("from") or {}
                user_field = from_field.get("user") or {}
                sender = user_field.get("displayName", "Unknown")
                all_messages.append({
                    "sender": sender,
                    "content": content,
                    "time": msg.get("createdDateTime", ""),
                    "source": "Chat"
                })

    # 2. Get all teams the user is a member of
    teams_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/joinedTeams"
    teams = get_all_pages(teams_url, headers)

    for team in teams:
        team_id = team["id"]
        # Get all channels for the team
        channels_url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels"
        channels = get_all_pages(channels_url, headers)

        for channel in channels:
            # Extract messages for each channel
            channel_id = channel["id"]
            msgs_url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages"
            
            msgs = get_all_messages_for_url(msgs_url, headers)
            for msg in msgs:
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
                        "time": msg.get("createdDateTime", ""),
                        "source": f"Team: {team_name} - Channel: {channel_name}"
                    })
    
    # Sort messages chronologically
    all_messages.sort(key=lambda x: x["time"])
    return all_messages

def create_or_get_direct_chat(token):
    """
    Creates a 1-on-1 chat with the user so the bot can send direct messages.
    """
    if MOCK_MODE:
        return "mock_chat_id_67890"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = "https://graph.microsoft.com/v1.0/chats"
    
    payload = {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{USER_ID}')"
            }
        ]
    }
    
    create_resp = requests.post(url, headers=headers, json=payload)
    if create_resp.status_code == 201:
        return create_resp.json()["id"]
    elif create_resp.status_code == 400:
        # Fallback to fetching existing 1-on-1 chats
        chats_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/chats?$filter=chatType eq 'oneOnOne'"
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
    if MOCK_MODE:
        print("\n--- MOCK MODE: Intercepted Outbound Message ---")
        print(message_html)
        print("-----------------------------------------------\n")
        return {"id": "mock_message_id_111"}

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

def create_or_get_todo_list(token, list_name="Tasks from Teams"):
    """
    Creates or retrieves a Microsoft To Do list.
    """
    if MOCK_MODE:
        return "mock_todo_list_id_123"
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 1. Fetch existing lists to see if it already exists
    lists_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/todo/lists"
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


def create_todo_task(token, list_id, title):
    """
    Creates a new task in the specified Microsoft To Do list.
    """
    if MOCK_MODE:
        print(f"\n--- MOCK MODE: Created To-Do Task [{title}] in list [{list_id}] ---")
        return {"id": "mock_task_id_456"}
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    tasks_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/todo/lists/{list_id}/tasks"
    
    payload = {
        "title": title
    }
    
    resp = requests.post(tasks_url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()

def create_or_get_onenote_notebook(token, notebook_name="Teams Recaps"):
    """
    Creates or retrieves a Microsoft OneNote notebook by name.
    """
    if MOCK_MODE:
        return "mock_notebook_id_789"
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    notebooks_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/onenote/notebooks"
    
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

def create_onenote_section(token, notebook_id, section_name):
    """
    Creates or retrieves a Microsoft OneNote section within a notebook by name.
    """
    if MOCK_MODE:
        return "mock_section_id_012"
        
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    sections_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/onenote/notebooks/{notebook_id}/sections"
    
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

def create_onenote_page(token, section_id, html_content, title="Daily Recap"):
    """
    Creates a new page in the specified Microsoft OneNote section.
    """
    if MOCK_MODE:
        print(f"\n--- MOCK MODE: Created OneNote Page '{title}' in section [{section_id}] ---")
        return {"id": "mock_page_id_345"}
        
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "text/html"
    }
    pages_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/onenote/sections/{section_id}/pages"
    
    # OneNote requires a valid HTML document with a <title> tag to set the page name
    full_html = f"<!DOCTYPE html><html><head><title>{title}</title></head><body>{html_content}</body></html>"
    
    resp = requests.post(pages_url, headers=headers, data=full_html.encode('utf-8'))
    resp.raise_for_status()
    return resp.json()
