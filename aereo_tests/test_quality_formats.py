"""C2 contract tests for RFC 7946 GeoJSON, safe KMZ and quality diagnostics."""
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from aereo.api import create_app
from app.services.geospatial import InvalidGeospatialUpload, process_upload
from app.services.geospatial.quality import build_quality_report
from .test_engine import KML
from .test_compatibility import zipped_shapes


def geojson_bytes(features):
    return json.dumps({'type': 'FeatureCollection', 'features': features}).encode('utf-8')


def feature(fid, geometry, props=None):
    return {'type': 'Feature', 'id': fid, 'properties': props or {}, 'geometry': geometry}


def kmz_bytes(paths):
    out = BytesIO()
    with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
        for name, data in paths:
            archive.writestr(name, data)
    return out.getvalue()


def test_geojson_mixed_valid_invalid_retains_original_ids_and_per_feature_failures():
    data = geojson_bytes([
        feature('parcel-17', {'type': 'Polygon', 'coordinates': [[[76, 12], [76.001, 12], [76.001, 12.001], [76, 12.001], [76, 12]]]}, {'name': 'Survey A'}),
        feature('bad-point', {'type': 'Point', 'coordinates': [181, 12]}, {'name': 'Invalid latitude or longitude'}),
        feature('inspection', {'type': 'Point', 'coordinates': [76, 12]}, {'name': 'Inspection pin'}),
    ])
    result = process_upload('survey.geojson', data)
    assert result['feature_count'] == 3
    assert result['status'] == 'COMPLETED_WITH_ERRORS'
    assert result['source_crs'] == 'EPSG:4326'
    assert result['features'][0]['id'] == 'parcel-17'
    assert result['features'][0]['properties']['name'] == 'Survey A'
    assert result['features'][0]['status'] == 'MEASURED'
    assert result['features'][0]['measurement']['value'] > 0
    assert result['features'][1]['status'] == 'FAILED'
    assert result['features'][1]['measurement'] is None
    assert result['features'][1]['geometry'] is None
    assert result['features'][2]['status'] == 'NOT_APPLICABLE'
    report = build_quality_report(result, file_id='f'*32)
    assert report['summary'] == {
        'total_features': 3, 'measured': 1, 'not_applicable': 1,
        'failed': 1, 'unsupported': 0, 'warning_features': 0,
        'error_features': 1, 'issue_count': 1,
    }
    assert report['issues'][0]['feature_id'] == 'bad-point'
    assert report['issues'][0]['code'] == 'TRANSFORM_FAILED'


def test_geojson_single_feature_and_utf8_properties():
    data = json.dumps(feature('pt-1', {'type':'Point','coordinates':[76, 12]}, {'name':'ಆಸ್ತಿ', 'survey_id': 'G-1'}), ensure_ascii=False).encode('utf-8')
    result = process_upload('survey.GEOJSON', data)
    assert result['features'][0]['properties']['name'] == 'ಆಸ್ತಿ'
    assert result['features'][0]['status'] == 'NOT_APPLICABLE'


@pytest.mark.parametrize('payload', [
    b'{bad', b'{"type":"FeatureCollection","features":{}}',
    b'{"type":"FeatureCollection","features":[]}',
    b'{"type":"FeatureCollection","features":[],"crs":{"type":"name"}}',
    b'{"type":"FeatureCollection","features":[],"x":NaN}',
    b'{"type":"Point","coordinates":[76,12]}',
])
def test_invalid_geojson_uploads_rejected(payload):
    with pytest.raises(InvalidGeospatialUpload):
        process_upload('bad.geojson', payload)


def test_geojson_malformed_feature_does_not_block_valid():
    good = feature('valid', {'type':'Point','coordinates':[76,12]})
    bad = feature('bad', {'type':'LineString','coordinates':[[76,12]]}, {'name':'broken line'})
    result = process_upload('mixed.geojson', geojson_bytes([good, bad, 123]))
    assert [f['status'] for f in result['features']] == ['NOT_APPLICABLE', 'FAILED', 'FAILED']
    assert result['failed_features'] == 2
    assert result['features'][2]['issues'][0]['code'] == 'PARSE_FAILED'


