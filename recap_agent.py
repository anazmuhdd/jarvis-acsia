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
        ("system", "You are an expert executive assistant whose job is to read raw chat logs "
                   "and generate concise, professional summaries for {user_name}.\n\n"
                   "CRITICAL INSTRUCTIONS - YOU MUST OBEY THESE RULES:\n"
                   "- ONLY use the information explicitly provided in the chat logs below.\n"
                   "- NEVER invent, assume, or hallucinate names, events, meetings, or tasks.\n"
                   "- If there are no actionable tasks for {user_name} explicitly mentioned in the text, leave the pending_tasks array empty.\n"
                   "- If the chat logs do not provide enough context for a summary, state exactly that.\n"
                   "- IMPORTANT: If '{user_name}' is generic (like 'the user'), assume the person who is the primary subject of the logs or the person requesting reminders is '{user_name}'.\n\n"
                   "YOUR OBJECTIVES:\n"
                   "1. **Analyze Context**: You will be provided with previous summary context. You must ensure the new recap logically follows "
                   "from that prior context, updating the status of ongoing conversations or noting new developments.\n"
                   "2. **Identify Personal To-Do List**: Carefully scan the raw chat logs to extract explicit or implicit tasks, requests, "
                   "or obligations assigned SPECIFICALLY to {user_name}. These should be framed as clear, actionable bullet points.\n"
                   "3. **Catch Reminders**: Any mention of phrases like 'remind me to', 'don't forget to', 'make sure I', or 'can you remind me' where the speaker is asking for a reminder for themselves MUST be added to the pending_tasks list for {user_name}.\n"
                   "4. **Synthesize**: Write a coherent, paragraph-style narrative for the 'recap' field summarizing the overall team's discussions and decisions.\n\n"
                   "TONE: Professional, concise, objective, and clear.\n\n"
                   "OUTPUT FORMAT MUST STRICTLY ADHERE TO THESE INSTRUCTIONS:\n"
                   "{format_instructions}"),
        ("user", "--- PREVIOUS RECAP CONTEXT ---\n"
                 "{previous_recap}\n\n"
                 "--- CHAT MESSAGES ---\n"
                 "{messages}\n\n"
                 "Based STIRCTLY on the provided text above, please generate the updated recap and extract the personal to-do list for {user_name}.")
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
