"""Build the worldwide runway table from OurAirports (public domain).

    curl -o runways.csv https://davidmegginson.github.io/ourairports-data/runways.csv
    curl -o airports.csv https://davidmegginson.github.io/ourairports-data/airports.csv
    python -B tools/build_runways.py runways.csv airports.csv

Writes crewbrief/runways.json.gz keyed by ICAO-style ident: every open land airport (large, medium or
small) with a runway of at least 2,000 ft. Source: https://ourairports.com/data/ (public domain).
For simulation use only, never for real-world navigation.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "crewbrief" / "runways.json.gz"
KEEP_TYPES = {"large_airport", "medium_airport", "small_airport"}
IDENT = re.compile(r"^[A-Z0-9]{4}$")
MIN_LENGTH_FT = 2000
WATER = {"WATER", "W"}


def number(value: str, digits: int | None = None) -> float | None:
    try:
        result = float(value) if value.strip() else None
    except ValueError:
        return None
    if result is not None and digits is not None:
        result = round(result, digits)
    return result


def point(lat: str, lon: str) -> dict[str, float] | None:
    la, lo = number(lat, 5), number(lon, 5)
    return {"lat": la, "lon": lo} if la is not None and lo is not None else None


def build(runways_csv: str, airports_csv: str) -> dict[str, list[dict]]:
    wanted: set[str] = set()
    with open(airports_csv, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["type"] in KEEP_TYPES and IDENT.match(row["ident"]):
                wanted.add(row["ident"])

    table: dict[str, list[dict]] = {}
    with open(runways_csv, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            icao = row["airport_ident"]
            if icao not in wanted or row["closed"] == "1" or row["surface"].strip().upper() in WATER:
                continue
            length = number(row["length_ft"])
            if not length or length < MIN_LENGTH_FT:
                continue
            for end, other in (("le", "he"), ("he", "le")):
                ident = row[f"{end}_ident"].strip()
                if not ident or ident.upper().startswith("H"):
                    continue
                heading = number(row[f"{end}_heading_degT"], 1)
                if heading is None:
                    # OurAirports leaves some headings blank; fall back to the runway number.
                    digits = "".join(c for c in ident if c.isdigit())
                    heading = float(digits) * 10 if digits else None
                entry = {
                    "id": ident,
                    "reciprocal": row[f"{other}_ident"].strip() or None,
                    "heading_true_deg": heading,
                    "length_ft": length,
                    "width_ft": number(row["width_ft"]),
                    "surface": row["surface"].strip()[:24] or None,
                    "threshold": point(row[f"{end}_latitude_deg"], row[f"{end}_longitude_deg"]),
                    "end": point(row[f"{other}_latitude_deg"], row[f"{other}_longitude_deg"]),
                    "elevation_ft": number(row[f"{end}_elevation_ft"]),
                    "displaced_threshold_ft": number(row[f"{end}_displaced_threshold_ft"]),
                }
                table.setdefault(icao, []).append({k: v for k, v in entry.items() if v is not None})
    return dict(sorted(table.items()))


def main(runways_csv: str, airports_csv: str) -> None:
    table = build(runways_csv, airports_csv)
    doc = {"_source": "OurAirports runways.csv + airports.csv (public domain), simulation use only", "runways": table}
    payload = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    # mtime=0 keeps the file byte-identical between rebuilds of the same data.
    OUT.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
    ends = sum(len(v) for v in table.values())
    print(f"wrote {OUT.name}: {ends} runway ends at {len(table)} airports, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
