from io import BytesIO
import zipfile
import pytest
import shapefile
from pyproj import CRS

from app.services.geospatial import process_upload, InvalidGeospatialUpload

KML = b'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark id="poly"><name>Plot</name><ExtendedData><Data name="owner"><value>Demo</value></Data></ExtendedData>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
76.5,12.0 76.51,12.0 76.51,12.01 76.5,12.01 76.5,12.0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark><name>Track</name><LineString><coordinates>76.5,12.0 76.51,12.0</coordinates></LineString></Placemark>
<Placemark><name>Beacon</name><Point><coordinates>76.5,12.0,100</coordinates></Point></Placemark>
</Document></kml>'''


def make_zip(with_prj=True, bad_geom=False):
    shp = BytesIO(); shx = BytesIO(); dbf = BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field('NAME', 'C', 40)
    if bad_geom:
        pts = [[500000,1400000],[500100,1400100],[500000,1400100],[500100,1400000],[500000,1400000]]
    else:
        # clockwise outer ring: from left-bottom up, then right, then down
        pts = [[500000,1400000],[500000,1400100],[500100,1400100],[500100,1400000],[500000,1400000]]
    writer.poly([pts]); writer.record('100x100 sample')
    writer.close()
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for extension, stream in [('shp',shp),('shx',shx),('dbf',dbf)]:
            z.writestr('data/plot.'+extension, stream.getvalue())
        if with_prj:
            z.writestr('data/plot.prj', CRS.from_epsg(32643).to_wkt())
    return output.getvalue()


def test_kml_multiple_geometries_and_attributes():
    output=process_upload('sample.kml', KML)
    assert output['feature_count']==3
    assert output['source_crs']=='EPSG:4326'
    assert output['status']=='COMPLETED'
    a,b,c=output['features']
    assert a['properties']['owner']=='Demo'
    assert a['measurement']['type']=='area'
    assert a['measurement']['value']>1000000
    assert a['geometry_type']=='Polygon'
    assert b['measurement']['unit']=='m'
    assert c['measurement'] is None and c['status']=='NOT_APPLICABLE'


def test_projected_shapefile_known_area():
    output=process_upload('plot.zip', make_zip())
    assert output['source_crs']=='EPSG:32643'
    assert output['status']=='COMPLETED'
    result=output['features'][0]
    assert result['properties']['NAME']=='100x100 sample'
    assert result['geometry']['type']=='Polygon'
    assert result['measurement_crs']=='EPSG:32643'
    assert result['measurement']['value']==pytest.approx(10000, abs=.05)


def test_no_prj_does_not_invent_measurements():
    output=process_upload('plot.zip',make_zip(with_prj=False))
    assert output['source_crs'] is None
    assert output['status']=='COMPLETED_WITH_ERRORS'
    result=output['features'][0]
    assert result['measurement'] is None
    assert result['status']=='FAILED'
    assert 'CRS' in result['error']


def test_invalid_geometry_is_per_feature_error():
    output=process_upload('plot.zip',make_zip(bad_geom=True))
    assert output['features'][0]['status']=='FAILED'
    assert output['features'][0]['measurement'] is None


def test_reject_wrong_file_extension():
    with pytest.raises(InvalidGeospatialUpload,match='Accepted types'):
        process_upload('x.pdf', KML)


def test_reject_non_kml_xml():
    with pytest.raises(InvalidGeospatialUpload,match='not a KML'):
        process_upload('x.kml',b'<a/>')


def test_reject_dtd_entity():
    evil=b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><kml><Placemark><name>&x;</name></Placemark></kml>'
    with pytest.raises(InvalidGeospatialUpload,match='Invalid or unsafe KML'):
        process_upload('x.kml',evil)


def test_reject_zip_slip():
    data=BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('../escape.shp',b'hello')
    with pytest.raises(InvalidGeospatialUpload,match='unsafe filename'):
        process_upload('data.zip',data.getvalue())


def test_reject_missing_shapefile_component():
    data=BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('data.shp',b'hello')
    with pytest.raises(InvalidGeospatialUpload,match=r'missing .shx'):
        process_upload('data.zip',data.getvalue())


def test_reject_invalid_zip():
    with pytest.raises(InvalidGeospatialUpload,match='valid ZIP'):
        process_upload('data.zip',b'garbage')


def test_kml_unsupported_geometry_doesnt_crash():
    raw=b'<kml><Placemark><Model><Location><longitude>2</longitude></Location></Model></Placemark></kml>'
    output=process_upload('data.kml',raw)
    assert output['features'][0]['status']=='FAILED'
    assert output['features'][0]['measurement'] is None


def test_kml_multigeometry():
    raw=b'<kml><Placemark><MultiGeometry><LineString><coordinates>76.5,12 76.51,12</coordinates></LineString><LineString><coordinates>76.51,12 76.52,12</coordinates></LineString></MultiGeometry></Placemark></kml>'
    output=process_upload('multi.kml',raw)
    assert output['features'][0]['geometry_type']=='MultiLineString'
    assert output['features'][0]['status']=='MEASURED'
    assert output['features'][0]['measurement']['value']>2000


def test_reject_huge_upload():
    with pytest.raises(InvalidGeospatialUpload,match='File must'):
        process_upload('x.kml',b'x'*(10*1024*1024+1))


def test_bad_kml_feature_does_not_block_valid_feature():
    raw=b'''<kml><Placemark><Point><coordinates>bad</coordinates></Point></Placemark>
    <Placemark><LineString><coordinates>76.5,12.0 76.51,12.0</coordinates></LineString></Placemark></kml>'''
    output=process_upload('mixed.kml',raw)
    assert output['status']=='COMPLETED_WITH_ERRORS'
    assert output['failed_features']==1
    assert output['successful_measurements']==1
    assert output['features'][0]['status']=='FAILED'
    assert output['features'][1]['measurement']['value']>0


def test_line_3_4_5_meters_in_utm_zip():
    shp=BytesIO(); shx=BytesIO(); dbf=BytesIO()
    writer=shapefile.Writer(shp=shp,shx=shx,dbf=dbf,shapeType=shapefile.POLYLINE)
    writer.field('ID','N',4)
    writer.line([[[500000,1400000],[500003,1400004]]]);writer.record(1);writer.close()
    data=BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        for ext,stream in [('shp',shp),('shx',shx),('dbf',dbf)]:
            z.writestr('route.'+ext,stream.getvalue())
        z.writestr('route.prj',CRS.from_epsg(32643).to_wkt())
    output=process_upload('route.zip',data.getvalue())
    assert output['features'][0]['measurement']['type']=='length'
    assert output['features'][0]['measurement']['value']==pytest.approx(5,abs=.001)
