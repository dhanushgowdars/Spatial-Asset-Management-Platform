"""Phase 3A: upload request throttling without changing existing API contracts."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from aereo.api import create_app
from .test_engine import KML


def upload(client):
    return client.post('/api/files/', files={
        'file': ('example.kml', KML, 'application/vnd.google-earth.kml+xml'),
    })


def test_phase3a_upload_limit_429_retry_after_but_health_and_get_work(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '2')
    monkeypatch.setenv('AEREO_UPLOAD_RATE_WINDOW_SECONDS', '60')
    with TestClient(create_app(f'sqlite:///{tmp_path / "basic.db"}')) as client:
        a = upload(client)
        b = upload(client)
        blocked = upload(client)
        assert a.status_code == b.status_code == 201
        assert blocked.status_code == 429, blocked.text
        assert blocked.json()['detail'] == 'Upload rate limit exceeded; retry later'
        assert 1 <= int(blocked.headers['retry-after']) <= 60
        assert client.get('/health').status_code == 200
        assert client.get(a.json()['measurements_url']).status_code == 200


def test_phase3a_raw_x_forwarded_for_cannot_evade_rate_limit(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '1')
    app = create_app(f'sqlite:///{tmp_path / "spoof.db"}')
    with TestClient(app, client=('198.51.100.4', 50004)) as client:
        assert upload(client).status_code == 201
        response = client.post('/api/files/', headers={'X-Forwarded-For': '203.0.113.91'}, files={
            'file': ('example.kml', KML, 'application/vnd.google-earth.kml+xml'),
        })
        assert response.status_code == 429


def test_phase3a_distinct_clients_have_distinct_counters(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '1')
    app = create_app(f'sqlite:///{tmp_path / "peers.db"}')
    with TestClient(app, client=('198.51.100.10', 41000)) as a:
        assert upload(a).status_code == 201
        assert upload(a).status_code == 429
    with TestClient(app, client=('198.51.100.11', 41001)) as b:
        assert upload(b).status_code == 201


def test_phase3a_window_expires_without_sleeping(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '1')
    monkeypatch.setenv('AEREO_UPLOAD_RATE_WINDOW_SECONDS', '10')
    app = create_app(f'sqlite:///{tmp_path / "clock.db"}')
    clock = [100.0]
    app.state.upload_rate_clock = lambda: clock[0]
    with TestClient(app) as client:
        assert upload(client).status_code == 201
        assert upload(client).status_code == 429
        clock[0] += 10.0
        assert upload(client).status_code == 201


@pytest.mark.parametrize('setting,value', [
    ('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '0'),
    ('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '10001'),
    ('AEREO_UPLOAD_REQUESTS_PER_WINDOW', 'not-a-number'),
    ('AEREO_UPLOAD_RATE_WINDOW_SECONDS', '3601'),
])
def test_phase3a_rejects_invalid_settings(monkeypatch, tmp_path, setting, value):
    monkeypatch.setenv(setting, value)
    with pytest.raises(ValueError, match=setting):
        create_app(f'sqlite:///{tmp_path / "invalid.db"}')
