from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.realtime import router as realtime_router
from .api.routes import router as api_router
from .core.config import get_settings
from .db import Base, engine

settings = get_settings()

app = FastAPI(
    title="AI-Powered Two-Way Calling Agent API",
    version="1.0.0",
    description="FastAPI backend for autonomous two-way AI sales calls, transcript storage and lead qualification.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(realtime_router)

from .api.twilio_routes import router as twilio_router
app.include_router(twilio_router)


@app.on_event("startup")
def create_tables_for_demo() -> None:
    Base.metadata.create_all(bind=engine)
