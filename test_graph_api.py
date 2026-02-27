import os
import requests

def get_headers(access_token):
    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

def list_task_lists(access_token):
    url = "https://graph.microsoft.com/v1.0/me/todo/lists"
    response = requests.get(url, headers=get_headers(access_token))
    if response.status_code == 200:
        return response.json().get('value', [])
    else:
        print(f"Error fetching task lists: {response.status_code} - {response.text}")
        return []

def list_tasks(access_token, list_id, filter_query=None):
    url = f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks"
    if filter_query:
        url += f"?$filter={filter_query}"
    
    response = requests.get(url, headers=get_headers(access_token))
    if response.status_code == 200:
        return response.json().get('value', [])
    else:
        print(f"Error fetching tasks for list {list_id} (filter: {filter_query}): {response.status_code} - {response.text}")
        return []

def main():
    access_token = os.environ.get("ACCESS_TOKEN")
    if not access_token:
        print("Error: ACCESS_TOKEN environment variable is not set.")
        print("Usage: ACCESS_TOKEN='your_token_here' python test_graph_api.py")
        return

    print("--- Fetching Task Lists ---")
    task_lists = list_task_lists(access_token)
    
    if not task_lists:
        print("No task lists found or error occurred.")
        return

    for task_list in task_lists:
        list_id = task_list['id']
        list_name = task_list.get('displayName', 'Unknown')
        print(f"\n=========================================")
        print(f"Task List: {list_name} (ID: {list_id})")
        print(f"=========================================")
        
        # 1. List all tasks with no filters
        print("\n  -> Fetching all tasks (no filters)...")
        all_tasks = list_tasks(access_token, list_id)
        print(f"     Found {len(all_tasks)} tasks total.")
        for task in all_tasks:
            print(f"       - [{task.get('status', 'unknown')}] {task.get('title', 'Untitled')}")
            
        # 2. List completed tasks
        print("\n  -> Fetching completed tasks...")
        completed_tasks = list_tasks(access_token, list_id, filter_query="status eq 'completed'")
        print(f"     Found {len(completed_tasks)} completed tasks.")
        for task in completed_tasks:
            print(f"       - [completed] {task.get('title', 'Untitled')}")
            
        # 3. List not completed tasks
        print("\n  -> Fetching not completed tasks...")
        not_completed_tasks = list_tasks(access_token, list_id, filter_query="status ne 'completed'")
        print(f"     Found {len(not_completed_tasks)} not completed tasks.")
        for task in not_completed_tasks:
            print(f"       - [{task.get('status', 'unknown')}] {task.get('title', 'Untitled')}")

if __name__ == "__main__":
    main()
