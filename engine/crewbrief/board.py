"""Fetch an airline's schedule from vAMSYS and shape the public board file.

CrewBrief needs only the schedule: fleet types, airports and routes. It never requests pilots,
PIREPs, live flights or statistics, so no pilot data is ever read or stored.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from . import BOARD_SCHEMA
from .snapshot import build_snapshot
from .tenants import Tenant

SCHEDULE_ENDPOINTS = ("fleet", "airports", "routes")


def fetch_schedule(client: Any, *, page_size: int = 100) -> dict[str, Any]:
    page = {"page[size]": page_size}
    return {
        "fleet": client.get_collection("/fleet", page),
        "airports": client.get_collection("/airports", page),
        "routes": client.get_collection("/routes", {**page, "filter[hidden]": "false"}),
    }


def schedule_only(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Drop everything but the schedule from a raw payload (used for demo files too)."""
    return {key: raw.get(key) for key in SCHEDULE_ENDPOINTS}


def build_board(raw: Mapping[str, Any], tenant: Tenant, *, now: datetime, source: str) -> dict[str, Any]:
    snapshot = build_snapshot(schedule_only(raw), {"name": tenant.name, "short_name": tenant.short_name},
                              now=now, source=source)
    used_types = {code for route in snapshot["routes"] for code in route["types"]}
    return {
        "schema": BOARD_SCHEMA,
        "source": source,
        "generated_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "airline": tenant.public(),
        "fleet": [
            {"code": f["code"], "name": f["name"], "type": f["type"]}
            for f in snapshot["fleet"]
            if f["code"] in used_types
        ],
        "routes": snapshot["routes"],
        "airports": snapshot["airports"],
    }
