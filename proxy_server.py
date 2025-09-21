from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import logging
from typing import Dict, Any
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
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

# Allowlist of valid use case IDs
ALLOWED_USE_CASES = {
    "100000",
    "100050",
    "101966", 
    "102550",
    "103366"
}

# Backend server configuration
BACKEND_BASE_URL = "http://localhost:8002"  # Chat server

@app.middleware("http")
async def validate_use_case_middleware(request: Request, call_next):
    """Middleware to validate X-Use-Case-ID header"""
    
    # Skip validation for root path and docs
    if request.url.path in ["/", "/docs", "/openapi.json"]:
        response = await call_next(request)
        return response
    
    use_case_id = request.headers.get("X-Use-Case-ID")
    
    # Log the request for monitoring
    logger.info(f"Request: {request.method} {request.url.path} - Use-Case-ID: {use_case_id}")
    
    if not use_case_id:
        logger.warning(f"Rejected request: Missing X-Use-Case-ID header from {request.client.host}")
        raise HTTPException(
            status_code=400, 
            detail="Missing required header: X-Use-Case-ID"
        )
    
    if use_case_id not in ALLOWED_USE_CASES:
        logger.warning(f"Rejected request: Unauthorized use case '{use_case_id}' from {request.client.host}")
        raise HTTPException(
            status_code=403, 
            detail=f"Unauthorized use case: {use_case_id}. Allowed values: {list(ALLOWED_USE_CASES)}"
        )
    
    logger.info(f"Approved request: Use case '{use_case_id}' is authorized")
    response = await call_next(request)
    return response

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Use-Case-ID Proxy",
        "status": "running",
        "allowed_use_cases": list(ALLOWED_USE_CASES)
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "allowed_use_cases": list(ALLOWED_USE_CASES)}

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
    uvicorn.run(app, host="0.0.0.0", port=8001)