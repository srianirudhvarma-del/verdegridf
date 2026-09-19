import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import app.state as state
from app.routes import router as api_router

logger = logging.getLogger(__name__)

TICK_INTERVAL_SECONDS = float(os.getenv("TICK_INTERVAL_SECONDS", "5"))


async def _tick_loop(interval_seconds: float) -> None:
    """Real interval loop driving Orchestrator.tick() with the real wall
    clock. tick() itself stays pure (takes `now` as a parameter) -- this
    is the one place that actually reads datetime.now() and sleeps."""
    while True:
        try:
            state.orchestrator.tick(
                datetime.now(timezone.utc),
                registry=state.telemetry_registry,
                command_queue=state.command_queue,
                action_queue=state.action_queue,
                stale_seconds=state.STALE_SECONDS,
            )
        except Exception:
            logger.exception("orchestrator tick failed")
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_tick_loop(TICK_INTERVAL_SECONDS))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Laptop Monitor API", lifespan=lifespan)

_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def read_root():
    return {"status": "Laptop Monitor API is running"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=True)
