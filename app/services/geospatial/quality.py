"""Deterministic QA diagnostics for geospatial measurement results.

Never synthesize source properties, repair invalid geometries or assign an
unjustified quality score.  Works with historical records lacking issues.
"""
from __future__ import annotations
from typing import Any


def _code_from_error(message: str, status: str) -> str:
    lower = message.lower()
    if status == 'UNSUPPORTED' or 'no measurement defined' in lower:
        return 'UNSUPPORTED_GEOMETRY'
    if 'empty geometry' in lower:
        return 'EMPTY_GEOMETRY'
    if 'invalid geometry:' in lower:
        return 'INVALID_GEOMETRY'
    if 'source crs unknown' in lower:
        return 'CRS_MISSING'
    if 'vertex limit' in lower:
        return 'VERTEX_LIMIT_EXCEEDED'
    if 'crs/measurement' in lower or 'longitude/latitude' in lower:
        return 'TRANSFORM_FAILED'
    if 'parse' in lower or 'expected geojson' in lower or 'geojson' in lower or 'missing' in lower or 'unreadable' in lower or 'unsupported kml' in lower:
        return 'PARSE_FAILED'
    return 'FEATURE_PROCESSING_FAILED'


def issues_for_feature(feature: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    status = feature.get('status') or 'FAILED'
    error = feature.get('error')
    if error:
        issues.append({
            'code': _code_from_error(str(error), status),
            'severity': 'WARNING' if status == 'UNSUPPORTED' else 'ERROR',
            'message': str(error),
        })
    for warning in feature.get('warnings') or []:
        text = str(warning)
        issues.append({
            'code': 'PROJECTION_DISTORTION_WARNING' if 'distortion' in text.lower() else 'MEASUREMENT_WARNING',
            'severity': 'WARNING',
            'message': text,
        })
    return issues


def build_quality_report(result: dict[str, Any], *, file_id: str) -> dict[str, Any]:
    features = result.get('features', [])
    statuses = ('MEASURED', 'NOT_APPLICABLE', 'FAILED', 'UNSUPPORTED')
    counts = {status.lower(): sum(f.get('status') == status for f in features) for status in statuses}
    issues: list[dict[str, Any]] = []
    feature_reports: list[dict[str, Any]] = []
    for feature in features:
        found = issues_for_feature(feature)
        for issue in found:
            issues.append({
                'feature_id': feature.get('id'),
                'feature_index': feature.get('index'),
                'geometry_type': feature.get('geometry_type'),
                **issue,
            })
        feature_reports.append({
            'id': feature.get('id'), 'index': feature.get('index'),
            'geometry_type': feature.get('geometry_type'), 'status': feature.get('status'),
            'issue_codes': [i['code'] for i in found],
        })
    return {
        'file_id': file_id, 'filename': result.get('filename'), 'status': result.get('status'),
        'summary': {
            'total_features': len(features),
            **counts,
            'warning_features': sum(any(i['severity'] == 'WARNING' for i in issues_for_feature(f)) for f in features),
            'error_features': sum(any(i['severity'] == 'ERROR' for i in issues_for_feature(f)) for f in features),
            'issue_count': len(issues),
        },
        'issues': issues,
        'features': feature_reports,
    }
