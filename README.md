# CrewBrief

Ready-made pilot briefings for vAMSYS virtual airlines, sold per airline per month. One build job
turns each airline's vAMSYS schedule into a white-label briefing board for every route and aircraft
type: live METAR/TAF, runway wind components and the favoured runway, fuel by phase, and a 3°
approach card. It grew out of the Crossroads Executive & Charter Crew Tools page.

("CrewBrief" is a working name. Check the name and domain before launch.)

```
tenants/*.json ──┐
vAMSYS (ops:read, schedule only) ──> engine/ ──> web/public/boards/<slug>/{board,crew}.json ──> static site
aviationweather.gov ──┘        Kimi's Jumpseat modules          landing page + board/#/<slug>
```

## Layout

| Path | What it is |
| --- | --- |
| `tenants/` | One JSON file per airline (brand, aircraft mapping, fuel overrides). Demo schedules as `*.raw.json` |
| `engine/crewbrief/` | Build command, tenant loader, schedule fetch, briefing builder |
| `engine/kimi_tools/` | Kimi's weather, fuel, performance and approach modules, vendored unchanged |
| `engine/vamsys/` | Read-only vAMSYS client (from the Crossroads site) |
| `engine/crewbrief/runways.json.gz` | 49,000 runway ends at 20,800 airports from OurAirports (public domain) |
| `engine/crewbrief/fuel_profiles.json` | Planning fuel flows for 61 aircraft types |
| `web/` | Vite + React: landing page (`index.html`) and the white-label board (`board/index.html`) |
| `.github/workflows/build-deploy.yml` | Tests, build every board, deploy to GitHub Pages every 20 minutes |

## Run it locally

```bash
cd engine
python -B -m unittest discover -s tests -t .
python -B -m crewbrief --tenants ../tenants --out ../web/public/boards      # add --offline to skip network

cd ../web
npm install
npm test
npm run build && npm run preview     # http://localhost:4190
```

## Onboard a new airline

1. The airline owner creates an API client in vAMSYS Orwell with only the `ops:read` scope.
2. Get the client ID and secret through a private channel (not email or Discord). All airlines'
   keys live in one repository secret, `CREWBRIEF_TENANT_KEYS`, as JSON:

   ```json
   {"CREWBRIEF_SKY_EXPRESS_CLIENT_ID": "…", "CREWBRIEF_SKY_EXPRESS_CLIENT_SECRET": "…"}
   ```

   The key names are the slug in capitals with dashes as underscores (`sky-express` → `SKY_EXPRESS`).
   GitHub secrets can't be read back, so keep the master copy in a password manager and paste the
   whole JSON again when you add an airline. (Passing all secrets with `toJSON(secrets)` gets the
   workflow flagged by GitHub as possibly malicious, so don't.)
3. Add `tenants/<slug>.json`:

   ```json
   {
     "slug": "sky-express",
     "name": "Sky Express Virtual",
     "short_name": "Sky Express",
     "source": "vamsys",
     "accent": "#0a5cad",
     "logo_url": "https://example.com/logo.png",
     "booking_url": "https://vamsys.io/login",
     "listed": false,
     "type_map": { "A20N-LEAP": "A20N", "B738 WL": "B738" },
     "fuel_overrides": {}
   }
   ```

4. Push. The next run prints `tenant=sky-express status=live routes=… unmatched_types=…`. If
   `unmatched_types` is not 0, add those fleet codes to `type_map`, or add a profile to
   `fuel_overrides` (kg/h for cruise, climb, descent, taxi and holding, plus `vref_kt`).
5. Send the owner `https://<site>/board/#/sky-express` and the embed code from the landing page.

To pause an airline that stops paying, set `"active": false`. Its board disappears on the next deploy.

## Privacy and safety

- The engine requests only `/fleet`, `/airports` and `/routes`. It never asks vAMSYS for pilots, PIREPs,
  live flights or statistics. A test checks that pilot data in a raw payload never reaches a board.
- vAMSYS Owner Terms §6.3: the airline is responsible for any third party it gives API
  credentials to, and the limit is 100 requests per minute per airline. CrewBrief makes 3 or more
  calls per airline every 20 minutes (one per page of results).
- Credentials exist only in the `CREWBRIEF_TENANT_KEYS` repository secret, and only the build step sees it. Logs show counts,
  never values or response bodies.
- If one airline's vAMSYS call fails, the others still build. With `CREWBRIEF_PUBLIC_URL` set, the
  failing airline keeps its last deployed board. A weather outage never blocks a deploy.
- Briefings are for flight simulation only. Fuel figures are planning estimates. Pilots dispatch
  with SimBrief.

## Before taking money

- Pick the final name and domain, and confirm the prices in `web/src/product.ts` (early access emails go to the address set there).
- Use a payment processor with hosted checkout, such as Stripe Payment Links, so no card data
  ever touches this site.
- Write terms of service and a privacy notice.
- If you use VATSIM branding or market to VATSIM partner airlines, read VATSIM's commercial-use
  rules first.
- Map tiles are not used, so OpenStreetMap's tile policy does not apply. Add a paid tile provider
  if a map is added later.
