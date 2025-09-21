from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import json
import logging
import yaml
from typing import Dict, Any
import uvicorn
from config_manager import config

# Configure logging
log_config = config.config.get('logging', {})
logging.basicConfig(
    level=getattr(logging, log_config.get('level', 'INFO')),
    format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Use-Case-ID Proxy", description="Proxy server with header-based access control")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get configuration
proxy_config = config.get_proxy_config()
security_config = config.get_security_config()
BACKEND_BASE_URL = proxy_config.get('backend_url', 'http://localhost:8002')

@app.middleware("http")
async def validate_use_case_middleware(request: Request, call_next):
    """Middleware to validate X-Use-Case-ID header"""

    try:
        # Skip validation for root path and docs
        if request.url.path in ["/", "/docs", "/openapi.json", "/config", "/config/reload"]:
            response = await call_next(request)
            return response

        use_case_id = request.headers.get("X-Use-Case-ID")

        # Log the request for monitoring
        logger.info(f"Request: {request.method} {request.url.path} - Use-Case-ID: {use_case_id}")

        if security_config.get('require_use_case_header', True) and not use_case_id:
            if security_config.get('log_rejected_requests', True):
                logger.warning(f"Rejected request: Missing X-Use-Case-ID header from {request.client.host}")
            return JSONResponse(
                status_code=400,
                content={"detail": "Missing required header: X-Use-Case-ID"}
            )

        if use_case_id and not config.is_use_case_allowed(use_case_id):
            if security_config.get('log_rejected_requests', True):
                logger.warning(f"Rejected request: Unauthorized use case '{use_case_id}' from {request.client.host}")
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Unauthorized use case: {use_case_id}. Allowed values: {config.get_allowed_use_cases()}",
                    "use_case_id": use_case_id,
                    "allowed_use_cases": config.get_allowed_use_cases()
                }
            )

        if use_case_id:
            description = config.get_use_case_description(use_case_id)
            logger.info(f"Approved request: Use case '{use_case_id}' ({description}) is authorized")

        response = await call_next(request)
        return response

    except Exception as e:
        logger.error(f"Error in use case validation middleware: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal middleware error: {str(e)}"}
        )

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Use-Case-ID Proxy",
        "status": "running",
        "allowed_use_cases": config.get_allowed_use_cases(),
        "backend_url": BACKEND_BASE_URL
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "allowed_use_cases": config.get_allowed_use_cases()}

@app.get("/config")
async def get_config():
    """Get current configuration (for debugging)"""
    return {
        "allowed_use_cases": config.get_allowed_use_cases(),
        "use_case_descriptions": {
            case: config.get_use_case_description(case) 
            for case in config.get_allowed_use_cases()
        },
        "security_config": config.get_security_config(),
        "backend_url": BACKEND_BASE_URL
    }

@app.post("/config/reload")
async def reload_config():
    """Reload configuration from file"""
    try:
        config.reload_config()
        return {
            "status": "success", 
            "message": "Configuration reloaded",
            "allowed_use_cases": config.get_allowed_use_cases()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reloading config: {str(e)}")

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(request: Request, path: str):
    """Proxy all requests to the backend server"""
    
    target_url = f"{BACKEND_BASE_URL}/{path}"
    
    # Prepare headers (forward all headers from client)
    headers = dict(request.headers)
    # Remove host header to avoid conflicts
    headers.pop("host", None)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Forward the request to backend
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=await request.body()
            )
            
            logger.info(f"Proxied to: {target_url} - Status: {response.status_code}")
            
            # Return the response from backend
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
    except httpx.RequestError as e:
        logger.error(f"Error proxying request to {target_url}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Backend service unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    proxy_config = config.get_proxy_config()
    uvicorn.run(
        app, 
        host=proxy_config.get('host', '0.0.0.0'), 
        port=proxy_config.get('port', 8001)
    )
