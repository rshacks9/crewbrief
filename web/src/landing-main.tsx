import "@fontsource/barlow-condensed/500.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource/source-sans-3/400.css";
import "@fontsource/source-sans-3/600.css";
import "./styles.css";

import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { BoardSummary } from "./lib";
import { loadIndex, safeAccent } from "./lib";
import { PRODUCT } from "./product";

function Mark() {
  // A folded flight strip with a heading tick.
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <rect x="3" y="7" width="26" height="18" rx="2" fill="#f5f3ee" />
      <rect x="3" y="7" width="8" height="18" rx="2" fill="#1f6f5c" />
      <path d="M15 13h10M15 19h6" stroke="#0e1a2b" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

function embedSnippet(origin: string): string {
  return `<iframe id="crewbrief" src="${origin}board/#/your-airline?embed=1"
  title="Crew briefings" style="width:100%;border:0;min-height:900px" loading="lazy"></iframe>
<script>
  addEventListener("message", (e) => {
    if (e.origin !== "${new URL(origin).origin}" || e.data?.type !== "crewbrief:height") return;
    document.getElementById("crewbrief").style.height = e.data.height + "px";
  });
</script>`;
}

function Landing() {
  const [demos, setDemos] = useState<BoardSummary[]>([]);
  useEffect(() => {
    loadIndex("./boards/").then(setDemos).catch(() => setDemos([]));
  }, []);
  const origin = new URL(".", window.location.href).href;
  const firstDemo = demos[0]?.slug ?? "northline-demo";
  const cta = PRODUCT.earlyAccessUrl;

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-bar">
        <div className="site-bar__inner">
          <a className="brandmark" href="./"><Mark />{PRODUCT.name}</a>
          <nav aria-label="Primary">
            <a href="#demo">Live demo</a>
            <a href="#how">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1}>
        <section className="hero">
          <div className="hero__inner">
            <div>
              <p className="eyebrow">For vAMSYS virtual airlines</p>
              <h1>A briefing for <em>every flight</em> on your schedule.</h1>
              <p className="lede">
                {PRODUCT.name} turns your vAMSYS schedule into a live briefing board for your pilots: weather and runway
                winds at both ends, a fuel estimate by phase and an approach card. It refreshes every 20 minutes, in your colours.
              </p>
              <div className="hero__actions">
                <a className="button" href={`board/#/${firstDemo}`}>See a live demo</a>
                {cta ? <a className="button button--ghost" href={cta} rel="noopener">Get early access</a> : <a className="button button--ghost" href="#pricing">See pricing</a>}
              </div>
            </div>
            <div className="strip" aria-hidden="true">
              <div className="strip__call"><small>Flight</small><b>NLV109</b>B738</div>
              <div><small>Route</small><b>EHAM → LPPT</b>996 nm · 2h 49m</div>
              <div><small>Fuel</small><b>8,208 kg</b>trip + 5% + 45 min</div>
              <div><small>Weather</small><b>Live</b>both ends</div>
              <div><small>Runway</small><b>By wind</b>favoured end</div>
              <div><small>Gate 5 nm</small><b>1,989 ft</b><span className="warn">3° · 145 kt</span></div>
            </div>
          </div>
        </section>

        <section className="section" id="demo">
          <p className="eyebrow">Live demo</p>
          <h2>Open a real board</h2>
          <p className="lede">Both boards update with live weather every 20 minutes. Crossroads is a real vAMSYS airline; Northline is a sample schedule.</p>
          <div className="demos">
            {demos.length ? demos.map((d) => (
              <a key={d.slug} className="demo" href={`board/#/${d.slug}`} style={{ ["--demo-accent" as string]: safeAccent(d.accent) }}>
                <h3>{d.name}</h3>
                <div className="demo__stats"><span>{d.routes} routes</span><span>{d.airports} airports</span><span>{d.types} aircraft types</span></div>
                <span className="demo__go">Open board →</span>
              </a>
            )) : <p className="muted">Demo boards are loading.</p>}
          </div>
        </section>

        <div className="band">
          <section className="section">
            <p className="eyebrow">What your pilots get</p>
            <h2>Everything to start a flight, on one page</h2>
            <div className="features">
              <div className="feature"><h3>Live weather</h3><p className="muted">METAR, TAF and flight category for every airport on your network, decoded into plain wind, visibility and cloud.</p></div>
              <div className="feature"><h3>Runway winds</h3><p className="muted">Headwind, tailwind and crosswind for every runway end, with the favoured runway picked for them. Data for 20,000+ airports.</p></div>
              <div className="feature"><h3>Fuel by phase</h3><p className="muted">Taxi, climb, cruise and descent fuel with contingency and reserve, for 60+ aircraft types. Use your own figures if you prefer.</p></div>
              <div className="feature"><h3>Approach card</h3><p className="muted">3° glide-path gates at 10, 5, 3 and 1 nm with heights, altitudes and approach speed for the favoured runway.</p></div>
            </div>
          </section>
        </div>

        <section className="section" id="how">
          <p className="eyebrow">How it works</p>
          <h2>Live in an afternoon</h2>
          <ol className="steps">
            <li><h3>Create a read-only key</h3><p className="muted">In vAMSYS Orwell, add an API client with the <code>ops:read</code> scope. It can read your schedule and nothing else.</p></li>
            <li><h3>We connect it</h3><p className="muted">We set up a private handover for the key and add your colours, logo and aircraft. Your board is built within 20 minutes.</p></li>
            <li><h3>Share it with pilots</h3><p className="muted">Link it from your pilot handbook or Discord, or embed it on your own website with two lines of code.</p></li>
          </ol>
          <h3 style={{ marginTop: 32, marginBottom: 10 }}>Embed code</h3>
          <code className="snippet">{embedSnippet(origin)}</code>
        </section>

        <div className="band">
          <section className="section" id="pricing">
            <p className="eyebrow">Pricing</p>
            <h2>One flat monthly price per airline</h2>
            <p className="lede">Pilots never pay. Cancel any time.</p>
            <div className="prices">
              {PRODUCT.plans.map((p) => (
                <div key={p.name} className={`price${p.featured ? " price--featured" : ""}`}>
                  {p.badge ? <span className="badge">{p.badge}</span> : null}
                  <h3>{p.name}</h3>
                  <div className="price__amount">${p.price}<small> / month</small></div>
                  <ul>{p.points.map((pt) => <li key={pt}>{pt}</li>)}</ul>
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="section" id="faq">
          <p className="eyebrow">Questions</p>
          <h2>FAQ</h2>
          <div className="faq">
            <details><summary>What do you do with our pilots' data?</summary><p>Nothing. {PRODUCT.name} reads only your fleet, airports and routes. It never requests pilots, PIREPs, live flights or statistics.</p></details>
            <details><summary>Is the fuel figure good enough to fly with?</summary><p>It's a quick-look planning estimate from typical published fuel flows, so pilots know roughly what they need before they open SimBrief. Pilots should still dispatch with SimBrief or their aircraft's own planner.</p></details>
            <details><summary>Which simulators does it work with?</summary><p>Any. Weather is real-world, so it matches MSFS, X-Plane or P3D with live weather on.</p></details>
            <details><summary>Our fleet uses custom codes like "A20N-LEAP".</summary><p>No problem. We map your fleet codes to aircraft types when we set you up, and you can supply your own fuel figures for any type.</p></details>
            <details><summary>Do you support phpVMS or other platforms?</summary><p>vAMSYS first. Tell us what you use and we'll prioritise the next platform by demand.</p></details>
            <details><summary>What if vAMSYS or the weather service is down?</summary><p>Your board keeps its last good version and catches up on the next refresh. One airline's problem never affects another's board.</p></details>
          </div>
        </section>

        <div className="cta-band">
          <section className="section">
            <div>
              <h2>Give your pilots a better start</h2>
              <p>Open a demo board now, or get in touch to set up yours.</p>
            </div>
            <div className="hero__actions">
              <a className="button" href={`board/#/${firstDemo}`}>See a live demo</a>
              {cta ? <a className="button button--ghost" href={cta} rel="noopener">Get early access</a> : null}
            </div>
          </section>
        </div>
      </main>

      <footer className="site-foot">
        <p>{PRODUCT.name} is for flight simulation only and must never be used for real-world navigation.</p>
        <p>Weather from aviationweather.gov. Runway data from OurAirports (public domain). Not affiliated with vAMSYS, Microsoft, Laminar Research or any airline.</p>
      </footer>
    </>
  );
}

const root = document.getElementById("root");
if (root) createRoot(root).render(<StrictMode><Landing /></StrictMode>);
