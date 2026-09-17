from fastapi import FastAPI


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