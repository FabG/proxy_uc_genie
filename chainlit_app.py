import chainlit as cl
import httpx
import json
from typing import Dict, Any
import asyncio
from config_manager import config

# Get configuration
chainlit_config = config.get_chainlit_config()
PROXY_URL = chainlit_config.get('proxy_url', 'http://localhost:8001')
USE_CASE_ID = chainlit_config.get('default_use_case_id', '100000')

# Headers to include in all requests
DEFAULT_HEADERS = {
    "X-Use-Case-ID": USE_CASE_ID,
    "Content-Type": "application/json",
    "User-Agent": "Chainlit-Client/1.0"
}

async def call_chat_api(message: str) -> Dict[str, Any]:
    """Call the chat API through the proxy"""
    
    endpoint = f"{PROXY_URL}/api/2.0/genie_dummy/spaces/start-conversation"
    
    payload = {
        "message": message,
        "model": "llama3.1",  # Updated to use Llama 3.1
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": False
    }
    
    print(f"📤 Calling API: {endpoint}")
    print(f"📦 Payload: {payload}")
    print(f"📋 Headers: {DEFAULT_HEADERS}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=DEFAULT_HEADERS,
                json=payload
            )
            
            print(f"📨 Response Status: {response.status_code}")
            print(f"📄 Response Text: {response.text}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 422:
                return {"error": f"Validation error (422): {response.text}"}
            elif response.status_code == 403:
                return {"error": "Access denied - unauthorized use case"}
            elif response.status_code == 400:
                return {"error": "Bad request - missing required headers"}
            else:
                return {"error": f"API error: {response.status_code} - {response.text}"}
                
    except httpx.RequestError as e:
        print(f"🚨 Connection error: {str(e)}")
        return {"error": f"Connection error: {str(e)}"}
    except Exception as e:
        print(f"🚨 Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

@cl.on_message
async def handle_message(message: cl.Message):
    """Handle incoming messages from the Chainlit interface"""
    
    # Show typing indicator
    async with cl.Step(name="Thinking...") as step:
        step.output = "Processing your message through the proxy..."
        
        # Call the chat API
        result = await call_chat_api(message.content)
        
        if "error" in result:
            # Handle errors
            await cl.Message(
                content=f"❌ **Error**: {result['error']}",
                author="System"
            ).send()
        else:
            # Success response
            response_text = result.get("response", "No response received")
            conversation_id = result.get("conversation_id", "unknown")
            model_used = result.get("model_used", "unknown")
            processing_time = result.get("processing_time", 0)
            token_count = result.get("token_count", 0)
            
            # Format processing time
            time_str = f"{processing_time:.2f}s" if processing_time else "unknown"
            
            await cl.Message(
                content=f"🤖 **Response**: {response_text}\n\n"
                       f"📝 **Conversation ID**: `{conversation_id}`\n"
                       f"🧠 **Model**: {model_used}\n"
                       f"🏷️ **Use Case**: {USE_CASE_ID}\n"
                       f"⏱️ **Processing Time**: {time_str}\n"
                       f"🔢 **Approx. Tokens**: {token_count}",
                author="Llama 3.1"
            ).send()
        
        step.output = "Complete!"

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    await cl.Message(
        content="🚀 **Welcome to the Ollama Llama 3.1 Chat Client!**\n\n"
               f"I'm connected through a FastAPI proxy with use-case ID: `{USE_CASE_ID}`\n\n"
               "🧠 **Powered by**: Ollama Llama 3.1\n"
               "🔗 **Architecture**: Chainlit → FastAPI Proxy → Ollama Chat Server\n\n"
               "Send me a message and I'll route it through the proxy to Ollama!",
        author="System"
    ).send()