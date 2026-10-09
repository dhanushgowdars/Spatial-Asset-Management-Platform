"""Reviewer-facing single-origin ASGI app (React + the assignment's REST API).

Static artifacts are built during the multi-stage Docker build. All API routes,
OpenAPI documentation, health checks, and validation logic come from aereo.api.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from aereo.api import create_app


def create_production_app(*, frontend_dir: str | Path | None = None, database_url: str | None = None) -> FastAPI:
    frontend_dir = Path(frontend_dir or os.getenv("AEREO_FRONTEND_DIR", "/srv/frontend/dist")).resolve()
    index = frontend_dir / "index.html"
    if not index.is_file():
        raise RuntimeError(f"React build missing at {index}; run the multi-stage Docker build")

    application = create_app(database_url)
    assets = frontend_dir / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="compiled-assets")
    samples = frontend_dir / "samples"
    if samples.is_dir():
        application.mount("/samples", StaticFiles(directory=samples), name="sample-inputs")

    @application.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/geospatial", status_code=307)

    @application.get("/{web_path:path}", include_in_schema=False)
    def serve_frontend(web_path: str):
        # Never mask nonexistent API paths behind the HTML app shell.
        if web_path.startswith(("api/", "assets/", "samples/")) or web_path in {
            "docs", "redoc", "openapi.json", "health"
        }:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (frontend_dir / web_path).resolve()
        if candidate.is_relative_to(frontend_dir) and candidate.is_file():
            return FileResponse(candidate)
        if web_path == "geospatial":
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Not found")

    return application
