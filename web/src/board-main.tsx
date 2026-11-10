import "@fontsource/barlow-condensed/500.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource/source-sans-3/400.css";
import "@fontsource/source-sans-3/600.css";
import "./styles.css";

import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Briefing, NetworkWeather } from "./briefing";
import type { Board, Crew } from "./lib";
import { boardHash, loadBoard, onAccent, parseBoardHash, routeKey, safeAccent } from "./lib";

const BOARDS_BASE = "../boards/";
const REFRESH_MS = 5 * 60_000;

function useHashLocation() {
  const [location, setLocation] = useState(() => parseBoardHash(window.location.hash));
  useEffect(() => {
    const onHash = () => setLocation(parseBoardHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return location;
}

/** In an iframe, tell the host page our height so it can size the frame (see the embed snippet). */
function useEmbedHeight(enabled: boolean) {
  useEffect(() => {
    if (!enabled || window.parent === window) return;
    const send = () => window.parent.postMessage({ type: "crewbrief:height", height: document.documentElement.scrollHeight }, "*");
    const observer = new ResizeObserver(send);
    observer.observe(document.body);
    send();
    return () => observer.disconnect();
  }, [enabled]);
}

function BoardApp() {
  const location = useHashLocation();
  const [data, setData] = useState<{ board: Board; crew: Crew } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEmbedHeight(location.embed);

  useEffect(() => {
    let alive = true;
    const load = () => loadBoard(BOARDS_BASE, location.slug)
      .then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : "unavailable"); });
    setData(null);
    if (!location.slug) { setError("no airline selected"); return; }
    void load();
    const timer = window.setInterval(load, REFRESH_MS);
    return () => { alive = false; window.clearInterval(timer); };
  }, [location.slug]);

  const accent = safeAccent(data?.board.airline.accent);
  useEffect(() => {
    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--on-accent", onAccent(accent));
    document.title = data ? `Crew briefings · ${data.board.airline.name}` : "Crew briefings · CrewBrief";
  }, [accent, data]);

  const routes = useMemo(
    () => [...(data?.board.routes ?? [])].sort((a, b) => routeKey(a).localeCompare(routeKey(b), undefined, { numeric: true })),
    [data],
  );
  const route = routes.find((r) => routeKey(r) === location.route) ?? routes[0];
  const type = route && route.types.includes(location.aircraft) ? location.aircraft : route?.types[0] ?? "";
  const names = Object.fromEntries((data?.board.fleet ?? []).map((f) => [f.code, f.name]));

  const go = (next: Partial<typeof location>) => {
    window.history.replaceState(null, "", boardHash({ ...location, ...next }));
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  };

  const byOrigin = useMemo(() => {
    const groups = new Map<string, typeof routes>();
    for (const r of routes) groups.set(r.from, [...(groups.get(r.from) ?? []), r]);
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [routes]);

  return (
    <div className={location.embed ? "is-embed" : undefined}>
      {!location.embed ? (
        <header className="board-bar">
          <div className="board-bar__inner">
            {data?.board.airline.logo_url ? <img className="board-bar__logo" src={data.board.airline.logo_url} alt="" /> : null}
            <div>
              <div className="board-bar__name">{data?.board.airline.name ?? "Crew briefings"}</div>
              <div className="board-bar__sub">Crew briefings</div>
            </div>
          </div>
        </header>
      ) : null}
      {data?.board.source === "demo" ? (
        <div className="notice" role="status">Demo board: the weather is live; the schedule updates itself once an airline connects vAMSYS.</div>
      ) : null}

      <main id="main" className="page">
        {error && !data ? (
          <p className="lede">This briefing board isn't available right now ({error}).</p>
        ) : !data ? (
          <p className="lede" aria-busy="true">Loading briefings…</p>
        ) : routes.length === 0 ? (
          <p className="lede">No routes are published yet.</p>
        ) : (
          <>
            <form className="picker" onSubmit={(e) => e.preventDefault()}>
              <label>
                <span>Flight</span>
                <select value={route ? routeKey(route) : ""} onChange={(e) => go({ route: e.target.value, aircraft: "" })}>
                  {byOrigin.map(([origin, list]) => (
                    <optgroup key={origin} label={`From ${origin}`}>
                      {list.map((r) => <option key={routeKey(r)} value={routeKey(r)}>{routeKey(r)} · {r.from} → {r.to}</option>)}
                    </optgroup>
                  ))}
                </select>
              </label>
              <label>
                <span>Aircraft</span>
                <select value={type} onChange={(e) => go({ route: route ? routeKey(route) : "", aircraft: e.target.value })}>
                  {(route?.types ?? []).map((t) => <option key={t} value={t}>{names[t] ?? t}</option>)}
                </select>
              </label>
              <button type="button" className="button button--quiet" onClick={() => window.print()}>Print briefing</button>
            </form>
            {route ? <Briefing board={data.board} crew={data.crew} route={route} type={type} /> : null}
            <NetworkWeather crew={data.crew} />
          </>
        )}
      </main>
      <p className="powered">Briefings by <a href="../" target="_top">CrewBrief</a> · for flight simulation only</p>
    </div>
  );
}

const root = document.getElementById("root");
if (root) createRoot(root).render(<StrictMode><BoardApp /></StrictMode>);
