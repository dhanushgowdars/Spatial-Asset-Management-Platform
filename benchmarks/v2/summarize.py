"""Summarize completed Locust *_stats.csv files, separating upload RPS."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("csv",nargs="+",type=Path,help="Locust *_stats.csv files")
    args=parser.parse_args()
    for path in args.csv:
        if not path.is_file():
            raise SystemExit(f"Missing file: {path}")
        with path.open(encoding="utf-8-sig",newline="") as f:
            rows=list(csv.DictReader(f))
        rows=[r for r in rows if r.get("Name")]
        aggregate=next((r for r in rows if r.get("Name")=="Aggregated"),None)
        uploads=[r for r in rows if r.get("Type")=="POST" and r.get("Name", "").startswith("POST [")]
        rps=sum(float(r.get("Requests/s") or 0) for r in uploads)
        count=sum(int(float(r.get("Request Count") or 0)) for r in uploads)
        failed=sum(int(float(r.get("Failure Count") or 0)) for r in uploads)
        print(f"\n{path}\n  uploads: {count} requests, {failed} failures, approximately {rps:.2f} uploads/sec")
        if aggregate:
            print(f"  all HTTP: {aggregate.get('Request Count')} requests, {aggregate.get('Failure Count')} failures, {aggregate.get('Requests/s')} req/sec")
        print("  Operation                         reqs  fail    p50 ms    p95 ms    req/s")
        for row in rows:
            if row.get("Name")=="Aggregated":continue
            print(f"  {row.get('Name','')[:33]:33s} {row.get('Request Count',''):>5s} {row.get('Failure Count',''):>5s} {row.get('50%',''):>9s} {row.get('95%',''):>9s} {row.get('Requests/s',''):>8s}")


if __name__=="__main__":main()
