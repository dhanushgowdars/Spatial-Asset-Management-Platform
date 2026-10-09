from fastapi.testclient import TestClient
from aereo.api import create_app
from .test_engine import KML, make_zip


def test_upload_status_measurements_geojson_and_restart(tmp_path):
    database_url=f'sqlite:///{tmp_path / "results.db"}'
    app = create_app(database_url)
    with TestClient(app) as client:
        assert client.get('/health').json()=={'status':'healthy'}
        uploaded=client.post('/api/files/',files={'file':('demo.kml',KML,'application/vnd.google-earth.kml+xml')})
        assert uploaded.status_code==201, uploaded.text
        record=uploaded.json()
        assert record['feature_count']==3
        fid=record['id']
        assert len(fid)==32
        info=client.get(f'/api/files/{fid}/')
        assert info.status_code==200
        assert info.json()['crs']=='EPSG:4326'
        results=client.get(f'/api/files/{fid}/measurements/')
        assert results.status_code==200
        assert len(results.json()['measurements'])==3
        geo=client.get(f'/api/files/{fid}/geojson/')
        assert geo.status_code==200
        assert geo.json()['type']=='FeatureCollection'
        assert len(geo.json()['features'])==3
    # Emulates restarting service and reconnecting to the same persistent DB.
    with TestClient(create_app(database_url)) as client:
        assert client.get(f'/api/files/{fid}/measurements/').status_code==200


def test_uploaded_shapefile_measurement(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "results.db"}')) as client:
        uploaded=client.post('/api/files/',files={'file':('plot.zip',make_zip(),'application/zip')})
        assert uploaded.status_code==201,uploaded.text
        fid=uploaded.json()['id']
        measurement=client.get(f'/api/files/{fid}/measurements/').json()['measurements'][0]
        assert abs(measurement['measurement']['value']-10000)<.05


def test_upload_validation_and_missing_file(tmp_path):
    with TestClient(create_app(f'sqlite:///{tmp_path / "results.db"}')) as client:
        assert client.post('/api/files/',files={'file':('wrong.pdf',b'hello','application/pdf')}).status_code==415
        assert client.post('/api/files/',files={'file':('bad.kml',b'not xml','application/xml')}).status_code==422
        assert client.post('/api/files/',files={'file':('x.kml',b'','application/xml')}).status_code==413
        assert client.get('/api/files/'+'0'*32+'/').status_code==404
        assert client.get('/api/files/'+'bad-id'+'/measurements/').status_code==404
