"""Seed exactly one verified API record per fixture for stable read-only load."""
from __future__ import annotations
from pathlib import Path
import json
import sys
import requests
from fixture_lib import load_manifest, enforce_local_only, verify_results, FIXTURES, READ_TARGETS

URL="http://127.0.0.1:18130"


def main():
    enforce_local_only(URL)
    entries=load_manifest()
    try:
        h=requests.get(f"{URL}/health",timeout=10)
        h.raise_for_status()
        if h.json().get("status")!="healthy":
            raise ValueError("Unexpected API health response")
    except Exception as exc:
        raise SystemExit(f"Start isolated local benchmark server first: {exc}") from exc
    targets={}
    for key,e in entries.items():
        content=(FIXTURES/e["filename"]).read_bytes()
        mime="application/geo+json" if e["filename"].endswith(".geojson") else (
            "application/zip" if e["filename"].endswith((".zip",".kmz")) else "application/vnd.google-earth.kml+xml")
        try:
            resp=requests.post(f"{URL}/api/files/",files={"file":(e["filename"],content,mime)},timeout=120)
            resp.raise_for_status()
            if resp.status_code!=201:
                raise ValueError(f"Expected 201, got {resp.status_code}")
            meta=resp.json()
            if meta.get("feature_count")!=e["feature_count"] or meta.get("successful_measurements")!=e["successful_measurements"] or meta.get("sha256")!=e["sha256"]:
                raise ValueError("Unexpected upload metadata or checksum")
            fid=meta["id"]
            r=requests.get(f"{URL}/api/files/{fid}/measurements/",timeout=120)
            r.raise_for_status()
            verify_results(r.json()["measurements"],e,full=True)
            targets[key]={"id":fid,"sha256":e["sha256"]}
        except Exception as exc:
            raise SystemExit(f"Failed to seed/verify {key}: {exc}") from exc
        print(f"PASS {key}: seeded id {fid}")
    READ_TARGETS.write_text(json.dumps({"server":URL,"targets":targets},indent=2)+"\n",encoding="utf-8")
    print(f"Saved stable read-only targets to {READ_TARGETS}")

if __name__=="__main__":
    main()
