"""Independent projected reference fixtures for C4A's 2D GIS boolean overlays."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pyproj import Transformer

from aereo.api import create_app
from app.services.geospatial import process_upload
from app.services.geospatial.spatial_intelligence import (
    AnalysisValidationError, compare_surveys, topology_report, route_zone_report,
    _extract,
)
from .test_engine import make_zip

UTM_TO_WGS = Transformer.from_crs(32643, 4326, always_xy=True)
X = 500_000
Y = 1_400_000


def _ring(x0, y0, x1, y1):
    p = [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
    return [list(UTM_TO_WGS.transform(x,y)) for x,y in p]


def poly(x0=0,y0=0,x1=100,y1=100, *, hole=None):
    rings = [_ring(X+x0,Y+y0,X+x1,Y+y1)]
    if hole:
        a,b,c,d=hole
        rings.append(_ring(X+a,Y+b,X+c,Y+d)[::-1])
    return {'type':'Polygon','coordinates':rings}


def line(x0=-20,y0=50,x1=120,y1=50):
    return {'type':'LineString','coordinates':[list(UTM_TO_WGS.transform(X+x,Y+y)) for x,y in ((x0,y0),(x1,y1))]}


def feature(fid,geometry):
    return {'type':'Feature','id':fid,'properties':{'survey_id':fid},'geometry':geometry}


def dataset(*features):
    return {'type':'FeatureCollection','features':list(features)}


def parsed(*features):
    return process_upload('test.geojson',json.dumps(dataset(*features)).encode())


def _compare(base,now):
    return compare_surveys(base,now,baseline_id='a'*32,current_id='b'*32)


def assert_metric(result, name, expected):
    assert result['metrics'][name] == pytest.approx(expected, abs=.08)


def test_identical_surveys_zero_change():
    a = parsed(feature('p',poly()))
    result = _compare(a,a)
    assert_metric(result,'baseline_area_m2',10000)
    assert_metric(result,'added_area_m2',0)
    assert_metric(result,'removed_area_m2',0)
    assert_metric(result,'overlap_area_m2',10000)
    assert result['metrics']['intersection_over_union_pct'] == 100
    assert result['measurement_crs']=='EPSG:32643'
    assert [f['properties']['category'] for f in result['change_geojson']['features']]==['unchanged_overlap']


def test_shifted_survey_exact_added_removed_overlap_and_roundtrip():
    baseline = parsed(feature('before',poly()))
    current = parsed(feature('after',poly(50,0,150,100)))
    result = _compare(baseline,current)
    for name in ('added_area_m2','removed_area_m2','overlap_area_m2'):
        assert_metric(result,name,5000)
    assert_metric(result,'net_change_m2',0)
    assert result['metrics']['intersection_over_union_pct'] == pytest.approx(33.3333,abs=.0001)
    assert len(result['change_geojson']['features']) == 3
    assert sum(f['properties']['area_m2'] for f in result['change_geojson']['features']) == pytest.approx(15000, abs=.1)


def test_disjoint_surveys_have_no_overlap():
    result = _compare(parsed(feature('before',poly())),parsed(feature('after',poly(120,0,220,100))))
    assert_metric(result,'overlap_area_m2',0)
    assert_metric(result,'added_area_m2',10000)
    assert_metric(result,'removed_area_m2',10000)
    assert result['metrics']['intersection_over_union_pct'] == 0


def test_expanded_survey_net_change():
    result=_compare(parsed(feature('a',poly())),parsed(feature('b',poly(0,0,200,100))))
    assert_metric(result,'net_change_m2',10000)
    assert_metric(result,'added_area_m2',10000)
    assert_metric(result,'removed_area_m2',0)


def test_polygon_hole_correctly_removed_and_area_conserved():
    a=parsed(feature('a',poly()))
    b=parsed(feature('b',poly(hole=(25,25,75,75))))
    result=_compare(a,b)
    assert_metric(result,'baseline_area_m2',10000)
    assert_metric(result,'current_area_m2',7500)
    assert_metric(result,'removed_area_m2',2500)
    assert_metric(result,'added_area_m2',0)


def test_multipart_union_prevents_double_counting():
    a=parsed(feature('a',poly()))
    b=parsed(feature('b1',poly()),feature('b2',poly(50,0,150,100)))
    result=_compare(a,b)
    assert_metric(result,'current_area_m2',15000)
    assert_metric(result,'added_area_m2',5000)
    assert_metric(result,'overlap_area_m2',10000)


def test_mixed_format_shapefile_and_geojson_share_projection():
    old=process_upload('shapefile.zip',make_zip())
    current=parsed(feature('same',poly()))
    result=_compare(old,current)
    assert_metric(result,'added_area_m2',0)
    assert_metric(result,'removed_area_m2',0)
    assert result['measurement_crs']=='EPSG:32643'


def test_bad_feature_is_disclosed_as_partial_instead_of_silent_omission():
    good=parsed(feature('good',poly()), feature('bad',{'type':'Point','coordinates':[181,20]}))
    result=_compare(good,parsed(feature('b',poly())))
    assert result['partial'] is True
    assert result['excluded_features']['baseline'][0]['feature_id']=='bad'
    assert result['metrics']['added_area_m2']==0


def test_missing_polygons_raise_actionable_error():
    points=parsed(feature('pin',{'type':'Point','coordinates':list(UTM_TO_WGS.transform(X,Y))}))
    with pytest.raises(AnalysisValidationError,match='at least one'):
        _compare(points,parsed(feature('parcel',poly())))


def test_global_extent_rejected_before_overlay():
    huge = parsed(feature('wide', {'type':'Polygon','coordinates':[[[-100,0],[-20,0],[-20,1],[-100,1],[-100,0]]]}))
    with pytest.raises(AnalysisValidationError,match='local UTM'):
        _compare(huge, huge)


def test_analysis_coordinate_limits_reject_large_payload_without_touching_uploads():
    data=parsed(feature('parcel',poly()))
    data['features']=data['features']*251
    with pytest.raises(AnalysisValidationError,match='250 features'):
        _extract(data)


def test_topology_adjacent_polygons_not_mistaken_for_overlap():
    a=parsed(feature('left',poly()),feature('right',poly(100,0,200,100)))
    result=topology_report(a,file_id='a'*32)
    assert result['overlap_pair_count']==0
    assert result['gaps_evaluated'] is False
    assert result['boundary_comparison'] is None


def test_topology_overlap_identifies_pair_and_area():
    a=parsed(feature('left',poly()),feature('right',poly(50,0,150,100)))
    result=topology_report(a,file_id='a'*32)
    assert result['overlap_pair_count']==1
    issue=result['overlap_issues'][0]
    assert issue['feature_a']=='left' and issue['feature_b']=='right'
    assert issue['overlap_area_m2']==pytest.approx(5000,abs=.08)
    assert result['geojson']['features'][0]['properties']['category']=='overlap_area'


def test_gaps_are_computed_only_against_explicit_reference():
    survey=parsed(feature('a',poly(0,0,40,100)),feature('b',poly(60,0,100,100)))
    ref=parsed(feature('site',poly()))
    without=topology_report(survey,file_id='a'*32)
    assert without['gaps_evaluated'] is False
    with_ref=topology_report(survey,file_id='a'*32,reference_data=ref,reference_id='b'*32)
    assert with_ref['gaps_evaluated'] is True
    assert with_ref['boundary_comparison']['uncovered_area_m2']==pytest.approx(2000,abs=.08)
    assert with_ref['boundary_comparison']['outside_reference_area_m2']==pytest.approx(0,abs=.08)


def test_polygons_outside_reference_count_as_outside():
    survey=parsed(feature('outside',poly(100,0,150,100)))
    ref=parsed(feature('site',poly()))
    out=topology_report(survey,file_id='a'*32,reference_data=ref,reference_id='b'*32)
    assert out['boundary_comparison']['outside_reference_area_m2']==pytest.approx(5000,abs=.08)


def test_topology_requires_measured_polygons():
    points=parsed(feature('pin',{'type':'Point','coordinates':list(UTM_TO_WGS.transform(X,Y))}))
    with pytest.raises(AnalysisValidationError,match='no successfully measured'):
        topology_report(points,file_id='a'*32)


def test_route_zone_length_and_boundary_intersection():
    routes=parsed(feature('r:1',line()))
    zones=parsed(feature('z:2',poly(30,0,70,100)))
    result=route_zone_report(routes,zones,route_id='a'*32,zone_id='b'*32)
    entry=result['routes'][0]
    assert entry['length_m']==pytest.approx(140,abs=.1)
    assert entry['inside_any_zone_m']==pytest.approx(40,abs=.1)
    assert entry['outside_all_zones_m']==pytest.approx(100,abs=.1)
    assert result['summary']['routes_crossing_zones']==1
    assert result['intersection_geojson']['features'][0]['properties']['zone_feature_id']=='z:2'
    assert result['intersection_geojson']['features'][0]['properties']['route_feature_id']=='r:1'


def test_route_zone_union_prevents_double_counting():
    routes=parsed(feature('r',line()))
    zones=parsed(feature('z1',poly(30,0,70,100)),feature('z2',poly(50,0,90,100)))
    result=route_zone_report(routes,zones,route_id='a'*32,zone_id='b'*32)
    entry=result['routes'][0]
    assert entry['inside_any_zone_m']==pytest.approx(60,abs=.1)
    assert sum(x['length_inside_m'] for x in entry['zone_intersections'])==pytest.approx(80,abs=.1)


def test_route_zone_requires_measured_line_and_polygon():
    polygons=parsed(feature('z',poly()))
    with pytest.raises(AnalysisValidationError,match='LineString route'):
        route_zone_report(polygons,polygons,route_id='a'*32,zone_id='b'*32)


def _upload(client,data):
    uploaded=client.post('/api/files/',files={'file':('area.geojson',json.dumps(data).encode(),'application/geo+json')})
    assert uploaded.status_code==201, uploaded.text
    return uploaded.json()['id']


def test_api_comparison_and_metadata_persistence(tmp_path):
    database_url=f'sqlite:///{tmp_path / "intel.db"}'
    with TestClient(create_app(database_url)) as client:
        base=_upload(client,dataset(feature('baseline',poly())))
        current=_upload(client,dataset(feature('current',poly(50,0,150,100))))
        request={'baseline_file_id':base,'current_file_id':current}
        resp=client.post('/api/analysis/compare',json=request)
        assert resp.status_code==200, resp.text
        assert resp.json()['metrics']['overlap_area_m2']==pytest.approx(5000,abs=.08)
        assert client.get(f'/api/files/{base}/measurements/').status_code==200
    with TestClient(create_app(database_url)) as client:
        assert client.post('/api/analysis/compare',json=request).status_code==200


def test_api_topology_route_zones_missing_and_invalid(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "all.db"}')) as client:
        survey=_upload(client,dataset(feature('z1',poly()), feature('z2',poly(50,0,150,100))))
        route=_upload(client,dataset(feature('road',line())))
        topo=client.post('/api/analysis/topology',json={'file_id':survey})
        assert topo.status_code==200,topo.text
        assert topo.json()['overlap_pair_count']==1
        rz=client.post('/api/analysis/route-zones',json={'route_file_id':route,'zone_file_id':survey})
        assert rz.status_code==200,rz.text
        assert rz.json()['summary']['routes_crossing_zones']==1
        assert client.post('/api/analysis/compare',json={'baseline_file_id':'bad','current_file_id':survey}).status_code==404
        assert client.post('/api/analysis/compare',json={'baseline_file_id':route,'current_file_id':survey}).status_code==422
        assert client.post('/api/analysis/topology',json={'file_id':survey,'reference_file_id':'bad'}).status_code==404
        assert client.post('/api/analysis/route-zones',json={'route_file_id':survey,'zone_file_id':route}).status_code==422


def test_openapi_schema_exposes_three_new_analysis_routes(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "paths.db"}')) as client:
        paths=client.get('/openapi.json').json()['paths']
        assert all(p in paths for p in ('/api/analysis/compare','/api/analysis/topology','/api/analysis/route-zones'))
        assert 'post' in paths['/api/analysis/compare']
