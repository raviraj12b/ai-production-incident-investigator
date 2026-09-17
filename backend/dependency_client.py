import httpx


DEPENDENCY_BASE_URL = "http://127.0.0.1:8001"
REQUEST_TIMEOUT_SECONDS = 2.0


async def fetch_dependency_data(request_id: str,):
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS
    ) as client:
        response = await client.get(
            f"{DEPENDENCY_BASE_URL}/data",
            headers={
                "X-Request-ID": request_id,
            },
        )

        response.raise_for_status()

        return response.json()