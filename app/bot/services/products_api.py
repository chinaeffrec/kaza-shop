import httpx

BASE_URL = "http://app:8000"

async def fetch_products():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/products/")
        response.raise_for_status()
        return response.json()