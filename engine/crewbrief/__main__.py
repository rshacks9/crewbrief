"""Build every airline's briefing board.

    python -B -m crewbrief --tenants ../tenants --out ../web/public/boards
    python -B -m crewbrief --tenants ../tenants --out ../web/public/boards --offline

For each active tenant this writes ``<out>/<slug>/board.json`` (schedule) and ``crew.json``
(weather, runway winds, fuel and approach cards), plus ``<out>/index.json`` listing the public
demo boards. One airline failing never blocks the others: with ``--previous-base`` its last
deployed files are carried over. Output is counts only: no names of pilots, tokens or bodies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .board import build_board, fetch_schedule
from .crew import build_crew, fetch_weather
from .tenants import Tenant, TenantError, load_tenants

MAX_PREVIOUS_BYTES = 8 * 1024 * 1024


def write_atomic(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"
    handle, temp_name = tempfile.mkstemp(prefix=".board-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def fetch_live(tenant: Tenant, credentials: tuple[str, str]) -> dict[str, Any]:
    from vamsys.client import ClientConfig, VamsysClient
    from vamsys.official import BASE_URL

    env = {"VAMSYS_BASE_URL": os.environ.get("VAMSYS_BASE_URL", BASE_URL),
           "VAMSYS_CLIENT_ID": credentials[0], "VAMSYS_CLIENT_SECRET": credentials[1]}
    return fetch_schedule(VamsysClient(ClientConfig.from_env(env)))


def fetch_previous(base: str, slug: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """The last deployed board for ``slug``, so a vAMSYS outage does not take a customer offline."""
    docs = []
    for name in ("board.json", "crew.json"):
        url = f"{base.rstrip('/')}/{slug}/{name}"
        if not url.startswith("https://"):
            return None
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "crewbrief/1"}), timeout=15) as response:  # noqa: S310
                body = response.read(MAX_PREVIOUS_BYTES + 1)
            if len(body) > MAX_PREVIOUS_BYTES:
                return None
            docs.append(json.loads(body.decode("utf-8")))
        except Exception:  # noqa: BLE001 - any failure just means "nothing to carry over"
            return None
    return docs[0], docs[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crewbrief")
    parser.add_argument("--tenants", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--only", help="build a single tenant slug")
    parser.add_argument("--offline", action="store_true", help="no vAMSYS or weather calls; demo data only")
    parser.add_argument("--previous-base", help="https URL of the deployed boards/ folder, for carry-over")
    args = parser.parse_args(argv)

    try:
        tenants = [t for t in load_tenants(args.tenants) if t.active and (not args.only or t.slug == args.only)]
    except TenantError as error:
        print(f"status=config-error {error}", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    boards: dict[str, tuple[Tenant, dict[str, Any]]] = {}
    carried: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    status: dict[str, str] = {}

    for tenant in tenants:
        credentials = None if args.offline else tenant.credentials(os.environ)
        if tenant.source == "vamsys" and credentials:
            try:
                raw = fetch_live(tenant, credentials)
                boards[tenant.slug] = (tenant, build_board(raw, tenant, now=now, source="vamsys"))
                status[tenant.slug] = "live"
                continue
            except Exception as error:  # noqa: BLE001 - one airline must never break the rest
                previous = fetch_previous(args.previous_base, tenant.slug) if args.previous_base else None
                if previous:
                    carried[tenant.slug] = previous
                    status[tenant.slug] = f"carried-over({type(error).__name__})"
                else:
                    status[tenant.slug] = f"error({type(error).__name__})"
                continue
        if tenant.fallback_raw is not None:
            raw = json.loads(tenant.fallback_raw.read_text(encoding="utf-8"))
            boards[tenant.slug] = (tenant, build_board(raw, tenant, now=now, source="demo"))
            status[tenant.slug] = "demo"
        else:
            status[tenant.slug] = "no-credentials"

    weather = None
    weather_status = "off"
    if boards and not args.offline and os.environ.get("CREWBRIEF_NO_WEATHER") != "1":
        icaos = {icao for _, board in boards.values() for icao in board["airports"]}
        try:
            weather = fetch_weather(icaos)
            weather_status = f"ok({len(weather)})"
        except Exception as error:  # noqa: BLE001 - weather outages must never block a deploy
            weather_status = f"unavailable({type(error).__name__})"

    index: list[dict[str, Any]] = []
    for slug, (tenant, board) in boards.items():
        crew = build_crew({"airports": board["airports"], "routes": board["routes"]}, now=now, weather_raw=weather,
                          type_map=tenant.type_map, profile_overrides=tenant.fuel_overrides)
        write_atomic(args.out / slug / "board.json", board)
        write_atomic(args.out / slug / "crew.json", crew)
        unmatched = len(crew["unmatched_types"])
        status[slug] += f" routes={len(board['routes'])} airports={len(board['airports'])} unmatched_types={unmatched}"
        if tenant.listed:
            index.append({**tenant.public(), "source": board["source"], "routes": len(board["routes"]),
                          "airports": len(board["airports"]), "types": len(board["fleet"])})
    for slug, (board, crew) in carried.items():
        write_atomic(args.out / slug / "board.json", board)
        write_atomic(args.out / slug / "crew.json", crew)
    write_atomic(args.out / "index.json", {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "boards": index})

    for slug in sorted(status):
        print(f"tenant={slug} status={status[slug]}")
    print(f"status=ok tenants={len(tenants)} built={len(boards)} carried={len(carried)} weather={weather_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
