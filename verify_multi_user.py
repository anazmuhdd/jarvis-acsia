import os
import json

def get_state_file(user_id: str) -> str:
    return f"recap_state_{user_id}.json"

def test_multi_user_isolation():
    print("Testing multi-user state isolation...")
    user1 = "user_alpha"
    user2 = "user_beta"
    
    file1 = get_state_file(user1)
    file2 = get_state_file(user2)
    
    # Cleanup
    if os.path.exists(file1): os.remove(file1)
    if os.path.exists(file2): os.remove(file2)
    
    # Simulate saving for user1
    data1 = {"previous_recap": "Recap for Alpha", "last_recap_at": "2026-01-01T00:00:00Z"}
    with open(file1, "w") as f: json.dump(data1, f)
    
    # Check isolation
    assert os.path.exists(file1)
    assert not os.path.exists(file2)
    print("1. Isolation check passed (file1 exists, file2 doesn't).")
    
    # Simulate saving for user2
    data2 = {"previous_recap": "Recap for Beta", "last_recap_at": "2026-02-01T00:00:00Z"}
    with open(file2, "w") as f: json.dump(data2, f)
    
    # Verify contents
    with open(file1, "r") as f: val1 = json.load(f)
    with open(file2, "r") as f: val2 = json.load(f)
    
    assert val1["previous_recap"] == "Recap for Alpha"
    assert val2["previous_recap"] == "Recap for Beta"
    print("2. Content verification passed.")
    
    # Cleanup
    os.remove(file1)
    os.remove(file2)
    print("All multi-user isolation tests passed!")

if __name__ == "__main__":
    test_multi_user_isolation()
