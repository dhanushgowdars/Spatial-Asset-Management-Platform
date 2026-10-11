"""Standalone assessment API. Run: uvicorn aereo.api:app --port 18130."""
from __future__ import annotations
import asyncio
from collections import OrderedDict, deque
from contextlib import asynccontextmanager, contextmanager
from math import ceil
from threading import BoundedSemaphore, Lock
import time
from datetime import datetime, timezone
from hashlib import sha256
import os
import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from aereo.response_cache import BoundedResponseCache, conditional_json_response
from aereo.request_telemetry import RequestTelemetryMiddleware
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.services.geospatial import InvalidGeospatialUpload, process_upload
from app.services.geospatial.engine import MAX_UPLOAD_BYTES
from app.services.geospatial.quality import build_quality_report
from app.services.geospatial.reporting import build_summary, build_geojson, build_csv
from app.services.geospatial.verification_report import build_verification_report
from app.services.geospatial.pdf_survey_report import render_pdf_verification_report
from app.services.geospatial.spatial_intelligence import (
    AnalysisValidationError, compare_surveys, topology_report, route_zone_report,
)


class CompareSurveysRequest(BaseModel):
    baseline_file_id: str
    current_file_id: str


class TopologyRequest(BaseModel):
    file_id: str
    reference_file_id: str | None = None


class RouteZoneRequest(BaseModel):
    route_file_id: str
    zone_file_id: str


class Base(DeclarativeBase):
    pass


