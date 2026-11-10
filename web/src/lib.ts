// Shapes written by engine/crewbrief (board.json, crew.json, index.json) and small formatting helpers.

export interface Airline {
  slug: string;
  name: string;
  short_name: string;
  accent: string;
  logo_url: string | null;
  booking_url: string | null;
}

export interface Route {
  kind: string;
  tags: string[];
  flight_number: string | null;
  callsign: string | null;
  from: string;
  to: string;
  distance_nm: number | null;
  duration_min: number | null;
  departure_time: string | null;
  types: string[];
  days: string[];
}

export interface Airport {
  icao: string;
  iata: string | null;
  name: string;
  country: string | null;
  lat: number | null;
  lon: number | null;
  base: boolean;
}

export interface Board {
  schema: "crewbrief-board/1";
  source: "vamsys" | "demo";
  generated_at: string;
  airline: Airline;
  fleet: { code: string; name: string; type: string | null }[];
  routes: Route[];
  airports: Record<string, Airport>;
}

export interface BoardSummary extends Airline {
  source: "vamsys" | "demo";
  routes: number;
  airports: number;
  types: number;
}

export interface WindComponents {
  headwind_kt: number;
  tailwind_kt: number;
  crosswind_kt: number;
  crosswind_from: string;
  gust_headwind_kt?: number;
  gust_crosswind_kt?: number;
}

export interface CrewRunway {
  id: string;
  reciprocal: string | null;
  heading_true_deg: number | null;
  length_ft: number | null;
  width_ft: number | null;
  surface: string | null;
  elevation_ft: number | null;
  wind: WindComponents | null;
}

export interface CrewMetar {
  raw: string;
  station?: string;
  wind?: { direction_deg: number | null; speed_kt: number; gust_kt?: number; variable: boolean };
  visibility?: { value: number; unit: string };
  temperature_c?: number;
  dewpoint_c?: number;
  altimeter?: { value: number; unit: string };
  observed_at?: string;
  age_s?: number;
  stale?: boolean;
}

export interface CrewAirport {
  flight_category: "VFR" | "MVFR" | "IFR" | "LIFR" | null;
  clouds: { cover: string; base_ft: number | null }[];
  metar: CrewMetar | null;
  taf: string | null;
  runways: CrewRunway[];
  preferred_runway: string | null;
}

export interface FuelPlan {
  phases: Record<string, { minutes: number; fuel_kg: number }>;
  trip_kg: number;
  contingency_kg: number;
  reserve_minutes: number;
  reserve_kg: number;
  total_kg: number;
}

export interface ApproachCard {
  runway: { identifier?: string; orientation?: { heading_true_deg?: number }; threshold_elevation_ft?: number; length_ft?: number; glide_path_deg?: number };
  wind?: { wind_direction_true_deg: number; wind_speed_kt: number; components: WindComponents };
  aircraft: { approach_speed_kt?: number; threshold_crossing_height_ft?: number };
  target_gates: { distance_to_threshold_nm: number; target_speed_kt?: number; height_above_threshold_ft?: number; altitude_ft_msl?: number }[];
}

export interface Crew {
  generated_at: string;
  weather_source: string | null;
  airports: Record<string, CrewAirport>;
  plans: Record<string, Record<string, FuelPlan>>;
  approaches: Record<string, Record<string, ApproachCard>>;
  unmatched_types?: string[];
  notes: Record<string, string>;
}

// ------------------------------------------------------------------ validation and loading

const SLUG = /^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$/;
const HEX = /^#[0-9a-fA-F]{6}$/;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isBoard(value: unknown): value is Board {
  if (!isObject(value) || value.schema !== "crewbrief-board/1") return false;
  const airline = value.airline;
  return (value.source === "vamsys" || value.source === "demo") && typeof value.generated_at === "string"
    && isObject(airline) && typeof airline.slug === "string" && typeof airline.name === "string"
    && Array.isArray(value.routes) && Array.isArray(value.fleet) && isObject(value.airports);
}

export function isCrew(value: unknown): value is Crew {
  return isObject(value) && typeof value.generated_at === "string" && isObject(value.airports)
    && isObject(value.plans) && isObject(value.approaches);
}

export function isSlug(value: string): boolean {
  return SLUG.test(value);
}

