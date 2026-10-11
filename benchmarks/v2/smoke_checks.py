"""Offline checks for fixture validity, projected reference geometry and safety."""
from __future__ import annotations
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
import shapefile
from shapely.geometry import shape
from pyproj import Transformer
from shapely.ops import transform
from fixture_lib import generate, load_manifest, enforce_local_only, FIXTURES


def main():
    generate()
    entries=load_manifest()
    back=Transformer.from_crs(4326,32643,always_xy=True)
    for key,ent in entries.items():
        data=(FIXTURES/ent['filename']).read_bytes()
        if ent['filename'].endswith('.geojson'):
            features=json.loads(data)['features']
            assert len(features)==ent['feature_count']
            assert len(ent['all_oracles'])==len(features)
            for feat, expected in zip(features,ent['all_oracles']):
                assert feat['id']==expected['id']
                geom=shape(feat['geometry'])
                assert geom.is_valid and not geom.is_empty
                metric=transform(back.transform,geom)
                if expected['status']=='MEASURED':
                    got=metric.area if expected['measurement_type']=='area' else metric.length
                    assert abs(got-expected['value']) <= max(0.25,abs(expected['value'])*0.0002), (key,feat['id'])
        elif ent['filename'].endswith('.zip'):
            with ZipFile(BytesIO(data)) as zf:
                namelist=zf.namelist()
                assert {'plots/bench.shp','plots/bench.shx','plots/bench.dbf','plots/bench.prj'}.issubset(namelist)
                shp=shapefile.Reader(shp=BytesIO(zf.read('plots/bench.shp')),
                                      shx=BytesIO(zf.read('plots/bench.shx')),
                                      dbf=BytesIO(zf.read('plots/bench.dbf')))
                assert len(shp)==250
                shp.close()
        elif ent['filename'].endswith('.kmz'):
            with ZipFile(BytesIO(data)) as zf:
                assert len([s for s in zf.namelist() if s.lower().endswith('.kml')])==1
        else:
            assert data.count(b'<Placemark') == 150
        print(f"VALID {key:20s} {ent['feature_count']:4d} features")
    enforce_local_only('http://127.0.0.1:18130')
    for bad in ['https://geoinsight-aereo.onrender.com','http://localhost:18130','http://127.0.0.1:18131','http://127.0.0.1:18130/bad','http://127.0.0.1:18130?bad']:
        try:enforce_local_only(bad)
        except RuntimeError:pass
        else:raise AssertionError(f"Unsafe target accepted: {bad}")
    print('OFFLINE SMOKE CHECKS PASSED')


if __name__=='__main__':main()
