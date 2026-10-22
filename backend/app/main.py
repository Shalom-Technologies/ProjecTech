from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
import asyncio
import logging
from app.routes import reviews

from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection, get_database
from app.delivery import run_periodic_jobs
from app.rate_limit import limiter
from app.error_handlers import (
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler,
)
from app.routes import auth, projects, messages, conversations, notifications, ws, payments, users, invoices, support

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _background_loop():
    """Releases deliveries whose review window ended and payout holds that matured."""
    while True:
        try:
            await run_periodic_jobs(get_database())
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - one bad run must not stop the loop
            logger.exception("Background job failed")
        await asyncio.sleep(settings.BACKGROUND_JOB_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    task = asyncio.create_task(_background_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await close_mongo_connection()


app = FastAPI(title="Marketplace API", version="1.0.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Centralized error handling
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(messages.router)
app.include_router(conversations.router)
app.include_router(notifications.router)
app.include_router(ws.router)
app.include_router(payments.router)
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(invoices.router)
app.include_router(support.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "Marketplace API is running"}