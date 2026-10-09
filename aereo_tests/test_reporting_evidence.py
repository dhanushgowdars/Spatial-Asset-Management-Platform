"""C3 independent metric-evidence, aggregation, export and compatibility contracts."""
from __future__ import annotations
import csv
from io import BytesIO, StringIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient
from pyproj import CRS
import shapefile

from aereo.api import create_app
from app.services.geospatial import process_upload
from app.services.geospatial.reporting import build_summary, build_csv, build_geojson
from .test_engine import KML, make_zip
from .test_compatibility import zipped_shapes


def test_projected_square_perimeter_centroid_bbox():
    entry = process_upload('plot.zip', make_zip())['features'][0]
    assert entry['measurement']['value'] == pytest.approx(10000, abs=.05)
    assert entry['evidence']['perimeter_m'] == pytest.approx(400, abs=.2)
    assert entry['evidence']['polygon_parts'] == 1
    assert entry['measurement_method'] == 'projected_planar_geometry'
    assert entry['evidence']['perimeter_method'] == 'planar_boundary_length_in_measurement_crs'
    assert len(entry['evidence']['centroid_wgs84']) == 2
    low_x, low_y, hi_x, hi_y = entry['evidence']['bbox_wgs84']
    x, y = entry['evidence']['centroid_wgs84']
    assert low_x < x < hi_x
    assert low_y < y < hi_y
    assert entry['measurement_crs'] == 'EPSG:32643'


def test_polygon_hole_perimeter_includes_inner_boundary():
    # UTM-projected Shapefile, 100x100 shell and 50x50 hole.
    shp, shx, dbf = BytesIO(), BytesIO(), BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field('NAME', 'C', 30)
    outer = [[500000, 1400000], [500000, 1400100], [500100, 1400100], [500100, 1400000], [500000, 1400000]]
    hole = [[500025, 1400025], [500075, 1400025], [500075, 1400075], [500025, 1400075], [500025, 1400025]]
    writer.poly([outer, hole]); writer.record('hole'); writer.close()
    out = BytesIO()
    with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
        for ext, handle in [('shp', shp), ('shx', shx), ('dbf', dbf)]:
            archive.writestr('survey.'+ext, handle.getvalue())
        archive.writestr('survey.prj', CRS.from_epsg(32643).to_wkt())
    entry = process_upload('hole.zip', out.getvalue())['features'][0]
    assert entry['status'] == 'MEASURED', entry
    assert entry['measurement']['value'] == pytest.approx(7500, abs=.05)
    assert entry['evidence']['perimeter_m'] == pytest.approx(600, abs=.2)


def test_kml_line_segments_start_end_and_length():
    _, route, point = process_upload('mixed.kml', KML)['features']
    assert route['status'] == 'MEASURED'
    assert route['evidence']['line_parts'] == 1
    assert route['evidence']['segments'] == 1
    assert route['evidence']['part_details'][0]['length_m'] == pytest.approx(route['measurement']['value'], abs=.00001)
    assert route['evidence']['part_details'][0]['start_wgs84'] == pytest.approx([76.5, 12.0], abs=1e-9)
    assert route['evidence']['part_details'][0]['end_wgs84'] == pytest.approx([76.51, 12.0], abs=1e-9)
    assert point['status'] == 'NOT_APPLICABLE'
    assert point['measurement'] is None
    assert point['evidence']['point_locations_wgs84'] == [[76.5, 12.0]]
    assert point['evidence']['point_count'] == 1


def test_multiline_part_counts_and_sum_consistency():
    kml=b'''<kml><Placemark><MultiGeometry><LineString><coordinates>76.5,12 76.51,12</coordinates></LineString><LineString><coordinates>76.51,12 76.52,12</coordinates></LineString></MultiGeometry></Placemark></kml>'''
    entry = process_upload('multi.kml', kml)['features'][0]
    assert entry['status'] == 'MEASURED'
    assert entry['evidence']['line_parts'] == 2
    assert entry['evidence']['segments'] == 2
    assert sum(part['length_m'] for part in entry['evidence']['part_details']) == pytest.approx(entry['measurement']['value'], abs=3e-6)


def test_unmeasurable_features_do_not_invent_evidence():
    missing = process_upload('missing.zip', zipped_shapes(include_prj=False))['features'][0]
    assert missing['status'] == 'FAILED'
    assert missing.get('evidence') is None
    bad = process_upload('bad.geojson', json.dumps({'type':'Feature','geometry':{'type':'Point','coordinates':[190,20]},'properties':{}}).encode())['features'][0]
    assert bad['status'] == 'FAILED'
    assert bad.get('evidence') is None


