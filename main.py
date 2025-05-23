import os
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, cast # Import cast
from dotenv import load_dotenv

# Async LLM Clients
from openai import AsyncOpenAI
# For OpenAI message types
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
)

from anthropic import AsyncAnthropic
from anthropic import NOT_GIVEN # Correctly import the sentinel instance for optional parameters
# For Anthropic message types (though often dicts are fine if structured correctly)
from anthropic.types import MessageParam # General type hint for messages

# --- Configuration ---
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not found. OpenAI models will not be available.")
if not ANTHROPIC_API_KEY:
    print("Warning: ANTHROPIC_API_KEY not found. Anthropic models will not be available.")

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

app = FastAPI(
    title="Multi-LLM Chat API",
    description="A simple chat interface supporting multiple Large Language Models."
)

# --- Pydantic Models (from frontend) ---
class ChatMessageInput(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessageInput]
    model: str

# --- LLM Interaction Functions ---
async def get_openai_response(messages_input: List[ChatMessageInput], model_id: str) -> str:
    if not openai_client:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured.")
    
    openai_messages: List[ChatCompletionMessageParam] = []
    for msg_in in messages_input:
        if msg_in.role == "system":
            openai_messages.append(ChatCompletionSystemMessageParam(role="system", content=msg_in.content))
        elif msg_in.role == "user":
            openai_messages.append(ChatCompletionUserMessageParam(role="user", content=msg_in.content))
        elif msg_in.role == "assistant":
            openai_messages.append(ChatCompletionAssistantMessageParam(role="assistant", content=msg_in.content))

    if not openai_messages: # Ensure there's something to send
        return "Error: No messages to send to OpenAI."

    try:
        completion = await openai_client.chat.completions.create(
            model=model_id,
            messages=openai_messages
        )
        if completion.choices[0].message.content is None:
            return "" 
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error with OpenAI API: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

async def get_anthropic_response(messages_input: List[ChatMessageInput], model_id: str) -> str:
    if not anthropic_client:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured.")

    system_prompt_content: str | None = None
    processed_anthropic_messages: List[MessageParam] = [] 

    if messages_input and messages_input[0].role == 'system':
        system_prompt_content = messages_input[0].content
        for msg_in in messages_input[1:]:
            processed_anthropic_messages.append(cast(MessageParam, {"role": msg_in.role, "content": msg_in.content}))
    else:
        for msg_in in messages_input:
            processed_anthropic_messages.append(cast(MessageParam, {"role": msg_in.role, "content": msg_in.content}))
    
    if not processed_anthropic_messages or not any(msg_dict.get("role") == "user" for msg_dict in processed_anthropic_messages if isinstance(msg_dict, dict)): # Check for user role
         raise HTTPException(status_code=400, detail="No user messages provided to Anthropic model after processing.")

    try:
        response = await anthropic_client.messages.create(
            model=model_id,
            max_tokens=1024,
            system=system_prompt_content if system_prompt_content else NOT_GIVEN, # Use the imported NOT_GIVEN
            messages=processed_anthropic_messages
        )
        
        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text
        
        if not response_text and not response.content: # If content is empty list
             return "" # Or handle as appropriate if an empty response is unexpected
        elif not response_text and response.content : # If content has blocks but none are text
             print(f"Anthropic response had no text blocks: {response.content}")
             return "[Anthropic response contained no processable text]"

        return response_text
    except Exception as e:
        print(f"Error with Anthropic API: {e}")
        raise HTTPException(status_code=500, detail=f"Anthropic API error: {str(e)}")

# --- API Endpoints ---
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    model_id_key = request.model
    
    MODEL_MAPPING = {
        "openai_gpt-3.5-turbo": {"provider": "openai", "id": "gpt-3.5-turbo"},
        "anthropic_claude-3-haiku": {"provider": "anthropic", "id": "claude-3-haiku-20240307"},
    }

    if model_id_key not in MODEL_MAPPING:
        raise HTTPException(status_code=400, detail=f"Invalid model key selected: {model_id_key}")

    selected_model_info = MODEL_MAPPING[model_id_key]
    provider = selected_model_info["provider"]
    actual_model_id = selected_model_info["id"]
    
    if provider == "openai":
        if not openai_client: # Added check here for clarity
            raise HTTPException(status_code=503, detail="OpenAI model selected, but API key not configured.")
        response_content = await get_openai_response(request.messages, actual_model_id)
    elif provider == "anthropic":
        if not anthropic_client: # Added check here for clarity
            raise HTTPException(status_code=503, detail="Anthropic model selected, but API key not configured.")
        response_content = await get_anthropic_response(request.messages, actual_model_id)
    else:
        raise HTTPException(status_code=500, detail="Model provider logic error.")

    return {"role": "assistant", "content": response_content}

# Serve static files
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")