import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fixture, timeOf } from "../match/model";
import {
  MatchApi,
  readReplay,
  type ReplayUpdate,
  type MetricsResponse,
} from "./api";
import { LiveSession, metricRows } from "./session";

class Source extends EventTarget {
  closed = false;
  onerror: (() => void) | null = null;
  close() {
    this.closed = true;
  }
  send(type: string, data: unknown) {
    this.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
}
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const id = "00000000-0000-0000-0000-000000000001";
let current: ReplayUpdate;
let sources: Source[];
let calls: string[];
let client: LiveSession;
let failControl: boolean;
let holdMetrics: (() => Promise<Response>) | null;
let lastMetrics: MetricsResponse;
const info = () => ({
  session_id: id,
  scenario: "ashford-demo-v1",
  home_club_id: fixture.teams[0].id,
  away_club_id: fixture.teams[1].id,
  state: current,
});
const fetcher: typeof fetch = async (input, options = {}) => {
  const url = new URL(String(input));
  calls.push(`${options.method ?? "GET"} ${url.pathname}${url.search}`);
  if (options.method === "DELETE") return new Response(null, { status: 204 });
  if (url.pathname.endsWith("/controls")) {
    if (failControl) return json({ detail: "Control rejected" }, 503);
    const control = JSON.parse(String(options.body));
    current = { ...current, events: [] };
    if (control.action === "seek")
      current = {
        ...current,
        revision: current.revision + 1,
        position_seconds: control.second,
        status: "paused",
      };
    if (control.action === "play" || control.action === "pause")
      current = {
        ...current,
        status: control.action === "play" ? "playing" : "paused",
      };
    return json(current);
  }
  if (url.pathname.endsWith("/league"))
    return json({
      season: fixture.season,
      clubs: fixture.teams.map((team) => ({
        ...team,
        tactical_identity: { formation: team.formation },
        squad: team.players,
      })),
    });
  if (url.pathname.endsWith("/events")) {
    if (Number(url.searchParams.get("revision")) !== current.revision)
      return json({ detail: "Stale revision" }, 409);
    const visible = fixture.events
      .map((event, index) => ({ sequence: index + 1, event }))
      .filter((item) => timeOf(item.event) <= current.position_seconds);
    const cursor = Number(url.searchParams.get("after_sequence"));
    const events = visible.filter((item) => item.sequence > cursor).slice(0, 2);
    const last = events.at(-1)?.sequence ?? cursor;
    return json({
      revision: current.revision,
      events,
      next_sequence: last + 1,
      has_more: visible.some((item) => item.sequence > last),
    });
  }
  if (url.pathname.endsWith("/metrics")) {
    if (holdMetrics) return holdMetrics();
    lastMetrics = {
      revision: current.revision,
      at_second: Math.floor(current.position_seconds),
      snapshot: {
        match_id: current.match_id,
        teams: [
          {
            team_id: fixture.teams[1].id,
            values: [{ key: "shots", value: 13 }],
          },
          { team_id: fixture.teams[0].id, values: [] },
        ],
      },
    };
    return json(lastMetrics);
  }
  if (url.pathname.endsWith("/context"))
    return json({
      ...fixture.context,
      revision: current.revision,
      at_second: Math.floor(current.position_seconds),
      climax: current.position_seconds >= 3720 ? fixture.context.climax : null,
    });
  return json(info());
};
beforeEach(() => {
  vi.useFakeTimers();
  sources = [];
  calls = [];
  failControl = false;
  holdMetrics = null;
  current = {
    match_id: fixture.match_id,
    revision: 0,
    position_seconds: 0,
    duration_seconds: 5400,
    speed: 4,
    status: "paused",
    score: [0, 0],
    events: [],
  };
  client = new LiveSession(
    new MatchApi("https://backend.test", fetcher),
    () => {
      const source = new Source();
      sources.push(source);
      return source as unknown as EventSource;
    },
  );
});
afterEach(() => {
  client.dispose();
  vi.useRealTimers();
});

describe("server session integration", () => {
  it("creates a session, seeks by server control, and renders missing metrics as absent", async () => {
    await client.start();
    expect(client.getSnapshot().connection).toBe("connected");
    expect(client.getSnapshot().info?.state.position_seconds).toBe(3660);
    expect(client.getSnapshot().info?.state.revision).toBe(1);
    const rows = metricRows(client.getSnapshot().metrics, fixture.teams);
    expect(rows[0].shots).toBeUndefined();
    expect(rows[1].shots).toBe(13);
  });
  it("rebuilds paginated history, deduplicates SSE overlap, and excludes future events", async () => {
    current.position_seconds = 3720;
    await client.start(id);
    expect(client.getSnapshot().events).toHaveLength(10);
    expect(calls.filter((call) => call.includes("/events?"))).toHaveLength(5);
    sources[0].send("replay", {
      ...current,
      events: [
        ...client.getSnapshot().events,
        { sequence: 99, event: fixture.events.at(-1) },
      ],
    });
    expect(client.getSnapshot().events).toHaveLength(10);
    expect(
      new Set(client.getSnapshot().events.map((item) => item.sequence)).size,
    ).toBe(10);
  });
  it("clears future goal, metrics and context immediately on reset and ignores delayed old metrics", async () => {
    current.position_seconds = 3720;
    await client.start(id);
    let release!: (response: Response) => void;
    const stale = structuredClone(lastMetrics);
    holdMetrics = () =>
      new Promise((resolve) => {
        release = resolve;
      });
    await vi.advanceTimersByTimeAsync(1000);
    current = {
      ...current,
      revision: 1,
      position_seconds: 3719,
      score: [1, 0],
      events: [],
    };
    sources[0].send("reset", current);
    expect(client.getSnapshot().metrics).toBeNull();
    expect(client.getSnapshot().context).toBeNull();
    expect(client.getSnapshot().events).toEqual([]);
    holdMetrics = null;
    release(json(stale));
    await vi.advanceTimersByTimeAsync(0);
    expect(client.getSnapshot().metrics?.revision).not.toBe(0);
    expect(
      client.getSnapshot().events.every((item) => timeOf(item.event) <= 3719),
    ).toBe(true);
    await vi.advanceTimersByTimeAsync(1000);
    expect(client.getSnapshot().metrics?.revision).toBe(1);
    expect(client.getSnapshot().context?.climax).toBeNull();
  });
  it("never seeks optimistically when a server rejects the control", async () => {
    await client.start();
    failControl = true;
    await client.control({ action: "seek", second: 3720 });
    expect(client.getSnapshot().info?.state.position_seconds).toBe(3660);
    expect(client.getSnapshot().busy).toBe(false);
    expect(client.getSnapshot().error).toBe("Control rejected");
  });
  it("reconciles a disconnected viewer at the latest revision with a fresh stream", async () => {
    await client.start();
    sources[0].onerror!();
    expect(client.getSnapshot().connection).toBe("reconnecting");
    expect(sources[0].closed).toBe(true);
    current = {
      ...current,
      revision: 2,
      position_seconds: 3720,
      score: [1, 1],
    };
    await vi.advanceTimersByTimeAsync(5000);
    expect(sources).toHaveLength(2);
    expect(client.getSnapshot().connection).toBe("connected");
    expect(client.getSnapshot().info?.state.revision).toBe(2);
    expect(client.getSnapshot().events).toHaveLength(10);
  });
  it("polls metrics at bounded cadence instead of on every replay tick", async () => {
    await client.start();
    const count = () =>
      calls.filter((call) => call.includes("/metrics?")).length;
    expect(count()).toBe(1);
    for (let i = 0; i < 20; i++)
      sources[0].send("replay", { ...current, position_seconds: 3660 + i });
    expect(count()).toBe(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(count()).toBe(2);
  });
  it("releases owned sessions on disposal but leaves a joined session active", async () => {
    await client.start();
    client.dispose();
    expect(sources[0].closed).toBe(true);
    expect(calls.filter((call) => call.startsWith("DELETE"))).toHaveLength(1);
    await client.start(id);
    client.dispose();
    expect(calls.filter((call) => call.startsWith("DELETE"))).toHaveLength(1);
  });
  it("closes at completion and when the server deletes the session", async () => {
    await client.start();
    sources[0].send("replay", {
      ...current,
      status: "finished",
      position_seconds: 5400,
    });
    expect(sources[0].closed).toBe(true);
    await client.start(id);
    sources[1].send("closed", { session_id: id });
    expect(client.getSnapshot().connection).toBe("closed");
    expect(sources[1].closed).toBe(true);
  });
  it("rejects malformed SSE payloads before applying them", () => {
    expect(() => readReplay('{"revision":0}')).toThrow();
    expect(() =>
      readReplay(
        JSON.stringify({ ...current, events: [{ sequence: 1, event: {} }] }),
      ),
    ).toThrow();
  });
  it("does not fetch historical fixtures outside the session evidence", async () => {
    await client.start(id);
    await expect(
      client.history("unrelated-fixture", new AbortController().signal),
    ).rejects.toThrow("not part of this session");
    expect(calls.some((call) => call.includes("/history/"))).toBe(false);
  });
  it("normalizes historical MatchResult frames into source events", async () => {
    const historyFetch: typeof fetch = async (input, options) =>
      String(input).includes("/history/")
        ? json({
            match_id: "past",
            home_club_id: fixture.teams[0].id,
            away_club_id: fixture.teams[1].id,
            frames: [{ events: [{ ...fixture.events[0], match_id: "past" }] }],
          })
        : fetcher(input, options);
    client.dispose();
    client = new LiveSession(
      new MatchApi("https://backend.test", historyFetch),
      () => new Source() as unknown as EventSource,
    );
    await client.start(id);
    const artifact = await client.history(
      Object.keys(fixture.context.historical_patterns)[0],
      new AbortController().signal,
    );
    expect(artifact.events).toHaveLength(1);
    expect(artifact.events[0].match_id).toBe("past");
  });
  it("rejects a historical response from a revision that was replaced while loading", async () => {
    let release!: (response: Response) => void;
    const slow: typeof fetch = async (input, options) =>
      String(input).includes("/history/")
        ? new Promise((resolve) => {
            release = resolve;
          })
        : fetcher(input, options);
    client.dispose();
    client = new LiveSession(
      new MatchApi("https://backend.test", slow),
      () => new Source() as unknown as EventSource,
    );
    await client.start(id);
    const fixtureId = Object.keys(fixture.context.historical_patterns)[0];
    const pending = client.history(fixtureId, new AbortController().signal);
    await client.control({ action: "seek", second: 3719 });
    release(json({ match_id: fixtureId, events: [] }));
    await expect(pending).rejects.toThrow("discard historical response");
  });
  it("releases a newly created session even when its response arrives after disposal", async () => {
    let release!: (response: Response) => void;
    client.dispose();
    const slowFetch: typeof fetch = async (input, options) => {
      if (options?.method === "POST")
        return new Promise((resolve) => {
          release = resolve;
        });
      return fetcher(input, options);
    };
    client = new LiveSession(new MatchApi("https://backend.test", slowFetch));
    const pending = client.start();
    client.dispose();
    release(json(info()));
    await pending;
    expect(client.getSnapshot().info).toBeNull();
    expect(calls.filter((call) => call.startsWith("DELETE"))).toHaveLength(1);
  });
  it("keeps the new revision when a delayed old replay arrives", async () => {
    current.position_seconds = 3720;
    await client.start(id);
    const stale = structuredClone(current);
    current = {
      ...current,
      revision: 1,
      position_seconds: 3719,
      score: [1, 0],
    };
    sources[0].send("reset", current);
    sources[0].send("replay", {
      ...stale,
      events: [{ sequence: 10, event: fixture.events[9] }],
    });
    expect(client.getSnapshot().info?.state.revision).toBe(1);
    expect(client.getSnapshot().info?.state.score).toEqual([1, 0]);
    expect(
      client.getSnapshot().events.every((item) => timeOf(item.event) <= 3719),
    ).toBe(true);
  });
});
