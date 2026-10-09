"""Standalone assessment API. Run: uvicorn aereo.api:app --port 18130."""
from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.services.geospatial import InvalidGeospatialUpload, process_upload
from app.services.geospatial.engine import MAX_UPLOAD_BYTES


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
    connect_args = {'check_same_thread': False} if database_url.startswith('sqlite') else {}
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    make_session = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        # Only creates the new assessment table. Never drops existing tables.
        Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    application = FastAPI(
        title='Aereo Geospatial File Measurement API',
        description='KML and zipped Shapefile measurement with transparent CRS metadata',
        version='0.1.0', lifespan=lifespan,
    )

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

    @application.post('/api/files/', status_code=201)
    async def upload_file(file: UploadFile = File(...), db: Session = Depends(session)):
        filename = file.filename or 'unknown'
        if not filename.lower().endswith(('.kml', '.zip')):
            raise HTTPException(status_code=415, detail='Upload .kml or .zip containing a Shapefile')
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        await file.close()
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail='Upload must be nonempty and <= 10 MiB')
        try:
            parsed = await run_in_threadpool(process_upload, filename, data)
        except InvalidGeospatialUpload as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        file_id = uuid4().hex
        row = UploadedGeospatialFile(
            id=file_id, filename=parsed['filename'],
            file_hash_sha256=sha256(data).hexdigest(), size_bytes=len(data),
            status=parsed['status'], source_crs=parsed['source_crs'],
            feature_count=parsed['feature_count'],
            successful_measurements=parsed['successful_measurements'],
            failed_features=parsed['failed_features'], result_json=parsed,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail='Could not store processed results') from exc
        return {
            **metadata(row),
            'file_url': f'/api/files/{file_id}/',
            'measurements_url': f'/api/files/{file_id}/measurements/',
            'geojson_url': f'/api/files/{file_id}/geojson/',
        }

    @application.get('/api/files/{file_id}/')
    def get_file(file_id: str, db: Session = Depends(session)):
        return metadata(lookup(file_id, db))

    @application.get('/api/files/{file_id}/measurements/')
    def get_measurements(file_id: str, db: Session = Depends(session)):
        row = lookup(file_id, db)
        return {
            'file_id': row.id, 'filename': row.filename,
            'crs': row.source_crs, 'feature_count': row.feature_count,
            'status': row.status, 'measurements': row.result_json['features'],
        }

    @application.get('/api/files/{file_id}/geojson/')
    def geojson(file_id: str, db: Session = Depends(session)):
        row = lookup(file_id, db)
        features = []
        for f in row.result_json['features']:
            if f['geometry'] is None:
                continue
            features.append({
                'type': 'Feature', 'id': f['id'], 'geometry': f['geometry'],
                'properties': {
                    **f['properties'], '_measurement': f['measurement'],
                    '_measurement_crs': f['measurement_crs'],
                    '_status': f['status'], '_error': f['error'],
                },
            })
        return {'type': 'FeatureCollection', 'features': features}
    return application


app = create_app()
