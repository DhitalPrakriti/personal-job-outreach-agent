"""AI Email Automation Agent — FastAPI Application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Email Automation Agent",
    description="Intelligent email outreach automation powered by AI agents",
    version="0.1.0",
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root():
    return {"message": "AI Email Automation Agent API", "docs": "/docs"}
