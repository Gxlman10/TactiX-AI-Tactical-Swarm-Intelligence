import {
  timeOf,
  type Context,
  type MatchEvent,
  type Point,
} from "../match/model";
import type { FixtureSummary, Metric, NetworkEdge, Pattern } from "./contracts";
import type { MetricsResponse } from "../live/api";

export const metricKeys = [
  "possession_pct",
  "pass_accuracy_pct",
  "field_tilt",
  "ppda",
  "xg_like",
  "progressive_passes",
  "pressure_success_pct",
  "high_recoveries",
] as const;
export function validCut(
  response: MetricsResponse | null | undefined,
  matchId: string,
  revision: number,
  second: number,
): response is MetricsResponse {
  return Boolean(
    response &&
    response.revision === revision &&
    response.snapshot.match_id === matchId &&
    response.at_second >= 0 &&
    response.at_second <= second,
  );
}
export function resolveEvidence(
  ids: string[],
  events: MatchEvent[],
  matchId: string,
  cutoff: number,
) {
  const index = new Map(
    events
      .filter((event) => event.match_id === matchId && timeOf(event) <= cutoff)
      .map((event) => [event.id, event]),
  );
  const unique = [...new Set(ids)];
  return {
    events: unique.flatMap((id) => (index.get(id) ? [index.get(id)!] : [])),
    missing: unique.filter((id) => !index.has(id)),
  };
}
export function edgeIds(
  edge: NetworkEdge,
  metric: Metric | undefined,
  events: MatchEvent[],
  teamId: string,
  matchId: string,
  cutoff: number,
) {
  return resolveEvidence(
    metric?.evidence?.event_ids ?? [],
    events,
    matchId,
    cutoff,
  )
    .events.filter(
      (event) =>
        event.team_id === teamId &&
        event.type === "pass" &&
        event.outcome === "success" &&
        event.end &&
        event.player_id === edge.from_player_id &&
        event.related_player_id === edge.to_player_id,
    )
    .map((event) => event.id);
}
export function nodeIds(
  playerId: string,
  metric: Metric | undefined,
  events: MatchEvent[],
  teamId: string,
  matchId: string,
  cutoff: number,
) {
  return resolveEvidence(
    metric?.evidence?.event_ids ?? [],
    events,
    matchId,
    cutoff,
  )
    .events.filter(
      (event) =>
        event.team_id === teamId &&
        event.type === "pass" &&
        event.outcome === "success" &&
        (event.player_id === playerId || event.related_player_id === playerId),
    )
    .map((event) => event.id);
}
export function metricText(metric: Metric | undefined, locale: string) {
  if (!metric || !Number.isFinite(metric.value)) return "—";
  return (
    new Intl.NumberFormat(locale, {
      maximumFractionDigits: metric.unit === "count" ? 0 : 2,
    }).format(metric.value) + (metric.unit === "%" ? "%" : "")
  );
}
export function pattern(value: unknown): Pattern | null {
  if (!value || typeof value !== "object") return null;
  const p = value as Pattern;
  return typeof p.match_id === "string" &&
    Array.isArray(p.event_ids) &&
    p.event_ids.every((id) => typeof id === "string") &&
    Array.isArray(p.possession_ids) &&
    Number.isFinite(p.loss_second) &&
    Number.isFinite(p.goal_second) &&
    p.goal_second >= p.loss_second &&
    Number.isFinite(p.elapsed_seconds)
    ? p
    : null;
}
export function occurrences(
  context: Context | null,
  fixtures: FixtureSummary[],
  matchId: string,
  cutoff: number,
) {
  const historical = Object.entries(context?.historical_patterns ?? {}).flatMap(
    ([fixtureId, values]) =>
      Array.isArray(values)
        ? values.flatMap((value) => {
            const p = pattern(value);
            const fixture = fixtures.find((f) => f.id === fixtureId);
            return p && fixture
              ? [{ pattern: p, fixture, fixtureId, current: false }]
              : [];
          })
        : [],
  );
  historical.sort(
    (a, b) =>
      a.fixture.matchday - b.fixture.matchday ||
      a.pattern.goal_second - b.pattern.goal_second,
  );
  const live = pattern(context?.climax);
  const rows: {
    pattern: Pattern;
    fixture?: FixtureSummary;
    fixtureId?: string;
    current: boolean;
  }[] = historical;
  if (live && live.match_id === matchId && live.goal_second <= cutoff)
    rows.push({ pattern: live, current: true });
  return rows;
}
/** Opposite directions curve on opposite sides; arrows stop before the node. */
export function edgePath(a: Point, b: Point) {
  const dx = b.x - a.x,
    dy = b.y - a.y,
    length = Math.hypot(dx, dy);
  if (length < 1) return "";
  const trim = Math.min(26, length / 4),
    ux = dx / length,
    uy = dy / length;
  return `M${a.x + ux * trim},${a.y + uy * trim} Q${(a.x + b.x) / 2 - uy * 28},${(a.y + b.y) / 2 + ux * 28} ${b.x - ux * trim},${b.y - uy * trim}`;
}
