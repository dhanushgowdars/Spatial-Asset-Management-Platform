"""Regression tests for server-authoritative metadata on calculated map layers."""
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, mapping
from shapely.ops import transform

from app.services.geospatial.spatial_intelligence import compare_surveys, topology_report, route_zone_report


def _geometry(geom):
    project = Transformer.from_crs('EPSG:32643', 'EPSG:4326', always_xy=True)
    return mapping(transform(project.transform, geom))


def _feature(name, geom):
    return {'id':name, 'geometry_type':geom.geom_type, 'geometry':_geometry(geom), 'status':'MEASURED'}


def _data(name, *features):
    return {'filename':name, 'features':list(features)}


def _assert_calculated(feature, root):
    props=feature['properties']
    assert props['_status']=='CALCULATED'
    assert props['_measurement_crs']==root['measurement_crs']
    assert props['_measurement_method']==root['method']
    assert props['_operation']
    assert props.get('area_m2', props.get('length_m'))>=0


def test_compare_area_exposes_calculation_provenance():
    old = _data('old.geojson', _feature('old', Polygon([(500000,1400000),(500100,1400000),(500100,1400100),(500000,1400100)])))
    new = _data('new.geojson', _feature('new', Polygon([(500050,1400000),(500150,1400000),(500150,1400100),(500050,1400100)])))
    report=compare_surveys(old,new,baseline_id='old-id',current_id='new-id')
    assert report['measurement_crs']=='EPSG:32643'
    assert report['metrics']['added_area_m2']==5000
    assert report['metrics']['removed_area_m2']==5000
    assert report['metrics']['overlap_area_m2']==5000
    assert {f['properties']['category'] for f in report['change_geojson']['features']}=={'added','removed','unchanged_overlap'}
    for f in report['change_geojson']['features']:
        _assert_calculated(f,report)
    labels={f['properties']['category']:f['properties']['_operation'] for f in report['change_geojson']['features']}
    assert labels['added'] != labels['removed'] != labels['unchanged_overlap']


def test_topology_overlap_and_coverage_have_provenance():
    a=Polygon([(500000,1400000),(500100,1400000),(500100,1400100),(500000,1400100)])
    b=Polygon([(500050,1400000),(500150,1400000),(500150,1400100),(500050,1400100)])
    source=_data('parcels.geojson',_feature('a',a),_feature('b',b))
    ref=_data('reference.geojson',_feature('ref',a))
    report=topology_report(source,file_id='survey-id',reference_data=ref,reference_id='reference-id')
    assert report['overlap_pair_count']==1
    assert report['measurement_crs']=='EPSG:32643'
    for f in report['geojson']['features']:
        _assert_calculated(f,report)


def test_route_clipped_length_has_provenance():
    route=LineString([(499970,1400050),(500110,1400050)])
    zone=Polygon([(500000,1400030),(500040,1400030),(500040,1400070),(500000,1400070)])
    report=route_zone_report(_data('route.geojson',_feature('r1',route)),_data('zone.geojson',_feature('z1',zone)),route_id='route-id',zone_id='zone-id')
    assert report['summary']['routes_crossing_zones']==1
    assert len(report['intersection_geojson']['features'])==1
    for f in report['intersection_geojson']['features']:
        _assert_calculated(f,report)
    assert abs(report['intersection_geojson']['features'][0]['properties']['length_m']-40)<0.01
