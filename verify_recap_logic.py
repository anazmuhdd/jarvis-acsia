import json
import os
from datetime import datetime, timedelta, timezone

# Mocking the functions to test state logic
STATE_FILE = "recap_state_test.json"

def load_previous_recap() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return {
                    "previous_recap": data.get("previous_recap", ""),
                    "last_recap_at": data.get("last_recap_at", None)
                }
        except json.JSONDecodeError:
            return {"previous_recap": "", "last_recap_at": None}
    return {"previous_recap": "", "last_recap_at": None}

def save_current_recap(recap: str, last_recap_at: str = None):
    data = {"previous_recap": recap}
    if last_recap_at:
        data["last_recap_at"] = last_recap_at
    else:
        data["last_recap_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)

def test_state_flow():
    print("Testing state flow...")
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        
    # Initial load
    state = load_previous_recap()
    assert state["previous_recap"] == ""
    assert state["last_recap_at"] is None
    print("1. Initial state check passed.")
    
    # Save first recap
    first_recap = "First recap content."
    first_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    save_current_recap(first_recap, last_recap_at=first_time)
    
    state = load_previous_recap()
    assert state["previous_recap"] == first_recap
    assert state["last_recap_at"] == first_time
    print("2. First save check passed.")
    
    # Simulate generate-all with stored time
    new_time = (datetime.fromisoformat(state["last_recap_at"].replace("Z", "+00:00")) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    save_current_recap("Second recap content.", last_recap_at=new_time)
    
    state = load_previous_recap()
    assert state["previous_recap"] == "Second recap content."
    assert state["last_recap_at"] == new_time
    print("3. Second save check passed.")
    
    os.remove(STATE_FILE)
    print("All state flow tests passed!")

if __name__ == "__main__":
    test_state_flow()
