import httpx
import asyncio
import json

PROXY_URL = "http://localhost:8001"

async def test_use_case(use_case_id: str, should_succeed: bool = True):
    """Test a specific use case ID"""
    
    headers = {
        "X-Use-Case-ID": use_case_id,
        "Content-Type": "application/json"
    }
    
    payload = {
        "message": f"Test message from {use_case_id}",
        "model": "llama2"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROXY_URL}/api/2.0/genie_dummy/spaces/start-conversation",
                headers=headers,
                json=payload,
                timeout=10.0
            )
            
            status = "✅ SUCCESS" if response.status_code == 200 else "❌ FAILED"
            expected = "Expected" if (response.status_code == 200) == should_succeed else "UNEXPECTED"
            
            print(f"{status} ({expected}): {use_case_id} -> {response.status_code}")
            if response.status_code != 200:
                print(f"   Error: {response.text}")
            else:
                data = response.json()
                print(f"   Response: {data.get('response', '')[:50]}...")
            
    except Exception as e:
        print(f"❌ ERROR: {use_case_id} -> {str(e)}")

async def run_tests():
    """Run comprehensive tests"""
    print("🧪 Testing FastAPI Proxy with Use-Case-ID Header Control\n")
    
    # Test valid use cases (should succeed)
    print("Testing VALID use case IDs:")
    valid_cases = ["100000", "100050", "101966", "102550", "103366"]
    for case in valid_cases:
        await test_use_case(case, should_succeed=True)
    
    print("\nTesting INVALID use case IDs:")
    # Test invalid use cases (should fail)
    invalid_cases = ["hacker-client", "unauthorized-app", ""]
    for case in invalid_cases:
        await test_use_case(case, should_succeed=False)
    
    # Test missing header
    print("\nTesting MISSING header:")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROXY_URL}/api/2.0/genie_dummy/spaces/start-conversation",
                json={"message": "test"},
                timeout=10.0
            )
            status = "❌ FAILED" if response.status_code == 400 else "❌ UNEXPECTED"
            print(f"{status}: No header -> {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ ERROR: No header -> {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_tests())