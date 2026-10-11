"""Phase 6A: additive download report and reproducible measurement evidence."""
from __future__ import annotations

from hashlib import sha256
import json
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from aereo.api import create_app
from .test_engine import KML, make_zip


def upload(client, name: str, content: bytes, media: str):
    response = client.post('/api/files/', files={'file': (name, content, media)})
    assert response.status_code == 201, response.text
    return response.json()['id']


def report(client, fid):
    return client.get(f'/api/files/{fid}/verification-report/')


def test_downloaded_report_has_content_disposition_and_input_hash(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "one.db"}')) as client:
        fid = upload(client, 'sample.kml', KML, 'application/vnd.google-earth.kml+xml')
        response = report(client, fid)
        assert response.status_code == 200, response.text
        assert response.headers['content-type'].startswith('application/json')
        assert response.headers['content-disposition'] == f'attachment; filename="geoinsight-verification-{fid}.json"'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['cache-control'] == 'no-store'
        data = response.json()
        assert data['report_type'] == 'geoinsight_measurement_verification'
        assert data['schema_version'] == '1.0'
        assert data['provenance']['file_id'] == fid
        assert data['provenance']['input_sha256'] == sha256(KML).hexdigest()
        assert data['provenance']['input_size_bytes'] == len(KML)
        assert data['processing']['feature_count'] == 3
        assert data['processing']['successful_measurements'] == 2
        assert len(data['features']) == 3


def test_report_preserves_exact_projected_area_perimeter(tmp_path):
    content = make_zip()
    with TestClient(create_app(f'sqlite:///{tmp_path / "area.db"}')) as client:
        fid = upload(client, 'plot.zip', content, 'application/zip')
        response = report(client, fid)
        assert response.status_code == 200, response.text
        feature = response.json()['features'][0]
        assert feature['status'] == 'MEASURED'
        assert feature['measurement']['type'] == 'area'
        assert feature['measurement']['value'] == pytest.approx(10_000, abs=0.05)
        assert feature['perimeter_m'] == pytest.approx(400, abs=0.05)
        assert feature['measurement']['unit'] == 'm2'
        assert feature['measurement_crs'] == 'EPSG:32643'
        assert feature['measurement_method'] == 'projected_planar_geometry'
        assert response.json()['summary']['totals']['area_m2'] == pytest.approx(10_000, abs=0.05)


def test_report_marks_points_not_applicable_and_no_invented_measurement(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "point.db"}')) as client:
        fid = upload(client, 'sample.kml', KML, 'application/vnd.google-earth.kml+xml')
        features = report(client, fid).json()['features']
        assert features[2]['status'] == 'NOT_APPLICABLE'
        assert features[2]['measurement'] is None
        assert features[2]['measurement_crs'] is None


def test_report_discloses_missing_crs_without_fake_area(tmp_path):
    raw = make_zip(with_prj=False)
    with TestClient(create_app(f'sqlite:///{tmp_path / "nocr.db"}')) as client:
        fid = upload(client, 'missing-crs.zip', raw, 'application/zip')
        result = report(client, fid).json()
        assert result['processing']['failed_features'] == 1
        assert result['provenance']['source_crs'] is None
        assert result['features'][0]['status'] == 'FAILED'
        assert result['features'][0]['measurement'] is None
        assert 'CRS' in result['features'][0]['error']


def test_report_does_not_republish_arbitrary_input_properties_or_geometries(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "privacy.db"}')) as client:
        fid = upload(client, 'sample.kml', KML, 'application/vnd.google-earth.kml+xml')
        data = report(client, fid).json()
        assert all('properties' not in f and 'geometry' not in f for f in data['features'])
        assert 'owner' not in json.dumps(data).lower()
        assert any('not survey-grade' in note for note in data['limitations'])
        assert any('no independent recomputation' in note for note in data['limitations'])


def test_report_does_not_change_existing_measurements_or_export(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "compat.db"}')) as client:
        fid = upload(client, 'sample.kml', KML, 'application/vnd.google-earth.kml+xml')
        before = client.get(f'/api/files/{fid}/measurements/').json()
        assert report(client, fid).status_code == 200
        after = client.get(f'/api/files/{fid}/measurements/').json()
        assert before == after
        assert client.get(f'/api/files/{fid}/export/?format=csv').status_code == 200
        assert client.get(f'/api/files/{fid}/summary/').status_code == 200
        assert client.get('/health').status_code == 200


def test_report_is_deterministic_across_restarts(tmp_path):
    db = f'sqlite:///{tmp_path / "restart.db"}'
    with TestClient(create_app(db)) as client:
        fid = upload(client, 'sample.kml', KML, 'application/vnd.google-earth.kml+xml')
        first = report(client, fid).content
    with TestClient(create_app(db)) as client:
        second = report(client, fid).content
    assert first == second


def test_unknown_and_malformed_identifiers_get_404(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "missing.db"}')) as client:
        assert report(client, '0' * 32).status_code == 404
        assert report(client, 'bad-id').status_code == 404
        assert client.get('/health').status_code == 200


def test_report_uses_existing_record_and_no_new_table(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "schema.db"}')) as client:
        fid = upload(client, 'sample.kml', KML, 'application/vnd.google-earth.kml+xml')
        assert report(client, fid).json()['provenance']['file_id'] == fid
    import sqlite3
    with sqlite3.connect(tmp_path / 'schema.db') as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {'aereo_geospatial_files'}
