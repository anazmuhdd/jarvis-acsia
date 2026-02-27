import os
import json
from dotenv import load_dotenv

load_dotenv()

from recap_agent import build_graph

def test_extraction():
    print("Testing task extraction with user example...")
    
    # Simulate chat messages based on user's recap
    messages = [
        {"time": "2026-02-27T10:00:00Z", "sender": "Jijimon Chandran", "content": "Hi Lila, I'm inquiring about the remaining runway. Let's discuss options.", "source": "Chat"},
        {"time": "2026-02-27T10:05:00Z", "sender": "Jijimon Chandran", "content": "Lila, can you please analyze option 3? I need the user impact and conversion willingness data as well.", "source": "Chat"},
        {"time": "2026-02-27T10:10:00Z", "sender": "Jijimon Chandran", "content": "Also, please run numbers on option 3 by end of day.", "source": "Chat"},
        {"time": "2026-02-27T10:15:00Z", "sender": "Jijimon Chandran", "content": "Wait, don't forget to fix the checkpoint bug before we scale anything. Reliability and speed are more important than vanity metrics right now.", "source": "Chat"}
    ]
    
    graph = build_graph()
    result = graph.invoke({
        "messages": messages,
        "previous_recap": "Yesterday we discussed the Q1 roadmap.",
        "current_recap": "",
        "pending_tasks": []
    })
    
    print("\n--- RESULTS ---")
    print(f"Recap: {result['current_recap']}")
    print("\nTasks Extracted:")
    for task in result['pending_tasks']:
        print(f"- {task}")
        
    expected_keywords = ["analyze option 3", "run numbers", "fix the checkpoint bug"]
    found = 0
    for keyword in expected_keywords:
        if any(keyword.lower() in t.lower() for t in result['pending_tasks']):
            found += 1
            
    if found >= 2: # At least 2 out of 3 major tasks found
        print("\nSUCCESS: Task extraction seems much better!")
    else:
        print(f"\nFAILURE: Only found {found}/{len(expected_keywords)} tasks.")

if __name__ == "__main__":
    test_extraction()
