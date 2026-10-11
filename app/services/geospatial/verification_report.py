"""Deterministic, non-certifying audit summary of persisted GeoInsight measurements.

Does not remeasure geometries or assert independent/survey-grade verification.
Does not include original geometries, arbitrary source properties or upload bytes.
"""
from __future__ import annotations

from typing import Any

from app.services.geospatial.reporting import build_summary


def build_verification_report(row: Any) -> dict[str, Any]:
    """Build a JSON-safe verification report from one persisted upload record."""
    stored = row.result_json
    features = stored['features']
    details: list[dict[str, Any]] = []
    for item in features:
        measurement = item.get('measurement')
        evidence = item.get('evidence') or {}
        # Deliberately exclude arbitrary user properties and raw geometry.
        details.append({
            'id': item.get('id'),
            'index': item.get('index'),
            'geometry_type': item.get('geometry_type'),
            'status': item.get('status'),
            'source_crs': item.get('crs'),
            'measurement_crs': item.get('measurement_crs'),
            'measurement_method': item.get('measurement_method'),
            'measurement': measurement,
            'perimeter_m': evidence.get('perimeter_m'),
            'warnings': list(item.get('warnings') or []),
            'error': item.get('error'),
            'issue_codes': [str(issue.get('code')) for issue in (item.get('issues') or []) if isinstance(issue, dict) and issue.get('code')],
        })

    summary = build_summary(stored, file_id=row.id)
    return {
        'report_type': 'geoinsight_measurement_verification',
        'schema_version': '1.0',
        'provenance': {
            'basis': 'persisted_upload_result',
            'input_sha256': row.file_hash_sha256,
            'input_size_bytes': row.size_bytes,
            'filename': row.filename,
            'file_id': row.id,
            'uploaded_at': row.created_at.isoformat(),
            'source_crs': row.source_crs,
        },
        'processing': {
            'status': row.status,
            'feature_count': row.feature_count,
            'successful_measurements': row.successful_measurements,
            'failed_features': row.failed_features,
            'measurement_basis': '2D projected planar geometry',
            'area_unit': 'm2',
            'length_unit': 'm',
        },
        'summary': {
            'counts': summary['counts'],
            'totals': summary['totals'],
            'warning_features': summary['warning_features'],
            'total_note': summary['total_note'],
        },
        'features': details,
        'limitations': [
            'Generated from existing persisted GIS results; no independent recomputation or external verification was performed.',
            'Measurements are 2D planar calculations in the listed measurement CRS and are not survey-grade or legal boundary certification.',
            'Projection distortion may occur; review feature-level CRS choices and warnings before technical use.',
            'Summed polygon areas are arithmetic feature totals, not necessarily a geometric union; overlaps may be counted more than once.',
            'Input SHA-256 identifies the originally uploaded bytes; original upload bytes are not included in this report.',
        ],
    }
