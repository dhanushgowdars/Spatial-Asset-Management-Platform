"""GeoInsight Phase 2B: bounded, retryable, per-app upload processing."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from fastapi.testclient import TestClient
import pytest

import aereo.api as api_module
from aereo.api import create_app
from .test_engine import KML


def _upload(client: TestClient):
    return client.post('/api/files/', files={
        'file': ('valid.kml', KML, 'application/vnd.google-earth.kml+xml'),
    })


def test_phase2b_normal_upload_and_measurements_remain_compatible(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_UPLOADS', '2')
    with TestClient(create_app(f'sqlite:///{tmp_path / "normal.db"}')) as client:
        first = _upload(client)
        second = _upload(client)
        for response in (first, second):
            assert response.status_code == 201, response.text
            record = response.json()
            assert record['feature_count'] == 3
            assert client.get(record['measurements_url']).status_code == 200
        assert first.json()['id'] != second.json()['id']


def test_phase2b_busy_upload_is_retryable_and_slot_recovers(monkeypatch, tmp_path):
    """A blocked GIS upload fills the sole slot; health remains responsive."""
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_UPLOADS', '1')
    entered = threading.Event()
    release = threading.Event()
    actual_processor = api_module.process_upload
    lock = threading.Lock()
    call_count = 0

    def controlled_processor(filename, data):
        nonlocal call_count
        with lock:
            call_count += 1
            is_first = call_count == 1
        if is_first:
            entered.set()
            if not release.wait(timeout=10):
                raise RuntimeError('Test synchronization timeout')
        return actual_processor(filename, data)

    monkeypatch.setattr(api_module, 'process_upload', controlled_processor)
    with TestClient(create_app(f'sqlite:///{tmp_path / "overload.db"}')) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(_upload, client)
            try:
                assert entered.wait(timeout=5), 'Initial GIS processing did not begin'
                # Distinguish intended admission control from other failures.
                start = time.perf_counter()
                overloaded = _upload(client)
                elapsed = time.perf_counter() - start
                assert overloaded.status_code == 503, overloaded.text
                assert overloaded.headers['retry-after'] == '1'
                assert 'busy' in overloaded.json()['detail']
                assert elapsed < 5, 'Overload response unexpectedly blocked'
                assert client.get('/health').status_code == 200
            finally:
                release.set()
            admitted = first.result(timeout=10)
            assert admitted.status_code == 201, admitted.text
        recovery = _upload(client)
        assert recovery.status_code == 201, recovery.text
        assert client.get(recovery.json()['measurements_url']).status_code == 200


@pytest.mark.parametrize('setting', ['0', '33', 'abc', '-1'])
def test_phase2b_rejects_invalid_concurrency_configuration(monkeypatch, tmp_path, setting):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_UPLOADS', setting)
    with pytest.raises(ValueError, match='AEREO_MAX_CONCURRENT_UPLOADS'):
        create_app(f'sqlite:///{tmp_path / "invalid.db"}')


def test_phase2b_parse_error_releases_slot(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_MAX_CONCURRENT_UPLOADS', '1')
    with TestClient(create_app(f'sqlite:///{tmp_path / "parse.db"}')) as client:
        rejected = client.post('/api/files/', files={
            'file': ('bad.kml', b'not valid XML', 'application/vnd.google-earth.kml+xml'),
        })
        assert rejected.status_code == 422, rejected.text
        allowed = _upload(client)
        assert allowed.status_code == 201, allowed.text