/** Only a plain #rrggbb accent is ever written into CSS. */
export function safeAccent(value: string | null | undefined, fallback = "#1f6f5c"): string {
  return value && HEX.test(value) ? value : fallback;
}

/** Text colour that stays readable on the accent (WCAG relative luminance). */
export function onAccent(hex: string): "#ffffff" | "#10151c" {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const lum = 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
  return (1.05 / (lum + 0.05)) >= ((lum + 0.05) / 0.05) ? "#ffffff" : "#10151c";
}

async function getJson(url: string, fetcher: typeof fetch): Promise<unknown> {
  const response = await fetcher(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`request failed (${response.status})`);
  return response.json();
}

function bust(): string {
  return `t=${Math.floor(Date.now() / 60000)}`;
}

export async function loadBoard(base: string, slug: string, fetcher: typeof fetch = fetch): Promise<{ board: Board; crew: Crew }> {
  if (!isSlug(slug)) throw new Error("unknown airline");
  const [board, crew] = await Promise.all([
    getJson(`${base}${slug}/board.json?${bust()}`, fetcher),
    getJson(`${base}${slug}/crew.json?${bust()}`, fetcher),
  ]);
  if (!isBoard(board)) throw new Error("board has an unexpected shape");
  if (!isCrew(crew)) throw new Error("briefings have an unexpected shape");
  return { board, crew };
}

export async function loadIndex(base: string, fetcher: typeof fetch = fetch): Promise<BoardSummary[]> {
  const doc = await getJson(`${base}index.json?${bust()}`, fetcher);
  if (!isObject(doc) || !Array.isArray(doc.boards)) throw new Error("index has an unexpected shape");
  return doc.boards.filter((b): b is BoardSummary => isObject(b) && typeof b.slug === "string" && isSlug(b.slug) && typeof b.name === "string");
}

// ------------------------------------------------------------------ hash routing for the board

export interface BoardLocation {
  slug: string;
  route: string;
  aircraft: string;
  embed: boolean;
}

/** #/northline-demo?route=NLV101&aircraft=B738&embed=1 */
export function parseBoardHash(hash: string): BoardLocation {
  const [path = "", query = ""] = hash.replace(/^#\/?/, "").split("?");
  const params = new URLSearchParams(query);
  return {
    slug: path.split("/")[0] ?? "",
    route: params.get("route") ?? "",
    aircraft: params.get("aircraft") ?? "",
    embed: params.get("embed") === "1",
  };
}

export function boardHash(location: BoardLocation): string {
  const params = new URLSearchParams();
  if (location.route) params.set("route", location.route);
  if (location.aircraft) params.set("aircraft", location.aircraft);
  if (location.embed) params.set("embed", "1");
  const query = params.toString();
  return `#/${location.slug}${query ? `?${query}` : ""}`;
}

export function routeKey(route: Route): string {
  return route.callsign ?? route.flight_number ?? `${route.from}-${route.to}`;
}

// ------------------------------------------------------------------ formatting

const integerFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const KG_TO_LB = 2.20462;

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : integerFormat.format(value);
}

export function formatDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || minutes < 0) return "—";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

export function relativeAge(iso: string, now: Date = new Date()): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "unknown";
  const minutes = Math.round((now.getTime() - then) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export function kgToLb(kg: number): number {
  return Math.round(kg * KG_TO_LB);
}

export function windText(wind: CrewMetar["wind"] | undefined): string {
  if (!wind) return "—";
  if (wind.speed_kt === 0) return "Calm";
  const dir = wind.variable || wind.direction_deg == null ? "VRB" : String(Math.round(wind.direction_deg)).padStart(3, "0") + "°";
  return `${dir} ${Math.round(wind.speed_kt)} kt${wind.gust_kt ? ` gusting ${Math.round(wind.gust_kt)}` : ""}`;
}

export function componentText(c: WindComponents | null | undefined): string {
  if (!c) return "—";
  const along = c.tailwind_kt > 0 ? `${c.tailwind_kt} kt tail` : `${Math.max(0, c.headwind_kt)} kt head`;
  const across = c.crosswind_kt > 0 ? `${c.crosswind_kt} kt cross from ${c.crosswind_from}` : "no crosswind";
  return `${along}, ${across}`;
}