def test_summary_excludes_points_and_failed_features_and_notes_overlap():
    result = process_upload('mixed.kml', KML)
    summary = build_summary(result, file_id='a'*32)
    assert summary['feature_count'] == 3
    assert summary['counts'] == {'measured':2,'not_applicable':1,'failed':0,'unsupported':0,'polygons_measured':1,'lines_measured':1}
    assert summary['totals']['area_m2'] == pytest.approx(result['features'][0]['measurement']['value'])
    assert summary['totals']['length_m'] == pytest.approx(result['features'][1]['measurement']['value'])
    assert 'overlap' in summary['total_note'].lower()


def test_csv_export_escaped_utf8_and_formula_injection():
    sample = {'features': [{
        'index': 0, 'id': '=HYPERLINK("https://evil")', 'status': 'NOT_APPLICABLE',
        'geometry_type': 'Point', 'crs': 'EPSG:4326', 'measurement': None,
        'evidence': {'point_locations_wgs84': [[76.5, 12.0]],'bbox_wgs84':[76.5,12.,76.5,12.]},
        'properties': {'name': 'ಆಸ್ತಿ, "parcel"', 'untrusted': '=2+2'}, 'warnings':[], 'error':None,
    }]}
    csv_text = build_csv(sample)
    rows = list(csv.DictReader(StringIO(csv_text)))
    assert len(rows) == 1
    assert rows[0]['id'].startswith("'=")
    assert json.loads(rows[0]['properties_json'])['name'] == 'ಆಸ್ತಿ, "parcel"'
    assert rows[0]['status'] == 'NOT_APPLICABLE'
    assert rows[0]['measurement_value'] == ''


def test_geojson_export_retains_measurement_and_original_attributes():
    data = process_upload('mixed.kml', KML)
    geo = build_geojson(data)
    assert geo['type'] == 'FeatureCollection'
    assert len(geo['features']) == 3
    prop = geo['features'][0]['properties']
    assert prop['owner'] == 'Demo'
    assert prop['_measurement'] == data['features'][0]['measurement']
    assert prop['_measurement_crs'] == data['features'][0]['measurement_crs']
    assert prop['_evidence']['perimeter_m'] > 0


def test_api_end_to_end_summary_csv_geojson_and_restart(tmp_path):
    db=f'sqlite:///{tmp_path / "reports.sqlite3"}'
    with TestClient(create_app(db)) as client:
        res = client.post('/api/files/', files={'file':('test.kml', KML, 'application/xml')})
        assert res.status_code == 201, res.text
        fid = res.json()['id']
        assert res.json()['summary_url'].endswith('/summary/')
        assert res.json()['export_url'].endswith('/export/')
        summary=client.get(f'/api/files/{fid}/summary/')
        assert summary.status_code==200
        assert summary.json()['counts']['measured']==2
        assert summary.json()['counts']['not_applicable']==1
        csv_response=client.get(f'/api/files/{fid}/export/?format=csv')
        assert csv_response.status_code==200
        assert 'attachment' in csv_response.headers['content-disposition']
        rows=list(csv.DictReader(StringIO(csv_response.text)))
        assert len(rows)==3
        assert 'perimeter_m' in rows[0]
        exported=client.get(f'/api/files/{fid}/export/?format=geojson')
        assert exported.status_code==200
        assert exported.headers['content-type'].startswith('application/geo+json')
        assert exported.json()==client.get(f'/api/files/{fid}/geojson/').json()
        assert 'perimeter_m' in exported.json()['features'][0]['properties']['_evidence']
        assert client.get(f'/api/files/{fid}/export/?format=xlsx').status_code==422
        assert client.get('/api/files/'+'0'*32+'/summary/').status_code==404
    with TestClient(create_app(db)) as client:
        assert client.get(f'/api/files/{fid}/summary/').status_code==200
        assert client.get(f'/api/files/{fid}/export/?format=csv').status_code==200


def test_summary_works_for_old_records_without_new_optional_fields():
    historical = {'filename':'old.kml','status':'COMPLETED','features':[{'status':'MEASURED','measurement':{'type':'area','value':50.,'unit':'m2'}}, {'status':'NOT_APPLICABLE','measurement':None}]}
    assert build_summary(historical, file_id='b'*32)['totals']['area_m2'] == 50
    assert len(list(csv.DictReader(StringIO(build_csv(historical))))) == 2
    assert build_geojson(historical)['features'] == []
