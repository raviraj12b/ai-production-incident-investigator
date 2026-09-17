from fastapi import FastAPI
import httpx

from fastapi import FastAPI, HTTPException

from backend.dependency_client import fetch_dependency_data


app = FastAPI(
    title="AI Production Incident Investigator - Demo Service",
    description="Production-like service used to generate and investigate incidents.",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "service": "incident-demo-api",
        "message": "AI Production Incident Investigator demo service"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "incident-demo-api"
    }

@app.get("/inventory")
async def get_inventory():
    try:
        dependency_response = await fetch_dependency_data()

        return {
            "status": "success",
            "source": "dependency-service",
            "dependency": dependency_response
        }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Dependency service timed out"
        )

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Dependency service returned "
                f"HTTP {exc.response.status_code}"
            )
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Dependency service unavailable"
        )