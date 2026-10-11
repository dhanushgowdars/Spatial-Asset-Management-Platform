"""Create realistic synthetic benchmark inputs, then check GeoInsight's real engine.

Uses the local repository's own parser for preflight, without touching any DB.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from time import perf_counter
from fixture_lib import generate, load_manifest, FIXTURES, verify_results


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--generate-only",action="store_true",help="Skip project-engine verification (for development only)")
    args=ap.parse_args()
    entries=generate()
    print(f"Generated {len(entries)} synthetic test files:")
    for key, e in entries.items():
        print(f"  {key:20s}: {e['feature_count']:4d} features, {e['bytes']:9d} bytes, SHA256 {e['sha256'][:12]}")
    if args.generate_only:
        print("WARNING: application-engine correctness validation SKIPPED")
        return
    repo=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(repo))
    try:
        from app.services.geospatial import process_upload
    except ImportError as exc:
        raise SystemExit(f"Cannot import actual GeoInsight engine from {repo}: {exc}") from exc
    print("\nValidating with existing GeoInsight GIS engine and independent projected-metric oracles:")
    for key,e in entries.items():
        start=perf_counter()
        parsed=process_upload(e['filename'],(FIXTURES/e['filename']).read_bytes())
        if parsed.get("status")!="COMPLETED" or parsed.get("feature_count")!=e['feature_count'] or parsed.get("source_crs")!=e['crs']:
            raise AssertionError(f"{key}: wrong engine status/features/CRS: {parsed.get('status')}, {parsed.get('feature_count')}, {parsed.get('source_crs')}")
        verify_results(parsed["features"],e,full=True)
        print(f"  PASS {key:20s} {perf_counter()-start:.3f}s")
    print("\nPREFLIGHT PASSED. Fixtures are suitable for controlled local benchmarks.")


if __name__=="__main__":
    main()
