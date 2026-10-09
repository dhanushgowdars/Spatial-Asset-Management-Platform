"""Pure, backward-compatible summary and export builders for processed GIS files."""
from __future__ import annotations

import csv
from io import StringIO
import json
from typing import Any


def build_summary(data: dict[str, Any], *, file_id: str) -> dict[str, Any]:
    """Aggregate only measured results. Totals are sums, not geometric unions."""
    features = data.get('features', [])
    measured = [f for f in features if f.get('status') == 'MEASURED' and f.get('measurement')]
    area = sum(float(f['measurement']['value']) for f in measured if f['measurement']['type'] == 'area')
    length = sum(float(f['measurement']['value']) for f in measured if f['measurement']['type'] == 'length')
    return {
        'file_id': file_id, 'filename': data.get('filename'),
        'status': data.get('status'), 'source_crs': data.get('source_crs'),
        'feature_count': len(features),
        'counts': {
            'measured': sum(f.get('status') == 'MEASURED' for f in features),
            'not_applicable': sum(f.get('status') == 'NOT_APPLICABLE' for f in features),
            'failed': sum(f.get('status') == 'FAILED' for f in features),
            'unsupported': sum(f.get('status') == 'UNSUPPORTED' for f in features),
            'polygons_measured': sum(f['measurement']['type'] == 'area' for f in measured),
            'lines_measured': sum(f['measurement']['type'] == 'length' for f in measured),
        },
        'totals': {'area_m2': round(area, 6), 'length_m': round(length, 6)},
        'warning_features': sum(bool(f.get('warnings')) for f in features),
        'total_note': 'Arithmetic sum of measured features, not a geometric union; overlapping polygons may be double-counted.',
    }


def build_geojson(data: dict[str, Any]) -> dict[str, Any]:
    """Preserve the existing /geojson/ fields, adding optional evidence metadata."""
    features = []
    for f in data.get('features', []):
        if f.get('geometry') is None:
            continue
        features.append({
            'type': 'Feature', 'id': f.get('id'), 'geometry': f['geometry'],
            'properties': {
                **f.get('properties', {}),
                '_measurement': f.get('measurement'),
                '_measurement_crs': f.get('measurement_crs'),
                '_status': f.get('status'), '_error': f.get('error'),
                '_measurement_method': f.get('measurement_method'),
                '_evidence': f.get('evidence'),
            },
        })
    return {'type': 'FeatureCollection', 'features': features}


def _csv_safe(value: Any) -> Any:
    # Prevent Excel/Sheets CSV formula execution in untrusted source fields.
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def build_csv(data: dict[str, Any]) -> str:
    """UTF-8 RFC-4180-friendly CSV; explicitly preserves output units."""
    fields = (
        'index', 'id', 'geometry_type', 'status', 'measurement_type',
        'measurement_value', 'unit', 'source_crs', 'measurement_crs',
        'measurement_method', 'perimeter_m', 'centroid_lon', 'centroid_lat',
        'bbox_wgs84', 'line_parts', 'segments', 'error', 'warnings', 'properties_json',
    )
    stream = StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\r\n')
    writer.writerow(fields)
    for feature in data.get('features', []):
        measurement = feature.get('measurement') or {}
        evidence = feature.get('evidence') or {}
        centroid = evidence.get('centroid_wgs84') or [None, None]
        row = {
            'index': feature.get('index'), 'id': feature.get('id'),
            'geometry_type': feature.get('geometry_type'), 'status': feature.get('status'),
            'measurement_type': measurement.get('type'),
            'measurement_value': measurement.get('value'), 'unit': measurement.get('unit'),
            'source_crs': feature.get('crs'), 'measurement_crs': feature.get('measurement_crs'),
            'measurement_method': feature.get('measurement_method'),
            'perimeter_m': evidence.get('perimeter_m'),
            'centroid_lon': centroid[0], 'centroid_lat': centroid[1],
            'bbox_wgs84': json.dumps(evidence.get('bbox_wgs84')) if evidence.get('bbox_wgs84') else None,
            'line_parts': evidence.get('line_parts'), 'segments': evidence.get('segments'),
            'error': feature.get('error'),
            'warnings': json.dumps(feature.get('warnings') or [], ensure_ascii=False),
            'properties_json': json.dumps(feature.get('properties') or {}, ensure_ascii=False, sort_keys=True),
        }
        writer.writerow([_csv_safe(row[field]) for field in fields])
    return stream.getvalue()