class UploadedGeospatialFile(Base):
    __tablename__ = 'aereo_geospatial_files'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_crs: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    successful_measurements: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_features: Mapped[int] = mapped_column(Integer, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def metadata(row: UploadedGeospatialFile) -> dict:
    return {
        'id': row.id, 'filename': row.filename, 'size_bytes': row.size_bytes,
        'sha256': row.file_hash_sha256, 'feature_count': row.feature_count,
        'crs': row.source_crs, 'status': row.status,
        'successful_measurements': row.successful_measurements,
        'failed_features': row.failed_features,
        'created_at': row.created_at.isoformat(),
    }


def create_app(database_url: str | None = None) -> FastAPI:
    database_url = database_url or os.getenv('AEREO_DATABASE_URL')
    if not database_url:
        Path('.aereo').mkdir(parents=True, exist_ok=True)
        database_url = 'sqlite:///./.aereo/measurements.sqlite3'
    # Configured separately per server process; valid range 1 to 32.
    raw_upload_limit = os.getenv('AEREO_MAX_CONCURRENT_UPLOADS', '4')
    try:
        max_gis_uploads = int(raw_upload_limit)
    except ValueError as exc:
        raise ValueError('AEREO_MAX_CONCURRENT_UPLOADS must be an integer from 1 to 32') from exc
    if not (1 <= max_gis_uploads <= 32):
        raise ValueError('AEREO_MAX_CONCURRENT_UPLOADS must be between 1 and 32')
    # Phase 3A limits request arrivals, separately from GIS concurrency slots.
    # Defaults deliberately permit lightweight reviewer exploration.
    def bounded_integer_setting(name: str, default: str, low: int, high: int) -> int:
        raw = os.getenv(name, default)
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f'{name} must be an integer from {low} to {high}') from exc
        if not low <= value <= high:
            raise ValueError(f'{name} must be between {low} and {high}')
        return value

    upload_rate_limit = bounded_integer_setting(
        'AEREO_UPLOAD_REQUESTS_PER_WINDOW', '120', 1, 10000,
    )
    upload_rate_window = bounded_integer_setting(
        'AEREO_UPLOAD_RATE_WINDOW_SECONDS', '60', 1, 3600,
    )
    upload_rate_lock = Lock()
    # Oldest clients can be evicted when memory cap is reached. Peer identity is
    # the ASGI request client, never untrusted user-submitted X-Forwarded-For.
    upload_rate_hits: OrderedDict[str, deque[float]] = OrderedDict()
    max_upload_rate_clients = 4096
    # Shared by compare, topology and route-zones within this app process.
    # This is concurrency protection, not a global or per-IP rate limit.
    max_analysis_jobs = bounded_integer_setting(
        'AEREO_MAX_CONCURRENT_ANALYSES', '4', 1, 32,
    )
    analysis_slots = BoundedSemaphore(max_analysis_jobs)
    connect_args = {'check_same_thread': False} if database_url.startswith('sqlite') else {}
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    make_session = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        # Only creates the new assessment table. Never drops existing tables.
        Base.metadata.create_all(bind=engine)
        # A fresh semaphore per application lifespan avoids reuse across event loops.
        application.state.gis_upload_slots = asyncio.Semaphore(max_gis_uploads)
        yield
        engine.dispose()

    application = FastAPI(
        title='Aereo Geospatial File Measurement API',
        description='KML, zipped Shapefile, GeoJSON and KMZ measurement with transparent CRS and quality diagnostics',
        version='0.1.0', lifespan=lifespan,
    )

    # Support direct TestClient calls that do not enter application lifespan.
    application.state.gis_upload_slots = asyncio.Semaphore(max_gis_uploads)
    # Injectable clock permits deterministic boundary tests without sleeping.
    application.state.upload_rate_clock = time.monotonic
    application.state.analysis_slots = analysis_slots
    response_cache = BoundedResponseCache(
        max_entries=bounded_integer_setting('AEREO_RESPONSE_CACHE_MAX_ENTRIES', '32', 0, 256),
        max_bytes=bounded_integer_setting('AEREO_RESPONSE_CACHE_MAX_BYTES', '33554432', 0, 134217728),
        max_item_bytes=bounded_integer_setting('AEREO_RESPONSE_CACHE_MAX_ITEM_BYTES', '4194304', 1024, 16777216),
        ttl_seconds=bounded_integer_setting('AEREO_RESPONSE_CACHE_TTL_SECONDS', '60', 1, 3600),
    )
    application.state.response_cache = response_cache


    @application.middleware('http')
    async def rate_limit_upload_requests(request: Request, call_next):
        if request.method == 'POST' and request.scope.get('path') == '/api/files/':
            # ASGI client address may be populated by a *trusted* proxy. Do not
            # inspect raw X-Forwarded-For/Real-IP headers in application code.
            peer = request.client.host if request.client else 'unknown'
            now = application.state.upload_rate_clock()
            retry_after = None
            with upload_rate_lock:
                visits = upload_rate_hits.get(peer)
                if visits is None:
                    if len(upload_rate_hits) >= max_upload_rate_clients:
                        upload_rate_hits.popitem(last=False)
                    visits = deque()
                    upload_rate_hits[peer] = visits
                else:
                    upload_rate_hits.move_to_end(peer)
                while visits and now - visits[0] >= upload_rate_window:
                    visits.popleft()
                if len(visits) >= upload_rate_limit:
                    retry_after = max(1, ceil(visits[0] + upload_rate_window - now))
                else:
                    visits.append(now)
            if retry_after is not None:
                return JSONResponse(
                    {'detail': 'Upload rate limit exceeded; retry later'},
                    status_code=429,
                    headers={'Retry-After': str(retry_after)},
                )
        return await call_next(request)

    # Telemetry must wrap the upload rate limiter, including its early 429 returns.
    application.add_middleware(RequestTelemetryMiddleware)

    @contextmanager
    def analysis_capacity():
        # Runs inside FastAPI's sync-route worker. Never block the event loop.
        acquired = analysis_slots.acquire(timeout=1.0)
        if not acquired:
            raise HTTPException(
                status_code=503,
                detail='GIS analysis processing is busy; retry shortly',
                headers={'Retry-After': '1'},
            )
        try:
            yield
        finally:
            analysis_slots.release()

    def session():
        with make_session() as db:
            yield db

    def lookup(file_id: str, db: Session) -> UploadedGeospatialFile:
        if len(file_id) != 32 or any(ch not in '0123456789abcdef' for ch in file_id.lower()):
            raise HTTPException(status_code=404, detail='File not found')
        row = db.get(UploadedGeospatialFile, file_id)
        if row is None:
            raise HTTPException(status_code=404, detail='File not found')
        return row

    @application.get('/health')
    def health(db: Session = Depends(session)):
        try:
            db.execute(select(func.count()).select_from(UploadedGeospatialFile)).scalar()
        except Exception as exc:
            raise HTTPException(status_code=503, detail='Database unavailable') from exc
        return {'status': 'healthy'}

    def persist_uploaded_file(data: bytes, parsed: dict) -> dict:
        """Own the SQLAlchemy session entirely inside a worker thread."""
        file_id = uuid4().hex
        row = UploadedGeospatialFile(
            id=file_id, filename=parsed['filename'],
            file_hash_sha256=sha256(data).hexdigest(), size_bytes=len(data),
            status=parsed['status'], source_crs=parsed['source_crs'],
            feature_count=parsed['feature_count'],
            successful_measurements=parsed['successful_measurements'],
            failed_features=parsed['failed_features'], result_json=parsed,
        )
        with make_session() as db:
            db.add(row)
            try:
                db.commit()
                db.refresh(row)
            except Exception as exc:
                db.rollback()
                raise HTTPException(status_code=503, detail='Could not store processed results') from exc
            saved_metadata = metadata(row)
        return {
            **saved_metadata,
            'file_url': f'/api/files/{file_id}/',
            'measurements_url': f'/api/files/{file_id}/measurements/',
            'geojson_url': f'/api/files/{file_id}/geojson/',
            'quality_url': f'/api/files/{file_id}/quality/',
            'summary_url': f'/api/files/{file_id}/summary/',
            'export_url': f'/api/files/{file_id}/export/',
        }

    @application.post('/api/files/', status_code=201)
    async def upload_file(file: UploadFile = File(...)):
        filename = file.filename or 'unknown'
        if not filename.lower().endswith(('.kml', '.zip', '.geojson', '.kmz')):
            raise HTTPException(status_code=415, detail='Upload .kml, .zip containing a Shapefile, .geojson or .kmz')
        # Bound in-flight CPU processing and DB persistence together. The wait
        # is intentionally short: no unbounded backlog of expensive jobs.
        try:
            await asyncio.wait_for(application.state.gis_upload_slots.acquire(), timeout=1.0)
        except asyncio.TimeoutError as exc:
            await file.close()
            raise HTTPException(
                status_code=503,
                detail='GIS upload processing is busy; retry shortly',
                headers={'Retry-After': '1'},
            ) from exc
        try:
            data = await file.read(MAX_UPLOAD_BYTES + 1)
            await file.close()
            if not data or len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail='Upload must be nonempty and <= 10 MiB')
            try:
                parsed = await run_in_threadpool(process_upload, filename, data)
            except InvalidGeospatialUpload as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            return await run_in_threadpool(persist_uploaded_file, data, parsed)
        finally:
            application.state.gis_upload_slots.release()

    @application.get('/api/files/{file_id}/')
    def get_file(file_id: str, db: Session = Depends(session)):
        return metadata(lookup(file_id, db))

    def cached_json_result(kind: str, file_id: str, request: Request, db: Session) -> Response:
        # Upload records are immutable in this API; cache entries expire after TTL.
        # Never return 304 for a nonexistent/unrecognized ID.
        key = (kind, file_id)
        item = response_cache.get(key)
        if item is None:
            row = lookup(file_id, db)
            if kind == 'measurements':
                payload = {
                    'file_id': row.id, 'filename': row.filename,
                    'crs': row.source_crs, 'feature_count': row.feature_count,
                    'status': row.status, 'measurements': row.result_json['features'],
                }
            elif kind == 'geojson':
                payload = build_geojson(row.result_json)
            else:
                raise RuntimeError('Unknown cached response type')
            # JSONResponse uses Starlette's JSON encoding just like FastAPI's
            # previous plain-dict return, preserving the response JSON contract.
            item = response_cache.build(JSONResponse(content=payload).body)
            cached = response_cache.put(key, item)
            cache_status = 'MISS' if cached else 'BYPASS'
        else:
            cache_status = 'HIT'
        return conditional_json_response(
            item, request.headers.get('if-none-match'), cache_status=cache_status,
        )

    @application.get('/api/files/{file_id}/measurements/')
    def get_measurements(file_id: str, request: Request, db: Session = Depends(session)):
        return cached_json_result('measurements', file_id, request, db)

    @application.get('/api/files/{file_id}/quality/')
    def get_quality(file_id: str, db: Session = Depends(session)):
        row = lookup(file_id, db)
        return build_quality_report(row.result_json, file_id=row.id)

    @application.get('/api/files/{file_id}/summary/')
    def get_summary(file_id: str, db: Session = Depends(session)):
        row = lookup(file_id, db)
        return build_summary(row.result_json, file_id=row.id)

    @application.get('/api/files/{file_id}/geojson/')
    def geojson(file_id: str, request: Request, db: Session = Depends(session)):
        return cached_json_result('geojson', file_id, request, db)

    @application.get('/api/files/{file_id}/verification-report.pdf')
    def download_pdf_verification_report(file_id: str, db: Session = Depends(session)):
        """Download PDF assembled from persisted report data, without GIS recalculation."""
        row = lookup(file_id, db)
        report = build_verification_report(row)
        try:
            payload = render_pdf_verification_report(report)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(content=payload, media_type='application/pdf', headers={
            'Content-Disposition': f'attachment; filename="geoinsight-survey-{row.id}.pdf"',
            'X-Content-Type-Options': 'nosniff',
            'Cache-Control': 'no-store',
        })

    @application.get('/api/files/{file_id}/verification-report/')
    def download_verification_report(file_id: str, db: Session = Depends(session)):
        """Download a deterministic audit summary of this persisted measurement.

        The report does not rerun GIS calculations or certify survey accuracy.
        """
        row = lookup(file_id, db)
        report = build_verification_report(row)
        body = json.dumps(report, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode('utf-8')
        return Response(content=body, media_type='application/json', headers={
            'Content-Disposition': f'attachment; filename="geoinsight-verification-{row.id}.json"',
            'X-Content-Type-Options': 'nosniff',
            'Cache-Control': 'no-store',
        })

    @application.get('/api/files/{file_id}/export/')
    def export(file_id: str, format: str = 'csv', db: Session = Depends(session)):
        row = lookup(file_id, db)
        if format == 'csv':
            return Response(
                build_csv(row.result_json), media_type='text/csv; charset=utf-8',
                headers={'Content-Disposition': 'attachment; filename="geoinsight-measurements.csv"',
                         'X-Content-Type-Options': 'nosniff'},
            )
        if format == 'geojson':
            return Response(
                json.dumps(build_geojson(row.result_json), ensure_ascii=False, allow_nan=False),
                media_type='application/geo+json',
                headers={'Content-Disposition': 'attachment; filename="geoinsight-features.geojson"',
                         'X-Content-Type-Options': 'nosniff'},
            )
        raise HTTPException(status_code=422, detail='Export format must be csv or geojson')
    @application.post('/api/analysis/compare')
    def compare_survey_files(request: CompareSurveysRequest, db: Session = Depends(session)):
        """Compare persisted polygon footprints, not untrusted inline coordinates."""
        with analysis_capacity():
            baseline = lookup(request.baseline_file_id, db)
            current = lookup(request.current_file_id, db)
            try:
                return compare_surveys(baseline.result_json, current.result_json,
                                       baseline_id=baseline.id, current_id=current.id)
            except AnalysisValidationError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post('/api/analysis/topology')
    def assess_topology(request: TopologyRequest, db: Session = Depends(session)):
        with analysis_capacity():
            survey = lookup(request.file_id, db)
            reference = lookup(request.reference_file_id, db) if request.reference_file_id else None
            try:
                return topology_report(survey.result_json, file_id=survey.id,
                                       reference_data=reference.result_json if reference else None,
                                       reference_id=reference.id if reference else None)
            except AnalysisValidationError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post('/api/analysis/route-zones')
    def route_zones(request: RouteZoneRequest, db: Session = Depends(session)):
        with analysis_capacity():
            routes = lookup(request.route_file_id, db)
            zones = lookup(request.zone_file_id, db)
            try:
                return route_zone_report(routes.result_json, zones.result_json,
                                         route_id=routes.id, zone_id=zones.id)
            except AnalysisValidationError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    return application


app = create_app()
