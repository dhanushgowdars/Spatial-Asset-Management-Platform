"""Phase 5A regression tests: request identity, response timing and safe logs."""
from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from aereo.api import create_app
from aereo.request_telemetry import LOG
from .test_engine import KML

ID = re.compile(r'^[0-9a-f]{32}$')
TIMING = re.compile(r'^app;dur=\d+(?:\.\d+)?$')


def client_for(tmp_path):
    return TestClient(create_app(f'sqlite:///{tmp_path / "telemetry.db"}'))


@pytest.mark.parametrize('path,expected', [
    ('/health', 200), ('/docs', 200), ('/openapi.json', 200),
    ('/api/files/' + '0' * 32 + '/', 404),
])
def test_status_and_request_headers(tmp_path, path, expected):
    with client_for(tmp_path) as client:
        response = client.get(path)
        assert response.status_code == expected
        assert ID.fullmatch(response.headers['x-request-id'])
        assert TIMING.fullmatch(response.headers['server-timing'])


def test_request_id_unique_and_untrusted_header_not_reflected(tmp_path):
    with client_for(tmp_path) as client:
        first = client.get('/health', headers={'X-Request-ID': 'private-user-tag'})
        second = client.get('/health', headers={'X-Request-ID': 'private-user-tag'})
        assert first.headers['x-request-id'] != second.headers['x-request-id']
        assert 'private-user-tag' not in str(first.headers)


def test_unknown_url_query_and_identifier_not_logged(tmp_path):
    with patch.object(LOG, 'log') as record:
        with client_for(tmp_path) as client:
            r = client.get('/unknown/confidential-path?token=should-never-log')
            assert r.status_code == 404
    events = [json.loads(args[0][1]) for args in record.call_args_list]
    assert events
    event = events[-1]
    assert event['route'] == '[unmatched]'
    assert event['status_code'] == 404
    assert event['request_id'] == r.headers['x-request-id']
    assert 'confidential-path' not in str(events)
    assert 'should-never-log' not in str(events)


def test_valid_upload_persistence_and_route_template_log(tmp_path):
    with patch.object(LOG, 'log') as record:
        with client_for(tmp_path) as client:
            up = client.post('/api/files/', files={'file': ('synthetic.kml', KML, 'application/vnd.google-earth.kml+xml')})
            assert up.status_code == 201, up.text
            result = client.get(up.json()['measurements_url'])
            assert result.status_code == 200
            assert result.json()['feature_count'] == 3
            assert ID.fullmatch(result.headers['x-request-id'])
    events = [json.loads(args[0][1]) for args in record.call_args_list]
    assert [e['route'] for e in events] == ['/api/files/', '/api/files/{file_id}/measurements/']
    assert up.json()['id'] not in str(events)
    assert 'synthetic.kml' not in str(events)


def test_etag_conditional_response_still_has_identifiers(tmp_path):
    with client_for(tmp_path) as client:
        up = client.post('/api/files/', files={'file': ('synthetic.kml', KML, 'application/vnd.google-earth.kml+xml')})
        assert up.status_code == 201
        path = up.json()['measurements_url']
        first = client.get(path)
        assert first.status_code == 200
        etag = first.headers['etag']
        conditional = client.get(path, headers={'If-None-Match': etag})
        assert conditional.status_code == 304
        assert conditional.content == b''
        assert conditional.headers['etag'] == etag
        assert ID.fullmatch(conditional.headers['x-request-id'])
        assert conditional.headers['x-request-id'] != first.headers['x-request-id']
        assert TIMING.fullmatch(conditional.headers['server-timing'])


def test_rejected_upload_response_has_request_id(tmp_path):
    with client_for(tmp_path) as client:
        rejected = client.post('/api/files/', files={'file': ('wrong.pdf', b'data', 'application/pdf')})
        assert rejected.status_code == 415
        assert ID.fullmatch(rejected.headers['x-request-id'])


def test_log_contains_only_documented_fields(tmp_path):
    with patch.object(LOG, 'log') as record:
        with client_for(tmp_path) as client:
            assert client.get('/health').status_code == 200
    assert record.called
    evt = json.loads(record.call_args[0][1])
    assert set(evt) == {'event', 'request_id', 'method', 'route', 'status_code', 'duration_ms'}
    assert evt['event'] == 'http_request'
    assert evt['route'] == '/health'
    assert evt['method'] == 'GET'
    assert isinstance(evt['duration_ms'], (int, float)) and evt['duration_ms'] >= 0


def test_separate_app_instances_generate_unique_ids(tmp_path):
    with client_for(tmp_path) as first, client_for(tmp_path) as second:
        a = first.get('/health')
        b = second.get('/health')
        assert a.status_code == b.status_code == 200
        assert a.headers['x-request-id'] != b.headers['x-request-id']
