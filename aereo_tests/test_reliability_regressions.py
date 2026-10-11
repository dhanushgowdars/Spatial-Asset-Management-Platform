"""Phase 5B: independent failure/recovery regressions, no external database."""
from __future__ import annotations

import os
import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aereo.api import create_app
from .conftest import AEREO_TEST_DEFAULTS
from .test_engine import KML


def _client(tmp_path, db_name='resilience.db'):
    return TestClient(create_app(f'sqlite:///{tmp_path / db_name}'))


def _upload(client):
    return client.post('/api/files/', files={
        'file': ('verified.kml', KML, 'application/vnd.google-earth.kml+xml'),
    })


def test_test_scoped_rate_and_cache_settings_are_stable():
    """Regression for inheriting a temporary 2-request live-probe limit."""
    for name, value in AEREO_TEST_DEFAULTS.items():
        assert os.environ[name] == value, name


def test_rejected_uploads_do_not_poison_following_valid_upload(tmp_path):
    with _client(tmp_path) as client:
        assert client.post('/api/files/', files={'file': ('bad.pdf', b'content', 'application/pdf')}).status_code == 415
        assert client.post('/api/files/', files={'file': ('bad.kml', b'not XML', 'application/xml')}).status_code == 422
        assert client.post('/api/files/', files={'file': ('empty.kml', b'', 'application/xml')}).status_code == 413
        good = _upload(client)
        assert good.status_code == 201, good.text
        assert client.get(good.json()['measurements_url']).json()['feature_count'] == 3
        assert client.get('/health').status_code == 200


def test_failed_database_commit_returns_503_then_next_upload_recovers(monkeypatch, tmp_path):
    """A failing worker-owned SQLAlchemy transaction must not poison the session."""
    real_commit = Session.commit
    calls = [0]

    def once_broken_commit(self, *args, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError('Injected single write failure — test only')
        return real_commit(self, *args, **kwargs)

    with _client(tmp_path) as client:
        with monkeypatch.context() as patch:
            patch.setattr(Session, 'commit', once_broken_commit)
            failed = _upload(client)
            assert failed.status_code == 503, failed.text
            assert failed.json()['detail'] == 'Could not store processed results'
            recovered = _upload(client)
            assert recovered.status_code == 201, recovered.text
        assert calls[0] == 2
        assert client.get(recovered.json()['measurements_url']).status_code == 200
        assert client.get('/health').status_code == 200


def test_failed_database_health_query_returns_503_then_recovers(monkeypatch, tmp_path):
    real_execute = Session.execute
    calls = [0]

    def once_broken_execute(self, *args, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError('Injected single read failure — test only')
        return real_execute(self, *args, **kwargs)

    with _client(tmp_path) as client:
        with monkeypatch.context() as patch:
            patch.setattr(Session, 'execute', once_broken_execute)
            down = client.get('/health')
            assert down.status_code == 503, down.text
            assert down.json()['detail'] == 'Database unavailable'
            healthy = client.get('/health')
            assert healthy.status_code == 200, healthy.text
            assert healthy.json() == {'status': 'healthy'}
        assert calls[0] >= 2


def test_limited_upload_does_not_block_health_or_cached_reads(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '1')
    with _client(tmp_path) as client:
        first = _upload(client)
        assert first.status_code == 201, first.text
        blocked = _upload(client)
        assert blocked.status_code == 429, blocked.text
        assert int(blocked.headers['retry-after']) >= 1
        assert client.get('/health').status_code == 200
        measurements_url = first.json()['measurements_url']
        measured = client.get(measurements_url)
        assert measured.status_code == 200
        assert client.get(measurements_url, headers={'If-None-Match': measured.headers['etag']}).status_code == 304
        assert re.fullmatch('[0-9a-f]{32}', blocked.headers['x-request-id'])
        assert 'app;dur=' in blocked.headers['server-timing']


def test_conditional_get_does_not_turn_missing_record_into_304(tmp_path):
    with _client(tmp_path) as client:
        uploaded = _upload(client)
        assert uploaded.status_code == 201, uploaded.text
        url = uploaded.json()['geojson_url']
        live = client.get(url)
        assert live.status_code == 200
        not_changed = client.get(url, headers={'If-None-Match': live.headers['etag']})
        assert not_changed.status_code == 304
        assert not_changed.content == b''
        not_found = client.get('/api/files/' + '0'*32 + '/geojson/',
                               headers={'If-None-Match': live.headers['etag']})
        assert not_found.status_code == 404
        assert client.get(url).status_code == 200


def test_upload_record_survives_app_restart_with_same_isolated_db(tmp_path):
    """A new app instance can re-read existing data; no table dropping or migration."""
    url = f'sqlite:///{tmp_path / "restart.db"}'
    with TestClient(create_app(url)) as first:
        saved = _upload(first)
        assert saved.status_code == 201, saved.text
        identifier = saved.json()['id']
        etag = first.get(saved.json()['measurements_url']).headers['etag']
    with TestClient(create_app(url)) as second:
        assert second.get('/health').status_code == 200
        response = second.get(f'/api/files/{identifier}/measurements/')
        assert response.status_code == 200
        assert response.json()['file_id'] == identifier
        assert response.headers['etag'] == etag
