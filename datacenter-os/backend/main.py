import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router
import uvicorn

from shared.scheduler_driver import tick

logger = logging.getLogger(__name__)

# Phase 8c: how often the periodic driver ticks (carbonclock deadline
# force-runs, idlehunter wake confirmations). Configurable; 5-10s is sane
# for the 30-60s telemetry cadence this whole codebase otherwise assumes.
SCHEDULER_TICK_INTERVAL_SECONDS = float(os.getenv("SCHEDULER_TICK_INTERVAL_SECONDS", "5"))


async def _scheduler_driver_loop(interval_seconds: float) -> None:
    """
    Real interval loop driving shared.scheduler_driver.tick() with the
    real wall clock. tick() itself stays pure (takes `now` as a
    parameter) -- this is the one place that actually reads
    datetime.now() and sleeps.
    """
    while True:
        try:
            tick(datetime.now(timezone.utc))
        except Exception:
            logger.exception("scheduler driver tick failed")
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    driver_task = asyncio.create_task(_scheduler_driver_loop(SCHEDULER_TICK_INTERVAL_SECONDS))
    try:
        yield
    finally:
        driver_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await driver_task


app = FastAPI(title="DatacenterOS API", lifespan=lifespan)

# Allowed origins come from the CORS_ORIGINS env var (comma-separated),
# defaulting to the local Vite dev server. Set this explicitly in
# production instead of relying on the default.
# Note: this API doesn't set cookies, so allow_credentials stays False.
# ("*" combined with allow_credentials=True is also rejected by browsers.)
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

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
    return {"status": "DatacenterOS API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
