from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import APIKeyHeader
from mcp.server.sse import SseServerTransport

from .config import settings
from .mcp_server import mcp
from . import qdrant_client as db

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Depends(api_key_header)) -> None:
    if not key or key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.ensure_collection()
    db.get_model()  # warm up the embedding model on startup
    yield


app = FastAPI(title="brain-mcp", lifespan=lifespan)

sse_transport = SseServerTransport("/mcp/messages")


@app.get("/mcp/sse", dependencies=[Depends(require_api_key)])
async def handle_sse(request: Request):
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp._mcp_server.run(
            streams[0],
            streams[1],
            mcp._mcp_server.create_initialization_options(),
        )


@app.post("/mcp/messages", dependencies=[Depends(require_api_key)])
async def handle_messages(request: Request):
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)
