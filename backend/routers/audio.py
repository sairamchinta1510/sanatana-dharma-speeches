import logging
from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import StreamingResponse, Response
import httpx

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/audio-proxy")
async def audio_proxy(url: str = Query(...), request: Request = None):
    """Stream archive.org audio through the backend.

    Archive.org CDN nodes sometimes reject direct browser requests.
    Proxying server-side (where requests always succeed) guarantees playback.
    Passes through Range headers so browser seeking works correctly.
    """
    req_headers = {}
    range_header = request.headers.get("Range") if request else None
    if range_header:
        req_headers["Range"] = range_header

    try:
        client = httpx.AsyncClient(follow_redirects=True, timeout=30)
        r = await client.send(
            client.build_request("GET", url, headers=req_headers),
            stream=True,
        )

        resp_headers = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        }
        for h in ("content-length", "content-range"):
            if h in r.headers:
                resp_headers[h] = r.headers[h]

        async def stream():
            try:
                async for chunk in r.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await r.aclose()
                await client.aclose()

        return StreamingResponse(
            stream(),
            status_code=r.status_code,
            media_type=r.headers.get("content-type", "audio/mpeg"),
            headers=resp_headers,
        )
    except Exception as e:
        logger.error("Audio proxy error for %s: %s", url, e)
        raise HTTPException(status_code=502, detail="Could not fetch audio")
