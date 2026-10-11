"""Phase 4A: response correctness, conditional HTTP, bounded TTL/LRU cache."""
from __future__ import annotations

from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from aereo.api import create_app
from .test_engine import KML


def upload(client):
    response = client.post('/api/files/', files={
        'file': ('fixture.kml', KML, 'application/vnd.google-earth.kml+xml'),
    })
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_measurements_etag_roundtrip_and_original_json_contract(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "etag.db"}')) as client:
        fid = upload(client)
        url = f'/api/files/{fid}/measurements/'
        first = client.get(url)
        assert first.status_code == 200
        assert first.headers['content-type'].startswith('application/json')
        assert first.headers['cache-control'] == 'private, no-cache'
        assert first.headers['x-geoinsight-cache'] == 'MISS'
        assert first.json()['file_id'] == fid
        assert first.json()['feature_count'] == 3
        assert len(first.json()['measurements']) == 3
        etag = first.headers['etag']
        assert etag == '"sha256-' + sha256(first.content).hexdigest() + '"'
        second = client.get(url)
        assert second.status_code == 200
        assert second.headers['x-geoinsight-cache'] == 'HIT'
        assert second.content == first.content
        assert second.headers['etag'] == etag
        not_modified = client.get(url, headers={'If-None-Match': etag})
        assert not_modified.status_code == 304
        assert not_modified.content == b''
        assert not_modified.headers['etag'] == etag
        assert not_modified.headers['x-geoinsight-cache'] == 'HIT'


def test_weak_list_and_star_validators(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "weak.db"}')) as client:
        fid = upload(client)
        url = f'/api/files/{fid}/measurements/'
        etag = client.get(url).headers['etag']
        for validator in (f'W/{etag}', f'"other", W/{etag}', '*'):
            response = client.get(url, headers={'If-None-Match': validator})
            assert response.status_code == 304
            assert response.content == b''
        assert client.get(url, headers={'If-None-Match': '"does-not-match"'}).status_code == 200
        assert client.get(url, headers={'If-None-Match': 'x'*9000}).status_code == 200


def test_geojson_conditional_get_keeps_feature_data(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "geojson.db"}')) as client:
        fid = upload(client)
        url = f'/api/files/{fid}/geojson/'
        first = client.get(url)
        assert first.status_code == 200
        assert first.json()['type'] == 'FeatureCollection'
        assert len(first.json()['features']) == 3
        assert client.get(url, headers={'If-None-Match': first.headers['etag']}).status_code == 304
        assert client.get(url).json() == first.json()
        # Each endpoint retains independent cache keys.
        measurements = client.get(f'/api/files/{fid}/measurements/')
        assert measurements.headers['etag'] != first.headers['etag']


def test_missing_file_is_404_even_with_wildcard(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "missing.db"}')) as client:
        for endpoint in ('measurements', 'geojson'):
            response = client.get(f'/api/files/{"0"*32}/{endpoint}/', headers={'If-None-Match': '*'})
            assert response.status_code == 404
        assert client.get('/api/files/not-a-valid-id/measurements/').status_code == 404


def test_ttl_expiry_forces_refresh_without_sleep(tmp_path):
    app = create_app(f'sqlite:///{tmp_path / "ttl.db"}')
    app.state.response_cache.clock = lambda: 10.0
    with TestClient(app) as client:
        fid = upload(client)
        url = f'/api/files/{fid}/measurements/'
        first = client.get(url)
        assert first.headers['x-geoinsight-cache'] == 'MISS'
        assert client.get(url).headers['x-geoinsight-cache'] == 'HIT'
        app.state.response_cache.clock = lambda: 10000.0
        again = client.get(url)
        assert again.status_code == 200
        assert again.headers['x-geoinsight-cache'] == 'MISS'
        assert again.content == first.content


