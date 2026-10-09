"""Regression tests for input variations likely in third-party GIS exports.

These fixtures are deterministic synthetic QA data, NOT third-party field surveys.
Run separately from the legacy PostGIS tests to avoid database side effects.
"""
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
import shapefile
from pyproj import CRS

from app.services.geospatial import InvalidGeospatialUpload, process_upload
from app.services.geospatial.engine import MAX_FEATURES


def zipped_shapes(
    kind=shapefile.POLYLINE,
    *,
    crs=32643,
    nested=True,
    upper=False,
    encoding='utf-8',
    records=None,
    include_prj=True,
):
    """Produce an in-memory Shapefile with independently configurable export traits."""
    shp, shx, dbf = BytesIO(), BytesIO(), BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=kind, encoding=encoding)
    writer.field('NAME', 'C', size=80)
    records = records if records is not None else [
        ('test', [[500000, 1400000], [500003, 1400004]])
    ]
    for label, coords in records:
        if kind == shapefile.POLYLINE:
            writer.line([coords])
        elif kind == shapefile.POLYGON:
            writer.poly([coords])
        elif kind == shapefile.POINT:
            writer.point(*coords)
        else:
            raise AssertionError('fixture geometry type not configured')
        writer.record(label)
    writer.close()
    out = BytesIO()
    stem = 'GIS Exports/Survey' if nested else 'Survey'
    extension = (lambda e: e.upper()) if upper else (lambda e: e)
    with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
        for ext, content in [('shp', shp), ('shx', shx), ('dbf', dbf)]:
            archive.writestr(stem + '.' + extension(ext), content.getvalue())
        if include_prj:
            archive.writestr(stem + '.' + extension('prj'), CRS.from_epsg(crs).to_wkt())
        if encoding != 'utf-8':
            archive.writestr(stem + '.' + extension('cpg'), encoding)
    return out.getvalue()


def test_nested_uppercase_shapefile_components():
    result = process_upload('REAL_EXPORT.ZIP', zipped_shapes(nested=True, upper=True))
    assert result['feature_count'] == 1
    assert result['source_crs'] == 'EPSG:32643'
    assert result['features'][0]['measurement']['value'] == pytest.approx(5, abs=1e-6)


def test_non_utf8_dbf_encoding_from_cpg():
    result = process_upload(
        'survey.zip', zipped_shapes(encoding='cp1252', records=[
            ('Café survey', [[500000, 1400000], [500003, 1400004]])
        ])
    )
    assert result['features'][0]['properties']['NAME'] == 'Café survey'


def test_projected_feet_are_reported_as_metres():
    # Pennsylvania South StatePlane EPSG:2272 uses US survey feet.
    # This is a 100 ft straight line, about 30.48006 m; slight projection
    # distortion is expected when measuring in a locally selected metric CRS.
    data = zipped_shapes(crs=2272, nested=False, records=[
        ('100 US survey feet', [[2500000, 400000], [2500100, 400000]])
    ])
    result = process_upload('feet.zip', data)
    entry = result['features'][0]
    assert result['status'] == 'COMPLETED', entry
    assert entry['measurement']['type'] == 'length'
    assert entry['measurement']['unit'] == 'm'
    assert entry['measurement']['value'] == pytest.approx(30.48006, abs=0.1)
    assert entry['measurement_crs'] != 'EPSG:2272'


def test_kml_placemarks_inside_nested_folder():
    xml = b'''<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
    <Folder><Folder><Placemark id="nested-point"><name>Inspection</name>
    <Point><coordinates>76.5,12.0</coordinates></Point>
    </Placemark></Folder></Folder></Document></kml>'''
    output = process_upload('nested.kml', xml)
    assert output['feature_count'] == 1
    assert output['features'][0]['id'] == 'nested-point'
    assert output['features'][0]['status'] == 'NOT_APPLICABLE'


def test_bad_geographic_shapefile_coordinates_never_get_measured_or_mapped():
    invalid = zipped_shapes(crs=4326, kind=shapefile.POINT, nested=False, records=[
        ('invalid coordinate', (181, 20))
    ])
    output = process_upload('invalid_coords.zip', invalid)
    feature = output['features'][0]
    assert feature['status'] == 'FAILED'
    assert feature['measurement'] is None
    assert feature['geometry'] is None
    assert 'latitude' in feature['error'].lower() or 'longitude' in feature['error'].lower()


def test_more_than_max_features_is_rejected_before_measuring():
    rows = [('x', (76.5, 12.0)) for _ in range(MAX_FEATURES + 1)]
    too_many = zipped_shapes(kind=shapefile.POINT, crs=4326, records=rows)
    with pytest.raises(InvalidGeospatialUpload, match='maximum feature count'):
        process_upload('too-many.zip', too_many)


def test_zip_case_insensitive_duplicate_paths_rejected():
    out = BytesIO()
    with ZipFile(out, 'w') as z:
        z.writestr('data/survey.SHP', b'abc')
        z.writestr('data/survey.shp', b'def')
    with pytest.raises(InvalidGeospatialUpload, match='duplicate paths'):
        process_upload('duplicate.zip', out.getvalue())
