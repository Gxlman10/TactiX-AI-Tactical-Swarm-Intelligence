import type { TeamAnalysis, FixtureSummary } from "../analyst/contracts";
import type { MatchEvent, Team, Context } from "../match/model";

export interface ReplayUpdate {
  match_id: string;
  revision: number;
  position_seconds: number;
  duration_seconds: number;
  speed: number;
  status: "paused" | "playing" | "finished";
  score: [number, number];
  events: { sequence: number; event: MatchEvent }[];
}
export interface SessionInfo {
  session_id: string;
  scenario: string;
  home_club_id: string;
  away_club_id: string;
  state: ReplayUpdate;
}
export interface League {
  season: string;
  fixtures?: FixtureSummary[];
  clubs: {
    id: string;
    name: string;
    city: string;
    tactical_identity: { formation: string };
    squad: Team["players"];
  }[];
}
export interface EventPage {
  revision: number;
  events: ReplayUpdate["events"];
  next_sequence: number;
  has_more: boolean;
}
export interface MetricsResponse {
  revision: number;
  at_second: number;
  snapshot: {
    match_id: string;
    teams: TeamAnalysis[];
  };
}
export type Control =
  | { action: "play" | "pause" }
  | { action: "seek"; second: number }
  | { action: "speed"; speed: number };
export type ApiContext = Context & { revision: number; at_second: number };
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public retryAfter = 2,
  ) {
    super(message);
  }
}
export class MatchApi {
  constructor(
    public base = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, ""),
    private fetcher: typeof fetch = (input, options) => fetch(input, options),
  ) {}
  url(path: string) {
    return `${this.base}/api/v1${path}`;
  }
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await this.fetcher(this.url(path), {
      ...options,
      headers: options.body
        ? { "Content-Type": "application/json", ...options.headers }
        : options.headers,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(
        response.status,
        typeof body?.detail === "string"
          ? body.detail
          : `HTTP ${response.status}`,
        Number(response.headers.get("Retry-After")) || 2,
      );
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
  session(id: string, signal?: AbortSignal) {
    return this.request<SessionInfo>(`/sessions/${encodeURIComponent(id)}`, {
      signal,
    });
  }
  create() {
    return this.request<SessionInfo>("/sessions", {
      method: "POST",
      body: JSON.stringify({ scenario: "ashford-demo-v1", speed: 4 }),
    });
  }
  remove(id: string) {
    return this.request<void>(`/sessions/${id}`, {
      method: "DELETE",
      keepalive: true,
    });
  }
  control(id: string, control: Control) {
    return this.request<ReplayUpdate>(`/sessions/${id}/controls`, {
      method: "POST",
      signal: AbortSignal.timeout(20000),
      body: JSON.stringify(control),
    });
  }
}

export function readReplay(data: string): ReplayUpdate {
  const value: ReplayUpdate = JSON.parse(data);
  if (
    !value ||
    !Number.isInteger(value.revision) ||
    value.revision < 0 ||
    !Number.isFinite(value.position_seconds) ||
    !Number.isFinite(value.duration_seconds) ||
    !Number.isFinite(value.speed) ||
    !["paused", "playing", "finished"].includes(value.status) ||
    !Array.isArray(value.events) ||
    !Array.isArray(value.score) ||
    value.score.length !== 2 ||
    !value.score.every(Number.isFinite)
  )
    throw new Error("Invalid replay response");
  for (const item of value.events) {
    if (
      !Number.isInteger(item.sequence) ||
      item.sequence < 1 ||
      !item.event ||
      typeof item.event.id !== "string" ||
      !Number.isFinite(item.event.minute) ||
      !Number.isFinite(item.event.second) ||
      !Number.isFinite(item.event.start?.x) ||
      !Number.isFinite(item.event.start?.y)
    )
      throw new Error("Invalid replay event");
  }
  return value;
}
