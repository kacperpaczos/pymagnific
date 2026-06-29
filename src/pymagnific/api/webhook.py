"""FastAPI webhook receiver."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Request

from pymagnific.core.config import get_settings
from pymagnific.dependencies import get_webhook_service

router = APIRouter()


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, str]:
    service = get_webhook_service()
    body = await request.body()
    try:
        path = service.process_webhook(
            body,
            webhook_id=request.headers.get("webhook-id", ""),
            webhook_timestamp=request.headers.get("webhook-timestamp", ""),
            webhook_signature=request.headers.get("webhook-signature", ""),
        )
    except PermissionError:
        raise HTTPException(status_code=401, detail="Invalid webhook signature") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok", "saved": str(path)}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = get_settings()
    yield


app = FastAPI(title="pymagnific webhook", lifespan=lifespan)
app.include_router(router)
