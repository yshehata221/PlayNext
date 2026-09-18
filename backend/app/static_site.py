"""
Serving the built frontend from the API process.

Only used by the desktop build and by single-service deployments; in normal
development Vite serves the frontend and proxies to this API. Mounted last so
it never shadows a real route, and unknown paths fall through to index.html
because the frontend is a single-page app.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("uvicorn.error")


def mount_frontend(app: FastAPI, directory: Path) -> bool:
    index = directory / "index.html"
    if not index.exists():
        log.warning("no frontend bundle at %s - API only", directory)
        return False

    app.mount("/assets", StaticFiles(directory=directory / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request):
        # a missing API route should still look like an API error, not a web page
        if path.startswith(("auth", "library", "browse", "friends", "wishlist", "stats",
                            "recommendations", "games", "steam", "media", "docs", "openapi.json")):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = directory / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    log.info("serving frontend from %s", directory)
    return True
