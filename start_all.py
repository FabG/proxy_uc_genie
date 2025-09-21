# start_all.py - Script to start all services
import subprocess
import time
import sys
import os

def start_service(command, name, delay=2):
    """Start a service with the given command"""
    print(f"Starting {name}...")
    proc = subprocess.Popen(command, shell=True)
    time.sleep(delay)
    return proc

def main():
    """Start all services"""
    print("🚀 Starting FastAPI Proxy System Demo...")
    
    # Start chat server
    chat_server = start_service(
        "python chat_server.py",
        "Chat Server (Port 8002)"
    )
    
    # Start proxy server  
    proxy_server = start_service(
        "python proxy_server.py", 
        "Proxy Server (Port 8001)"
    )
    
    # Start chainlit client
    chainlit_client = start_service(
        "chainlit run chainlit_app.py -w --host 0.0.0.0 --port 8000",
        "Chainlit Client (Port 8000)",
        delay=3
    )
    
    print("\n✅ All services started!")
    print("\n📍 Service URLs:")
    print("   - Chainlit Client: http://localhost:8000")
    print("   - Proxy Server: http://localhost:8001 (docs: http://localhost:8001/docs)")
    print("   - Chat Server: http://localhost:8002 (docs: http://localhost:8002/docs)")
    print("\n🧪 Test different use cases by modifying USE_CASE_ID in chainlit_app.py")
    print("   Valid IDs: 100000, 100050, 101966, 102550, 103366")
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
