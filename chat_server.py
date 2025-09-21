from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uvicorn
import time
import uuid
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from config_manager import config
import ollama
import logging

# Configure logging
logger = logging.getLogger(__name__)

chat_app = FastAPI(title="Ollama Chat Server", description="Backend chat server with Ollama Llama 3.1 integration")

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
    model: Optional[str] = "llama3.1"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    stream: Optional[bool] = False

class ConversationResponse(BaseModel):
    conversation_id: str
    response: str
    model_used: str
    timestamp: str
    use_case_id: Optional[str] = None
    processing_time: Optional[float] = None
    token_count: Optional[int] = None

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant" 
    content: str
    timestamp: float

class ConversationHistory(BaseModel):
    conversation_id: str
    messages: List[ChatMessage]
    model_used: str
    created_at: float
    use_case_id: Optional[str] = None

# In-memory storage for conversations
conversations: Dict[str, ConversationHistory] = {}

# Ollama configuration
OLLAMA_CONFIG = {
    "base_url": "http://localhost:11434",  # Default Ollama URL
    "default_model": "llama3.1",
    "timeout": 60,
    "max_retries": 3
}

async def check_ollama_connection():
    """Check if Ollama is running and has the required model"""
    try:
        # Check if Ollama is accessible
        models = ollama.list()
        available_models = [model['name'] for model in models['models']]
        
        logger.info(f"Ollama connection successful. Available models: {available_models}")
        
        # Check if llama3.1 is available
        if not any('llama3.1' in model for model in available_models):
            logger.warning("⚠️  Llama 3.1 not found. Available models: " + ", ".join(available_models))
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ollama connection failed: {str(e)}")
        logger.error("Make sure Ollama is running with: ollama serve")
        logger.error("And Llama 3.1 is installed with: ollama pull llama3.1")
        return False