def test_kmz_single_nested_kml_uses_same_terrain_as_kml():
    zipped = kmz_bytes([('doc/data/document.kml', KML), ('images/legend.png', b'not loaded')])
    result = process_upload('survey.kmz', zipped)
    plain = process_upload('survey.kml', KML)
    assert result['feature_count'] == plain['feature_count']
    assert result['successful_measurements'] == plain['successful_measurements']
    assert [f['status'] for f in result['features']] == [f['status'] for f in plain['features']]


@pytest.mark.parametrize('paths', [
    [('readme.txt', b'no KML')],
    [('a.kml', KML), ('b.kml', KML)],
    [('../evil.kml', KML)],
    [('doc.kml', b'<!DOCTYPE kml [<!ENTITY x SYSTEM "file:///etc/passwd">]><kml>&x;</kml>')],
    [('DOC.KML', KML), ('doc.kml', KML)],
])
def test_unsafe_or_ambiguous_kmz_rejected(paths):
    with pytest.raises(InvalidGeospatialUpload):
        process_upload('bad.kmz', kmz_bytes(paths))


def test_missing_crs_yields_structured_qa_diagnostic():
    result = process_upload('no-prj.zip', zipped_shapes(include_prj=False))
    report = build_quality_report(result, file_id='x'*32)
    assert report['summary']['failed'] == 1
    assert report['issues'][0]['code'] == 'CRS_MISSING'
    assert report['issues'][0]['severity'] == 'ERROR'


def test_unknown_geometry_is_reported_without_fake_measurement():
    kml=b'''<kml><Document><Placemark><MultiGeometry><Point><coordinates>76,12</coordinates></Point><LineString><coordinates>76,12 76.01,12</coordinates></LineString></MultiGeometry></Placemark></Document></kml>'''
    result = process_upload('collection.kml', kml)
    report = build_quality_report(result, file_id='1'*32)
    assert report['summary']['unsupported'] == 1
    assert report['issues'][0]['code'] == 'UNSUPPORTED_GEOMETRY'
    assert result['features'][0]['measurement'] is None


def test_quality_endpoint_real_persistence_and_unknown_id(tmp_path):
    db_url = f'sqlite:///{tmp_path / "data.sqlite"}'
    data = geojson_bytes([
        feature('ok', {'type':'Point','coordinates':[76,12]}),
        feature('bad', {'type':'Point','coordinates':[200,12]}),
    ])
    with TestClient(create_app(db_url)) as client:
        response = client.post('/api/files/', files={'file': ('sample.geojson', data, 'application/geo+json')})
        assert response.status_code == 201, response.text
        meta = response.json()
        file_id = meta['id']
        assert meta['quality_url'] == f'/api/files/{file_id}/quality/'
        qa = client.get(meta['quality_url'])
        assert qa.status_code == 200
        assert qa.json()['summary']['failed'] == 1
        assert qa.json()['issues'][0]['feature_id'] == 'bad'
        assert client.get(f'/api/files/{file_id}/measurements/').status_code == 200
        assert len(client.get(f'/api/files/{file_id}/geojson/').json()['features']) == 1
        assert client.get('/api/files/' + '0'*32 + '/quality/').status_code == 404
        assert client.post('/api/files/', files={'file': ('payload.txt', b'bad')}).status_code == 415
    with TestClient(create_app(db_url)) as client:
        assert client.get(f'/api/files/{file_id}/quality/').json()['summary']['total_features'] == 2


def test_kmz_api_upload_and_bad_archive(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "data.sqlite"}')) as client:
        upload = client.post('/api/files/', files={'file': ('map.kmz', kmz_bytes([('doc.kml', KML)]), 'application/vnd.google-earth.kmz')})
        assert upload.status_code == 201, upload.text
        assert upload.json()['feature_count'] == 3
        bad = client.post('/api/files/', files={'file': ('bad.kmz', kmz_bytes([('../doc.kml', KML)]), 'application/zip')})
        assert bad.status_code == 422
