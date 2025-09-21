import subprocess
import time
import sys
import os
from config_manager import config

def start_service(command, name, delay=2):
    """Start a service with the given command"""
    print(f"Starting {name}...")
    proc = subprocess.Popen(command, shell=True)
    time.sleep(delay)
    return proc

def main():
    """Start all services"""
    print("🚀 Starting FastAPI Proxy System Demo...")
    
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