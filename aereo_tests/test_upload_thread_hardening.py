"""Regression tests for non-blocking upload persistence in GeoInsight Phase 2A."""
from concurrent.futures import ThreadPoolExecutor
import threading

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import aereo.api as api_module
from aereo.api import create_app
from .test_engine import KML


def test_upload_database_commit_runs_outside_event_loop(tmp_path, monkeypatch):
    """A sync ORM commit must not execute on the async request's event-loop thread."""
    event_loop_thread_ids = set()
    commit_thread_ids = []
    original_pool = api_module.run_in_threadpool
    original_commit = Session.commit

    async def observed_pool(function, *args, **kwargs):
        event_loop_thread_ids.add(threading.get_ident())
        return await original_pool(function, *args, **kwargs)

    def observed_commit(self, *args, **kwargs):
        commit_thread_ids.append(threading.get_ident())
        return original_commit(self, *args, **kwargs)

    monkeypatch.setattr(api_module, 'run_in_threadpool', observed_pool)
    monkeypatch.setattr(Session, 'commit', observed_commit)

    with TestClient(create_app(f'sqlite:///{tmp_path / "phase2a.db"}')) as client:
        response = client.post('/api/files/', files={'file': ('valid.kml', KML, 'application/vnd.google-earth.kml+xml')})
        assert response.status_code == 201, response.text
        record = response.json()
        assert record['feature_count'] == 3
        assert client.get(record['measurements_url']).status_code == 200

    assert event_loop_thread_ids, 'Instrumentation did not capture request thread'
    assert commit_thread_ids, 'Instrumentation did not capture ORM commit'
    assert all(worker_id not in event_loop_thread_ids for worker_id in commit_thread_ids)


def test_multiple_uploads_persist_with_independent_sessions(tmp_path):
    """Separate uploads must each return accessible, distinct persistent records."""
    with TestClient(create_app(f'sqlite:///{tmp_path / "parallel.db"}')) as client:
        def send(index):
            return client.post('/api/files/', files={'file': (f'valid-{index}.kml', KML, 'application/vnd.google-earth.kml+xml')})

        with ThreadPoolExecutor(max_workers=3) as executor:
            responses = list(executor.map(send, range(3)))

        for response in responses:
            assert response.status_code == 201, response.text
        ids = [response.json()['id'] for response in responses]
        assert len(set(ids)) == 3
        for response in responses:
            record = response.json()
            result = client.get(record['measurements_url'])
            assert result.status_code == 200
            assert len(result.json()['measurements']) == 3