def test_lru_eviction_respects_entry_limit(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_RESPONSE_CACHE_MAX_ENTRIES', '1')
    app = create_app(f'sqlite:///{tmp_path / "lru.db"}')
    with TestClient(app) as client:
        one, two = upload(client), upload(client)
        url1 = f'/api/files/{one}/measurements/'
        url2 = f'/api/files/{two}/measurements/'
        assert client.get(url1).headers['x-geoinsight-cache'] == 'MISS'
        assert client.get(url1).headers['x-geoinsight-cache'] == 'HIT'
        assert client.get(url2).headers['x-geoinsight-cache'] == 'MISS'
        assert app.state.response_cache.entry_count == 1
        assert client.get(url1).headers['x-geoinsight-cache'] == 'MISS'


def test_oversized_response_bypasses_cache_but_preserves_etag(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_RESPONSE_CACHE_MAX_ITEM_BYTES', '1024')
    app = create_app(f'sqlite:///{tmp_path / "oversize.db"}')
    with TestClient(app) as client:
        fid = upload(client)
        url = f'/api/files/{fid}/measurements/'
        first = client.get(url)
        assert len(first.content) > 1024
        assert first.headers['x-geoinsight-cache'] == 'BYPASS'
        assert app.state.response_cache.entry_count == 0
        assert client.get(url).headers['x-geoinsight-cache'] == 'BYPASS'
        assert client.get(url, headers={'If-None-Match': first.headers['etag']}).status_code == 304


def test_disabled_cache_still_supports_conditional_get(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_RESPONSE_CACHE_MAX_ENTRIES', '0')
    app = create_app(f'sqlite:///{tmp_path / "disabled.db"}')
    with TestClient(app) as client:
        fid = upload(client)
        url = f'/api/files/{fid}/measurements/'
        first = client.get(url)
        assert first.headers['x-geoinsight-cache'] == 'BYPASS'
        assert app.state.response_cache.entry_count == 0
        assert client.get(url, headers={'If-None-Match': first.headers['etag']}).status_code == 304


def test_cache_is_scoped_per_app_instance(tmp_path):
    url = f'sqlite:///{tmp_path / "separate.db"}'
    with TestClient(create_app(url)) as first_client:
        fid = upload(first_client)
        assert first_client.get(f'/api/files/{fid}/measurements/').headers['x-geoinsight-cache'] == 'MISS'
        assert first_client.get(f'/api/files/{fid}/measurements/').headers['x-geoinsight-cache'] == 'HIT'
    with TestClient(create_app(url)) as second_client:
        response = second_client.get(f'/api/files/{fid}/measurements/')
        assert response.status_code == 200
        assert response.headers['x-geoinsight-cache'] == 'MISS'


def test_gets_do_not_consume_upload_rate_budget(monkeypatch, tmp_path):
    monkeypatch.setenv('AEREO_UPLOAD_REQUESTS_PER_WINDOW', '1')
    with TestClient(create_app(f'sqlite:///{tmp_path / "rate.db"}')) as client:
        fid = upload(client)
        url = f'/api/files/{fid}/measurements/'
        assert client.get(url).status_code == 200
        assert client.get(url).status_code == 200
        assert client.post('/api/files/', files={
            'file': ('second.kml', KML, 'application/vnd.google-earth.kml+xml')
        }).status_code == 429


@pytest.mark.parametrize(('name', 'value'), [
    ('AEREO_RESPONSE_CACHE_MAX_ENTRIES', '257'),
    ('AEREO_RESPONSE_CACHE_MAX_ENTRIES', '-1'),
    ('AEREO_RESPONSE_CACHE_MAX_BYTES', '-1'),
    ('AEREO_RESPONSE_CACHE_MAX_ITEM_BYTES', '32'),
    ('AEREO_RESPONSE_CACHE_TTL_SECONDS', '0'),
    ('AEREO_RESPONSE_CACHE_TTL_SECONDS', 'invalid'),
])
def test_invalid_settings_fail_explicitly(monkeypatch, tmp_path, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        create_app(f'sqlite:///{tmp_path / "invalid.db"}')
