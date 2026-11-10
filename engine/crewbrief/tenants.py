"""Customer (tenant) configuration and credentials.

Each airline is one JSON file in ``tenants/``. Credentials never live in those files: they come
from the environment, either as plain variables or as one JSON object in ``CREWBRIEF_SECRETS``
(GitHub Actions passes ``toJSON(secrets)``). For airline slug ``sky-express`` the names are
``CREWBRIEF_SKY_EXPRESS_CLIENT_ID`` and ``CREWBRIEF_SKY_EXPRESS_CLIENT_SECRET``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
ICAO_TYPE = re.compile(r"^[A-Z0-9]{2,4}$")
PROFILE_KEYS = ("cruise", "climb", "descent", "taxi", "holding")
SOURCES = ("vamsys", "demo")


class TenantError(ValueError):
    """A tenant file is invalid. The message names the file and field, never a secret."""


@dataclass(frozen=True)
class Tenant:
    slug: str
    name: str
    short_name: str
    source: str
    accent: str = "#e8703a"
    logo_url: str | None = None
    booking_url: str | None = None
    listed: bool = False
    active: bool = True
    fallback_raw: Path | None = None
    type_map: dict[str, str] = field(default_factory=dict)
    fuel_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def env_prefix(self) -> str:
        return "CREWBRIEF_" + self.slug.upper().replace("-", "_")

    def credentials(self, environ: Mapping[str, str]) -> tuple[str, str] | None:
        bag: dict[str, Any] = dict(environ)
        packed = environ.get("CREWBRIEF_SECRETS")
        if packed:
            try:
                extra = json.loads(packed)
            except json.JSONDecodeError as error:
                raise TenantError("CREWBRIEF_SECRETS is not valid JSON") from error
            if isinstance(extra, dict):
                bag = {**extra, **bag}
        client_id = bag.get(f"{self.env_prefix}_CLIENT_ID")
        secret = bag.get(f"{self.env_prefix}_CLIENT_SECRET")
        if isinstance(client_id, str) and isinstance(secret, str) and client_id.strip() and secret.strip():
            return client_id.strip(), secret.strip()
        return None

    def public(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "short_name": self.short_name,
            "accent": self.accent,
            "logo_url": self.logo_url,
            "booking_url": self.booking_url,
        }


def _https(value: Any, where: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not value.startswith("https://") or len(value) > 300 or any(c.isspace() for c in value):
        raise TenantError(f"{where}: must be an https:// URL")
    return value


def _text(value: Any, where: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise TenantError(f"{where}: required text, at most {limit} characters")
    return value.strip()


def parse_tenant(doc: Mapping[str, Any], path: Path) -> Tenant:
    where = path.name
    slug = doc.get("slug")
    if not isinstance(slug, str) or not SLUG.match(slug):
        raise TenantError(f"{where}: slug must be lowercase letters, digits and dashes")
    if path.stem != slug:
        raise TenantError(f"{where}: file name must be {slug}.json")
    source = doc.get("source", "vamsys")
    if source not in SOURCES:
        raise TenantError(f"{where}: source must be one of {SOURCES}")
    accent = doc.get("accent", "#e8703a")
    if not isinstance(accent, str) or not HEX.match(accent):
        raise TenantError(f"{where}: accent must look like #1a2b3c")

    fallback = doc.get("fallback_raw")
    fallback_path: Path | None = None
    if fallback is not None:
        if not isinstance(fallback, str) or "/" in fallback or "\\" in fallback or not fallback.endswith(".raw.json"):
            raise TenantError(f"{where}: fallback_raw must be a *.raw.json file next to the tenant file")
        fallback_path = path.with_name(fallback)
        if not fallback_path.is_file():
            raise TenantError(f"{where}: fallback_raw file {fallback} not found")
    if source == "demo" and fallback_path is None:
        raise TenantError(f"{where}: demo tenants need fallback_raw")

    type_map: dict[str, str] = {}
    for key, value in (doc.get("type_map") or {}).items():
        if not isinstance(key, str) or not isinstance(value, str) or not ICAO_TYPE.match(value):
            raise TenantError(f"{where}: type_map values must be ICAO type designators like A20N")
        type_map[key] = value

    overrides: dict[str, dict[str, Any]] = {}
    for key, value in (doc.get("fuel_overrides") or {}).items():
        if not isinstance(key, str) or not ICAO_TYPE.match(key) or not isinstance(value, dict):
            raise TenantError(f"{where}: fuel_overrides keys must be ICAO types with a profile object")
        for phase in PROFILE_KEYS:
            flow = value.get(phase)
            if not isinstance(flow, (int, float)) or isinstance(flow, bool) or not 0 < flow < 100_000:
                raise TenantError(f"{where}: fuel_overrides.{key}.{phase} must be kg/h between 0 and 100000")
        overrides[key] = dict(value)

    return Tenant(
        slug=slug,
        name=_text(doc.get("name"), f"{where}: name", 80),
        short_name=_text(doc.get("short_name") or doc.get("name"), f"{where}: short_name", 30),
        source=source,
        accent=accent,
        logo_url=_https(doc.get("logo_url"), f"{where}: logo_url"),
        booking_url=_https(doc.get("booking_url"), f"{where}: booking_url"),
        listed=doc.get("listed") is True,
        active=doc.get("active", True) is not False,
        fallback_raw=fallback_path,
        type_map=type_map,
        fuel_overrides=overrides,
    )


def load_tenants(directory: Path) -> list[Tenant]:
    tenants: list[Tenant] = []
    for path in sorted(directory.glob("*.json")):
        if path.name.endswith(".raw.json"):
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise TenantError(f"{path.name}: not valid JSON ({error.msg})") from error
        tenants.append(parse_tenant(doc, path))
    slugs = [t.slug for t in tenants]
    if len(slugs) != len(set(slugs)):
        raise TenantError("duplicate tenant slugs")
    return tenants
