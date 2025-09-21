from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Correct import statement
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
import time
import uuid

chat_app = FastAPI(title="Genie Dummy Chat Server", description="Backend chat server with Ollama integration")

# Add CORS middleware
chat_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class StartConversationRequest(BaseModel):
    message: str
    model: Optional[str] = "llama2"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000

class ConversationResponse(BaseModel):
    conversation_id: str
    response: str
    model_used: str
    timestamp: str
    use_case_id: Optional[str] = None

# In-memory storage for conversations
conversations: Dict[str, list] = {}

@chat_app.get("/")
async def chat_root():
    return {"service": "Dummy Chat Server", "status": "running", "version": "2.0"}

@chat_app.post("/api/2.0/genie_dummy/spaces/start-conversation", response_model=ConversationResponse)
async def start_conversation(request: StartConversationRequest, headers: Dict[str, Any] = None):
    """Start a new conversation with the dummy chat service"""
    
    try:
        # Generate conversation ID
        conversation_id = str(uuid.uuid4())
        
        # Get use case ID from headers (passed through proxy)
        use_case_id = headers.get("x-use-case-id") if headers else "unknown"
        
        # Simulate Ollama response (in real scenario, you'd call ollama here)
        dummy_responses = [
            "Hello! I'm a Genie (dummy) chat assistant. How can I help you today?",
            "That's an interesting question! Let me think about that...",
            "I understand your request. Here's what I think about that topic...",
            "Great question! Based on my training, I can share some insights...",
            "Thanks for reaching out! I'm here to help with your query..."
        ]
        
        import random
        response_text = random.choice(dummy_responses) + f" (Processed by {request.model})"
        
        # Store conversation
        conversations[conversation_id] = [
            {
                "role": "user",
                "content": request.message,
                "timestamp": time.time()
            },
            {
                "role": "assistant", 
                "content": response_text,
                "timestamp": time.time()
            }
        ]
        
        # Create response
        response = ConversationResponse(
            conversation_id=conversation_id,
            response=response_text,
            model_used=request.model,
            timestamp=str(time.time()),
            use_case_id=use_case_id
        )
        
        print(f"New conversation started: {conversation_id} for use-case: {use_case_id}")
        return response
        
    except Exception as e:
        print(f"Error in start_conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting conversation: {str(e)}")

@chat_app.get("/api/2.0/genie_dummy/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "conversation_id": conversation_id,
        "messages": conversations[conversation_id]
    }

@chat_app.get("/api/2.0/genie_dummy/health")
async def chat_health():
    return {
        "status": "healthy",
        "active_conversations": len(conversations),
        "service": "dummy_chat_server"
    }

if __name__ == "__main__":
    uvicorn.run(chat_app, host="0.0.0.0", port=8002)