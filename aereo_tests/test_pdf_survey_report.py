"""Phase 7B PDF endpoint: persisted-data proof, no database modifications."""
from __future__ import annotations

from hashlib import sha256

from fastapi.testclient import TestClient

from aereo.api import create_app
from app.services.geospatial.pdf_survey_report import render_pdf_verification_report, clean, fmt
from .test_engine import KML, make_zip


def _upload(client, name='sample.kml', data=KML, mime='application/vnd.google-earth.kml+xml'):
    response = client.post('/api/files/', files={'file': (name, data, mime)})
    assert response.status_code == 201, response.text
    return response.json()['id']


def _pdf(client, file_id):
    return client.get(f'/api/files/{file_id}/verification-report.pdf')


def test_pdf_returns_downloadable_bytes_and_correct_headers(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "pdf.db"}')) as client:
        file_id = _upload(client)
        response = _pdf(client, file_id)
        assert response.status_code == 200, response.text
        assert response.content.startswith(b'%PDF-')
        assert len(response.content) > 1600
        assert response.headers['content-type'].startswith('application/pdf')
        assert response.headers['content-disposition'] == f'attachment; filename="geoinsight-survey-{file_id}.pdf"'
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers.get('x-request-id')


def test_pdf_does_not_mutate_stored_results_or_json_report(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "unchanged.db"}')) as client:
        file_id = _upload(client)
        before = client.get(f'/api/files/{file_id}/verification-report/').content
        measured_before = client.get(f'/api/files/{file_id}/measurements/').content
        assert _pdf(client, file_id).status_code == 200
        assert client.get(f'/api/files/{file_id}/verification-report/').content == before
        assert client.get(f'/api/files/{file_id}/measurements/').content == measured_before
        assert client.get('/health').status_code == 200


def test_valid_polygon_and_missing_crs_both_yield_pdf(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "variety.db"}')) as client:
        polygon = _upload(client, 'plot.zip', make_zip(), 'application/zip')
        missing = _upload(client, 'no-prj.zip', make_zip(with_prj=False), 'application/zip')
        assert _pdf(client, polygon).content.startswith(b'%PDF-')
        assert _pdf(client, missing).content.startswith(b'%PDF-')
        assert client.get(f'/api/files/{missing}/verification-report/').json()['processing']['failed_features'] == 1


def test_pdf_is_readable_after_app_restart(tmp_path):
    db = f'sqlite:///{tmp_path / "restart.db"}'
    with TestClient(create_app(db)) as client:
        file_id = _upload(client)
        first = _pdf(client, file_id).content
    with TestClient(create_app(db)) as client:
        second = _pdf(client, file_id).content
    assert first.startswith(b'%PDF-') and second.startswith(b'%PDF-')
    assert first == second


def test_unknown_or_malformed_id_remains_404(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "missing.db"}')) as client:
        assert _pdf(client, '0'*32).status_code == 404
        assert _pdf(client, 'bad-file-id').status_code == 404


def test_renderer_refuses_unbounded_or_mismatched_feature_counts():
    from json import loads
    basic = {'report_type':'geoinsight_measurement_verification', 'schema_version':'1.0',
             'features':[], 'processing': {'feature_count':2}, 'provenance':{}, 'summary':{}}
    import pytest
    with pytest.raises(ValueError, match='mismatch'):
        render_pdf_verification_report(basic)
    basic['features'] = [{}] * 2001
    with pytest.raises(ValueError, match='up to'):
        render_pdf_verification_report(basic)


def test_external_properties_are_not_passed_to_pdf_builder(tmp_path, monkeypatch):
    from aereo import api as api_module
    import app.services.geospatial.pdf_survey_report as pdf_module
    original = pdf_module.render_pdf_verification_report
    seen = {}
    def capture(report):
        seen['report'] = report
        return original(report)
    monkeypatch.setattr(api_module, 'render_pdf_verification_report', capture)
    with TestClient(create_app(f'sqlite:///{tmp_path / "private.db"}')) as client:
        file_id = _upload(client)
        assert _pdf(client, file_id).status_code == 200
    assert seen['report']['provenance']['input_sha256'] == sha256(KML).hexdigest()
    assert all('properties' not in f and 'geometry' not in f for f in seen['report']['features'])


def test_html_like_filename_text_is_escaped_and_signed_zero_normalized():
    assert clean('<script>hello</script>') == '&lt;script&gt;hello&lt;/script&gt;'
    assert fmt(-0.000000000001, ' m2') == '0 m2'
    assert fmt(10000.0,' m2') == '10,000 m2'