async def generate_ollama_response(message: str, model: str = "llama3.1", conversation_history: List[ChatMessage] = None) -> Dict[str, Any]:
    """Generate response using Ollama Llama 3.1"""
    
    start_time = time.time()
    
    try:
        # Prepare conversation context
        messages = []
        
        # Add conversation history if available
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages for context
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Add current message
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # Call Ollama
        logger.info(f"Calling Ollama with model: {model}")
        response = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": 0.7,
                "num_ctx": 4096,  # Context window
                "top_p": 0.9,
                "repeat_penalty": 1.1
            }
        )
        
        processing_time = time.time() - start_time
        
        # Extract response content
        response_content = response['message']['content']
        
        # Calculate approximate token count (rough estimation)
        token_count = len(response_content.split()) + len(message.split())
        
        logger.info(f"Ollama response generated in {processing_time:.2f}s, ~{token_count} tokens")
        
        return {
            "content": response_content,
            "processing_time": processing_time,
            "token_count": token_count,
            "model": model,
            "success": True
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Ollama error: {str(e)}"
        logger.error(f"❌ {error_msg} (after {processing_time:.2f}s)")
        
        # Return fallback response
        return {
            "content": f"I apologize, but I encountered an error while processing your request: {str(e)}. Please ensure Ollama is running and Llama 3.1 is available.",
            "processing_time": processing_time,
            "token_count": 0,
            "model": model,
            "success": False,
            "error": str(e)
        }

@chat_app.get("/")
async def chat_root():
    return {
        "service": "Ollama Chat Server", 
        "status": "running", 
        "version": "2.0",
        "model": OLLAMA_CONFIG["default_model"],
        "ollama_url": OLLAMA_CONFIG["base_url"]
    }

@chat_app.get("/health")
async def health_check():
    """Comprehensive health check including Ollama status"""
    ollama_status = await check_ollama_connection()
    
    return {
        "status": "healthy" if ollama_status else "degraded",
        "active_conversations": len(conversations),
        "service": "ollama_chat_server",
        "ollama_connected": ollama_status,
        "default_model": OLLAMA_CONFIG["default_model"]
    }

@chat_app.get("/models")
async def list_available_models():
    """List available Ollama models"""
    try:
        models = ollama.list()
        return {
            "available_models": [model['name'] for model in models['models']],
            "default_model": OLLAMA_CONFIG["default_model"],
            "recommended": "llama3.1"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cannot connect to Ollama: {str(e)}")

@chat_app.post("/api/2.0/genie_dummy/spaces/start-conversation", response_model=ConversationResponse)
async def start_conversation(request: StartConversationRequest, http_request: Request):
    """Start a new conversation with Ollama Llama 3.1"""
    
    try:
        # Generate conversation ID
        conversation_id = str(uuid.uuid4())
        
        # Get use case ID from headers (passed through proxy)
        use_case_id = http_request.headers.get("x-use-case-id", "unknown")
        
        logger.info(f"Starting conversation {conversation_id} for use-case: {use_case_id}")
        logger.info(f"Request: {request.message[:100]}..." if len(request.message) > 100 else f"Request: {request.message}")
        
        # Generate response using Ollama
        ollama_result = await generate_ollama_response(
            message=request.message,
            model=request.model or OLLAMA_CONFIG["default_model"]
        )
        
        # Create conversation history
        user_message = ChatMessage(
            role="user",
            content=request.message,
            timestamp=time.time()
        )
        
        assistant_message = ChatMessage(
            role="assistant",
            content=ollama_result["content"],
            timestamp=time.time()
        )
        
        # Store conversation
        conversation_history = ConversationHistory(
            conversation_id=conversation_id,
            messages=[user_message, assistant_message],
            model_used=ollama_result["model"],
            created_at=time.time(),
            use_case_id=use_case_id
        )
        
        conversations[conversation_id] = conversation_history
        
        # Create response
        response = ConversationResponse(
            conversation_id=conversation_id,
            response=ollama_result["content"],
            model_used=ollama_result["model"],
            timestamp=str(time.time()),
            use_case_id=use_case_id,
            processing_time=ollama_result.get("processing_time"),
            token_count=ollama_result.get("token_count")
        )
        
        logger.info(f"✅ Conversation {conversation_id} completed successfully")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error in start_conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting conversation: {str(e)}")

@chat_app.post("/api/2.0/genie_dummy/conversations/{conversation_id}/continue")
async def continue_conversation(conversation_id: str, request: StartConversationRequest, http_request: Request):
    """Continue an existing conversation"""
    
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    try:
        conversation = conversations[conversation_id]
        
        # Generate response with conversation history
        ollama_result = await generate_ollama_response(
            message=request.message,
            model=request.model or conversation.model_used,
            conversation_history=conversation.messages
        )
        
        # Add new messages to conversation
        user_message = ChatMessage(
            role="user",
            content=request.message,
            timestamp=time.time()
        )
        
        assistant_message = ChatMessage(
            role="assistant", 
            content=ollama_result["content"],
            timestamp=time.time()
        )
        
        conversation.messages.extend([user_message, assistant_message])
        
        # Create response
        response = ConversationResponse(
            conversation_id=conversation_id,
            response=ollama_result["content"],
            model_used=ollama_result["model"],
            timestamp=str(time.time()),
            use_case_id=conversation.use_case_id,
            processing_time=ollama_result.get("processing_time"),
            token_count=ollama_result.get("token_count")
        )
        
        logger.info(f"✅ Continued conversation {conversation_id}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error continuing conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error continuing conversation: {str(e)}")

@chat_app.get("/api/2.0/genie_dummy/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversations[conversation_id]

@chat_app.delete("/api/2.0/genie_dummy/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    del conversations[conversation_id]
    return {"message": f"Conversation {conversation_id} deleted successfully"}

@chat_app.post("/api/2.0/genie_dummy/debug")
async def debug_endpoint(request: Request):
    """Debug endpoint to see what data is being received"""
    body = await request.body()
    return {
        "method": request.method,
        "headers": dict(request.headers),
        "query_params": dict(request.query_params),
        "body_raw": body.decode() if body else None,
        "content_type": request.headers.get("content-type"),
        "ollama_status": await check_ollama_connection()
    }

if __name__ == "__main__":
    import sys

    chat_config = config.get_chat_server_config()
    uvicorn.run(
        chat_app,
        host=chat_config.get('host', '0.0.0.0'),
        port=chat_config.get('port', 8002)
    )
