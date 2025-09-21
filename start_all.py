import subprocess
import time
import sys
import os
from config_manager import config
import ollama

def is_llama3_1_running():
    try:
        # Attempt to get a response from llama3.1
        response = ollama.chat(model='llama3.1', messages=[
            {'role': 'user', 'content': 'Hello'}
        ])
        # If a response is received, the model is likely running and accessible
        return True
    except ollama.ResponseError as e:
        # Handle specific Ollama errors, e.g., model not found or server not running
        print(f"Ollama error: {e}")
        return False
    except Exception as e:
        # Handle other potential connection or general errors
        print(f"An unexpected error occurred: {e}")
        return False


def start_service(command, name, delay=2):
    """Start a service with the given command"""
    print(f"Starting {name}...")
    proc = subprocess.Popen(command, shell=True)
    time.sleep(delay)
    return proc

def main():
    """Start all services"""
    print("🚀 Starting FastAPI Proxy System Demo...")
    print("Checking if Ollama run llama3.1 is running...")

    if is_llama3_1_running():
        print("✅ Ollama run llama3.1 appears to be running.")

    else:
        print("❌ Ollama run llama3.1 does not appear to be running or accessible.")
        print("📝 Setup instructions:")
        print("   1. (if not done already) Install Ollama: https://ollama.ai")
        print("   2. (if not done already) Start Ollama: ollama serve")
        print("   3. (if not done already) Pull Llama 3.1: ollama pull llama3.1")
        print("   4. Run Llama 3.1: ollama run llama3.1")
        sys.exit("Please start Ollama run llama3.1 and try again.")
        

    # Get configuration
    proxy_config = config.get_proxy_config()
    chat_config = config.get_chat_server_config()
    chainlit_config = config.get_chainlit_config()
    
    # Start chat server
    chat_server = start_service(
        "python chat_server.py",
        f"Chat Server (Port {chat_config.get('port', 8002)})"
    )
    
    # Start proxy server  
    proxy_server = start_service(
        "python proxy_server.py", 
        f"Proxy Server (Port {proxy_config.get('port', 8001)})"
    )
    
    # Start chainlit client
    chainlit_client = start_service(
        f"chainlit run chainlit_app.py -w --host {chainlit_config.get('host', '0.0.0.0')} --port {chainlit_config.get('port', 8000)}",
        f"Chainlit Client (Port {chainlit_config.get('port', 8000)})",
        delay=3
    )
    
    print("\n✅ All services started!")
    print("\n📍 Service URLs:")
    print(f"   - Chainlit Client: http://localhost:{chainlit_config.get('port', 8000)}")
    print(f"   - Proxy Server: http://localhost:{proxy_config.get('port', 8001)} (docs: http://localhost:{proxy_config.get('port', 8001)}/docs)")
    print(f"   - Chat Server: http://localhost:{chat_config.get('port', 8002)} (docs: http://localhost:{chat_config.get('port', 8002)}/docs)")
    print(f"\n📋 Current allowed use cases: {', '.join(config.get_allowed_use_cases())}")
    print("\n🔧 Configuration Management:")
    print("   - Edit config.yaml to change allowed use cases")
    print(f"   - POST to http://localhost:{proxy_config.get('port', 8001)}/config/reload to reload config")
    print(f"   - GET http://localhost:{proxy_config.get('port', 8001)}/config to view current config")
    print("\n❌ To stop all services, press Ctrl+C")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        chat_server.terminate()
        proxy_server.terminate() 
        chainlit_client.terminate()
        print("✅ All services stopped!")

if __name__ == "__main__":
    main()