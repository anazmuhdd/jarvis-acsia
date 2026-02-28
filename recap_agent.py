import os
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from pydantic import BaseModel, Field

# Ensure NVIDIA_API_KEY is set in your environment variables.
# Using a suitable dense/large model hosted by Nvidia.
llm = ChatNVIDIA(model="meta/llama-3.1-70b-instruct")

class AgentState(TypedDict):
    messages: List[dict]         # All the messages fetched
    previous_recap: str          # Previous recap context 
    current_recap: str           # The generated recap
    pending_tasks: List[str]     # Extracted pending tasks

class RecapOutput(BaseModel):
    recap: str = Field(description="The summary of the activities, considering the previous recap as context. Ensure it flows logically as an incremental update.")
    pending_tasks: List[str] = Field(description="List of concrete, actionable pending tasks extracted from the chat messages.")

from langchain_core.output_parsers import PydanticOutputParser

USER_NAME = os.getenv("USER_NAME", "the user")

def generate_recap_and_tasks(state: AgentState) -> dict:
    messages = state["messages"]
    previous_recap = state.get("previous_recap", "")
    
    if not previous_recap:
        previous_recap = "No prior recap available."
    
    if not messages:
        return {
            "current_recap": "No chat activity found.",
            "pending_tasks": []
        }
    
    import re
    def clean_html(text):
        if not text: return ""
        # Remove HTML tags
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)

    # Format messages for the prompt
    msg_str = "\n".join([f"[{m['time']}] [{m.get('source', 'Chat')}] {m['sender']}: {clean_html(m['content'])}" for m in messages])
    
    parser = PydanticOutputParser(pydantic_object=RecapOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are Lila Jarvis — a dedicated personal Teams recap bot.\n"
                   "Your job is to read raw Microsoft Teams chat logs and generate a concise, professional summary for your user.\n\n"
                   "IDENTITY: You are a personal assistant bot. Your entire purpose is to help your user stay on top of conversations and tasks.\n\n"
                   "CRITICAL RULES - MUST OBEY:\n"
                   "- ONLY use information explicitly present in the chat logs. NEVER invent names, events, meetings, or tasks.\n"
                   "- A 'task' is ANY explicit or implicit request for action, analysis, update, or follow-up directed at {user_name}.\n"
                   "- {user_name} may appear in the chat under various names or nicknames. Treat ALL references to {user_name} as the same person.\n"
                   "- **CATCH ALL ACTION ITEMS**: This includes questions ('Can you look into X?'), requests ('Please send the report'), implicit asks ('We need an update on Y'), and reminders.\n"
                   "- If a task is mentioned in the chat targeting {user_name}, it MUST appear in the pending_tasks list.\n"
                   "- If there are no actionable tasks explicitly for {user_name}, leave pending_tasks empty.\n\n"
                   "YOUR OBJECTIVES:\n"
                   "1. **Build on Context**: A previous recap will be given. Ensure the new recap logically extends it, highlighting new developments, decisions, and updates.\n"
                   "2. **Extract {user_name}'s Personal To-Do List**: Scan the chat for every task, request, or obligation assigned to {user_name} — explicitly or implicitly. Focus on verbs: 'analyze', 'send', 'follow up', 'fix', 'share', 'raise', 'respond', etc.\n"
                   "3. **Capture Reminders**: Any time {user_name} says 'remind me to', 'don't forget to', 'make sure I', or 'can you remind me', add it to pending_tasks.\n"
                   "4. **Write a Team Narrative**: Produce a clear, paragraph-style narrative summarizing the overall discussions and decisions by the team.\n\n"
                   "VOICE & PERSPECTIVE — MANDATORY:\n"
                   "- The recap will be delivered directly to {user_name}.\n"
                   "- You MUST address the user strictly in second-person ('you', 'your') at ALL times.\n"
                   "- NEVER write or reference the user's real name anywhere in the recap or pending_tasks.\n"
                   "- This includes avoiding:\n"
                   "  - Direct name mentions (e.g. 'Jiji', 'Jijimon', 'Jijimon Chandran')\n"
                   "  - Third-person references to the user (e.g. 'he', 'him', 'his')\n"
                   "  - Variations, nicknames, initials, or partial names (e.g. 'J.C.', 'JC', 'J said...')\n"
                   "- Even if the name appears repeatedly in the chat logs, you MUST replace ALL references with second-person phrasing.\n"
                   "- If the user speaks in the chat, convert their statements into second-person recap format.\n"
                   "- If others refer to the user by name, convert those references to second-person.\n"
                   "- Refer to ALL other participants (anyone who is NOT {user_name}) by their actual name in third-person as normal.\n\n"
                   "EXAMPLES — STRICTLY FOLLOW:\n"
                   "  CORRECT:   'You were asked to send the report.'\n"
                   "  INCORRECT: 'Jiji was asked to send the report.'\n"
                   "  INCORRECT: 'Jijimon mentioned...'\n"
                   "  INCORRECT: 'J said...'\n\n"
                   "TONE: Confident, professional, concise, and clear — like a smart executive assistant briefing their boss.\n\n"
                   "OUTPUT FORMAT — STRICTLY FOLLOW:\n"
                   "{format_instructions}"),
        ("user", "--- PREVIOUS RECAP CONTEXT ---\n"
                 "{previous_recap}\n\n"
                 "--- CHAT MESSAGES ---\n"
                 "{messages}\n\n"
                 "Based STRICTLY on the above, generate the updated recap and extract the personal to-do list. "
                 "CRITICAL REMINDER: NEVER write the user's real name, nickname, initials, or any variation anywhere in the output. "
                 "Every reference to {user_name} — whether they spoke or were spoken to — must appear as 'you' or 'your'.")
    ])
    
    chain = prompt | llm | parser
    
    print("Invoking NVIDIA LLM for recap generation...")
    try:
        result = chain.invoke({
            "previous_recap": previous_recap,
            "messages": msg_str,
            "user_name": USER_NAME,
            "format_instructions": parser.get_format_instructions()
        })
        
        return {
            "current_recap": result.recap,
            "pending_tasks": result.pending_tasks
        }
    except Exception as e:
        print(f"Warning: Output parsing failed. Reason: {e}")
        return {
            "current_recap": "Failed to parse the recap from the AI model.",
            "pending_tasks": []
        }

def build_graph():
    """
    Constructs and compiles the LangGraph for the recap agent.
    """
    workflow = StateGraph(AgentState)
    
    # Add a single node for simplicity, though this could be expanded into multi-step reasoning
    workflow.add_node("generate_recap_and_tasks", generate_recap_and_tasks)
    
    workflow.set_entry_point("generate_recap_and_tasks")
    workflow.add_edge("generate_recap_and_tasks", END)
    
    return workflow.compile()
