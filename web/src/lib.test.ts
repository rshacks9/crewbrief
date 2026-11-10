import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  boardHash,
  componentText,
  isBoard,
  isCrew,
  isSlug,
  kgToLb,
  loadBoard,
  onAccent,
  parseBoardHash,
  routeKey,
  safeAccent,
  windText,
  type Board,
  type Crew,
} from "./lib";

const read = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf-8"));

describe("committed demo boards", () => {
  for (const slug of ["crossroads", "northline-demo"]) {
    it(`${slug}: board and crew match and every route has a briefing`, () => {
      const board: unknown = read(`../public/boards/${slug}/board.json`);
      const crew: unknown = read(`../public/boards/${slug}/crew.json`);
      expect(isBoard(board)).toBe(true);
      expect(isCrew(crew)).toBe(true);
      const b = board as Board;
      const c = crew as Crew;
      for (const route of b.routes) {
        const plans = c.plans[routeKey(route)];
        expect(plans, routeKey(route)).toBeTruthy();
        for (const type of route.types) expect(plans?.[type], `${routeKey(route)} ${type}`).toBeTruthy();
      }
      for (const icao of Object.keys(b.airports)) expect(c.airports[icao]?.runways.length, icao).toBeGreaterThan(0);
    });
  }

  it("index lists the public demos", () => {
    const index = read("../public/boards/index.json");
    expect(index.boards.map((b: { slug: string }) => b.slug).sort()).toEqual(["crossroads", "northline-demo"]);
  });
});

describe("validation and safety", () => {
  it("only accepts plain slugs and #rrggbb accents", () => {
    expect(isSlug("northline-demo")).toBe(true);
    expect(isSlug("../secrets")).toBe(false);
    expect(isSlug("UPPER")).toBe(false);
    expect(safeAccent("#2a6fb7")).toBe("#2a6fb7");
    expect(safeAccent("red;background:url(x)")).toBe("#1f6f5c");
    expect(safeAccent(null)).toBe("#1f6f5c");
  });

  it("picks readable text on light and dark accents", () => {
    expect(onAccent("#0e1a2b")).toBe("#ffffff");
    expect(onAccent("#f5d000")).toBe("#10151c");
  });

  it("loadBoard refuses unknown slugs and bad shapes", async () => {
    const never = (async () => { throw new Error("should not fetch"); }) as unknown as typeof fetch;
    await expect(loadBoard("./", "../x", never)).rejects.toThrow("unknown airline");
    const junk = (async () => new Response("{}", { status: 200 })) as typeof fetch;
    await expect(loadBoard("./", "ok-air", junk)).rejects.toThrow("unexpected shape");
    const missing = (async () => new Response("", { status: 404 })) as typeof fetch;
    await expect(loadBoard("./", "ok-air", missing)).rejects.toThrow("404");
  });
});

describe("board hash routing", () => {
  it("round-trips airline, route, aircraft and embed", () => {
    const loc = parseBoardHash("#/northline-demo?route=NLV109&aircraft=B738&embed=1");
    expect(loc).toEqual({ slug: "northline-demo", route: "NLV109", aircraft: "B738", embed: true });
    expect(boardHash(loc)).toBe("#/northline-demo?route=NLV109&aircraft=B738&embed=1");
    expect(parseBoardHash("")).toEqual({ slug: "", route: "", aircraft: "", embed: false });
    expect(boardHash({ slug: "a-air", route: "", aircraft: "A20N-LEAP", embed: false })).toBe("#/a-air?aircraft=A20N-LEAP");
  });
});

describe("formatting", () => {
  it("formats wind, components and weights", () => {
    expect(kgToLb(1000)).toBe(2205);
    expect(windText({ direction_deg: 50, speed_kt: 12.4, gust_kt: 22, variable: false })).toBe("050° 12 kt gusting 22");
    expect(windText({ direction_deg: 0, speed_kt: 0, variable: false })).toBe("Calm");
    expect(componentText({ headwind_kt: 9, tailwind_kt: 0, crosswind_kt: 3, crosswind_from: "left" })).toBe("9 kt head, 3 kt cross from left");
    expect(componentText(null)).toBe("—");
  });
});
