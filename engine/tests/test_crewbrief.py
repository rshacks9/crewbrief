"""CrewBrief engine: tenants, credentials, schedule-only fetch, type mapping and the build command."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from crewbrief import __main__ as cli
from crewbrief.board import SCHEDULE_ENDPOINTS, build_board, fetch_schedule
from crewbrief.crew import build_crew, fetch_weather, load_profiles, load_runways
from crewbrief.tenants import TenantError, load_tenants, parse_tenant

ROOT = Path(__file__).resolve().parents[2]
TENANTS = ROOT / "tenants"
NOW = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)


def write_tenant(directory: Path, doc: dict, raw: dict | None = None) -> Path:
    path = directory / f"{doc['slug']}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    if raw is not None:
        (directory / doc["fallback_raw"]).write_text(json.dumps(raw), encoding="utf-8")
    return path


MINI_RAW = {
    "airports": [
        {"id": 1, "icao": "EHAM", "name": "Amsterdam", "latitude": 52.3, "longitude": 4.76},
        {"id": 2, "icao": "EGLL", "name": "Heathrow", "latitude": 51.47, "longitude": -0.46},
    ],
    "fleet": [{"id": 7, "code": "A20N-LEAP", "name": "A320neo", "type": "pax"}, {"id": 8, "code": "ZZZZ", "name": "Mystery", "type": "pax"}],
    "routes": [{"id": 1, "departure_id": 1, "arrival_id": 2, "callsign": "TST1", "flight_number": "T1",
                "flight_distance": 200, "flight_length": "01:00:00", "fleet_ids": [7, 8], "hidden": False}],
    # Present in a raw dump but must never reach the board.
    "pireps": [{"id": 1, "pilot": {"username": "secret-pilot"}}],
    "flight_map": [{"pilot": {"username": "secret-pilot"}}],
}


class TenantTests(unittest.TestCase):
    def test_bundled_tenants_are_valid(self):
        tenants = {t.slug: t for t in load_tenants(TENANTS)}
        self.assertIn("crossroads", tenants)
        self.assertIn("northline-demo", tenants)
        self.assertEqual(tenants["northline-demo"].type_map, {"A20N-LEAP": "A20N"})

    def test_rejects_bad_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            base = {"slug": "ok-air", "name": "OK Air", "source": "vamsys"}
            cases = [
                ({**base, "slug": "Bad Slug"}, "slug"),
                ({**base, "accent": "red; background:url(x)"}, "accent"),
                ({**base, "logo_url": "javascript:alert(1)"}, "https"),
                ({**base, "source": "demo"}, "fallback_raw"),
                ({**base, "fallback_raw": "../../etc/passwd.raw.json"}, "fallback_raw"),
                ({**base, "type_map": {"X": "not a type"}}, "type_map"),
                ({**base, "fuel_overrides": {"A20N": {"cruise": -1}}}, "fuel_overrides"),
            ]
            for doc, needle in cases:
                path = d / "ok-air.json" if doc["slug"] == "ok-air" else d / "bad.json"
                with self.subTest(needle=needle), self.assertRaises(TenantError) as ctx:
                    parse_tenant(doc, path)
                self.assertIn(needle, str(ctx.exception))

    def test_file_name_must_match_slug(self):
        with self.assertRaises(TenantError):
            parse_tenant({"slug": "a-air", "name": "A", "source": "vamsys"}, Path("b-air.json"))

    def test_credentials_from_plain_env_or_packed_secrets(self):
        tenant = parse_tenant({"slug": "sky-express", "name": "Sky", "source": "vamsys"}, Path("sky-express.json"))
        self.assertIsNone(tenant.credentials({}))
        plain = {"CREWBRIEF_SKY_EXPRESS_CLIENT_ID": "id1", "CREWBRIEF_SKY_EXPRESS_CLIENT_SECRET": "s1"}
        self.assertEqual(tenant.credentials(plain), ("id1", "s1"))
        packed = {"CREWBRIEF_SECRETS": json.dumps({"CREWBRIEF_SKY_EXPRESS_CLIENT_ID": "id2", "CREWBRIEF_SKY_EXPRESS_CLIENT_SECRET": "s2"})}
        self.assertEqual(tenant.credentials(packed), ("id2", "s2"))
        self.assertNotIn("secret", json.dumps(tenant.public()).lower())


class FakeClient:
    def __init__(self):
        self.paths: list[str] = []

    def get_collection(self, path, query=None):
        self.paths.append(path)
        return MINI_RAW[path.strip("/")]


class BoardTests(unittest.TestCase):
    def test_fetch_requests_schedule_only(self):
        client = FakeClient()
        raw = fetch_schedule(client)
        self.assertEqual(sorted(client.paths), ["/airports", "/fleet", "/routes"])
        self.assertEqual(set(raw), set(SCHEDULE_ENDPOINTS))

    def test_board_never_contains_pilot_data(self):
        tenant = parse_tenant({"slug": "t-air", "name": "T Air", "source": "vamsys"}, Path("t-air.json"))
        board = build_board(MINI_RAW, tenant, now=NOW, source="demo")
        text = json.dumps(board)
        self.assertNotIn("secret-pilot", text)
        self.assertEqual(board["schema"], "crewbrief-board/1")
        self.assertEqual([r["callsign"] for r in board["routes"]], ["TST1"])
        self.assertEqual({f["code"] for f in board["fleet"]}, {"A20N-LEAP", "ZZZZ"})

    def test_type_map_and_unmatched_types(self):
        tenant = parse_tenant({"slug": "t-air", "name": "T Air", "source": "vamsys", "type_map": {"A20N-LEAP": "A20N"}}, Path("t-air.json"))
        board = build_board(MINI_RAW, tenant, now=NOW, source="demo")
        crew = build_crew(board, now=NOW, weather_raw=None, type_map=tenant.type_map)
        self.assertIn("A20N-LEAP", crew["plans"]["TST1"])
        self.assertEqual(crew["unmatched_types"], ["ZZZZ"])
        self.assertIn("A20N-LEAP", crew["approaches"]["EGLL"])

    def test_fuel_override_replaces_default(self):
        board = build_board(MINI_RAW, parse_tenant({"slug": "t-air", "name": "T", "source": "vamsys"}, Path("t-air.json")), now=NOW, source="demo")
        heavy = {"cruise": 9000, "climb": 9000, "descent": 9000, "taxi": 9000, "holding": 9000}
        base = build_crew(board, now=NOW, weather_raw=None, type_map={"A20N-LEAP": "A20N"})
        tuned = build_crew(board, now=NOW, weather_raw=None, type_map={"A20N-LEAP": "A20N"}, profile_overrides={"A20N": heavy})
        self.assertGreater(tuned["plans"]["TST1"]["A20N-LEAP"]["trip_kg"], base["plans"]["TST1"]["A20N-LEAP"]["trip_kg"])


class DataTests(unittest.TestCase):
    def test_worldwide_runways_cover_major_airports(self):
        runways = load_runways()
        self.assertGreater(len(runways), 15000)
        for icao in ("EHAM", "KJFK", "EGLL", "YSSY", "RJTT", "KTYQ", "FAOR"):
            self.assertTrue(runways.get(icao), icao)
        sample = runways["EHAM"][0]
        self.assertTrue({"id", "heading_true_deg", "length_ft"} <= set(sample))

    def test_profiles_cover_common_types_and_are_sane(self):
        profiles = load_profiles()["profiles"]
        for code in ("A20N", "A320", "A21N", "B738", "B38M", "B789", "A359", "E190", "CRJ9", "DH8D", "C172", "A388", "B77L"):
            self.assertIn(code, profiles)
        for code, p in profiles.items():
            with self.subTest(code=code):
                self.assertTrue(p["descent"] < p["cruise"] < p["climb"], code)
                self.assertTrue(p["taxi"] < p["cruise"], code)
                self.assertTrue(50 <= p["vref_kt"] <= 170, code)

    def test_weather_requests_are_chunked(self):
        urls: list[str] = []

        def fake_fetch(url):
            urls.append(url)
            return []

        icaos = [f"K{chr(65 + i // 26)}{chr(65 + i % 26)}A" for i in range(200)]
        fetch_weather(icaos, fetch=fake_fetch)
        self.assertEqual(len(urls), 6)  # 3 chunks × (METAR + TAF)
        self.assertTrue(all(url.startswith("https://aviationweather.gov/api/data/") for url in urls))


class CliTests(unittest.TestCase):
    def run_cli(self, *args, env=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict("os.environ", env or {}, clear=True), redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_offline_build_writes_boards_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = self.run_cli("--tenants", str(TENANTS), "--out", tmp, "--offline")
            self.assertEqual(code, 0)
            self.assertIn("tenant=crossroads status=demo", out)
            index = json.loads((Path(tmp) / "index.json").read_text(encoding="utf-8"))
            self.assertEqual({b["slug"] for b in index["boards"]}, {"crossroads", "northline-demo"})
            board = json.loads((Path(tmp) / "northline-demo" / "board.json").read_text(encoding="utf-8"))
            crew = json.loads((Path(tmp) / "northline-demo" / "crew.json").read_text(encoding="utf-8"))
            self.assertEqual(len(board["routes"]), len(crew["plans"]))
            self.assertEqual(crew["unmatched_types"], [])

    def test_failing_airline_is_carried_over_and_others_still_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "tenants"
            d.mkdir()
            write_tenant(d, {"slug": "live-air", "name": "Live Air", "source": "vamsys"})
            write_tenant(d, {"slug": "demo-air", "name": "Demo Air", "source": "demo", "fallback_raw": "demo-air.raw.json"}, MINI_RAW)
            env = {"CREWBRIEF_LIVE_AIR_CLIENT_ID": "id", "CREWBRIEF_LIVE_AIR_CLIENT_SECRET": "very-secret-value", "CREWBRIEF_NO_WEATHER": "1"}
            previous = ({"schema": "crewbrief-board/1", "old": True}, {"generated_at": "x"})
            with mock.patch.object(cli, "fetch_live", side_effect=RuntimeError("very-secret-value")), \
                 mock.patch.object(cli, "fetch_previous", return_value=previous):
                code, out, err = self.run_cli("--tenants", str(d), "--out", str(Path(tmp) / "out"),
                                              "--previous-base", "https://example.test/boards/", env=env)
            self.assertEqual(code, 0)
            self.assertIn("tenant=live-air status=carried-over(RuntimeError)", out)
            self.assertIn("tenant=demo-air status=demo", out)
            self.assertNotIn("very-secret-value", out + err)
            carried = json.loads((Path(tmp) / "out" / "live-air" / "board.json").read_text(encoding="utf-8"))
            self.assertTrue(carried["old"])

    def test_missing_credentials_without_fallback_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "tenants"
            d.mkdir()
            write_tenant(d, {"slug": "new-air", "name": "New Air", "source": "vamsys"})
            code, out, _ = self.run_cli("--tenants", str(d), "--out", str(Path(tmp) / "out"), "--offline")
            self.assertEqual(code, 0)
            self.assertIn("tenant=new-air status=no-credentials", out)
            self.assertFalse((Path(tmp) / "out" / "new-air").exists())

    def test_config_error_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "broken.json").write_text("{not json", encoding="utf-8")
            code, _, err = self.run_cli("--tenants", tmp, "--out", str(Path(tmp) / "out"), "--offline")
            self.assertEqual(code, 2)
            self.assertIn("config-error", err)


class VendoredTests(unittest.TestCase):
    """kimi_tools must stay byte-identical to Kimi's Jumpseat plugins when that workspace is present."""

    UPSTREAM = ROOT.parent / "venture" / "plugins"
    PAIRS = {
        "weather.py": "weather_briefing/weather.py",
        "fuel_core.py": "fuel_planner/core.py",
        "performance.py": "performance_calculator/calculations.py",
        "approach.py": "approach_briefing/plugin.py",
    }

    @unittest.skipUnless((ROOT.parent / "venture" / "plugins").is_dir(), "Kimi's workspace not present")
    def test_vendored_files_match_upstream(self):
        for local, upstream in self.PAIRS.items():
            self.assertEqual((ROOT / "engine" / "kimi_tools" / local).read_bytes(), (self.UPSTREAM / upstream).read_bytes(), local)


if __name__ == "__main__":
    unittest.main()
