import chainlit as cl
import httpx
import json
from typing import Dict, Any, List
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

async def get_allowed_use_cases() -> List[str]:
    """Fetch allowed use-case IDs from the proxy server"""
    try:
        config_endpoint = f"{PROXY_URL}/config"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(config_endpoint)
            if response.status_code == 200:
                config_data = response.json()
                return config_data.get("allowed_use_cases", [])
            else:
                return []
    except Exception as e:
        print(f"🚨 Error fetching allowed use cases: {str(e)}")
        return []

async def call_chat_api(message: str, use_case_id: str = None) -> Dict[str, Any]:
    """Call the chat API through the proxy with dynamic use-case ID"""

    endpoint = f"{PROXY_URL}/api/2.0/genie_dummy/spaces/start-conversation"

    payload = {
        "message": message,
        "model": "llama3.1",  # Updated to use Llama 3.1
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": False
    }

    # Use dynamic use-case ID or fall back to default
    current_use_case_id = use_case_id or USE_CASE_ID

    # Create headers with dynamic use-case ID
    headers = {
        "X-Use-Case-ID": current_use_case_id,
        "Content-Type": "application/json",
        "User-Agent": "Chainlit-Client/1.0"
    }

    print(f"📤 Calling API: {endpoint}")
    print(f"📦 Payload: {payload}")
    print(f"📋 Headers: {headers}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload
            )
            
            print(f"📨 Response Status: {response.status_code}")
            print(f"📄 Response Text: {response.text}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 422:
                return {"error": f"Validation error (422): {response.text}", "error_type": "validation"}
            elif response.status_code == 403:
                # Parse the 403 error response to get more details
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", "Access denied - unauthorized use case")
                except:
                    error_detail = "Access denied - unauthorized use case"

                return {
                    "error": error_detail,
                    "error_type": "forbidden",
                    "status_code": 403,
                    "use_case_id": current_use_case_id
                }
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", "Bad request - missing required headers")
                except:
                    error_detail = "Bad request - missing required headers"
                return {"error": error_detail, "error_type": "bad_request"}
            else:
                return {"error": f"API error: {response.status_code} - {response.text}", "error_type": "api_error"}
                
    except httpx.RequestError as e:
        print(f"🚨 Connection error: {str(e)}")
        return {"error": f"Connection error: {str(e)}"}
    except Exception as e:
        print(f"🚨 Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

@cl.on_message
async def handle_message(message: cl.Message):
    """Handle incoming messages from the Chainlit interface"""

    # Check if the message is a use-case ID change command
    if message.content.startswith("/use-case "):
        new_use_case_id = message.content.replace("/use-case ", "").strip()
        if new_use_case_id:
            cl.user_session.set("use_case_id", new_use_case_id)
            await cl.Message(
                content=f"✅ **Use-Case ID Updated**\n\n"
                       f"🏷️ **New Use-Case ID**: `{new_use_case_id}`\n\n"
                       f"All subsequent chat requests will use this use-case ID.",
                author="System"
            ).send()
        else:
            await cl.Message(
                content="❌ **Invalid Command**\n\n"
                       "Please provide a use-case ID: `/use-case 100001`",
                author="System"
            ).send()
        return

    # Show current use-case ID command
    if message.content.strip() == "/current-use-case":
        current_use_case_id = cl.user_session.get("use_case_id", USE_CASE_ID)
        await cl.Message(
            content=f"🏷️ **Current Use-Case ID**: `{current_use_case_id}`\n\n"
                   f"Use `/use-case <new_id>` to change it.",
            author="System"
        ).send()
        return

    # Show allowed use-case IDs command
    if message.content.strip() == "/allowed-use-cases":
        allowed_use_cases = await get_allowed_use_cases()
        if allowed_use_cases:
            content = "**✅ Allowed Use-Case IDs:**\n\n"
            for uc_id in allowed_use_cases:
                content += f"• `{uc_id}`\n"
            content += f"\n**💡 To use one:**\n"
            content += f"Type: `/use-case <id>` (e.g., `/use-case {allowed_use_cases[0]}`)"
        else:
            content = "❌ **Unable to fetch allowed use-case IDs**\n\n" \
                     "This may indicate a connection issue or server problem. " \
                     "Please contact your administrator."

        await cl.Message(content=content, author="System").send()
        return

    # Show help command
    if message.content.strip() in ["/help", "/h"]:
        current_use_case_id = cl.user_session.get("use_case_id", USE_CASE_ID)
        await cl.Message(
            content="**🔧 Available Commands:**\n\n"
                   "• `/use-case <id>` - Change use-case ID (e.g., `/use-case 100001`)\n"
                   "• `/current-use-case` - Show current use-case ID\n"
                   "• `/allowed-use-cases` - List all allowed use-case IDs\n"
                   "• `/help` or `/h` - Show this help message\n\n"
                   f"🏷️ **Current Use-Case ID**: `{current_use_case_id}`\n\n"
                   "💬 **Regular Usage**: Just type your message to chat with Llama 3.1!",
            author="System"
        ).send()
        return

    # Get current use-case ID from session
    current_use_case_id = cl.user_session.get("use_case_id", USE_CASE_ID)

    # Show typing indicator
    async with cl.Step(name="Thinking...") as step:
        step.output = "Processing your message through the proxy..."

        # Call the chat API with current use-case ID
        result = await call_chat_api(message.content, current_use_case_id)

        if "error" in result:
            # Handle different types of errors with specific messaging
            error_type = result.get("error_type", "unknown")
            error_message = result.get("error")

            if error_type == "forbidden":
                # Special handling for 403 Forbidden errors
                use_case_id = result.get("use_case_id", current_use_case_id)

                # Try to fetch allowed use-case IDs to provide helpful suggestions
                allowed_use_cases = await get_allowed_use_cases()

                content = f"🚫 **Access Denied (403 Forbidden)**\n\n" \
                         f"❌ **Use-Case ID `{use_case_id}` is not authorized**\n\n" \
                         f"**Error Details:** {error_message}\n\n"

                if allowed_use_cases:
                    content += f"**✅ Allowed Use-Case IDs:**\n"
                    for uc_id in allowed_use_cases:
                        content += f"• `{uc_id}`\n"
                    content += f"\n**💡 Try one of the allowed IDs:**\n"
                    content += f"Type: `/use-case {allowed_use_cases[0]}` (example)\n\n"
                else:
                    content += f"**💡 What to do:**\n" \
                              f"• Check with your administrator for allowed use-case IDs\n" \
                              f"• Contact support if you believe this is an error\n\n"

                content += f"**Commands:**\n" \
                          f"• `/current-use-case` - Check your current use-case ID\n" \
                          f"• `/help` - Show all available commands"

                await cl.Message(content=content, author="System").send()
            elif error_type == "bad_request":
                await cl.Message(
                    content=f"⚠️ **Bad Request (400)**\n\n"
                           f"❌ **Error:** {error_message}\n\n"
                           f"This usually indicates a missing or invalid header. "
                           f"Please try again or contact support if the issue persists.",
                    author="System"
                ).send()
            elif error_type == "validation":
                await cl.Message(
                    content=f"📝 **Validation Error (422)**\n\n"
                           f"❌ **Error:** {error_message}\n\n"
                           f"Please check your message format and try again.",
                    author="System"
                ).send()
            else:
                # Generic error handling
                await cl.Message(
                    content=f"❌ **Error**: {error_message}",
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
                       f"🏷️ **Use Case**: {current_use_case_id}\n"
                       f"⏱️ **Processing Time**: {time_str}\n"
                       f"🔢 **Approx. Tokens**: {token_count}",
                author="Llama 3.1"
            ).send()

        step.output = "Complete!"

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    # Initialize session with default use-case ID
    cl.user_session.set("use_case_id", USE_CASE_ID)

    await cl.Message(
        content="🚀 **Welcome to the Ollama Llama 3.1 Chat Client!**\n\n"
               f"🏷️ **Current Use-Case ID**: `{USE_CASE_ID}`\n\n"
               "🧠 **Powered by**: Ollama Llama 3.1\n"
               "🔗 **Architecture**: Chainlit → FastAPI Proxy → Ollama Chat Server\n\n"
               "**💡 Quick Commands:**\n"
               "• `/use-case <new_id>` - Change use-case ID\n"
               "• `/allowed-use-cases` - List valid IDs\n"
               "• `/current-use-case` - Show current ID\n"
               "• `/help` - Show all commands\n\n"
               "💬 **Start chatting** or use commands to manage your use-case ID!",
        author="System"
    ).send()