"""Phase 3B: bounded synchronous analysis route execution and recovery."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from aereo.api import create_app
from .test_engine import KML


def upload(client):
    reply = client.post('/api/files/', files={
        'file': ('sample.kml', KML, 'application/vnd.google-earth.kml+xml'),
    })
    assert reply.status_code == 201, reply.text
    return reply.json()['id']


def compare(client, fid):
    return client.post('/api/analysis/compare', json={
        'baseline_file_id': fid, 'current_file_id': fid,
    })


def topology(client, fid):
    return client.post('/api/analysis/topology', json={'file_id': fid})


def routes(client, fid):
    return client.post('/api/analysis/route-zones', json={
        'route_file_id': fid, 'zone_file_id': fid,
    })


def test_phase3b_all_three_analysis_routes_preserve_200_and_contract(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_ANALYSES', '2')
    with TestClient(create_app(f'sqlite:///{tmp_path / "normal.db"}')) as client:
        fid = upload(client)
        a = compare(client, fid)
        b = topology(client, fid)
        c = routes(client, fid)
        assert a.status_code == 200, a.text
        assert b.status_code == 200, b.text
        assert c.status_code == 200, c.text
        assert 'metrics' in a.json()
        assert 'overlap_pair_count' in b.json()
        assert 'summary' in c.json()
        assert client.get('/health').status_code == 200
        assert client.get(f'/api/files/{fid}/measurements/').status_code == 200


@pytest.mark.parametrize('operation', [compare, topology, routes])
def test_phase3b_busy_analysis_503_retry_after_and_health(monkeypatch, tmp_path, operation):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_ANALYSES', '1')
    app = create_app(f'sqlite:///{tmp_path / "busy.db"}')
    with TestClient(app) as client:
        fid = upload(client)
        slots = app.state.analysis_slots
        assert slots.acquire(blocking=False)
        try:
            response = operation(client, fid)
            assert response.status_code == 503, response.text
            assert response.headers.get('retry-after') == '1'
            assert response.json()['detail'] == 'GIS analysis processing is busy; retry shortly'
            assert client.get('/health').status_code == 200
            assert client.get(f'/api/files/{fid}/measurements/').status_code == 200
        finally:
            slots.release()
        assert operation(client, fid).status_code == 200


def test_phase3b_404_releases_capacity(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_ANALYSES', '1')
    with TestClient(create_app(f'sqlite:///{tmp_path / "404.db"}')) as client:
        fid = upload(client)
        response = client.post('/api/analysis/compare', json={
            'baseline_file_id': '0'*32, 'current_file_id': fid,
        })
        assert response.status_code == 404
        assert compare(client, fid).status_code == 200


def test_phase3b_422_releases_capacity(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_ANALYSES', '1')
    with TestClient(create_app(f'sqlite:///{tmp_path / "422.db"}')) as client:
        fid = upload(client)
        point = client.post('/api/files/', files={
            'file': ('point.geojson', b'{"type":"Feature","id":"pin","properties":{},"geometry":{"type":"Point","coordinates":[76.5,12.0]}}', 'application/geo+json')
        })
        assert point.status_code == 201, point.text
        response = client.post('/api/analysis/compare', json={
            'baseline_file_id': point.json()['id'], 'current_file_id': fid,
        })
        assert response.status_code == 422, response.text
        assert compare(client, fid).status_code == 200


def test_phase3b_unexpected_exception_releases_capacity(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_ANALYSES', '1')
    import aereo.api as api
    app = create_app(f'sqlite:///{tmp_path / "error.db"}')
    with TestClient(app) as client:
        fid = upload(client)
        original = api.compare_surveys
        def explode(*args, **kwargs):
            raise RuntimeError('synthetic test error')
        with monkeypatch.context() as patch:
            patch.setattr(api, 'compare_surveys', explode)
            with pytest.raises(RuntimeError, match='synthetic test error'):
                compare(client, fid)
        assert compare(client, fid).status_code == 200


@pytest.mark.parametrize('value', ['0', '33', 'broken'])
def test_phase3b_rejects_invalid_config(monkeypatch, tmp_path, value):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_ANALYSES', value)
    with pytest.raises(ValueError, match='AEREO_MAX_CONCURRENT_ANALYSES'):
        create_app(f'sqlite:///{tmp_path / "bad.db"}')


def test_phase3b_analysis_not_charged_to_upload_rate_limit(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '1')
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_ANALYSES', '1')
    with TestClient(create_app(f'sqlite:///{tmp_path / "independent.db"}')) as client:
        fid = upload(client)
        blocked = client.post('/api/files/', files={
            'file': ('second.kml', KML, 'application/vnd.google-earth.kml+xml')
        })
        assert blocked.status_code == 429
        assert compare(client, fid).status_code == 200
        assert topology(client, fid).status_code == 200